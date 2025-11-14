from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, JSON, DateTime, func, Text, Integer
from app.db.base import Base

class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(160))
    cnpj: Mapped[str] = mapped_column(String(20))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # NOVOS
    contact_email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    certificate_template_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_min_presence_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ex.: 75
    lgpd_policy_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    config_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    users = relationship("User", back_populates="client")
    students = relationship("Student", back_populates="client")
    events = relationship("Event", back_populates="client")
    