from enum import Enum
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, UniqueConstraint, DateTime, func
from app.db.base import Base
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

class EnrollmentStatus(str, Enum):
    pending="pending"
    confirmed="confirmed"
    waitlist="waitlist"
    cancelled="cancelled"

class Enrollment(Base):
    __tablename__ = "enrollments"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    status: Mapped[EnrollmentStatus] = mapped_column(default=EnrollmentStatus.pending)
    qr_seed: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student")
    event = relationship("Event")

    __table_args__ = (UniqueConstraint("student_id","event_id", name="uq_enrollment_student_event"),)
