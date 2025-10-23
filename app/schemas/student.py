from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re

def _normalize_cpf(value: str) -> str:
    if value is None:
        raise ValueError("CPF obrigatório.")
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        raise ValueError("CPF deve conter 11 dígitos.")
    if digits == digits[0] * 11:
        raise ValueError("CPF inválido.")
    def _dv(nums: str) -> str:
        s = sum(int(n) * w for n, w in zip(nums, range(len(nums) + 1, 1, -1)))
        r = (s * 10) % 11
        return "0" if r == 10 else str(r)
    d1 = _dv(digits[:9])
    d2 = _dv(digits[:9] + d1)
    if digits[-2:] != d1 + d2:
        raise ValueError("CPF inválido.")
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"

class StudentBase(BaseModel):
    name: str
    cpf: str
    email: EmailStr
    ra: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("cpf", mode="before")
    @classmethod
    def _valida_formata_cpf(cls, v):
        return _normalize_cpf(v)

class StudentCreate(StudentBase):
    pass

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    cpf: Optional[str] = None
    email: Optional[EmailStr] = None
    ra: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("cpf", mode="before")
    @classmethod
    def _valida_formata_cpf_update(cls, v):
        if v in (None, "", "null"):
            return v
        return _normalize_cpf(v)

class Student(StudentBase):
    id: int
    client_id: int
