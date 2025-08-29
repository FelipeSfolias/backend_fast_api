from pydantic import BaseModel
from datetime import date, time

class DayEventBase(BaseModel):
    date: date
    start_time: time
    end_time: time
    room: str | None = None
    capacity: int | None = None

class DayEventCreate(DayEventBase): pass
class DayEvent(DayEventBase):
    id: int
    event_id: int
