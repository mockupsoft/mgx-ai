# -*- coding: utf-8 -*-
"""Migration script for Secret Management and Encryption System

Revision ID: phase_14_secret_management_001
Revises: 
Create Date: 2024-12-17 14:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import func
from enum import Enum

# Create ENUM types for secret management
secret_type_enum = postgresql.ENUM(
    'api_key', 'database_cred', 'oauth_token', 'webhook_secret', 
    'ssh_key', 'certificate', 'encryption_key', 'password', 'jwt_secret',
    name='secret_type'
)

secret_rotation_policy_enum = postgresql.ENUM(
    'manual', 'auto_30_days', 'auto_60_days', 'auto_90_days',
    'auto_180_days', 'auto_365_days',
    name='secret_rotation_policy'
)

secret_backend_enum = postgresql.ENUM(
    'fernet', 'vault', 'aws_kms', 'azure_keyvault',
    name='secret_backend'
)

secret_audit_action_enum = postgresql.ENUM(
    'created', 'accessed', 'rotated', 'deleted', 'updated',
    'encryption_key_rotated', 'backup_created', 'restore_performed',
    name='secret_audit_action'
)

def upgrade():
    """Create secret management tables."""
    
    # Create ENUM types
    secret_type_enum.create(op.get_bind())
    secret_rotation_policy_enum.create(op.get_bind())
    secret_backend_enum.create(op.get_bind())
    secret_audit_action_enum.create(op.get_bind())
    
    # Create secrets table
    op.create_table(
        'secrets',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Workspace relationship
        sa.Column('workspace_id', sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        
        # Secret identification and metadata
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('secret_type', secret_type_enum, nullable=False),
        sa.Column('usage', sa.Text(), comment='Description of what the secret is used for'),
        
        # Encrypted value - never store plaintext
        sa.Column('encrypted_value', sa.Text(), nullable=False, comment='Encrypted secret value'),
        
        # Rotation configuration
        sa.Column('rotation_policy', secret_rotation_policy_enum, nullable=False, 
                 server_default='manual'),
        sa.Column('last_rotated_at', sa.DateTime(timezone=True), comment='When the secret was last rotated'),
        sa.Column('rotation_due_at', sa.DateTime(timezone=True), comment='When rotation is next due'),
        
        # Audit trail for secret management
        sa.Column('created_by_user_id', sa.String(36), nullable=True),
        sa.Column('updated_by_user_id', sa.String(36), nullable=True),
        
        # Metadata and organization
        sa.Column('meta_data', JSONB, server_default='{}', nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', JSONB, comment='Tags for categorizing secrets'),
        
        # Indexes and constraints
        sa.Index('idx_secrets_workspace_type', 'workspace_id', 'secret_type'),
        sa.Index('idx_secrets_rotation_due', 'rotation_due_at'),
        sa.Index('idx_secrets_active', 'is_active'),
        sa.Index('idx_secrets_name_active', 'workspace_id', 'name', 'is_active'),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_secrets_workspace_name')
    )
    
    # Create secret_audits table
    op.create_table(
        'secret_audits',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign key relationship
        sa.Column('secret_id', sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(['secret_id'], ['secrets.id'], ondelete='CASCADE'),
        
        # Audit details
        sa.Column('action', secret_audit_action_enum, nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        
        # Context information
        sa.Column('ip_address', sa.String(45), comment='IP address of the request'),
        sa.Column('user_agent', sa.String(500), comment='User agent of the request'),
        sa.Column('request_id', sa.String(100), comment='Unique request identifier'),
        
        # Operation details
        sa.Column('details', JSONB, comment='Additional operation details'),
        sa.Column('metadata', JSONB, comment='Additional metadata'),
        
        # Success/failure tracking
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), comment='Error message if the operation failed'),
        
        # Indexes
        sa.Index('idx_secret_audits_secret_timestamp', 'secret_id', 'created_at'),
        sa.Index('idx_secret_audits_user_action', 'user_id', 'action'),
        sa.Index('idx_secret_audits_action_timestamp', 'action', 'created_at'),
        sa.Index('idx_secret_audits_secret_id', 'secret_id')
    )
    
    # Create trigger function for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Add updated_at triggers for both tables
    op.execute("""
        CREATE TRIGGER update_secrets_updated_at 
        BEFORE UPDATE ON secrets 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_secret_audits_updated_at 
        BEFORE UPDATE ON secret_audits 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Create indexes for performance optimization
    op.create_index('idx_secrets_workspace_name', 'secrets', ['workspace_id', 'name'])
    op.create_index('idx_secrets_name_trgm', 'secrets', ['name'], postgresql_using='gin',
                   postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('idx_secret_audits_created_at', 'secret_audits', ['created_at'])
    op.create_index('idx_secret_audits_ip_address', 'secret_audits', ['ip_address'])
    
    # Add check constraints
    op.execute("""
        ALTER TABLE secrets ADD CONSTRAINT chk_secret_name_not_empty 
        CHECK (length(trim(name)) > 0);
    """)
    
    op.execute("""
        ALTER TABLE secrets ADD CONSTRAINT chk_secret_rotation_policy_valid
        CHECK (
            rotation_policy = 'manual' OR rotation_due_at IS NOT NULL
        );
    """)
    
    op.execute("""
        ALTER TABLE secret_audits ADD CONSTRAINT chk_secret_audit_action_valid
        CHECK (action IN ('created', 'accessed', 'rotated', 'deleted', 'updated', 
                         'encryption_key_rotated', 'backup_created', 'restore_performed'));
    """)
    
    # Add comments to tables and columns
    op.execute("COMMENT ON TABLE secrets IS 'Secure secret storage with encryption and rotation support';")
    op.execute("COMMENT ON TABLE secret_audits IS 'Audit trail for secret access and management operations';")
    
    op.execute("COMMENT ON COLUMN secrets.name IS 'Secret name (e.g., GITHUB_TOKEN, DATABASE_PASSWORD)';")
    op.execute("COMMENT ON COLUMN secrets.encrypted_value IS 'Encrypted secret value - never store plaintext';")
    op.execute("COMMENT ON COLUMN secrets.rotation_policy IS 'Rotation policy for the secret';")
    op.execute("COMMENT ON COLUMN secrets.rotation_due_at IS 'When rotation is next due';")
    op.execute("COMMENT ON COLUMN secrets.is_active IS 'Whether the secret is active';")
    
    op.execute("COMMENT ON COLUMN secret_audits.action IS 'Action performed on the secret';")
    op.execute("COMMENT ON COLUMN secret_audits.details IS 'Additional operation details';")
    op.execute("COMMENT ON COLUMN secret_audits.success IS 'Whether the operation was successful';")


def downgrade():
    """Drop secret management tables and enums."""
    
    # Drop indexes
    op.drop_index('idx_secret_audits_ip_address', table_name='secret_audits')
    op.drop_index('idx_secret_audits_created_at', table_name='secret_audits')
    op.drop_index('idx_secrets_name_trgm', table_name='secrets')
    op.drop_index('idx_secrets_workspace_name', table_name='secrets')
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_secret_audits_updated_at ON secret_audits;")
    op.execute("DROP TRIGGER IF EXISTS update_secrets_updated_at ON secrets;")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables
    op.drop_table('secret_audits')
    op.drop_table('secrets')
    
    # Drop ENUM types
    secret_audit_action_enum.drop(op.get_bind())
    secret_backend_enum.drop(op.get_bind())
    secret_rotation_policy_enum.drop(op.get_bind())
    secret_type_enum.drop(op.get_bind())