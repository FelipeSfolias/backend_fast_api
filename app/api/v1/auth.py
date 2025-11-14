# app/api/v1/auth.py
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant
from app.core.tokens import create_access_token, create_refresh_token, decode_refresh
from app.core.security_password import verify_and_maybe_upgrade

from app.models.user import User
from app.models.role import Role
from app.models.user_role import user_roles  # tabela de associação

# ---- RefreshToken é opcional: se o model não existir, os endpoints continuam
RefreshToken = None  # type: ignore
try:
    from app.models.tokens import RefreshToken as _RT  # seu ZIP original
    RefreshToken = _RT  # type: ignore
except Exception:
    try:
        from app.models.refresh_token import RefreshToken as _RT  # variações
        RefreshToken = _RT  # type: ignore
    except Exception:
        RefreshToken = None

router = APIRouter()

# ---------- helpers ----------
def normalize_email(s: str) -> str:
    return (s or "").strip().lower()

def ensure_password_policy(password: str):
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Senha fora do padrão (8–128).")

def _read_password_field(user: User):
    for name in ["password_hash", "hashed_password", "password"]:
        if hasattr(user, name):
            return name, getattr(user, name)
    raise HTTPException(status_code=500, detail="Modelo de usuário sem campo de senha")

async def _extract_credentials_from_request(request: Request) -> tuple[str, str]:
    """Aceita JSON, x-www-form-urlencoded e raw 'username=...&password=...'."""
    ct = (request.headers.get("content-type") or "").lower()

    if ct.startswith("application/json"):
        data = await request.json()
        if isinstance(data, dict):
            em = normalize_email(data.get("username") or data.get("email") or "")
            pw = data.get("password") or ""
            if em and pw:
                return em, pw

    if ct.startswith("application/x-www-form-urlencoded"):
        form = await request.body()
        parsed = parse_qs(form.decode(), keep_blank_values=True)
        em = normalize_email((parsed.get("username", [""])[0]) or "")
        pw = (parsed.get("password", [""])[0]) or ""
        if em and pw:
            return em, pw

    raw = (await request.body()).decode()
    if raw:
        parsed = parse_qs(raw, keep_blank_values=True)
        em = normalize_email((parsed.get("username", [""])[0]) or "")
        pw = (parsed.get("password", [""])[0]) or ""
        if em and pw:
            return em, pw

    raise HTTPException(
        status_code=422,
        detail=[{"loc": ["body"], "msg": "Esperado JSON {username,password} ou form-urlencoded ou raw 'username=...&password=...'", "type": "value_error"}],
    )

def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        raise HTTPException(status_code=422, detail=[{"loc": ["token"], "msg": "Field required", "type": "value_error.missing"}])
    return tok

def _role_names_for_user(db: Session, user_id: int) -> list[str]:
    rows = db.execute(
        select(Role.name)
        .select_from(user_roles.join(Role, user_roles.c.role_id == Role.id))
        .where(user_roles.c.user_id == user_id)
    ).all()
    return [r[0] for r in rows]

def _user_payload(db: Session, user: User) -> dict:
    names = [r.name for r in getattr(user, "roles", [])] or _role_names_for_user(db, user.id)
    # prioridade de papel opcional: admin > organizer > portaria > aluno
    priority = ["admin", "organizer", "portaria", "aluno"]
    primary = next((p for p in priority if p in names), (names[0] if names else None))
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "status": getattr(user, "status", None),
        "mfa": bool(getattr(user, "mfa", False)),
        "roles": names,
        "role": primary,
    }

def _get_user_by_email(db: Session, tenant_id: int, email_addr: str) -> User | None:
    """Busca tolerante a duplicados: em caso de múltiplos, pega o mais novo."""
    stmt = select(User).where(User.client_id == tenant_id, User.email == email_addr)
    try:
        return db.execute(stmt).scalar_one_or_none()
    except MultipleResultsFound:
        return db.scalars(
            select(User)
            .where(User.client_id == tenant_id, User.email == email_addr)
            .order_by(User.id.desc())
            .limit(1)
        ).first()

def _issue_tokens_for(user: User, tenant, scope: str = "") -> dict:
    sub = user.email  # compat: sub = e-mail
    return {
        "access_token": create_access_token(sub=sub, tenant=tenant.slug, scope=scope),
        "refresh_token": create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope),
        "token_type": "bearer",
    }

# ---------- endpoints ----------
@router.post("/login")
async def login(
    request: Request,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email_addr, password = await _extract_credentials_from_request(request)
    ensure_password_policy(password)

    user = _get_user_by_email(db, tenant.id, email_addr)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored_hash = _read_password_field(user)
    ok, new_hash = verify_and_maybe_upgrade(password, stored_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user)
        db.commit()
        db.refresh(user)

    tokens = _issue_tokens_for(user, tenant)

    # registra refresh (se existir o model)
    payload = decode_refresh(tokens["refresh_token"])
    try:
        if RefreshToken is not None and payload and payload.get("jti"):
            row = RefreshToken(jti=payload["jti"])
            if hasattr(row, "tenant_slug"):
                row.tenant_slug = tenant.slug
            if hasattr(row, "user_email"):
                row.user_email = user.email
            if hasattr(row, "issued_at") and "iat" in payload:
                row.issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            if hasattr(row, "expires_at") and "exp" in payload:
                row.expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            db.add(row)
            db.commit()
    except Exception:
        # não derruba o login por erro de logging de refresh
        pass

    return {**tokens, "user": _user_payload(db, user)}

@router.post("/token")
def login_oauth2_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email_addr = normalize_email(form.username)
    password = form.password or ""
    if not email_addr or not password:
        raise HTTPException(status_code=400, detail="E-mail e senha são obrigatórios.")
    ensure_password_policy(password)

    user = _get_user_by_email(db, tenant.id, email_addr)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored_hash = _read_password_field(user)
    ok, new_hash = verify_and_maybe_upgrade(password, stored_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user)
        db.commit()
        db.refresh(user)

    tokens = _issue_tokens_for(user, tenant)
    return {**tokens, "user": _user_payload(db, user)}

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

    sub_email = normalize_email(payload.get("sub") or "")
    scope = payload.get("scope", "")

    user = _get_user_by_email(db, tenant.id, sub_email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found for this tenant")

    new_access = create_access_token(sub=sub_email, tenant=tenant.slug, scope=scope)
    new_refresh = create_refresh_token(sub=sub_email, tenant=tenant.slug, scope=scope)

    # rotação: revoga antigo e registra o novo, se possível
    try:
        if RefreshToken is not None and hasattr(RefreshToken, "jti"):
            old_jti = payload.get("jti")
            if old_jti:
                rt = db.execute(select(RefreshToken).where(RefreshToken.jti == old_jti)).scalar_one_or_none()
                if rt and getattr(rt, "revoked_at", None) is None:
                    rt.revoked_at = datetime.utcnow().replace(tzinfo=timezone.utc)
                    db.add(rt)

            new_payload = decode_refresh(new_refresh)
            if new_payload and new_payload.get("jti"):
                row = RefreshToken(jti=new_payload["jti"])
                if hasattr(row, "tenant_slug"):
                    row.tenant_slug = tenant.slug
                if hasattr(row, "user_email"):
                    row.user_email = sub_email
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
        if RefreshToken is not None and hasattr(RefreshToken, "jti"):
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
