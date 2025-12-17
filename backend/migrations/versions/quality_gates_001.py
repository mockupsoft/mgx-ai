"""Add quality gate system tables

Revision ID: quality_gates_001
Revises: 
Create Date: 2024-12-16 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'quality_gates_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create quality gate tables."""
    
    # Create quality_gates table
    op.create_table(
        'quality_gates',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('gate_type', sa.Enum('lint', 'coverage', 'contract', 'performance', 'security', 'complexity', 'type_check', name='qualitygatetype'), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_blocking', sa.Boolean(), nullable=False, default=True),
        sa.Column('threshold_config', sa.JSON(), nullable=False, default=dict),
        sa.Column('status', sa.Enum('pending', 'running', 'passed', 'failed', 'warning', 'skipped', 'error', 'timeout', name='qualitygatestatus'), nullable=False, default='pending'),
        sa.Column('last_evaluation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_result', sa.Boolean(), nullable=True),
        sa.Column('total_evaluations', sa.Integer(), default=0),
        sa.Column('passed_evaluations', sa.Integer(), default=0),
        sa.Column('failed_evaluations', sa.Integer(), default=0),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'project_id'],
            ['projects.workspace_id', 'projects.id'],
            name='fk_quality_gates_project_in_workspace',
            ondelete='RESTRICT'
        ),
        sa.Index('idx_quality_gates_workspace_project', 'workspace_id', 'project_id'),
        sa.Index('idx_quality_gates_type', 'gate_type'),
        sa.Index('idx_quality_gates_status', 'status'),
        sa.UniqueConstraint('workspace_id', 'project_id', 'gate_type', name='uq_quality_gates_unique_type'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create gate_executions table
    op.create_table(
        'gate_executions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gate_id', sa.String(36), sa.ForeignKey('quality_gates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('task_run_id', sa.String(36), sa.ForeignKey('task_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sandbox_execution_id', sa.String(36), sa.ForeignKey('sandbox_executions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'passed', 'failed', 'warning', 'skipped', 'error', 'timeout', name='qualitygatestatus'), nullable=False, default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column('passed_with_warnings', sa.Boolean(), default=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_details', sa.JSON(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('recommendations', sa.JSON(), nullable=True),
        sa.Column('issues_found', sa.Integer(), default=0),
        sa.Column('critical_issues', sa.Integer(), default=0),
        sa.Column('high_issues', sa.Integer(), default=0),
        sa.Column('medium_issues', sa.Integer(), default=0),
        sa.Column('low_issues', sa.Integer(), default=0),
        sa.Column('config_used', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Index('idx_gate_executions_gate_id', 'gate_id'),
        sa.Index('idx_gate_executions_workspace_id', 'workspace_id'),
        sa.Index('idx_gate_executions_task_run', 'task_run_id'),
        sa.Index('idx_gate_executions_sandbox_execution', 'sandbox_execution_id'),
        sa.Index('idx_gate_executions_status', 'status'),
        sa.Index('idx_gate_executions_started_at', 'started_at'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create trigger to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Add triggers for quality_gates
    op.execute("""
        CREATE TRIGGER update_quality_gates_updated_at
        BEFORE UPDATE ON quality_gates
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Add triggers for gate_executions
    op.execute("""
        CREATE TRIGGER update_gate_executions_updated_at
        BEFORE UPDATE ON gate_executions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Insert default gate configurations
    op.execute("""
        INSERT INTO quality_gates (
            id, workspace_id, project_id, name, gate_type, 
            is_enabled, is_blocking, threshold_config, status, description
        ) VALUES 
        (
            'gate_lint_default', 'default', 'default', 
            'Code Linting', 'lint',
            true, true, 
            '{"fail_on_error": true, "fail_on_warning": false, "max_warnings": 10}',
            'pending',
            'Code linting using ESLint, Ruff, and Pint'
        ),
        (
            'gate_coverage_default', 'default', 'default',
            'Test Coverage', 'coverage', 
            true, true,
            '{"min_percentage": 80}',
            'pending',
            'Test coverage enforcement'
        ),
        (
            'gate_security_default', 'default', 'default',
            'Security Audit', 'security',
            true, true,
            '{"allow_dev_dependencies": false, "critical_only": false}',
            'pending', 
            'Security audit and vulnerability scanning'
        ),
        (
            'gate_performance_default', 'default', 'default',
            'Performance Tests', 'performance',
            true, true,
            '{"max_response_time_ms": 500, "min_throughput_rps": 100}',
            'pending',
            'Performance smoke tests'
        ),
        (
            'gate_contract_default', 'default', 'default',
            'API Contract', 'contract',
            true, true,
            '{"endpoints": [], "validation": {}}',
            'pending',
            'API endpoint contract testing'
        ),
        (
            'gate_complexity_default', 'default', 'default',
            'Code Complexity', 'complexity',
            true, true,
            '{"max_cyclomatic": 10, "max_cognitive": 15}',
            'pending',
            'Code complexity limits'
        ),
        (
            'gate_type_check_default', 'default', 'default',
            'Type Checking', 'type_check',
            true, true,
            '{"strict_mode": false}',
            'pending',
            'Type checking for TypeScript and Python'
        )
    """)


def downgrade():
    """Drop quality gate tables."""
    
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS update_gate_executions_updated_at ON gate_executions;")
    op.execute("DROP TRIGGER IF EXISTS update_quality_gates_updated_at ON quality_gates;")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables
    op.drop_table('gate_executions')
    op.drop_table('quality_gates')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS qualitygatestatus;")
    op.execute("DROP TYPE IF EXISTS qualitygatetype;")