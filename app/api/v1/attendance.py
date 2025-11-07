# app/api/v1/attendance.py
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_current_user_scoped
from app.api.permissions import Role
from app.schemas.user import UserOut
from pydantic import BaseModel

router = APIRouter()

class AttendanceOut(BaseModel):
    id: int
    enrollment_id: int
    status: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[AttendanceOut])
def list_attendance(
    db: Session = Depends(get_db),
    user: UserOut = Depends(get_current_user_scoped),
):
    # Se Aluno -> filtra por suas matrículas
    # Se Portaria/Organizador/Admin -> pode ver geral
    # Ajuste os modelos/joins conforme seu schema
    if user.role == Role.ALUNO:
        # exemplo: filtrar por enrollment.student_id == user.id
        # ...
        pass
    # ...
    return []
