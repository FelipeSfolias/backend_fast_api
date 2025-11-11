# app/api/v1/gate.py
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
<<<<<<< HEAD
from pydantic import BaseModel
import datetime as dt
from zoneinfo import ZoneInfo
from app.api.v1.users import require_roles
=======

>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_min_role, ROLE_PORTARIA
from app.models.enrollment import Enrollment as EnrollmentModel
from app.models.day_event import DayEvent as DayEventModel
from app.models.attendance import Attendance as AttendanceModel

router = APIRouter()

from pydantic import BaseModel
class GatePayload(BaseModel):
    enrollment_id: int
    day_event_id: int
    action: Literal["checkin", "checkout"]

def _require_same_tenant(db: Session, tenant, enr_id: int, day_id: int) -> tuple[EnrollmentModel, DayEventModel]:
    enr = db.get(EnrollmentModel, enr_id)
    if not enr:
        raise HTTPException(status_code=404, detail="Enrollment não encontrado")
    day = db.get(DayEventModel, day_id)
    if not day:
        raise HTTPException(status_code=404, detail="Dia do evento não encontrado")
    # valida escopo via evento do DayEvent
    ev = db.get(type(day).event.property.mapper.class_, day.event_id)  # DayEvent->Event
    if not ev or ev.client_id != tenant.id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    return enr, day

<<<<<<< HEAD
def _parse_ts(ts: str | None):
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


def _window_utc(day: DayModel):
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


@router.post("/scan", dependencies=[Depends(require_roles("portaria","organizer","admin"))])
def scan(
    body: ScanIn = Body(...),
=======
@router.post("/scan", dependencies=[Depends(require_min_role(ROLE_PORTARIA))])
def gate_scan(
    body: GatePayload = Body(...),
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    enr, day = _require_same_tenant(db, tenant, body.enrollment_id, body.day_event_id)

    att = db.execute(
        select(AttendanceModel).where(
            AttendanceModel.enrollment_id == enr.id,
            AttendanceModel.day_event_id == day.id,
        )
    ).scalar_one_or_none()

    now = dt.datetime.now(dt.timezone.utc)
    if body.action == "checkin":
        if not att:
            att = AttendanceModel(enrollment_id=enr.id, day_event_id=day.id, checkin_at=now, origin="gate")
        else:
            att.checkin_at = now
    else:
<<<<<<< HEAD
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
@router.get("/attendance/{enrollment_id}/{day_event_id}", dependencies=[Depends(require_roles("portaria","organizer","admin"))])
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
=======
        if not att:
            raise HTTPException(status_code=404, detail="Registro de presença não encontrado para checkout")
        att.checkout_at = now
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0

    db.add(att); db.commit(); db.refresh(att)
    return {
        "id": att.id,
        "enrollment_id": att.enrollment_id,
        "day_event_id": att.day_event_id,
        "checkin_at": att.checkin_at,
        "checkout_at": att.checkout_at,
    }
