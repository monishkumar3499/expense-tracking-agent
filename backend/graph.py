import json
import re
from typing import TypedDict, List, Literal, Union, Optional, Callable
from datetime import date

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings
from finance_tools import (
    spending_summary, monthly_trend, budget_status,
    detect_anomalies, cash_flow_forecast, goal_progress,
    tax_summary, get_recent_transactions, get_recurring_expenses,
    category_breakdown, merchant_insights, daily_spending_pattern,
    detect_recurring
)
from sqlalchemy.orm import Session
from memory.memory_manager import memory_manager
from memory.insights import extract_insight


# ─────────────────────────────────────────────
# SYSTEM PROMPTS  (one per LLM stage)
# ─────────────────────────────────────────────

# ── STAGE 1: INTENT DETECTOR ──────────────────────────────────────────────────
# Role   : Understand what the user wants and map it to exactly one tool call.
# Task   : Output a single CALL line – nothing else.
# Format : CALL: tool_name({"key": "value"})
# ──────────────────────────────────────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = f"""
### ROLE
You are Finn-Intent, a routing engine inside a personal finance assistant.
Your ONLY job is to read the user's message and output the single correct tool call.

### TASK
1. Read the user query carefully.
2. Choose EXACTLY ONE tool from the list below that best answers it.
3. Output ONLY the CALL line – no greetings, no explanation, no markdown.

### OUTPUT FORMAT (STRICT)
Your entire response must be exactly one line:
CALL: tool_name({{"arg": "value"}})

If the query is pure small talk (e.g., "hi", "thanks"), output:
DIRECT: <your short reply here>

### TOOL REFERENCE
| Tool | When to use | Key argument |
|---|---|---|
| get_spending_summary | User asks about expenses, spending, biggest costs, where money went | period: "latest" / "today" / "this_week" / "this_month" / "last_month" / "last_3_months" / "last_6_months" / "this_year" / "all_time" |
| get_monthly_trend | User asks about trends, month-over-month, how spending changed | months: integer (default 6, max 12) |
| get_budget_status | User asks about budget health, limits, overspending, on-track status | (no args) |
| detect_anomalies_tool | User asks about unusual, suspicious, weird, or abnormal transactions | (no args) |
| get_cash_flow_forecast | User asks about forecast, upcoming bills, future expenses | days: 30 / 60 / 90 |
| get_goal_progress | User asks about savings goals, targets, how close they are | (no args) |
| get_tax_summary | User asks about tax, deductions, tax-deductible expenses | (no args) |
| get_recent_transactions | User asks about latest/recent transactions, what was just added | limit: integer (default 10) |
| get_recurring_expenses | User asks about subscriptions, monthly bills, or recurring costs | (no args) |
| get_category_breakdown | User asks for a deep dive into ONE specific category (e.g. "Food") | category: "Food" / "Transport" / etc., months: int (default 3) |
| get_merchant_insights | User asks about where they shop most, top shops, store frequency | top_n: integer (default 10) |
| get_daily_pattern | User asks about which days they spend most on, habits by day | months: integer (default 3) |
| get_detect_recurring | User asks to auto-detect subscriptions or find repeating patterns | (no args) |

### FEW-SHOT EXAMPLES
User: "What are my biggest expenses?"
Output: CALL: get_spending_summary({{"period": "this_month"}})

User: "Show me my spending trend"
Output: CALL: get_monthly_trend({{"months": 6}})

User: "Am I over budget?"
Output: CALL: get_budget_status({{}})

User: "Any weird transactions?"
Output: CALL: detect_anomalies_tool({{}})

User: "What bills are coming up?"
Output: CALL: get_cash_flow_forecast({{"days": 30}})

User: "How are my savings goals doing?"
Output: CALL: get_goal_progress({{}})

User: "What can I deduct for tax?"
Output: CALL: get_tax_summary({{}})

User: "Show me what I just added"
Output: CALL: get_recent_transactions({{"limit": 10}})

User: "Show me my subscriptions"
Output: CALL: get_recurring_expenses({{}})

User: "Tell me more about my Food spending"
Output: CALL: get_category_breakdown({{"category": "Food", "months": 3}})

User: "Where do I shop the most?"
Output: CALL: get_merchant_insights({{"top_n": 10}})

User: "Which days do I spend most on?"
Output: CALL: get_daily_pattern({{"months": 3}})

