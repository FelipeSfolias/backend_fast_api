# app/core/security_password.py
from __future__ import annotations

from typing import Tuple
from passlib.context import CryptContext

# Importa bcrypt nativo para contornar bug do passlib + bcrypt recentes
try:
    import bcrypt as _bcrypt  # type: ignore
except Exception:  # se por algum motivo não existir, setamos para None
    _bcrypt = None  # type: ignore

# Argon2 como padrão; aceitamos bcrypt/bcrypt_sha256 como legado
pwd_context = CryptContext(
    schemes=[
        "argon2",         # padrão, seguro, sem limite prático de 72B
        "bcrypt_sha256",  # bcrypt com pré-hash SHA-256 (aceita senhas longas)
        "bcrypt",         # legado: limite 72B
    ],
    deprecated="auto",
    # Parâmetros Argon2 (ajuste conforme infra/tempo)
    argon2__time_cost=2,
    argon2__memory_cost=19456,  # ~19MB
    argon2__parallelism=1,
)

def _is_bcrypt_hash(h: str) -> bool:
    return isinstance(h, str) and h.startswith("$2")

def _is_argon2_hash(h: str) -> bool:
    return isinstance(h, str) and h.startswith("$argon2")

def hash_password(plain: str) -> str:
    if not isinstance(plain, str) or not plain:
        raise ValueError("Senha inválida.")
    if len(plain) > 4096:  # defesa - não aceitar inputs absurdos
        raise ValueError("Senha grande demais.")
    return pwd_context.hash(plain)

def verify_and_maybe_upgrade(plain: str, stored_hash: str) -> Tuple[bool, str | None]:
    """
    Retorna (ok, new_hash_or_None).
    - ok: senha correta?
    - new_hash_or_None: se precisar atualizar (ex.: de bcrypt para argon2), retorna o novo hash.
    Regras:
      * Para hashes argon2 / bcrypt_sha256 -> usa passlib normalmente.
      * Para bcrypt ($2*) -> contorna o passlib chamando bcrypt nativo diretamente
        (evita o bug do backend detection em ambientes com bcrypt recentes).
      * Trata o caso >72 bytes em bcrypt (tenta plain[:72]).
    """
    # Caminho 1: argon2/bcrypt_sha256 – passlib funciona bem
    if _is_argon2_hash(stored_hash) or (isinstance(stored_hash, str) and stored_hash.startswith("$bcrypt-sha256$")):
        ok = pwd_context.verify(plain, stored_hash)
        if not ok:
            return False, None
        # upgrade se necessário (parâmetros argon2 alterados etc.)
        if pwd_context.needs_update(stored_hash):
            return True, pwd_context.hash(plain)
        return True, None

    # Caminho 2: bcrypt puro ($2a/$2b/$2y) – contornar passlib
    if _is_bcrypt_hash(stored_hash):
        # Se a lib bcrypt nativa existir, use-a diretamente.
        if _bcrypt is not None:
            try:
                ok = _bcrypt.checkpw(plain.encode("utf-8"), stored_hash.encode("utf-8"))
            except ValueError as e:
                # Pode ser erro por senha >72B (mesmo que aqui seja raro)
                msg = str(e).lower()
                if "72" in msg and "longer" in msg:
                    # tenta com truncamento para compat com bcrypt
                    ok = _bcrypt.checkpw(plain[:72].encode("utf-8"), stored_hash.encode("utf-8"))
                else:
                    raise
            if not ok:
                return False, None
            # Se passou, fazemos upgrade para Argon2 com a senha COMPLETA
            return True, pwd_context.hash(plain)

        # Sem lib bcrypt nativa disponível? Tenta via passlib, com fallback de truncamento
        try:
            ok = pwd_context.verify(plain, stored_hash)
        except Exception as e:
            # tentativa com truncamento para casos >72B
            try:
                ok = pwd_context.verify(plain[:72], stored_hash)
            except Exception:
                raise
            if not ok:
                return False, None
            return True, pwd_context.hash(plain)

        if not ok:
            return False, None
        # Upgrade para Argon2 se possível
        if pwd_context.needs_update(stored_hash) or _is_bcrypt_hash(stored_hash):
            return True, pwd_context.hash(plain)
        return True, None

    # Caminho 3: qualquer outra coisa – deixar o passlib decidir
    ok = pwd_context.verify(plain, stored_hash)
    if not ok:
        return False, None
    if pwd_context.needs_update(stored_hash):
        return True, pwd_context.hash(plain)
    return True, None
