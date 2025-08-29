from typing import Any, Dict
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, JSON, DateTime, func, ForeignKey
from app.db.base import Base
from typing import Any, Dict
from datetime import datetime

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int]
    action: Mapped[str] = mapped_column(String(30))
    diff_json: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
