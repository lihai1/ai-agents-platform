"""Initial migration for agent schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create agent schema
    op.execute('CREATE SCHEMA IF NOT EXISTS agent')
    
    # Create chatkit_threads table
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
    
    # Create chatkit_items table
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

def downgrade():
    op.drop_index('idx_chatkit_items_thread_id', table_name='chatkit_items', schema='agent')
    op.drop_table('chatkit_items', schema='agent')
    op.drop_index('idx_chatkit_threads_user_id', table_name='chatkit_threads', schema='agent')
    op.drop_table('chatkit_threads', schema='agent')
    op.execute('DROP SCHEMA IF EXISTS agent')
