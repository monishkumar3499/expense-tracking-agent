from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import sys
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from database import SessionLocal, engine, init_db
from config import settings
import models, schemas
from pathlib import Path
import json, uuid, shutil, asyncio
from datetime import datetime, date, timedelta
from finance_tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, detect_recurring, goal_progress, categorise)
from graph import ProductionAgent
from typing import List, Optional, Union
from contextlib import asynccontextmanager

# --- WINDOWS ENCODING FIX ---
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# --- MINIMAL LOG MANAGER (Internal) ---
class LogManager:
    def __init__(self):
        self.listeners: List[asyncio.Queue] = []

    async def subscribe(self):
        queue = asyncio.Queue()
        self.listeners.append(queue)
        try:
            while True:
                msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                if msg is None: break
                yield f"data: {msg}\n\n"
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"
        finally:
            if queue in self.listeners: self.listeners.remove(queue)

    def push(self, msg: str):
        for q in self.listeners: q.put_nowait(msg)

    def stop(self):
        for q in self.listeners: q.put_nowait(None)
        self.listeners.clear()

log_manager = LogManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [STARTUP] Initializing database...")
    init_db()
    print("✅ [STARTUP] Database ready.")
    yield
    print("🛑 [SHUTDOWN] Closing connections...")
    log_manager.stop()

