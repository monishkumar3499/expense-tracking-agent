import json
import re
from typing import TypedDict, List, Literal, Union
from datetime import date

# Official LangGraph & LangChain imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama

from config import settings
from finance_tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, goal_progress, tax_summary,
                   get_recent_transactions)
from sqlalchemy.orm import Session
from logs import log_manager

# --- COMPANY-LEVEL CONFIGURATION ---
  
TOOLS_DEFINITION = """
1. get_spending_summary(period: str) - Periods: 'latest' (for just uploaded items), 'today', 'this_week', 'this_month', 'last_month', 'last_3_months', 'this_year'
2. get_monthly_trend(months: int) - Default 6 months
3. get_budget_status() - Current month budget utilization
4. detect_anomalies_tool() - Find unusual high spending
5. get_cash_flow_forecast(days: int) - Forecast (30, 60, or 90 days)
6. get_goal_progress() - Savings goals status
7. get_tax_summary() - Current financial year tax-deductible summary
8. get_recent_transactions(limit: int) - Get the very last added transactions (use after uploads)
"""

SYSTEM_INSTRUCTIONS = f"""You are 'Finn', a high-fidelity AI Financial Intelligence Agent. 
Your mission is to provide rigorous, data-backed financial research from the user's personal database.

### OPERATIONAL FRAMEWORK:
1. **INTENT AUDIT**: Carefully analyze the user's request. Is it about current spending, long-term trends, or budget status?
2. **DATA GATHERING**: You are FORBIDDEN from generating numbers ($ or ₹) from internal memory. You MUST execute the most relevant tool from the list below.
3. **SYNTHESIS**: Once you receive 'TOOL_RESULT', you must structure your final answer as a 'Financial Research Summary'.

### CORE PROTOCOLS:
- **UPLOAD AWARENESS**: If the user asks about "my expenses" or "what I just added", you MUST prioritize `get_recent_transactions(limit=10)` to find the newly ingested data, regardless of the transaction date.
- **ZERO HALLUCINATION**: If the 'TOOL_RESULT' is empty or missing, explicitly state 0. NEVER guess.
- **TEMPORAL PIVOT**: If 'this_month' results are 0, you must assume the user means 'all-time' or 'recent history'. Proactively call `get_recent_transactions`.
- **TOOL SYNTAX**: Your only valid action when data is missing is exactly: CALL: tool_name({{"param": "val"}})

### AVAILABLE INTELLIGENCE TOOLS:
{TOOLS_DEFINITION}
"""

# --- STATE DEFINITION ---

class AgentState(TypedDict):
    """The state of the graph session."""
    messages: List[BaseMessage]
    db: Session
    error: Union[str, None]
    iterations: int

# --- NODES ---

def call_model(state: AgentState):
    """Reasoning node: Determines intent and decides on next action."""
    print(f"[GRAPH-NODE] Reasoning... (Iteration {state.get('iterations', 0) + 1})")
    log_manager.push("Analyzing financial intent...")
    
    llm = ChatOllama(
        model=settings.model_name,
        base_url=settings.ollama_url,
        temperature=0.1
    )
    
    # Prepend System message if not present
    if not any(isinstance(m, SystemMessage) for m in state["messages"]):
        state["messages"].insert(0, SystemMessage(content=SYSTEM_INSTRUCTIONS))
    
    response = llm.invoke(state["messages"])
    
    content = re.sub(r"^(Assistant:\s*)", "", response.content, flags=re.I)

    # --- INTENT-BASED AUTO-CORRECTION ---
    # Only auto-correct on the VERY FIRST reasoning pass to avoid loops
    user_query = str(state["messages"][-1].content).lower()
    financial_keywords = ["spend", "expense", "transaction", "how much", "total", "category", "biggest", "bill", "mình"]
    is_financial = any(k in user_query for k in financial_keywords)
    is_upload = any(k in user_query for k in ["upload", "just added", "new data", "recent", "what's this"])
    
    if is_financial and "CALL:" not in content and state.get("iterations", 0) == 1:
        if is_upload:
            print("[GRAPH-GATE] Upload intent detected. Calling latest summary.")
            content = "CALL: get_spending_summary({\"period\": \"latest\"})"
        else:
            print("[GRAPH-GATE] Financial intent detected without tool call. Auto-correcting.")
            content = "CALL: get_spending_summary({\"period\": \"this_month\"})"
    
    # --- HALLUCINATION GATE ---
    has_tool_result = any("TOOL_RESULT" in str(m.content) for m in state["messages"])
    contains_money = bool(re.search(r"(\$|₹|\d+\,\d+)", content))
    
    # Only force tool usage if we haven't successfully results yet
    if contains_money and not has_tool_result and "CALL:" not in content and state.get("iterations", 0) == 1:
        print("[GRAPH-GATE] Hallucination detected! Forcing tool usage.")
        content = "CALL: get_recent_transactions({})"
    
    return {
        "messages": state["messages"] + [AIMessage(content=content)],
        "iterations": state.get("iterations", 0) + 1
    }

