# app/api/v1/gate.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user_scoped
from app.api.permissions import Role, require_role_at_least
from app.schemas.user import UserOut
from pydantic import BaseModel

router = APIRouter()

class CheckInRequest(BaseModel):
    enrollment_id: int
    gate: str | None = None

@router.post("/checkin", dependencies=[Depends(require_role_at_least(Role.PORTARIA))])
def do_checkin(
    data: CheckInRequest,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    # implemente sua lógica de marcar presença por enrollment_id
    # ...
    return {"ok": True, "checked": data.enrollment_id}

@router.get("/my-status")
def my_gate_status(
    db: Session = Depends(get_db),
    user: UserOut = Depends(get_current_user_scoped),
):
    # aluno/qualquer perfil pode consultar, mas aqui retorne só dados do próprio usuário (LGPD)
    # ...
    return {"user_id": user.id, "status": "ok"}
