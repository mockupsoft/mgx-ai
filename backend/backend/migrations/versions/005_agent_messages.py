"""Agent message log table

Revision ID: 005_agent_messages
Revises: 004_agent_core
Create Date: 2025-12-14

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_agent_messages"
down_revision = "004_agent_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_messages",
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
        sa.Column("agent_instance_id", sa.String(length=36), nullable=False),
        sa.Column(
            "direction",
            sa.Enum("inbound", "outbound", "system", name="agentmessagedirection"),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["task_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_agent_messages_id"), "agent_messages", ["id"], unique=False)
    op.create_index(op.f("ix_agent_messages_workspace_id"), "agent_messages", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_agent_messages_project_id"), "agent_messages", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_agent_messages_agent_instance_id"),
        "agent_messages",
        ["agent_instance_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_messages_direction"), "agent_messages", ["direction"], unique=False)
    op.create_index(
        op.f("ix_agent_messages_correlation_id"),
        "agent_messages",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_messages_task_id"), "agent_messages", ["task_id"], unique=False)
    op.create_index(op.f("ix_agent_messages_run_id"), "agent_messages", ["run_id"], unique=False)
    op.create_index(
        "idx_agent_messages_instance_created_at",
        "agent_messages",
        ["agent_instance_id", "created_at"],
        unique=False,
    )

    with op.batch_alter_table("agent_messages") as batch_op:
        batch_op.create_foreign_key(
            "fk_agent_messages_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_messages") as batch_op:
        batch_op.drop_constraint("fk_agent_messages_project_in_workspace", type_="foreignkey")

    op.drop_index("idx_agent_messages_instance_created_at", table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_run_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_task_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_correlation_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_direction"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_agent_instance_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_project_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_workspace_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_id"), table_name="agent_messages")

    op.drop_table("agent_messages")

    # Cleanup enum type on Postgres
    try:
        sa.Enum(name="agentmessagedirection").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
