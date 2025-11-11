# app/api/deps.py
from __future__ import annotations
from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.user import User
from app.core.tokens import decode_access

# ---------- DB ----------
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _norm(s: str | None) -> str:
    return (s or "").strip().lower()

def get_tenant(request: Request, db: Session = Depends(get_db)) -> Client:
    slug = (
        _norm(request.path_params.get("tenant"))
        or _norm(request.headers.get("X-Tenant"))
        or _norm(request.query_params.get("tenant"))
    )
    if not slug:
        raise HTTPException(status_code=404, detail="Tenant not found")

    cli = db.execute(select(Client).where(func.lower(Client.slug) == slug)).scalar_one_or_none()
    if not cli and slug.isdigit():
        cli = db.execute(select(Client).where(Client.id == int(slug))).scalar_one_or_none()
    if not cli:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return cli

# ---------- Auth ----------
def _get_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth.split(" ", 1)[1].strip()

def _load_user_by_sub(db: Session, tenant: Client, sub: str) -> User | None:
    # teu sub é e-mail (padrão). Aceita id numérico como fallback.
    if sub and sub.isdigit():
        return db.execute(
            select(User).where(
                User.id == int(sub),
                (getattr(User, "client_id") == tenant.id) if hasattr(User, "client_id") else User.client.has(id=tenant.id),
            )
        ).scalar_one_or_none()
    return db.execute(
        select(User).where(
            User.email == sub,
            User.client.has(slug=tenant.slug),
        )
    ).scalar_one_or_none()

def get_current_user_scoped(
    request: Request,
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
) -> User:
    """Valida access token e escopo (tenant), e retorna o usuário do tenant."""
    token = _get_bearer_token(request)
    payload = decode_access(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("tenant") != tenant.slug:
        raise HTTPException(status_code=401, detail="Tenant mismatch")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token (sub)")

    user = _load_user_by_sub(db, tenant, sub)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# alias legado
get_current_user = get_current_user_scoped
