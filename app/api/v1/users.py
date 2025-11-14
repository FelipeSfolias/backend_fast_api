# app/api/v1/users.py
from __future__ import annotations
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path
from sqlalchemy import select, and_, delete, insert
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.models.user import User
from app.models.role import Role
from app.models.student import Student
from app.models.user_role import user_roles  # <<< usamos a tabela de associação
from app.schemas.user import UserCreate, UserUpdate, UserOut, RoleName

# hashing compatível com o projeto
try:
    from app.core.security_password import hash_password  # teu helper principal
except Exception:  # fallback
    from app.core.security import get_password_hash as hash_password  # se existir

router = APIRouter()

# --------------------------------------------------------------------------- #
# Helpers de roles SEM relationship (funcionam mesmo que User.roles não exista)
# --------------------------------------------------------------------------- #

_ALLOWED = {"admin", "organizer", "portaria", "aluno"}

def _role_ids_for_names(db: Session, names: list[str]) -> dict[str, int]:
    """Garante que as roles existam e retorna {name_lower: id}."""
    want = [n.strip().lower() for n in names if n]
    if not want:
        return {}
    # busca existentes
    rows = db.execute(select(Role.id, Role.name).where(Role.name.in_(want))).all()
    have = {n.lower(): i for i, n in rows}
    # cria faltantes
    missing = [n for n in want if n not in have]
    for n in missing:
        r = Role(name=n)
        db.add(r)
        db.flush()         # pega r.id sem commit
        have[n] = r.id
    return have

def _get_role_names(db: Session, user_id: int) -> list[str]:
    rows = db.execute(
        select(Role.name)
        .select_from(user_roles.join(Role, user_roles.c.role_id == Role.id))
        .where(user_roles.c.user_id == user_id)
    ).all()
    return sorted({r[0] for r in rows})

def _assign_roles(db: Session, user_id: int, names: list[str]) -> None:
    lower = [n.strip().lower() for n in names if n]
    invalid = [n for n in lower if n not in _ALLOWED]
    if invalid:
        raise HTTPException(422, detail=f"Roles inválidas: {invalid}")
    name_to_id = _role_ids_for_names(db, lower)
    # zera atuais
    db.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
    # insere novas
    if name_to_id:
        db.execute(
            insert(user_roles),
            [{"user_id": user_id, "role_id": name_to_id[n]} for n in lower],
        )

def _set_password_on_model(u: User, hashed: str):
    # compatível com diferentes nomes de campo
    if hasattr(u, "hashed_password"):
        u.hashed_password = hashed
    elif hasattr(u, "password_hash"):
        u.password_hash = hashed
    elif hasattr(u, "password"):
        u.password = hashed
    else:
        raise HTTPException(500, "Modelo User sem campo de senha")

def _ensure_unique_email(db: Session, client_id: int, email: str, exclude_user_id: Optional[int] = None):
    q = select(User).where(and_(User.client_id == client_id, User.email == email))
    u = db.scalar(q)
    if u and (exclude_user_id is None or u.id != exclude_user_id):
        raise HTTPException(409, detail="E-mail já utilizado neste tenant.")

def _to_out(db: Session, u: User) -> UserOut:
    return UserOut(
        id=u.id,
        name=u.name,
        email=u.email,
        status=getattr(u, "status", None),
        mfa=bool(getattr(u, "mfa", False)),
        roles=_get_role_names(db, u.id),
    )

# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@router.post("/", response_model=UserOut, status_code=201,
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
        email=body.email.strip().lower(),
        status=body.status or "active",
        mfa=bool(body.mfa),
    )
    _set_password_on_model(u, hash_password(body.password))
    db.add(u)
    db.flush()  # garante u.id

    # atribui roles via tabela de junção
    if body.roles:
        _assign_roles(db, u.id, list(body.roles))

    db.commit()
    db.refresh(u)
    return _to_out(db, u)

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
    users = db.scalars(stmt).all()

    out: list[UserOut] = []
    for u in users:
        u_out = _to_out(db, u)
        if role and role not in u_out.roles:
            continue
        out.append(u_out)
    return out

@router.get("/{user_id}", response_model=UserOut,
            dependencies=[Depends(require_roles("admin","organizer","portaria"))])
def get_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    u = db.scalar(select(User).where(and_(User.id == user_id, User.client_id == tenant.id)))
    if not u:
        raise HTTPException(404, "User not found")
    return _to_out(db, u)

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

    if body.email is not None:
        _ensure_unique_email(db, tenant.id, body.email, exclude_user_id=u.id)
        u.email = body.email.strip().lower()
    if body.name is not None:
        u.name = body.name
    if body.status is not None:
        u.status = body.status
    if body.mfa is not None:
        u.mfa = body.mfa
    if body.password:
        _set_password_on_model(u, hash_password(body.password))
    if body.roles is not None:
        _assign_roles(db, u.id, list(body.roles))

    db.add(u); db.commit(); db.refresh(u)
    return _to_out(db, u)

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
    """Garante que todo Student do tenant tenha papel 'aluno'."""
    students = db.scalars(select(Student).where(Student.client_id == tenant.id)).all()
    created = 0
    updated = 0

    for s in students:
        u = db.scalar(select(User).where(and_(User.client_id == tenant.id, User.email == s.email)))
        if u:
            roles = set(_get_role_names(db, u.id))
            if "aluno" not in roles:
                _assign_roles(db, u.id, ["aluno"])
                updated += 1
        elif create_missing and s.email:
            pwd = secrets.token_urlsafe(temp_password_len)
            u = User(
                client_id=tenant.id,
                name=s.name,
                email=s.email.strip().lower(),
                status="active",
            )
            _set_password_on_model(u, hash_password(pwd))
            db.add(u); db.flush()
            _assign_roles(db, u.id, ["aluno"])
            created += 1

    db.commit()
    return {"synced": True, "created_users": created, "updated_users": updated}
