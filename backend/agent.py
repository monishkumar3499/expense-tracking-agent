import requests
from config import settings
from finance_tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, goal_progress, tax_summary,
                   get_recent_transactions)
from sqlalchemy.orm import Session
from datetime import date
import json
import re
from logs import log_manager

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

SYSTEM_PROMPT = f"""You are Finn, a smart finance assistant.
Today: {date.today().isoformat()}

When a user asks about their finances, you MUST follow these steps:
1. If you don't have 'TOOL_RESULT' yet, you MUST output a tool call to get data.
2. Format the call EXACTLY like this: CALL: tool_name({{"arg": "val"}})
3. Once you have 'TOOL_RESULT', summarize ONLY that real data in INR (₹).
4. If 'TOOL_RESULT' is empty/0, say: "I checked your records but found nothing for this yet."

CRITICAL: 
- NEVER make up numbers or merchants.
- DO NOT say you need data. Just output the CALL.
- If the user mentions 'uploaded' or 'bills', always use 'get_recent_transactions'.

AVAILABLE TOOLS:
{TOOLS_LIST}
"""

def run_tool(name: str, args: dict, db: Session) -> dict:
    # Normalize tool names
    name = name.strip().lower()
    try:
        if name == "get_spending_summary":
            return spending_summary(db, args.get("period", "this_month"))
        elif name == "get_monthly_trend":
            return monthly_trend(db, args.get("months", 6))
        elif name == "get_budget_status":
            return budget_status(db)
        elif name == "detect_anomalies_tool" or name == "detect_anomalies":
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
    return {"error": f"Tool '{name}' not found."}

def chat(user_message: str, history: list, db: Session) -> str:
    print(f"[AGENT] New request: '{user_message[:50]}...'")
    log_manager.push("Analyzing request...")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-5:]:
        messages.append({"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        # Track tool calls to prevent repeating the same one
        calls_made = set()
        
        for i in range(4):
            print(f"[AGENT] Iteration {i+1}...")
            response = requests.post(
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return f"Error from Ollama: {response.text}"
                
            content = response.json().get('message', {}).get('content', '')
            print(f"[AGENT] Model says: '{content[:100]}...'")

            if not content.strip():
                return "I'm listening, but I didn't get enough data to answer that. Could you clarify?"

            # Detect tool call
            match = re.search(r"CALL:\s*(\w+)(?:\((.*)\))?", content)
            if match:
                fn_name = match.group(1).strip()
                call_key = f"{fn_name}:{match.group(2)}"
                
                if call_key in calls_made:
                    print(f"[LOOP] Repetitive call detected: {fn_name}. Forcing final summary.")
                    messages.append({"role": "system", "content": "You already called that tool and got the result above. Do NOT call it again. Please summarize the data you have."})
                    continue

                fn_args_raw = match.group(2) if match.group(2) else "{}"
                try:
                    clean_args = re.search(r"\{.*\}", fn_args_raw)
                    fn_args = json.loads(clean_args.group(0)) if clean_args else {}
                except:
                    fn_args = {}
                
                print(f"[TOOL] Executing: {fn_name}({fn_args})")
                log_manager.push(f"Accessing data: {fn_name.replace('get_', '').replace('_', ' ')}...")
                result = run_tool(fn_name, fn_args, db)
                
                # Mark as called
                calls_made.add(call_key)
                
                # Append to history with high priority (system role)
                clean_content = re.sub(r"^(Assistant:\s*)", "", content, flags=re.I)
                messages.append({"role": "assistant", "content": clean_content})
                # Use 'system' role for results to make them stand out
                messages.append({"role": "system", "content": f"TOOL_RESULT: {json.dumps(result)}"})
                continue 
            else:
                # No tool call, return final response
                return re.sub(r"^(Assistant:\s*)", "", content, flags=re.I)

        return "I found the data but I'm having trouble summarizing it concisely. Could you try a more specific question?"

    except Exception as e:
        print(f"❌ [AGENT] Error: {str(e)}")
        return f"I encountered an error while thinking: {str(e)}"
