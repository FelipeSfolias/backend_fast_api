from __future__ import annotations
from typing import Optional
from datetime import datetime, date, time
from pydantic import BaseModel


# ---- referências “lite” usadas na resposta ----

class StudentRef(BaseModel):
    id: int
    name: str
    email: str
    cpf: Optional[str] = None
    ra: Optional[str] = None
    phone: Optional[str] = None

    model_config = {"from_attributes": True}


class EventRef(BaseModel):
    id: int
    title: str
    venue: Optional[str] = None
    workload_hours: Optional[int] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DayEventRef(BaseModel):
    id: int
    date: date
    start_time: time
    end_time: time
    room: Optional[str] = None
    capacity: Optional[int] = None

    model_config = {"from_attributes": True}


class EnrollmentRef(BaseModel):
    id: int
    status: str  # se no ORM vier Enum, abaixo converto p/ string
    student: StudentRef
    event: EventRef

    model_config = {"from_attributes": True}


# ---- resposta principal ----

class AttendanceOut(BaseModel):
    id: int
    checkin_at: Optional[datetime] = None
    checkout_at: Optional[datetime] = None
    origin: str
    day_event: DayEventRef
    enrollment: EnrollmentRef

    model_config = {"from_attributes": True}
