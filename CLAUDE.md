# 💸 Personal Expense Tracker Agent — CLAUDE.md
## Build Instructions for Claude Code (No Auth, Single User, Full Features)

---

## WHAT TO BUILD

A **single-user AI expense tracker** — no login, no auth, no multi-user complexity.
The app runs locally, stores data in SQLite (no external DB needed), and uses the API keys from `.env`.

One command to start. Everything works out of the box.

---

## FOLDER STRUCTURE (already exists)

```
/
├── frontend/     ← Next.js app
├── backend/      ← FastAPI app
└── .env          ← API keys (read this first, never overwrite)
```

---

## STEP 0 — READ .ENV FIRST

Read `.env` and identify available keys. Use only what exists:

```
GEMINI_API_KEY=...      # For vision OCR + embeddings
GEMINI_API_KEY=...        # Also for chat reasoning
```

That's it. No DB URL, no Redis, no S3 needed. Everything runs locally.

---

## STEP 1 — BACKEND (`/backend`)

### Install dependencies

```bash
cd backend
pip install fastapi uvicorn[standard] python-multipart sqlalchemy \
  aiosqlite google-generativeai groq pdfplumber pillow \
  python-dotenv pydantic-settings fuzzywuzzy python-levenshtein \
  aiofiles pandas python-dateutil
pip freeze > requirements.txt
```

### Project structure

```
backend/
├── main.py              # FastAPI entry point — all routes here
├── database.py          # SQLite setup with SQLAlchemy (sync, simple)
├── models.py            # All DB models in one file
├── config.py            # Settings from .env
├── agent.py             # LLM agent orchestrator
├── tools.py             # All analysis tools
├── ocr.py               # Receipt/PDF extraction via Gemini vision
├── storage.py           # Local file storage (saves to /uploads folder)
└── requirements.txt
```

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str = ""
    groq_api_key: str = ""
    upload_dir: str = "uploads"
    db_path: str = "expense_tracker.db"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
```

### `database.py` — SQLite, sync, simple

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

engine = create_engine("sqlite:///expense_tracker.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from models import Transaction, Budget, Goal, RecurringExpense, ChatMessage
    Base.metadata.create_all(bind=engine)
```

### `models.py` — All models in one file

```python
from sqlalchemy import Column, String, Float, Boolean, Date, DateTime, Text, Integer
from sqlalchemy.dialects.sqlite import JSON
from database import Base
import uuid
from datetime import datetime

def gen_id():
    return str(uuid.uuid4())

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=gen_id)
    merchant = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    category = Column(String, default="Miscellaneous")
    subcategory = Column(String, default="")
    date = Column(Date, nullable=False)
    source = Column(String, default="manual")   # receipt | bank_statement | upi | manual
    description = Column(Text, default="")
    raw_text = Column(Text, default="")
    file_id = Column(String, default="")
    is_recurring = Column(Boolean, default=False)
    tax_deductible = Column(Boolean, default=False)
    tax_section = Column(String, default="")
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(String, primary_key=True, default=gen_id)
    category = Column(String, nullable=False, unique=True)
    monthly_limit = Column(Float, nullable=False)
    alert_threshold = Column(Float, default=0.8)

class Goal(Base):
    __tablename__ = "goals"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    deadline = Column(Date)
    status = Column(String, default="active")   # active | completed | paused
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"
    id = Column(String, primary_key=True, default=gen_id)
    merchant = Column(String, nullable=False)
    avg_amount = Column(Float)
    frequency = Column(String)   # weekly | monthly | yearly
    last_seen = Column(Date)
    next_expected = Column(Date)
    category = Column(String, default="Miscellaneous")
    is_active = Column(Boolean, default=True)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True, default=gen_id)
    role = Column(String, nullable=False)   # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

### `ocr.py` — Receipt & bank statement extraction

```python
import google.generativeai as genai
from config import settings
import json, base64, re
from pathlib import Path

genai.configure(api_key=settings.gemini_api_key)

OCR_PROMPT = """
You are a financial data extraction expert. Extract ALL transactions from this receipt or bank statement image/document.

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "transactions": [
    {
      "merchant": "merchant or payee name",
      "amount": 123.45,
      "currency": "INR",
      "date": "YYYY-MM-DD",
      "description": "brief description",
      "category_hint": "Food & Dining | Transport | Shopping | etc"
    }
  ],
  "document_type": "receipt | bank_statement | upi_screenshot",
  "confidence": 0.95
}

Rules:
- For bank statements: extract EVERY debit transaction as a separate object
- If date is unclear, use today's date
- Amounts should be positive numbers
- Merchant should be the actual store/app name not a code
- If multiple items on one receipt, sum them into ONE transaction for the merchant
"""

