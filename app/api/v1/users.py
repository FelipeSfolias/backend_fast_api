# app/api/v1/users.py
from __future__ import annotations
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.models.user import User
from app.models.role import Role
from app.models.student import Student
from app.schemas.user import UserCreate, UserUpdate, UserOut, RoleName

# hashing compatível com seu projeto
try:
    from app.core.security_password import hash_password  # seu helper
except Exception:  # fallback
    from app.core.security import get_password_hash as hash_password  # se existir

router = APIRouter()

# utils -----------------------------------------------------------------------

def _role_names(u: User) -> list[str]:
    names: list[str] = []
    for r in (u.roles or []):
        n = getattr(r, "name", None)
        if n:
            names.append(str(n))
    return sorted(set(names))

def _to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        name=u.name,
        email=u.email,
        status=u.status,
        mfa=u.mfa,
        roles=_role_names(u),
    )

def _get_or_create_roles(db: Session, names: list[RoleName]) -> list[Role]:
    """Busca as roles; se não existirem (seed faltando), cria na hora."""
    out: list[Role] = []
    lower = [n.lower() for n in names]
    if not lower:
        return out
    rows = db.scalars(select(Role).where(Role.name.in_(lower))).all()
    found = {r.name for r in rows}
    out.extend(rows)
    for missing in (set(lower) - found):
        r = Role(name=missing)
        db.add(r)
        out.append(r)
    return out

def _ensure_unique_email(db: Session, client_id: int, email: str, exclude_user_id: Optional[int]=None):
    q = select(User).where(and_(User.client_id == client_id, User.email == email))
    u = db.scalar(q)
    if u and (exclude_user_id is None or u.id != exclude_user_id):
        raise HTTPException(409, detail="E-mail já utilizado neste tenant.")

# endpoints -------------------------------------------------------------------

@router.post("/", response_model=UserOut,
             dependencies=[Depends(require_roles("admin"))])
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    _ensure_unique_email(db, tenant.id, body.email)
    u = User(
        client_id=tenant.id,
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        status=body.status or "active",
        mfa=body.mfa,
    )
    u.roles = _get_or_create_roles(db, body.roles or [])
    db.add(u); db.commit(); db.refresh(u)
    return _to_out(u)

@router.get("/", response_model=List[UserOut],
            dependencies=[Depends(require_roles("admin","organizer","portaria"))])
def list_users(
    role: Optional[RoleName] = Query(None),
    q: Optional[str] = Query(None, description="filtra por nome/email"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    stmt = select(User).where(User.client_id == tenant.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where((User.name.ilike(like)) | (User.email.ilike(like)))
    rows = db.scalars(stmt).all()
    outs = []
    for u in rows:
        rolenames = _role_names(u)
        if role and role not in rolenames:
            continue
        outs.append(_to_out(u))
    return outs

@router.get("/{user_id}", response_model=UserOut,
            dependencies=[Depends(require_roles("admin","organizer","portaria"))])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    u = db.scalar(select(User).where(and_(User.id == user_id, User.client_id == tenant.id)))
    if not u:
        raise HTTPException(404, "User not found")
    return _to_out(u)

@router.patch("/{user_id}", response_model=UserOut,
              dependencies=[Depends(require_roles("admin"))])
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    u = db.scalar(select(User).where(and_(User.id == user_id, User.client_id == tenant.id)))
    if not u:
        raise HTTPException(404, "User not found")

    if body.email is not None:  # se você quiser permitir troca de e-mail
        _ensure_unique_email(db, tenant.id, body.email, exclude_user_id=u.id)

    if body.name is not None:
        u.name = body.name
    if body.status is not None:
        u.status = body.status
    if body.mfa is not None:
        u.mfa = body.mfa
    if body.password:
        u.hashed_password = hash_password(body.password)
    if body.roles is not None:
        u.roles = _get_or_create_roles(db, body.roles)

    db.add(u); db.commit(); db.refresh(u)
    return _to_out(u)

@router.delete("/{user_id}", status_code=204,
               dependencies=[Depends(require_roles("admin"))])
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    u = db.scalar(select(User).where(and_(User.id == user_id, User.client_id == tenant.id)))
    if not u:
        raise HTTPException(404, "User not found")
    u.status = "inactive"
    db.add(u); db.commit()
    return

@router.post("/sync-students", dependencies=[Depends(require_roles("admin"))])
def sync_students_as_aluno(
    create_missing: bool = Query(False, description="cria User p/ Student sem usuário?"),
    temp_password_len: int = Query(10, ge=6, le=64),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    """
    Garante que todo Student do tenant tenha papel 'aluno':
     - se já há User com mesmo e-mail: anexa role 'aluno'
     - se não há User e create_missing=true: cria User com senha temporária
    """
    alunos_role = _get_or_create_roles(db, ["aluno"])[0]
    students = db.scalars(select(Student).where(Student.client_id == tenant.id)).all()

    created = 0
    updated = 0
    for s in students:
        u = db.scalar(select(User).where(and_(User.client_id == tenant.id, User.email == s.email)))
        if u:
            names = _role_names(u)
            if "aluno" not in names:
                u.roles = list(u.roles) + [alunos_role]
                db.add(u); updated += 1
        elif create_missing and s.email:
            pwd = secrets.token_urlsafe(temp_password_len)
            u = User(
                client_id=tenant.id,
                name=s.name,
                email=s.email,
                hashed_password=hash_password(pwd),
                status="active",
            )
            u.roles = [alunos_role]
            db.add(u); created += 1
    db.commit()
    return {"synced": True, "created_users": created, "updated_users": updated}
