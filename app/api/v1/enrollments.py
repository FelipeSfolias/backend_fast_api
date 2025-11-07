# app/api/v1/enrollments.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_current_user_scoped
from app.api.permissions import Role, require_roles
from app.schemas.user import UserOut
from app.models.enrollment import Enrollment  # ajuste
from app.models.event import Event  # ajuste
from pydantic import BaseModel

class EnrollmentOut(BaseModel):
    id: int
    student_id: int
    event_id: int
    status: str

    class Config:
        from_attributes = True

class EnrollmentCreate(BaseModel):
    student_id: int
    event_id: int

router = APIRouter()

@router.get("/", response_model=List[EnrollmentOut])
def list_enrollments(
    db: Session = Depends(get_db),
    user: UserOut = Depends(get_current_user_scoped),
):
    # LGPD: Aluno só vê matrículas dele; demais perfis veem todas
    stmt = select(Enrollment)
    if user.role == Role.ALUNO:
        stmt = stmt.where(Enrollment.student_id == user.id)  # ajuste se student_id != user_id
    return db.execute(stmt).scalars().all()

@router.post("/", response_model=EnrollmentOut, dependencies=[Depends(require_roles([Role.ORGANIZADOR, Role.ADMIN_CLIENTE]))])
def create_enrollment(
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    obj = Enrollment(student_id=data.student_id, event_id=data.event_id, status="active")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.post("/{enrollment_id}/cancel", response_model=EnrollmentOut, dependencies=[Depends(require_roles([Role.ORGANIZADOR, Role.ADMIN_CLIENTE]))])
def cancel_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    enr = db.get(Enrollment, enrollment_id)
    if not enr:
        raise HTTPException(404, "Matrícula não encontrada")
    enr.status = "canceled"
    db.commit()
    db.refresh(enr)
    return enr
