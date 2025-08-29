from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, UniqueConstraint, DateTime, func
from app.db.base import Base
from datetime import datetime
from typing import Optional, Dict, Any





class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    name: Mapped[str] = mapped_column(String(160))
    cpf: Mapped[str] = mapped_column(String(14))
    email: Mapped[str] = mapped_column(String(160))
    ra: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="students")

    __table_args__ = (
        UniqueConstraint("client_id","email", name="uq_student_email_tenant"),
    )
