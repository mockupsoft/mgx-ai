"""DeepSite project_rules and stack_hint columns

Revision ID: deepsite_project_rules_001
Revises: deepsite_chat_history_001
Create Date: 2026-04-12 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'deepsite_project_rules_001'
down_revision = 'deepsite_chat_history_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'deepsite_projects',
        sa.Column(
            'project_rules',
            sa.JSON(),
            nullable=True,
            comment='Project-specific rules from first Mike analysis: {stack, rules_text}',
        ),
    )
    op.add_column(
        'deepsite_projects',
        sa.Column(
            'stack_hint',
            sa.String(50),
            nullable=True,
            comment='Selected stack: html/laravel-blade/flutter-laravel/laravel-react',
        ),
    )


def downgrade() -> None:
    op.drop_column('deepsite_projects', 'project_rules')
    op.drop_column('deepsite_projects', 'stack_hint')
