from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.api.deps import get_db, get_tenant
from app.core.tokens import (
    create_access_token,
    create_refresh_token,
    decode_refresh,
)
from app.core.security_password import (
    verify_and_maybe_upgrade,
    hash_password,
)

from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate
from app.models.user import User
from app.models.role import Role
from app.models.tokens import RefreshToken

router = APIRouter()

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def issue_tokens_for(user: User, tenant, scope: str = "") -> dict:
    sub = user.email
    return {
        "access_token": create_access_token(sub=sub, tenant=tenant.slug, scope=scope),
        "refresh_token": create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope),
        "token_type": "bearer",
    }

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        # manter 422 quando nenhum for enviado
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["token"], "msg": "Field required", "type": "value_error.missing"}],
        )
    return tok

# nomes possíveis no modelo de usuário
_PASSWORD_FIELDS = ["password_hash", "hashed_password", "password"]

def _read_password_field(user: User):
    """
    Retorna (field_name, stored_value). Se não existir, levanta AttributeError.
    """
    for f in _PASSWORD_FIELDS:
        if hasattr(user, f):
            return f, getattr(user, f)
    raise AttributeError(f"User model has no password field (expected one of: {_PASSWORD_FIELDS})")

def _looks_hashed(value: str) -> bool:
    # bcrypt: $2b$ / $2a$ / $2y$ | argon2: $argon2...
    return isinstance(value, str) and (value.startswith("$2") or value.startswith("$argon2"))

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    user = db.execute(
        select(User).where(User.email == form_data.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    field_name, stored = _read_password_field(user)

    if stored and _looks_hashed(stored):
        ok, new_hash = verify_and_maybe_upgrade(form_data.password, stored)
        if not ok:
            raise HTTPException(status_code=401, detail="invalid_credentials")
    else:
        # senha legada em texto puro (ou None) — aceita e já migra para hash
        if stored is None or stored != form_data.password:
            raise HTTPException(status_code=401, detail="invalid_credentials")
        new_hash = hash_password(form_data.password)

    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user)
        db.commit()

    return issue_tokens_for(user, tenant)


class LoginJSON(BaseModel):
    username: EmailStr
    password: str

@router.post("/login-json")
def login_json(
    payload: LoginJSON,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    user = db.execute(
        select(User).where(User.email == payload.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    field_name, stored = _read_password_field(user)

    if stored and _looks_hashed(stored):
        ok, new_hash = verify_and_maybe_upgrade(payload.password, stored)
        if not ok:
            raise HTTPException(status_code=401, detail="invalid_credentials")
    else:
        if stored is None or stored != payload.password:
            raise HTTPException(status_code=401, detail="invalid_credentials")
        new_hash = hash_password(payload.password)

    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user)
        db.commit()

    return issue_tokens_for(user, tenant)


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

    access = create_access_token(sub=payload["sub"], tenant=tenant.slug)
    return TokenPair(access_token=access, refresh_token=tok, token_type="bearer")


@router.post("/logout")
def logout(
    token: str | None = Body(default=None, embed=True),
    token_q: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if payload and payload.get("tenant") == tenant.slug and "jti" in payload:
        rt = db.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).scalar_one_or_none()
        if rt and rt.revoked_at is None:
            rt.revoked_at = datetime.utcnow()
            db.add(rt)
            db.commit()
    return {"ok": True}


@router.post("/signup")
def signup(
    body: UserCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    # e-mail único por tenant
    if db.execute(
        select(User).where(User.email == body.email, User.client_id == tenant.id)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # escolha dinâmica do campo de senha
    password_field = None
    for f in _PASSWORD_FIELDS:
        if hasattr(User, f):
            password_field = f
            break
    if not password_field:
        raise HTTPException(status_code=500, detail="User model missing password field")

    user = User(
        client_id=tenant.id,
        name=body.name,
        email=body.email,
    )
    setattr(user, password_field, hash_password(body.password))

    db.add(user)
    db.commit()
    db.refresh(user)

    # atribuir perfis se enviados
    for rname in getattr(body, "role_names", []) or []:
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role:
            user.roles.append(role)
    db.commit()

    return {"id": user.id, "email": user.email}
