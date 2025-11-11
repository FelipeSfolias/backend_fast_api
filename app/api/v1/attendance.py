# app/api/v1/attendance.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
<<<<<<< HEAD
from app.models.attendance import Attendance
from app.models.enrollment import Enrollment
import datetime as dt
from app.api.v1.users import require_roles

router = APIRouter()

class CheckIn(BaseModel):
    enrollment_id: int
    day_event_id: int
    origin: str | None = "manual"

@router.post("/checkin",  dependencies=[Depends(require_roles("portaria","organizer","admin"))])
def checkin(
    payload: CheckIn,
    tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    enr = db.get(Enrollment, payload.enrollment_id)
    if not enr or enr.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    att = db.execute(
        select(Attendance).where(
            Attendance.enrollment_id == payload.enrollment_id,
            Attendance.day_event_id == payload.day_event_id
=======
from app.core.rbac import ROLE_ALUNO
from app.models.attendance import Attendance as AttendanceModel
from app.models.enrollment import Enrollment as EnrollmentModel
from app.models.student import Student as StudentModel
from app.schemas.attendance import Attendance as AttendanceOut

router = APIRouter()

def _current_student_id(db: Session, tenant, user) -> Optional[int]:
    st = db.execute(
        select(StudentModel.id).where(
            StudentModel.client_id == tenant.id,
            StudentModel.email == user.email
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
        )
    ).scalar_one_or_none()
    return st

<<<<<<< HEAD
    if not att:
        att = Attendance(
            enrollment_id=payload.enrollment_id,
            event_id=enr.event_id,
            day_event_id=payload.day_event_id,
            origin=payload.origin or "manual",
            checkin_at=dt.datetime.utcnow(),
        )
        db.add(att)
    else:
        att.checkin_at = att.checkin_at or dt.datetime.utcnow()

    db.commit()
    db.refresh(att)
    return {"id": att.id, "checkin_at": att.checkin_at}

class CheckOut(BaseModel):
    enrollment_id: int
    day_event_id: int
    
@router.post("/checkout", dependencies=[Depends(require_roles("portaria","organizer","admin"))])
def checkout(
    payload: CheckOut,
    tenant = Depends(get_tenant),
=======
@router.get("/", response_model=List[AttendanceOut])
def list_attendance(
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    user = Depends(get_current_user_scoped),
    event_id: Optional[int] = Query(None),
):
    # base query: by tenant via join enrollment->student
    stmt = (
        select(AttendanceModel)
        .join(EnrollmentModel, EnrollmentModel.id == AttendanceModel.enrollment_id)
        .join(StudentModel, StudentModel.id == EnrollmentModel.student_id)
        .where(StudentModel.client_id == tenant.id)
    )
    if event_id is not None:
        stmt = stmt.where(EnrollmentModel.event_id == event_id)

    role_names = {r.name for r in user.roles or []}
    if ROLE_ALUNO in role_names:
        my_sid = _current_student_id(db, tenant, user)
        if not my_sid:
            return []
        stmt = stmt.where(EnrollmentModel.student_id == my_sid)

    rows = db.execute(stmt).scalars().all()
    return rows
