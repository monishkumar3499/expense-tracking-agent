from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import SessionLocal, engine, init_db
from config import settings
import models, schemas
from pathlib import Path
import json, uuid
from datetime import datetime, date, timedelta
from ocr import extract_from_file
from tools import (spending_summary, monthly_trend, budget_status,
                   detect_anomalies, cash_flow_forecast, detect_recurring, goal_progress, tax_summary, categorise)
import agent
from typing import List, Optional

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

# Dependency
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ── UPLOAD ────────────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    print(f"📥 [API] Uploading file: {file.filename}")
    file_path = f"{settings.upload_dir}/{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        data = await extract_from_file(file_path)
        data["file_id"] = file.filename
        print(f"✅ [API] OCR Complete for {file.filename}")
        return data
    except Exception as e:
        print(f"❌ [API] OCR Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    return detect_recurring(db)

# ── CHAT ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
def chat_endpoint(body: schemas.ChatRequest, db: Session = Depends(get_db)):
    history = db.query(models.ChatMessage).order_by(models.ChatMessage.id).all()
    history_list = [{"role": m.role, "content": m.content} for m in history]
    
    # Save user message
    user_msg = models.ChatMessage(role="user", content=body.message)
    db.add(user_msg)
    db.commit()
    
    response = agent.chat(body.message, history_list, db)
    
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
