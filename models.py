"""
models.py  – SQLAlchemy ORM definitions
Add any new tables here; database.py imports `Base` and runs Base.metadata.create_all().
"""

import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Text
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ─────────────────────────────────────────────────────────────
# ⬇ existing tables from your project (keep them) …
# Example:
# class TimerLog(Base):
#     __tablename__ = "timer_log"
#     id        = Column(Integer, primary_key=True)
#     user_id   = Column(Integer, nullable=False, index=True)
#     started   = Column(DateTime, default=dt.datetime.utcnow)
#     seconds   = Column(Integer, default=0)
#
# (Leave your current definitions untouched – just add the two below.)

# ─────────────────────────────────────────────────────────────
# 1️⃣  Doubt table
class Doubt(Base):
    __tablename__ = "doubts"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, nullable=False, index=True)
    subject       = Column(String(64))
    nature        = Column(String(64))
    text          = Column(Text)
    photo_file_id = Column(String(256))
    pdf_file_id   = Column(String(256))
    public        = Column(Boolean, default=True)
    asked_at      = Column(DateTime, default=dt.datetime.utcnow)
    answered_at   = Column(DateTime)

# 2️⃣  Daily quota tracker
class DoubtQuota(Base):
    __tablename__ = "doubt_quota"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, nullable=False, index=True)
    date          = Column(Date, nullable=False, index=True)
    public_count  = Column(Integer, default=0)
    private_count = Column(Integer, default=0)
    last_reset    = Column(Date, nullable=True) 
