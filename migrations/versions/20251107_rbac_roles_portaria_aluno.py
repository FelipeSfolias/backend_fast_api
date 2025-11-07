"""rbac: padroniza roles (admin, organizer, portaria, aluno)

Revision ID: 20251107_rbac_roles_portaria
Revises: 90d35432c0e8
Create Date: 2025-11-07 12:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20251107_rbac_roles_portaria"  # <= agora cabe em 32
down_revision: Union[str, Sequence[str], None] = "90d35432c0e8"
branch_labels = None
depends_on = None


def _upsert_role(conn, name: str) -> None:
    bp = sa.bindparam("name", type_=sa.String(32))
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text("INSERT INTO roles (name) VALUES (:name) ON CONFLICT (name) DO NOTHING").bindparams(bp),
            {"name": name},
        )
    elif conn.dialect.name == "mysql":
        conn.execute(
            sa.text("INSERT INTO roles (name) VALUES (:name) ON DUPLICATE KEY UPDATE name=VALUES(name)").bindparams(bp),
            {"name": name},
        )
    else:
        conn.execute(
            sa.text(
                "INSERT INTO roles (name) "
                "SELECT :name WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name=:name)"
            ).bindparams(bp),
            {"name": name},
        )

def upgrade() -> None:
    conn = op.get_bind()
    # renomeia legados, se existirem
    conn.execute(sa.text("UPDATE roles SET name='portaria' WHERE name='gate'"))
    conn.execute(sa.text("UPDATE roles SET name='aluno'    WHERE name='student'"))
    # garante as quatro
    for r in ["admin", "organizer", "portaria", "aluno"]:
        _upsert_role(conn, r)

def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE roles SET name='gate'    WHERE name='portaria'"))
    conn.execute(sa.text("UPDATE roles SET name='student' WHERE name='aluno'"))
