# models.py
"""
SQLAlchemy models for Legalight Study Bot.
------------------------------------------------
• Base           – declarative base used everywhere.
• Doubt          – each question a student submits.
• DoubtQuota     – per-user daily quota (public / private counters).
"""

import enum
import datetime as dt

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ----------------------------------------------------------------------
# Enums to keep subject / nature values consistent throughout the app
# (⚠ These *must* match the labels used in doubts.py)
class Subject(enum.Enum):
    ENGLISH           = "English & RC"
    LEGAL             = "Legal Reasoning"
    LOGICAL           = "Logical Reasoning"
    MATHS             = "Mathematics"
    GK                = "GK / Current Affairs"
    MOCK              = "Mock Test"
    SECTIONAL         = "Sectional Test"
    STRATEGY          = "Strategy / Time-Mgmt"
    APPLICATION       = "Application / College"
    OTHER             = "Other / Custom"


class Nature(enum.Enum):
    CANT_SOLVE        = "Can’t solve"
    CANT_ANSWER       = "Don’t understand answer"
    WRONG_ANSWER      = "Explain my wrong answer"
    CONCEPT           = "Concept clarification"
    ALT_METHOD        = "Alternative method"
    SOURCE_REQUEST    = "Source / reference request"
    TIME_MGMT         = "Time-management advice"
    STRATEGY          = "Test-taking strategy"
    OTHER             = "Other / Custom"


# ----------------------------------------------------------------------
class Doubt(Base):
    """
    One row per student question.
    A media file (photo / PDF) is stored as Telegram file_id.
    """
    __tablename__ = "doubts"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, index=True, nullable=False)
    subject         = Column(String(40), nullable=False)   # Subject.value
    nature          = Column(String(40), nullable=False)   # Nature.value
    question_text   = Column(Text, nullable=True)
    question_file   = Column(String(200), nullable=True)   # TG file_id
    is_public       = Column(Boolean, default=False, nullable=False)

    # --- answer fields (filled by admin later) ---
    answer_text     = Column(Text, nullable=True)
    answer_file     = Column(String(200), nullable=True)   # TG file_id
    answered        = Column(Boolean, default=False, nullable=False)
    answered_at     = Column(DateTime, nullable=True)

    created_at      = Column(DateTime, default=dt.datetime.utcnow, nullable=False)


# ----------------------------------------------------------------------
class DoubtQuota(Base):
    """
    Per-user daily quota counters.
    Primary-key = user_id so we always have at most 1 row / user.
    `last_reset` tracks the date these counters were last zeroed.
    """
    __tablename__ = "doubt_quota"

    user_id        = Column(Integer, primary_key=True)
    last_reset     = Column(Date, default=dt.date.today, nullable=False)
    public_count   = Column(Integer, default=0, nullable=False)
    private_count  = Column(Integer, default=0, nullable=False)
