# app/api/v1/auth.py
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Tuple
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant
from app.core.tokens import create_access_token, create_refresh_token, decode_refresh
from app.core.security_password import verify_and_maybe_upgrade, hash_password

from app.models.user import User
from app.models.role import Role
from app.models.tokens import RefreshToken

router = APIRouter()

# --------------------- Helpers ---------------------

def normalize_email(email: str):
    return (email or "").strip().lower()

def ensure_password_policy(password: str):
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Senha fora do padrão (8–128).")

def issue_tokens_for(user: User, tenant, scope: str = ""):
    sub = user.email
    return {
        "access_token": create_access_token(sub=sub, tenant=tenant.slug, scope=scope),
        "refresh_token": create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope),
        "token_type": "bearer",
    }

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None):
    tok = token_body or token_query
    if not tok:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["token"], "msg": "Field required", "type": "value_error.missing"}],
        )
    return tok

_PASSWORD_FIELDS = ["password_hash", "hashed_password", "password"]

def _read_password_field(user: User):
    for f in _PASSWORD_FIELDS:
        if hasattr(user, f):
            return f, getattr(user, f)
    raise AttributeError(f"User model has no password field (expected one of: {_PASSWORD_FIELDS})")

def _looks_hashed(value: str):
    return isinstance(value, str) and (value.startswith("$2") or value.startswith("$argon2"))

async def _extract_credentials_from_request(request: Request):
    """
    Extrai (email, password) aceitando:
      - JSON: {"username": "...", "password": "..."}
      - application/x-www-form-urlencoded
      - body cru "username=...&password=..."
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

    # 2b) querystring crua
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

# --------------------- Endpoints ---------------------

@router.post("/login")
async def login(
    request: Request,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email, password = await _extract_credentials_from_request(request)
    ensure_password_policy(password)

    user = db.execute(
        select(User).where(
            User.email == email,
            User.client.has(slug=tenant.slug)
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


@router.post("/token")
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
            User.client.has(slug=tenant.slug)
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


@router.post("/refresh")
def refresh(
    token: str | None = Body(default=None, embed=True),        # {"token":"<refresh>"}
    token_q: str | None = Query(default=None, alias="token"),  # ?token=<refresh>
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if not payload or payload.get("tenant") != tenant.slug or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    scope = payload.get("scope", "")

    new_access = create_access_token(sub=sub, tenant=tenant.slug, scope=scope)
    new_refresh = create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope)

    # opcional: registrar/revogar refresh se houver 'jti'
    try:
        if hasattr(RefreshToken, "jti"):
            old_jti = payload.get("jti")
            if old_jti:
                rt = db.execute(select(RefreshToken).where(RefreshToken.jti == old_jti)).scalar_one_or_none()
                if rt and getattr(rt, "revoked_at", None) is None:
                    rt.revoked_at = datetime.utcnow()
                    db.add(rt)

            new_payload = decode_refresh(new_refresh)
            if new_payload and new_payload.get("jti"):
                row = RefreshToken(jti=new_payload["jti"])
                if hasattr(row, "tenant_slug"):
                    row.tenant_slug = tenant.slug
                if hasattr(row, "client_id"):
                    row.client_id = getattr(tenant, "id", None)
                if hasattr(row, "user_email"):
                    row.user_email = sub
                if hasattr(row, "scope"):
                    row.scope = scope
                if hasattr(row, "issued_at") and "iat" in new_payload:
                    row.issued_at = datetime.fromtimestamp(new_payload["iat"], tz=timezone.utc)
                if hasattr(row, "expires_at") and "exp" in new_payload:
                    row.expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)
                db.add(row)
            db.commit()
    except Exception:
        pass

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
def logout(
    token: str | None = Body(default=None, embed=True),
    token_q: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if payload and payload.get("tenant") == tenant.slug and hasattr(RefreshToken, "jti") and "jti" in payload:
        rt = db.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).scalar_one_or_none()
        if rt and getattr(rt, "revoked_at", None) is None:
            rt.revoked_at = datetime.utcnow()
            db.add(rt)
            db.commit()
    return {"ok": True}


# ---------------------- Signup ----------------------

from pydantic import BaseModel, EmailStr

class UserCreateIn(BaseModel):
    name: str | None = None
    email: EmailStr
    password: str
    role_names: list[str] | None = None

@router.post("/signup")
def signup(
    body: UserCreateIn,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email = normalize_email(body.email)
    ensure_password_policy(body.password)

    exists = db.execute(
        select(User).where(
            User.email == email,
            User.client.has(slug=tenant.slug)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    # decide dinamicamente o campo de senha
    password_field = None
    for f in _PASSWORD_FIELDS:
        if hasattr(User, f):
            password_field = f
            break
    if not password_field:
        raise HTTPException(status_code=500, detail="User model missing password field")

    user = User(email=email, name=body.name)
    if hasattr(User, "client_id"):
        setattr(user, "client_id", getattr(tenant, "id", None))
    elif hasattr(user, "client"):
        setattr(user, "client", tenant)

    setattr(user, password_field, hash_password(body.password))

    db.add(user)
    db.commit()
    db.refresh(user)

    for rname in (body.role_names or []):
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role and hasattr(user, "roles"):
            user.roles.append(role)
    db.commit()

    return {"id": user.id, "email": user.email}
