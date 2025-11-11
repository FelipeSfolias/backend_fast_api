from pydantic import BaseModel
from enum import Enum

class EnrollmentStatus(str, Enum):
    pending="pending"
    confirmed="confirmed"
    waitlist="waitlist"
    cancelled="cancelled"

class Enrollment(BaseModel):
    id: int
    student_id: int
    event_id: int
    status: EnrollmentStatus

class EnrollmentCreate(BaseModel):
    student_id: int
    event_id: int
