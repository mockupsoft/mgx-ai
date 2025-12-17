"""RBAC and Audit Logging Models Migration

Revision ID: rbac_audit_logging_001
Revises: 
Create Date: 2024-12-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'rbac_audit_logging_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    role_name_enum = postgresql.ENUM('admin', 'developer', 'viewer', 'auditor', name='role_name')
    role_name_enum.create(op.get_bind())
    
    permission_resource_enum = postgresql.ENUM(
        'tasks', 'workflows', 'repositories', 'repos', 'agents', 'settings', 
        'users', 'audit', 'metrics', 'workspaces', 'projects', name='permission_resource'
    )
    permission_resource_enum.create(op.get_bind())
    
    permission_action_enum = postgresql.ENUM(
        'create', 'read', 'update', 'delete', 'execute', 'approve', 'manage', 'connect', 
        name='permission_action'
    )
    permission_action_enum.create(op.get_bind())
    
    audit_action_enum = postgresql.ENUM(
        'USER_LOGIN', 'USER_LOGOUT', 'USER_CREATED', 'USER_UPDATED', 'USER_DELETED',
        'ROLE_CREATED', 'ROLE_UPDATED', 'ROLE_DELETED', 'ROLE_ASSIGNED', 'ROLE_REVOKED',
        'PERMISSION_GRANTED', 'PERMISSION_REVOKED',
        'WORKSPACE_CREATED', 'WORKSPACE_UPDATED', 'WORKSPACE_DELETED',
        'WORKSPACE_ACCESS_GRANTED', 'WORKSPACE_ACCESS_REVOKED',
        'PROJECT_CREATED', 'PROJECT_UPDATED', 'PROJECT_DELETED',
        'TASK_CREATED', 'TASK_UPDATED', 'TASK_DELETED', 'TASK_EXECUTED',
        'TASK_RUN_STARTED', 'TASK_RUN_COMPLETED', 'TASK_RUN_FAILED',
        'WORKFLOW_CREATED', 'WORKFLOW_UPDATED', 'WORKFLOW_DELETED',
        'WORKFLOW_EXECUTED', 'WORKFLOW_STEP_EXECUTED',
        'REPOSITORY_CONNECTED', 'REPOSITORY_DISCONNECTED', 'REPOSITORY_ACCESS_GRANTED',
        'AGENT_CREATED', 'AGENT_UPDATED', 'AGENT_DELETED', 'AGENT_ENABLED',
        'AGENT_DISABLED', 'AGENT_MESSAGE_SENT',
        'SETTINGS_CHANGED', 'SYSTEM_BACKUP_CREATED', 'SYSTEM_MAINTENANCE_MODE_ENABLED',
        'UNAUTHORIZED_ACCESS_ATTEMPT', 'SECURITY_VIOLATION_DETECTED',
        'DATA_EXPORTED', 'DATA_IMPORTED', 'BULK_OPERATION_PERFORMED',
        'SANDBOX_EXECUTION_STARTED', 'SANDBOX_EXECUTION_COMPLETED', 'SANDBOX_EXECUTION_FAILED',
        name='audit_action'
    )
    audit_action_enum.create(op.get_bind())
    
    audit_log_status_enum = postgresql.ENUM(
        'success', 'failure', 'error', 'warning', name='audit_log_status'
    )
    audit_log_status_enum.create(op.get_bind())
    
    # Create roles table
    op.create_table('roles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Enum('admin', 'developer', 'viewer', 'auditor', name='role_name'), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_roles_workspace_name')
    )
    op.create_index('idx_roles_workspace_name', 'roles', ['workspace_id', 'name'])
    
    # Create user_roles table
    op.create_table('user_roles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', sa.String(length=36), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assigned_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_user_roles_user_workspace', 'user_id', 'workspace_id'),
        sa.Index('idx_user_roles_role', 'role_id'),
        sa.UniqueConstraint('user_id', 'workspace_id', 'role_id', name='uq_user_roles_unique_assignment')
    )
    
    # Create permissions table
    op.create_table('permissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', sa.String(length=36), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('resource', sa.Enum(
            'tasks', 'workflows', 'repositories', 'repos', 'agents', 'settings', 
            'users', 'audit', 'metrics', 'workspaces', 'projects', name='permission_resource'
        ), nullable=False),
        sa.Column('action', sa.Enum(
            'create', 'read', 'update', 'delete', 'execute', 'approve', 'manage', 'connect', 
            name='permission_action'
        ), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_permissions_role_resource_action', 'role_id', 'resource', 'action'),
        sa.UniqueConstraint('workspace_id', 'role_id', 'resource', 'action', name='uq_permissions_unique')
    )
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.Enum(
            'USER_LOGIN', 'USER_LOGOUT', 'USER_CREATED', 'USER_UPDATED', 'USER_DELETED',
            'ROLE_CREATED', 'ROLE_UPDATED', 'ROLE_DELETED', 'ROLE_ASSIGNED', 'ROLE_REVOKED',
            'PERMISSION_GRANTED', 'PERMISSION_REVOKED',
            'WORKSPACE_CREATED', 'WORKSPACE_UPDATED', 'WORKSPACE_DELETED',
            'WORKSPACE_ACCESS_GRANTED', 'WORKSPACE_ACCESS_REVOKED',
            'PROJECT_CREATED', 'PROJECT_UPDATED', 'PROJECT_DELETED',
            'TASK_CREATED', 'TASK_UPDATED', 'TASK_DELETED', 'TASK_EXECUTED',
            'TASK_RUN_STARTED', 'TASK_RUN_COMPLETED', 'TASK_RUN_FAILED',
            'WORKFLOW_CREATED', 'WORKFLOW_UPDATED', 'WORKFLOW_DELETED',
            'WORKFLOW_EXECUTED', 'WORKFLOW_STEP_EXECUTED',
            'REPOSITORY_CONNECTED', 'REPOSITORY_DISCONNECTED', 'REPOSITORY_ACCESS_GRANTED',
            'AGENT_CREATED', 'AGENT_UPDATED', 'AGENT_DELETED', 'AGENT_ENABLED',
            'AGENT_DISABLED', 'AGENT_MESSAGE_SENT',
            'SETTINGS_CHANGED', 'SYSTEM_BACKUP_CREATED', 'SYSTEM_MAINTENANCE_MODE_ENABLED',
            'UNAUTHORIZED_ACCESS_ATTEMPT', 'SECURITY_VIOLATION_DETECTED',
            'DATA_EXPORTED', 'DATA_IMPORTED', 'BULK_OPERATION_PERFORMED',
            'SANDBOX_EXECUTION_STARTED', 'SANDBOX_EXECUTION_COMPLETED', 'SANDBOX_EXECUTION_FAILED',
            name='audit_action'
        ), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('success', 'failure', 'error', 'warning', name='audit_log_status'), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_audit_logs_workspace_timestamp', 'workspace_id', 'created_at'),
        sa.Index('idx_audit_logs_user_action', 'user_id', 'action'),
        sa.Index('idx_audit_logs_resource', 'resource_type', 'resource_id'),
        sa.Index('idx_audit_logs_status', 'status')
    )


def downgrade() -> None:
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('permissions')
    op.drop_table('user_roles')
    op.drop_table('roles')
    
    # Drop enums
    op.execute('DROP TYPE audit_log_status')
    op.execute('DROP TYPE audit_action')
    op.execute('DROP TYPE permission_action')
    op.execute('DROP TYPE permission_resource')
    op.execute('DROP TYPE role_name')