async def extract_from_file(file_path: str) -> dict:
    model = genai.GenerativeModel("gemini-1.5-flash")
    path = Path(file_path)

    if path.suffix.lower() == ".pdf":
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        response = model.generate_content([OCR_PROMPT + f"\n\nDOCUMENT TEXT:\n{text}"])
    else:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        mime = "image/jpeg"
        if path.suffix.lower() == ".png": mime = "image/png"
        elif path.suffix.lower() == ".webp": mime = "image/webp"
        response = model.generate_content([
            OCR_PROMPT,
            {"mime_type": mime, "data": base64.b64encode(image_bytes).decode()}
        ])

    raw = response.text.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)
```

---

### `tools.py` — All analysis tools

```python
from sqlalchemy.orm import Session
from models import Transaction, Budget, Goal, RecurringExpense
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import statistics

CATEGORIES = {
    "Food & Dining": ["swiggy", "zomato", "uber eats", "restaurant", "cafe", "biryani", "pizza", "burger", "dominos", "kfc", "mcdonalds", "starbucks"],
    "Transport": ["uber", "ola", "rapido", "irctc", "metro", "petrol", "fuel", "auto", "bus", "flight", "indigo", "air india"],
    "Utilities": ["electricity", "bescom", "tneb", "water", "gas", "internet", "broadband", "airtel", "jio"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "zepto", "blinkit", "instamart", "meesho", "nykaa"],
    "Entertainment": ["netflix", "hotstar", "spotify", "youtube", "prime video", "cinema", "pvr", "inox", "bookmyshow"],
    "Healthcare": ["pharmacy", "hospital", "clinic", "apollo", "medplus", "diagnostic", "lab", "doctor", "medicine"],
    "Education": ["udemy", "coursera", "book", "course", "training", "school", "college", "byju"],
    "Subscriptions": ["subscription", "renewal", "monthly plan", "annual plan", "premium"],
    "Travel": ["oyo", "makemytrip", "goibibo", "booking.com", "airbnb"],
    "Groceries": ["bigbasket", "dmart", "reliance fresh", "more supermarket", "vegetables", "supermarket"],
}

def categorise(merchant: str, description: str = "") -> tuple:
    text = (merchant + " " + description).lower()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return category, 0.9
    return "Miscellaneous", 0.4

def get_period_dates(period: str) -> tuple:
    today = date.today()
    if period == "today":
        return today, today
    elif period == "this_week":
        return today - timedelta(days=today.weekday()), today
    elif period == "this_month":
        return today.replace(day=1), today
    elif period == "last_month":
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        return first, last
    elif period == "last_3_months":
        return (today - relativedelta(months=3)).replace(day=1), today
    elif period == "this_year":
        return today.replace(month=1, day=1), today
    return today.replace(day=1), today

def spending_summary(db: Session, period: str = "this_month") -> dict:
    start, end = get_period_dates(period)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False,
        Transaction.date >= start,
        Transaction.date <= end
    ).all()
    by_category = defaultdict(float)
    by_merchant = defaultdict(float)
    for t in txns:
        by_category[t.category] += t.amount
        by_merchant[t.merchant] += t.amount
    top_merchants = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "period": period, "start": str(start), "end": str(end),
        "total": round(sum(by_category.values()), 2),
        "transaction_count": len(txns),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)},
        "top_merchants": [{"merchant": m, "amount": round(a, 2)} for m, a in top_merchants],
    }

def monthly_trend(db: Session, months: int = 6) -> list:
    today = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        start = d.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        txns = db.query(Transaction).filter(
            Transaction.deleted == False,
            Transaction.date >= start, Transaction.date <= end
        ).all()
        by_cat = defaultdict(float)
        for t in txns:
            by_cat[t.category] += t.amount
        result.append({
            "month": start.strftime("%b %Y"),
            "total": round(sum(by_cat.values()), 2),
            "by_category": {k: round(v, 2) for k, v in by_cat.items()}
        })
    return result

def budget_status(db: Session) -> list:
    budgets = db.query(Budget).all()
    today = date.today()
    month_start = today.replace(day=1)
    result = []
    for b in budgets:
        txns = db.query(Transaction).filter(
            Transaction.deleted == False,
            Transaction.category == b.category,
            Transaction.date >= month_start, Transaction.date <= today
        ).all()
        total_spent = sum(t.amount for t in txns)
        pct = round(total_spent / b.monthly_limit, 3) if b.monthly_limit > 0 else 0
        result.append({
            "id": b.id, "category": b.category, "limit": b.monthly_limit,
            "spent": round(total_spent, 2),
            "remaining": round(max(0, b.monthly_limit - total_spent), 2),
            "utilisation_pct": min(pct, 1.0),
            "alert": pct >= b.alert_threshold,
            "over_budget": pct > 1.0,
        })
    return result

