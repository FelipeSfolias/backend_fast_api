# app/api/v1/certificates.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user_scoped
from app.api.permissions import Role, require_roles
from app.schemas.user import UserOut
from pydantic import BaseModel

router = APIRouter()

class CertificateOut(BaseModel):
    id: int
    enrollment_id: int
    url: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[CertificateOut])
def my_certificates(
    db: Session = Depends(get_db),
    user: UserOut = Depends(get_current_user_scoped),
):
    # Filtrar por certificates de enrollments do próprio user (LGPD)
    # ...
    return []

@router.post("/issue", response_model=CertificateOut, dependencies=[Depends(require_roles([Role.ORGANIZADOR, Role.ADMIN_CLIENTE]))])
def issue_certificate(
    enrollment_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    # Geração/emissão somente Organizador/Admin
    # ...
    return {"id": 1, "enrollment_id": enrollment_id, "url": "https://..."}
