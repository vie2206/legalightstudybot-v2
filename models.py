# models.py
from sqlalchemy import Column, Integer, Date
from database import Base

class Checkin(Base):
    __tablename__ = "checkins"
    user_id = Column(Integer, primary_key=True)
    date    = Column(Date,    primary_key=True)