def detect_anomalies(db: Session) -> list:
    ninety_days_ago = date.today() - timedelta(days=90)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False, Transaction.date >= ninety_days_ago
    ).all()
    by_category = defaultdict(list)
    for t in txns:
        by_category[t.category].append(t)
    anomalies = []
    for cat, items in by_category.items():
        if len(items) < 5:
            continue
        amounts = [t.amount for t in items]
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0
        if stdev == 0:
            continue
        for t in items:
            z = (t.amount - mean) / stdev
            if z > 2.5:
                anomalies.append({
                    "id": t.id, "merchant": t.merchant, "amount": t.amount,
                    "date": str(t.date), "category": t.category,
                    "z_score": round(z, 2),
                    "message": f"Unusually high: {t.merchant} ₹{t.amount:,.0f} vs avg ₹{mean:,.0f}"
                })
    return sorted(anomalies, key=lambda x: x["z_score"], reverse=True)

def cash_flow_forecast(db: Session, days: int = 30) -> dict:
    today = date.today()
    end = today + timedelta(days=days)
    recurring = db.query(RecurringExpense).filter(
        RecurringExpense.is_active == True,
        RecurringExpense.next_expected <= end
    ).all()
    upcoming = []
    projected_outflow = 0.0
    for r in recurring:
        upcoming.append({
            "merchant": r.merchant, "amount": r.avg_amount,
            "expected_date": str(r.next_expected), "category": r.category
        })
        projected_outflow += r.avg_amount
    avg_monthly = _avg_monthly_spend(db)
    variable = (avg_monthly / 30) * days
    total = projected_outflow + variable
    return {
        "forecast_days": days, "projected_outflow": round(total, 2),
        "recurring_outflow": round(projected_outflow, 2),
        "variable_outflow": round(variable, 2),
        "upcoming_bills": sorted(upcoming, key=lambda x: x["expected_date"]),
        "risk_level": "HIGH" if total > 30000 else "MEDIUM" if total > 15000 else "LOW",
    }

def _avg_monthly_spend(db: Session) -> float:
    three_months_ago = (date.today() - relativedelta(months=3)).replace(day=1)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False,
        Transaction.date >= three_months_ago,
        Transaction.is_recurring == False
    ).all()
    return sum(t.amount for t in txns) / 3 if txns else 5000.0

def detect_recurring(db: Session) -> list:
    six_months_ago = date.today() - relativedelta(months=6)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False, Transaction.date >= six_months_ago
    ).order_by(Transaction.merchant, Transaction.date).all()
    by_merchant = defaultdict(list)
    for t in txns:
        by_merchant[t.merchant.lower().strip()].append(t)
    detected = []
    for merchant, items in by_merchant.items():
        if len(items) < 2:
            continue
        amounts = [t.amount for t in items]
        avg_amount = statistics.mean(amounts)
        dates = sorted([t.date for t in items])
        if len(dates) >= 2:
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_interval = statistics.mean(intervals)
            if 25 <= avg_interval <= 35: freq = "monthly"
            elif 6 <= avg_interval <= 8: freq = "weekly"
            elif 350 <= avg_interval <= 380: freq = "yearly"
            else: continue
            next_exp = dates[-1] + timedelta(days=int(avg_interval))
            detected.append({
                "merchant": items[0].merchant, "avg_amount": round(avg_amount, 2),
                "frequency": freq, "last_seen": str(dates[-1]),
                "next_expected": str(next_exp), "category": items[0].category,
                "occurrences": len(items)
            })
    return detected

def goal_progress(db: Session) -> list:
    goals = db.query(Goal).filter(Goal.status != "deleted").all()
    today = date.today()
    result = []
    for g in goals:
        pct = round(g.current_amount / g.target_amount, 3) if g.target_amount > 0 else 0
        days_left = (g.deadline - today).days if g.deadline else None
        result.append({
            "id": g.id, "name": g.name, "target": g.target_amount,
            "current": g.current_amount,
            "remaining": round(g.target_amount - g.current_amount, 2),
            "pct": min(pct, 1.0), "status": g.status,
            "days_left": days_left,
            "deadline": str(g.deadline) if g.deadline else None,
            "description": g.description,
        })
    return result

def tax_summary(db: Session) -> dict:
    today = date.today()
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    fy_end = date(fy_start.year + 1, 3, 31)
    deductible = db.query(Transaction).filter(
        Transaction.deleted == False, Transaction.tax_deductible == True,
        Transaction.date >= fy_start, Transaction.date <= fy_end
    ).all()
    by_section = defaultdict(float)
    for t in deductible:
        by_section[t.tax_section or "General"] += t.amount
    return {
        "financial_year": f"{fy_start.year}-{str(fy_end.year)[2:]}",
        "total_deductible": round(sum(by_section.values()), 2),
        "by_section": {k: round(v, 2) for k, v in by_section.items()},
        "transactions": [{"merchant": t.merchant, "amount": t.amount, "date": str(t.date), "section": t.tax_section} for t in deductible]
    }
```

---

### `agent.py` — LLM Agent with tool calling

```python
import google.generativeai as genai
from config import settings
from tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, goal_progress, tax_summary)
from sqlalchemy.orm import Session
from datetime import date
import json

genai.configure(api_key=settings.gemini_api_key)

