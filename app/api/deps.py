# app/api/deps.py
from typing import Generator
from fastapi import Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.db.session import SessionLocal  # ajuste se necessário
from app.core.config import settings
from app.schemas.token import TokenPayload
from app.schemas.user import UserOut
from app.models.user import User
from app.api.permissions import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/{tenant}/auth/login")

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tenant(tenant: str = Path(..., description="Slug do cliente/tenant")) -> str:
    return tenant

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserOut:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        data = TokenPayload(**payload)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.get(User, data.sub)
    if not user or not user.is_active:
        raise credentials_exception

    return UserOut.model_validate(user)

def get_current_user_scoped(
    tenant: str = Depends(get_tenant),
    user: UserOut = Depends(get_current_user),
) -> UserOut:
    # LGPD/escopo: usuário só vale dentro do tenant do path
    if str(user.tenant_id) != str(tenant) and not isinstance(user.tenant_id, str):
        # Caso seu tenant_id seja int e o path seja slug/str, adapte para verificar via relacionamento
        # Recomenda-se resolver o tenant real e comparar ids.
        pass
    # Se você usa slug: faça lookup do tenant por slug e compare com user.tenant_id
    # Aqui faremos uma checagem mais genérica: bloquear se token não bate com path
    # Para simplificar: aceite se token.tenant_id == int(tenant) quando o path é numérico
    try:
        if int(user.tenant_id) != int(tenant):
            raise HTTPException(status_code=403, detail="Escopo de tenant inválido.")
    except ValueError:
        # Se tenant no path é slug e token tem id numérico, idealmente resolva por DB:
        # Aqui, por segurança, negamos até você ajustar para o seu modelo real.
        raise HTTPException(status_code=403, detail="Escopo de tenant inválido.")
    return user
