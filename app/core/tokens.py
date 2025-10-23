from datetime import datetime, timedelta
from jose import jwt, JWTError
from app.core.config import settings

ALGO = getattr(settings, "ALGORITHM", "HS256")
ACCESS_MIN = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_DAYS = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7))

def create_access_token(*, sub: str, tenant: str, scope: str = "") -> str:
    now = datetime.utcnow()
    payload = {"sub": sub, "tenant": tenant, "scope": scope, "type": "access", "iat": now,
               "exp": now + timedelta(minutes=ACCESS_MIN)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def create_refresh_token(*, sub: str, tenant: str, scope: str = "") -> str:
    now = datetime.utcnow()
    payload = {"sub": sub, "tenant": tenant, "scope": scope, "type": "refresh", "iat": now,
               "exp": now + timedelta(days=REFRESH_DAYS)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def decode_access(token: str):
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
        return data if data.get("type") == "access" else None
    except JWTError:
        return None

def decode_refresh(token: str):
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
        return data if data.get("type") == "refresh" else None
    except JWTError:
        return None

try:
    from .config import settings
except Exception:
    # fallback p/ Render (env vars)
    import os
    class _Settings:
        SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
        ALGORITHM = os.getenv("ALGORITHM", "HS256")
        ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    settings = _Settings()
