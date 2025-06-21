# models.py  ── replace the whole file
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean, Text, Enum, func
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

### ─────────────────────────────────────────────────────────────
class Doubt(Base):
    __tablename__ = "doubt"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, nullable=False, index=True)
    ts_created  = Column(DateTime, default=func.now(), nullable=False)

    subject     = Column(String(30),  nullable=False)
    nature      = Column(String(30),  nullable=False)
    question    = Column(Text,       nullable=False)
    media_id    = Column(String(120), nullable=True)

    answered    = Column(Boolean, default=False, nullable=False)
    answer_ts   = Column(DateTime, nullable=True)
    public      = Column(Boolean, default=True,  nullable=False)
    answer_text = Column(Text,    nullable=True)
    answer_mid  = Column(Integer, nullable=True)   # tg message-id of answer


class DoubtQuota(Base):
    """
    Daily quota per user.
    • PK is (user_id, date) so one row per day.
    """
    __tablename__ = "doubt_quota"
    user_id       = Column(Integer, primary_key=True)
    date          = Column(Date,    primary_key=True,
                            default=dt.date.today, server_default=func.date('now'))
    public_count  = Column(Integer, nullable=False, default=0)
    private_count = Column(Integer, nullable=False, default=0)

### ─────────────────────────────────────────────────────────────
# (other existing tables, if any, stay unchanged)
