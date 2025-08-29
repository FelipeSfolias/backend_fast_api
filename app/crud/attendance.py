from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta
from app.crud.base import CRUDBase
from app.models.attendance import Attendance
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.day_event import DayEvent
from app.core.config import settings
from zoneinfo import ZoneInfo

class CRUDAttendance(CRUDBase[Attendance, None, None]):
    def checkin(self, db: Session, *, enrollment_id: int, day_event_id: int) -> Attendance:
        enr = db.get(Enrollment, enrollment_id)
        if not enr or enr.status != EnrollmentStatus.confirmed:
            raise ValueError("ENROLLMENT_NOT_CONFIRMED")
        day = db.get(DayEvent, day_event_id)
        # janela
        tz = ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)  # agora no fuso do cliente
        start = datetime.combine(day.date, day.start_time).replace(tzinfo=tz)
        end = datetime.combine(day.date, day.end_time).replace(tzinfo=tz)
        if now < (start - timedelta(minutes=settings.CHECKIN_WINDOW_MIN_BEFORE)) or \
           now > (end + timedelta(minutes=settings.CHECKIN_WINDOW_MIN_AFTER)):
            raise ValueError("OUT_OF_WINDOW")
        # único
        att = db.execute(
            select(Attendance).where(
                Attendance.enrollment_id == enrollment_id,
                Attendance.day_event_id == day_event_id
            )
        ).scalar_one_or_none()
        if att and att.checkin_at:
            raise RuntimeError("ALREADY_CHECKED_IN")
        if not att:
            att = Attendance(enrollment_id=enrollment_id, day_event_id=day_event_id)

        att.checkin_at = datetime.now(tz)
        db.add(att); db.commit(); db.refresh(att)
        return att

    def checkout(self, db: Session, *, enrollment_id: int, day_event_id: int) -> Attendance:
        att = db.execute(select(Attendance).where(Attendance.enrollment_id==enrollment_id, Attendance.day_event_id==day_event_id)).scalar_one_or_none()
        if not att or not att.checkin_at:
            raise ValueError("NO_CHECKIN")
        if att.checkout_at:
            return att
        att.checkout_at = datetime.utcnow()
        db.add(att); db.commit(); db.refresh(att)
        return att

attendance_crud = CRUDAttendance(Attendance)
