"""phase 3.3 security monitor: machines, telemetry windows, incidents, response actions

Revision ID: b3d9a4c61e07
Revises: 7a6cd6618743
Create Date: 2026-11-07 09:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3d9a4c61e07'
down_revision = '7a6cd6618743'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('monitored_machines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('window_count', sa.Integer(), nullable=False),
    sa.Column('last_score', sa.Float(), nullable=True),
    sa.Column('alert_state', sa.JSON(), nullable=True),
    sa.Column('isolated_simulated', sa.Boolean(), nullable=False),
    sa.Column('isolated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('simulated','agent')", name='ck_machine_kind'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    op.create_table('telemetry_windows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('machine_id', sa.Integer(), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('above', sa.Boolean(), nullable=False),
    sa.Column('alert', sa.Boolean(), nullable=False),
    sa.Column('sim_phase', sa.String(length=20), nullable=True),
    sa.Column('features', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['machine_id'], ['monitored_machines.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('machine_id', 'seq', name='uq_window_machine_seq')
    )

    op.create_table('security_incidents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('machine_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=14), nullable=False),
    sa.Column('risk_level', sa.String(length=10), nullable=False),
    sa.Column('peak_score', sa.Float(), nullable=False),
    sa.Column('windows_above', sa.Integer(), nullable=False),
    sa.Column('alert_count', sa.Integer(), nullable=False),
    sa.Column('groups', sa.JSON(), nullable=True),
    sa.Column('reasons', sa.JSON(), nullable=True),
    sa.Column('risk_why', sa.JSON(), nullable=True),
    sa.Column('is_simulated', sa.Boolean(), nullable=False),
    sa.Column('sim_family', sa.String(length=30), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_by', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.CheckConstraint("risk_level IN ('low','medium','high','critical')", name='ck_incident_risk'),
    sa.CheckConstraint("status IN ('open','acknowledged','resolved','false_positive')", name='ck_incident_status'),
    sa.ForeignKeyConstraint(['closed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['machine_id'], ['monitored_machines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('security_incidents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_security_incidents_machine_id'), ['machine_id'], unique=False)

    op.create_table('incident_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('incident_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('note', sa.String(length=300), nullable=True),
    sa.Column('performed_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('simulated', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['incident_id'], ['security_incidents.id'], ),
    sa.ForeignKeyConstraint(['performed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('incident_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_incident_actions_incident_id'), ['incident_id'], unique=False)


def downgrade():
    with op.batch_alter_table('incident_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incident_actions_incident_id'))
    op.drop_table('incident_actions')

    with op.batch_alter_table('security_incidents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_security_incidents_machine_id'))
    op.drop_table('security_incidents')

    op.drop_table('telemetry_windows')
    op.drop_table('monitored_machines')
