# app/core/security_password.py
from __future__ import annotations
from passlib.context import CryptContext

# Contexto: Argon2 como padrão; aceita hashes legados (bcrypt/bcrypt_sha256).
# Evita que bcrypt estoure erro em senhas >72 bytes.
pwd_context = CryptContext(
    schemes=[
        "argon2",         # novo padrão
        "bcrypt_sha256",  # pré-hash com SHA-256 (sem limite de 72 bytes)
        "bcrypt",         # legado (tem limite de 72 bytes)
    ],
    deprecated="auto",
    # Parâmetros Argon2 (ajuste conforme sua infra)
    argon2__time_cost=2,
    argon2__memory_cost=19456,
    argon2__parallelism=1,
    # Bcrypt: não levantar erro de 72 bytes; permitir truncamento silencioso
    bcrypt__truncate_error=False,
)

def _truncate_utf8(s: str, n: int = 72) -> str:
    b = s.encode("utf-8")
    return b[:n].decode("utf-8", "ignore")

def hash_password(plain: str) -> str:
    """Gera hash seguro (argon2 por padrão)."""
    return pwd_context.hash(plain)

def verify_and_maybe_upgrade(plain: str, stored_hash: str) -> tuple[bool, str | None]:
    """
    Verifica a senha contra o hash salvo.
    - Se o hash for bcrypt e a senha tiver >72 bytes, tenta com senha truncada,
      e se validar, retorna um novo hash Argon2 usando a senha COMPLETA.
    - Se o hash for antigo (needs_update), retorna novo hash (Argon2).
    Retorna (ok, new_hash_ou_None).
    """
    try:
        ok = pwd_context.verify(plain, stored_hash)
    except Exception as e:
        msg = str(e).lower()
        if ("72" in msg or "longer than 72" in msg) and stored_hash.startswith("$2"):
            # Hash legado bcrypt; revalida com senha truncada (regra do bcrypt)
            plain_trunc = _truncate_utf8(plain, 72)
            ok_trunc = pwd_context.verify(plain_trunc, stored_hash)
            if not ok_trunc:
                return False, None
            # Upgrade para Argon2 com a senha COMPLETA
            return True, pwd_context.hash(plain)
        # outros erros: propaga
        raise

    if not ok:
        return False, None

    if pwd_context.needs_update(stored_hash):
        return True, pwd_context.hash(plain)

    return True, None