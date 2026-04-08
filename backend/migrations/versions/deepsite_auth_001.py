"""DeepSite Auth and Projects Migration

Revision ID: deepsite_auth_001
Revises: rbac_audit_logging_001
Create Date: 2026-01-10 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'deepsite_auth_001'
down_revision = 'rbac_audit_logging_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('username', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('last_login', sa.DateTime(timezone=True), nullable=True))
    
    # Create unique index on username
    op.create_index('idx_users_username', 'users', ['username'], unique=True)
    
    # Create deepsite_projects table
    op.create_table('deepsite_projects',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pages', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('files', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('commits', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_deepsite_projects_slug')
    )
    
    # Create indexes
    op.create_index('idx_deepsite_projects_user_id', 'deepsite_projects', ['user_id'])
    op.create_index('idx_deepsite_projects_slug', 'deepsite_projects', ['slug'])


def downgrade() -> None:
    # Drop deepsite_projects table
    op.drop_index('idx_deepsite_projects_slug', table_name='deepsite_projects')
    op.drop_index('idx_deepsite_projects_user_id', table_name='deepsite_projects')
    op.drop_table('deepsite_projects')
    
    # Remove columns from users table
    op.drop_index('idx_users_username', table_name='users')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'username')
