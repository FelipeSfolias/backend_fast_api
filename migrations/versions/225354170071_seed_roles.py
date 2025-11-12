"""seed roles

Revision ID: seedroles01a2b3
Revises: 20251107_rbac_roles_portaria
Create Date: 2025-11-11 19:30:00.036352
"""
from alembic import op
import sqlalchemy as sa

revision = "seedroles01a2b3"                 # ID curto e único (<=32)
down_revision = "20251107_rbac_roles_portaria"  # <<< depende do shim
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    for name in ("admin", "organizer", "portaria", "aluno"):
        conn.execute(
            sa.text(
                "INSERT INTO roles(name) "
                "SELECT :n WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name=:n)"
            ),
            {"n": name},
        )

def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM roles WHERE name IN ('admin','organizer','portaria','aluno')"
    ))
