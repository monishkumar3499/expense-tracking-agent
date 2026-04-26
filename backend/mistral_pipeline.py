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
from datetime import date

# FORCE PATH FIX: Ensure Roaming packages are visible
roaming_path = os.path.expandvars(r'%APPDATA%\Python\Python312\site-packages')
if roaming_path not in sys.path:
    sys.path.insert(0, roaming_path)
    print(f"🔧 [ENVIRONMENT] Injected path: {roaming_path}")

from pathlib import Path
from config import settings
try:
    from finance_tools import CATEGORIES
except ImportError:
    CATEGORIES = {}

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
        print("❌ [MISTRAL] Error: MISTRAL_API_KEY missing in .env")
        return {"error": "MISTRAL_API_KEY not found in configuration."}

    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json"
    }

    try:
        # 1. Determine MIME type and format
        ext = Path(file_path).suffix.lower()
        is_pdf = ext == '.pdf'
        
        mime_type = "application/pdf" if is_pdf else f"image/{ext.replace('.', '') if ext != '.jpg' else 'jpeg'}"
        
        # Read and encode file
        print(f"📸 [MISTRAL] Reading {ext} file...")
        with open(file_path, "rb") as f:
            encoded_content = base64.b64encode(f.read()).decode("utf-8")
        print(f"📏 [MISTRAL] Content encoded (Size: {len(encoded_content)/1024:.1f} KB)")

        # 2. Call OCR Endpoint
        print("📡 [MISTRAL] Sending request to Mistral OCR endpoint...")
        
        # Mistral OCR v1/ocr expects 'document_url' for PDFs and 'image_url' for images
        # Both can accept data URIs
        if is_pdf:
            doc_type = "document_url"
            url_key = "document_url"
        else:
            doc_type = "image_url"
            url_key = "image_url"

        ocr_payload = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": doc_type,
                url_key: f"data:{mime_type};base64,{encoded_content}"
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

        # 3. Use Local LLM (Gemma) to structure the data
        # Prepare categories for prompt
        base_categories = list(CATEGORIES.keys()) + ["Overall", "Miscellaneous"]
        category_str = ", ".join(base_categories)

        system_msg = f"""You are a receipt parser and financial classifier.
STRICT RULES:
1. Extract ONLY specific line items (e.g. 'Avocado Toast') and their corresponding unit price/rate.
2. IGNORE: UPI IDs, payment methods, tax breakdowns, auth codes, and receipt numbers.
3. The 'amount' field MUST be a clean positive number.
4. Extract the printed 'TOTAL' amount separately into the 'total' field.
5. Create a short, human-friendly summary name for the entire receipt (e.g., 'Groceries from Walmart', 'Dinner at Starbucks', 'Stationary from Local Shop'). Store this in 'bill_name'.
6. Date must be YYYY-MM-DD.
7. CLASSIFICATION: Map each item to EXACTLY ONE of these categories: {category_str}."""

        user_msg = f"""MARKDOWN DATA:
{raw_markdown}

TASK: Convert the individual items from the receipt into JSON transactions. 
Also find the final total amount shown on the bill and generate a summary name.

JSON FORMAT:
{{
  "type": "receipt",
  "bill_name": "Summarized Name",
  "transactions": [
    {{
      "date": "YYYY-MM-DD",
      "description": "Product Name",
      "amount": 12.50,
      "category_hint": "One of: {category_str}"
    }}
  ],
  "total": 0.00,
  "currency": "INR"
}}"""

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

        print("📥 [MISTRAL] AI Structuring complete")
        result = json.loads(final_json_text)
        
        # 4. POST-PROCESSING: Deduplicate and Filter
        unique_txns = []
        seen_keys = set()
        valid_categories = [c.lower() for c in base_categories]

        for t in result.get("transactions", []):
            desc = str(t.get("description", "Unknown")).strip()
            junk_keywords = ["subtotal", "total", "tax", "ship to", "bill to", "receipt", "invoice", "unknown", "sales tax", "amount due", "balance", "usd"]
            if any(k in desc.lower() for k in junk_keywords):
                continue
                
            try:
                raw_amt = str(t.get("amount", "0")).replace("$", "").replace("₹", "").replace(",", "").strip()
                match_amt = re.search(r"(\d+\.?\d*)", raw_amt)
                if not match_amt: continue
                amt = round(abs(float(match_amt.group(1))), 2)
            except (ValueError, TypeError, AttributeError):
                continue
                
            dt = t.get("date") or date.today().isoformat()
            # Map back to capitalized category name for consistency
            cat_hint = str(t.get("category_hint", "Miscellaneous")).strip()
            cat = "Miscellaneous"
            for c in base_categories:
                if cat_hint.lower() == c.lower():
                    cat = c
                    break

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
        
        # Calculate sum of items to compare/ensure consistency
        items_total = round(sum(t["amount"] for t in unique_txns), 2)
        
        if "total" in result:
            try:
                result["total"] = round(abs(float(result["total"])), 2)
            except:
                result["total"] = items_total
        else:
            result["total"] = items_total
            
        print(f"📊 [MISTRAL] Items Sum: {items_total}, Reported Total: {result.get('total')}")
            
        result["raw_text"] = raw_markdown
        
        print("💎 [MISTRAL] FINAL STRUCTURED JSON:")
        print(json.dumps(result, indent=2))
        
        return result

    except Exception as e:
        print(f"🔥 [MISTRAL] ERROR during pipeline: {str(e)}")
        return {"error": str(e)}
