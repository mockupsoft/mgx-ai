"""Agent core tables - definitions, instances, contexts

Revision ID: 004_agent_core
Revises: 003_repository_links
Create Date: 2024-12-14

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004_agent_core"
down_revision = "003_repository_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agent_definitions table
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("agent_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("config_schema", sa.JSON(), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_agent_definitions_slug"),
    )
    op.create_index(op.f("ix_agent_definitions_id"), "agent_definitions", ["id"], unique=False)
    op.create_index(op.f("ix_agent_definitions_name"), "agent_definitions", ["name"], unique=False)
    op.create_index(op.f("ix_agent_definitions_slug"), "agent_definitions", ["slug"], unique=False)
    op.create_index(op.f("ix_agent_definitions_agent_type"), "agent_definitions", ["agent_type"], unique=False)
    op.create_index(op.f("ix_agent_definitions_is_enabled"), "agent_definitions", ["is_enabled"], unique=False)

    # Create agent_instances table
    op.create_table(
        "agent_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("definition_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Enum("idle", "initializing", "active", "busy", "error", "offline", name="agentstatus"), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["definition_id"], ["agent_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_instances_id"), "agent_instances", ["id"], unique=False)
    op.create_index(op.f("ix_agent_instances_workspace_id"), "agent_instances", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_agent_instances_project_id"), "agent_instances", ["project_id"], unique=False)
    op.create_index(op.f("ix_agent_instances_definition_id"), "agent_instances", ["definition_id"], unique=False)
    op.create_index(op.f("ix_agent_instances_status"), "agent_instances", ["status"], unique=False)
    op.create_index(
        op.f("ix_agent_instances_workspace_project"), "agent_instances", ["workspace_id", "project_id"], unique=False
    )

    # Add FK constraint for workspace/project pair (cannot add in create_table due to batch operations)
    with op.batch_alter_table("agent_instances") as batch_op:
        batch_op.create_foreign_key(
            "fk_agent_instances_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )

    # Create agent_contexts table
    op.create_table(
        "agent_contexts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("rollback_pointer", sa.Integer(), nullable=True),
        sa.Column("rollback_state", sa.Enum("pending", "success", "failed", name="contextrollbackstate"), nullable=True),
        sa.ForeignKeyConstraint(["instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "name", name="uq_agent_contexts_instance_name"),
    )
    op.create_index(op.f("ix_agent_contexts_id"), "agent_contexts", ["id"], unique=False)
    op.create_index(op.f("ix_agent_contexts_workspace_id"), "agent_contexts", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_agent_contexts_project_id"), "agent_contexts", ["project_id"], unique=False)
    op.create_index(op.f("ix_agent_contexts_instance_id"), "agent_contexts", ["instance_id"], unique=False)
    op.create_index(
        op.f("ix_agent_contexts_workspace_project"), "agent_contexts", ["workspace_id", "project_id"], unique=False
    )

    # Add FK constraint for workspace/project pair
    with op.batch_alter_table("agent_contexts") as batch_op:
        batch_op.create_foreign_key(
            "fk_agent_contexts_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )

    # Create agent_context_versions table
    op.create_table(
        "agent_context_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("context_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["context_id"], ["agent_contexts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("context_id", "version", name="uq_agent_context_versions_context_version"),
    )
    op.create_index(op.f("ix_agent_context_versions_id"), "agent_context_versions", ["id"], unique=False)
    op.create_index(op.f("ix_agent_context_versions_context_id"), "agent_context_versions", ["context_id"], unique=False)
    op.create_index(
        op.f("ix_agent_context_versions_context_version"),
        "agent_context_versions",
        ["context_id", "version"],
        unique=False,
    )


def downgrade() -> None:
    # Drop agent_context_versions
    op.drop_index(op.f("ix_agent_context_versions_context_version"), table_name="agent_context_versions")
    op.drop_index(op.f("ix_agent_context_versions_context_id"), table_name="agent_context_versions")
    op.drop_index(op.f("ix_agent_context_versions_id"), table_name="agent_context_versions")
    op.drop_table("agent_context_versions")

    # Drop agent_contexts
    with op.batch_alter_table("agent_contexts") as batch_op:
        batch_op.drop_constraint("fk_agent_contexts_project_in_workspace", type_="foreignkey")

    op.drop_index(op.f("ix_agent_contexts_workspace_project"), table_name="agent_contexts")
    op.drop_index(op.f("ix_agent_contexts_instance_id"), table_name="agent_contexts")
    op.drop_index(op.f("ix_agent_contexts_project_id"), table_name="agent_contexts")
    op.drop_index(op.f("ix_agent_contexts_workspace_id"), table_name="agent_contexts")
    op.drop_index(op.f("ix_agent_contexts_id"), table_name="agent_contexts")
    op.drop_table("agent_contexts")

    # Drop agent_instances
    with op.batch_alter_table("agent_instances") as batch_op:
        batch_op.drop_constraint("fk_agent_instances_project_in_workspace", type_="foreignkey")

    op.drop_index(op.f("ix_agent_instances_workspace_project"), table_name="agent_instances")
    op.drop_index(op.f("ix_agent_instances_status"), table_name="agent_instances")
    op.drop_index(op.f("ix_agent_instances_definition_id"), table_name="agent_instances")
    op.drop_index(op.f("ix_agent_instances_project_id"), table_name="agent_instances")
    op.drop_index(op.f("ix_agent_instances_workspace_id"), table_name="agent_instances")
    op.drop_index(op.f("ix_agent_instances_id"), table_name="agent_instances")
    op.drop_table("agent_instances")

    # Drop agent_definitions
    op.drop_index(op.f("ix_agent_definitions_is_enabled"), table_name="agent_definitions")
    op.drop_index(op.f("ix_agent_definitions_agent_type"), table_name="agent_definitions")
    op.drop_index(op.f("ix_agent_definitions_slug"), table_name="agent_definitions")
    op.drop_index(op.f("ix_agent_definitions_name"), table_name="agent_definitions")
    op.drop_index(op.f("ix_agent_definitions_id"), table_name="agent_definitions")
    op.drop_table("agent_definitions")
