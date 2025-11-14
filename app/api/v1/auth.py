# app/api/v1/auth.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs
from typing import Tuple, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select
import sqlalchemy as sa

from app.api.deps import get_db, get_tenant
from app.core.tokens import create_access_token, create_refresh_token, decode_refresh
from app.core.security_password import verify_and_maybe_upgrade  # teu módulo original

from app.models.user import User
from app.models.role import Role
from app.models.tokens import RefreshToken  # já existe no teu ZIP

# (opcional) se existir o modelo da tabela associativa, usamos no fallback:
try:
    from app.models.user_role import UserRole  # pode não existir no teu ZIP; tratamos abaixo
except Exception:  # pragma: no cover
    UserRole = None  # type: ignore

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

def _collect_role_names(db: Session, user: User) -> Tuple[List[str], Optional[str]]:
    """
    Retorna (roles_ordenadas, role_principal) do usuário.
    1) tenta via relacionamento user.roles
    2) fallback: consulta via UserRole/roles (ou SQL textual)
    """
    names: Set[str] = set()

    # 1) relacionamento já carregado / lazy
    for r in (getattr(user, "roles", None) or []):
        n = getattr(r, "name", None)
        if n:
            names.add(str(n).lower())

    # 2) fallback por consulta direta
    if not names:
        if UserRole is not None:
            rows = db.execute(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
            ).all()
            for (n,) in rows:
                if n:
                    names.add(str(n).lower())
        else:
            # fallback textual: supõe nomes de tabela "user_roles" e "roles"
            rows = db.execute(
                sa.text(
                    "SELECT r.name FROM roles r "
                    "JOIN user_roles ur ON ur.role_id = r.id "
                    "WHERE ur.user_id = :uid"
                ),
                {"uid": user.id},
            ).all()
            for (n,) in rows:
                if n:
                    names.add(str(n).lower())

    ordered = sorted(names)
    precedence = ["admin", "organizer", "portaria", "aluno"]
    primary = next((p for p in precedence if p in names), None)
    return ordered, primary

def _auth_response(
    user: User,
    tokens: dict,
    roles: List[str],
    primary_role: Optional[str],
):
    """
    Monta a resposta sem alterar o formato dos tokens que você já usa.
    Adiciona os dados de usuário com roles.
    """
    return {
        **tokens,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "roles": roles,            # <<<<<< usado no front
            "role": primary_role,      # <<<<<< papel principal
            "status": getattr(user, "status", None),
            "mfa": getattr(user, "mfa", None),
        },
    }

def issue_tokens_for(user: User, tenant, scope: str = "") -> dict:
    # Mantém seu sub como e-mail (compatibilidade)
    sub = user.email
    return {
        "access_token": create_access_token(sub=sub, tenant=tenant.slug, scope=scope),
        "refresh_token": create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope),
        "token_type": "bearer",
    }

async def _extract_credentials_from_request(request: Request) -> tuple[str, str]:
    # 1) JSON {username,password} ou {email,password}
    if request.headers.get("content-type", "").lower().startswith("application/json"):
        data = await request.json()
        if isinstance(data, dict):
            email = normalize_email(data.get("username") or data.get("email") or "")
            password = data.get("password") or ""
            if email and password:
                return email, password

    # 2) x-www-form-urlencoded (username/password)
    if request.headers.get("content-type", "").lower().startswith("application/x-www-form-urlencoded"):
        form = await request.body()
        parsed = parse_qs(form.decode(), keep_blank_values=True)
        email = normalize_email((parsed.get("username", [""])[0]) or "")
        password = (parsed.get("password", [""])[0]) or ""
        if email and password:
            return email, password

    # 3) texto puro "username=...&password=..."
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

# ---------- endpoints ----------
@router.post("/login")
async def login(
    request: Request,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    email, password = await _extract_credentials_from_request(request)
    ensure_password_policy(password)

    user = db.execute(
        select(User).where(User.email == email, User.client.has(slug=tenant.slug))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored_hash = _read_password_field(user)
    ok, new_hash = verify_and_maybe_upgrade(password, stored_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user); db.commit()

    roles, primary = _collect_role_names(db, user)
    tokens = issue_tokens_for(user, tenant)

    # registra refresh (se o model existir com jti)
    payload = decode_refresh(tokens["refresh_token"])
    try:
        if payload and payload.get("jti"):
            row = RefreshToken(jti=payload["jti"])
            if hasattr(row, "tenant_slug"):
                row.tenant_slug = tenant.slug
            if hasattr(row, "user_email"):
                row.user_email = user.email
            if hasattr(row, "issued_at") and "iat" in payload:
                row.issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            if hasattr(row, "expires_at") and "exp" in payload:
                row.expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            db.add(row); db.commit()
    except Exception:
        pass

    return _auth_response(user, tokens, roles, primary)

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
        select(User).where(User.email == email, User.client.has(slug=tenant.slug))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    field_name, stored_hash = _read_password_field(user)
    ok, new_hash = verify_and_maybe_upgrade(password, stored_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if new_hash:
        setattr(user, field_name, new_hash)
        db.add(user); db.commit()

    roles, primary = _collect_role_names(db, user)
    tokens = issue_tokens_for(user, tenant)
    return _auth_response(user, tokens, roles, primary)

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

    sub = payload.get("sub")  # e-mail (seu sub)
    scope = payload.get("scope", "")

    # rotação: cria novos tokens primeiro (mantém tua semântica)
    new_access = create_access_token(sub=sub, tenant=tenant.slug, scope=scope)
    new_refresh = create_refresh_token(sub=sub, tenant=tenant.slug, scope=scope)

    # rotação (revoga antigo e registra o novo) se houver jti
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
                if hasattr(row, "tenant_slug"):
                    row.tenant_slug = tenant.slug
                if hasattr(row, "user_email"):
                    row.user_email = sub
                if hasattr(row, "issued_at") and "iat" in new_payload:
                    row.issued_at = datetime.fromtimestamp(new_payload["iat"], tz=timezone.utc)
                if hasattr(row, "expires_at") and "exp" in new_payload:
                    row.expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)
                db.add(row)
            db.commit()
    except Exception:
        pass

    # carrega o usuário para devolver as roles também no refresh
    user = db.execute(
        select(User).where(User.email == sub, User.client.has(slug=tenant.slug))
    ).scalar_one_or_none()
    if not user:
        # Mesmo se o user tiver sido removido, devolvemos tokens como antes (fallback)
        return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}

    roles, primary = _collect_role_names(db, user)
    tokens = {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}
    return _auth_response(user, tokens, roles, primary)

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
            rt.revoked_at = datetime.utcnow().replace(tzinfo=timezone.utc)
            db.add(rt)
            db.commit()
    return {"ok": True}
