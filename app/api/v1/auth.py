# app/api/v1/auth.py
from __future__ import annotations
from datetime import datetime, timezone
import email
from urllib.parse import parse_qs
from typing import Tuple, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import sqlalchemy as sa
from sqlalchemy import select, join
from app.api.deps import get_db, get_tenant
from app.core.tokens import create_access_token, create_refresh_token, decode_refresh
from app.core.security_password import verify_and_maybe_upgrade
from app.models.user import User
from app.models.role import Role
from app.models.user_role import user_roles
# ---- imports tolerantes (evita boot crash se o nome do arquivo/model variar) ----
RefreshToken = None  # type: ignore
try:
    from app.models.tokens import RefreshToken as _RT  # seu ZIP original
    RefreshToken = _RT  # type: ignore
except Exception:
    try:
        from app.models.refresh_token import RefreshToken as _RT  # alguns forks
        RefreshToken = _RT  # type: ignore
    except Exception:
        RefreshToken = None  # sem persistência de refresh; endpoints seguem funcionando

UserRole = None  # type: ignore
try:
    from app.models.user_role import UserRole as _UR
    UserRole = _UR  # type: ignore
except Exception:
    try:
        from app.models.user_roles import UserRole as _UR  # variação comum
        UserRole = _UR  # type: ignore
    except Exception:
        UserRole = None  # usamos fallback SQL textual

router = APIRouter()

# ---------- helpers ----------
def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def ensure_password_policy(password: str):
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Senha fora do padrão (8–128).")

def _read_password_field(user: User):
    for name in ["password_hash", "hashed_password", "password"]:
        if hasattr(user, name):
            return name, getattr(user, name)
    raise HTTPException(status_code=500, detail="Modelo de usuário sem campo de senha")

def _auth_response(user: User, tokens: dict, roles: List[str], primary_role: Optional[str]):
    return {
        **tokens,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "roles": roles,       # <- para o front gatear páginas
            "role": primary_role, # <- papel principal
            "status": getattr(user, "status", None),
            "mfa": getattr(user, "mfa", None),
        },
    }

def issue_tokens_for(user: User, tenant, scope: str = "") -> dict:
    sub = user.email  # mantém compatibilidade: sub = email
    return {
        "access_token": create_access_token(sub=sub, tenant=tenant.slug, scope=scope),
        "refresh_token": create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope),
        "token_type": "bearer",
    }

async def _extract_credentials_from_request(request: Request) -> tuple[str, str]:
    ct = request.headers.get("content-type", "").lower()
    if ct.startswith("application/json"):
        data = await request.json()
        if isinstance(data, dict):
            email = normalize_email(data.get("username") or data.get("email") or "")
            password = data.get("password") or ""
            if email and password:
                return email, password
    if ct.startswith("application/x-www-form-urlencoded"):
        form = await request.body()
        parsed = parse_qs(form.decode(), keep_blank_values=True)
        email = normalize_email((parsed.get("username", [""])[0]) or "")
        password = (parsed.get("password", [""])[0]) or ""
        if email and password:
            return email, password
    raw = (await request.body()).decode()
    if raw:
        parsed = parse_qs(raw, keep_blank_values=True)
        email = normalize_email((parsed.get("username", [""])[0]) or "")
        password = (parsed.get("password", [""])[0]) or ""
        if email and password:
            return email, password
    raise HTTPException(
        status_code=422,
        detail=[{"loc": ["body"], "msg": "Esperado JSON {username,password} ou form-urlencoded ou raw 'username=...&password=...'", "type": "value_error"}],
    )

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        raise HTTPException(status_code=422, detail=[{"loc": ["token"], "msg": "Field required", "type": "value_error.missing"}])
    return tok

# ... imports e helpers mantidos


def _role_names_for_user(db, user_id: int) -> list[str]:
    # funciona mesmo que o relationship não tenha sido carregado
    try:
        rel = getattr(type(user_roles.c.user_id).table, "name", "user_roles")  # só para evitar lints
    except Exception:
        pass
    rows = db.execute(
        select(Role.name)
        .select_from(user_roles.join(Role, user_roles.c.role_id == Role.id))
        .where(user_roles.c.user_id == user_id)
    ).all()
    return [r[0] for r in rows]

