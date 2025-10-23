from pydantic import BaseModel, field_validator
from typing import Optional
import datetime as dt


class DayEventBase(BaseModel):
    date: dt.date
    start_time: dt.time
    end_time: dt.time
    room: Optional[str] = None
    capacity: Optional[int] = None

    # Validação opcional: se ambos informados, start_time < end_time
    @field_validator("end_time")
    @classmethod
    def _check_time_order(cls, v: dt.time, info):
        start = info.data.get("start_time")
        if start and v and start >= v:
            raise ValueError("end_time deve ser maior que start_time")
        return v


class DayEventCreate(DayEventBase):
    pass


class DayEvent(DayEventBase):
    id: int
    event_id: int


class DayEventUpdate(BaseModel):
    date: Optional[dt.date] = None
    start_time: Optional[dt.time] = None
    end_time: Optional[dt.time] = None
    room: Optional[str] = None
    capacity: Optional[int] = None

    class Config:
        from_attributes = True

    # Validação opcional também no update (quando ambos forem enviados)
    @field_validator("end_time")
    @classmethod
    def _check_time_order_update(cls, v: Optional[dt.time], info):
        start = info.data.get("start_time")
        if start is not None and v is not None and start >= v:
            raise ValueError("end_time deve ser maior que start_time")
        return v
