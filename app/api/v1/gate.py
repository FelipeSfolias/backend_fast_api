# app/api/v1/gate.py
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

# IMPORTANTE: sem prefix aqui!
router = APIRouter(tags=["gate"])

TZ = ZoneInfo(getattr(settings, "TIMEZONE", "America/Sao_Paulo"))
EARLY_MIN = int(getattr(settings, "GATE_EARLY_MIN", 15))
LATE_MIN  = int(getattr(settings, "GATE_LATE_MIN",  30))


class ScanIn(BaseModel):
    enrollment_id: int
    day_event_id: int
    action: str                    # "checkin" | "checkout"
    device_id: str | None = None
    ts: str | None = None          # ISO 8601 opcional p/ testes (ex: "2025-11-02T08:59:00-03:00")


def _parse_ts(ts: str | None) -> dt.datetime:
    if not ts:
        return dt.datetime.now(dt.timezone.utc)
    try:
        d = dt.datetime.fromisoformat(ts)
        if d.tzinfo is None:
            d = d.replace(tzinfo=TZ).astimezone(dt.timezone.utc)
        else:
            d = d.astimezone(dt.timezone.utc)
        return d
    except Exception:
        raise HTTPException(status_code=400, detail="INVALID_TS_FORMAT")


def _window_utc(day: DayModel) -> tuple[dt.datetime, dt.datetime]:
    start_local = dt.datetime.combine(day.date, day.start_time, tzinfo=TZ)
    end_local   = dt.datetime.combine(day.date, day.end_time,   tzinfo=TZ)
    if end_local <= start_local:
        # atravessa a meia-noite
        end_local = end_local + dt.timedelta(days=1)

    # tolerâncias
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
    # valida enrollment & day_event
    enr = db.get(EnrollmentModel, body.enrollment_id)
    if not enr:
        raise HTTPException(status_code=404, detail="ENROLLMENT_NOT_FOUND")

    day = db.get(DayModel, body.day_event_id)
    if not day:
        raise HTTPException(status_code=404, detail="DAY_NOT_FOUND")

    # opcional: garantir mesmo evento
    if getattr(enr, "event_id", None) != getattr(day, "event_id", None):
        raise HTTPException(status_code=400, detail="MISMATCH_EVENT")

    now_utc = _parse_ts(body.ts)
    start_utc, end_utc = _window_utc(day)
    if not (start_utc <= now_utc <= end_utc):
        raise HTTPException(status_code=400, detail="OUT_OF_WINDOW")

    # upsert por (enrollment_id, day_event_id)
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
        "window_utc": {"start": start_utc.isoformat(), "end": end_utc.isoformat()},
    }


# GET de debug para conferir o registro salvo
@router.get("/attendance/{enrollment_id}/{day_event_id}")
def get_attendance(
    enrollment_id: int,
    day_event_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_user_scoped),
):
    att = db.execute(
        select(AttendanceModel).where(
            AttendanceModel.enrollment_id == enrollment_id,
            AttendanceModel.day_event_id == day_event_id,
        )
    ).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="ATTENDANCE_NOT_FOUND")

    return {
        "enrollment_id": att.enrollment_id,
        "day_event_id": att.day_event_id,
        "checkin_at": getattr(att, "checkin_at", None),
        "checkout_at": getattr(att, "checkout_at", None),
        "origin": getattr(att, "origin", None),
    }
