# database.py
"""
Shared SQLAlchemy helpers.

• engine, SessionLocal
• session_scope() context-manager
• init_db() – create tables at startup
• re-exports of ORM models
"""
import os, contextlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Doubt, DoubtQuota   # re-export

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./legalight.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine        = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal  = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db() -> None:
    Base.metadata.create_all(bind=engine)

@contextlib.contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
