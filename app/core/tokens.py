# app/core/tokens.py
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt, JWTError
from app.core.config import settings

# Compatível com teu Settings: usa JWT_ALGORITHM se existir; senão "HS256"
ALGO = getattr(settings, "JWT_ALGORITHM", "HS256")

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _exp(minutes: int = 15) -> datetime:
    return _now() + timedelta(minutes=minutes)

def _exp_days(days: int) -> datetime:
    return _now() + timedelta(days=days)

def create_access_token(*, sub: str, tenant: str, scope: str = "") -> str:
    """Access token curto (minutos), assinado com SECRET_KEY."""
    expire_min = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    payload: Dict[str, Any] = {
        "type": "access",
        "sub": sub,
        "tenant": tenant,
        "scope": scope,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(_exp(expire_min).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def create_refresh_token(*, sub: str, tenant: str, scope: str = "") -> str:
    """Refresh longo (dias), também assinado com SECRET_KEY (como no teu projeto)."""
    expire_days = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7))
    payload: Dict[str, Any] = {
        "type": "refresh",
        "sub": sub,
        "tenant": tenant,
        "scope": scope,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(_exp_days(expire_days).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def decode_refresh(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "refresh":
        return None
    # exigidos pelo teu fluxo
    if not payload.get("sub") or not payload.get("tenant") or not payload.get("jti"):
        return None
    return payload

def decode_access(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "access":
        return None
    if not payload.get("sub") or not payload.get("tenant"):
        return None
    return payload