User: "Find any repeating patterns in my history"
Output: CALL: get_detect_recurring({{}})

### RULES
- NEVER output two CALL lines.
- NEVER output CALL and DIRECT together.
- NEVER add any text before or after the single output line.
- Today's date: {date.today().isoformat()}
"""


# ── STAGE 2: ANALYST / SUMMARIZER ─────────────────────────────────────────────
# Role   : Transform raw JSON tool output into a clear, friendly financial answer.
# Task   : Write a helpful 2-4 paragraph response using only the data provided.
# Format : Plain paragraphs. No CALL lines. No JSON. No function names.
# ──────────────────────────────────────────────────────────────────────────────
ANALYST_SYSTEM_PROMPT = """
### ROLE
You are Finn, a warm and expert personal finance assistant.
You have just received raw financial data from a secure database query.

### TASK
Transform the raw data into a helpful, conversational financial summary for the user.
Answer the user's original question directly using ONLY the numbers in the data.

### OUTPUT FORMAT
- Write 2 to 4 short paragraphs of plain text.
- Use ₹ (INR) for all currency values.
- Bold the most important numbers using **₹X** markdown.
- End with exactly one actionable tip or encouraging observation.
- Do NOT use bullet lists as the primary format – prose paragraphs only.
- Do NOT mention tool names, function names, JSON, or database.
- Do NOT output any line starting with "CALL:".
- Do NOT say "I will look that up" or "please wait".

### CRITICAL CONSTRAINT
You are given all the data you need. Never say data is unavailable.
If a total is 0, say "no transactions were found for that period."

