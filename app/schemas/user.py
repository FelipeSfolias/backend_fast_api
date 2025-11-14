# app/schemas/user.py
from __future__ import annotations
from typing import Literal, List, Optional
from pydantic import BaseModel, EmailStr, Field

RoleName = Literal["admin", "organizer", "portaria", "aluno"]

class UserBase(BaseModel):
    name: str
    email: EmailStr
    status: str = "active"
    mfa: Optional[bool] = None

class UserCreate(UserBase):
    password: str = Field(min_length=6)
    roles: List[RoleName] = Field(default_factory=list)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    mfa: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
    roles: Optional[List[RoleName]] = None  # substitui conjunto de papéis (se enviado)

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    status: str
    mfa: Optional[bool] = None
    roles: List[str] = []

    model_config = {"from_attributes": True}
