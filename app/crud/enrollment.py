from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.crud.base import CRUDBase
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.schemas.enrollment import Enrollment as EnrSchema
from app.models.event import Event

class CRUDEnrollment(CRUDBase[Enrollment, EnrSchema, EnrSchema]):
    def enroll(self, db: Session, *, student_id: int, event_id: int, qr_seed: str) -> Enrollment:
        event = db.get(Event, event_id)
        confirmed_count = db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.event_id==event_id, Enrollment.status==EnrollmentStatus.confirmed))
        status = EnrollmentStatus.confirmed
        if event.capacity_total and confirmed_count >= event.capacity_total:
            status = EnrollmentStatus.waitlist
        enr = Enrollment(student_id=student_id, event_id=event_id, status=status, qr_seed=qr_seed)
        db.add(enr); db.commit(); db.refresh(enr)
        return enr

enrollment_crud = CRUDEnrollment(Enrollment)
