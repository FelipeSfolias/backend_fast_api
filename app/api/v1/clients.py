from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.schemas.client import Client as ClientOut, ClientUpdate
from app.models.client import Client as ClientModel

router = APIRouter()

@router.get("/", response_model=ClientOut)
def get_my_client(db: Session = Depends(get_db), tenant = Depends(get_tenant), _=Depends(get_current_user_scoped)):
    c: ClientModel = tenant
    return ClientOut(
        id=c.id, name=c.name, cnpj=c.cnpj, slug=c.slug, logo_url=c.logo_url,
        contact_email=c.contact_email, contact_phone=c.contact_phone,
        certificate_template_html=c.certificate_template_html,
        default_min_presence_pct=c.default_min_presence_pct,
        lgpd_policy_text=c.lgpd_policy_text, config_json=c.config_json
    )

@router.put("/", response_model=ClientOut, dependencies=[Depends(require_roles("admin"))])
def update_my_client(body: ClientUpdate, db: Session = Depends(get_db), tenant = Depends(get_tenant), _=Depends(get_current_user_scoped)):
    c: ClientModel = db.get(ClientModel, tenant.id)
    if not c: raise HTTPException(404)
    data = body.model_dump(exclude_unset=True)
    for k,v in data.items():
        setattr(c, k, v)
    db.add(c); db.commit(); db.refresh(c)
    return ClientOut(
        id=c.id, name=c.name, cnpj=c.cnpj, slug=c.slug, logo_url=c.logo_url,
        contact_email=c.contact_email, contact_phone=c.contact_phone,
        certificate_template_html=c.certificate_template_html,
        default_min_presence_pct=c.default_min_presence_pct,
        lgpd_policy_text=c.lgpd_policy_text, config_json=c.config_json
    )
