# app/core/security_password.py
from __future__ import annotations
from passlib.context import CryptContext

# Contexto: Argon2 como padrão; aceita hashes legados (bcrypt/bcrypt_sha256).
# E MUITO IMPORTANTE: não deixar o bcrypt estourar erro >72 bytes.
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    # Argon2 (ajuste conforme sua infra)
    argon2__time_cost=2,
    argon2__memory_cost=19456,
    argon2__parallelism=1,
    # Bcrypt: não levantar erro em senhas >72 bytes (trunca com segurança)
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
    Verifica senha contra o hash salvo.
    - Se o hash for legado (bcrypt) e a senha tiver >72 bytes, faz verificação com a senha truncada
      *sem* quebrar, e se der OK faz UPGRADE automático para Argon2 usando a senha completa.
    - Se o hash for antigo (qualquer esquema), re-hasha com Argon2.
    Retorna (ok, new_hash_ou_None).
    """
    try:
        ok = pwd_context.verify(plain, stored_hash)
    except Exception as e:
        msg = str(e).lower()
        # Alguns ambientes ainda propagam o erro do bcrypt. Tratamos aqui.
        if ("72" in msg or "longer than 72" in msg) and stored_hash.startswith("$2"):
            # Hash é bcrypt ($2x$). Verifica com senha truncada e, se OK, migra p/ Argon2.
            plain_trunc = _truncate_utf8(plain, 72)
            ok_trunc = pwd_context.verify(plain_trunc, stored_hash)
            if not ok_trunc:
                return False, None
            return True, pwd_context.hash(plain)  # upgrade com a senha COMPLETA
        # Outros erros: propague para que o handler capture.
        raise

    if not ok:
        return False, None

    if pwd_context.needs_update(stored_hash):
        return True, pwd_context.hash(plain)

    return True, None
