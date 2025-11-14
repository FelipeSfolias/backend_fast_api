from sqlalchemy import Table, Column, Integer, ForeignKey

# Compatível com seus layouts (base_class ou base)
try:
    from app.db.base_class import Base
except Exception:
    from app.db.base import Base  # type: ignore


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)
