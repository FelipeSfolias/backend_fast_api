from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date, time

# ---------------------------
# Event Schemas
# ---------------------------

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    venue: Optional[str] = None
    capacity_total: Optional[int] = None
    workload_hours: Optional[int] = None
    min_presence_pct: Optional[int] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    status: str = "draft"

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    venue: str | None = None
    capacity_total: int | None = None
    workload_hours: int | None = None
    min_presence_pct: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: str | None = None

    class Config:
        from_attributes = True

class Event(EventBase):
    id: int
    client_id: int

# ---------------------------
# DayEvent Update Schema
# (usado por PUT /events/{event_id}/days/{day_id})
# ---------------------------

class DayEventUpdate(BaseModel):
    date: Optional [datetime] | None = None          # <- corrigido (antes estava 'data')
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = None
    capacity: int | None = None

    class Config:
        from_attributes = True
