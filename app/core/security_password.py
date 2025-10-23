# app/core/security_password.py
from __future__ import annotations
from passlib.context import CryptContext

# Argon2 como padrão; aceitamos bcrypt/bcrypt_sha256 como legado
pwd_context = CryptContext(
    schemes=[
        "argon2",         # novo padrão, sem limite prático de 72 bytes
        "bcrypt_sha256",  # bcrypt com pré-hash SHA-256 (sem limite de 72 bytes)
        "bcrypt",         # legado (tem limite de 72 bytes)
    ],
    deprecated="auto",

    # Parâmetros Argon2 – ajuste conforme a infra (tempo/memória)
    argon2__time_cost=2,
    argon2__memory_cost=19456,  # ~19MB
    argon2__parallelism=1,
)

def hash_password(plain: str) -> str:
    # Você pode impor um limite razoável (ex.: 128) ANTES de hashear:
    if not isinstance(plain, str) or len(plain) == 0:
        raise ValueError("Senha inválida.")
    if len(plain) > 1024:  # defesa: não aceite lixo gigante
        raise ValueError("Senha grande demais.")
    return pwd_context.hash(plain)

def verify_and_maybe_upgrade(plain: str, stored_hash: str) -> tuple[bool, str | None]:
    """
    Retorna (ok, new_hash_or_None).
    - ok: senha correta?
    - new_hash_or_None: se precisar atualizar (ex.: de bcrypt para argon2), retorna o novo hash.
    """
    try:
        ok = pwd_context.verify(plain, stored_hash)
    except Exception as e:
        msg = str(e)
        # Caso clássico do bcrypt: senha >72 bytes
        if "72" in msg and "longer" in msg or "password" in msg and "72" in msg:
            # Tenta verificar truncando (p/ compat c/ bcrypt puro)
            ok_trunc = pwd_context.verify(plain[:72], stored_hash)
            if not ok_trunc:
                return False, None
            # Correto: atualiza para argon2 com a senha COMPLETA
            return True, pwd_context.hash(plain)
        # Outros erros: propaga
        raise

    if not ok:
        return False, None

    # Se o hash precisar de update (ex.: ainda é bcrypt/bcrypt_sha256), atualiza
    if pwd_context.needs_update(stored_hash):
        return True, pwd_context.hash(plain)

    return True, None
