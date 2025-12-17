"""phase_17_cost_tracking_001

Phase 17: Cost Tracking & Resource Monitoring

Tables:
- llm_calls: Track LLM API calls with costs and token usage
- resource_usage: Track compute resource usage
- execution_costs: Aggregated cost summary for executions
- workspace_budgets: Budget limits and alerts for workspaces
- project_budgets: Budget limits for projects

Revision ID: phase_17_cost_tracking_001
Revises: phase_15_project_generator_001
Create Date: 2024-12-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase_17_cost_tracking_001'
down_revision = 'phase_15_project_generator_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create llm_calls table
    op.create_table(
        'llm_calls',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('execution_id', sa.String(length=36), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('tokens_prompt', sa.Integer(), nullable=False),
        sa.Column('tokens_completion', sa.Integer(), nullable=False),
        sa.Column('tokens_total', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('call_metadata', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Record of LLM API call with cost tracking'
    )
    op.create_index('idx_llm_calls_workspace_timestamp', 'llm_calls', ['workspace_id', 'timestamp'])
    op.create_index('idx_llm_calls_execution', 'llm_calls', ['execution_id'])
    op.create_index('idx_llm_calls_provider_model', 'llm_calls', ['provider', 'model'])
    op.create_index('idx_llm_calls_timestamp', 'llm_calls', ['timestamp'])
    op.create_index(op.f('ix_llm_calls_id'), 'llm_calls', ['id'])
    op.create_index(op.f('ix_llm_calls_workspace_id'), 'llm_calls', ['workspace_id'])
    op.create_index(op.f('ix_llm_calls_provider'), 'llm_calls', ['provider'])
    op.create_index(op.f('ix_llm_calls_model'), 'llm_calls', ['model'])

    # Create resource_usage table
    op.create_table(
        'resource_usage',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('execution_id', sa.String(length=36), nullable=True),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('usage_value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('usage_metadata', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Record of compute resource usage'
    )
    op.create_index('idx_resource_usage_workspace_timestamp', 'resource_usage', ['workspace_id', 'timestamp'])
    op.create_index('idx_resource_usage_execution', 'resource_usage', ['execution_id'])
    op.create_index('idx_resource_usage_type', 'resource_usage', ['resource_type'])
    op.create_index('idx_resource_usage_timestamp', 'resource_usage', ['timestamp'])
    op.create_index(op.f('ix_resource_usage_id'), 'resource_usage', ['id'])
    op.create_index(op.f('ix_resource_usage_workspace_id'), 'resource_usage', ['workspace_id'])
    op.create_index(op.f('ix_resource_usage_resource_type'), 'resource_usage', ['resource_type'])

    # Create execution_costs table
    op.create_table(
        'execution_costs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('execution_id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('total_llm_cost', sa.Float(), nullable=False),
        sa.Column('total_compute_cost', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('breakdown', sa.JSON(), nullable=False),
        sa.Column('llm_call_count', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('execution_id'),
        comment='Aggregated cost summary for an execution'
    )
    op.create_index('idx_execution_costs_workspace', 'execution_costs', ['workspace_id'])
    op.create_index('idx_execution_costs_timestamp', 'execution_costs', ['timestamp'])
    op.create_index(op.f('ix_execution_costs_id'), 'execution_costs', ['id'])
    op.create_index(op.f('ix_execution_costs_execution_id'), 'execution_costs', ['execution_id'])
    op.create_index(op.f('ix_execution_costs_workspace_id'), 'execution_costs', ['workspace_id'])

    # Create workspace_budgets table
    op.create_table(
        'workspace_budgets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('monthly_budget_usd', sa.Float(), nullable=False),
        sa.Column('current_month_spent', sa.Float(), nullable=False),
        sa.Column('alert_threshold_percent', sa.Integer(), nullable=False),
        sa.Column('alert_emails', sa.JSON(), nullable=False),
        sa.Column('alerts_sent', sa.JSON(), nullable=False),
        sa.Column('last_alert_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('budget_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('budget_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('hard_limit', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id'),
        comment='Budget limits and alerts for a workspace'
    )
    op.create_index('idx_workspace_budgets_workspace', 'workspace_budgets', ['workspace_id'])
    op.create_index(op.f('ix_workspace_budgets_id'), 'workspace_budgets', ['id'])
    op.create_index(op.f('ix_workspace_budgets_workspace_id'), 'workspace_budgets', ['workspace_id'], unique=True)

    # Create project_budgets table
    op.create_table(
        'project_budgets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('monthly_budget_usd', sa.Float(), nullable=False),
        sa.Column('current_month_spent', sa.Float(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id'),
        comment='Budget limits for a specific project'
    )
    op.create_index('idx_project_budgets_project', 'project_budgets', ['project_id'])
    op.create_index('idx_project_budgets_workspace', 'project_budgets', ['workspace_id'])
    op.create_index(op.f('ix_project_budgets_id'), 'project_budgets', ['id'])
    op.create_index(op.f('ix_project_budgets_project_id'), 'project_budgets', ['project_id'], unique=True)
    op.create_index(op.f('ix_project_budgets_workspace_id'), 'project_budgets', ['workspace_id'])


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Drop tables in reverse order
    op.drop_table('project_budgets')
    op.drop_table('workspace_budgets')
    op.drop_table('execution_costs')
    op.drop_table('resource_usage')
    op.drop_table('llm_calls')
