"""Workspace & Project multi-tenancy

Revision ID: 002_workspace_project
Revises: 001_initial_schema
Create Date: 2025-12-13

"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002_workspace_project"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    default_workspace_id = str(uuid.uuid4())
    default_project_id = str(uuid.uuid4())

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_index(op.f("ix_workspaces_id"), "workspaces", ["id"], unique=False)
    op.create_index(op.f("ix_workspaces_slug"), "workspaces", ["slug"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_projects_workspace_id_id"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)
    op.create_index(op.f("ix_projects_workspace_id"), "projects", ["workspace_id"], unique=False)

    # Seed default workspace and project for backfilling existing rows
    workspaces_table = sa.table(
        "workspaces",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("metadata", sa.JSON()),
    )
    projects_table = sa.table(
        "projects",
        sa.column("id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("metadata", sa.JSON()),
    )

    op.bulk_insert(
        workspaces_table,
        [
            {
                "id": default_workspace_id,
                "name": "Default Workspace",
                "slug": "default",
                "metadata": {},
            }
        ],
    )
    op.bulk_insert(
        projects_table,
        [
            {
                "id": default_project_id,
                "workspace_id": default_workspace_id,
                "name": "Default Project",
                "slug": "default",
                "metadata": {},
            }
        ],
    )

    # Add tenant columns (nullable first), then backfill, then enforce NOT NULL.
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))

    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))

    with op.batch_alter_table("metric_snapshots") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))

    # Backfill tasks
    op.execute(
        sa.text(
            "UPDATE tasks SET workspace_id = :ws, project_id = :proj "
            "WHERE workspace_id IS NULL OR project_id IS NULL"
        ).bindparams(ws=default_workspace_id, proj=default_project_id)
    )

    # Backfill runs based on parent task
    op.execute(
        sa.text(
            "UPDATE task_runs "
            "SET workspace_id = (SELECT t.workspace_id FROM tasks t WHERE t.id = task_runs.task_id), "
            "    project_id = (SELECT t.project_id FROM tasks t WHERE t.id = task_runs.task_id) "
            "WHERE workspace_id IS NULL OR project_id IS NULL"
        )
    )

    # Backfill metrics based on task_run (preferred) then task
    op.execute(
        sa.text(
            "UPDATE metric_snapshots "
            "SET workspace_id = COALESCE("
            "        (SELECT r.workspace_id FROM task_runs r WHERE r.id = metric_snapshots.task_run_id),"
            "        (SELECT t.workspace_id FROM tasks t WHERE t.id = metric_snapshots.task_id),"
            "        :ws"
            "    ),"
            "    project_id = COALESCE("
            "        (SELECT r.project_id FROM task_runs r WHERE r.id = metric_snapshots.task_run_id),"
            "        (SELECT t.project_id FROM tasks t WHERE t.id = metric_snapshots.task_id),"
            "        :proj"
            "    ) "
            "WHERE workspace_id IS NULL OR project_id IS NULL"
        ).bindparams(ws=default_workspace_id, proj=default_project_id)
    )

    # Add indexes + constraints
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.create_index(op.f("ix_tasks_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_tasks_project_id"), ["project_id"], unique=False)
        batch_op.create_foreign_key("fk_tasks_workspace", "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
        batch_op.create_foreign_key(
            "fk_tasks_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )
        batch_op.alter_column("workspace_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("project_id", existing_type=sa.String(length=36), nullable=False)

    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.create_index(op.f("ix_task_runs_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_task_runs_project_id"), ["project_id"], unique=False)
        batch_op.create_index(op.f("ix_task_runs_workspace_status"), ["workspace_id", "status"], unique=False)
        batch_op.create_foreign_key(
            "fk_task_runs_workspace",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_task_runs_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )
        batch_op.alter_column("workspace_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("project_id", existing_type=sa.String(length=36), nullable=False)

    with op.batch_alter_table("metric_snapshots") as batch_op:
        batch_op.create_index(op.f("ix_metric_snapshots_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_metric_snapshots_project_id"), ["project_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_metric_snapshots_workspace",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_metric_snapshots_project_in_workspace",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )
        batch_op.alter_column("workspace_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("project_id", existing_type=sa.String(length=36), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("metric_snapshots") as batch_op:
        batch_op.drop_constraint("fk_metric_snapshots_project_in_workspace", type_="foreignkey")
        batch_op.drop_constraint("fk_metric_snapshots_workspace", type_="foreignkey")
        batch_op.drop_index(op.f("ix_metric_snapshots_project_id"))
        batch_op.drop_index(op.f("ix_metric_snapshots_workspace_id"))
        batch_op.drop_column("project_id")
        batch_op.drop_column("workspace_id")

    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.drop_constraint("fk_task_runs_project_in_workspace", type_="foreignkey")
        batch_op.drop_constraint("fk_task_runs_workspace", type_="foreignkey")
        batch_op.drop_index(op.f("ix_task_runs_workspace_status"))
        batch_op.drop_index(op.f("ix_task_runs_project_id"))
        batch_op.drop_index(op.f("ix_task_runs_workspace_id"))
        batch_op.drop_column("project_id")
        batch_op.drop_column("workspace_id")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_project_in_workspace", type_="foreignkey")
        batch_op.drop_constraint("fk_tasks_workspace", type_="foreignkey")
        batch_op.drop_index(op.f("ix_tasks_project_id"))
        batch_op.drop_index(op.f("ix_tasks_workspace_id"))
        batch_op.drop_column("project_id")
        batch_op.drop_column("workspace_id")

    op.drop_index(op.f("ix_projects_workspace_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_id"), table_name="projects")
    op.drop_table("projects")

    op.drop_index(op.f("ix_workspaces_slug"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_id"), table_name="workspaces")
    op.drop_table("workspaces")