try:
    from groq import Groq
    groq_client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
except Exception:
    groq_client = None

TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "get_spending_summary",
        "description": "Get total spending summary and breakdown by category for a time period",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "enum": ["today", "this_week", "this_month", "last_month", "last_3_months", "this_year"]}
        }, "required": ["period"]}
    }},
    {"type": "function", "function": {
        "name": "get_monthly_trend",
        "description": "Get spending trend across multiple months",
        "parameters": {"type": "object", "properties": {
            "months": {"type": "integer", "description": "Number of months (default 6)"}
        }}
    }},
    {"type": "function", "function": {
        "name": "get_budget_status",
        "description": "Get current budget utilisation for all categories",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "detect_anomalies",
        "description": "Detect unusual or abnormally high transactions",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "get_cash_flow_forecast",
        "description": "Forecast upcoming expenses for next 30, 60, or 90 days",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "enum": [30, 60, 90]}
        }, "required": ["days"]}
    }},
    {"type": "function", "function": {
        "name": "get_goal_progress",
        "description": "Get savings goals and progress",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "get_tax_summary",
        "description": "Get tax-deductible expenses summary for current financial year",
        "parameters": {"type": "object", "properties": {}}
    }},
]

SYSTEM_PROMPT = f"""You are Finn, a warm and sharp personal finance advisor.

You have access to the user's complete transaction history and powerful analysis tools.

TODAY: {date.today().strftime("%d %B %Y")}

YOUR STYLE:
- Friendly, direct — like a smart friend who knows finance
- Always add context: "that's 23% more than last month"
- Spot patterns and mention them proactively
- Give concrete, actionable suggestions
- Format amounts as ₹X,XXX
- Keep responses concise, use bullet points for lists

RULES:
- Always use tools to get real data — never invent numbers
- If asked "how am I doing?" run summary + budget_status + anomalies
- After data, always end with 1-2 actionable insights
"""

def run_tool(name: str, args: dict, db: Session) -> str:
    if name == "get_spending_summary":
        return json.dumps(spending_summary(db, args.get("period", "this_month")))
    elif name == "get_monthly_trend":
        return json.dumps(monthly_trend(db, args.get("months", 6)))
    elif name == "get_budget_status":
        return json.dumps(budget_status(db))
    elif name == "detect_anomalies":
        return json.dumps(detect_anomalies(db))
    elif name == "get_cash_flow_forecast":
        return json.dumps(cash_flow_forecast(db, args.get("days", 30)))
    elif name == "get_goal_progress":
        return json.dumps(goal_progress(db))
    elif name == "get_tax_summary":
        return json.dumps(tax_summary(db))
    return json.dumps({"error": "unknown tool"})

def chat(user_message: str, history: list, db: Session) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    if groq_client:
        response = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=messages, tools=TOOLS_SCHEMA, tool_choice="auto", max_tokens=2000,
        )
        msg = response.choices[0].message
        if msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = run_tool(tc.function.name, args, db)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            final = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile", messages=messages, max_tokens=2000
            )
            return final.choices[0].message.content
        return msg.content
    else:
        # Gemini fallback
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)
        context = f"\nCONTEXT:\n{json.dumps(spending_summary(db, 'this_month'))}"
        response = model.generate_content(context + "\nUSER: " + user_message)
        return response.text
```

---

### `main.py` — All routes in one file

```python
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import os, uuid, shutil
from pathlib import Path

from config import settings
from database import get_db, init_db
from models import Transaction, Budget, Goal, RecurringExpense, ChatMessage
from ocr import extract_from_file
from tools import (spending_summary, monthly_trend, budget_status, detect_anomalies,
                   cash_flow_forecast, detect_recurring, goal_progress, tax_summary, categorise)
import agent

app = FastAPI(title="Expense Tracker Agent")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)
Path(settings.upload_dir).mkdir(exist_ok=True)

@app.on_event("startup")
def startup(): init_db()

# ── UPLOAD ────────────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    allowed = ["image/jpeg", "image/png", "image/webp", "application/pdf", "image/heic"]
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    save_path = f"{settings.upload_dir}/{file_id}{ext}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = await extract_from_file(save_path)
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {str(e)}")
    return {"file_id": file_id, "extracted": result}

@app.post("/api/upload/confirm")
def confirm_transactions(data: dict, db: Session = Depends(get_db)):
    saved = []
    for txn in data.get("transactions", []):
        cat, _ = categorise(txn.get("merchant", ""), txn.get("description", ""))
        if txn.get("category"): cat = txn["category"]
        t = Transaction(
            merchant=txn["merchant"], amount=float(txn["amount"]),
            currency=txn.get("currency", "INR"), category=cat,
            date=date.fromisoformat(txn["date"]),
            source=txn.get("source", "receipt"),
            description=txn.get("description", ""),
            file_id=txn.get("file_id", ""),
        )
        db.add(t); saved.append(t.id)
    db.commit()
    _sync_recurring(db)
    return {"saved": len(saved), "transaction_ids": saved}

