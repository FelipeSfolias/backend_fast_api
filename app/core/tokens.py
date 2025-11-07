# app/core/tokens.py
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt, JWTError
from app.core.config import settings

ALGO = settings.ALGORITHM

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _exp_minutes(minutes: int) -> int:
    return int((_utcnow() + timedelta(minutes=minutes)).timestamp())

def _exp_days(days: int) -> int:
    return int((_utcnow() + timedelta(days=days)).timestamp())

def create_access_token(*, sub: int, tenant: str, extra: Optional[Dict[str, Any]] = None) -> str:
    payload: Dict[str, Any] = {
        "jti": uuid.uuid4().hex,
        "type": "access",
        "sub": int(sub),
        "tenant": str(tenant),
        "exp": _exp_minutes(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": int(_utcnow().timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)

def create_refresh_token(*, sub: int, tenant: str, extra: Optional[Dict[str, Any]] = None) -> str:
    payload: Dict[str, Any] = {
        "jti": uuid.uuid4().hex,
        "type": "refresh",
        "sub": int(sub),
        "tenant": str(tenant),
        "exp": _exp_days(settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": int(_utcnow().timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.REFRESH_SECRET_KEY, algorithm=ALGO)

def decode_access(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None
    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("tenant"):
        return None
    return payload

def decode_refresh(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None
    if payload.get("type") != "refresh" or not payload.get("sub") or not payload.get("tenant"):
        return None
    return payload
