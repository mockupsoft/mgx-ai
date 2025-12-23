"""Performance optimization tables

Revision ID: performance_optimization_001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'performance_optimization_001'
down_revision = None  # Update with latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Performance metrics table
    op.create_table(
        'performance_metrics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('execution_id', sa.String(36), index=True),
        sa.Column('metric_type', sa.String(50), nullable=False, index=True),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Index('idx_perf_metrics_workspace_timestamp', 'workspace_id', 'timestamp'),
        sa.Index('idx_perf_metrics_execution', 'execution_id'),
        sa.Index('idx_perf_metrics_type_name', 'metric_type', 'metric_name'),
    )
    
    # Token usage analytics table
    op.create_table(
        'token_usage_analytics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False),  # day, week, month
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('avg_tokens_per_call', sa.Float(), nullable=False),
        sa.Column('max_tokens_per_call', sa.Integer(), nullable=False),
        sa.Column('min_tokens_per_call', sa.Integer(), nullable=False),
        sa.Column('total_cost_usd', sa.Float(), nullable=False),
        sa.Column('call_count', sa.Integer(), nullable=False),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Index('idx_token_analytics_workspace_period', 'workspace_id', 'period_start'),
    )
    
    # Agent communication metrics table
    op.create_table(
        'agent_communication_metrics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('execution_id', sa.String(36), index=True),
        sa.Column('agent_instance_id', sa.String(36), index=True),
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.Column('message_size_bytes', sa.Integer(), nullable=False),
        sa.Column('communication_latency_ms', sa.Float(), nullable=True),
        sa.Column('context_size_bytes', sa.Integer(), nullable=True),
        sa.Column('context_versions', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Index('idx_agent_comm_workspace_timestamp', 'workspace_id', 'timestamp'),
        sa.Index('idx_agent_comm_execution', 'execution_id'),
    )
    
    # Turn calculation history table
    op.create_table(
        'turn_calculation_history',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('execution_id', sa.String(36), index=True),
        sa.Column('complexity', sa.String(10), nullable=False),
        sa.Column('budget_usd', sa.Float(), nullable=False),
        sa.Column('calculated_rounds', sa.Integer(), nullable=False),
        sa.Column('actual_rounds', sa.Integer(), nullable=False),
        sa.Column('early_terminated', sa.Boolean(), nullable=False, default=False),
        sa.Column('termination_reason', sa.String(100), nullable=True),
        sa.Column('cost_per_round_usd', sa.Float(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=False),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Index('idx_turn_calc_workspace_timestamp', 'workspace_id', 'timestamp'),
        sa.Index('idx_turn_calc_execution', 'execution_id'),
    )


def downgrade() -> None:
    op.drop_table('turn_calculation_history')
    op.drop_table('agent_communication_metrics')
    op.drop_table('token_usage_analytics')
    op.drop_table('performance_metrics')

