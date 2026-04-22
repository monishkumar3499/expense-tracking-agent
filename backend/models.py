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
