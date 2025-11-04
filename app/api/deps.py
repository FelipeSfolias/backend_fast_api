from fastapi import Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import SessionLocal
from app.core.tenancy import resolve_tenant
from app.models.user import User
from app.models.role import Role
from app.core.tokens import decode_access
from app.db.session import get_db
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  # a URL final inclui /{tenant}/auth/login

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# app/api/deps.py
from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.client import Client

def _norm_slug(s: str | None) -> str:
    return (s or "").strip().lower()

def get_tenant(
    request: Request,
    tenant: str | None = Path(default=None, description="Tenant slug in path"),
    db: Session = Depends(get_db),
) -> Client:
    # prioridade: path -> header -> query
    slug = _norm_slug(tenant) or _norm_slug(request.headers.get("X-Tenant")) or _norm_slug(request.query_params.get("tenant"))
    if not slug:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # match por slug (case-insensitive)
    stmt = select(Client).where(func.lower(Client.slug) == slug)
    cli = db.execute(stmt).scalar_one_or_none()

    # fallback: se veio número, tenta por id
    if not cli and slug.isdigit():
        cli = db.execute(select(Client).where(Client.id == int(slug))).scalar_one_or_none()

    if not cli:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return cli


def get_current_user_scoped(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db), tenant=Depends(get_tenant)) -> User:
    payload = decode_access(token)
    if not payload or payload.get("tenant") != tenant.slug:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    email = payload.get("sub")
    user = db.execute(select(User).where(User.email==email, User.client_id==tenant.id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
