# app/api/v1/certificates.py
from __future__ import annotations

import io
import hmac
import hashlib
import datetime as dt
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.event import Event as EventModel
from app.models.day_event import DayEvent as DayModel
from app.models.student import Student as StudentModel
from app.models.enrollment import Enrollment as EnrollmentModel
from app.models.attendance import Attendance as AttendanceModel
from app.core.config import settings  # SECRET_KEY

from PIL import Image, ImageDraw, ImageFont
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader

router = APIRouter(prefix="/certificates", tags=["certificates"])

# --------------------------------------------------------------------
# Helpers de segurança / verificação
# --------------------------------------------------------------------

def _cert_payload(tenant_slug: str, event_id: int, student_id: int, issued_at: str):
    return f"{tenant_slug}|{event_id}|{student_id}|{issued_at}"

def _sign(payload: str):
    key = settings.SECRET_KEY.encode("utf-8")
    sig = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig

def _make_code(tenant_slug: str, event_id: int, student_id: int):
    issued_at = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    payload = _cert_payload(tenant_slug, event_id, student_id, issued_at)
    sig = _sign(payload)
    return f"{issued_at}.{sig}"

def _verify_code(tenant_slug: str, event_id: int, student_id: int, code: str):
    try:
        issued_at, sig = code.split(".", 1)
    except ValueError:
        return False
    payload = _cert_payload(tenant_slug, event_id, student_id, issued_at)
    return hmac.compare_digest(_sign(payload), sig)

# --------------------------------------------------------------------
# Regra de elegibilidade (Enrollment + Attendance por DayEvent)
# --------------------------------------------------------------------

def _student_is_eligible(
    db: Session, tenant, event_id: int, student_id: int
):
    """
    Retorna (eligible, lista_de_dias),
    onde cada item é (inicio_janela, fim_janela, tem_presenca).

    Regra: o aluno precisa ter Attendance (check-in feito) para CADA DayEvent do evento.
    """
    # evento do tenant
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # matrícula do aluno no evento
    enr = db.execute(
        select(EnrollmentModel).where(
            EnrollmentModel.student_id == student_id,
            EnrollmentModel.event_id == e.id,
        )
    ).scalar_one_or_none()
    if not enr:
        # não matriculado => inelegível
        return False, []

    # dias do evento
    days: List[DayModel] = db.execute(
        select(DayModel).where(DayModel.event_id == e.id)
    ).scalars().all()
    if not days:
        return False, []

    results: List[Tuple[dt.datetime, dt.datetime, bool]] = []
    for d in days:
        start_dt = dt.datetime.combine(d.date, d.start_time)
        end_dt = dt.datetime.combine(d.date, d.end_time)

        # presença vinculada à matrícula + dia
        att = db.execute(
            select(AttendanceModel).where(
                AttendanceModel.enrollment_id == enr.id,
                AttendanceModel.day_event_id == d.id,
            )
        ).scalar_one_or_none()

        # Exigir checkin_at (se quiser exigir checkout_at também, inclua no boolean)
        has_presence = bool(att and att.checkin_at)
        results.append((start_dt, end_dt, has_presence))

    eligible = all(ok for *_ , ok in results)
    return eligible, results

# --------------------------------------------------------------------
# Composição de imagem (Pillow) + QR e conversão para PDF
# --------------------------------------------------------------------

