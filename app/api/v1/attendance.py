# app/api/v1/attendance.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
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
        )
    ).scalar_one_or_none()
    return st

@router.get("/", response_model=List[AttendanceOut])
def list_attendance(
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
