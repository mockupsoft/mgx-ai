# -*- coding: utf-8 -*-
"""backend.db.models.entities

Core database models.

Multi-tenancy hierarchy:
Workspace -> Project -> Task -> TaskRun

MetricSnapshot is scoped to a workspace/project as well.
"""

from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base, SerializationMixin, TimestampMixin
from .enums import ArtifactType, MetricType, RunStatus, TaskStatus


class Workspace(Base, TimestampMixin, SerializationMixin):
    """Top-level tenant container."""

    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="workspace", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, slug='{self.slug}')>"


class Project(Base, TimestampMixin, SerializationMixin):
    """Project within a workspace."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
        UniqueConstraint("workspace_id", "id", name="uq_projects_workspace_id_id"),
        Index("idx_projects_workspace_id", "workspace_id"),
    )

    workspace = relationship("Workspace", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, workspace_id='{self.workspace_id}', slug='{self.slug}')>"


class Task(Base, TimestampMixin, SerializationMixin):
    """Task model representing individual task definitions."""

    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True, comment="Task name")
    description = Column(Text, comment="Task description")

    config = Column(JSON, nullable=False, default=dict, comment="Task configuration")

    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)

    max_rounds = Column(Integer, default=5, comment="Maximum execution rounds")
    max_revision_rounds = Column(Integer, default=2, comment="Maximum revision rounds")
    memory_size = Column(Integer, default=50, comment="Team memory size")

    total_runs = Column(Integer, default=0, comment="Total number of runs")
    successful_runs = Column(Integer, default=0, comment="Successful runs count")
    failed_runs = Column(Integer, default=0, comment="Failed runs count")

    last_run_at = Column(DateTime(timezone=True), comment="Last run timestamp")
    last_run_duration = Column(Float, comment="Last run duration in seconds")
    last_error = Column(Text, comment="Last execution error message")

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_tasks_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_tasks_workspace_project", "workspace_id", "project_id"),
    )

    workspace = relationship("Workspace", back_populates="tasks")
    project = relationship("Project", back_populates="tasks")

    runs = relationship("TaskRun", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, workspace_id='{self.workspace_id}', name='{self.name}', status='{self.status}')>"

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100


class TaskRun(Base, TimestampMixin, SerializationMixin):
    """TaskRun model representing individual executions of tasks."""

    __tablename__ = "task_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    run_number = Column(Integer, nullable=False, comment="Sequence number within task")

    status = Column(SQLEnum(RunStatus), nullable=False, default=RunStatus.PENDING, index=True)

    plan = Column(JSON, comment="Execution plan")
    results = Column(JSON, comment="Execution results")

    started_at = Column(DateTime(timezone=True), comment="Run start time")
    completed_at = Column(DateTime(timezone=True), comment="Run completion time")
    duration = Column(Float, comment="Duration in seconds")

    error_message = Column(Text, comment="Error message if failed")
    error_details = Column(JSON, comment="Detailed error information")

    memory_used = Column(Integer, comment="Memory used in MB")
    round_count = Column(Integer, comment="Number of rounds executed")

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_task_runs_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_task_runs_task_id_status", "task_id", "status"),
        Index("idx_task_runs_started_at", "started_at"),
        Index("idx_task_runs_workspace_status", "workspace_id", "status"),
    )

    task = relationship("Task", back_populates="runs")
    workspace = relationship("Workspace")
    project = relationship("Project")

    metrics = relationship("MetricSnapshot", back_populates="task_run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="task_run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TaskRun(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"

    @property
    def is_success(self) -> bool:
        return self.status == RunStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == RunStatus.FAILED


class MetricSnapshot(Base, TimestampMixin, SerializationMixin):
    """MetricSnapshot model for storing performance and system metrics."""

    __tablename__ = "metric_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    task_run_id = Column(String(36), ForeignKey("task_runs.id", ondelete="SET NULL"), nullable=True, index=True)

    name = Column(String(255), nullable=False, index=True, comment="Metric name")
    metric_type = Column(SQLEnum(MetricType), nullable=False, comment="Type of metric")
    value = Column(Float, nullable=False, comment="Metric value")
    unit = Column(String(50), comment="Unit of measurement")

    labels = Column(JSON, comment="Metric labels/tags")
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Measurement timestamp")

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_metric_snapshots_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_metric_snapshots_task_run_timestamp", "task_run_id", "timestamp"),
        Index("idx_metric_snapshots_name_timestamp", "name", "timestamp"),
        Index("idx_metric_snapshots_workspace_name_timestamp", "workspace_id", "name", "timestamp"),
    )

    task = relationship("Task")
    task_run = relationship("TaskRun", back_populates="metrics")
    workspace = relationship("Workspace")
    project = relationship("Project")

    def __repr__(self) -> str:
        return f"<MetricSnapshot(id={self.id}, name='{self.name}', value={self.value})>"


class Artifact(Base, TimestampMixin, SerializationMixin):
    """Artifact model for storing generated files and outputs."""

    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    task_run_id = Column(String(36), ForeignKey("task_runs.id", ondelete="SET NULL"), nullable=True, index=True)

    name = Column(String(255), nullable=False, comment="Artifact name")
    artifact_type = Column(SQLEnum(ArtifactType), nullable=False, comment="Type of artifact")

    file_path = Column(Text, comment="File path or URL")
    file_size = Column(BigInteger, comment="File size in bytes")
    file_hash = Column(String(64), comment="SHA256 hash for integrity")

    content_type = Column(String(100), comment="MIME type")
    content = Column(Text, comment="Text content or metadata")

    meta_data = Column("metadata", JSON, comment="Additional metadata")

    __table_args__ = (
        Index("idx_artifacts_task_run_type", "task_run_id", "artifact_type"),
        Index("idx_artifacts_file_hash", "file_hash"),
    )

    task = relationship("Task")
    task_run = relationship("TaskRun", back_populates="artifacts")

    def __repr__(self) -> str:
        return f"<Artifact(id={self.id}, name='{self.name}', type='{self.artifact_type}')>"


__all__ = [
    "Workspace",
    "Project",
    "Task",
    "TaskRun",
    "MetricSnapshot",
    "Artifact",
    "TaskStatus",
    "RunStatus",
    "MetricType",
    "ArtifactType",
]
