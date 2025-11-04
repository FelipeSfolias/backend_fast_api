import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def _normalize(url: str) -> str:
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url and url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

RAW = os.getenv("DATABASE_URL")
if not RAW or not RAW.strip():
    RAW = "sqlite:///./data/events.db"  # fallback dev

SQLALCHEMY_DATABASE_URL = _normalize(RAW)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from typing import Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal  # precisa existir no session.py

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
