from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

try:
    from app.db.base_class import Base
except Exception:
    from app.db.base import Base  # type: ignore

from app.models.user_role import user_roles


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), nullable=False, unique=True)

    # M2M: roles <-> users
    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
