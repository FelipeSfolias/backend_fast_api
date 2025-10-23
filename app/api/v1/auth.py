# app/api/v1/auth.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import select

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

router = APIRouter(prefix="/auth", tags=["auth"])

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def ensure_password_policy(password: str) -> None:
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Senha fora do padrão (8–128).")

def issue_tokens_for(user: User, tenant) -> TokenPair:
    sub = str(user.id)  # use sempre o id como subject
    access = create_access_token(sub=sub, tenant=tenant.slug, scope="user")
    refresh = create_refresh_token(sub=sub, tenant=tenant.slug, scope="user")
    return TokenPair(access_token=access, refresh_token=refresh, token_type="bearer")

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        # manter 422 quando nenhum for enviado
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["token"], "msg": "Field required", "type": "value_error.missing"}],
        )
    return tok

# nomes possíveis no modelo de usuário (AJUSTE AQUI se seu modelo usar outro campo)
_PASSWORD_FIELDS = ["hashed_password", "password_hash", "password"]

def _read_password_field(user: User) -> Tuple[str, str | None]:
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
# Esquemas auxiliares
# --------------------------------------------------------------------

class LoginJSON(BaseModel):
    username: EmailStr
    password: str

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.post("/login", response_model=TokenPair)
def login(
    body: dict,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    """
    Login via JSON livre (espera {"email": "...", "password": "..."}).
    Usa verify_and_maybe_upgrade() para lidar com hashes legados (bcrypt >72 bytes)
    e migra para Argon2 quando necessário.
    """
    email = normalize_email(body.get("email") or "")
    password = body.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="E-mail e senha são obrigatórios.")
    ensure_password_policy(password)

    # Filtro por tenant (AJUSTE AQUI se sua relação/coluna for diferente)
    user = db.execute(
        select(User).where(
            User.email == email,
            User.client_id == tenant.id
        )
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored = _read_password_field(user)

    # Se já está hasheado (bcrypt/argon2), verifica e faz upgrade se necessário
    if stored and _looks_hashed(stored):
        try:
            ok, new_hash = verify_and_maybe_upgrade(password, stored)
        except Exception:
            # Não exponha detalhes (inclui caso bcrypt >72B)
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
        if not ok:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    else:
        # Caso muito legado: senha em claro no banco (evite, mas suportamos migração)
        if stored is None or stored != password:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
        new_hash = hash_password(password)

    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user)
        db.commit()

    return issue_tokens_for(user, tenant)


@router.post("/login-json", response_model=TokenPair)
def login_json(
    payload: LoginJSON,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    """
    Login via JSON tipado (LoginJSON: username=email, password).
    Mesma lógica do /login: verify_and_maybe_upgrade e upgrade de hash.
    """
    email = normalize_email(payload.username)
    ensure_password_policy(payload.password)

    user = db.execute(
        select(User).where(
            User.email == email,
            User.client_id == tenant.id
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    field_name, stored = _read_password_field(user)

    if stored and _looks_hashed(stored):
        try:
            ok, new_hash = verify_and_maybe_upgrade(payload.password, stored)
        except Exception:
            raise HTTPException(status_code=401, detail="invalid_credentials")
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


@router.post("/token", response_model=TokenPair)
def login_oauth2_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    """
    Login no padrão OAuth2 (form-data: username/password).
    Usa a mesma verificação e upgrade do login JSON.
    """
    email = normalize_email(form.username)
    password = form.password or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="E-mail e senha são obrigatórios.")
    ensure_password_policy(password)

    user = db.execute(
        select(User).where(
            User.email == email,
            User.client_id == tenant.id
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored = _read_password_field(user)

    if stored and _looks_hashed(stored):
        try:
            ok, new_hash = verify_and_maybe_upgrade(password, stored)
        except Exception:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
        if not ok:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    else:
        if stored is None or stored != password:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
        new_hash = hash_password(password)

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

    # emite novo access; mantém o mesmo refresh
    access = create_access_token(sub=payload["sub"], tenant=tenant.slug, scope="user")
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
            rt.revoked_at = datetime.now(timezone.utc)
            db.add(rt)
            db.commit()
    return {"ok": True}


@router.post("/signup")
def signup(
    body: UserCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    """
    Cadastro: sempre aplica hash_password() no campo de senha.
    Garante e-mail único por tenant.
    """
    email = normalize_email(body.email)
    ensure_password_policy(body.password)

    # e-mail único por tenant
    if db.execute(
        select(User).where(User.email == email, User.client_id == tenant.id)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # escolha do campo de senha conforme o modelo
    password_field = None
    for f in _PASSWORD_FIELDS:
        if hasattr(User, f):
            password_field = f
            break
    if not password_field:
        raise HTTPException(status_code=500, detail="User model missing password field")

    # cria usuário
    user = User(
        client_id=tenant.id,  # AJUSTE AQUI se o vínculo com tenant for diferente
        name=getattr(body, "name", None),
        email=email,
    )
    setattr(user, password_field, hash_password(body.password))

    db.add(user)
    db.commit()
    db.refresh(user)

    # atribui roles se enviados
    for rname in getattr(body, "role_names", []) or []:
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role:
            # garanta que existe relação User.roles no seu modelo
            user.roles.append(role)
    db.commit()

    return {"id": user.id, "email": user.email}
