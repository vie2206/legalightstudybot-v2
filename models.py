# models.py
from sqlalchemy import (
    Column, Integer, String, Date, DateTime,
    Boolean, func
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ────────────────────────────────────────────────
class Doubt(Base):
    __tablename__ = "doubts"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, nullable=False)
    subject     = Column(String(30),  nullable=False)
    nature      = Column(String(30),  nullable=False)
    text        = Column(String(400))          # optional free-text
    media_id    = Column(String(200))          # Telegram file_id (photo / doc)
    media_type  = Column(String(10))           # "photo" | "doc"
    is_public   = Column(Boolean, default=False)
    answered    = Column(Boolean, default=False)
    created_at  = Column(DateTime, server_default=func.now())


class DoubtQuota(Base):
    """Per-user daily quota row (composite PK user_id+date)."""
    __tablename__ = "doubt_quota"

    user_id       = Column(Integer, primary_key=True)
    date          = Column(Date,     primary_key=True)
    public_count  = Column(Integer,  default=0, nullable=False)
    private_count = Column(Integer,  default=0, nullable=False)
