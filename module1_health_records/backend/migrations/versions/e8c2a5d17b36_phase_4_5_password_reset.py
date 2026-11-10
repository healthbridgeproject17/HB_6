"""phase 4.5 password reset tokens

Revision ID: e8c2a5d17b36
Revises: d5e1f7a92c14
Create Date: 2026-11-10 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8c2a5d17b36'
down_revision = 'd5e1f7a92c14'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
