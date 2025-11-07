# app/api/v1/gate.py
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select

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

@router.post("/scan", dependencies=[Depends(require_min_role(ROLE_PORTARIA))])
def gate_scan(
    body: GatePayload = Body(...),
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
        if not att:
            raise HTTPException(status_code=404, detail="Registro de presença não encontrado para checkout")
        att.checkout_at = now

    db.add(att); db.commit(); db.refresh(att)
    return {
        "id": att.id,
        "enrollment_id": att.enrollment_id,
        "day_event_id": att.day_event_id,
        "checkin_at": att.checkin_at,
        "checkout_at": att.checkout_at,
    }
