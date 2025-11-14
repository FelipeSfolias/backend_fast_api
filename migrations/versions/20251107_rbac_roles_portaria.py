"""rbac: shim portaria

Revision ID: 20251107_rbac_roles_portaria
Revises: 90d35432c0e8
Create Date: 2025-11-12 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "a9f89ac8c02f"
down_revision = "90d35432c0e8"
branch_labels = None
depends_on = None

def upgrade():
    # no-op: ponte para manter a cadeia linear
    pass

def downgrade():
    pass
