# app/api/v1/gate.py (ou o arquivo onde está seu endpoint de scan)
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
import datetime as dt
from zoneinfo import ZoneInfo

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.config import settings
from app.models.enrollment import Enrollment as EnrollmentModel
from app.models.day_event import DayEvent as DayModel
from app.models.attendance import Attendance as AttendanceModel

router = APIRouter(prefix="/gate", tags=["gate"])

# Config padrão (pode mover para settings.py)
TZ = ZoneInfo(getattr(settings, "TIMEZONE", "America/Sao_Paulo"))
EARLY_MIN = int(getattr(settings, "GATE_EARLY_MIN", 15))  # tolerância antes do start
LATE_MIN  = int(getattr(settings, "GATE_LATE_MIN",  30))  # tolerância depois do end

class ScanIn(BaseModel):
    enrollment_id: int
    day_event_id: int
    action: str                    # "checkin" ou "checkout"
    device_id: str | None = None
    ts: str | None = None          # opcional: ISO 8601 para testes (ex: "2025-10-24T08:59:00-03:00")

def _parse_ts(ts: str | None) -> dt.datetime:
    """
    Converte ts (ISO 8601) em datetime timezone-aware (UTC).
    Se não enviado, usa agora em UTC.
    """
    if not ts:
        return dt.datetime.now(dt.timezone.utc)
    try:
        # fromisoformat aceita “YYYY-MM-DDTHH:MM:SS[+/-HH:MM]”
        d = dt.datetime.fromisoformat(ts)
        if d.tzinfo is None:
            # Se veio sem tz, assume timezone do app e converte pra UTC
            d = d.replace(tzinfo=TZ).astimezone(dt.timezone.utc)
        else:
            d = d.astimezone(dt.timezone.utc)
        return d
    except Exception:
        raise HTTPException(status_code=400, detail="INVALID_TS_FORMAT")

def _window_utc(day: DayModel) -> tuple[dt.datetime, dt.datetime]:
    """
    Monta a janela [start, end] em UTC a partir do dia (local do app/tenant) com tolerâncias.
    Considera overnight (end < start -> vira dia seguinte).
    """
    start_local = dt.datetime.combine(day.date, day.start_time, tzinfo=TZ)
    end_local   = dt.datetime.combine(day.date, day.end_time,   tzinfo=TZ)
    if end_local <= start_local:
        # caso raro: evento atravessa a meia-noite
        end_local = end_local + dt.timedelta(days=1)

    # Tolerâncias
    start_local = start_local - dt.timedelta(minutes=EARLY_MIN)
    end_local   = end_local   + dt.timedelta(minutes=LATE_MIN)

    return (start_local.astimezone(dt.timezone.utc),
            end_local.astimezone(dt.timezone.utc))

@router.post("/scan")
def scan(
    body: ScanIn = Body(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # 1) valida enrollment e day_event do mesmo evento
    enr = db.get(EnrollmentModel, body.enrollment_id)
    if not enr:
        raise HTTPException(status_code=404, detail="ENROLLMENT_NOT_FOUND")

    day = db.get(DayModel, body.day_event_id)
    if not day:
        raise HTTPException(status_code=404, detail="DAY_NOT_FOUND")

    # (opcional) confira se enrollment pertence ao mesmo event_id do day
    if getattr(enr, "event_id", None) != getattr(day, "event_id", None):
        raise HTTPException(status_code=400, detail="MISMATCH_EVENT")

    # 2) horário atual (UTC), janela em UTC com tolerância
    now_utc = _parse_ts(body.ts)
    start_utc, end_utc = _window_utc(day)

    if not (start_utc <= now_utc <= end_utc):
        # devolve info de debug útil
        raise HTTPException(status_code=400, detail="OUT_OF_WINDOW")

    # 3) persiste attendance (uma linha por enrollment+day)
    att = db.execute(
        select(AttendanceModel).where(
            AttendanceModel.enrollment_id == enr.id,
            AttendanceModel.day_event_id == day.id,
        )
    ).scalar_one_or_none()

    if not att:
        att = AttendanceModel(enrollment_id=enr.id, day_event_id=day.id)

    if body.action == "checkin":
        att.checkin_at = now_utc
    elif body.action == "checkout":
        att.checkout_at = now_utc
    else:
        raise HTTPException(status_code=400, detail="INVALID_ACTION")

    if hasattr(att, "origin") and body.device_id:
        att.origin = body.device_id

    db.add(att)
    db.commit()
    db.refresh(att)

    return {
        "ok": True,
        "enrollment_id": enr.id,
        "day_event_id": day.id,
        "action": body.action,
        "ts_utc": now_utc.isoformat(),
        "window_utc": {
            "start": start_utc.isoformat(),
            "end": end_utc.isoformat(),
        },
    }
