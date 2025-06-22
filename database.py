# database.py
"""
DB helper: creates engine / session factory and a contextmanager.
Re-exports the model classes for convenience (no circular import).
"""

import os, contextlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models  # ← owns Base + tables

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./legalight.db")

connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
engine        = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal  = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def init_db():
    models.Base.metadata.create_all(bind=engine)

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

# handy re-exports (NOT imported by models, so no loop)
Doubt       = models.Doubt
DoubtQuota  = models.DoubtQuota
