# backend/core/security_password.py
from __future__ import annotations
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    argon2__time_cost=2,
    argon2__memory_cost=19456,  # ~19 MB
    argon2__parallelism=1,
)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_and_maybe_upgrade(plain: str, stored_hash: str) -> tuple[bool, str | None]:
    ok = pwd_context.verify(plain, stored_hash)
    if not ok:
        return False, None
    if pwd_context.needs_update(stored_hash):
        return True, pwd_context.hash(plain)
    return True, None
