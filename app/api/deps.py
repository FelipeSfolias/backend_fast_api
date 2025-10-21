from fastapi import Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import SessionLocal
from app.core.tenancy import resolve_tenant
from app.models.user import User
from app.models.role import Role
from app.core.tokens import decode_access

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  # a URL final inclui /{tenant}/auth/login

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_tenant(tenant: str = Path(...), db: Session = Depends(get_db)):
    return resolve_tenant(db, tenant)

def get_current_user_scoped(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db), tenant=Depends(get_tenant)) -> User:
    payload = decode_access(token)
    if not payload or payload.get("tenant") != tenant.slug:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    email = payload.get("sub")
    user = db.execute(select(User).where(User.email==email, User.client_id==tenant.id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
