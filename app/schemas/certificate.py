from pydantic import BaseModel
from datetime import datetime

class Certificate(BaseModel):
    id: int
    enrollment_id: int
    issued_at: datetime
    pdf_url: str
    verify_code: str
    status: str
