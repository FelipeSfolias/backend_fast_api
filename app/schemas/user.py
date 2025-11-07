# app/schemas/user.py
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, EmailStr

# v2: from_attributes; v1: orm_mode=True (se estiver em Pydantic v1, troque as Configs)
class UserBase(BaseModel):
    name: str
    email: EmailStr
    status: str = "active"

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    status: Optional[str] = "active"
    # nomes de papéis a vincular (ex.: ["admin"], ["organizer","portaria"], etc.)
    role_names: Optional[List[str]] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    role_names: Optional[List[str]] = None

class User(BaseModel):
    id: int
    client_id: int
    name: str
    email: EmailStr
    status: str
    roles: List[str] = []

    class Config:
        from_attributes = True

# Compatibilidade com código legado que importava UserOut
UserOut = User
