from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from secrets import token_hex
from typing import List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.crud.enrollment import enrollment_crud
from app.schemas.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.event import Event
from app.models.enrollment import Enrollment as Enr
from sqlalchemy import select
from app.models.enrollment import Enrollment as Enr, EnrollmentStatus
from starlette.status import HTTP_409_CONFLICT
from fastapi import Query

router = APIRouter()
# app/api/v1/enrollments.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.event import Event

router = APIRouter()

@router.post("/events/{event_id}/enroll",status_code=201,
             dependencies=[Depends(require_roles("admin","organizer"))])
def enroll(event_id: int, student_id: int, idempotent: bool = Query(False),
           db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    s = db.get(Student, student_id); e = db.get(Event, event_id)
    if not s or s.client_id != tenant.id or not e or e.client_id != tenant.id:
        raise HTTPException(404)
    dup = db.execute(select(Enr).where(Enr.student_id==s.id, Enr.event_id==e.id)).scalar_one_or_none()
    if dup:
        if idempotent:
            return Enrollment(id=dup.id, student_id=dup.student_id, event_id=dup.event_id, status=dup.status)
        raise HTTPException(status_code=HTTP_409_CONFLICT,
                            detail={"code":"ENROLLMENT_EXISTS","message":"Aluno já inscrito neste evento.","details":{"enrollment_id":dup.id}})
    enr = enrollment_crud.enroll(db, student_id=s.id, event_id=e.id, qr_seed=token_hex(16))
    return Enrollment(id=enr.id, student_id=s.id, event_id=e.id, status=enr.status)

@router.get("", summary="List Enrollments (supports expand=student,event)")
def list_enrollments(
    tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
    event_id: int | None = Query(None, alias="event_id"),
    status: str | None = Query(None, alias="status"),  # ex.: pending/confirmed/canceled
    expand: str = Query("", description="Comma-separated: student,event"),
):
    expand_set = {p.strip() for p in expand.split(",") if p.strip()}
    # Preferimos filtrar por evento (que tem client_id). Se não houver, filtramos por Student->client_id.
    stmt = select(Enrollment)

    # Eager load se pedido
    load_opts = []
    if "student" in expand_set:
        load_opts.append(joinedload(Enrollment.student))
    if "event" in expand_set:
        load_opts.append(joinedload(Enrollment.event))
    if load_opts:
        stmt = stmt.options(*load_opts)

    if event_id is not None:
        stmt = stmt.join(Event, Enrollment.event_id == Event.id).where(Event.client_id == tenant.id, Enrollment.event_id == event_id)
    else:
        # Sem event_id: garanta escopo por tenant via Student (ou Event)
        stmt = stmt.join(Student, Enrollment.student_id == Student.id).where(Student.client_id == tenant.id)

    if status:
        stmt = stmt.where(Enrollment.status == status)

    rows = db.execute(stmt).scalars().all()

    out = []
    for enr in rows:
        item = {
            "id": enr.id,
            "student_id": enr.student_id,
            "event_id": enr.event_id,
            "status": enr.status,
        }
        if "student" in expand_set:
            st = getattr(enr, "student", None)
            if st:
                item["student"] = {
                    "id": st.id,
                    "name": getattr(st, "name", None),
                    "email": getattr(st, "email", None),
                    "cpf": getattr(st, "cpf", None),
                    "ra": getattr(st, "ra", None),
                    "phone": getattr(st, "phone", None),
                }
        if "event" in expand_set:
            ev = getattr(enr, "event", None)
            if ev:
                item["event"] = {
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
        out.append(item)
    return out

@router.put("/enrollments/{enr_id}/cancel")
def cancel_enr(enr_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    enr = db.get(Enr, enr_id)
    if not enr or enr.event.client_id != tenant.id: raise HTTPException(404)
    enr.status = EnrollmentStatus.cancelled
    db.add(enr); db.commit()
    return {"ok": True}
