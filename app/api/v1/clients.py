# app/api/v1/clients.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user_scoped
from app.api.permissions import Role, require_roles
from app.schemas.user import UserOut
from pydantic import BaseModel

router = APIRouter()

class ClientUpdate(BaseModel):
    name: str | None = None
    contact_email: str | None = None

@router.get("/", dependencies=[Depends(require_roles([Role.ADMIN_CLIENTE]))])
def get_client(
    db: Session = Depends(get_db),
    user: UserOut = Depends(get_current_user_scoped),
):
    # retorne dados do tenant do user (Admin)
    # ...
    return {"tenant_id": user.tenant_id}

@router.patch("/", dependencies=[Depends(require_roles([Role.ADMIN_CLIENTE]))])
def update_client(
    data: ClientUpdate,
    db: Session = Depends(get_db),
    user: UserOut = Depends(get_current_user_scoped),
):
    # atualizar dados do tenant
    # ...
    return {"ok": True}
