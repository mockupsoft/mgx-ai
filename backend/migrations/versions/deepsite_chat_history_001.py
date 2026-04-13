"""DeepSite chat_history column

Revision ID: deepsite_chat_history_001
Revises: deepsite_auth_001
Create Date: 2026-04-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'deepsite_chat_history_001'
down_revision = 'deepsite_auth_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'deepsite_projects',
        sa.Column('chat_history', sa.JSON(), nullable=True,
                  comment='Serialized chat timeline: {items, artifacts}'),
    )


def downgrade() -> None:
    op.drop_column('deepsite_projects', 'chat_history')
