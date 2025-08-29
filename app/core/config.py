# app/core/config.py
import os
from typing import ClassVar
from pydantic import BaseModel, Field

def _default_database_url() -> str:
    data_dir = os.path.abspath(os.getenv("DATA_DIR", "./data"))
    os.makedirs(data_dir, exist_ok=True)
    return os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(data_dir, 'events.db')}")

class Settings(BaseModel):
    # Constante (não vira campo Pydantic)
    DATA_DIR: ClassVar[str] = os.path.abspath(os.getenv("DATA_DIR", "./data"))

    # Campos de configuração
    DATABASE_URL: str = Field(default_factory=_default_database_url)
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "CHANGE_ME_SUPER_SECRET"))
    REFRESH_SECRET_KEY: str = Field(default_factory=lambda: os.getenv("REFRESH_SECRET_KEY", "CHANGE_ME_ANOTHER_SECRET"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")))
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default_factory=lambda: int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")))
    QR_ROTATION_SECONDS: int = Field(default_factory=lambda: int(os.getenv("QR_ROTATION_SECONDS", "45")))
    CHECKIN_WINDOW_MIN_BEFORE: int = Field(default_factory=lambda: int(os.getenv("CHECKIN_WINDOW_MIN_BEFORE", "30")))
    CHECKIN_WINDOW_MIN_AFTER: int = Field(default_factory=lambda: int(os.getenv("CHECKIN_WINDOW_MIN_AFTER", "30")))
    TIMEZONE: str = Field(default_factory=lambda: os.getenv("TIMEZONE", "America/Sao_Paulo"))

settings = Settings()
