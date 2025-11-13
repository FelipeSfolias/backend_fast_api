# app/api/v1/attendance.py
from __future__ import annotations
from app.core.rbac import require_roles
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import ROLE_ALUNO
from app.models.attendance import AttendanceOut as Attendance
from app.models.enrollment import Enrollment
from app.models.student import Student as StudentModel
from app.schemas.attendance import Attendance as AttendanceOut
from sqlalchemy.orm import Session, joinedload
from app.models.event import Event
from sqlalchemy import select, and_

router = APIRouter()

def _current_student_id(db: Session, tenant, user) -> Optional[int]:
    st = db.execute(
        select(StudentModel.id).where(
            StudentModel.client_id == tenant.id,
            StudentModel.email == user.email
        )
    ).scalar_one_or_none()
    return st

# GET /{tenant}/attendance?event_id=..&day_id=..&student_id=..
@router.get("/", response_model=List[AttendanceOut],
            dependencies=[Depends(require_roles("admin", "organizer", "portaria"))])
def list_attendance(
    event_id: Optional[int] = None,
    day_id: Optional[int] = None,
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    # Eager load: enrollment -> student, event; day_event
    stmt = (
        select(Attendance)
        .join(Attendance.enrollment)
        .join(Enrollment.event)
        .join(Attendance.day_event)
        .where(Event.client_id == tenant.id)
        .options(
            joinedload(Attendance.enrollment).joinedload(Enrollment.student),
            joinedload(Attendance.enrollment).joinedload(Enrollment.event),
            joinedload(Attendance.day_event),
        )
    )

    conds = []
    if event_id is not None:
        conds.append(Enrollment.event_id == event_id)
    if day_id is not None:
        conds.append(Attendance.day_event_id == day_id)
    if student_id is not None:
        conds.append(Enrollment.student_id == student_id)
    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.scalars(stmt).all()

    # Se status vier como Enum, converto para string antes de validar
    for a in rows:
        if getattr(a.enrollment, "status", None) is not None and hasattr(a.enrollment.status, "value"):
            a.enrollment.status = a.enrollment.status.value  # type: ignore[attr-defined]

    # Pydantic a partir do ORM (graças ao from_attributes)
    return [AttendanceOut.model_validate(a) for a in rows]