### EXAMPLE STRUCTURE
[Paragraph 1 – direct answer to the user's question with key numbers]
[Paragraph 2 – breakdown of categories or details]
[Paragraph 3 – comparison, trend, or context if available]
[Final sentence – one specific, actionable tip or positive observation]
"""


# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    messages: List[BaseMessage]
    db: Session
    tool_result: Union[dict, None]       # stores raw tool output
    relevant_memory: List[str]            # retrieved RAG context
    iterations: int
    log_callback: Optional[Callable[[str], None]]


# ─────────────────────────────────────────────
# LLM FACTORY
# ─────────────────────────────────────────────

def get_llm(temperature: float = 0.05):
    """Returns the configured LLM. Lower temperature = more deterministic routing."""
    if settings.use_local_llm:
        print(f"[LLM] Using Local Ollama: {settings.model_name}")
        return ChatOllama(
            model=settings.model_name,
            base_url=settings.ollama_url,
            temperature=temperature,
        )
    else:
        model = settings.model_name if "gemini" in settings.model_name.lower() else "gemini-1.5-flash"
        print(f"[LLM] Using Google: {model}")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
        )


# ─────────────────────────────────────────────
# HELPER: parse CALL line
# ─────────────────────────────────────────────

def _parse_call(text: str) -> tuple[str, dict] | None:
    """
    Parses 'CALL: fn_name({"k": "v"})' or 'CALL: fn_name()'
    Returns (fn_name, args_dict) or None if not a valid CALL line.
    """
    # Match CALL: fn_name({...}) or CALL: fn_name()
    match = re.search(
        r"CALL\s*:\s*(\w+)\s*\((\{.*?\})?\)",
        text,
        re.I | re.S
    )
    if not match:
        return None

    fn_name = match.group(1).strip().lower()
    raw_args = match.group(2) or "{}"

    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        # fallback: try key=value pairs
        args = {}
        for k, v in re.findall(r'(\w+)\s*[:=]\s*["\']?([^"\'},\)]+)["\']?', raw_args):
            args[k.strip()] = v.strip()

    return fn_name, args


# ─────────────────────────────────────────────
# NODE 1: INTENT DETECTOR
# ─────────────────────────────────────────────

async def detect_intent(state: AgentState) -> dict:
    """
    Stage 1 LLM call.
    Uses the strict INTENT prompt to produce either:
      - CALL: tool_name({args})
      - DIRECT: <reply>
    Stores result in state without touching messages.
    """
    iteration = state.get("iterations", 0) + 1
    print(f"[GRAPH-NODE] Intent Detection (Iteration {iteration})")
    if state.get("log_callback"):
        state["log_callback"]("Analyzing your question...")

    llm = get_llm(temperature=0.0)   # zero temperature for deterministic routing

    # Only send system + latest user message to keep context tiny for small models
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)
                     and "TOOL_RESULT" not in m.content]
    last_user_msg = user_messages[-1] if user_messages else HumanMessage(content="Hello")

    invoke_messages = [
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        last_user_msg,
    ]

    response = await llm.ainvoke(invoke_messages)
    raw = response.content.strip()
    print(f"DEBUG: Intent Response: {raw}")

    # Strip model-added prefixes like "Assistant:" or "Finn:"
    raw = re.sub(r"^(Assistant|Finn)\s*:\s*", "", raw, flags=re.I).strip()

    print(f"[INTENT-RAW] {raw}")

    # ── Auto-fix: model forgot CALL: prefix ──────────────────────
    tool_names = [
        "get_spending_summary", "get_monthly_trend", "get_budget_status",
        "detect_anomalies_tool", "get_cash_flow_forecast", "get_goal_progress",
        "get_tax_summary", "get_recent_transactions", "get_recurring_expenses",
        "get_category_breakdown", "get_merchant_insights", "get_daily_pattern",
        "get_detect_recurring"
    ]
    if "CALL:" not in raw.upper() and "DIRECT:" not in raw.upper():
        for tn in tool_names:
            if tn in raw:
                raw = "CALL: " + raw
                print(f"[INTENT-FIX] Auto-prefixed CALL:")
                break
        else:
            # No known tool found – treat as direct reply
            raw = f"DIRECT: {raw}"
            print(f"[INTENT-FIX] Treated as DIRECT reply")

    return {
        "messages": state["messages"] + [AIMessage(content=raw)],
        "iterations": iteration,
        "tool_result": None,
        "direct_reply": None,
    }


# ─────────────────────────────────────────────
# NODE 2: TOOL EXECUTOR
# ─────────────────────────────────────────────

async def execute_tool(state: AgentState) -> dict:
    """
    Parses the CALL from the last AIMessage and executes the matching finance tool.
    Stores result in state["tool_result"].
    """
    last_ai = state["messages"][-1].content
    parsed = _parse_call(last_ai)

    if not parsed:
        return {
            "tool_result": {"error": "Could not parse tool call."},
            "error": "parse_error",
        }

    fn_name, fn_args = parsed
    print(f"[GRAPH-NODE] Executing: {fn_name}({fn_args})")
    if state.get("log_callback"):
        state["log_callback"](f"Fetching {fn_name.replace('get_', '').replace('_', ' ')}...")

    db = state["db"]
    try:
        if fn_name == "get_spending_summary":
            res = spending_summary(db, fn_args.get("period", "this_month"))
        elif fn_name == "get_monthly_trend":
            res = monthly_trend(db, int(fn_args.get("months", 6)))
        elif fn_name == "get_budget_status":
            res = budget_status(db)
        elif fn_name in ("detect_anomalies_tool", "detect_anomalies"):
            res = detect_anomalies(db)
        elif fn_name == "get_cash_flow_forecast":
            res = cash_flow_forecast(db, int(fn_args.get("days", 30)))
        elif fn_name == "get_goal_progress":
            res = goal_progress(db)
        elif fn_name == "get_tax_summary":
            res = tax_summary(db)
        elif fn_name == "get_recent_transactions":
            res = get_recent_transactions(db, int(fn_args.get("limit", 10)))
        elif fn_name == "get_recurring_expenses":
            res = get_recurring_expenses(db)
        elif fn_name == "get_category_breakdown":
            res = category_breakdown(db, fn_args.get("category", "Miscellaneous"), int(fn_args.get("months", 3)))
        elif fn_name == "get_merchant_insights":
            res = merchant_insights(db, int(fn_args.get("top_n", 10)))
        elif fn_name == "get_daily_pattern":
            res = daily_spending_pattern(db, int(fn_args.get("months", 3)))
        elif fn_name == "get_detect_recurring":
            res = detect_recurring(db)
        else:
            res = {"error": f"Unknown tool: {fn_name}"}
    except Exception as exc:
        res = {"error": str(exc)}

    print(f"[TOOL-RESULT] Success! Data keys: {list(res.keys())}")
    return {"tool_result": res}


# ─────────────────────────────────────────────
# NODE 2.5: MEMORY RETRIEVER (RAG)
# ─────────────────────────────────────────────

async def retrieve_memory(state: AgentState) -> dict:
    """
    Stage 2 (Parallel): Fetches relevant long-term insights from ChromaDB.
    """
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)
                     and "TOOL_RESULT" not in m.content]
    last_query = user_messages[-1].content if user_messages else ""
    
    print(f"[GRAPH-NODE] RAG Retrieval for: {last_query[:50]}...")
    
    relevant = []
    try:
        relevant = memory_manager.search_memory(last_query, limit=3, threshold=0.6)
    except Exception as e:
        print(f"⚠️ [RAG-ERROR] {e}")
        
    return {"relevant_memory": relevant}


# ─────────────────────────────────────────────
# NODE 3: ANALYST (SUMMARIZER)
# ─────────────────────────────────────────────

async def analyse_and_respond(state: AgentState) -> dict:
    """
    Stage 2 LLM call.
    Takes the raw tool_result + original user question,
    and produces a clean, friendly financial analysis.
    """
    print("[GRAPH-NODE] Generating analyst response...")
    if state.get("log_callback"):
        state["log_callback"]("Preparing your financial summary...")

    llm = get_llm(temperature=0.3)  # slight creativity for natural language

    # Grab the original user question (no TOOL_RESULT messages)
    user_messages = [
        m for m in state["messages"]
        if isinstance(m, HumanMessage) and "TOOL_RESULT" not in m.content
    ]
    original_question = user_messages[-1].content if user_messages else "Tell me about my finances."

    tool_data = json.dumps(state["tool_result"], indent=2)

    # Grab relevant memories from RAG
    memories = state.get("relevant_memory", [])
    memory_context = ""
    if memories:
        memory_context = "\n### RELEVANT PAST CONTEXT (MEMORY)\n- " + "\n- ".join(memories)

    if memories:
        print(f"DEBUG: Injecting Memory Context:\n{memory_context}")

    invoke_messages = [
        SystemMessage(content=ANALYST_SYSTEM_PROMPT + memory_context),
        HumanMessage(content=(
            f"User's question: {original_question}\n\n"
            f"Financial data:\n{tool_data}"
        )),
    ]

    response = await llm.ainvoke(invoke_messages)
    raw = response.content.strip()
    raw = re.sub(r"^(Assistant|Finn)\s*:\s*", "", raw, flags=re.I).strip()

    # Safety: if model hallucinated a CALL line, strip it and use fallback
    if re.search(r"^CALL\s*:", raw, re.I | re.M):
        print("[ANALYST-GUARD] Stripped hallucinated CALL from analyst output.")
        raw = re.sub(r"CALL\s*:.*", "", raw, flags=re.I).strip()
        if not raw:
            raw = (
                f"Based on your financial data, your total spending is "
                f"₹{state['tool_result'].get('total', 'N/A')}. "
                f"Please review your dashboard for full details."
            )

    print(f"[ANALYST-OUTPUT] {raw[:200]}...")

    return {
        "messages": state["messages"] + [AIMessage(content=raw)],
    }


# ─────────────────────────────────────────────
# NODE 5: MEMORY ARCHIVER
# ─────────────────────────────────────────────

async def archive_memory(state: AgentState) -> dict:
    """
    Stage 3: Extracts a new insight from the exchange and saves it to ChromaDB.
    Runs after the analyst response is ready.
    """
    # Get last user msg and last AI msg
    user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)
                 and "TOOL_RESULT" not in m.content]
    ai_msgs = [m for m in state["messages"] if isinstance(m, AIMessage)
               and "DIRECT:" not in m.content and "CALL:" not in m.content]
    
    if user_msgs and ai_msgs:
        user_text = user_msgs[-1].content
        ai_text = ai_msgs[-1].content
        
        # This is a fire-and-forget extraction
        print("[GRAPH-NODE] Memory Archiving (Insight Extraction)...")
        insight = await extract_insight(user_text, ai_text)
        if insight:
            print(f"🧠 [ARCHIVE] New Insight Found: {insight}")
            memory_manager.add_insight(insight)
        else:
            print("🧠 [ARCHIVE] No new permanent insight detected in this turn.")
            
    return {}


# ─────────────────────────────────────────────
# NODE 4: DIRECT REPLY (small talk)
# ─────────────────────────────────────────────

async def send_direct_reply(state: AgentState) -> dict:
    """
    For DIRECT: replies – just clean and return the text from intent node.
    No second LLM call needed.
    """
    last_ai = state["messages"][-1].content
    reply = re.sub(r"^DIRECT\s*:\s*", "", last_ai, flags=re.I).strip()
    if not reply:
        reply = "Hello! I'm Finn, your personal finance assistant. How can I help you today?"

    # Replace the last AIMessage with the clean reply
    updated_messages = state["messages"][:-1] + [AIMessage(content=reply)]
    return {"messages": updated_messages}


# ─────────────────────────────────────────────
# ROUTING EDGE
# ─────────────────────────────────────────────

def route_after_intent(state: AgentState) -> Literal["executor", "direct_reply"]:
    """
    Inspects the last AIMessage from the intent node.
    Routes to executor if CALL:, else direct_reply.
    """
    last = state["messages"][-1].content
    if re.search(r"^CALL\s*:", last, re.I | re.M):
        return "executor"
    return "direct_reply"


# ─────────────────────────────────────────────
# GRAPH ASSEMBLY
# ─────────────────────────────────────────────

def create_financial_graph():
    """
    Graph topology:
    
    [intent_detector]
         |
    route_after_intent()
         |              \\
    [executor]      [direct_reply]
         |                |
    [analyst]            END
         |
        END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("intent_detector", detect_intent)
    workflow.add_node("executor", execute_tool)
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("analyst", analyse_and_respond)
    workflow.add_node("archive_memory", archive_memory)
    workflow.add_node("direct_reply", send_direct_reply)

    workflow.set_entry_point("intent_detector")

    workflow.add_conditional_edges(
        "intent_detector",
        route_after_intent,
        {
            "executor": "executor",
            "direct_reply": "direct_reply",
        }
    )

    # From executor, we ALSO go to retrieve_memory to build context
    workflow.add_edge("executor", "retrieve_memory")
    workflow.add_edge("retrieve_memory", "analyst")
    workflow.add_edge("analyst", "archive_memory")
    workflow.add_edge("archive_memory", END)
    workflow.add_edge("direct_reply", END)

    return workflow.compile()


# ─────────────────────────────────────────────
# PRODUCTION AGENT ENTRY POINT
# ─────────────────────────────────────────────

class ProductionAgent:
    def __init__(self, db: Session, log_callback: Optional[Callable[[str], None]] = None):
        self.db = db
        self.log_callback = log_callback
        self.app = create_financial_graph()

    async def execute(self, user_query: str, history: list) -> str:
        """
        Runs the graph and returns the final clean text response.
        The response is always a plain-text string suitable for the frontend chat UI.
        """
        # Build message history (last 6 turns, no TOOL_RESULT messages)
        messages: List[BaseMessage] = []
        for turn in history[-6:]:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if "TOOL_RESULT" in content:
                continue   # never pass raw tool data as history
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=user_query))

        inputs = {
            "messages": messages,
            "db": self.db,
            "tool_result": None,
            "relevant_memory": [],
            "direct_reply": None,
            "error": None,
            "iterations": 0,
            "log_callback": self.log_callback,
        }

        try:
            final_state = await self.app.ainvoke(inputs)
        except Exception as exc:
            print(f"[AGENT-ERROR] {exc}")
            return (
                "I ran into an issue while analysing your finances. "
                "Please try again in a moment."
            )

        # The final answer is always the last AIMessage
        last_msg = final_state["messages"][-1]
        response = last_msg.content.strip() if hasattr(last_msg, "content") else ""

        # Strip any accidental prefixes
        response = re.sub(r"^(Finn|Assistant)\s*:\s*", "", response, flags=re.I).strip()

        # Hard guard: if the response leaked a CALL line, replace entirely
        if re.search(r"^CALL\s*:", response, re.I | re.M):
            tool_result = final_state.get("tool_result") or {}
            total = tool_result.get("total", "")
            response = (
                f"I've pulled your latest financial data. "
                f"{'Your total spending is ₹' + str(total) + '.' if total else ''} "
                f"Please ask a specific question and I'll break it down for you."
            ).strip()

        # If empty, give a safe fallback
        if not response:
            response = (
                "I couldn't generate a summary right now. "
                "Please try rephrasing your question."
            )

        return response
