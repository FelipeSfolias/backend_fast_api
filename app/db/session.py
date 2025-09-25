import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def _normalize(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

RAW_DB_URL = os.getenv("DATABASE_URL")
if not RAW_DB_URL or RAW_DB_URL.strip() == "":
    RAW_DB_URL = "sqlite:///./data/events.db"  # fallback dev

SQLALCHEMY_DATABASE_URL = _normalize(RAW_DB_URL)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
