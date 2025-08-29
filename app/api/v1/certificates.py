from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.crud.certificate import issue_if_eligible
from app.models.certificate import Certificate, CertificateStatus
from app.models.enrollment import Enrollment
from app.schemas.certificate import Certificate as CertSchema

router = APIRouter()

@router.post("/issue", dependencies=[Depends(require_roles("admin","organizer"))])
def issue_batch(event_id: int = Query(...), db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    enrs = db.execute(select(Enrollment).join(Enrollment.event).where(Enrollment.event_id==event_id, Enrollment.event.has(client_id=tenant.id))).scalars().all()
    issued = []
    for e in enrs:
        c = issue_if_eligible(db, enrollment_id=e.id)
        if c: issued.append(c.id)
    return {"issued_ids": issued}

@router.get("/", response_model=List[CertSchema])
def list_certs(event_id: int | None = None, student_id: int | None = None, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    stmt = select(Certificate).join(Enrollment).join(Enrollment.event).where(Enrollment.event.has(client_id=tenant.id))
    if event_id: stmt = stmt.where(Enrollment.event_id==event_id)
    if student_id: stmt = stmt.where(Enrollment.student_id==student_id)
    rows = db.execute(stmt).scalars().all()
    return [CertSchema(id=c.id, enrollment_id=c.enrollment_id, issued_at=c.issued_at, pdf_url=c.pdf_url, verify_code=c.verify_code, status=c.status) for c in rows]

# público
@router.get("/verify/{code}", tags=["public"])
def verify_public(code: str, db: Session = Depends(get_db)):
    c = db.execute(select(Certificate).where(Certificate.verify_code==code)).scalar_one_or_none()
    if not c: raise HTTPException(404, "NOT_FOUND")
    e = db.get(Enrollment, c.enrollment_id)
    return {"status": c.status, "enrollment_id": e.id, "event_id": e.event_id, "student_id": e.student_id, "issued_at": c.issued_at, "pdf_url": c.pdf_url}
