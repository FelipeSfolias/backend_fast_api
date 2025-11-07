# app/schemas/user.py
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.api.permissions import Role

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    role: Role = Role.ALUNO
    tenant_id: int

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[Role] = None  # só Admin do Cliente deve poder mudar
    # sem tenant_id aqui por segurança

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    role: Role
    tenant_id: int

    class Config:
        from_attributes = True  # pydantic v2 (ajuste para orm_mode=True no v1)
