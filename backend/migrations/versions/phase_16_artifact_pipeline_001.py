"""Phase 16: Artifact & Release Pipeline

Revision ID: phase_16_artifact_pipeline_001
Revises:
Create Date: 2025-12-17

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "phase_16_artifact_pipeline_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    artifact_build_status = postgresql.ENUM(
        "pending",
        "building",
        "completed",
        "failed",
        name="artifactbuildstatus",
    )
    artifact_build_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "artifact_builds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("status", artifact_build_status, nullable=False, server_default="pending"),
        sa.Column("build_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("results", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_artifact_builds_execution", "artifact_builds", ["execution_id"])
    op.create_index("idx_artifact_builds_project", "artifact_builds", ["project_id"])
    op.create_index("idx_artifact_builds_status", "artifact_builds", ["status"])
    op.create_index("idx_artifact_builds_created_at", "artifact_builds", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_artifact_builds_created_at", table_name="artifact_builds")
    op.drop_index("idx_artifact_builds_status", table_name="artifact_builds")
    op.drop_index("idx_artifact_builds_project", table_name="artifact_builds")
    op.drop_index("idx_artifact_builds_execution", table_name="artifact_builds")
    op.drop_table("artifact_builds")

    op.execute("DROP TYPE IF EXISTS artifactbuildstatus;")