app = FastAPI(title="Expense Tracker Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)
Path(settings.upload_dir).mkdir(exist_ok=True)

# ── LOGS ───────────────────────────────────────────────────────────────────

@app.get("/api/status/stream")
async def stream_logs():
    from fastapi.responses import StreamingResponse
    return StreamingResponse(log_manager.subscribe(), media_type="text/event-stream")

# Dependency
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ── UPLOAD & OCR ──────────────────────────────────────────────────────────────
@app.post("/api/upload")
@app.post("/api/extract")
async def upload_and_extract(file: UploadFile = File(...)):
    print(f"📡 [LOG] Received file: {file.filename}")
    
    # Save file to temp location for processing
    suffix = Path(file.filename or "upload").suffix or ".jpg"
    temp_path = Path(settings.upload_dir) / f"{uuid.uuid4().hex}{suffix}"
    
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process with Mistral OCR Pipeline
        from mistral_pipeline import extract_with_mistral
        print("📡 [LOG] Initializing Mistral OCR...")
        final_result = await asyncio.to_thread(extract_with_mistral, str(temp_path))
        print("📡 [LOG] Structuring extracted data...")
        
        if final_result.get("error"):
            # Fallback or Error
            raise HTTPException(status_code=500, detail=f"Mistral OCR failed: {final_result['error']}")

        # 3. Map to existing schema for frontend compatibility
        mapped_transactions = []
        for t in final_result.get("transactions", []):
            mapped_transactions.append({
                "merchant": t.get("description", "Unknown"),
                "amount": round(float(t.get("amount", 0.0)), 2),
                "date": t.get("date") or date.today().isoformat(),
                "currency": final_result.get("currency", "INR"),
                "category": t.get("category_hint") or "Miscellaneous",
                "description": t.get("description", ""),
                "confidence": 0.99,
                "source": "mistral"
            })
        
        response_data = {
            "transactions": mapped_transactions,
            "document_type": final_result.get("type", "receipt"),
            "bill_name": final_result.get("bill_name", file.filename),
            "bill_total": final_result.get("total", 0.0),
            "confidence": 0.99,
            "file_id": file.filename,
            "raw_text": final_result.get("raw_text", "")
        }
        
        print(f"✅ [API] OCR & Refinement Complete for {file.filename}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [API] Extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Keep the file in upload_dir if needed for later confirm, 
        # or delete if it was just a temp path. 
        # The original code kept it in settings.upload_dir/{file.filename}
        # Let's mirror the original behavior of keeping a copy if requested.
        final_file_path = Path(settings.upload_dir) / file.filename
        if not final_file_path.exists():
            shutil.copy(temp_path, final_file_path)
        if temp_path.exists():
            temp_path.unlink()

@app.post("/api/upload/confirm")
async def confirm_upload(body: schemas.TransactionList, db: Session = Depends(get_db)):
    print(f"💾 [API] Confirming {len(body.transactions)} transactions")
    for t in body.transactions:
        db_t = models.Transaction(**t.model_dump())
        db.add(db_t)
    db.commit()
    print("✅ [API] Transactions saved.")
    return {"status": "success"}

# ── TRANSACTIONS ──────────────────────────────────────────────────────────────
@app.get("/api/transactions")
def get_transactions(
    page: int = 1, limit: int = 15, search: str = "", category: str = "",
    db: Session = Depends(get_db)
):
    # We want to group by file_id (receipts)
    # But for manual ones (no file_id), we want them separate.
    # We'll use a subquery or just group in Python for simplicity since limit is small.
    # However, pagination on GROUPS is tricky in raw SQL.
    # Let's try to fetch all active transactions and group them.
    
    query = db.query(models.Transaction).filter(models.Transaction.deleted == False)
    if search:
        query = query.filter(
            or_(
                models.Transaction.merchant.ilike(f"%{search}%"),
                models.Transaction.bill_name.ilike(f"%{search}%"),
                models.Transaction.category.ilike(f"%{search}%")
            )
        )
    
    all_txns = query.order_by(desc(models.Transaction.date), desc(models.Transaction.created_at)).all()
    
    bills = []
    seen_files = {} # file_id -> bill object
    
    for t in all_txns:
        if t.file_id:
            if t.file_id not in seen_files:
                bill = {
                    "id": t.file_id,
                    "name": t.bill_name or t.merchant,
                    "date": t.date,
                    "total": t.bill_total or t.amount,
                    "items": [],
                    "is_receipt": True
                }
                seen_files[t.file_id] = bill
                bills.append(bill)
            seen_files[t.file_id]["items"].append(t)
            # Ensure total is correct if bill_total was missing
            if not t.bill_total:
                 seen_files[t.file_id]["total"] = sum(item.amount for item in seen_files[t.file_id]["items"])
        else:
            # Manual transaction, treat as a single-item bill
            bills.append({
                "id": t.id,
                "name": t.merchant,
                "date": t.date,
                "total": t.amount,
                "items": [t],
                "is_receipt": False
            })
    
    # Paginate groups
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    return {
        "bills": bills[start_idx:end_idx],
        "total_pages": (len(bills) + limit - 1) // limit,
        "current_page": page
    }

@app.delete("/api/transactions/bill/{bill_id}")
def delete_bill(bill_id: str, db: Session = Depends(get_db)):
    print(f"🗑️ [API] Deleting bill: {bill_id}")
    # Try as file_id
    txns = db.query(models.Transaction).filter(models.Transaction.file_id == bill_id).all()
    if txns:
        for t in txns:
            t.deleted = True
    else:
        # Try as individual ID
        t = db.query(models.Transaction).filter(models.Transaction.id == bill_id).first()
        if t:
            t.deleted = True
            
    db.commit()
    return {"status": "success"}

@app.post("/api/transactions")
def create_transaction(txn: schemas.TransactionCreate, db: Session = Depends(get_db)):
    db_txn = models.Transaction(**txn.model_dump())
    db.add(db_txn)
    db.commit()
    db.refresh(db_txn)
    return db_txn

@app.put("/api/transactions/{id}")
def update_transaction(id: str, txn: schemas.TransactionCreate, db: Session = Depends(get_db)):
    db_txn = db.query(models.Transaction).filter(models.Transaction.id == id).first()
    if not db_txn: raise HTTPException(404)
    for k,v in txn.model_dump().items(): setattr(db_txn, k, v)
    db.commit()
    return db_txn

@app.delete("/api/transactions/{id}")
def delete_transaction(id: str, db: Session = Depends(get_db)):
    db_txn = db.query(models.Transaction).filter(models.Transaction.id == id).first()
    if not db_txn: raise HTTPException(404)
    db_txn.deleted = True
    db.commit()
    return {"status": "success"}

# ── FINANCIAL GOALS (DASHBOARD) ──────────────────────────────────────────────

@app.get("/api/financial-goals", response_model=List[schemas.FinancialGoalDetail])
async def list_financial_goals(db: Session = Depends(get_db)):
    """Unified endpoint for budget tracking using central finance tools."""
    data = budget_status(db)
    # The frontend expects a list directly
    return data["goals"]

@app.put("/api/financial-goals/{goal_id}")
async def update_financial_goal(goal_id: str, goal: schemas.FinancialGoalCreate, db: Session = Depends(get_db)):
    db_goal = db.query(models.FinancialGoal).filter(models.FinancialGoal.id == goal_id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    for key, value in goal.model_dump().items():
        setattr(db_goal, key, value)
    
    db.commit()
    return {"status": "success"}

@app.delete("/api/financial-goals/{goal_id}")
async def delete_financial_goal(goal_id: str, db: Session = Depends(get_db)):
    db_goal = db.query(models.FinancialGoal).filter(models.FinancialGoal.id == goal_id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    db_goal.status = "deleted"
    db.commit()
    return {"status": "success"}

@app.post("/api/financial-goals", response_model=schemas.FinancialGoal)
async def create_financial_goal(goal: schemas.FinancialGoalCreate, db: Session = Depends(get_db)):
    db_goal = models.FinancialGoal(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

# ── SAVINGS GOALS ────────────────────────────────────────────────────────────
@app.get("/api/goals")
def list_savings_goals(db: Session = Depends(get_db)):
    return db.query(models.Goal).filter(models.Goal.status != "deleted").all()

@app.post("/api/goals")
def create_savings_goal(goal: schemas.GoalCreate, db: Session = Depends(get_db)):
    db_goal = models.Goal(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

# ── ANALYTICS ────────────────────────────────────────────────────────────────
@app.get("/api/analytics/summary")
def api_summary(period: str = "this_month", db: Session = Depends(get_db)):
    return spending_summary(db, period)

@app.get("/api/analytics/trend")
def api_trend(months: Union[int, str] = 6, db: Session = Depends(get_db)):
    return monthly_trend(db, months)

@app.get("/api/analytics/budgets")
def api_budgets(db: Session = Depends(get_db)):
    return budget_status(db)

@app.get("/api/analytics/anomalies")
def api_anomalies(db: Session = Depends(get_db)):
    return detect_anomalies(db)

@app.get("/api/analytics/forecast")
def api_forecast(days: int = 30, db: Session = Depends(get_db)):
    return cash_flow_forecast(db, days)

# ── SUBSCRIPTIONS ────────────────────────────────────────────────────────────
@app.get("/api/subscriptions")
def get_subs(db: Session = Depends(get_db)):
    return db.query(models.RecurringExpense).all()

@app.post("/api/subscriptions/detect")
def api_detect_subs(db: Session = Depends(get_db)):
    print("📡 [LOG] Scanning transactions for patterns...")
    return detect_recurring(db)

@app.post("/api/subscriptions")
def create_sub(sub: schemas.RecurringExpenseCreate, db: Session = Depends(get_db)):
    db_sub = models.RecurringExpense(**sub.model_dump())
    if not db_sub.next_expected:
        # Default next expected to 1 month from now if not set
        db_sub.next_expected = date.today() + timedelta(days=30)
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

@app.put("/api/subscriptions/{sub_id}")
def update_sub(sub_id: str, sub: schemas.RecurringExpenseCreate, db: Session = Depends(get_db)):
    db_sub = db.query(models.RecurringExpense).filter(models.RecurringExpense.id == sub_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    for key, value in sub.model_dump().items():
        setattr(db_sub, key, value)
    
    db.commit()
    return {"status": "success"}

@app.delete("/api/subscriptions/{sub_id}")
def delete_sub(sub_id: str, db: Session = Depends(get_db)):
    db_sub = db.query(models.RecurringExpense).filter(models.RecurringExpense.id == sub_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    db.delete(db_sub)
    db.commit()
    return {"status": "success"}

# ── CHAT ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat_endpoint(body: schemas.ChatRequest, db: Session = Depends(get_db)):
    history = db.query(models.ChatMessage).order_by(models.ChatMessage.id).all()
    history_list = [{"role": m.role, "content": m.content} for m in history]
    
    # Save user message
    user_msg = models.ChatMessage(role="user", content=body.message)
    db.add(user_msg)
    db.commit()
    
    # Use the new Official LangGraph ProductionAgent with Log Callback
    agent_executor = ProductionAgent(db, log_callback=log_manager.push)
    response = await agent_executor.execute(body.message, history_list)
    
    # Save assistant message
    assistant_msg = models.ChatMessage(role="assistant", content=response)
    db.add(assistant_msg)
    db.commit()
    
    return {"response": response}

@app.get("/api/chat/history")
def get_chat_history(db: Session = Depends(get_db)):
    # Only return active messages for the UI
    return db.query(models.ChatMessage).filter(models.ChatMessage.is_active == True).order_by(models.ChatMessage.id).all()

@app.delete("/api/chat/history")
def clear_chat_history(db: Session = Depends(get_db)):
    # Deactivate instead of delete
    db.query(models.ChatMessage).filter(models.ChatMessage.is_active == True).update({"is_active": False})
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
