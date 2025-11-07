# app/api/deps.py
from __future__ import annotations
from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.user import User
from app.core.tokens import decode_access  # precisa existir no seu projeto

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _load_tenant(db: Session, tenant_param: str) -> Client | None:
    if tenant_param.isdigit():
        return db.get(Client, int(tenant_param))
    return db.execute(select(Client).where(Client.slug == tenant_param)).scalar_one_or_none()

def get_tenant(request: Request, db: Session = Depends(get_db)) -> Client:
    tenant_param = request.path_params.get("tenant")
    if tenant_param is None:
        raise HTTPException(status_code=400, detail="Tenant ausente na rota")
    tenant = _load_tenant(db, str(tenant_param))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant

def _load_user_by_sub(db: Session, tenant: Client, sub: int) -> User | None:
    return db.execute(
        select(User).options(joinedload(User.roles)).where(User.id == int(sub), User.client_id == tenant.id)
    ).scalar_one_or_none()

def get_current_user_scoped(
    token: str = Depends(lambda request: request.headers.get("Authorization","").split("Bearer ",1)[-1] if "Authorization" in request.headers else ""),
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    payload = decode_access(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    token_tenant = str(payload.get("tenant"))
    if token_tenant not in {str(tenant.id), tenant.slug}:
        raise HTTPException(status_code=401, detail="Tenant mismatch")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token (sub)")

    user = _load_user_by_sub(db, tenant, sub)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    status_val = getattr(user, "status", "active")
    if status_val and str(status_val).lower() != "active":
        raise HTTPException(status_code=401, detail="User disabled")

    return user

get_current_user = get_current_user_scoped
