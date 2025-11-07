# app/api/v1/enrollments.py
from __future__ import annotations

import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles, ROLE_ADMIN, ROLE_ORGANIZER, ROLE_ALUNO
from app.models.enrollment import Enrollment as EnrollmentModel
from app.models.student import Student as StudentModel
from app.models.event import Event as EventModel
from app.schemas.enrollment import Enrollment as EnrollmentOut, EnrollmentCreate

router = APIRouter()

def _current_student_id(db: Session, tenant, user) -> Optional[int]:
    """Resolve o Student.id correspondente ao usuário atual (por e-mail + tenant)."""
    st = db.execute(
        select(StudentModel.id).where(
            StudentModel.client_id == tenant.id,
            StudentModel.email == user.email
        )
    ).scalar_one_or_none()
    return st

@router.get("/", response_model=List[EnrollmentOut])
def list_enrollments(
    event_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    user = Depends(get_current_user_scoped),
):
    stmt = (
        select(EnrollmentModel)
        .join(StudentModel, StudentModel.id == EnrollmentModel.student_id)
        .where(StudentModel.client_id == tenant.id)
    )
    if event_id is not None:
        stmt = stmt.where(EnrollmentModel.event_id == event_id)
    if status is not None:
        stmt = stmt.where(EnrollmentModel.status == status)

    # LGPD: aluno só vê as próprias matrículas (por e-mail)
    role_names = {r.name for r in user.roles or []}
    if ROLE_ALUNO in role_names:
        my_sid = _current_student_id(db, tenant, user)
        if not my_sid:
            return []  # sem vínculo de student
        stmt = stmt.where(EnrollmentModel.student_id == my_sid)

    rows = db.execute(stmt).scalars().all()
    return rows

@router.get("/events/{event_id}/enrollments", response_model=List[EnrollmentOut])
def list_enrollments_by_event(
    event_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    user = Depends(get_current_user_scoped),
):
    return list_enrollments(event_id=event_id, status=None, db=db, tenant=tenant, user=user)  # type: ignore

@router.post("/", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def create_enrollment(
    body: EnrollmentCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # valida student e event do mesmo tenant
    st = db.get(StudentModel, body.student_id)
    if not st or st.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Student não encontrado")
    ev = db.get(EventModel, body.event_id)
    if not ev or ev.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # cria matrícula
    obj = EnrollmentModel(
        student_id=body.student_id,
        event_id=body.event_id,
        status="pending",
        qr_seed=secrets.token_hex(16),
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.post("/{enrollment_id}/cancel", response_model=EnrollmentOut,
             dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def cancel_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    enr = db.get(EnrollmentModel, enrollment_id)
    if not enr:
        raise HTTPException(status_code=404, detail="Enrollment não encontrado")
    # valida que matrícula pertence ao tenant via student->client_id
    st = db.get(StudentModel, enr.student_id)
    if not st or st.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Enrollment não encontrado")

    if str(enr.status).lower() not in {"canceled","cancelled"}:
        enr.status = "cancelled"
        db.add(enr); db.commit(); db.refresh(enr)
    return enr
