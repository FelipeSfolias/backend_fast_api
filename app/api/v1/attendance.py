from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.attendance import Attendance
from app.models.enrollment import Enrollment
from app.schemas.attendance import Attendance as AttSchema

router = APIRouter()

@router.get("/", response_model=List[AttSchema])
def list_attendance(event_id: int | None = None, day_id: int | None = None, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    stmt = select(Attendance).join(Enrollment).join(Enrollment.event).where(Enrollment.event.has(client_id=tenant.id))
    if event_id: stmt = stmt.where(Enrollment.event_id==event_id)
    if day_id: stmt = stmt.where(Attendance.day_event_id==day_id)
    rows = db.execute(stmt).scalars().all()
    return [AttSchema(id=a.id, enrollment_id=a.enrollment_id, day_event_id=a.day_event_id, checkin_at=a.checkin_at, checkout_at=a.checkout_at, origin=a.origin) for a in rows]
