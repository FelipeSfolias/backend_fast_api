# app/db/init_db.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.role import Role
from app.models.user import User
from app.core.security import hash_password

ROLE_NAMES = ["admin", "organizer", "portaria", "aluno"]

def init_db(db: Session) -> None:
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for name in ROLE_NAMES:
        if name not in roles:
            r = Role(name=name)
            db.add(r); db.flush()
            roles[name] = r

    tenant = db.scalar(select(Client).where(Client.slug == "demo"))
    if not tenant:
        tenant = Client(name="Cliente Demo", cnpj="00.000.000/0000-00", slug="demo", logo_url=None)
        db.add(tenant); db.flush()

    admin = db.scalar(select(User).where(User.client_id == tenant.id, User.email == "admin@demo"))
    if not admin:
        admin = User(
            client_id=tenant.id,
            name="Admin Demo",
            email="admin@demo",
            hashed_password=hash_password("admin123"),
            status="active",
        )
        db.add(admin); db.flush()
        admin.roles.append(roles["admin"])

    db.commit()
