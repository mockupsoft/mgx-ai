"""GitHub webhook events table

Revision ID: github_webhooks_001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'github_webhooks_001'
down_revision = 'file_level_approval_001'  # Update to latest migration
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'github_webhook_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('delivery_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('repository_id', sa.String(36), sa.ForeignKey('repository_links.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('repo_full_name', sa.String(255), nullable=True, index=True),
        sa.Column('payload', postgresql.JSON, nullable=False),
        sa.Column('parsed_data', postgresql.JSON, nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    op.create_index('idx_webhook_events_delivery_id', 'github_webhook_events', ['delivery_id'])
    op.create_index('idx_webhook_events_event_type', 'github_webhook_events', ['event_type'])
    op.create_index('idx_webhook_events_repo_full_name', 'github_webhook_events', ['repo_full_name'])
    op.create_index('idx_webhook_events_created_at', 'github_webhook_events', ['created_at'])
    op.create_index('idx_webhook_events_processed', 'github_webhook_events', ['processed'])


def downgrade():
    op.drop_index('idx_webhook_events_processed', table_name='github_webhook_events')
    op.drop_index('idx_webhook_events_created_at', table_name='github_webhook_events')
    op.drop_index('idx_webhook_events_repo_full_name', table_name='github_webhook_events')
    op.drop_index('idx_webhook_events_event_type', table_name='github_webhook_events')
    op.drop_index('idx_webhook_events_delivery_id', table_name='github_webhook_events')
    op.drop_table('github_webhook_events')

