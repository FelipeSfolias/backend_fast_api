# app/core/security_password.py
from __future__ import annotations
from passlib.context import CryptContext

# Importante: bcrypt__truncate_error=False evita o erro de 72 bytes
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    # Argon2 (ajuste se quiser endurecer)
    argon2__time_cost=2,
    argon2__memory_cost=19456,  # ~19 MB
    argon2__parallelism=1,
    # Bcrypt: NÃO estourar erro para senhas > 72 bytes (trunca e verifica)
    bcrypt__truncate_error=False,
)

def hash_password(plain: str) -> str:
    """Gera hash (argon2 por padrão)."""
    return pwd_context.hash(plain)

def verify_and_maybe_upgrade(plain: str, stored_hash: str) -> tuple[bool, str | None]:
    """
    Verifica a senha e, se o hash for antigo (ex.: bcrypt), retorna um novo hash (argon2) para upgrade.
    """
    ok = pwd_context.verify(plain, stored_hash)
    if not ok:
        return False, None
    if pwd_context.needs_update(stored_hash):
        return True, pwd_context.hash(plain)
    return True, None
