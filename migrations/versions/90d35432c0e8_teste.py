# alembic/versions/xxxxxxxx_add_user_role.py
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "xxxxxxxx_add_user_role"
down_revision = "<COLOQUE_A_REV_ANterior>"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("role", sa.Enum("ALUNO","PORTARIA","ORGANIZADOR","ADMIN_CLIENTE", name="role"), nullable=False, server_default="ALUNO"))
    # Se precisar, remova o server_default depois:
    op.alter_column("users", "role", server_default=None)

def downgrade():
    op.drop_column("users", "role")
    sa.Enum(name="role").drop(op.get_bind(), checkfirst=False)
