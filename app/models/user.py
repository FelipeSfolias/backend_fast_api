from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

try:
    from app.db.base_class import Base
except Exception:
    from app.db.base import Base  # type: ignore

from app.models.user_role import user_roles  # garante que a tabela exista


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    name = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    mfa = Column(Boolean, default=False)
    
    client = relationship("Client", back_populates="users")  # <- necessário
    roles = relationship("Role", secondary=user_roles, back_populates="users")
