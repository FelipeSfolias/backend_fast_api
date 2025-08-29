from pydantic import BaseModel, EmailStr
from typing import Optional

class StudentBase(BaseModel):
    name: str
    cpf: str
    email: EmailStr
    ra: Optional[str] = None
    phone: Optional[str] = None

class StudentCreate(StudentBase): pass
class StudentUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    ra: str | None = None
    phone: str | None = None

class Student(StudentBase):
    id: int
    client_id: int
