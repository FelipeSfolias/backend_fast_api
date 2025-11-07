# app/schemas/token.py
from typing import Optional
from pydantic import BaseModel
from app.api.permissions import Role

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: int  # user_id
    tenant_id: int
    role: Role
    exp: int
