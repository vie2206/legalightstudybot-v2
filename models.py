# models.py
import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TaskLog(Base):
    __tablename__ = 'tasks_log'

    # preset list of allowed task types
    TYPES = [
        'CLAT_MOCK', 'SECTIONAL', 'NEWSPAPER', 'EDITORIAL', 'GK_CA', 'MATHS',
        'LEGAL_REASONING', 'LOGICAL_REASONING', 'CLATOPEDIA',
        'SELF_STUDY', 'ENGLISH', 'STUDY_TASK'
    ]

    id        = Column(Integer, primary_key=True)
    user_id   = Column(Integer, index=True, nullable=False)
    chat_id   = Column(Integer, nullable=False)
    task_type = Column(String, nullable=False)
    start_ts  = Column(DateTime, nullable=False)
    paused_at = Column(DateTime, nullable=True)
    elapsed   = Column(Integer, default=0, nullable=False)  # accumulated seconds
    end_ts    = Column(DateTime, nullable=True)

    def elapsed_str(self) -> str:
        """Return human-readable total elapsed (h m s)."""
        total = self.elapsed
        if self.paused_at is None and self.end_ts is None:
            # still running, add live seconds
            delta = datetime.datetime.utcnow() - self.start_ts
            total += int(delta.total_seconds())
        hrs, rem = divmod(total, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if hrs:
            parts.append(f"{hrs}h")
        if mins or hrs:
            parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return " ".join(parts)
