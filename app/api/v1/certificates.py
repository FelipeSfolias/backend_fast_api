# app/api/v1/certificates.py
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.core.config import settings

from app.models.client import Client
from app.models.event import Event
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.certificate import Certificate

from app.schemas.certificate import Certificate as CertificateOut  # seu schema
from app.services.certificates import (
    issue_certificate_for_enrollment,
    compute_presence_stats,
    is_eligible,
)

router = APIRouter()
verify_router = APIRouter()  # público

def _to_out(c: Certificate) -> CertificateOut:
    return CertificateOut(
        id=c.id,
        enrollment_id=c.enrollment_id,
        issued_at=c.issued_at,
        pdf_url=c.pdf_url,
        verify_code=c.verify_code,
        status=c.status,
    )

def _verify_base(request: Request) -> str:
    # prioridade: env PUBLIC_BASE_URL; senão, monta com host da requisição
    base = getattr(settings, "PUBLIC_BASE_URL", "") or str(request.base_url).rstrip("/")
    return f"{base}/verify"

# ----------------------- elegibilidade -----------------------

@router.get("/eligibility/{enrollment_id}")
def check_eligibility(
    enrollment_id: int = Path(..., ge=1),
    mode: str = Query("day", pattern="^(day|hours)$"),
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    enr = db.get(Enrollment, enrollment_id)
    if not enr:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    ok, stats, req = is_eligible(db, enr, mode=mode)
    return {"eligible": ok, "required_pct": req, "stats": stats}

# -------------------------- emissão --------------------------

@router.post("/issue/{enrollment_id}", response_model=CertificateOut,
             dependencies=[Depends(require_roles("admin", "organizer"))])
def issue_one(
    request: Request,
    enrollment_id: int = Path(..., ge=1),
    mode: str = Query("day", pattern="^(day|hours)$"),
    reissue: bool = Query(False, description="Revoga anterior e reemite"),
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    enr = db.get(Enrollment, enrollment_id)
    if not enr:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    cert = issue_certificate_for_enrollment(
        db=db, tenant=tenant, enrollment=enr,
        verify_url_base=_verify_base(request),
        mode=mode, reissue=reissue,
    )
    if not cert:
        raise HTTPException(status_code=412, detail="Aluno não elegível pela regra de presença")
    return _to_out(cert)

@router.post("/batch/{event_id}", response_model=List[CertificateOut],
             dependencies=[Depends(require_roles("admin", "organizer"))])
def issue_batch(
    request: Request,
    event_id: int = Path(..., ge=1),
    mode: str = Query("day", pattern="^(day|hours)$"),
    reissue_existing: bool = Query(False, description="Se true, revoga os ativos e reemite"),
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    ev = db.get(Event, event_id)
    if not ev or ev.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Event not found")

    enrs = db.execute(
        select(Enrollment).where(Enrollment.event_id == event_id)
    ).scalars().all()

    out: List[CertificateOut] = []
    for enr in enrs:
        cert = issue_certificate_for_enrollment(
            db=db, tenant=tenant, enrollment=enr,
            verify_url_base=_verify_base(request),
            mode=mode, reissue=reissue_existing,
        )
        if cert:
            out.append(_to_out(cert))
    return out

# -------------------------- leitura --------------------------

@router.get("/{certificate_id}", response_model=CertificateOut)
def get_certificate(
    certificate_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    c = db.get(Certificate, certificate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    # valida escopo por tenant via enrollment->event
    enr = db.get(Enrollment, c.enrollment_id)
    ev = db.get(Event, enr.event_id) if enr else None
    if not ev or ev.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return _to_out(c)

# -------------------- verificação pública --------------------

@verify_router.get("/{code}")
def verify_public(
    code: str,
    db: Session = Depends(get_db),
):
    c = db.execute(select(Certificate).where(Certificate.verify_code == code)).scalar_one_or_none()
    if not c or c.status != "issued":
        raise HTTPException(status_code=404, detail="Certificado não encontrado ou revogado")

    enr = db.get(Enrollment, c.enrollment_id)
    ev = db.get(Event, enr.event_id) if enr else None
    st = db.get(Student, enr.student_id) if enr else None
    cli = db.get(Client, ev.client_id) if ev else None

    # resposta “LGPD-friendly”
    return {
        "status": c.status,
        "verify_code": c.verify_code,
        "issued_at": c.issued_at,
        "client": {"name": cli.name, "slug": cli.slug} if cli else None,
        "event": {"title": ev.title, "id": ev.id} if ev else None,
        "student": {"name": st.name} if st else None,
        "pdf_url": c.pdf_url,
    }