def _compose_certificate_image(
    bg_path: str,
    student_name: str,
    event_title: str,
    period_text: str,
    cert_code: str,
    verify_url: str,
):
    # Carrega template
    bg = Image.open(bg_path).convert("RGB")
    W, H = bg.size
    draw = ImageDraw.Draw(bg)

    # Fontes (se não existirem, cai no default)
    try:
        font_title = ImageFont.truetype("app/assets/Inter-Bold.ttf", size=int(H * 0.055))
        font_name = ImageFont.truetype("app/assets/Inter-SemiBold.ttf", size=int(H * 0.07))
        font_text = ImageFont.truetype("app/assets/Inter-Regular.ttf", size=int(H * 0.035))
        font_small = ImageFont.truetype("app/assets/Inter-Regular.ttf", size=int(H * 0.03))
    except Exception:
        font_title = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Título
    title = "CERTIFICADO DE PARTICIPAÇÃO"
    tw, th = draw.textbbox((0, 0), title, font=font_title)[2:]
    draw.text(((W - tw) // 2, int(H * 0.12)), title, fill=(0, 0, 0), font=font_title)

    # Nome do aluno
    nw, nh = draw.textbbox((0, 0), student_name, font=font_name)[2:]
    draw.text(((W - nw) // 2, int(H * 0.28)), student_name, fill=(0, 0, 0), font=font_name)

    # Texto do evento
    body = f'Conferimos que participou do evento "{event_title}" no período {period_text}.'
    draw.text((int(W * 0.12), int(H * 0.40)), body, fill=(0, 0, 0), font=font_text)

    # QR code
    qr = qrcode.make(verify_url)
    qr = qr.resize((int(H * 0.22), int(H * 0.22)))
    bg.paste(qr, (int(W * 0.1), int(H * 0.62)))

    # Código e URL
    draw.text((int(W * 0.1), int(H * 0.86)), f"Código: {cert_code}", fill=(0, 0, 0), font=font_small)
    draw.text((int(W * 0.1), int(H * 0.90)), f"Verifique: {verify_url}", fill=(0, 0, 0), font=font_small)

    return bg

def _image_to_pdf_bytes(img: Image.Image):
    # Converte imagem para PDF (A4 paisagem) via ReportLab
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    w, h = landscape(A4)

    img_w, img_h = img.size
    ratio = min(w / img_w, h / img_h)
    target_w, target_h = img_w * ratio, img_h * ratio
    x = (w - target_w) / 2
    y = (h - target_h) / 2

    c.drawImage(ImageReader(img), x, y, width=target_w, height=target_h)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.get("/{event_id}/students/{student_id}/generate.pdf")
def generate_certificate_pdf(
    event_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # aluno do tenant
    s = db.get(StudentModel, student_id)
    if not s or getattr(s, "client_id", tenant.id) != tenant.id:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")

    eligible, _ = _student_is_eligible(db, tenant, event_id, student_id)
    if not eligible:
        raise HTTPException(status_code=422, detail="student_not_eligible")

    e = db.get(EventModel, event_id)

    # período (menor/maior date dos DayEvent)
    days = db.execute(select(DayModel).where(DayModel.event_id == e.id)).scalars().all()
    min_date = min(d.date for d in days)
    max_date = max(d.date for d in days)
    period_text = f"{min_date.strftime('%d/%m/%Y')} a {max_date.strftime('%d/%m/%Y')}"

    # código + URL de verificação
    code = _make_code(tenant.slug, e.id, s.id)
    # Ajuste o domínio abaixo conforme sua infra:
    verify_url = f"https://{tenant.slug}.seu-dominio.com/certificates/verify?event={e.id}&student={s.id}&code={code}"

    # compõe arte e gera PDF
    bg_path = "app/assets/certificate_bg.png"  # coloque um template no repo
    img = _compose_certificate_image(
        bg_path=bg_path,
        student_name=getattr(s, "name", getattr(s, "full_name", "Aluno(a)")),
        event_title=e.title,
        period_text=period_text,
        cert_code=code,
        verify_url=verify_url,
    )
    pdf = _image_to_pdf_bytes(img)

    filename = f"certificado_{e.id}_{s.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

@router.get("/verify")
def verify_certificate(
    event: int = Query(...),
    student: int = Query(...),
    code: str = Query(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    ok = _verify_code(tenant.slug, event, student, code)
    if not ok:
        raise HTTPException(status_code=404, detail="invalid_code")
    return {"ok": True, "event": event, "student": student, "tenant": tenant.slug}
