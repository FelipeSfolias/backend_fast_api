# app/api/v1/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.tokens import create_access_token, create_refresh_token, decode_refresh
from app.core.security_password import verify_and_maybe_upgrade
from app.core.security import hash_password
from app.core.rbac import require_roles

from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, User as UserOut

router = APIRouter()

@router.post("/login")
def login_for_access_token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    user = db.execute(
        select(User).where(User.email == form.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    ok, new_hash = verify_and_maybe_upgrade(form.password, user.hashed_password)
    if not ok:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if new_hash:
        user.hashed_password = new_hash
        db.add(user); db.commit()

    tenant_claim = tenant.slug or str(tenant.id)
    access = create_access_token(sub=user.id, tenant=tenant_claim)
    refresh = create_refresh_token(sub=user.id, tenant=tenant_claim)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/refresh")
def refresh_access_token(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    payload = decode_refresh(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Refresh inválido ou expirado")
    if str(payload.get("tenant")) not in {str(tenant.id), tenant.slug}:
        raise HTTPException(status_code=401, detail="Tenant mismatch")
    user = db.get(User, int(payload["sub"]))
    if not user or user.client_id != tenant.id:
        raise HTTPException(status_code=401, detail="User not found")
    tenant_claim = tenant.slug or str(tenant.id)
    access = create_access_token(sub=user.id, tenant=tenant_claim)
    return {"access_token": access, "token_type": "bearer"}

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles("admin"))])
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    exists = db.execute(select(User).where(User.email == body.email, User.client_id == tenant.id)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado neste cliente")

    user = User(
        client_id=tenant.id,
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        status=body.status or "active",
    )
    db.add(user); db.commit(); db.refresh(user)

    for rname in (body.role_names or []):
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role:
            user.roles.append(role)
    db.commit(); db.refresh(user)

    return UserOut(
        id=user.id,
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        status=user.status,
        roles=[r.name for r in user.roles or []],
    )

@router.get("/me", response_model=UserOut)
def read_me(user = Depends(get_current_user_scoped)):
    return UserOut(
        id=user.id,
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        status=user.status,
        roles=[r.name for r in user.roles or []],
    )
