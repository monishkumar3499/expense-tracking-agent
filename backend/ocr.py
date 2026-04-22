import requests
import google.generativeai as genai
from config import settings
from pathlib import Path
import json, base64
import re

# Configure Gemini
genai.configure(api_key=settings.gemini_api_key)

# We'll use the Chat model to process Moondream's description into JSON
def _parse_with_chat_model(description: str):
    print("🧠 [OCR] Parsing description into JSON using local chat model...")
    prompt = f"""Convert this receipt description into a RAW JSON object following the schema below.
Description: {description}

Expected Structure:
{{
  "transactions": [
    {{
      "merchant": "name",
      "amount": 123.45,
      "currency": "INR",
      "date": "YYYY-MM-DD",
      "description": "summary",
      "category": "Miscellaneous"
    }}
  ],
  "document_type": "receipt",
  "confidence": 0.8
}}
Return ONLY RAW JSON."""

    try:
        response = requests.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json"
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('message', {}).get('content', '')
    except Exception as e:
        print(f"⚠️ [OCR] Chat parsing failed: {str(e)}")
    return "{}"

async def extract_from_file(file_path: str):
    print(f"🖼️ [OCR] Reading file: {Path(file_path).name}")
    
    # Stage 1: Moondream Description
    try:
        print(f"🧠 [OCR] Describing image with {settings.ollama_ocr_model}...")
        with open(file_path, "rb") as image_file:
            img_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Moondream works best with simple descriptive prompts
        desc_res = requests.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_ocr_model,
                "messages": [{
                    "role": "user",
                    "content": "Extract the merchant name, total amount spent, currency, and date from this receipt. If it is a bank statement or list, summarize the transactions.",
                    "images": [img_b64]
                }],
                "stream": False
            },
            timeout=120
        )
        
        if desc_res.status_code == 200:
            description = desc_res.json().get('message', {}).get('content', '')
            print(f"📝 [OCR] Description: {description[:100]}...")
            
            # Stage 2: Qwen JSON Parsing
            json_text = _parse_with_chat_model(description)
            data = json.loads(_clean_json(json_text))
            
            # Validate structure
            if not data.get("transactions"):
                raise ValueError("No transactions found in parsed JSON")
                
            print("✅ [OCR] Local extraction successful via 2-stage pipeline.")
            return data
            
    except Exception as e:
        print(f"⚠️ [OCR] Local pipeline failed: {str(e)}")

    # Stage 3: Gemini Fallback
    print(f"🧠 [OCR] Falling back to remote model...")
    try:
        # Try multiple common fallout names
        fallback_model = settings.gemini_model if settings.gemini_model else "gemini-1.5-flash"
        model = genai.GenerativeModel(fallback_model)
        path = Path(file_path)
        img_data = {
            "mime_type": "image/png" if path.suffix.lower() == '.png' else "image/jpeg",
            "data": path.read_bytes()
        }
        
        OCR_PROMPT = "Extract transaction details as RAW JSON." # Simplified prompt for gemini
        response = model.generate_content([OCR_PROMPT, img_data])
        raw_text = _clean_json(response.text)
        print("✅ [OCR] Remote extraction successful.")
        return json.loads(raw_text)
    except Exception as e:
        print(f"❌ [OCR] Critical failure: {str(e)}")
        return {
            "transactions": [{"merchant": "Manual Entry (OCR Failed)", "amount": 0.0, "currency": "INR", "date": "2024-01-01", "category": "Miscellaneous"}],
            "document_type": "unknown",
            "confidence": 0.0
        }

def _clean_json(txt):
    txt = re.sub(r'```json\n?', '', txt)
    txt = re.sub(r'\n?```', '', txt)
    return txt.strip()
