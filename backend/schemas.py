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
    bill_name: str = ""
    bill_total: float = 0.0
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

class RecurringExpenseBase(BaseModel):
    merchant: str
    avg_amount: float
    category: str = "Miscellaneous"
    frequency: str = "monthly" # monthly, yearly, 6-months, 3-months
    last_seen: Optional[date] = None
    next_expected: Optional[date] = None

class RecurringExpenseCreate(RecurringExpenseBase):
    pass

class RecurringExpense(RecurringExpenseBase):
    id: str
    is_active: bool
    class Config:
        from_attributes = True

class FinancialGoalBase(BaseModel):
    timeline: str   # 1_month, 6_months, 1_year
    total_budget: float
    category_budgets: dict = {}   # {"Food": 1000, ...}
    start_date: date
    end_date: date

class FinancialGoalCreate(FinancialGoalBase):
    pass

class FinancialGoal(FinancialGoalBase):
    id: str
    status: str = "active"
    created_at: datetime
    class Config:
        from_attributes = True

class CategoryProgress(BaseModel):
    budget: float
    spent: float
    percentage: float

class FinancialGoalDetail(FinancialGoal):
    total_spent: float
    progress_percentage: float
    category_progress: dict[str, CategoryProgress]
    health_score: float # 0-100, where 100 is good (under budget)
