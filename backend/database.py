from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import settings

engine = create_engine(f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False})
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
    
    # Clear chat history on startup for session-based experience
    db = SessionLocal()
    try:
        db.query(ChatMessage).delete()
        db.commit()
    finally:
        db.close()
