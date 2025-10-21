from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.models.attendance import Attendance
from app.models.enrollment import Enrollment
from app.schemas.attendance import Attendance as AttSchema

router = APIRouter()

# backend/api/v1/attendance.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from models.attendance import Attendance
from models.enrollment import Enrollment
import datetime as dt

router = APIRouter()

class CheckIn(BaseModel):
    enrollment_id: int
    day_event_id: int
    origin: str | None = "manual"

@router.post("/checkin")
def checkin(
    payload: CheckIn,
    tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    enr = db.get(Enrollment, payload.enrollment_id)
    if not enr or enr.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    att = db.execute(
        select(Attendance).where(
            Attendance.enrollment_id == payload.enrollment_id,
            Attendance.day_event_id == payload.day_event_id
        )
    ).scalar_one_or_none()

    if not att:
        att = Attendance(
            enrollment_id=payload.enrollment_id,
            event_id=enr.event_id,
            day_event_id=payload.day_event_id,
            origin=payload.origin or "manual",
            checkin_at=dt.datetime.utcnow(),
        )
        db.add(att)
    else:
        att.checkin_at = att.checkin_at or dt.datetime.utcnow()

    db.commit()
    db.refresh(att)
    return {"id": att.id, "checkin_at": att.checkin_at}

class CheckOut(BaseModel):
    enrollment_id: int
    day_event_id: int

@router.post("/checkout")
def checkout(
    payload: CheckOut,
    tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    att = db.execute(
        select(Attendance).where(
            Attendance.enrollment_id == payload.enrollment_id,
            Attendance.day_event_id == payload.day_event_id
        )
    ).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Attendance not found")
    att.checkout_at = dt.datetime.utcnow()
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "checkout_at": att.checkout_at}
