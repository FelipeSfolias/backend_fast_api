from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, UniqueConstraint, DateTime, String
from app.db.base import Base

class AttendanceOrigin(str, Enum):
    gate="gate"
    api="api"
    offline_sync="offline_sync"

class Attendance(Base):
    __tablename__ = "attendances"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"))
    day_event_id: Mapped[int] = mapped_column(ForeignKey("day_events.id"))
    checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default=AttendanceOrigin.gate)

    __table_args__ = (UniqueConstraint("enrollment_id","day_event_id", name="uq_attendance_unique"),)
