from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.event import Event

router = APIRouter()

STATUS_CANCELED = {"canceled", "cancelled"}  # tolerar os dois
STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"

def _bool_param(val: str | bool | None) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in {"1","true","t","yes","y","on"}
    return False

def _enr_out(enr: Enrollment) -> dict:
    return {
        "id": enr.id,
        "student_id": enr.student_id,
        "event_id": enr.event_id,
        "status": enr.status,
    }

@router.post("/events/{event_id}/enroll", status_code=201, summary="Enroll student into event")
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

    # 1) Escopo por tenant: garanta que EVENTO e ALUNO pertencem ao tenant
    ev = db.execute(
        select(Event).where(Event.id == event_id, Event.client_id == tenant.id)
    ).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="event_not_found")

    st = db.execute(
        select(Student).where(Student.id == student_id, Student.client_id == tenant.id)
    ).scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="student_not_found")

    # 2) Procure matrícula existente (qualquer status)
    existing = db.execute(
        select(Enrollment).where(
            Enrollment.event_id == event_id,
            Enrollment.student_id == student_id,
        )
    ).scalar_one_or_none()

    if existing:
        # 2a) Idempotência real: devolva a existente sem alterar
        if idem:
            return _enr_out(existing)

        # 2b) Se estava cancelada e permitimos reativar -> volta pra pending
        if existing.status in STATUS_CANCELED and reactivate:
            existing.status = STATUS_PENDING
            db.add(existing); db.commit(); db.refresh(existing)
            return _enr_out(existing)

        # 2c) Já existe ativa → 409
        if existing.status not in STATUS_CANCELED:
            raise HTTPException(status_code=409, detail="already_enrolled")

        # 2d) Estava cancelada e reativação não permitida → 409
        raise HTTPException(status_code=409, detail="enrollment_canceled")

    # 3) Criar nova matrícula como 'pending' por padrão
    enr = Enrollment(student_id=student_id, event_id=event_id, status=STATUS_PENDING)
    db.add(enr); db.commit(); db.refresh(enr)
    return _enr_out(enr)


# (opcional) cancelar matrícula explicitamente
@router.post("/enrollments/{enr_id}/cancel", summary="Cancel enrollment")
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
    enr.status = "canceled"  # padronize num dos dois
    db.add(enr); db.commit(); db.refresh(enr)
    return _enr_out(enr)


# LISTAGEM com expand (student,event) — você pode chamar por event_id
@router.get("/enrollments", summary="List Enrollments (supports expand=student,event)")
def list_enrollments(
    event_id: int | None = Query(None, alias="event_id"),
    status: str | None = Query(None, alias="status"),
    expand: str = Query("", description="Comma-separated: student,event"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    expand_set = {p.strip() for p in expand.split(",") if p.strip()}
    stmt = select(Enrollment).join(Event, Enrollment.event_id == Event.id).where(Event.client_id == tenant.id)

    if event_id is not None:
        stmt = stmt.where(Enrollment.event_id == event_id)
    if status:
        stmt = stmt.where(Enrollment.status == status)

    # eager loads
    opts = []
    if "student" in expand_set:
        opts.append(joinedload(Enrollment.student))
    if "event" in expand_set:
        opts.append(joinedload(Enrollment.event))
    if opts:
        stmt = stmt.options(*opts)

    rows = db.execute(stmt).scalars().all()

    out = []
    for enr in rows:
        data = _enr_out(enr)
        if "student" in expand_set and getattr(enr, "student", None):
            st = enr.student
            data["student"] = {
                "id": st.id, "name": getattr(st, "name", None),
                "email": getattr(st, "email", None),
                "cpf": getattr(st, "cpf", None),
                "ra": getattr(st, "ra", None),
                "phone": getattr(st, "phone", None),
            }
        if "event" in expand_set and getattr(enr, "event", None):
            ev = enr.event
            data["event"] = {
                "id": ev.id, "title": getattr(ev, "title", None),
                "description": getattr(ev, "description", None),
                "venue": getattr(ev, "venue", None),
                "start_at": getattr(ev, "start_at", None),
                "end_at": getattr(ev, "end_at", None),
                "status": getattr(ev, "status", None),
                "capacity_total": getattr(ev, "capacity_total", None),
                "workload_hours": getattr(ev, "workload_hours", None),
                "min_presence_pct": getattr(ev, "min_presence_pct", None),
            }
        out.append(data)
    return out