def _user_payload(db, user):
    # tenta via relationship; senão, faz join
    names = [r.name for r in getattr(user, "roles", [])] or _role_names_for_user(db, user.id)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "status": user.status,
        "mfa": bool(user.mfa),
        "roles": names,
        # por compat: primeiro papel também como 'role'
        "role": names[0] if names else None,
    }

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db), tenant = Depends(get_tenant)):
    email, password = await _extract_credentials_from_request(request)
    ensure_password_policy(password)

    user = db.execute(
        select(User).where(User.email == email, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored_hash = _read_password_field(user)
    ok, new_hash = verify_and_maybe_upgrade(password, stored_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user); db.commit(); db.refresh(user)

    tokens = issue_tokens_for(user, tenant)
    payload = decode_refresh(tokens["refresh_token"])
    try:
        if payload and payload.get("jti"):
            row = RefreshToken(jti=payload["jti"])
            if hasattr(row, "tenant_slug"): row.tenant_slug = tenant.slug
            if hasattr(row, "user_email"):  row.user_email  = user.email
            if hasattr(row, "issued_at") and "iat" in payload:
                row.issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            if hasattr(row, "expires_at") and "exp" in payload:
                row.expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            db.add(row); db.commit()
    except Exception:
        pass

    return {
        **tokens,
        "user": _user_payload(db, user),
    }

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
        select(User).where(User.email == email, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored_hash = _read_password_field(user)
    ok, new_hash = verify_and_maybe_upgrade(password, stored_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user); db.commit(); db.refresh(user)

    tokens = issue_tokens_for(user, tenant)
    return {
        **tokens,
        "user": _user_payload(db, user),
    }

@router.post("/refresh")
def refresh(
    token: str | None = Body(default=None, embed=True),
    token_q: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if not payload or payload.get("tenant") != tenant.slug or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    scope = payload.get("scope", "")

    user = db.scalars(
    select(User)
    .where(User.email == email, User.client_id == tenant.id)
    .order_by(User.id.desc())
    .limit(1)
).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found for this tenant")

    new_access  = create_access_token(sub=sub, tenant=tenant.slug, scope=scope)
    new_refresh = create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope)

    try:
        if hasattr(RefreshToken, "jti"):
            old_jti = payload.get("jti")
            if old_jti:
                rt = db.execute(select(RefreshToken).where(RefreshToken.jti == old_jti)).scalar_one_or_none()
                if rt and getattr(rt, "revoked_at", None) is None:
                    rt.revoked_at = datetime.utcnow().replace(tzinfo=timezone.utc)
                    db.add(rt)

            new_payload = decode_refresh(new_refresh)
            if new_payload and new_payload.get("jti"):
                row = RefreshToken(jti=new_payload["jti"])
                if hasattr(row, "tenant_slug"): row.tenant_slug = tenant.slug
                if hasattr(row, "user_email"):  row.user_email  = sub
                if hasattr(row, "issued_at") and "iat" in new_payload:
                    row.issued_at = datetime.fromtimestamp(new_payload["iat"], tz=timezone.utc)
                if hasattr(row, "expires_at") and "exp" in new_payload:
                    row.expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)
                db.add(row)
            db.commit()
    except Exception:
        pass

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user": _user_payload(db, user),
    }

@router.post("/logout")
def logout(
    token: str | None = Body(default=None, embed=True),
    token_q: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if not payload or payload.get("tenant") != tenant.slug or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        if hasattr(RefreshToken, "jti"):
            jti = payload.get("jti")
            if jti:
                rt = db.execute(select(RefreshToken).where(RefreshToken.jti == jti)).scalar_one_or_none()
                if rt and getattr(rt, "revoked_at", None) is None:
                    rt.revoked_at = datetime.utcnow().replace(tzinfo=timezone.utc)
                    db.add(rt)
                    db.commit()
    except Exception:
        pass

    return {"detail": "Logged out"}