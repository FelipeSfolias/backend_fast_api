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

def require_roles(*roles: str):
    allowed = set(roles)
    def dep(user = Depends(get_current_user_scoped)):
        user_roles = _user_role_names(user)
        if not (user_roles & allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return dep

def require_min_role(min_role: str):
    if min_role not in _RANK:
        raise RuntimeError(f"Unknown role: {min_role}")
    need = _RANK[min_role]
    def dep(user = Depends(get_current_user_scoped)):
        for r in _user_role_names(user):
            if _RANK.get(r, -1) >= need:
                return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return dep
