"""Add is_admin flag to operators"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b405bc41c4c3'
down_revision = '464b27697f65'
branch_labels = None
depends_on = None

def upgrade():
    # Añadimos la columna con un valor por defecto FALSE para los registros existentes
    op.add_column(
        'operators',
        sa.Column(
            'is_admin',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false')
        )
    )
    # Una vez creada, podemos eliminar el server_default si lo prefieres
    op.alter_column(
        'operators',
        'is_admin',
        server_default=None
    )

def downgrade():
    op.drop_column('operators', 'is_admin')
