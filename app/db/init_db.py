# app/db/init_db.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.role import Role
from app.models.user import User
from app.core.security import hash_password

ROLE_NAMES = ["admin", "organizer", "gate", "student"]

def init_db(db: Session) -> None:
    # Roles
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for name in ROLE_NAMES:
        if name not in roles:
            r = Role(name=name)
            db.add(r); db.flush()
            roles[name] = r

    # Cliente demo
    tenant = db.scalar(select(Client).where(Client.slug == "demo"))
    if not tenant:
        tenant = Client(
            name="Cliente Demo",
            cnpj="00.000.000/0000-00",
            slug="demo",
            contact_email="contato@democliente.com",  # válido
            default_min_presence_pct=75,
            lgpd_policy_text="Política de privacidade (demo).",
            certificate_template_html=None,
            config_json={},
        )
        db.add(tenant); db.flush()

    # Usuário admin@demo
    admin = db.scalar(select(User).where(User.client_id == tenant.id, User.email == "admin@demo"))
    if not admin:
        admin = User(
            client_id=tenant.id,
            name="Admin Demo",
            email="admin@demo",
            hashed_password=hash_password("admin123"),
            status="active",
        )
        admin.roles.append(roles["admin"])
        db.add(admin)

    db.commit()
