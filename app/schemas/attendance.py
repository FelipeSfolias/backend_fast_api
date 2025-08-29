from pydantic import BaseModel
from datetime import datetime

class Attendance(BaseModel):
    id: int
    enrollment_id: int
    day_event_id: int
    checkin_at: datetime | None
    checkout_at: datetime | None
    origin: str
