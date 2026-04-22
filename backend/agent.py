import requests
from config import settings
from tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, goal_progress, tax_summary,
                   get_recent_transactions)
from sqlalchemy.orm import Session
from datetime import date
import json
import re

TOOLS_LIST = """
1. get_spending_summary(period: str) - Periods: 'today', 'this_week', 'this_month', 'last_month', 'last_3_months', 'this_year'
2. get_monthly_trend(months: int) - Default 6 months
3. get_budget_status() - Current month budget utilization
4. detect_anomalies_tool() - Find unusual high spending
5. get_cash_flow_forecast(days: int) - Forecast (30, 60, or 90 days)
6. get_goal_progress() - Savings goals status
7. get_tax_summary() - Current financial year tax-deductible summary
8. get_recent_transactions(limit: int) - Get the very last added transactions (use after uploads)
"""

SYSTEM_PROMPT = f"""You are Finn, a smart and direct personal finance assistant. 
TODAY: {date.today().strftime("%d %B %Y")}

To provide accurate answers, you MUST use tools. 
If the user says they've uploaded something, ALWAYS use 'get_recent_transactions' first to see exactly what was just added, regardless of the date on the receipt.

If you need data, output a tool call in this EXACT format:
CALL: tool_name({{"arg1": "val1"}})

AVAILABLE TOOLS:
{TOOLS_LIST}

EXAMPLE:
User: I've uploaded my old bills.
Assistant: CALL: get_recent_transactions({{"limit": 5}})

Wait for the data before giving a final summary.
"""

def run_tool(name: str, args: dict, db: Session) -> dict:
    try:
        if name == "get_spending_summary":
            return spending_summary(db, args.get("period", "this_month"))
        elif name == "get_monthly_trend":
            return monthly_trend(db, args.get("months", 6))
        elif name == "get_budget_status":
            return budget_status(db)
        elif name == "detect_anomalies_tool":
            return detect_anomalies(db)
        elif name == "get_cash_flow_forecast":
            return cash_flow_forecast(db, args.get("days", 30))
        elif name == "get_goal_progress":
            return goal_progress(db)
        elif name == "get_tax_summary":
            return tax_summary(db)
        elif name == "get_recent_transactions":
            return get_recent_transactions(db, args.get("limit", 5))
    except Exception as e:
        return {"error": str(e)}
    return {"error": "unknown tool"}

def chat(user_message: str, history: list, db: Session) -> str:
    print(f"💬 [AGENT] New request: '{user_message[:50]}...'")
    print(f"🧠 [AGENT] Using Ollama Manual Loop ({settings.ollama_chat_model})...")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-5:]:
        messages.append({"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        # Loop for tool calls (up to 2 iterations)
        for _ in range(2):
            response = requests.post(
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.ollama_chat_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0}
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return f"Error from Ollama: {response.text}"
                
            content = response.json().get('message', {}).get('content', '')
            
            # Detect tool call: CALL: tool_name({"arg": "val"})
            match = re.search(r"CALL:\s*(\w+)\((.*)\)", content)
            if match:
                fn_name = match.group(1)
                fn_args_raw = match.group(2)
                try:
                    fn_args = json.loads(fn_args_raw)
                except:
                    fn_args = {}
                
                print(f"🛠️ [TOOL] Detected Call: {fn_name} with {fn_args}")
                result = run_tool(fn_name, fn_args, db)
                
                # Append the assistant's call and the tool's result to history
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"TOOL_RESULT: {json.dumps(result)}"})
                continue # Next iteration to get final response
            else:
                return content

        return "I tried to get your data but got stuck in a loop. Try asking in a different way."

    except Exception as e:
        print(f"❌ [AGENT] Error: {str(e)}")
        return f"I encountered an error while thinking: {str(e)}"
