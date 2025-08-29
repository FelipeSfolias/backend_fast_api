from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from app.db.base import Base

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    capacity_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    workload_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_presence_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="draft")

    client = relationship("Client", back_populates="events")
    days = relationship("DayEvent", back_populates="event", cascade="all, delete-orphan")
