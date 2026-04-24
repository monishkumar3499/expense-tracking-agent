"""
mistral_pipeline.py
-------------------
Bypasses the mistralai SDK and uses direct HTTP requests to Mistral's API.
This ensures compatibility even when the local Python environment has library conflicts.
"""

import json
import re
import logging
import requests
import base64
import sys
import os

# FORCE PATH FIX: Ensure Roaming packages are visible
roaming_path = os.path.expandvars(r'%APPDATA%\Python\Python312\site-packages')
if roaming_path not in sys.path:
    sys.path.insert(0, roaming_path)
    print(f"🔧 [ENVIRONMENT] Injected path: {roaming_path}")

from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)

# Constants for Mistral API
MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"
MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"

def extract_with_mistral(file_path: str) -> dict:
    """
    Directly calls Mistral API via requests (No SDK required).
    """
    print(f"🔍 [MISTRAL] Starting extraction for: {file_path}")
    
    if not settings.mistral_api_key:
        print("❌ [MISTRAL] Error: MISTRAL_API_KEY missing")
        return {"error": "MISTRAL_API_KEY not found in configuration."}

    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json"
    }

    try:
        # 1. Read and encode image
        print("📸 [MISTRAL] Reading image file...")
        with open(file_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
        print(f"📏 [MISTRAL] Image encoded (Size: {len(encoded_image)/1024:.1f} KB)")

        # 2. Call OCR Endpoint
        print("📡 [MISTRAL] Sending request to Mistral OCR endpoint...")
        ocr_payload = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{encoded_image}"
            }
        }
        
        ocr_resp = requests.post(MISTRAL_OCR_URL, json=ocr_payload, headers=headers, timeout=120)
        ocr_resp.raise_for_status()
        print("📥 [MISTRAL] OCR response received successfully")
        
        ocr_data = ocr_resp.json()
        raw_markdown = ""
        for page in ocr_data.get("pages", []):
            raw_markdown += page.get("markdown", "") + "\n"

        print(f"📝 [MISTRAL] Extracted Markdown Length: {len(raw_markdown)} chars")
        print("📝 [MISTRAL] RAW OCR OUTPUT PREVIEW:")
        print("-" * 30)
        print(raw_markdown[:500] + "...")
        print("-" * 30)

        # IMPROVED PROMPT FOR SMALL MODELS (Gemma 3:1B)
        system_msg = """You are a receipt parser. 
STRICT RULES:
1. Extract ONLY specific line items (e.g. 'Avocado Toast').
2. IGNORE: UPI IDs, payment methods, auth codes, and receipt numbers.
3. The 'amount' field MUST be a clean positive number.
4. IGNORE 'TOTAL' and 'SUBTOTAL' lines to avoid double counting.
5. Date must be YYYY-MM-DD."""

        user_msg = f"""MARKDOWN DATA:
{raw_markdown}

TASK: Convert the lines from the 'QTY | DESCRIPTION | AMOUNT' table into JSON.
JSON FORMAT:
{{
  "type": "receipt",
  "transactions": [
    {{
      "date": "YYYY-MM-DD",
      "description": "Short name of item",
      "amount": 10.50,
      "category_hint": "one of: food, transport, shopping, utilities, entertainment, healthcare, education, miscellaneous"
    }}
  ],
  "total": 0.00,
  "currency": "$"
}}"""

        if settings.use_local_llm:
            print(f"🧠 [MISTRAL] Sending to LOCAL OLLAMA ({settings.model_name}) for structuring...")
            payload = {
                "model": settings.model_name,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0}
            }
            chat_resp = requests.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=120)
            chat_resp.raise_for_status()
            final_json_text = chat_resp.json()["message"]["content"]
        else:
            print("🧠 [MISTRAL] Sending to MISTRAL-LARGE for structuring...")
            chat_payload = {
                "model": "mistral-large-latest",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                "response_format": {"type": "json_object"}
            }
            chat_resp = requests.post(MISTRAL_CHAT_URL, json=chat_payload, headers=headers, timeout=120)
            chat_resp.raise_for_status()
            final_json_text = chat_resp.json()["choices"][0]["message"]["content"]

        print("📥 [MISTRAL] AI Structuring complete")
        result = json.loads(final_json_text)
        
        # 4. POST-PROCESSING: Deduplicate and Filter
        unique_txns = []
        seen_keys = set()
        
        # Mapping for better categorization if the model failed
        valid_categories = ["food", "transport", "shopping", "utilities", "entertainment", "healthcare", "education", "miscellaneous"]

        for t in result.get("transactions", []):
            desc = str(t.get("description", "Unknown")).strip()
            # Skip common "junk" descriptions and totals
            junk_keywords = ["subtotal", "total", "tax", "ship to", "bill to", "receipt", "invoice", "unknown", "sales tax", "amount due", "balance", "usd"]
            if any(k in desc.lower() for k in junk_keywords):
                continue
                
            # Robust amount parsing
            try:
                raw_amt = str(t.get("amount", "0")).replace("$", "").replace("₹", "").replace(",", "").strip()
                # Extact only the numeric part (handling cases like '12.50 USD' or 'UPI ID...')
                match_amt = re.search(r"(\d+\.?\d*)", raw_amt)
                if not match_amt: continue
                amt = round(abs(float(match_amt.group(1))), 2)
            except (ValueError, TypeError, AttributeError):
                continue
            dt = t.get("date") or date.today().isoformat()
            cat = t.get("category_hint", "miscellaneous").lower()
            if cat not in valid_categories: cat = "miscellaneous"

            # Unique key: (lower_desc, amount, date)
            key = (desc.lower(), amt, dt)
            if key not in seen_keys and amt > 0:
                unique_txns.append({
                    "date": dt,
                    "description": desc,
                    "amount": amt,
                    "category_hint": cat
                })
                seen_keys.add(key)

        result["transactions"] = unique_txns
        if "total" in result:
            result["total"] = round(abs(float(result["total"])), 2)
            
        result["raw_text"] = raw_markdown
        
        print("💎 [MISTRAL] FINAL STRUCTURED JSON:")
        print(json.dumps(result, indent=2))
        
        print(f"✨ [MISTRAL] Successfully parsed {len(result.get('transactions', []))} transactions")
        return result

    except Exception as e:
        print(f"🔥 [MISTRAL] ERROR during pipeline: {str(e)}")
        logger.error(f"❌ Direct Mistral Pipeline failed: {e}")
        return {"error": str(e)}
