# -*- coding: utf-8 -*-
"""Phase 15: Project Generator & Scaffold Engine

Revision ID: phase_15_project_generator_001
Revises: 
Create Date: 2024-12-17 14:30:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase_15_project_generator_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    project_template_status = postgresql.ENUM(
        'draft', 'active', 'deprecated', 'archived',
        name='projecttemplatestatus'
    )
    project_template_status.create(op.get_bind())

    project_generation_status = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed', 'cancelled',
        name='projectgenerationstatus'
    )
    project_generation_status.create(op.get_bind())

    stack_type = postgresql.ENUM(
        'express_ts', 'fastapi', 'nextjs', 'laravel',
        name='stacktype'
    )
    stack_type.create(op.get_bind())

    template_feature_type = postgresql.ENUM(
        'auth', 'database', 'logging', 'validation', 'testing', 'docker',
        'cicd', 'monitoring', 'api_docs', 'websocket', 'file_upload',
        'email', 'cache', 'queue',
        name='templatefeaturetype'
    )
    template_feature_type.create(op.get_bind())

    # Create project_templates table
    op.create_table(
        'project_templates',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('stack', stack_type, nullable=False),
        sa.Column('version', sa.String(50), server_default='1.0.0'),
        sa.Column('status', project_template_status, server_default='draft'),
        sa.Column('author', sa.String(200), nullable=True),
        sa.Column('manifest', sa.JSON(), nullable=False),
        sa.Column('default_features', sa.JSON(), nullable=True),
        sa.Column('supported_features', sa.JSON(), nullable=True),
        sa.Column('environment_variables', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_project_templates_stack_status', 'stack', 'status'),
        sa.Index('idx_project_templates_usage', 'usage_count'),
    )

    # Create template_features table
    op.create_table(
        'template_features',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_type', template_feature_type, nullable=False),
        sa.Column('compatible_stacks', sa.JSON(), nullable=False),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('conflicts', sa.JSON(), nullable=True),
        sa.Column('files', sa.JSON(), nullable=True),
        sa.Column('scripts', sa.JSON(), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=True),
        sa.Column('version', sa.String(50), server_default='1.0.0'),
        sa.Column('author', sa.String(200), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.Index('idx_template_features_type', 'feature_type'),
        sa.Index('idx_template_features_stacks', 'compatible_stacks'),
    )

    # Create generated_projects table
    op.create_table(
        'generated_projects',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('workspace_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_id', sa.String(36), nullable=False),
        sa.Column('features_used', sa.JSON(), nullable=True),
        sa.Column('custom_settings', sa.JSON(), nullable=True),
        sa.Column('status', project_generation_status, server_default='pending'),
        sa.Column('progress', sa.Integer(), server_default='0'),
        sa.Column('project_path', sa.String(500), nullable=True),
        sa.Column('files_created', sa.Integer(), server_default='0'),
        sa.Column('repository_url', sa.String(500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('build_successful', sa.Boolean(), nullable=True),
        sa.Column('tests_passed', sa.Boolean(), nullable=True),
        sa.Column('generated_by', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['project_templates.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_generated_projects_workspace_status', 'workspace_id', 'status'),
        sa.Index('idx_generated_projects_template', 'template_id'),
        sa.Index('idx_generated_projects_status_timestamp', 'status', 'created_at'),
    )

    # Add relationship for generated_projects in workspaces table (if needed)
    # Note: The relationship is defined in the model, but we may need to add a column here if there's a backref


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('generated_projects')
    op.drop_table('template_features')
    op.drop_table('project_templates')

    # Drop enums in reverse order
    op.execute('DROP TYPE templatefeaturetype')
    op.execute('DROP TYPE stacktype')
    op.execute('DROP TYPE projectgenerationstatus')
    op.execute('DROP TYPE projecttemplatestatus')