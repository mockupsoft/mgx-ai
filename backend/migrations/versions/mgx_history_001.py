"""MGX run history (output/ metadata in PostgreSQL)

Revision ID: mgx_history_001
Revises: deepsite_auth_001
Create Date: 2026-04-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "mgx_history_001"
down_revision = "deepsite_auth_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mgx_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("complexity", sa.String(length=8), nullable=True),
        sa.Column("output_dir", sa.String(length=1024), nullable=True),
        sa.Column("plan_summary", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("results_summary", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_mgx_runs_status", "mgx_runs", ["status"])
    op.create_index("idx_mgx_runs_created_at", "mgx_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_mgx_runs_created_at", table_name="mgx_runs")
    op.drop_index("idx_mgx_runs_status", table_name="mgx_runs")
    op.drop_table("mgx_runs")
