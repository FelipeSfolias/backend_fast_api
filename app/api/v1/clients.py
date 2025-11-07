# app/api/v1/clients.py
from __future__ import annotations

import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.models.client import Client as ClientModel
from app.schemas.client import (
    Client as ClientOut,
    ClientBase,
    ClientUpdate,
)

# Dois routers para evitar confusão de prefixo
tenant_router = APIRouter()
public_router = APIRouter()

# -------- helpers --------
def _to_out(c: ClientModel) -> ClientOut:
    return ClientOut(
        id=c.id,
        name=c.name,
        cnpj=c.cnpj,
        slug=c.slug,
        logo_url=c.logo_url,
        contact_email=c.contact_email,
        contact_phone=c.contact_phone,
        certificate_template_html=c.certificate_template_html,
        default_min_presence_pct=c.default_min_presence_pct,
        lgpd_policy_text=c.lgpd_policy_text,
        config_json=c.config_json,
    )

_slug_re = re.compile(r"[^a-z0-9\-]")

def _normalize_slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace(" ", "-")
    s = _slug_re.sub("", s)
    return s

# -------- tenant-scoped --------

@tenant_router.get("", response_model=ClientOut)
@tenant_router.get("/", response_model=ClientOut)
def get_my_client(
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    c = db.get(ClientModel, tenant.id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return _to_out(c)

@tenant_router.put("", response_model=ClientOut, dependencies=[Depends(require_roles("admin"))])
@tenant_router.put("/", response_model=ClientOut, dependencies=[Depends(require_roles("admin"))])
def update_my_client(
    body: ClientUpdate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    c = db.get(ClientModel, tenant.id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)

    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)

# -------- público (provisionamento) --------

@public_router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
@public_router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientBase,
    db: Session = Depends(get_db),
):
    # normaliza slug (minúsculo, sem espaços e sem chars inválidos)
    body.slug = _normalize_slug(body.slug)

    # slug único
    exists = db.execute(
        select(ClientModel).where(ClientModel.slug == body.slug)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Slug já existe")

    c = ClientModel(
        name=body.name,
        cnpj=body.cnpj,
        slug=body.slug,
        logo_url=body.logo_url,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        certificate_template_html=body.certificate_template_html,
        default_min_presence_pct=body.default_min_presence_pct,
        lgpd_policy_text=body.lgpd_policy_text,
        config_json=body.config_json or {},
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)

# ------- debug opcional -------
@public_router.get("/_debug/tenants")
def list_tenants(db: Session = Depends(get_db)):
    rows = db.execute(select(ClientModel.id, ClientModel.slug, ClientModel.name)).all()
    return [{"id": r.id, "slug": r.slug, "name": r.name} for r in rows]