def call_tool(state: AgentState):
    """Action node: Executes the identified financial tool with loop protection."""
    last_message = state["messages"][-1].content
    match = re.search(r"CALL:\s*(\w+)(?:\((.*)\))?", last_message)
    
    if not match:
        return {"messages": state["messages"] + [AIMessage(content="Internal error: Tool call parsing failed.")], "error": "Parse Error"}
    
    fn_name = match.group(1).strip().lower()
    fn_args_raw = match.group(2) if match.group(2) else "{}"
    
    # --- LOOP PROTECTION ---
    history_text = " ".join([str(m.content) for m in state["messages"]])
    if f"TOOL_RESULT:" in history_text and f"CALL: {fn_name}" in history_text:
        print(f"[GRAPH-PROTECT] Loop detected for {fn_name}. Forcing summary.")
        msg = SystemMessage(content="CRITICAL: You already have the data in a TOOL_RESULT above. DO NOT reply with a CALL. Talk to the user now.")
        return {"messages": state["messages"] + [msg]}

    # Robust JSON parsing
    try:
        clean_args = re.search(r"\{.*\}", fn_args_raw)
        fn_args = json.loads(clean_args.group(0)) if clean_args else {}
    except:
        fn_args = {}

    print(f"[GRAPH-NODE] Executing Tool: {fn_name} with {fn_args}")
    log_manager.push(f"Querying financial engine: {fn_name.replace('get_', '').replace('_', ' ')}...")
    
    # Internal tool mapping
    db = state["db"]
    try:
        if fn_name == "get_spending_summary": res = spending_summary(db, fn_args.get("period", "this_month"))
        elif fn_name == "get_monthly_trend": res = monthly_trend(db, fn_args.get("months", 6))
        elif fn_name == "get_budget_status": res = budget_status(db)
        elif fn_name in ["detect_anomalies_tool", "detect_anomalies"]: res = detect_anomalies(db)
        elif fn_name == "get_cash_flow_forecast": res = cash_flow_forecast(db, fn_args.get("days", 30))
        elif fn_name == "get_goal_progress": res = goal_progress(db)
        elif fn_name == "get_tax_summary": res = tax_summary(db)
        elif fn_name == "get_recent_transactions": res = get_recent_transactions(db, fn_args.get("limit", 5))
        else: res = {"error": f"Capability '{fn_name}' not discovered."}
    except Exception as e:
        res = {"error": str(e)}

    print(f"[GRAPH-DATA] Tool Output: {str(res)[:200]}...")
    
    # Using HumanMessage for result often works better for small models as they react more to 'User' input
    result_msg = HumanMessage(content=f"TOOL_RESULT: {json.dumps(res)}")
    
    return {"messages": state["messages"] + [result_msg]}

def call_summarizer(state: AgentState):
    """Summarization node: Focuses solely on explaining the TOOL_RESULT to the user."""
    print("[GRAPH-NODE] Summarizing data for user...")
    log_manager.push("Summarizing results...")
    
    llm = ChatOllama(
        model=settings.model_name,
        base_url=settings.ollama_url,
        temperature=0.1
    )
    
    summary_prompt = """You are a Financial Research Analyst.
    INSTRUCTION: Provide a 'Financial Intelligence Summary' based on the TOOL_RESULT.
    
    STRUCTURE:
    1. **Overview**: Total amount and count.
    2. **Insight**: Breakdown of categories or top merchants with specific INR (₹) values.
    3. **Conclusion**: 1 sentence on health/trend.
    
    STRICT: Use ONLY TOOL_RESULT values. Bold all currency values."""
    
    # We only send the original query and the tool results to keep it focused
    history_messages = [m for m in state["messages"] if isinstance(m, (HumanMessage, SystemMessage)) and "TOOL_RESULT" in str(m.content)]
    user_query = [m for m in state["messages"] if isinstance(m, HumanMessage) and "TOOL_RESULT" not in str(m.content)][-1]
    
    messages = [
        SystemMessage(content=summary_prompt),
        user_query
    ] + history_messages
    
    response = llm.invoke(messages)
    response.content = re.sub(r"^(Assistant:\s*)", "", response.content, flags=re.I)
    
    return {"messages": state["messages"] + [response]}

# --- EDGES ---

def route_decision(state: AgentState) -> Literal["executor", "summarizer", END]:
    """Conditional edge: Decides the next path."""
    last_message = state["messages"][-1].content
    has_result = any("TOOL_RESULT" in str(m.content) for m in state["messages"])
    
    # 1. Check for iteration limit
    if state.get("iterations", 0) > 4:
        print("[GRAPH-EDGE] Max iterations reached. Cleaning up.")
        return "summarizer" if has_result else END

    # 2. If model wants to call a tool, go to executor
    if "CALL:" in last_message:
        return "executor"
    
    # 3. If we have data, we MUST summarize it
    if has_result:
        return "summarizer"

    return END

# --- GRAPH ASSEMBLY ---

def create_financial_graph():
    """Compiles the official StateGraph for production use."""
    workflow = StateGraph(AgentState)

    workflow.add_node("reasoner", call_model)
    workflow.add_node("executor", call_tool)
    workflow.add_node("summarizer", call_summarizer)

    workflow.set_entry_point("reasoner")
    
    # Logic: Reason -> (Executor or Summarizer or End)
    workflow.add_conditional_edges("reasoner", route_decision)
    # Logic: Executor -> Reasoner (Allow it to see the data and decide if it needs more)
    workflow.add_edge("executor", "reasoner")
    # Logic: Summarizer -> End
    workflow.add_edge("summarizer", END)

    return workflow.compile()

# --- ENTRY POINT ---

class ProductionAgent:
    def __init__(self, db: Session):
        self.db = db
        self.app = create_financial_graph()

    def execute(self, user_query: str, history: list) -> str:
        # Prepare LangChain message format
        messages = []
        for h in history[-6:]:
            if h["role"] == "user": messages.append(HumanMessage(content=h["content"]))
            else: messages.append(AIMessage(content=h["content"]))
        
        messages.append(HumanMessage(content=user_query))

        # Run StateGraph
        inputs = {
            "messages": messages,
            "db": self.db,
            "iterations": 0
        }
        
        try:
            final_state = self.app.invoke(inputs)
            return final_state["messages"][-1].content
        except Exception as e:
            return f"The financial controller encountered a protocol error: {str(e)}"
