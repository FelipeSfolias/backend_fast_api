# app/api/v1/auth.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Tuple, Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant
from app.core.tokens import (create_access_token, create_refresh_token, decode_refresh)
from app.core.security_password import (verify_and_maybe_upgrade, hash_password)
from app.schemas.auth import TokenPair  # LoginRequest existe, mas o /login não tipa mais o body
from app.schemas.user import UserCreate
from app.models.user import User
from app.models.role import Role
from app.models.tokens import RefreshToken

router = APIRouter()

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def ensure_password_policy(password: str) -> None:
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Senha fora do padrão (8–128).")

def issue_tokens_for(user: User, tenant, scope: str = "") -> TokenPair:
    # Mantém compat: sub = email (se o restante do código espera isso)
    sub = user.email
    return TokenPair(
        access_token=create_access_token(sub=sub, tenant=tenant.slug, scope=scope),
        refresh_token=create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope),
        token_type="bearer",
    )

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["token"], "msg": "Field required", "type": "value_error.missing"}],
        )
    return tok

# nomes possíveis no modelo de usuário
_PASSWORD_FIELDS = ["hashed_password", "password_hash", "password"]

def _read_password_field(user: User) -> Tuple[str, str | None]:
    for f in _PASSWORD_FIELDS:
        if hasattr(user, f):
            return f, getattr(user, f)
    raise AttributeError(f"User model has no password field (expected one of: {_PASSWORD_FIELDS})")

def _looks_hashed(value: str) -> bool:
    return isinstance(value, str) and (value.startswith("$2") or value.startswith("$argon2"))

async def _extract_credentials_from_request(request: Request) -> Tuple[str, str]:
    """
    Extrai (email, password) aceitando:
      - JSON: {"username": "...", "password": "..."}
      - application/x-www-form-urlencoded
      - raw "username=...&password=..." (mesmo com Content-Type incorreto)
    """
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    # 1) form urlencoded
    if ctype == "application/x-www-form-urlencoded":
        form = await request.form()
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""
        if username and password:
            return normalize_email(username), password

    # 2) corpo bruto
    body_bytes = await request.body()
    text = body_bytes.decode(errors="ignore").strip() if body_bytes else ""

    # 2a) JSON
    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            username = (data.get("username") or "").strip()
            password = data.get("password") or ""
            if username and password:
                return normalize_email(username), password
        except Exception:
            pass

    # 2b) querystring bruta
    if text:
        parsed = parse_qs(text, keep_blank_values=True)
        if parsed:
            username = (parsed.get("username", [""])[0] or "").strip()
            password = parsed.get("password", [""])[0] or ""
            if username and password:
                return normalize_email(username), password

    raise HTTPException(
        status_code=422,
        detail=[{"loc": ["body"], "msg": "Esperado JSON {username,password}, form-url-encoded ou raw 'username=...&password=...'", "type": "value_error"}],
    )

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.post("/login", response_model=TokenPair)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email, password = await _extract_credentials_from_request(request)
    ensure_password_policy(password)

    # >>> IMPORTANTÍSSIMO: filtra por RELAÇÃO usando slug (evita mismatch de ids)
    user = db.execute(
        select(User).where(
            User.email == email,
            User.client.has(slug=tenant.slug)  # <-- mudança principal
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


@router.post("/token", response_model=TokenPair)
def login_oauth2_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email = normalize_email(form.username)
    password = form.password or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="E-mail e senha são obrigatórios.")
    ensure_password_policy(password)

    user = db.execute(
        select(User).where(
            User.email == email,
            User.client.has(slug=tenant.slug)  # <-- mudança principal
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


from datetime import datetime
from sqlalchemy import select
from fastapi import Body, Depends, HTTPException, Query

# ... (demais imports do arquivo)
# from app.core.tokens import create_access_token, create_refresh_token, decode_refresh
# from app.models.tokens import RefreshToken

@router.post("/refresh", response_model=TokenPair)
def refresh(
    token: str | None = Body(default=None, embed=True),        # {"token":"<refresh>"}
    token_q: str | None = Query(default=None, alias="token"),  # ?token=<refresh>
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)

    payload = decode_refresh(tok)
    if not payload or payload.get("tenant") != tenant.slug:
        raise HTTPException(status_code=401, detail="Invalid token")

    old_jti = payload.get("jti")
    if not old_jti:
        raise HTTPException(status_code=401, detail="Invalid token")

    # reuso/rotação
    rt = db.execute(
        select(RefreshToken).where(RefreshToken.jti == old_jti)
    ).scalar_one_or_none()
    if rt and rt.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    if rt:
        rt.revoked_at = datetime.utcnow()
        db.add(rt)

    sub = payload.get("sub")
    scope = payload.get("scope", "")

    new_access = create_access_token(sub=sub, tenant=tenant.slug, scope=scope)
    new_refresh = create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope)

    new_payload = decode_refresh(new_refresh)
    new_jti = new_payload.get("jti") if new_payload else None
    if new_jti:
        db.add(RefreshToken(jti=new_jti))
    db.commit()

    return TokenPair(access_token=new_access, refresh_token=new_refresh, token_type="bearer")


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
    email = normalize_email(body.email)
    ensure_password_policy(body.password)

    # único por tenant (via relação pelo slug)
    if db.execute(
        select(User).where(
            User.email == email,
            User.client.has(slug=tenant.slug)  # <-- mudança principal
        )
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    password_field = None
    for f in _PASSWORD_FIELDS:
        if hasattr(User, f):
            password_field = f
            break
    if not password_field:
        raise HTTPException(status_code=500, detail="User model missing password field")

    # vincula ao tenant atual
    user = User(
        email=email,
        name=getattr(body, "name", None),
    )
    # se seu modelo exige client_id explicitamente, defina:
    # user.client_id = db.execute(select(Client.id).where(Client.slug == tenant.slug)).scalar_one()
    setattr(user, password_field, hash_password(body.password))

    db.add(user)
    db.commit()
    db.refresh(user)

    # atribui roles se enviados
    for rname in getattr(body, "role_names", []) or []:
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role and hasattr(user, "roles"):
            user.roles.append(role)
    db.commit()

    return {"id": user.id, "email": user.email}
