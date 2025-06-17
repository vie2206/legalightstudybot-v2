# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1) Point to a local file-based SQLite DB
#    The file 'legalight.db' will be created next to this script.
ENGINE = create_engine("sqlite:///legalight.db", echo=False, future=True)

# 2) Our “base” class for all models (tables)
Base = declarative_base()

# 3) Session factory to get DB sessions
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=ENGINE)
