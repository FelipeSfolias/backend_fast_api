from enum import Enum
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, DateTime
from app.db.base import Base

class CertificateStatus(str, Enum):
    issued="issued"
    revoked="revoked"

class Certificate(Base):
    __tablename__ = "certificates"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pdf_url: Mapped[str] = mapped_column(String(255))
    verify_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[CertificateStatus] = mapped_column(default=CertificateStatus.issued)
