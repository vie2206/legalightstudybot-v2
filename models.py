# models.py
from sqlalchemy import Column, Integer, String, Date, Text, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base
import datetime as dt

Base = declarative_base()

# ───────── doubts ─────────
class Doubt(Base):
    __tablename__ = "doubts"
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, nullable=False, index=True)
    subject     = Column(String(40), nullable=False)
    nature      = Column(String(40), nullable=False)
    question    = Column(Text,     nullable=False)
    file_id     = Column(String(120))               # Telegram file-id (photo / doc)
    is_public   = Column(Boolean, default=False)    # False = DM answer
    answered    = Column(Boolean, default=False)
    answer      = Column(Text)
    answered_at = Column(DateTime)

class DoubtQuota(Base):
    """
    Daily quota row – one per user per date.
    """
    __tablename__ = "doubt_quota"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, nullable=False)
    date          = Column(Date,    nullable=False)
    public_count  = Column(Integer, default=0)
    private_count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_doubtquota_user_date"),
    )
