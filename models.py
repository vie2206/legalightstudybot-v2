# models.py

from sqlalchemy import Column, Integer, Date, Boolean
from database import Base

class Checkin(Base):
    __tablename__ = "checkins"
    user_id = Column(Integer, primary_key=True)
    date    = Column(Date,    primary_key=True)

class StreakAlert(Base):
    __tablename__ = "streak_alerts"
    user_id    = Column(Integer, primary_key=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
