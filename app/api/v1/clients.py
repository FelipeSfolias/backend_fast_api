# app/api/v1/clients.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.models.client import Client as ClientModel
from app.schemas.client import Client as ClientOut, ClientBase, ClientUpdate

router = APIRouter()

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

@router.get("/_debug/tenants")
def list_tenants(db: Session = Depends(get_db)):
    rows = db.execute(select(ClientModel.id, ClientModel.slug, ClientModel.name)).all()
    return [{"id": r.id, "slug": r.slug, "name": r.name} for r in rows]

# GET do client do tenant atual
@router.get("/", response_model=ClientOut)
def get_my_client(
    db: Session = Depends(get_db),
    tenant: ClientModel = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    c = db.get(ClientModel, tenant.id)
    if not c:
        raise HTTPException(404, "Client not found")
    return _to_out(c)

# PUT do client do tenant (somente admin)
@router.put("/", response_model=ClientOut, dependencies=[Depends(require_roles("admin"))])
def update_my_client(
    body: ClientUpdate,
    db: Session = Depends(get_db),
    tenant: ClientModel = Depends(get_tenant),
    _user = Depends(get_current_user_scoped),
):
    c = db.get(ClientModel, tenant.id)
    if not c:
        raise HTTPException(404, "Client not found")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)

    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)

# POST sem tenant no path (criar novo client)
@router.post("", response_model=ClientOut)
def create_client(body: ClientBase, db: Session = Depends(get_db)):
    exists = db.execute(select(ClientModel).where(ClientModel.slug == body.slug)).scalar_one_or_none()
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
