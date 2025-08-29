from sqlalchemy.orm import Session
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, User as UserOut, UserBase

from app.core.security import get_password_hash

class CRUDUser(CRUDBase[User, UserCreate, UserBase]):
    def create(self, db: Session, obj_in: UserCreate, extra=None) -> User:
        data = obj_in.model_dump()
        role_names = data.pop("role_names", [])
        data["hashed_password"] = get_password_hash(data.pop("password"))
        if extra: data.update(extra)
        user = User(**data)
        db.add(user); db.commit(); db.refresh(user)
        # roles
        for name in role_names:
            role = db.execute(select(Role).where(Role.name==name)).scalar_one_or_none()
            if role: user.roles.append(role)
        db.commit(); db.refresh(user)
        return user

    def get_by_email(self, db: Session, email: str, client_id: int) -> User | None:
        return db.execute(select(User).where(User.email==email, User.client_id==client_id)).scalar_one_or_none()

user_crud = CRUDUser(User)
