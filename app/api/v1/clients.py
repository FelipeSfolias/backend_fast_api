# app/api/v1/clients.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles, ROLE_ADMIN
from app.models.client import Client as ClientModel
from app.schemas.client import Client as ClientOut, ClientUpdate

router = APIRouter()

@router.get("/_debug/tenants")
def list_tenants(db: Session = Depends(get_db)):
    rows = db.execute(select(ClientModel.id, ClientModel.slug, ClientModel.name)).all()
    return [{"id": r.id, "slug": r.slug, "name": r.name} for r in rows]

@router.get("/", response_model=ClientOut, dependencies=[Depends(require_roles(ROLE_ADMIN))])
def get_my_client(
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    c = db.get(ClientModel, tenant.id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return ClientOut.model_validate(c)

@router.patch("/", response_model=ClientOut, dependencies=[Depends(require_roles(ROLE_ADMIN))])
def update_my_client(
    body: ClientUpdate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    c = db.get(ClientModel, tenant.id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)
    db.add(c); db.commit(); db.refresh(c)
    return ClientOut.model_validate(c)
