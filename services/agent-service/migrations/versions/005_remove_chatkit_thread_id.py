"""Remove chatkit_thread_id column from agent_runs and drop obsolete chatkit tables

Since run_id and thread_id are now the same (1 session per agent-container),
we no longer need a separate chatkit_thread_id field or the legacy chatkit_threads/chatkit_items tables.

Revision ID: 005
Revises: 004
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade():
    # Drop foreign key constraint first
    try:
        op.drop_constraint(
            'agent_runs_chatkit_thread_id_fkey',
            'agent_runs',
            schema='agent'
        )
    except Exception:
        # Constraint may not exist
        pass
    
    # Drop the chatkit_thread_id column
    try:
        op.drop_column('agent_runs', 'chatkit_thread_id', schema='agent')
    except Exception:
        # Column may not exist
        pass
    
    # Drop obsolete chatkit tables
    try:
        op.drop_index('idx_chatkit_items_thread_id', table_name='chatkit_items', schema='agent')
        op.drop_table('chatkit_items', schema='agent')
    except Exception:
        pass
    
    try:
        op.drop_index('idx_chatkit_threads_user_id', table_name='chatkit_threads', schema='agent')
        op.drop_table('chatkit_threads', schema='agent')
    except Exception:
        pass

def downgrade():
    # Re-add chatkit tables
    op.create_table(
        'chatkit_threads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_chatkit_threads_user_id', 'chatkit_threads', ['user_id'], schema='agent')
    
    op.create_table(
        'chatkit_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['agent.chatkit_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_chatkit_items_thread_id', 'chatkit_items', ['thread_id'], schema='agent')
    
    # Re-add the chatkit_thread_id column
    op.add_column(
        'agent_runs',
        sa.Column('chatkit_thread_id', sa.String(), nullable=True),
        schema='agent'
    )
    
    # Re-add the foreign key constraint
    op.create_foreign_key(
        'agent_runs_chatkit_thread_id_fkey',
        'agent_runs',
        'chatkit_threads',
        ['chatkit_thread_id'],
        ['id'],
        ondelete='SET NULL',
        schema='agent'
    )
