# database.py
"""
DB helper – _no_ cross-imports with `models.py`.

• engine / SessionLocal creation
• session_scope() context-manager
• init_db() – called once from bot.py
"""

import os
import contextlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ───────────── engine & session ─────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./legalight.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ───────────── helpers ─────────────
def init_db():
    """Create tables defined in models.py once at start-up."""
    # ‼️  *import here* to avoid circular dependency
    from models import Base
    Base.metadata.create_all(bind=engine)

@contextlib.contextmanager
def session_scope():
    """`with session_scope() as db:` → auto-commit / rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
