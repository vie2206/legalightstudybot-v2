# models.py
import datetime as dt
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Doubt(Base):
    __tablename__ = "doubt"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    subject = Column(String(50), nullable=False)
    nature = Column(String(50), nullable=False)
    label = Column(String(100), nullable=False)    # custom text if “Other”
    content = Column(Text, nullable=False)         # the student’s question
    timestamp = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)

class DoubtQuota(Base):
    __tablename__ = "doubt_quota"
    # Composite PK on (user_id, date)
    user_id = Column(Integer, primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)
    public_count = Column(Integer, default=0, nullable=False)
    private_count = Column(Integer, default=0, nullable=False)
    last_reset = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
