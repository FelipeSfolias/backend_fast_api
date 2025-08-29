from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, LargeBinary, Integer
from app.db.base import Base

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    user_email: Mapped[str] = mapped_column(String(160))
    tenant_slug: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    signature: Mapped[str] = mapped_column(String(80), index=True)
    response_body: Mapped[bytes] = mapped_column(LargeBinary)
    response_mime: Mapped[str] = mapped_column(String(80))
    status_code: Mapped[int] = mapped_column(Integer)
