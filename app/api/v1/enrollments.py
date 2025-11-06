# app/api/v1/enrollments.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import secrets

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.event import Event

router = APIRouter()

STATUS_CANCELED = {"canceled", "cancelled"}
STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"

def _bool_param(val):
    if isinstance(val, bool): return val
    if isinstance(val, str): return val.lower() in {"1","true","t","yes","y","on"}
    return False

def _new_qr_seed(n: int = 20) -> str:
    # string curta, URL-safe; ajuste n se quiser maior
    return secrets.token_urlsafe(n)[:n]

def _enr_out(enr: Enrollment) -> dict:
    return {
        "id": enr.id,
        "student_id": enr.student_id,
        "event_id": enr.event_id,
        "status": enr.status,
        # acrescente se quiser expor
        # "qr_seed": getattr(enr, "qr_seed", None),
    }

@router.post("/events/{event_id}/enroll", status_code=201)
def enroll_student(
    event_id: int,
    student_id: int = Query(..., alias="student_id"),
    idempotent: str | bool | None = Query(False, alias="idempotent"),
    reactivate_if_canceled: str | bool | None = Query(True, alias="reactivate_if_canceled"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    idem = _bool_param(idempotent)
    reactivate = _bool_param(reactivate_if_canceled)

    # Escopo por tenant
    ev = db.execute(select(Event).where(Event.id == event_id, Event.client_id == tenant.id)).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="event_not_found")

    st = db.execute(select(Student).where(Student.id == student_id, Student.client_id == tenant.id)).scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="student_not_found")

    existing = db.execute(
        select(Enrollment).where(Enrollment.event_id == event_id, Enrollment.student_id == student_id)
    ).scalar_one_or_none()

    if existing:
        if idem:
            return _enr_out(existing)
        if existing.status in STATUS_CANCELED and reactivate:
            existing.status = STATUS_PENDING
            db.add(existing); db.commit(); db.refresh(existing)
            return _enr_out(existing)
        if existing.status not in STATUS_CANCELED:
            raise HTTPException(status_code=409, detail="already_enrolled")
        raise HTTPException(status_code=409, detail="enrollment_canceled")

    enr = Enrollment(student_id=student_id, event_id=event_id, status=STATUS_PENDING)

    # >>>>>>>>> FIX PRINCIPAL: preencher qr_seed se campo existir e estiver vazio
    if hasattr(Enrollment, "qr_seed") and not getattr(enr, "qr_seed", None):
        setattr(enr, "qr_seed", _new_qr_seed())

    db.add(enr)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # pg codes: 23505 unique_violation, 23502 not_null_violation
        pgcode = getattr(getattr(e, "orig", None), "pgcode", None)
        if pgcode == "23505":
            # duplicado → se idempotent, retorna o existente; senão 409
            if idem and existing:
                return _enr_out(existing)
            raise HTTPException(status_code=409, detail="duplicate_enrollment")
        if pgcode == "23502":
            # not null violation: provavelmente qr_seed não preenchido
            raise HTTPException(status_code=500, detail="missing_required_column (qr_seed?)")
        # outro erro
        raise HTTPException(status_code=500, detail="db_error")
    db.refresh(enr)
    return _enr_out(enr)
