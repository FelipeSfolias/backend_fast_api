from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.bases import Base
from .user_role import user_roles

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), nullable=False, unique=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")
