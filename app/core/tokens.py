# app/core/tokens.py
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt, JWTError  # python-jose
from app.core.config import settings

# Ajuste os nomes conforme seu settings
# settings.SECRET_KEY
# settings.ACCESS_TOKEN_EXPIRE_MINUTES
# settings.REFRESH_TOKEN_EXPIRE_DAYS
# settings.JWT_ALGORITHM

ALGO = getattr(settings, "JWT_ALGORITHM", "HS256")

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _exp(minutes: int = 15) -> datetime:
    return _now() + timedelta(minutes=minutes)

def _exp_days(days: int) -> datetime:
    return _now() + timedelta(days=days)

def create_access_token(*, sub: str, tenant: str, scope: str = "") -> str:
    """
    Gera JWT de acesso com:
      - type=access
      - sub=<identificador do usuário> (email ou id, conforme seu uso)
      - tenant=<slug>
      - scope=<opcional>
    """
    expire_min = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    payload: Dict[str, Any] = {
        "type": "access",
        "sub": sub,
        "tenant": tenant,
        "scope": scope,
        "iat": int(_now().timestamp()),
        "exp": int(_exp(expire_min).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def create_refresh_token(*, sub: str, tenant: str, scope: str = "") -> str:
    """
    Gera JWT de refresh com:
      - type=refresh
      - jti=<uuid4>
      - exp longo (ex.: 30 dias)
    """
    expire_days = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 30))
    payload: Dict[str, Any] = {
        "type": "refresh",
        "sub": sub,
        "tenant": tenant,
        "scope": scope,
        "jti": str(uuid.uuid4()),
        "iat": int(_now().timestamp()),
        "exp": int(_exp_days(expire_days).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def decode_refresh(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica o JWT e retorna o payload SOMENTE se:
      - assinatura/exp ok
      - type == 'refresh'
    Senão, retorna None.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "refresh":
        return None
    # sub, tenant e jti são esperados
    if not payload.get("sub") or not payload.get("tenant") or not payload.get("jti"):
        return None
    return payload
