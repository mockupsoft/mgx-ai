"""Repository links

Revision ID: 003_repository_links
Revises: 002_workspace_project
Create Date: 2025-12-13

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_repository_links"
down_revision = "002_workspace_project"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repository_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("GITHUB", name="repositoryprovider"),
            nullable=False,
        ),
        sa.Column("repo_full_name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("CONNECTED", "DISCONNECTED", "ERROR", name="repositorylinkstatus"),
            nullable=False,
        ),
        sa.Column("auth_payload", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "provider",
            "repo_full_name",
            name="uq_repository_links_project_provider_repo",
        ),
    )

    op.create_index(op.f("ix_repository_links_id"), "repository_links", ["id"], unique=False)
    op.create_index(op.f("ix_repository_links_project_id"), "repository_links", ["project_id"], unique=False)
    op.create_index(op.f("ix_repository_links_provider"), "repository_links", ["provider"], unique=False)
    op.create_index(op.f("ix_repository_links_repo_full_name"), "repository_links", ["repo_full_name"], unique=False)
    op.create_index(op.f("ix_repository_links_status"), "repository_links", ["status"], unique=False)

    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("repo_full_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("default_branch", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("primary_repository_link_id", sa.String(length=36), nullable=True))
        batch_op.create_index(op.f("ix_projects_repo_full_name"), ["repo_full_name"], unique=False)
        batch_op.create_index(op.f("ix_projects_primary_repository_link_id"), ["primary_repository_link_id"], unique=False)



def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_index(op.f("ix_projects_primary_repository_link_id"))
        batch_op.drop_index(op.f("ix_projects_repo_full_name"))
        batch_op.drop_column("primary_repository_link_id")
        batch_op.drop_column("default_branch")
        batch_op.drop_column("repo_full_name")

    op.drop_index(op.f("ix_repository_links_status"), table_name="repository_links")
    op.drop_index(op.f("ix_repository_links_repo_full_name"), table_name="repository_links")
    op.drop_index(op.f("ix_repository_links_provider"), table_name="repository_links")
    op.drop_index(op.f("ix_repository_links_project_id"), table_name="repository_links")
    op.drop_index(op.f("ix_repository_links_id"), table_name="repository_links")

    op.drop_table("repository_links")
