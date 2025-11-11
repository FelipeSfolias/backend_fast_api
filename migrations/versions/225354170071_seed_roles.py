"""seed roles

Revision ID: 225354170071
Revises: 90d35432c0e8
Create Date: 2025-11-11 19:30:00.036352

"""
from alembic import op
import sqlalchemy as sa

# Use a rev ID curta (gerada pelo Alembic)
revision = "90d35432c0e8"
down_revision = "225354170071"  # ex: "90d35432c0e8"
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
