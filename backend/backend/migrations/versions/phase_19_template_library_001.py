"""phase_19_template_library_001

Phase 19: Template & Prompt Library System

Tables:
- reusable_modules: Module templates (auth, catalog, cart, checkout, admin)
- file_templates: Individual files within module templates
- parameters: Configurable parameters for module templates
- prompt_templates: Prompt templates for code generation
- adrs: Architecture Decision Records

Revision ID: phase_19_template_library_001
Revises: phase_18_deployment_validator_001
Create Date: 2024-12-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase_19_template_library_001'
down_revision = 'phase_18_deployment_validator_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create reusable_modules table
    op.create_table(
        'reusable_modules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.Enum('authentication', 'commerce', 'admin', 'infrastructure', 'api_design', 'database', 'testing', 'documentation', 'workflow', 'security', name='templatecategory'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('tech_stacks', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('dependencies', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('documentation', sa.Text(), nullable=True),
        sa.Column('params', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rating', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('visibility', sa.Enum('public', 'private', 'draft', name='templatevisibility'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        comment='Reusable module templates'
    )
    op.create_index('idx_reusable_modules_category', 'reusable_modules', ['category'])
    op.create_index('idx_reusable_modules_visibility', 'reusable_modules', ['visibility'])
    op.create_index('idx_reusable_modules_active', 'reusable_modules', ['is_active'])
    op.create_index(op.f('ix_reusable_modules_id'), 'reusable_modules', ['id'])
    
    # Create file_templates table
    op.create_table(
        'file_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('module_id', sa.String(length=36), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('is_test', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_config', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['module_id'], ['reusable_modules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='File templates for reusable modules'
    )
    op.create_index('idx_file_templates_module', 'file_templates', ['module_id'])
    op.create_index('idx_file_templates_language', 'file_templates', ['language'])
    op.create_index(op.f('ix_file_templates_id'), 'file_templates', ['id'])
    
    # Create parameters table
    op.create_table(
        'parameters',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('module_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('param_type', sa.String(length=50), nullable=False),
        sa.Column('default_value', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('validation_rules', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['module_id'], ['reusable_modules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Parameter definitions for module templates'
    )
    op.create_index('idx_parameters_module', 'parameters', ['module_id'])
    op.create_index(op.f('ix_parameters_id'), 'parameters', ['id'])
    
    # Create prompt_templates table
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.Enum('authentication', 'commerce', 'admin', 'infrastructure', 'api_design', 'database', 'testing', 'documentation', 'workflow', 'security', name='templatecategory'), nullable=False),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('context_required', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('output_format', sa.Enum('code', 'documentation', 'schema', 'explanation', 'test_case', 'configuration', name='promptoutputformat'), nullable=False),
        sa.Column('examples', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rating', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('visibility', sa.Enum('public', 'private', 'draft', name='templatevisibility'), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        comment='Prompt templates for code generation'
    )
    op.create_index('idx_prompt_templates_category', 'prompt_templates', ['category'])
    op.create_index('idx_prompt_templates_visibility', 'prompt_templates', ['visibility'])
    op.create_index(op.f('ix_prompt_templates_id'), 'prompt_templates', ['id'])
    
    # Create adrs table
    op.create_table(
        'adrs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('status', sa.Enum('proposed', 'accepted', 'deprecated', 'superseded', name='adrstatus'), nullable=False),
        sa.Column('context', sa.Text(), nullable=False),
        sa.Column('decision', sa.Text(), nullable=False),
        sa.Column('consequences', sa.Text(), nullable=False),
        sa.Column('alternatives_considered', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('related_adrs', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='Architecture Decision Records'
    )
    op.create_index('idx_adrs_workspace', 'adrs', ['workspace_id'])
    op.create_index('idx_adrs_status', 'adrs', ['status'])
    op.create_index('idx_adrs_created_at', 'adrs', ['created_at'])
    op.create_index(op.f('ix_adrs_id'), 'adrs', ['id'])


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table('adrs')
    op.drop_table('prompt_templates')
    op.drop_table('parameters')
    op.drop_table('file_templates')
    op.drop_table('reusable_modules')