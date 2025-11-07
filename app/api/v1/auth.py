# app/api/v1/auth.py
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Body, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select
import sqlalchemy as sa
from jose import jwt

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.tokens import create_access_token, decode_refresh  # usamos só o decode no /refresh
from app.core.security import verify_and_maybe_upgrade, hash_password
from app.core.rbac import require_roles, ROLE_ADMIN
from app.core.config import settings

from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, User as UserSchema

router = APIRouter()

def _utcnow():
    return datetime.now(timezone.utc)

# ---------- SQL helpers (Core) ----------
_INS_REFRESH = sa.text("""
    INSERT INTO refresh_tokens (jti, user_email, tenant_slug, expires_at, revoked_at)
    VALUES (:jti, :user_email, :tenant_slug, :expires_at, NULL)
    ON CONFLICT (jti) DO NOTHING
""").bindparams(
    sa.bindparam("jti", type_=sa.String(64)),
    sa.bindparam("user_email", type_=sa.String(160)),
    sa.bindparam("tenant_slug", type_=sa.String(64)),
    sa.bindparam("expires_at", type_=sa.DateTime(timezone=True)),
)

_SEL_REFRESH_BY_JTI = sa.text("""
    SELECT jti, user_email, tenant_slug, expires_at, revoked_at
    FROM refresh_tokens
    WHERE jti = :jti
""").bindparams(
    sa.bindparam("jti", type_=sa.String(64))
)

_UPD_REVOKE_BY_JTI = sa.text("""
    UPDATE refresh_tokens
    SET revoked_at = :now
    WHERE jti = :jti
      AND revoked_at IS NULL
      AND tenant_slug = :tenant_slug
""").bindparams(
    sa.bindparam("now", type_=sa.DateTime(timezone=True)),
    sa.bindparam("jti", type_=sa.String(64)),
    sa.bindparam("tenant_slug", type_=sa.String(64)),
)

_UPD_REVOKE_ALL = sa.text("""
    UPDATE refresh_tokens
    SET revoked_at = :now
    WHERE user_email = :email
      AND tenant_slug = :tenant_slug
      AND revoked_at IS NULL
""").bindparams(
    sa.bindparam("now", type_=sa.DateTime(timezone=True)),
    sa.bindparam("email", type_=sa.String(160)),
    sa.bindparam("tenant_slug", type_=sa.String(64)),
)

# ---------- endpoints ----------
@router.post("/login")
def login_for_access_token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    user = db.execute(
        select(User).where(User.email == form.username, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    ok, new_hash = verify_and_maybe_upgrade(form.password, user.hashed_password)
    if not ok:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if new_hash:
        user.hashed_password = new_hash
        db.add(user); db.commit()

    tenant_claim = tenant.slug or str(tenant.id)

    # access token normal
    access = create_access_token(sub=user.id, tenant=tenant_claim)

    # ----- refresh token sem "auto-decode": montamos payload e assinamos -----
    now = _utcnow()
    jti = uuid.uuid4().hex
    exp_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload_refresh = {
        "jti": jti,
        "type": "refresh",
        "sub": int(user.id),
        "tenant": str(tenant_claim),
        "exp": int(exp_at.timestamp()),
        "iat": int(now.timestamp()),
    }
    refresh = jwt.encode(payload_refresh, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)

    # Persistimos usando os MESMOS valores (sem decodificar)
    db.execute(
        _INS_REFRESH,
        {
            "jti": jti,
            "user_email": user.email,
            "tenant_slug": tenant_claim,
            "expires_at": exp_at,
        },
    )
    db.commit()

    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/refresh")
def refresh_access_token(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    payload = decode_refresh(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Refresh inválido ou expirado")

    t_claim = str(payload.get("tenant"))
    if t_claim not in {str(tenant.id), tenant.slug}:
        raise HTTPException(status_code=401, detail="Tenant mismatch")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Refresh inválido")

    row = db.execute(_SEL_REFRESH_BY_JTI, {"jti": jti}).mappings().first()
    if not row:
        raise HTTPException(status_code=401, detail="Refresh não encontrado")
    if row["tenant_slug"] != t_claim:
        raise HTTPException(status_code=401, detail="Tenant mismatch")
    if row["revoked_at"] is not None:
        raise HTTPException(status_code=401, detail="Refresh revogado")
    if row["expires_at"] <= _utcnow():
        raise HTTPException(status_code=401, detail="Refresh expirado")

    user = db.execute(
        select(User).where(User.id == int(payload["sub"]), User.client_id == tenant.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token(sub=user.id, tenant=t_claim)
    return {"access_token": access, "token_type": "bearer"}

@router.post("/logout")
def logout(
    token: str = Body(..., embed=True),  # envie o REFRESH token aqui
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),  # exige estar autenticado (access)
):
    payload = decode_refresh(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Refresh inválido")
    t_claim = str(payload.get("tenant"))
    if t_claim not in {str(tenant.id), tenant.slug}:
        raise HTTPException(status_code=401, detail="Tenant mismatch")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=400, detail="Refresh inválido")

    res = db.execute(
        _UPD_REVOKE_BY_JTI,
        {"now": _utcnow(), "jti": jti, "tenant_slug": t_claim},
    )
    db.commit()
    return {"revoked": bool(res.rowcount)}

@router.post("/logout-all")
def logout_all(
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    user = Depends(get_current_user_scoped),
):
    t_claim = tenant.slug or str(tenant.id)
    res = db.execute(
        _UPD_REVOKE_ALL,
        {"now": _utcnow(), "email": user.email, "tenant_slug": t_claim},
    )
    db.commit()
    return {"revoked_count": int(res.rowcount or 0)}

@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(ROLE_ADMIN))])
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    exists = db.execute(
        select(User).where(User.email == body.email, User.client_id == tenant.id)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado neste cliente")

    user = User(
        client_id=tenant.id,
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        status=body.status or "active",
    )
    db.add(user); db.flush()

    if body.role_names:
        roles = db.scalars(select(Role).where(Role.name.in_(body.role_names))).all()
        for r in roles:
            user.roles.append(r)

    db.commit(); db.refresh(user)
    return UserSchema(
        id=user.id,
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        status=user.status,
        roles=[r.name for r in user.roles],
    )

@router.get("/me", response_model=UserSchema)
def read_me(user = Depends(get_current_user_scoped)):
    return UserSchema(
        id=user.id,
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        status=user.status,
        roles=[r.name for r in user.roles or []],
    )
