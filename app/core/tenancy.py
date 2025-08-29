from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.client import Client

def resolve_tenant(db: Session, tenant_slug: str) -> Client:
    tenant = db.execute(select(Client).where(Client.slug == tenant_slug)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant
