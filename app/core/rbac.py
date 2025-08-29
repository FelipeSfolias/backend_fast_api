from fastapi import Depends, HTTPException, status
from app.api.deps import get_current_user_scoped

def require_roles(*roles: str):
    def dep(user = Depends(get_current_user_scoped)):
        user_roles = {r.name for r in user.roles}
        if not (set(roles) & user_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return dep
