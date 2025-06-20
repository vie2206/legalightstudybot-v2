# database.py
"""
Central DB helper.
 • engine + SessionLocal as before
 • session_scope() – safe commit/rollback wrapper
 • init_db() now also *ensures* the `last_reset` column exists on doubt_quotas.
 • re-exports Doubt & DoubtQuota so feature modules can simply:
       from database import session_scope, Doubt, DoubtQuota
"""

import os, contextlib, datetime as dt
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from models import Base, Doubt, DoubtQuota   # ← re-export

# ─────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./legalight.db")
connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine        = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal  = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ─────────────────────────────────────────────────────────────────────
def _ensure_last_reset_column():
    """
    If the *existing* DB (old deploy) lacks `last_reset` in doubt_quotas,
    add it on the fly and back-fill with today.
    (SQLite & Postgres compatible – uses simple SQL text.)
    """
    insp = inspect(engine)
    if "doubt_quotas" not in insp.get_table_names():
        return                     # table will be created fresh anyway

    cols = {c["name"] for c in insp.get_columns("doubt_quotas")}
    if "last_reset" in cols:
        return                     # already present → nothing to do

    today_iso = dt.date.today().isoformat()

    with engine.begin() as conn:
        # 1️⃣ add column
        if DATABASE_URL.startswith("sqlite"):
            conn.exec_driver_sql(
                "ALTER TABLE doubt_quotas ADD COLUMN last_reset DATE"
            )
        else:  # Postgres/MySQL etc.
            conn.exec_driver_sql(
                "ALTER TABLE doubt_quotas ADD COLUMN last_reset DATE"
            )
        # 2️⃣ back-fill existing rows
        conn.exec_driver_sql(
            "UPDATE doubt_quotas SET last_reset = :d", {"d": today_iso}
        )

# ─────────────────────────────────────────────────────────────────────
def init_db():
    """Create missing tables, then ensure `last_reset` exists."""
    Base.metadata.create_all(bind=engine)
    _ensure_last_reset_column()

# ─────────────────────────────────────────────────────────────────────
@contextlib.contextmanager
def session_scope():
    """
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
