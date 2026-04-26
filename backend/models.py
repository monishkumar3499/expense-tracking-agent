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
    bill_name = Column(String, default="")  # Summarized name for the whole receipt
    bill_total = Column(Float, default=0.0)  # Total amount for the whole receipt
    is_recurring = Column(Boolean, default=False)
    tax_deductible = Column(Boolean, default=False)
    tax_section = Column(String, default="")
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FinancialGoal(Base):
    __tablename__ = "financial_goals"
    id = Column(String, primary_key=True, default=gen_id)
    timeline = Column(String, nullable=False)   # 1_month | 6_months | 1_year
    total_budget = Column(Float, nullable=False)
    category_budgets = Column(JSON, default=dict)   # {"Food": 1000, ...}
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String, default="active") # active | deleted
    created_at = Column(DateTime, default=datetime.utcnow)
