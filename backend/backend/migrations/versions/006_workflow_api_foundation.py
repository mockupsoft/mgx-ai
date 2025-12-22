"""Workflow API foundation

Revision ID: 006_workflow_api_foundation
Revises: 005_agent_messages
Create Date: 2025-12-15

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "006_workflow_api_foundation"
down_revision = "005_agent_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    workflowstatus = sa.Enum("pending", "running", "completed", "failed", "cancelled", "timeout", name="workflowstatus")
    workflowstepstatus = sa.Enum("pending", "running", "completed", "failed", "cancelled", "skipped", name="workflowstepstatus")
    workflowsteptype = sa.Enum("task", "condition", "parallel", "sequential", "agent", name="workflowsteptype")
    
    workflowstatus.create(op.get_bind())
    workflowstepstatus.create(op.get_bind())
    workflowsteptype.create(op.get_bind())

    # Create workflow_definitions table
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_workflow_definitions_id"), "workflow_definitions", ["id"], unique=False)
    op.create_index("idx_workflow_definitions_workspace_project", "workflow_definitions", ["workspace_id", "project_id"], unique=False)
    op.create_index("idx_workflow_definitions_name_version", "workflow_definitions", ["name", "version"], unique=False)

    # Add workspace/project FK constraint
    with op.batch_alter_table("workflow_definitions") as batch_op:
        batch_op.create_foreign_key(
            "fk_workflow_definitions_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )

    # Create unique constraint on name/version per workspace/project
    op.create_unique_constraint(
        "uq_workflow_definitions_unique",
        "workflow_definitions",
        ["workspace_id", "project_id", "name", "version"]
    )

    # Create workflow_steps table
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "step_type",
            sa.Enum("task", "condition", "parallel", "sequential", "agent", name="workflowsteptype"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=True),
        sa.Column("agent_definition_id", sa.String(length=36), nullable=True),
        sa.Column("agent_instance_id", sa.String(length=36), nullable=True),
        sa.Column("depends_on_steps", sa.JSON(), nullable=False),
        sa.Column("condition_expression", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["agent_definition_id"], ["agent_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_workflow_steps_id"), "workflow_steps", ["id"], unique=False)
    op.create_index("idx_workflow_steps_workflow_order", "workflow_steps", ["workflow_id", "step_order"], unique=False)
    op.create_index("idx_workflow_steps_agent_definition", "workflow_steps", ["agent_definition_id"], unique=False)
    op.create_index("idx_workflow_steps_agent_instance", "workflow_steps", ["agent_instance_id"], unique=False)

    # Create unique constraint on workflow/name
    op.create_unique_constraint(
        "uq_workflow_steps_workflow_name",
        "workflow_steps",
        ["workflow_id", "name"]
    )

    # Create workflow_variables table
    op.create_table(
        "workflow_variables",
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=50), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("default_value", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_workflow_variables_id"), "workflow_variables", ["id"], unique=False)
    op.create_index("idx_workflow_variables_workflow", "workflow_variables", ["workflow_id"], unique=False)

    # Create unique constraint on workflow/name for variables
    op.create_unique_constraint(
        "uq_workflow_variables_workflow_name",
        "workflow_variables",
        ["workflow_id", "name"]
    )

    # Create workflow_executions table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("execution_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", "cancelled", "timeout", name="workflowstatus"),
            nullable=False,
        ),
        sa.Column("input_variables", sa.JSON(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_workflow_executions_id"), "workflow_executions", ["id"], unique=False)
    op.create_index("idx_workflow_executions_workflow", "workflow_executions", ["workflow_id"], unique=False)
    op.create_index("idx_workflow_executions_status", "workflow_executions", ["status"], unique=False)
    op.create_index("idx_workflow_executions_started_at", "workflow_executions", ["started_at"], unique=False)
    op.create_index("idx_workflow_executions_workspace_status", "workflow_executions", ["workspace_id", "status"], unique=False)

    # Add workspace/project FK constraint
    with op.batch_alter_table("workflow_executions") as batch_op:
        batch_op.create_foreign_key(
            "fk_workflow_executions_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )

    # Create workflow_step_executions table
    op.create_table(
        "workflow_step_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("step_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", "cancelled", "skipped", name="workflowstepstatus"),
            nullable=False,
        ),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["workflow_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_workflow_step_executions_id"), "workflow_step_executions", ["id"], unique=False)
    op.create_index("idx_workflow_step_executions_execution", "workflow_step_executions", ["execution_id"], unique=False)
    op.create_index("idx_workflow_step_executions_step", "workflow_step_executions", ["step_id"], unique=False)
    op.create_index("idx_workflow_step_executions_status", "workflow_step_executions", ["status"], unique=False)
    op.create_index("idx_workflow_step_executions_started_at", "workflow_step_executions", ["started_at"], unique=False)

    # Create unique constraint on execution/step
    op.create_unique_constraint(
        "uq_workflow_step_executions_execution_step",
        "workflow_step_executions",
        ["execution_id", "step_id"]
    )


def downgrade() -> None:
    # Drop workflow_step_executions table
    op.drop_table("workflow_step_executions")

    # Drop workflow_executions table
    op.drop_table("workflow_executions")

    # Drop workflow_variables table
    op.drop_table("workflow_variables")

    # Drop workflow_steps table
    op.drop_table("workflow_steps")

    # Drop workflow_definitions table
    op.drop_table("workflow_definitions")

    # Drop enum types
    try:
        sa.Enum(name="workflowstepstatus").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
    
    try:
        sa.Enum(name="workflowstatus").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
    
    try:
        sa.Enum(name="workflowsteptype").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass