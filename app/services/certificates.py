# app/services/certificates.py
from __future__ import annotations

import os, io, uuid, base64, datetime as dt
from typing import Dict, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from jinja2 import Environment, BaseLoader, select_autoescape

# PDF (usa xhtml2pdf; fallback simples com reportlab se não estiver instalado)
try:
    from xhtml2pdf import pisa  # type: ignore
    _HAS_PISA = True
except Exception:
    _HAS_PISA = False
try:
    from reportlab.pdfgen import canvas  # type: ignore
    from reportlab.lib.pagesizes import A4  # type: ignore
    _HAS_REPORTLAB = True
except Exception:
    _HAS_REPORTLAB = False

import qrcode  # type: ignore

from app.core.config import settings
from app.models.client import Client
from app.models.event import Event
from app.models.student import Student
from app.models.enrollment import Enrollment
from app.models.day_event import DayEvent
from app.models.attendance import Attendance
from app.models.certificate import Certificate

# -------------------------- Utils --------------------------

def _data_dir() -> str:
    # vamos publicar em: /static/certificates/<tenant>/file.pdf
    base = os.path.join(settings.DATA_DIR, "public", "certificates")
    os.makedirs(base, exist_ok=True)
    return base

def _tenant_dir(tenant_slug: str) -> str:
    path = os.path.join(_data_dir(), tenant_slug)
    os.makedirs(path, exist_ok=True)
    return path

def _now_tz() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _mask_cpf(cpf: str | None) -> str:
    if not cpf:
        return ""
    digits = "".join([c for c in cpf if c.isdigit()])
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return cpf

def _qr_data_uri(text: str) -> str:
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _render_html(template: str, ctx: Dict) -> str:
    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(["html", "xml"]),
        enable_async=False,
    )
    tpl = env.from_string(template)
    return tpl.render(**ctx)

def _html_to_pdf_bytes(html: str) -> bytes:
    if _HAS_PISA:
        out = io.BytesIO()
        pisa.CreatePDF(io.StringIO(html), dest=out)
        return out.getvalue()
    if _HAS_REPORTLAB:
        # fallback bem simples (texto puro)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        textobj = c.beginText(40, A4[1] - 40)
        for line in html.splitlines():
            textobj.textLine(line[:150])
        c.drawText(textobj)
        c.showPage()
        c.save()
        return buf.getvalue()
    raise RuntimeError("Nenhum renderizador de PDF disponível (xhtml2pdf/reportlab)")

def _save_pdf(tenant_slug: str, verify_code: str, pdf_bytes: bytes) -> Tuple[str, str]:
    # path físico + URL pública (via StaticFiles /static)
    dir_tenant = _tenant_dir(tenant_slug)
    filename = f"{verify_code}.pdf"
    path = os.path.join(dir_tenant, filename)
    with open(path, "wb") as f:
        f.write(pdf_bytes)
    # URL que será servida pelo StaticFiles (ver main.py)
    url = f"/static/certificates/{tenant_slug}/{filename}"
    return path, url

def _new_code(db: Session) -> str:
    # 10 chars Base32 sem padding — curto e único
    while True:
        raw = uuid.uuid4().bytes
        code = base64.b32encode(raw).decode("ascii").rstrip("=").lower()[:10]
        exists = db.execute(select(Certificate).where(Certificate.verify_code == code)).scalar_one_or_none()
        if not exists:
            return code

# -------------------- Cálculo de presença --------------------

class PresenceStats(Dict):
    pass

def compute_presence_stats(
    db: Session, enrollment: Enrollment, mode: str = "day"
) -> PresenceStats:
    """
    mode= 'day'  -> presença por dia (conta presença se houve checkin)
          'hours'-> soma minutos (checkout - checkin) capado ao horário do dia
    """
    event = db.get(Event, enrollment.event_id)
    if not event:
        raise ValueError("event not found")

    days = db.execute(select(DayEvent).where(DayEvent.event_id == event.id)).scalars().all()
    total_days = len(days)
    if total_days == 0:
        return PresenceStats(total_days=0, present_days=0, pct=0.0, minutes=0, minutes_total=0)

    if mode == "day":
        present_days = db.execute(
            select(func.count(Attendance.id))
            .where(
                Attendance.enrollment_id == enrollment.id,
                Attendance.day_event_id.in_([d.id for d in days]),
                Attendance.checkin_at.is_not(None),
            )
        ).scalar() or 0
        pct = (present_days / total_days) * 100.0
        return PresenceStats(
            total_days=total_days, present_days=present_days, pct=pct, minutes=0, minutes_total=0
        )

    # hours
    minutes_total = 0
    minutes = 0
    for d in days:
        start = dt.datetime.combine(d.date, d.start_time, tzinfo=dt.timezone.utc)
        end = dt.datetime.combine(d.date, d.end_time, tzinfo=dt.timezone.utc)
        dur = max(0, int((end - start).total_seconds() // 60))
        minutes_total += dur

        att = db.execute(
            select(Attendance)
            .where(Attendance.enrollment_id == enrollment.id, Attendance.day_event_id == d.id)
        ).scalar_one_or_none()
        if not att or not att.checkin_at:
            continue
        chk_in = att.checkin_at
        chk_out = att.checkout_at or end
        # cap nos limites do dia
        chk_in = max(chk_in, start)
        chk_out = min(chk_out, end)
        gain = max(0, int((chk_out - chk_in).total_seconds() // 60))
        minutes += min(gain, dur)

    pct = (minutes / minutes_total) * 100.0 if minutes_total else 0.0
    return PresenceStats(
        total_days=total_days, present_days=None, pct=pct, minutes=minutes, minutes_total=minutes_total
    )

def min_presence_pct(db: Session, event: Event) -> int:
    if event.min_presence_pct is not None:
        return int(event.min_presence_pct)
    # fallback do cliente
    cli = db.get(Client, event.client_id)
    if cli and cli.default_min_presence_pct is not None:
        return int(cli.default_min_presence_pct)
    return 75  # padrão

def is_eligible(db: Session, enrollment: Enrollment, mode: str = "day") -> Tuple[bool, PresenceStats, int]:
    stats = compute_presence_stats(db, enrollment, mode=mode)
    ev = db.get(Event, enrollment.event_id)
    req = min_presence_pct(db, ev)
    return (stats["pct"] >= req), stats, req

# -------------------- Emissão/Reemissão --------------------

def build_certificate_html(
    *,
    client: Client,
    event: Event,
    student: Student,
    verify_url: str,
    verify_code: str,
    stats: PresenceStats,
    required_pct: int,
) -> str:
    # template do cliente (Jinja2). Se não tiver, cria um básico.
    tpl = client.certificate_template_html or """
<!doctype html>
<html>
  <body style="font-family: Arial, Helvetica, sans-serif; padding: 36px;">
    <div style="text-align:center;">
      {% if client.logo_url %}<img src="{{ client.logo_url }}" style="max-height:80px"><br>{% endif %}
      <h1>Certificado</h1>
      <p>Certificamos que <b>{{ aluno.nome }}</b> (CPF {{ aluno.cpf_mask }})
         participou do evento <b>{{ evento.titulo }}</b>
         realizado de {{ evento.inicio }} a {{ evento.fim }},
         cumprindo {{ carga_horas }} horas e atingindo {{ stats.pct|round(2) }}% de presença
         (mínimo exigido {{ required_pct }}%).</p>
      <p>Emitido em {{ emissao }} — Código de verificação: <b>{{ codigo }}</b></p>
      <img src="{{ qr_data_uri }}" style="height:120px">
      <div style="font-size: 12px; margin-top:8px">
        Verifique em: {{ verify_url }}
      </div>
    </div>
  </body>
</html>
    """.strip()

    qr = _qr_data_uri(verify_url)

    carga = event.workload_hours or 0
    inicio = event.start_at.date().isoformat() if event.start_at else ""
    fim = event.end_at.date().isoformat() if event.end_at else ""

    ctx = dict(
        client=dict(nome=client.name, logo_url=client.logo_url),
        aluno=dict(nome=student.name, cpf_mask=_mask_cpf(student.cpf)),
        evento=dict(titulo=event.title, inicio=inicio, fim=fim),
        emissao=dt.datetime.now().date().isoformat(),
        codigo=verify_code,
        verify_url=verify_url,
        qr_data_uri=qr,
        stats=stats,
        required_pct=required_pct,
        carga_horas=carga,
    )
    return _render_html(tpl, ctx)

def issue_certificate_for_enrollment(
    *,
    db: Session,
    tenant: Client,
    enrollment: Enrollment,
    verify_url_base: str,
    mode: str = "day",
    reissue: bool = False,
) -> Optional[Certificate]:
    ok, stats, req = is_eligible(db, enrollment, mode=mode)
    if not ok:
        return None

    # revoga anterior, se reissue=True
    if reissue:
        db.execute(
            sa.update(Certificate)
            .where(Certificate.enrollment_id == enrollment.id, Certificate.status == "issued")
            .values(status="revoked")
        )

    code = _new_code(db)
    verify_url = f"{verify_url_base.rstrip('/')}/{code}"

    # carrega dados
    event = db.get(Event, enrollment.event_id)
    student = db.get(Student, enrollment.student_id)
    html = build_certificate_html(
        client=tenant, event=event, student=student,
        verify_url=verify_url, verify_code=code,
        stats=stats, required_pct=req,
    )

    pdf_bytes = _html_to_pdf_bytes(html)
    _, pdf_url = _save_pdf(tenant.slug, code, pdf_bytes)

    cert = Certificate(
        enrollment_id=enrollment.id,
        issued_at=_now_tz(),
        pdf_url=pdf_url,
        verify_code=code,
        status="issued",
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert
