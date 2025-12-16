"""Add sandbox execution support

Revision ID: sandbox_execution_001
Revises: 
Create Date: 2024-12-16 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'sandbox_execution_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create sandbox execution tables and enums."""
    
    # Create enums first
    sandbox_execution_status = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed', 'cancelled', 'timeout',
        name='sandboxexecutionstatus'
    )
    sandbox_execution_status.create(op.get_bind())
    
    sandbox_execution_language = postgresql.ENUM(
        'javascript', 'node', 'python', 'php', 'docker',
        name='sandboxexecutionlanguage'
    )
    sandbox_execution_language.create(op.get_bind())
    
    # Create sandbox_executions table
    op.create_table('sandbox_executions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        
        # Multi-tenancy
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        
        # Execution details
        sa.Column('execution_type', sandbox_execution_language, nullable=False),
        sa.Column('status', sandbox_execution_status, nullable=False),
        
        # Command and code
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('code', sa.Text()),
        
        # Results
        sa.Column('stdout', sa.Text()),
        sa.Column('stderr', sa.Text()),
        sa.Column('exit_code', sa.Integer()),
        sa.Column('success', sa.Boolean()),
        
        # Resource usage
        sa.Column('duration_ms', sa.Integer()),
        sa.Column('max_memory_mb', sa.Integer()),
        sa.Column('cpu_percent', sa.Float()),
        sa.Column('network_io', sa.BigInteger()),
        sa.Column('disk_io', sa.BigInteger()),
        
        # Error information
        sa.Column('error_type', sa.String(length=255)),
        sa.Column('error_message', sa.Text()),
        sa.Column('timeout_seconds', sa.Integer(), default=30),
        
        # Container information
        sa.Column('container_id', sa.String(length=255)),
        
        # Metadata
        sa.Column('meta_data', sa.JSON(), nullable=False, default=dict),
        
        # Constraints and indexes
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'project_id'],
            ['projects.workspace_id', 'projects.id'],
            name='fk_sandbox_executions_project_in_workspace',
            ondelete='RESTRICT'
        ),
        sa.CheckConstraint('duration_ms >= 0', name='ck_sandbox_executions_duration_positive'),
        sa.CheckConstraint('max_memory_mb >= 0', name='ck_sandbox_executions_memory_positive'),
        sa.CheckConstraint('cpu_percent >= 0 AND cpu_percent <= 100', name='ck_sandbox_executions_cpu_valid'),
        sa.CheckConstraint('network_io >= 0', name='ck_sandbox_executions_network_positive'),
        sa.CheckConstraint('disk_io >= 0', name='ck_sandbox_executions_disk_positive'),
    )
    
    # Create indexes
    op.create_index('idx_sandbox_executions_workspace_project', 'sandbox_executions', ['workspace_id', 'project_id'])
    op.create_index('idx_sandbox_executions_status', 'sandbox_executions', ['status'])
    op.create_index('idx_sandbox_executions_execution_type', 'sandbox_executions', ['execution_type'])
    op.create_index('idx_sandbox_executions_created_at', 'sandbox_executions', ['created_at'])
    op.create_index(op.f('ix_sandbox_executions_id'), 'sandbox_executions', ['id'], unique=True)


def downgrade():
    """Drop sandbox execution tables and enums."""
    
    # Drop indexes
    op.drop_index('ix_sandbox_executions_id', table_name='sandbox_executions')
    op.drop_index('idx_sandbox_executions_created_at', table_name='sandbox_executions')
    op.drop_index('idx_sandbox_executions_execution_type', table_name='sandbox_executions')
    op.drop_index('idx_sandbox_executions_status', table_name='sandbox_executions')
    op.drop_index('idx_sandbox_executions_workspace_project', table_name='sandbox_executions')
    
    # Drop table
    op.drop_table('sandbox_executions')
    
    # Drop enums
    op.execute('DROP TYPE sandboxexecutionlanguage')
    op.execute('DROP TYPE sandboxexecutionstatus')