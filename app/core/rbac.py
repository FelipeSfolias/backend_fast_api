# app/core/rbac.py
from fastapi import Depends, HTTPException, status
from app.api.deps import get_current_user_scoped

ROLE_ADMIN = "admin"         # Admin do Cliente
ROLE_ORGANIZER = "organizer" # Organizador
ROLE_PORTARIA = "portaria"   # Portaria
ROLE_ALUNO = "aluno"         # Aluno

_HIERARCHY = [ROLE_ALUNO, ROLE_PORTARIA, ROLE_ORGANIZER, ROLE_ADMIN]
_RANK = {name: idx for idx, name in enumerate(_HIERARCHY)}

def _user_role_names(user) -> set[str]:
    return {r.name for r in (user.roles or [])}

def require_roles(*allowed: str):
    allowed_set = set(allowed)
    def dep(user = Depends(get_current_user_scoped)):
        user_roles = _user_role_names(user)
        if not (user_roles & allowed_set):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return dep

def require_min_role(min_role: str):
    min_rank = _RANK.get(min_role, -1)
    if min_rank < 0:
        raise RuntimeError(f"Unknown role: {min_role}")
    def dep(user = Depends(get_current_user_scoped)):
        for n in _user_role_names(user):
            if _RANK.get(n, -1) >= min_rank:
                return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return dep
