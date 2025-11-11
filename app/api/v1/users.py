# app/api/v1/users.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.core.security_password import hash_password
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, User as UserOut

router = APIRouter()

def _user_to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        client_id=u.client_id,
        name=u.name,
        email=u.email,
        status=u.status,
        roles=[r.name for r in (u.roles or [])],
    )

@router.get("/", response_model=List[UserOut], dependencies=[Depends(require_roles("admin"))])
def list_users(
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    rows = db.execute(select(User).where(User.client_id == tenant.id)).scalars().all()
    return [_user_to_out(u) for u in rows]

@router.post("/", response_model=UserOut, status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    exists = db.execute(
        select(User).where(User.client_id == tenant.id, User.email == body.email)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Email já cadastrado para este cliente.")

    u = User(
        client_id=tenant.id,
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        status="active",
    )

    if body.role_names:
        roles = db.execute(select(Role).where(Role.name.in_(body.role_names))).scalars().all()
        wanted = {r.lower() for r in body.role_names}
        found = {r.name.lower() for r in roles}
        missing = sorted(wanted - found)
        if missing:
            raise HTTPException(status_code=422, detail=f"Roles inválidas: {', '.join(missing)}")
        u.roles = roles

    db.add(u)
    db.commit()
    db.refresh(u)
    return _user_to_out(u)

@router.put("/{user_id}/roles", response_model=UserOut, dependencies=[Depends(require_roles("admin"))])
def set_roles(
    user_id: int = Path(..., ge=1),
    role_names: List[str] = None,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    if role_names is None:
        raise HTTPException(status_code=422, detail="role_names é obrigatório (lista de strings).")

    u = db.get(User, user_id)
    if not u or u.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # não remover o último admin do tenant
    if "admin" not in {r.lower() for r in role_names}:
        admins_left = db.execute(
            select(User).join(User.roles).where(
                User.client_id == tenant.id, Role.name == "admin", User.id != u.id
            )
        ).scalars().all()
        if not admins_left:
            raise HTTPException(status_code=409, detail="Não é possível remover o último admin do cliente.")

    roles = db.execute(select(Role).where(Role.name.in_(role_names))).scalars().all()
    wanted = {r.lower() for r in role_names}
    found = {r.name.lower() for r in roles}
    missing = sorted(wanted - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"Roles inválidas: {', '.join(missing)}")

    u.roles = roles
    db.add(u); db.commit(); db.refresh(u)
    return _user_to_out(u)
