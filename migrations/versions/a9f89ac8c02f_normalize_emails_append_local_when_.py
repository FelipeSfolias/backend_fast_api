"""normalize emails: append .local when domain has no dot

Revision ID: a9f89ac8c02f
Revises: seedroles01a2b3
Create Date: 2025-11-14 15:19:28.716651

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9f89ac8c02f'
down_revision: Union[str, Sequence[str], None] = 'seedroles01a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Acrescenta ".local" quando o domínio não possui ponto (ex.: admin@demo)
    op.execute(sa.text("""
        UPDATE users u
           SET email = u.email || '.local'
         WHERE u.email ~ '^[^@]+@[^.@]+$'
           AND NOT EXISTS (
                 SELECT 1 FROM users u2
                  WHERE u2.client_id = u.client_id
                    AND u2.email = u.email || '.local'
           );
        -- (opcional) se quiser limpar refresh tokens atrelados ao e-mail antigo:
        DELETE FROM refresh_tokens rt
         WHERE rt.user_email ~ '^[^@]+@[^.@]+$';
    """))

def downgrade() -> None:
    # Reverte somente os que terminam com .local e cujo "sem .local" não conflita
    op.execute(sa.text("""
        UPDATE users u
           SET email = regexp_replace(u.email, '\\.local$', '', 1)
         WHERE u.email ~ '^[^@]+@[^.@]+\\.local$'
           AND NOT EXISTS (
                 SELECT 1 FROM users u2
                  WHERE u2.client_id = u.client_id
                    AND u2.email = regexp_replace(u.email, '\\.local$', '', 1)
           );
    """))
