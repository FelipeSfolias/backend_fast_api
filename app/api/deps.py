from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound

from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.core.tokens import decode_access

# ----------------------------------------------------------------------
# Lê o Bearer do header Authorization (sem usar OAuth2PasswordBearer)
# ----------------------------------------------------------------------
def get_bearer_token(authorization: str = Header(None, alias="Authorization")) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]

# ----------------------------------------------------------------------
# Tenant tolerante a duplicados de slug (pega o de maior id)
# ----------------------------------------------------------------------
def get_tenant(tenant: str, db: Session = Depends(get_db)) -> Client:
    stmt = select(Client).where(Client.slug == tenant)
    try:
        row = db.execute(stmt).scalar_one_or_none()
    except MultipleResultsFound:
        row = db.scalars(stmt.order_by(Client.id.desc()).limit(1)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return row

# ----------------------------------------------------------------------
# Usuário atual do tenant, tolerando e-mails duplicados (pega o mais novo)
# ----------------------------------------------------------------------
def get_current_user_scoped(
    token: str = Depends(get_bearer_token),   # <-- antes estava Depends(...)
    db: Session = Depends(get_db),
    tenant: Client = Depends(get_tenant),
) -> User:
    payload = decode_access(token)
    email = (payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    stmt = select(User).where(User.client_id == tenant.id, User.email == email)
    try:
        user = db.execute(stmt).scalar_one_or_none()
    except MultipleResultsFound:
        user = db.scalars(stmt.order_by(User.id.desc()).limit(1)).first()

    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado no tenant")
    return user
