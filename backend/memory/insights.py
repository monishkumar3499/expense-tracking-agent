import json
import re
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from config import settings

# This prompt is designed to be extremely focused and lightweight.
# It only triggers when a permanent fact or preference is revealed.
INSIGHT_EXTRACTION_PROMPT = """
### ROLE
You are a Memory Extractor for a personal finance assistant.
Your job is to identify if the current conversation reveals any PERMANENT facts, preferences, or goals about the user.

### GUIDELINES
1. Extract only facts that will be useful for FUTURE financial advice.
2. Examples of insights:
   - "User wants to save ₹50,000 for a laptop by December."
   - "User prefers to keep Food spending below ₹5,000/month."
   - "User mentioned they shop at Reliance Fresh for groceries."
   - "User is planning a vacation to Goa in July."
3. Ignore temporary or conversational filler.
4. If no permanent insight is found, return exactly the word "None".
5. Return a clean, single-sentence insight. No JSON, no labels.

### INPUT
User said: {user_msg}
Finn replied: {ai_msg}

### OUTPUT
Insight (or "None"):
"""

async def extract_insight(user_msg: str, ai_msg: str) -> Optional[str]:
    """Uses the LLM to extract a single clean insight from a conversation turn."""
    from graph import get_llm
    
    llm = get_llm(temperature=0.0)
    prompt = INSIGHT_EXTRACTION_PROMPT.format(user_msg=user_msg, ai_msg=ai_msg)
    
    try:
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        content = response.content.strip()
        
        # Strip common AI filler
        content = re.sub(r"^(Insight|Result|Output):\s*", "", content, flags=re.I).strip()
        
        if content.lower() == "none" or len(content) < 5:
            return None
            
        return content
    except Exception as e:
        print(f"⚠️ [INSIGHT] Failed to extract memory: {e}")
        return None
