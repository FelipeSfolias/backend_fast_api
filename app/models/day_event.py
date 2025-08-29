from datetime import date, time, datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, Date, Time
from app.db.base import Base

class DayEvent(Base):
    __tablename__ = "day_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    date: Mapped[datetime] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    room: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    event = relationship("Event", back_populates="days")