# ── TRANSACTIONS ──────────────────────────────────────────────────────────────
class TransactionIn(BaseModel):
    merchant: str
    amount: float
    category: Optional[str] = None
    date: str
    description: Optional[str] = ""
    source: Optional[str] = "manual"

@app.get("/api/transactions")
def list_transactions(
    category: Optional[str] = None, search: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    page: int = 1, limit: int = 30, db: Session = Depends(get_db)
):
    q = db.query(Transaction).filter(Transaction.deleted == False)
    if category: q = q.filter(Transaction.category == category)
    if search: q = q.filter(Transaction.merchant.ilike(f"%{search}%"))
    if date_from: q = q.filter(Transaction.date >= date.fromisoformat(date_from))
    if date_to: q = q.filter(Transaction.date <= date.fromisoformat(date_to))
    total = q.count()
    txns = q.order_by(Transaction.date.desc()).offset((page-1)*limit).limit(limit).all()
    return {"total": total, "page": page, "limit": limit, "transactions": [_txn_dict(t) for t in txns]}

@app.post("/api/transactions")
def add_transaction(txn: TransactionIn, db: Session = Depends(get_db)):
    cat = txn.category or categorise(txn.merchant, txn.description or "")[0]
    t = Transaction(merchant=txn.merchant, amount=txn.amount, category=cat,
                    date=date.fromisoformat(txn.date), description=txn.description or "",
                    source=txn.source or "manual")
    db.add(t); db.commit(); db.refresh(t)
    return _txn_dict(t)

