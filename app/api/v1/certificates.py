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
import datetime as dt
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from api.deps import get_db, get_tenant, get_current_user_scoped
from models.event import Event
from models.enrollment import Enrollment
from models.attendance import Attendance
from models.certificate import Certificate
from models.client import Client  # se existir
import secrets, datetime as dt


router = APIRouter()

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
# backend/api/v1/certificates.py

router = APIRouter()

def _gen_code(n=8) -> str:
    # código curto para verificação pública
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))

@router.post("/issue-batch")
def issue_batch(
    tenant = Depends(get_tenant),
    event_id: int = Query(...),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    ev = db.get(Event, event_id)
    if not ev or ev.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Event not found")

    # total de dias do evento
    total_days = db.scalar(select(func.count()).select_from(Attendance.day_event_id.distinct()).where(Attendance.event_id == event_id))
    if not total_days:
        # fallback: se você tiver tabela DayEvent, substitua por count nela
        total_days = 1

    min_pct = ev.min_presence_pct or getattr(tenant, "default_min_presence_pct", 75)

    # pega matrículas do evento
    enrs = db.execute(
        select(Enrollment).where(Enrollment.event_id == event_id)
    ).scalars().all()

    issued = 0
    for enr in enrs:
        # presença do aluno (dias que tem checkin e checkout)
        present_days = db.scalar(
            select(func.count()).select_from(Attendance).where(
                Attendance.enrollment_id == enr.id,
                Attendance.event_id == event_id,
                Attendance.checkin_at.is_not(None),
                Attendance.checkout_at.is_not(None),
            )
        ) or 0

        pct = int((present_days / total_days) * 100) if total_days else 0
        if pct < min_pct:
            continue

        # evita duplicidade por matrícula
        already = db.execute(
            select(Certificate).where(Certificate.enrollment_id == enr.id)
        ).scalar_one_or_none()
        if already:
            continue

        cert = Certificate(
            enrollment_id=enr.id,
            issued_at=dt.datetime.utcnow(),
            pdf_url=None,  # gerar depois (wkhtmltopdf etc.)
            verify_code=_gen_code(),
            status="issued",
        )
        db.add(cert)
        issued += 1

    db.commit()
    return {"issued": issued}
