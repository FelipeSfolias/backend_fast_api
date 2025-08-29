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

@router.post("/events/{event_id}/enroll", response_model=Enrollment, status_code=201,
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

@router.get("/enrollments", response_model=List[Enrollment])
def list_enr(event_id: int | None = Query(None), status: EnrollmentStatus | None = None, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    stmt = select(Enr).join(Event).where(Event.client_id==tenant.id)
    if event_id: stmt = stmt.where(Enr.event_id==event_id)
    if status: stmt = stmt.where(Enr.status==status)
    rows = db.execute(stmt).scalars().all()
    return [Enrollment(id=r.id, student_id=r.student_id, event_id=r.event_id, status=r.status) for r in rows]

@router.put("/enrollments/{enr_id}/cancel")
def cancel_enr(enr_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    enr = db.get(Enr, enr_id)
    if not enr or enr.event.client_id != tenant.id: raise HTTPException(404)
    enr.status = EnrollmentStatus.cancelled
    db.add(enr); db.commit()
    return {"ok": True}
