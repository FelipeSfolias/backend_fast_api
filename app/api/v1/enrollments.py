# app/api/v1/enrollments.py
from __future__ import annotations
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.event import Event

router = APIRouter()  # <<< NÃO redefinir este router em nenhum outro ponto do arquivo

# ------------------------ helpers ------------------------

STATUS_CANCELED = {"canceled", "cancelled"}
STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"

def _bool_param(val) -> bool:
    if isinstance(val, bool): return val
    if isinstance(val, str): return val.lower() in {"1", "true", "t", "yes", "y", "on"}
    return False

def _new_qr_seed(n: int = 20) -> str:
    # string curta e URL-safe
    return secrets.token_urlsafe(n)[:n]

def _expand_param(raw: str) -> set[str]:
    return {p.strip() for p in (raw or "").split(",") if p.strip()}

def _enr_to_dict(enr: Enrollment) -> dict:
    return {
        "id": enr.id,
        "student_id": enr.student_id,
        "event_id": enr.event_id,
        "status": enr.status,
    }

def _list_enrollments_core(
    db: Session,
    tenant,
    event_id: int | None,
    status: str | None,
    expand: set[str],
):
    stmt = (
        select(Enrollment)
        .join(Event, Enrollment.event_id == Event.id)
        .where(Event.client_id == tenant.id)
    )
    if event_id is not None:
        stmt = stmt.where(Enrollment.event_id == event_id)
    if status:
        stmt = stmt.where(Enrollment.status == status)

    opts = []
    if "student" in expand:
        opts.append(joinedload(Enrollment.student))
    if "event" in expand:
        opts.append(joinedload(Enrollment.event))
    if opts:
        stmt = stmt.options(*opts)

    rows = db.execute(stmt).scalars().all()
    out = []
    for enr in rows:
        d = _enr_to_dict(enr)
        if "student" in expand and getattr(enr, "student", None):
            st = enr.student
            d["student"] = {
                "id": st.id,
                "name": getattr(st, "name", None),
                "email": getattr(st, "email", None),
                "cpf": getattr(st, "cpf", None),
                "ra": getattr(st, "ra", None),
                "phone": getattr(st, "phone", None),
            }
        if "event" in expand and getattr(enr, "event", None):
            ev = enr.event
            d["event"] = {
                "id": ev.id,
                "title": getattr(ev, "title", None),
                "description": getattr(ev, "description", None),
                "venue": getattr(ev, "venue", None),
                "start_at": getattr(ev, "start_at", None),
                "end_at": getattr(ev, "end_at", None),
                "status": getattr(ev, "status", None),
                "capacity_total": getattr(ev, "capacity_total", None),
                "workload_hours": getattr(ev, "workload_hours", None),
                "min_presence_pct": getattr(ev, "min_presence_pct", None),
            }
        out.append(d)
    return out

# ------------------------ endpoints: LISTAGEM ------------------------

@router.get("/enrollments")
@router.get("/enrollments/")          # com barra
@router.get("")                       # compat raiz do tenant
@router.get("/")                      # compat raiz do tenant
def list_enrollments(
    event_id: int | None = Query(None, alias="event_id"),
    status: str | None = Query(None, alias="status"),
    expand: str = Query("", description="Comma-separated: student,event"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    return _list_enrollments_core(db, tenant, event_id, status, _expand_param(expand))

@router.get("/events/{event_id}/enrollments")
def list_enrollments_by_event(
    event_id: int,
    status: str | None = Query(None, alias="status"),
    expand: str = Query("", description="Comma-separated: student,event"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    return _list_enrollments_core(db, tenant, event_id, status, _expand_param(expand))

# ------------------------ endpoints: CREATE/CANCEL ------------------------

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
            return _enr_to_dict(existing)
        if existing.status in STATUS_CANCELED and reactivate:
            existing.status = STATUS_PENDING
            db.add(existing); db.commit(); db.refresh(existing)
            return _enr_to_dict(existing)
        if existing.status not in STATUS_CANCELED:
            raise HTTPException(status_code=409, detail="already_enrolled")
        raise HTTPException(status_code=409, detail="enrollment_canceled")

    enr = Enrollment(student_id=student_id, event_id=event_id, status=STATUS_PENDING)

    # Preenche qr_seed se existir e for NOT NULL
    if hasattr(Enrollment, "qr_seed") and not getattr(enr, "qr_seed", None):
        setattr(enr, "qr_seed", _new_qr_seed())

    db.add(enr)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        pgcode = getattr(getattr(e, "orig", None), "pgcode", None)
        if pgcode == "23505":  # unique_violation
            if idem and existing:
                return _enr_to_dict(existing)
            raise HTTPException(status_code=409, detail="duplicate_enrollment")
        if pgcode == "23502":  # not_null_violation
            raise HTTPException(status_code=500, detail="missing_required_column (qr_seed?)")
        raise HTTPException(status_code=500, detail="db_error")

    db.refresh(enr)
    return _enr_to_dict(enr)

@router.post("/enrollments/{enr_id}/cancel")
def cancel_enrollment(
    enr_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    enr = db.execute(
        select(Enrollment)
        .join(Event, Enrollment.event_id == Event.id)
        .where(Enrollment.id == enr_id, Event.client_id == tenant.id)
    ).scalar_one_or_none()
    if not enr:
        raise HTTPException(status_code=404, detail="enrollment_not_found")
    enr.status = "canceled"
    db.add(enr); db.commit(); db.refresh(enr)
    return _enr_to_dict(enr)
