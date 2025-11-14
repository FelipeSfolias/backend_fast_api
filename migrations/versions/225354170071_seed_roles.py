"""seed roles

Revision ID: seedroles01a2b3
Revises: 20251107_rbac_roles_portaria
Create Date: 2025-11-11 19:30:00.036352
"""
from alembic import op
import sqlalchemy as sa

revision = "seedroles01a2b3"
down_revision = "a9f89ac8c02f"
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()

    stmt = sa.text(
        "INSERT INTO roles(name) VALUES (:n) "
        "ON CONFLICT (name) DO NOTHING"
    ).bindparams(sa.bindparam("n", type_=sa.String(32)))

    for name in ("admin", "organizer", "portaria", "aluno"):
        conn.execute(stmt, {"n": name})


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM roles WHERE name IN ('admin','organizer','portaria','aluno')"
    ))
