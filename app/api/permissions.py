# app/api/permissions.py
from enum import IntEnum
from typing import Iterable, Optional, Callable
from fastapi import Depends, HTTPException, status
from app.api.deps import get_current_user_scoped
from app.schemas.user import UserOut

class Role(IntEnum):
    ALUNO = 1
    PORTARIA = 2
    ORGANIZADOR = 3
    ADMIN_CLIENTE = 4

# Ordem lógica (LGPD/menor privilégio): ALUNO < PORTARIA < ORGANIZADOR < ADMIN_CLIENTE
ROLE_NAMES_PT = {
    Role.ADMIN_CLIENTE: "Admin do Cliente",
    Role.ORGANIZADOR: "Organizador",
    Role.PORTARIA: "Portaria",
    Role.ALUNO: "Aluno",
}

def require_roles(allowed: Iterable[Role]) -> Callable[[UserOut], UserOut]:
    """
    Use: Depends(require_roles([Role.ADMIN_CLIENTE, Role.ORGANIZADOR]))
    Bloqueia quem não tiver uma das roles permitidas.
    """
    allowed_set = set(allowed)

    def _checker(user: UserOut = Depends(get_current_user_scoped)) -> UserOut:
        if Role(user.role) not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado para o perfil '{ROLE_NAMES_PT.get(Role(user.role), 'Desconhecido')}'.",
            )
        return user

    return _checker

def require_role_at_least(min_role: Role) -> Callable[[UserOut], UserOut]:
    """
    Use: Depends(require_role_at_least(Role.PORTARIA))
    Permite min_role e superiores na hierarquia.
    """
    def _checker(user: UserOut = Depends(get_current_user_scoped)) -> UserOut:
        if Role(user.role) < min_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requer no mínimo o perfil '{ROLE_NAMES_PT[min_role]}'.",
            )
        return user

    return _checker
