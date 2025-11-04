# app/api/deps.py
from __future__ import annotations
from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

# pega a SessionLocal do seu módulo de sessão
from app.db.session import SessionLocal
from app.models.client import Client


# --- DB dependency -------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Tenant dependency (flexível) ---------------------------------
def _norm(s: str | None) -> str:
    return (s or "").strip().lower()

def get_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Client:
    """
    Resolve o tenant em 3 fontes, nessa ordem:
    1) path param: request.path_params["tenant"] (se a rota tiver /{tenant}/...)
    2) header:     X-Tenant: <slug>
    3) query:      ?tenant=<slug>
    Faz busca case-insensitive por slug; se for numérico, tenta por id.
    """
    slug = (
        _norm(request.path_params.get("tenant"))
        or _norm(request.headers.get("X-Tenant"))
        or _norm(request.query_params.get("tenant"))
    )
    if not slug:
        raise HTTPException(status_code=404, detail="Tenant not found")

    cli = db.execute(
        select(Client).where(func.lower(Client.slug) == slug)
    ).scalar_one_or_none()

    if not cli and slug.isdigit():
        cli = db.execute(
            select(Client).where(Client.id == int(slug))
        ).scalar_one_or_none()

    if not cli:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return cli
