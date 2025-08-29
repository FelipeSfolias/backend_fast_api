from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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

class EventCreate(EventBase): pass
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

class Event(EventBase):
    id: int
    client_id: int
