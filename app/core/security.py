from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def _create_token(subject: str, secret: str, minutes: int | None = None, days: int | None = None, token_type: Literal["access","refresh"]="access", extra: dict | None=None):
    now = datetime.now(tz=timezone.utc)
    exp = now + (timedelta(minutes=minutes) if minutes else timedelta(days=days or 1))
    payload = {"sub": subject, "exp": exp, "iat": now, "type": token_type, "jti": str(uuid.uuid4())}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

def create_access_token(subject: str, tenant_slug: str):
    return _create_token(subject, settings.SECRET_KEY, minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES, token_type="access", extra={"tenant": tenant_slug})

def create_refresh_token(subject: str, tenant_slug: str):
    return _create_token(subject, settings.REFRESH_SECRET_KEY, days=settings.REFRESH_TOKEN_EXPIRE_DAYS, token_type="refresh", extra={"tenant": tenant_slug})

def decode_access(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

def decode_refresh(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
