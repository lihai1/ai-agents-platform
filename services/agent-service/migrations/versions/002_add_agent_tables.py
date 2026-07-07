"""Add agent workflow tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    # Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('repository_id', sa.String(), nullable=False),
        sa.Column('chatkit_thread_id', sa.String(), nullable=True),
        sa.Column('task', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('current_phase', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('cancel_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_cost', sa.Float(), nullable=True),
        sa.Column('cost_incurred', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('repair_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_repair_count', sa.Integer(), server_default='2', nullable=False),
        sa.ForeignKeyConstraint(['chatkit_thread_id'], ['agent.chatkit_threads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_agent_runs_user_id', 'agent_runs', ['user_id'], schema='agent')
    op.create_index('idx_agent_runs_project_id', 'agent_runs', ['project_id'], schema='agent')
    op.create_index('idx_agent_runs_repository_id', 'agent_runs', ['repository_id'], schema='agent')
    op.create_index('idx_agent_runs_status', 'agent_runs', ['status'], schema='agent')
    
    # Create agent_steps table
    op.create_table(
        'agent_steps',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('phase', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('input_data', postgresql.JSON(), nullable=True),
        sa.Column('output_data', postgresql.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['agent.agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_agent_steps_run_id', 'agent_steps', ['run_id'], schema='agent')
    op.create_index('idx_agent_steps_phase', 'agent_steps', ['phase'], schema='agent')
    
    # Create agent_events table
    op.create_table(
        'agent_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_data', postgresql.JSON(), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent.agent_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['agent.agent_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_agent_events_run_id', 'agent_events', ['run_id'], schema='agent')
    op.create_index('idx_agent_events_step_id', 'agent_events', ['step_id'], schema='agent')
    op.create_index('idx_agent_events_event_type', 'agent_events', ['event_type'], schema='agent')
    op.create_index('idx_agent_events_sequence_number', 'agent_events', ['sequence_number'], schema='agent')
    
    # Create skill_snapshots table
    op.create_table(
        'skill_snapshots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('skill_name', sa.String(), nullable=False),
        sa.Column('skill_version', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('skill_yaml', sa.Text(), nullable=False),
        sa.Column('skill_markdown', sa.Text(), nullable=False),
        sa.Column('output_schema', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent.agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_skill_snapshots_run_id', 'skill_snapshots', ['run_id'], schema='agent')
    
    # Create agent_artifacts table
    op.create_table(
        'agent_artifacts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=True),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent.agent_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['agent.agent_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_agent_artifacts_run_id', 'agent_artifacts', ['run_id'], schema='agent')
    op.create_index('idx_agent_artifacts_step_id', 'agent_artifacts', ['step_id'], schema='agent')
    op.create_index('idx_agent_artifacts_kind', 'agent_artifacts', ['kind'], schema='agent')
    
    # Create agent_approvals table
    op.create_table(
        'agent_approvals',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=True),
        sa.Column('approval_type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('decision', sa.String(), nullable=True),
        sa.Column('decided_by', sa.String(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent.agent_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['agent.agent_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='agent'
    )
    op.create_index('idx_agent_approvals_run_id', 'agent_approvals', ['run_id'], schema='agent')
    op.create_index('idx_agent_approvals_step_id', 'agent_approvals', ['step_id'], schema='agent')

def downgrade():
    op.drop_index('idx_agent_approvals_step_id', table_name='agent_approvals', schema='agent')
    op.drop_index('idx_agent_approvals_run_id', table_name='agent_approvals', schema='agent')
    op.drop_table('agent_approvals', schema='agent')
    
    op.drop_index('idx_agent_artifacts_kind', table_name='agent_artifacts', schema='agent')
    op.drop_index('idx_agent_artifacts_step_id', table_name='agent_artifacts', schema='agent')
    op.drop_index('idx_agent_artifacts_run_id', table_name='agent_artifacts', schema='agent')
    op.drop_table('agent_artifacts', schema='agent')
    
    op.drop_index('idx_skill_snapshots_run_id', table_name='skill_snapshots', schema='agent')
    op.drop_table('skill_snapshots', schema='agent')
    
    op.drop_index('idx_agent_events_sequence_number', table_name='agent_events', schema='agent')
    op.drop_index('idx_agent_events_event_type', table_name='agent_events', schema='agent')
    op.drop_index('idx_agent_events_step_id', table_name='agent_events', schema='agent')
    op.drop_index('idx_agent_events_run_id', table_name='agent_events', schema='agent')
    op.drop_table('agent_events', schema='agent')
    
    op.drop_index('idx_agent_steps_phase', table_name='agent_steps', schema='agent')
    op.drop_index('idx_agent_steps_run_id', table_name='agent_steps', schema='agent')
    op.drop_table('agent_steps', schema='agent')
    
    op.drop_index('idx_agent_runs_status', table_name='agent_runs', schema='agent')
    op.drop_index('idx_agent_runs_repository_id', table_name='agent_runs', schema='agent')
    op.drop_index('idx_agent_runs_project_id', table_name='agent_runs', schema='agent')
    op.drop_index('idx_agent_runs_user_id', table_name='agent_runs', schema='agent')
    op.drop_table('agent_runs', schema='agent')
