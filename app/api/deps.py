# app/api/deps.py
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.db.session import get_db
from app.models.client import Client
from app.core.tokens import decode_access
from app.models.user import User

def _pick_latest(db: Session, stmt):
    try:
        return db.execute(stmt).scalar_one_or_none()
    except MultipleResultsFound:
        return db.scalars(stmt.order_by(User.id.desc()).limit(1)).first()

def get_tenant(tenant: str, db: Session = Depends(get_db)) -> Client:
    stmt = select(Client).where(Client.slug == tenant)
    try:
        row = db.execute(stmt).scalar_one_or_none()
    except MultipleResultsFound:
        row = db.scalars(
            select(Client).where(Client.slug == tenant).order_by(Client.id.desc()).limit(1)
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return row

def get_current_user_scoped(
    token: str = Depends(...),  # seu dependency que extrai o bearer
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
) -> User:
    payload = decode_access(token)
    email = (payload.get("sub") or "").lower()

    stmt = select(User).where(User.client_id == tenant.id, User.email == email)
    try:
        user = db.execute(stmt).scalar_one_or_none()
    except MultipleResultsFound:
        user = db.scalars(stmt.order_by(User.id.desc()).limit(1)).first()

    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado no tenant")
    return user
