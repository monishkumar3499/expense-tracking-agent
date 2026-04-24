from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import SessionLocal, engine, init_db
from config import settings
import models, schemas
from pathlib import Path
import json, uuid, shutil
from datetime import datetime, date, timedelta
from finance_tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, detect_recurring, goal_progress, tax_summary, categorise)
from graph import ProductionAgent
import agent # Keep for legacy compatibility during transition if needed
from typing import List, Optional, AsyncGenerator
import asyncio
from logs import log_manager

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [STARTUP] Initializing database...")
    init_db()
    print("✅ [STARTUP] Database ready.")
    yield
    print("🛑 [SHUTDOWN] Closing connections...")

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
    log_manager.push(f"Received file: {file.filename}")
    
    # Save file to temp location for processing
    suffix = Path(file.filename or "upload").suffix or ".jpg"
    temp_path = Path(settings.upload_dir) / f"{uuid.uuid4().hex}{suffix}"
    
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process with Mistral OCR Pipeline
        from mistral_pipeline import extract_with_mistral
        log_manager.push("Initializing Mistral OCR...")
        final_result = extract_with_mistral(str(temp_path))
        log_manager.push("Structuring extracted data...")
        
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
    query = db.query(models.Transaction).filter(models.Transaction.deleted == False)
    if search:
        query = query.filter(models.Transaction.merchant.ilike(f"%{search}%"))
    if category:
        query = query.filter(models.Transaction.category == category)
    
    total = query.count()
    txns = query.order_by(desc(models.Transaction.date)).offset((page-1)*limit).limit(limit).all()
    return {"transactions": txns, "total": total}

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

# ── BUDGETS ──────────────────────────────────────────────────────────────────
@app.post("/api/budgets")
def create_budget(budget: schemas.BudgetCreate, db: Session = Depends(get_db)):
    db_budget = models.Budget(**budget.model_dump())
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget

@app.delete("/api/budgets/{id}")
def delete_budget(id: str, db: Session = Depends(get_db)):
    db_b = db.query(models.Budget).filter(models.Budget.id == id).first()
    if db_b:
        db.delete(db_b)
        db.commit()
    return {"status": "success"}

# ── GOALS ────────────────────────────────────────────────────────────────────
@app.post("/api/goals")
def create_goal(goal: schemas.GoalCreate, db: Session = Depends(get_db)):
    db_goal = models.Goal(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

# ── ANALYTICS ────────────────────────────────────────────────────────────────
@app.get("/api/analytics/summary")
def api_summary(period: str = "this_month", db: Session = Depends(get_db)):
    from logs import log_manager
    log_manager.push(f"Refreshing {period.replace('_', ' ')} summary...")
    return spending_summary(db, period)

@app.get("/api/analytics/trend")
def api_trend(months: int = 6, db: Session = Depends(get_db)):
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

@app.get("/api/analytics/goals")
def api_goals(db: Session = Depends(get_db)):
    return goal_progress(db)

# ── SUBSCRIPTIONS ────────────────────────────────────────────────────────────
@app.get("/api/subscriptions")
def get_subs(db: Session = Depends(get_db)):
    return db.query(models.RecurringExpense).all()

@app.post("/api/subscriptions/detect")
def api_detect_subs(db: Session = Depends(get_db)):
    log_manager.push("Scanning transactions for patterns...")
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

# ── CHAT ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
def chat_endpoint(body: schemas.ChatRequest, db: Session = Depends(get_db)):
    history = db.query(models.ChatMessage).order_by(models.ChatMessage.id).all()
    history_list = [{"role": m.role, "content": m.content} for m in history]
    
    # Save user message
    user_msg = models.ChatMessage(role="user", content=body.message)
    db.add(user_msg)
    db.commit()
    
    # Use the new Official LangGraph ProductionAgent
    agent_executor = ProductionAgent(db)
    response = agent_executor.execute(body.message, history_list)
    
    # Save assistant message
    assistant_msg = models.ChatMessage(role="assistant", content=response)
    db.add(assistant_msg)
    db.commit()
    
    return {"response": response}

@app.get("/api/chat/history")
def get_chat_history(db: Session = Depends(get_db)):
    return db.query(models.ChatMessage).order_by(models.ChatMessage.id).all()

@app.delete("/api/chat/history")
def clear_chat_history(db: Session = Depends(get_db)):
    db.query(models.ChatMessage).delete()
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
