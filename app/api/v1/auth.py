from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone

from app.api.deps import get_db, get_tenant
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_refresh
)
from app.schemas.auth import TokenPair, LoginRequest
from app.schemas.user import UserCreate
from app.models.user import User
from app.models.role import Role
from app.models.tokens import RefreshToken
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import select

from app.api.deps import get_db, get_tenant
from app.core.security import create_access_token, decode_refresh
from app.schemas.auth import TokenPair
from app.models.tokens import RefreshToken

router = APIRouter()

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        # manter 422 quando nenhum for enviado
        raise HTTPException(status_code=422, detail=[{"loc":["token"],"msg":"Field required","type":"value_error.missing"}])
    return tok

# IMPORTANTE: como esse router será montado em "/{tenant}/auth",
# aqui os paths são APENAS "/login", "/refresh", "/logout", etc.
@router.post("/login", response_model=TokenPair)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    user = db.execute(
        select(User).where(User.email == form.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access = create_access_token(subject=user.email, tenant_slug=tenant.slug)
    refresh = create_refresh_token(subject=user.email, tenant_slug=tenant.slug)
    payload = decode_refresh(refresh)

    db.add(RefreshToken(
        jti=payload["jti"],
        user_email=user.email,
        tenant_slug=tenant.slug,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    ))
    db.commit()

    return TokenPair(access_token=access, refresh_token=refresh)

# opcional: login via JSON
@router.post("/login-json", response_model=TokenPair)
def login_json(body: LoginRequest, db: Session = Depends(get_db), tenant = Depends(get_tenant)):
    user = db.execute(
        select(User).where(User.email == body.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access = create_access_token(subject=user.email, tenant_slug=tenant.slug)
    refresh = create_refresh_token(subject=user.email, tenant_slug=tenant.slug)
    payload = decode_refresh(refresh)

    db.add(RefreshToken(
        jti=payload["jti"],
        user_email=user.email,
        tenant_slug=tenant.slug,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    ))
    db.commit()

    return TokenPair(access_token=access, refresh_token=refresh)

@router.post("/refresh", response_model=TokenPair)
def refresh(
    token: str | None = Body(default=None, embed=True),        # aceita {"token":"..."}
    token_q: str | None = Query(default=None, alias="token"),  # aceita ?token=...
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if not payload or payload.get("tenant") != tenant.slug:
        raise HTTPException(status_code=401, detail="Invalid token")

    access = create_access_token(subject=payload["sub"], tenant_slug=tenant.slug)
    return TokenPair(access_token=access, refresh_token=tok)

@router.post("/logout")
def logout(
    token: str | None = Body(default=None, embed=True),
    token_q: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if payload and payload.get("tenant") == tenant.slug:
        rt = db.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).scalar_one_or_none()
        if rt:
            rt.revoked_at = datetime.utcnow()
            db.add(rt); db.commit()
    return {"ok": True}

@router.post("/signup")
def signup(body: UserCreate, db: Session = Depends(get_db), tenant = Depends(get_tenant)):
    if db.execute(
        select(User).where(User.email == body.email, User.client_id == tenant.id)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(client_id=tenant.id, name=body.name, email=body.email,
                hashed_password=get_password_hash(body.password))
    db.add(user); db.commit(); db.refresh(user)

    for rname in body.role_names:
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role:
            user.roles.append(role)
    db.commit()
    return {"id": user.id, "email": user.email}
