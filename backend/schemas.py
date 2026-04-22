from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime

class TransactionBase(BaseModel):
    merchant: str
    amount: float
    currency: str = "INR"
    category: str = "Miscellaneous"
    subcategory: str = ""
    date: date
    source: str = "manual"
    description: str = ""
    file_id: str = ""
    tax_deductible: bool = False
    tax_section: str = ""

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: str
    created_at: datetime
    class Config:
        from_attributes = True

class TransactionList(BaseModel):
    transactions: List[TransactionCreate]

class BudgetBase(BaseModel):
    category: str
    monthly_limit: float
    alert_threshold: float = 0.8

class BudgetCreate(BudgetBase):
    pass

class Budget(BudgetBase):
    id: str
    class Config:
        from_attributes = True

class GoalBase(BaseModel):
    name: str
    target_amount: float
    current_amount: float = 0.0
    deadline: Optional[date] = None
    description: str = ""

class GoalCreate(GoalBase):
    pass

class Goal(GoalBase):
    id: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str
