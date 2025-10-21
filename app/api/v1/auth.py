from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone

from app.api.deps import get_db, get_tenant
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_refresh
)
from app.schemas.auth import TokenPair, LoginRequest
from app.schemas.user import UserCreate
from app.models.user import User
from app.models.role import Role
from app.models.tokens import RefreshToken
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import select

from app.api.deps import get_db, get_tenant
from app.core.security import create_access_token, decode_refresh
from app.schemas.auth import TokenPair
from app.models.tokens import RefreshToken

router = APIRouter()

# backend/api/v1/auth.py
from datetime import datetime, timedelta

# 1) Tenta usar funções já existentes no seu projeto, se houver
try:
    from core.security import create_access_token as _mk_access  # ou encode_access
except Exception:
    _mk_access = None
try:
    from core.security import create_refresh_token as _mk_refresh  # ou encode_refresh
except Exception:
    _mk_refresh = None

# 2) Se não houver, usa um fallback local com jose
if _mk_access is None or _mk_refresh is None:
    from jose import jwt
    from core.config import settings

    ALGO = getattr(settings, "ALGORITHM", "HS256")
    ACCESS_MIN = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_DAYS = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7))

    def _jwt_encode(payload: dict, minutes: int = 0, days: int = 0) -> str:
        now = datetime.utcnow()
        exp = now + timedelta(minutes=minutes, days=days)
        to_encode = {**payload, "iat": now, "exp": exp}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGO)

    def _mk_access(*, sub: str, tenant: str, scope: str = "") -> str:
        return _jwt_encode({"sub": sub, "tenant": tenant, "scope": scope, "type": "access"},
                           minutes=ACCESS_MIN)

    def _mk_refresh(*, sub: str, tenant: str, scope: str = "") -> str:
        return _jwt_encode({"sub": sub, "tenant": tenant, "scope": scope, "type": "refresh"},
                           days=REFRESH_DAYS)

def issue_tokens_for(user, tenant, scope: str = "") -> dict:
    """Devolve o payload esperado pelo seu Swagger."""
    sub = getattr(user, "email", None) or getattr(user, "username")
    access = _mk_access(sub=sub, tenant=tenant.slug, scope=scope)
    refresh = _mk_refresh(sub=sub, tenant=tenant.slug, scope=scope)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


def _get_token_from_body_or_query(token_body: str | None, token_query: str | None) -> str:
    tok = token_body or token_query
    if not tok:
        # manter 422 quando nenhum for enviado
        raise HTTPException(status_code=422, detail=[{"loc":["token"],"msg":"Field required","type":"value_error.missing"}])
    return tok

# backend/api/v1/auth.py
from app.core.security_password import verify_and_maybe_upgrade
# ...

@router.post("/login")
def login(  # (exemplo com OAuth2PasswordRequestForm)
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    user = db.execute(
        select(User).where(User.email == form_data.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    ok, new_hash = verify_and_maybe_upgrade(form_data.password, user.password_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    if new_hash:
        user.password_hash = new_hash
        db.add(user)
        db.commit()

    # ... gere os tokens e retorne (acesso/refresh)
    return issue_tokens_for(user, tenant)  # exemplo


from pydantic import BaseModel, EmailStr
# ...
class LoginJSON(BaseModel):
    username: EmailStr
    password: str

@router.post("/login-json")
def login_json(payload: LoginJSON, db: Session = Depends(get_db), tenant = Depends(get_tenant)):
    user = db.execute(
        select(User).where(User.email == payload.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    ok, new_hash = verify_and_maybe_upgrade(payload.password, user.password_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="invalid_credentials")

    if new_hash:
        user.password_hash = new_hash
        db.add(user)
        db.commit()

    return issue_tokens_for(user, tenant)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    token: str | None = Body(default=None, embed=True),        # aceita {"token":"..."}
    token_q: str | None = Query(default=None, alias="token"),  # aceita ?token=...
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if not payload or payload.get("tenant") != tenant.slug:
        raise HTTPException(status_code=401, detail="Invalid token")

    access = create_access_token(subject=payload["sub"], tenant_slug=tenant.slug)
    return TokenPair(access_token=access, refresh_token=tok)

@router.post("/logout")
def logout(
    token: str | None = Body(default=None, embed=True),
    token_q: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    tok = _get_token_from_body_or_query(token, token_q)
    payload = decode_refresh(tok)
    if payload and payload.get("tenant") == tenant.slug:
        rt = db.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).scalar_one_or_none()
        if rt:
            rt.revoked_at = datetime.utcnow()
            db.add(rt); db.commit()
    return {"ok": True}

@router.post("/signup")
def signup(body: UserCreate, db: Session = Depends(get_db), tenant = Depends(get_tenant)):
    if db.execute(
        select(User).where(User.email == body.email, User.client_id == tenant.id)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(client_id=tenant.id, name=body.name, email=body.email,
                hashed_password=get_password_hash(body.password))
    db.add(user); db.commit(); db.refresh(user)

    for rname in body.role_names:
        role = db.execute(select(Role).where(Role.name == rname)).scalar_one_or_none()
        if role:
            user.roles.append(role)
    db.commit()
    return {"id": user.id, "email": user.email}
