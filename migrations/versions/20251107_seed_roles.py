"""seed default roles (admin, organizer, portaria, aluno)

Revision ID: 20251107_seed_roles
Revises: 90d35432c0e8
Create Date: 2025-11-07 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251107_seed_roles'
down_revision: Union[str, Sequence[str], None] = '90d35432c0e8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    roles = ["admin","organizer","portaria","aluno"]
    for r in roles:
        conn.execute(
            sa.text(
                "INSERT INTO roles (name) "
                "SELECT :name WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name=:name)"
            ),
            {"name": r},
        )

def downgrade() -> None:
    conn = op.get_bind()
    for r in ["admin","organizer","portaria","aluno"]:
        conn.execute(sa.text("DELETE FROM roles WHERE name=:name"), {"name": r})
