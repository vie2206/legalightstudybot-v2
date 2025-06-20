# database.py
"""
Central DB helper.
 • engine + SessionLocal as before
 • session_scope()  – safe commit/rollback wrapper
 • re-exports of Doubt & DoubtQuota so feature modules can do:
       from database import session_scope, Doubt, DoubtQuota
"""

import os
import contextlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Doubt, DoubtQuota  # ← re-export

# ─────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./legalight.db")

# For SQLite only: allow multithread access
connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ─────────────────────────────────────────────────────────────
def init_db():
    """Create any missing tables at startup."""
    Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────────────────────────
@contextlib.contextmanager
def session_scope():
    """
    Usage:
        with session_scope() as db:
            db.add(obj)
    Auto-commits on success, rolls back on error.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