@app.patch("/api/transactions/{txn_id}")
def update_transaction(txn_id: str, data: dict, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not t: raise HTTPException(404)
    for k, v in data.items():
        if hasattr(t, k): setattr(t, k, v)
    db.commit(); return _txn_dict(t)

@app.delete("/api/transactions/{txn_id}")
def delete_transaction(txn_id: str, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if t: t.deleted = True; db.commit()
    return {"deleted": True}

def _txn_dict(t):
    return {"id": t.id, "merchant": t.merchant, "amount": t.amount, "currency": t.currency,
            "category": t.category, "date": str(t.date), "source": t.source,
            "description": t.description, "tax_deductible": t.tax_deductible, "created_at": str(t.created_at)}

# ── ANALYTICS ─────────────────────────────────────────────────────────────────
@app.get("/api/analytics/summary")
def analytics_summary(period: str = "this_month", db: Session = Depends(get_db)):
    return spending_summary(db, period)

@app.get("/api/analytics/trend")
def analytics_trend(months: int = 6, db: Session = Depends(get_db)):
    return monthly_trend(db, months)

@app.get("/api/analytics/budgets")
def analytics_budgets(db: Session = Depends(get_db)):
    return budget_status(db)

@app.get("/api/analytics/anomalies")
def analytics_anomalies(db: Session = Depends(get_db)):
    return detect_anomalies(db)

@app.get("/api/analytics/forecast")
def analytics_forecast(days: int = 30, db: Session = Depends(get_db)):
    return cash_flow_forecast(db, days)

@app.get("/api/analytics/goals")
def analytics_goals(db: Session = Depends(get_db)):
    return goal_progress(db)

@app.get("/api/analytics/tax")
def analytics_tax(db: Session = Depends(get_db)):
    return tax_summary(db)

# ── BUDGETS ───────────────────────────────────────────────────────────────────
@app.get("/api/budgets")
def get_budgets(db: Session = Depends(get_db)):
    return [{"id": b.id, "category": b.category, "monthly_limit": b.monthly_limit} for b in db.query(Budget).all()]

@app.post("/api/budgets")
def set_budget(data: dict, db: Session = Depends(get_db)):
    existing = db.query(Budget).filter(Budget.category == data["category"]).first()
    if existing:
        existing.monthly_limit = data["monthly_limit"]
    else:
        db.add(Budget(category=data["category"], monthly_limit=data["monthly_limit"],
                      alert_threshold=data.get("alert_threshold", 0.8)))
    db.commit(); return {"saved": True}

@app.delete("/api/budgets/{budget_id}")
def delete_budget(budget_id: str, db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.id == budget_id).first()
    if b: db.delete(b); db.commit()
    return {"deleted": True}

# ── GOALS ─────────────────────────────────────────────────────────────────────
@app.get("/api/goals")
def get_goals(db: Session = Depends(get_db)): return goal_progress(db)

@app.post("/api/goals")
def create_goal(data: dict, db: Session = Depends(get_db)):
    g = Goal(name=data["name"], target_amount=data["target_amount"],
             current_amount=data.get("current_amount", 0),
             deadline=date.fromisoformat(data["deadline"]) if data.get("deadline") else None,
             description=data.get("description", ""))
    db.add(g); db.commit(); db.refresh(g)
    return {"id": g.id, "name": g.name}

@app.patch("/api/goals/{goal_id}")
def update_goal(goal_id: str, data: dict, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if not g: raise HTTPException(404)
    for k, v in data.items():
        if hasattr(g, k): setattr(g, k, v)
    db.commit(); return {"updated": True}

@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: str, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if g: g.status = "deleted"; db.commit()
    return {"deleted": True}

# ── SUBSCRIPTIONS ─────────────────────────────────────────────────────────────
@app.get("/api/subscriptions")
def get_subscriptions(db: Session = Depends(get_db)):
    rows = db.query(RecurringExpense).filter(RecurringExpense.is_active == True).all()
    return [{"id": r.id, "merchant": r.merchant, "avg_amount": r.avg_amount,
             "frequency": r.frequency, "next_expected": str(r.next_expected),
             "category": r.category} for r in rows]

@app.post("/api/subscriptions/detect")
def run_detect_recurring(db: Session = Depends(get_db)):
    detected = detect_recurring(db)
    saved = 0
    for d in detected:
        existing = db.query(RecurringExpense).filter(RecurringExpense.merchant == d["merchant"]).first()
        if not existing:
            r = RecurringExpense(**{k: v for k, v in d.items() if k != "occurrences"})
            db.add(r); saved += 1
    db.commit()
    return {"detected": len(detected), "new": saved, "items": detected}

# ── CHAT ──────────────────────────────────────────────────────────────────────
class ChatIn(BaseModel):
    message: str

@app.post("/api/chat")
def chat_endpoint(body: ChatIn, db: Session = Depends(get_db)):
    history_rows = db.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(10).all()
    history = [{"role": h.role, "content": h.content} for h in reversed(history_rows)]
    db.add(ChatMessage(role="user", content=body.message)); db.commit()
    response = agent.chat(body.message, history, db)
    db.add(ChatMessage(role="assistant", content=response)); db.commit()
    return {"response": response}

@app.get("/api/chat/history")
def chat_history(limit: int = 50, db: Session = Depends(get_db)):
    msgs = db.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    return [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in reversed(msgs)]

@app.delete("/api/chat/history")
def clear_history(db: Session = Depends(get_db)):
    db.query(ChatMessage).delete(); db.commit()
    return {"cleared": True}

@app.get("/health")
def health(): return {"status": "ok"}

def _sync_recurring(db: Session):
    detected = detect_recurring(db)
    for d in detected:
        existing = db.query(RecurringExpense).filter(RecurringExpense.merchant == d["merchant"]).first()
        if not existing:
            r = RecurringExpense(**{k: v for k, v in d.items() if k != "occurrences"})
            db.add(r)
    db.commit()
```

**Run backend:**
```bash
cd backend && uvicorn main:app --reload --port 8000
```

---

## STEP 2 — FRONTEND (`/frontend`)

### Initialize

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-git
npm install axios recharts react-dropzone react-hot-toast lucide-react date-fns clsx react-markdown
```

### `frontend/.env.local`
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## FRONTEND DESIGN SYSTEM

**Aesthetic: Dark finance terminal — sharp, dense, data-forward**

```css
/* CSS variables to use throughout */
--bg-base: #0D0D14;          /* main background */
--bg-surface: #13131F;       /* cards, sidebars */
--bg-raised: #1A1A2E;        /* hover states, modals */
--border: #1E1E2E;           /* all borders */
--accent: #6C63FF;           /* primary actions, active states */
--accent-dim: rgba(108,99,255,0.15); /* accent backgrounds */
--green: #00C896;            /* positive values, success */
--yellow: #F59E0B;           /* warnings, medium alerts */
--red: #EF4444;              /* danger, over budget */
--text-primary: #F1F1F5;     /* main text */
--text-muted: #6B7280;       /* labels, secondary */
--text-faint: #374151;       /* disabled, dividers */

/* Typography */
font-family: 'DM Sans', sans-serif  /* body */
font-family: 'DM Mono', monospace   /* all numbers/amounts */
```

Import fonts in `app/layout.tsx`:
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />
```

**Component patterns:**
- Cards: `bg-[#13131F] border border-[#1E1E2E] rounded-xl p-5`
- Amount text: `font-mono text-[#F1F1F5] tabular-nums`
- Positive delta: `text-[#00C896]` with ↑ arrow
- Negative delta: `text-[#EF4444]` with ↓ arrow
- Category badges: small pill with emoji + name
- All interactive elements: `transition-all duration-150` hover states

---

## FRONTEND PAGES

### `lib/api.ts`

```typescript
import axios from 'axios'
const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000' })
export default api
export const CATEGORIES = [
  "Food & Dining","Transport","Utilities","Shopping","Entertainment",
  "Healthcare","Education","Subscriptions","Travel","Groceries","Miscellaneous"
]
export const CATEGORY_EMOJI: Record<string, string> = {
  "Food & Dining":"🍽️","Transport":"🚗","Utilities":"⚡","Shopping":"🛍️",
  "Entertainment":"🎬","Healthcare":"💊","Education":"📚","Subscriptions":"🔄",
  "Travel":"✈️","Groceries":"🛒","Miscellaneous":"📦"
}
```

---

### `app/layout.tsx`

Root layout with:
- Google Fonts import (DM Sans + DM Mono)
- `<Toaster>` from react-hot-toast
- Background color `#0D0D14`
- Sidebar + main content flex layout
- Mobile: sidebar collapses to bottom nav bar

---

### `components/Sidebar.tsx`

Left sidebar, 220px wide on desktop:
- Header: "💸 Finn" in accent color + tagline "Your money, understood"
- Nav links with lucide icons:
  - `MessageSquare` → /chat → "Chat with Finn"
  - `LayoutDashboard` → /dashboard → "Dashboard"
  - `Receipt` → /transactions → "Transactions"
  - `Target` → /budgets → "Budgets"
  - `Trophy` → /goals → "Goals"
  - `RefreshCw` → /subscriptions → "Subscriptions"
- Active state: left violet bar + `bg-[#1A1A2E]`
- Footer: "⚡ Gemini + Groq" in muted text

On mobile (< 768px): fixed bottom tab bar, 5 icons only, no labels

---

### `app/chat/page.tsx` — MAIN PAGE

Full-height chat interface. Layout:
```
┌──────────────────────────────────┐
│ Header: "Chat with Finn 🤖"      │ [Clear history btn]
├──────────────────────────────────┤
│                                  │
│  Messages area (scrollable)      │
│                                  │
│  [empty state: suggested prompts]│
│                                  │
├──────────────────────────────────┤
│ [📎] [input field          ] [→] │
└──────────────────────────────────┘
```

**Messages:**
- User bubble: right, `bg-[#6C63FF]`, rounded-2xl, no top-right radius
- Finn bubble: left, `bg-[#13131F] border border-[#1E1E2E]`, avatar "F" circle
- Render markdown properly: bold, bullets, headings
- Timestamps: `text-xs text-[#6B7280]` below each bubble
- Auto-scroll to bottom on new message

**Empty state — suggested prompts grid (2x3):**
```
"💰 How much did I spend this month?"
"📊 Am I over budget anywhere?"
"🔍 What are my biggest expenses?"
"📅 Show me upcoming bills"
"🎯 How are my savings goals?"
"⚠️ Any unusual transactions?"
```
Clicking fills input and sends immediately.

**Loading state:** Three animated dots `● ● ●` pulsing in a Finn bubble

**File upload:**
- Paperclip `Paperclip` icon in input bar
- Accepts: `image/*,application/pdf`
- On select: show file name + size chip in input area
- Send → POST `/api/upload` → show "🔍 Extracting transactions..." in chat
- On success → open `UploadConfirmModal`

**`UploadConfirmModal`:**
- Overlay modal
- Title: "Found X transactions" + document_type badge
- Editable table:
  | Merchant | Amount (₹) | Date | Category |
  |----------|-----------|------|----------|
  | editable | editable  | editable | dropdown |
- Each row has a delete (×) button
- "Confirm & Save" → POST `/api/upload/confirm` → toast "✅ X transactions saved!"
- "Cancel" closes modal

---

### `app/dashboard/page.tsx`

**Section 1 — Top KPI Cards (4 in a row):**

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ 💰 This Month│ │ 📊 Txns      │ │ 🎯 Budget    │ │ ⚠️ Alerts    │
│ ₹24,340      │ │ 47           │ │ 3/5 healthy  │ │ 2 anomalies  │
│ ↑12% vs last │ │ avg ₹518/day │ │ ██████░░ 72% │ │ tap to view  │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

**Section 2 — Two column layout:**

Left (60%): **Spending Trend** — Recharts AreaChart
- Last 6 months on X axis
- Stacked area by top 5 categories
- Tooltip shows breakdown on hover
- Data from `/api/analytics/trend`

Right (40%): **Category Breakdown** — Recharts PieChart (donut style)
- Center: total amount
- Legend: category + ₹ amount + % badge
- Data from `/api/analytics/summary?period=this_month`

**Section 3 — Two column layout:**

Left: **Budget Progress**
- Each budget category as a row:
  ```
  Food & Dining 🍽️  ₹8,200 / ₹10,000
  [████████░░] 82%  ⚠️ Near limit
  ```
- Red if > 100%, yellow if > 80%, green otherwise
- "Set Budget" button opens quick modal

Right: **Upcoming Bills**
- List from `/api/analytics/forecast?days=30`
- Each item: merchant emoji + name, amount, days until due
- Items due ≤ 3 days: red badge "Due soon"

**Section 4 — Goals row:**
Goal cards in horizontal scroll:
```
┌──────────────────┐
│ 🏖️ Goa Trip     │
│   ₹18,000/50,000 │
│  ○───────── 36% │  ← SVG circle progress
│  68 days left    │
└──────────────────┘
```

**Section 5 — Anomaly Banner (show only if anomalies exist):**
```
⚠️ 2 unusual transactions detected — ₹4,500 at Amazon (3× your average)  [View Details]
```
Yellow banner at top of page

---

### `app/transactions/page.tsx`

**Toolbar:**
- Search input (searches merchant name)
- Category filter dropdown
- Date range: from/to date pickers
- "Add Transaction" button (opens modal)
- "Export CSV" button (client-side generate)

**Transaction table:**
```
Date       Merchant          Category      Amount    Source
Apr 22  🍽️ Swiggy           Food & Dining  ₹450    receipt 📎
Apr 21  🚗 Uber              Transport      ₹230    bank 🏦
Apr 20  🛍️ Amazon            Shopping     ₹1,899   manual ✏️
```
- Clicking a row opens edit modal
- Edit modal: all fields editable, including tax_deductible toggle
- Delete button with "Are you sure?" inline confirmation
- Pagination: prev/next + page X of Y

**Add Transaction modal:**
- Fields: merchant, amount, date (today default), category dropdown, description, source
- Save button

---

### `app/budgets/page.tsx`

**Header:** "Monthly Budgets" + current month label + "Add Budget" button

**Budget cards grid:**
```
┌─────────────────────────┐
│ 🍽️ Food & Dining        │
│ ₹8,200 spent            │
│ ₹10,000 limit           │
│ [████████░░] 82%        │
│ ₹1,800 remaining        │
│           [Edit] [Delete]│
└─────────────────────────┘
```

**Add/Edit Budget modal:**
- Category dropdown (only show unconfigured categories for Add)
- Monthly limit input
- Alert threshold slider (default 80%)
- Save button

**Bottom section:** "Unbudgeted categories" — list of categories that have spend but no budget set, with quick "Set limit" button

---

### `app/goals/page.tsx`

**Header:** "Savings Goals" + "Add Goal" button

**Goal cards:**
```
┌──────────────────────────────────┐
│ 🏖️ Goa Trip           [Active]  │
│                                  │
│         ╭─────╮                  │
│        ╱  36%  ╲   ← SVG ring   │
│       │ ₹18,000 │                │
│        ╲       ╱                 │
│         ╰─────╯                  │
│                                  │
│ Target: ₹50,000                  │
│ Remaining: ₹32,000               │
│ Deadline: Jun 30, 2025 (68 days) │
│                                  │
│ [+ Add Progress]  [Edit] [Delete]│
└──────────────────────────────────┘
```

SVG progress ring: `stroke-dasharray` and `stroke-dashoffset` for the ring fill

**"Add Progress" modal:**
- Amount input
- Note field
- Updates `current_amount` via PATCH `/api/goals/{id}`

**Add Goal modal:**
- Name, target amount, current amount (optional), deadline (optional), description

---

### `app/subscriptions/page.tsx` (BONUS page — add to sidebar)

**Header:** "Recurring & Subscriptions" + "Detect Now" button

**Subscription cards:**
```
🎬 Netflix          ₹649/month    Next: May 1   [Cancel]
📦 Amazon Prime     ₹299/month    Next: May 15  [Cancel]
🎵 Spotify          ₹119/month    Next: May 8   [Cancel]
```

**"Detect Now" button:** Calls `/api/subscriptions/detect` → shows newly found recurring expenses

**Summary at top:**
```
11 active subscriptions  •  ₹4,240/month total  •  ₹50,880/year
```

---

## START COMMANDS

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open: **http://localhost:3000** → auto-redirects to /chat

---

## IMPLEMENTATION RULES

1. **No auth, no login pages** — app opens directly to `/chat`
2. **SQLite only** — `expense_tracker.db` auto-created in `/backend` on first run
3. **No Redis, no Qdrant, no external services** — everything local
4. **Files** saved to `/backend/uploads/` folder (create if missing)
5. **API keys** read only from `.env` — never hardcoded
6. **Groq missing** → use Gemini for all LLM tasks gracefully
7. **All INR** amounts displayed with ₹ symbol, monospace font
8. **Mobile responsive** — sidebar becomes bottom tab bar at < 768px
9. **No TypeScript strict errors** — use `any` where needed, don't block build
10. **react-hot-toast** for all success/error feedback (never use `alert()`)
11. **Auto-scroll** chat to bottom on new messages
12. **Loading states** on every API call — skeleton loaders on dashboard, spinner on chat

---

## VERIFY AFTER BUILD

- [ ] Upload a receipt photo → OCR extracts → confirm saves transaction
- [ ] Ask Finn "how much did I spend this month?" → real answer with numbers
- [ ] Dashboard loads with charts populated from transaction data
- [ ] Add a budget → budget progress bar appears
- [ ] Add a goal → goal card with ring appears
- [ ] Transactions page shows list, filter by category works
- [ ] Mobile view: bottom nav visible, sidebar hidden