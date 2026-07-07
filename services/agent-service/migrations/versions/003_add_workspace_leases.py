"""Add workspace leases table

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_leases',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('volume_name', sa.String(), nullable=False),
        sa.Column('container_id', sa.String(), nullable=True),
        sa.Column('branch_name', sa.String(), nullable=False),
        sa.Column('repository_url', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('leased_at', sa.DateTime(timezone=True), server_default=sa.text('now'), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id'),
    )
    op.create_index(op.f('ix_workspace_leases_run_id'), 'workspace_leases', ['run_id'], unique=False)
    op.create_index(op.f('ix_workspace_leases_status'), 'workspace_leases', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_leases_status'), table_name='workspace_leases')
    op.drop_index(op.f('ix_workspace_leases_run_id'), table_name='workspace_leases')
    op.drop_table('workspace_leases')
