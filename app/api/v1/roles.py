from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_current_user_scoped
from app.core.rbac import require_roles
from app.models.role import Role

router = APIRouter()

@router.get("/", dependencies=[Depends(get_current_user_scoped),
                               Depends(require_roles("admin","organizer","portaria"))])
def list_roles(db: Session = Depends(get_db)):
    return [{"id": r.id, "name": r.name} for r in db.scalars(select(Role)).all()]
