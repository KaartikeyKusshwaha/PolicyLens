from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Use SQLite for zero-config local storage
# Create data directory if it doesn't exist
data_dir = Path("data")
data_dir.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/policylens.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
