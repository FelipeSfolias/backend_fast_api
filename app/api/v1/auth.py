# app/api/v1/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.security import verify_password, get_password_hash, create_access_token
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.models.user import User
from app.api.permissions import Role, require_roles

router = APIRouter()

@router.post("/login", response_model=Token)
def login_for_access_token(
    tenant: str = Depends(get_tenant),
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Atenção: tenant do path deve ser aplicado no filtro
    user = db.query(User).filter(
        User.email == form_data.username,
        User.tenant_id == int(tenant)  # ajuste conforme seu tenant
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password) or not user.is_active:
        raise HTTPException(status_code=401, detail="E-mail/senha inválidos ou usuário inativo.")

    access_token = create_access_token(user=UserOut.model_validate(user), expires_delta=timedelta(minutes=60))
    return Token(access_token=access_token)

@router.post("/users", response_model=UserOut, dependencies=[Depends(require_roles([Role.ADMIN_CLIENTE]))])
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    # Apenas Admin do Cliente cria usuários (no mesmo tenant)
    exists = db.query(User).filter(User.email == data.email, User.tenant_id == data.tenant_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado neste cliente.")
    obj = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        is_active=data.is_active,
        role=int(data.role),
        tenant_id=data.tenant_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/me", response_model=UserOut)
def read_me(user: UserOut = Depends(get_current_user_scoped)):
    return user

@router.patch("/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_roles([Role.ADMIN_CLIENTE]))])
def update_user(
    user_id: int,
    updates: UserUpdate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    if updates.full_name is not None:
        user.full_name = updates.full_name
    if updates.is_active is not None:
        user.is_active = updates.is_active
    if updates.role is not None:
        user.role = int(updates.role)
    db.commit()
    db.refresh(user)
    return user
