from pydantic import BaseModel, EmailStr
from typing import List

class UserBase(BaseModel):
    name: str
    email: EmailStr
    status: str = "active"

class UserCreate(UserBase):
    password: str
    role_names: List[str] = []

class User(BaseModel):
    id: int
    client_id: int
    name: str
    email: EmailStr
    status: str
    roles: List[str]
