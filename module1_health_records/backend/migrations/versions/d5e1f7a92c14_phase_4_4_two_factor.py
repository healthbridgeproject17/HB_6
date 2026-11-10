"""phase 4.4 two-factor login: secret, enabled flag, replay guard, backup codes

Revision ID: d5e1f7a92c14
Revises: b3d9a4c61e07
Create Date: 2026-11-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e1f7a92c14'
down_revision = 'b3d9a4c61e07'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('totp_secret_enc', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('totp_enabled', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('users', sa.Column('totp_last_step', sa.BigInteger(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('backup_code_hashes', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('users', 'backup_code_hashes')
    op.drop_column('users', 'totp_last_step')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret_enc')
