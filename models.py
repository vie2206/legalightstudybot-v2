# models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Date, DateTime, Text, Boolean
import datetime as dt


class Base(DeclarativeBase):
    pass


# ────────────────────────────────────────────
class Doubt(Base):
    __tablename__ = "doubt"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:       Mapped[int]      = mapped_column(Integer, index=True, nullable=False)
    subject:       Mapped[str]      = mapped_column(String(30),  nullable=False)   # e.g. “ENGLISH”
    nature:        Mapped[str]      = mapped_column(String(30),  nullable=False)   # e.g. “CANT_SOLVE”
    text:          Mapped[str]      = mapped_column(Text,        nullable=True)    # user’s question text
    photo_file_id: Mapped[str]      = mapped_column(String(120), nullable=True)    # Telegram file-id
    is_public:     Mapped[bool]     = mapped_column(Boolean,     nullable=False)
    created_at:    Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, nullable=False
    )

    # admin reply
    answer_text:   Mapped[str]      = mapped_column(Text,        nullable=True)
    answer_photo_file_id: Mapped[str] = mapped_column(String(120), nullable=True)
    answered_at:   Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)


class DoubtQuota(Base):
    """
    Composite PK: (user_id, date)
    Daily counters for public/private submissions.
    """
    __tablename__ = "doubt_quota"

    user_id:       Mapped[int]   = mapped_column(Integer, primary_key=True)
    date:          Mapped[dt.date] = mapped_column(Date,    primary_key=True)
    public_count:  Mapped[int]   = mapped_column(Integer,  default=0, nullable=False)
    private_count: Mapped[int]   = mapped_column(Integer,  default=0, nullable=False)
