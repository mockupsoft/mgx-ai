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
    Boolean,
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
from .enums import (
    AgentMessageDirection,
    AgentStatus,
    ArtifactType,
    ContextRollbackState,
    MetricType,
    RepositoryLinkStatus,
    RepositoryProvider,
    RunStatus,
    TaskStatus,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
    SandboxExecutionStatus,
    SandboxExecutionLanguage,
    QualityGateType,
    QualityGateStatus,
    GateSeverity,
    AuditLogStatus,
    AuditAction,
    PermissionResource,
    PermissionAction,
    RoleName,
    SecretType,
    SecretRotationPolicy,
    SecretAuditAction,
)


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

    # Primary repository reference (optional)
    repo_full_name = Column(
        String(255),
        index=True,
        comment="Primary linked repository full name (e.g. owner/repo)",
    )
    default_branch = Column(String(255), comment="Reference/default branch for the primary repository")
    primary_repository_link_id = Column(
        String(36),
        index=True,
        comment="RepositoryLink id used as the project's primary repository (no FK constraint)",
    )

    # Git preferences
    run_branch_prefix = Column(String(255), default="mgx", comment="Branch prefix for task runs (e.g., 'mgx' -> mgx/task-name/run-1)")
    commit_template = Column(Text, comment="Template for commit messages (supports {task_name}, {run_number} placeholders)")

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
        UniqueConstraint("workspace_id", "id", name="uq_projects_workspace_id_id"),
        Index("idx_projects_workspace_id", "workspace_id"),
    )

    workspace = relationship("Workspace", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    repository_links = relationship(
        "RepositoryLink",
        back_populates="project",
        cascade="all, delete-orphan",
        foreign_keys="RepositoryLink.project_id",
    )


    def __repr__(self) -> str:
        return f"<Project(id={self.id}, workspace_id='{self.workspace_id}', slug='{self.slug}')>"


class RepositoryLink(Base, TimestampMixin, SerializationMixin):
    """Link between a Project and an external Git repository."""

    __tablename__ = "repository_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider = Column(SQLEnum(RepositoryProvider), nullable=False, index=True)
    repo_full_name = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Normalized full repository name (e.g. owner/repo)",
    )
    default_branch = Column(String(255), comment="Remote default branch")

    status = Column(
        SQLEnum(RepositoryLinkStatus),
        nullable=False,
        default=RepositoryLinkStatus.CONNECTED,
        index=True,
    )

    auth_payload = Column(JSON, nullable=False, default=dict, comment="Auth metadata (installation_id, etc.)")
    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    last_validated_at = Column(DateTime(timezone=True), comment="Last time access was validated")

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "provider",
            "repo_full_name",
            name="uq_repository_links_project_provider_repo",
        ),
        Index("idx_repository_links_project_provider", "project_id", "provider"),
    )

    project = relationship("Project", back_populates="repository_links", foreign_keys=[project_id])

    def __repr__(self) -> str:
        return f"<RepositoryLink(id={self.id}, provider='{self.provider}', repo='{self.repo_full_name}')>"


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

    # Git preferences (can override project defaults)
    run_branch_prefix = Column(String(255), comment="Branch prefix for this task's runs (overrides project setting)")
    commit_template = Column(Text, comment="Commit message template for this task (overrides project setting)")

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

    # Git metadata
    branch_name = Column(String(255), index=True, comment="Git branch created for this run")
    commit_sha = Column(String(64), comment="Latest commit SHA from this run")
    pr_url = Column(String(512), comment="Pull request URL if created")
    git_status = Column(String(50), comment="Git operation status (pending, branch_created, committed, pushed, pr_opened, failed)")

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


class AgentDefinition(Base, TimestampMixin, SerializationMixin):
    """Global agent definition with metadata and capabilities."""

    __tablename__ = "agent_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    name = Column(String(255), nullable=False, index=True, comment="Agent name")
    slug = Column(String(255), nullable=False, unique=True, index=True, comment="Unique slug identifier")
    agent_type = Column(String(100), nullable=False, index=True, comment="Agent type/class name")
    description = Column(Text, comment="Agent description")

    capabilities = Column(JSON, nullable=False, default=list, comment="List of agent capabilities")
    config_schema = Column(JSON, comment="JSON schema for agent configuration")
    meta_data = Column(JSON, nullable=False, default=dict, comment="Agent metadata")

    is_enabled = Column(Boolean, default=True, nullable=False, index=True, comment="Whether the agent is enabled globally")

    __table_args__ = (
        Index("idx_agent_definitions_slug", "slug"),
        Index("idx_agent_definitions_type", "agent_type"),
    )

    instances = relationship("AgentInstance", back_populates="definition", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AgentDefinition(id={self.id}, slug='{self.slug}', type='{self.agent_type}')>"


class AgentInstance(Base, TimestampMixin, SerializationMixin):
    """Workspace-/project-scoped agent instantiation."""

    __tablename__ = "agent_instances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    definition_id = Column(String(36), ForeignKey("agent_definitions.id", ondelete="RESTRICT"), nullable=False, index=True)

    name = Column(String(255), nullable=False, comment="Instance name (can differ from definition)")
    status = Column(SQLEnum(AgentStatus), nullable=False, default=AgentStatus.IDLE, index=True)

    config = Column(JSON, nullable=False, default=dict, comment="Instance-specific configuration")
    state = Column(JSON, comment="Current runtime state")

    last_heartbeat = Column(DateTime(timezone=True), comment="Last heartbeat timestamp")
    last_error = Column(Text, comment="Last error message")

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_agent_instances_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_agent_instances_definition", "definition_id"),
        Index("idx_agent_instances_workspace_project", "workspace_id", "project_id"),
        Index("idx_agent_instances_status", "status"),
    )

    definition = relationship("AgentDefinition", back_populates="instances")
    workspace = relationship("Workspace")
    project = relationship("Project")
    contexts = relationship("AgentContext", back_populates="instance", cascade="all, delete-orphan")
    messages = relationship("AgentMessage", back_populates="instance", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AgentInstance(id={self.id}, name='{self.name}', status='{self.status}')>"


class AgentContext(Base, TimestampMixin, SerializationMixin):
    """Persistent shared context for agents with versioning."""

    __tablename__ = "agent_contexts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    instance_id = Column(String(36), ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False, comment="Context name/identifier")
    current_version = Column(Integer, default=0, nullable=False, comment="Current version number")

    rollback_pointer = Column(Integer, comment="Version to rollback to (if any)")
    rollback_state = Column(SQLEnum(ContextRollbackState), comment="State of rollback operation")

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_agent_contexts_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_agent_contexts_instance", "instance_id"),
        Index("idx_agent_contexts_workspace_project", "workspace_id", "project_id"),
        UniqueConstraint("instance_id", "name", name="uq_agent_contexts_instance_name"),
    )

    instance = relationship("AgentInstance", back_populates="contexts")
    workspace = relationship("Workspace")
    project = relationship("Project")
    versions = relationship("AgentContextVersion", back_populates="context", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AgentContext(id={self.id}, name='{self.name}', version={self.current_version})>"


class AgentContextVersion(Base, TimestampMixin, SerializationMixin):
    """Versioned snapshot of agent context state."""

    __tablename__ = "agent_context_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    context_id = Column(String(36), ForeignKey("agent_contexts.id", ondelete="CASCADE"), nullable=False, index=True)

    version = Column(Integer, nullable=False, comment="Version number (sequence)")
    data = Column(JSON, nullable=False, default=dict, comment="Context data snapshot")

    change_description = Column(Text, comment="Description of changes in this version")
    created_by = Column(String(255), comment="User/agent who created this version")

    __table_args__ = (
        Index("idx_agent_context_versions_context", "context_id"),
        Index("idx_agent_context_versions_version", "context_id", "version"),
        UniqueConstraint("context_id", "version", name="uq_agent_context_versions_context_version"),
    )

    context = relationship("AgentContext", back_populates="versions")

    def __repr__(self) -> str:
        return f"<AgentContextVersion(context_id={self.context_id}, version={self.version})>"


class AgentMessage(Base, TimestampMixin, SerializationMixin):
    """Persistent agent message log entry."""

    __tablename__ = "agent_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    agent_instance_id = Column(
        String(36),
        ForeignKey("agent_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    direction = Column(SQLEnum(AgentMessageDirection), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)

    correlation_id = Column(String(255), index=True)

    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    run_id = Column(String(36), ForeignKey("task_runs.id", ondelete="SET NULL"), index=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_agent_messages_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_agent_messages_instance_created_at", "agent_instance_id", "created_at"),
    )

    instance = relationship("AgentInstance", back_populates="messages")
    workspace = relationship("Workspace")
    project = relationship("Project")

    def __repr__(self) -> str:
        return (
            f"<AgentMessage(id={self.id}, agent_instance_id={self.agent_instance_id}, direction={self.direction})>"
        )


class WorkflowDefinition(Base, TimestampMixin, SerializationMixin):
    """Workflow definition with steps and configuration."""

    __tablename__ = "workflow_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    name = Column(String(255), nullable=False, comment="Workflow name")
    description = Column(Text, comment="Workflow description")
    
    version = Column(Integer, nullable=False, default=1, comment="Version number")
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="Whether the workflow is active")

    config = Column(JSON, nullable=False, default=dict, comment="Workflow configuration")
    timeout_seconds = Column(Integer, default=3600, comment="Default timeout in seconds")
    max_retries = Column(Integer, default=3, comment="Default maximum retries per step")

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workflow_definitions_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_workflow_definitions_workspace_project", "workspace_id", "project_id"),
        Index("idx_workflow_definitions_name_version", "name", "version"),
        UniqueConstraint("workspace_id", "project_id", "name", "version", name="uq_workflow_definitions_unique"),
    )

    workspace = relationship("Workspace")
    project = relationship("Project")
    steps = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")
    variables = relationship("WorkflowVariable", back_populates="workflow", cascade="all, delete-orphan")
    executions = relationship("WorkflowExecution", back_populates="definition", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkflowDefinition(id={self.id}, name='{self.name}', version={self.version})>"


class WorkflowStep(Base, TimestampMixin, SerializationMixin):
    """Individual step within a workflow definition."""

    __tablename__ = "workflow_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workflow_id = Column(String(36), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False, comment="Step name")
    step_type = Column(SQLEnum(WorkflowStepType), nullable=False, comment="Type of step")
    step_order = Column(Integer, nullable=False, comment="Order in execution sequence")

    config = Column(JSON, nullable=False, default=dict, comment="Step configuration")
    timeout_seconds = Column(Integer, comment="Step-specific timeout override")
    max_retries = Column(Integer, comment="Step-specific retry override")

    # Agent requirements
    agent_definition_id = Column(String(36), ForeignKey("agent_definitions.id", ondelete="RESTRICT"), nullable=True, index=True)
    agent_instance_id = Column(String(36), ForeignKey("agent_instances.id", ondelete="RESTRICT"), nullable=True, index=True)

    # Dependencies
    depends_on_steps = Column(JSON, nullable=False, default=list, comment="List of step IDs this step depends on")
    condition_expression = Column(Text, comment="Conditional expression for step execution")

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_workflow_steps_workflow_order", "workflow_id", "step_order"),
        Index("idx_workflow_steps_agent_definition", "agent_definition_id"),
        Index("idx_workflow_steps_agent_instance", "agent_instance_id"),
        UniqueConstraint("workflow_id", "name", name="uq_workflow_steps_workflow_name"),
    )

    workflow = relationship("WorkflowDefinition", back_populates="steps")
    agent_definition = relationship("AgentDefinition")
    agent_instance = relationship("AgentInstance")
    executions = relationship("WorkflowStepExecution", back_populates="step", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkflowStep(id={self.id}, name='{self.name}', type='{self.step_type}', order={self.step_order})>"


class WorkflowVariable(Base, TimestampMixin, SerializationMixin):
    """Variable definitions for workflows."""

    __tablename__ = "workflow_variables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workflow_id = Column(String(36), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False, comment="Variable name")
    data_type = Column(String(50), nullable=False, comment="Data type (string, int, float, bool, json)")
    is_required = Column(Boolean, default=False, nullable=False, comment="Whether the variable is required")

    default_value = Column(JSON, comment="Default value")
    description = Column(Text, comment="Variable description")

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_workflow_variables_workflow", "workflow_id"),
        UniqueConstraint("workflow_id", "name", name="uq_workflow_variables_workflow_name"),
    )

    workflow = relationship("WorkflowDefinition", back_populates="variables")

    def __repr__(self) -> str:
        return f"<WorkflowVariable(id={self.id}, name='{self.name}', type='{self.data_type}')>"


class WorkflowExecution(Base, TimestampMixin, SerializationMixin):
    """Individual workflow execution tracking."""

    __tablename__ = "workflow_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workflow_id = Column(String(36), ForeignKey("workflow_definitions.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    execution_number = Column(Integer, nullable=False, comment="Sequence number within workflow")
    status = Column(SQLEnum(WorkflowStatus), nullable=False, default=WorkflowStatus.PENDING, index=True)

    # Input parameters
    input_variables = Column(JSON, comment="Input variables passed to the workflow")

    # Results and tracking
    results = Column(JSON, comment="Execution results")
    started_at = Column(DateTime(timezone=True), comment="Execution start time")
    completed_at = Column(DateTime(timezone=True), comment="Execution completion time")
    duration = Column(Float, comment="Duration in seconds")

    error_message = Column(Text, comment="Error message if failed")
    error_details = Column(JSON, comment="Detailed error information")

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workflow_executions_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_workflow_executions_workflow", "workflow_id"),
        Index("idx_workflow_executions_status", "status"),
        Index("idx_workflow_executions_started_at", "started_at"),
        Index("idx_workflow_executions_workspace_status", "workspace_id", "status"),
    )

    definition = relationship("WorkflowDefinition", back_populates="executions")
    workspace = relationship("Workspace")
    project = relationship("Project")
    step_executions = relationship("WorkflowStepExecution", back_populates="execution", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, workflow_id='{self.workflow_id}', status='{self.status}')>"

    @property
    def is_success(self) -> bool:
        return self.status == WorkflowStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == WorkflowStatus.FAILED


class WorkflowStepExecution(Base, TimestampMixin, SerializationMixin):
    """Individual step execution tracking."""

    __tablename__ = "workflow_step_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    execution_id = Column(String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="RESTRICT"), nullable=False, index=True)

    status = Column(SQLEnum(WorkflowStepStatus), nullable=False, default=WorkflowStepStatus.PENDING, index=True)

    # Step execution data
    input_data = Column(JSON, comment="Input data passed to the step")
    output_data = Column(JSON, comment="Output data from the step")
    results = Column(JSON, comment="Step execution results")

    started_at = Column(DateTime(timezone=True), comment="Step start time")
    completed_at = Column(DateTime(timezone=True), comment="Step completion time")
    duration = Column(Float, comment="Duration in seconds")

    retry_count = Column(Integer, default=0, comment="Number of retries attempted")
    error_message = Column(Text, comment="Error message if failed")
    error_details = Column(JSON, comment="Detailed error information")

    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_workflow_step_executions_execution", "execution_id"),
        Index("idx_workflow_step_executions_step", "step_id"),
        Index("idx_workflow_step_executions_status", "status"),
        Index("idx_workflow_step_executions_started_at", "started_at"),
        UniqueConstraint("execution_id", "step_id", name="uq_workflow_step_executions_execution_step"),
    )

    execution = relationship("WorkflowExecution", back_populates="step_executions")
    step = relationship("WorkflowStep", back_populates="executions")

    def __repr__(self) -> str:
        return f"<WorkflowStepExecution(id={self.id}, step_id='{self.step_id}', status='{self.status}')>"

    @property
    def is_success(self) -> bool:
        return self.status == WorkflowStepStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == WorkflowStepStatus.FAILED


class SandboxExecution(Base, TimestampMixin, SerializationMixin):
    """Sandboxed code execution record."""

    __tablename__ = "sandbox_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    execution_type = Column(SQLEnum(SandboxExecutionLanguage), nullable=False, index=True)
    status = Column(SQLEnum(SandboxExecutionStatus), nullable=False, default=SandboxExecutionStatus.PENDING, index=True)

    # Execution details
    command = Column(Text, nullable=False, comment="Command executed")
    code = Column(Text, comment="Source code executed")
    
    # Results
    stdout = Column(Text, comment="Standard output")
    stderr = Column(Text, comment="Standard error")
    exit_code = Column(Integer, comment="Process exit code")
    success = Column(Boolean, comment="Execution success status")
    
    # Resource usage
    duration_ms = Column(Integer, comment="Execution duration in milliseconds")
    max_memory_mb = Column(Integer, comment="Maximum memory used in MB")
    cpu_percent = Column(Float, comment="CPU usage percentage")
    network_io = Column(BigInteger, comment="Network I/O in bytes")
    disk_io = Column(BigInteger, comment="Disk I/O in bytes")
    
    # Error information
    error_type = Column(String(255), comment="Error type/category")
    error_message = Column(Text, comment="Error message")
    timeout_seconds = Column(Integer, default=30, comment="Execution timeout in seconds")
    
    # Container information
    container_id = Column(String(255), comment="Docker container ID")
    
    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_sandbox_executions_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_sandbox_executions_workspace_project", "workspace_id", "project_id"),
        Index("idx_sandbox_executions_status", "status"),
        Index("idx_sandbox_executions_execution_type", "execution_type"),
        Index("idx_sandbox_executions_created_at", "created_at"),
    )

    workspace = relationship("Workspace")
    project = relationship("Project")

    def __repr__(self) -> str:
        return f"<SandboxExecution(id={self.id}, execution_type='{self.execution_type}', status='{self.status}')>"

    @property
    def is_success(self) -> bool:
        return self.status == SandboxExecutionStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status in [SandboxExecutionStatus.FAILED, SandboxExecutionStatus.TIMEOUT]

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.duration_ms / 1000.0 if self.duration_ms else 0.0


class QualityGate(Base, TimestampMixin, SerializationMixin):
    """Quality gate configuration and definition."""

    __tablename__ = "quality_gates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)

    name = Column(String(255), nullable=False, comment="Gate name")
    gate_type = Column(SQLEnum(QualityGateType), nullable=False, index=True, comment="Type of quality gate")
    
    # Gate configuration
    is_enabled = Column(Boolean, default=True, nullable=False, comment="Whether this gate is enabled")
    is_blocking = Column(Boolean, default=True, nullable=False, comment="Whether gate failure blocks deployment")
    
    # Threshold configuration (JSON for flexibility)
    threshold_config = Column("threshold_config", JSON, nullable=False, default=dict, comment="Gate-specific threshold configuration")
    
    # Gate status
    status = Column(SQLEnum(QualityGateStatus), nullable=False, default=QualityGateStatus.PENDING, index=True)
    last_evaluation_at = Column(DateTime(timezone=True), comment="Last time this gate was evaluated")
    last_result = Column(Boolean, comment="Last evaluation result")
    
    # Statistics
    total_evaluations = Column(Integer, default=0, comment="Total number of evaluations")
    passed_evaluations = Column(Integer, default=0, comment="Number of passed evaluations")
    failed_evaluations = Column(Integer, default=0, comment="Number of failed evaluations")
    
    # Metadata
    description = Column(Text, comment="Gate description")
    meta_data = Column("metadata", JSON, nullable=False, default=dict)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_quality_gates_project_in_workspace",
            ondelete="RESTRICT",
        ),
        Index("idx_quality_gates_workspace_project", "workspace_id", "project_id"),
        Index("idx_quality_gates_type", "gate_type"),
        Index("idx_quality_gates_status", "status"),
        UniqueConstraint("workspace_id", "project_id", "gate_type", name="uq_quality_gates_unique_type"),
    )

    workspace = relationship("Workspace")
    project = relationship("Project")
    executions = relationship("GateExecution", back_populates="gate", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<QualityGate(id={self.id}, gate_type='{self.gate_type}', status='{self.status}')>"

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_evaluations == 0:
            return 0.0
        return (self.passed_evaluations / self.total_evaluations) * 100

    @property
    def is_healthy(self) -> bool:
        """Check if gate is in a healthy state."""
        return self.pass_rate >= 80.0  # 80% pass rate threshold


class GateExecution(Base, TimestampMixin, SerializationMixin):
    """Individual execution of a quality gate."""

    __tablename__ = "gate_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    gate_id = Column(String(36), ForeignKey("quality_gates.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Related execution context
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    task_run_id = Column(String(36), ForeignKey("task_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    sandbox_execution_id = Column(String(36), ForeignKey("sandbox_executions.id", ondelete="SET NULL"), nullable=True, index=True)

    # Execution details
    status = Column(SQLEnum(QualityGateStatus), nullable=False, default=QualityGateStatus.PENDING, index=True)
    started_at = Column(DateTime(timezone=True), comment="Execution start time")
    completed_at = Column(DateTime(timezone=True), comment="Execution completion time")
    duration_ms = Column(Integer, comment="Execution duration in milliseconds")
    
    # Results
    passed = Column(Boolean, comment="Execution result")
    passed_with_warnings = Column(Boolean, default=False, comment="Passed but with warnings")
    error_message = Column(Text, comment="Error message if failed")
    
    # Detailed results (JSON for flexibility)
    result_details = Column("result_details", JSON, comment="Detailed gate-specific results")
    metrics = Column(JSON, comment="Metrics captured during execution")
    recommendations = Column(JSON, comment="Recommendations for improvement")
    
    # Issue tracking
    issues_found = Column(Integer, default=0, comment="Number of issues found")
    critical_issues = Column(Integer, default=0, comment="Number of critical issues")
    high_issues = Column(Integer, default=0, comment="Number of high severity issues")
    medium_issues = Column(Integer, default=0, comment="Number of medium severity issues")
    low_issues = Column(Integer, default=0, comment="Number of low severity issues")
    
    # Configuration snapshot
    config_used = Column(JSON, comment="Configuration used for this execution")

    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "workspace_id"],
            ["tasks.workspace_id", "tasks.id"],
            name="fk_gate_executions_task",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["task_run_id", "workspace_id"],
            ["task_runs.workspace_id", "task_runs.id"],
            name="fk_gate_executions_task_run",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["sandbox_execution_id", "workspace_id"],
            ["sandbox_executions.workspace_id", "sandbox_executions.id"],
            name="fk_gate_executions_sandbox_execution",
            ondelete="SET NULL",
        ),
        Index("idx_gate_executions_gate_id", "gate_id"),
        Index("idx_gate_executions_task_run", "task_run_id"),
        Index("idx_gate_executions_sandbox_execution", "sandbox_execution_id"),
        Index("idx_gate_executions_status", "status"),
        Index("idx_gate_executions_started_at", "started_at"),
    )

    gate = relationship("QualityGate", back_populates="executions")
    task = relationship("Task")
    task_run = relationship("TaskRun")
    sandbox_execution = relationship("SandboxExecution")

    def __repr__(self) -> str:
        return f"<GateExecution(id={self.id}, gate_id='{self.gate_id}', status='{self.status}')>"

    @property
    def is_success(self) -> bool:
        return self.status == QualityGateStatus.PASSED

    @property
    def is_failure(self) -> bool:
        return self.status == QualityGateStatus.FAILED

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.duration_ms / 1000.0 if self.duration_ms else 0.0

    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return self.critical_issues + self.high_issues + self.medium_issues + self.low_issues


class Role(Base, TimestampMixin, SerializationMixin):
    """Role definition for RBAC system."""
    
    __tablename__ = "roles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(SQLEnum(RoleName), nullable=False, index=True)
    permissions = Column(JSON, nullable=False, default=list, comment="List of permission strings (e.g., 'tasks:*', 'users:read')")
    
    description = Column(Text, comment="Role description")
    
    is_system_role = Column(Boolean, default=False, nullable=False, index=True, comment="Whether this is a system-defined role")
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_roles_workspace_name"),
        Index("idx_roles_workspace_name", "workspace_id", "name"),
    )
    
    workspace = relationship("Workspace", back_populates="roles")
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    permissions_table = relationship("Permission", back_populates="role", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Role(id={self.id}, workspace_id='{self.workspace_id}', name='{self.name}')>"


class UserRole(Base, TimestampMixin, SerializationMixin):
    """User-role assignments for RBAC system."""
    
    __tablename__ = "user_roles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    user_id = Column(String(36), nullable=False, index=True, comment="User ID (references external auth system)")
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    assigned_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    assigned_by_user_id = Column(String(36), nullable=True, comment="User ID who assigned this role")
    
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    __table_args__ = (
        Index("idx_user_roles_user_workspace", "user_id", "workspace_id"),
        Index("idx_user_roles_role", "role_id"),
        UniqueConstraint("user_id", "workspace_id", "role_id", name="uq_user_roles_unique_assignment"),
    )
    
    workspace = relationship("Workspace")
    role = relationship("Role", back_populates="user_roles")
    
    def __repr__(self) -> str:
        return f"<UserRole(id={self.id}, user_id='{self.user_id}', workspace_id='{self.workspace_id}', role_id='{self.role_id}')>"


class Permission(Base, TimestampMixin, SerializationMixin):
    """Permission definitions for RBAC system."""
    
    __tablename__ = "permissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    resource = Column(SQLEnum(PermissionResource), nullable=False, index=True)
    action = Column(SQLEnum(PermissionAction), nullable=False, index=True)
    
    conditions = Column(JSON, comment="Additional conditions for this permission (e.g., resource ownership)")
    
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_permissions_workspace",
            ondelete="CASCADE",
        ),
        Index("idx_permissions_role_resource_action", "role_id", "resource", "action"),
        UniqueConstraint("workspace_id", "role_id", "resource", "action", name="uq_permissions_unique"),
    )
    
    workspace = relationship("Workspace")
    role = relationship("Role", back_populates="permissions_table")
    
    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, role_id='{self.role_id}', resource='{self.resource}', action='{self.action}')>"


class AuditLog(Base, TimestampMixin, SerializationMixin):
    """Audit log for tracking all user actions and changes."""
    
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    
    user_id = Column(String(36), nullable=True, index=True, comment="User ID who performed the action (nullable for system actions)")
    
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True, comment="Type of resource affected (task, workflow, etc.)")
    resource_id = Column(String(36), nullable=True, index=True, comment="ID of the affected resource")
    
    changes = Column(JSON, comment="Before/after values for changes")
    
    status = Column(SQLEnum(AuditLogStatus), nullable=False, default=AuditLogStatus.SUCCESS, index=True)
    
    ip_address = Column(String(45), comment="Client IP address")
    user_agent = Column(Text, comment="Client user agent")
    
    execution_time_ms = Column(Integer, comment="Execution time in milliseconds")
    error_message = Column(Text, comment="Error message if action failed")
    
    __table_args__ = (
        Index("idx_audit_logs_workspace_timestamp", "workspace_id", "created_at"),
        Index("idx_audit_logs_user_action", "user_id", "action"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_status", "status"),
    )
    
    workspace = relationship("Workspace")
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, workspace_id='{self.workspace_id}', user_id='{self.user_id}', action='{self.action}')>"


class Secret(Base, TimestampMixin, SerializationMixin):
    """Secure secret storage with encryption and rotation support."""

    __tablename__ = "secrets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True, comment="Secret name (e.g., 'GITHUB_TOKEN', 'DATABASE_PASSWORD')")
    secret_type = Column(SQLEnum(SecretType), nullable=False, comment="Type of secret")
    usage = Column(Text, comment="Description of what the secret is used for")

    # Encrypted value - never store plaintext
    encrypted_value = Column(Text, nullable=False, comment="Encrypted secret value")

    # Rotation configuration
    rotation_policy = Column(SQLEnum(SecretRotationPolicy), nullable=False, default=SecretRotationPolicy.MANUAL, index=True)
    last_rotated_at = Column(DateTime(timezone=True), comment="When the secret was last rotated")
    rotation_due_at = Column(DateTime(timezone=True), comment="When rotation is next due")

    # Audit trail for secret management
    created_by_user_id = Column(String(36), nullable=True, index=True, comment="User who created the secret")
    updated_by_user_id = Column(String(36), nullable=True, index=True, comment="User who last updated the secret")

    # Metadata
    meta_data = Column(JSON, nullable=False, default=dict, comment="Additional secret metadata")
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="Whether the secret is active")

    # Tags for organization
    tags = Column(JSON, comment="Tags for categorizing secrets")

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_secrets_workspace_name"),
        Index("idx_secrets_workspace_type", "workspace_id", "secret_type"),
        Index("idx_secrets_rotation_due", "rotation_due_at"),
        Index("idx_secrets_active", "is_active"),
    )

    workspace = relationship("Workspace")
    audit_logs = relationship("SecretAudit", back_populates="secret", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Secret(id={self.id}, workspace_id='{self.workspace_id}', name='{self.name}', type='{self.secret_type}')>"

    @property
    def is_rotation_due(self) -> bool:
        """Check if the secret is due for rotation."""
        if not self.rotation_due_at:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) >= self.rotation_due_at


class SecretAudit(Base, TimestampMixin, SerializationMixin):
    """Audit trail for secret access and management operations."""

    __tablename__ = "secret_audits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)

    secret_id = Column(String(36), ForeignKey("secrets.id", ondelete="CASCADE"), nullable=False, index=True)

    # Audit details
    action = Column(SQLEnum(SecretAuditAction), nullable=False, index=True, comment="Action performed on the secret")
    user_id = Column(String(36), nullable=True, index=True, comment="User who performed the action")

    # Context information
    ip_address = Column(String(45), comment="IP address of the request")
    user_agent = Column(String(500), comment="User agent of the request")
    request_id = Column(String(100), comment="Unique request identifier")

    # Operation details
    details = Column(JSON, comment="Additional operation details")
    metadata = Column(JSON, comment="Additional metadata")

    # Success/failure tracking
    success = Column(Boolean, default=True, nullable=False, index=True, comment="Whether the operation was successful")
    error_message = Column(Text, comment="Error message if the operation failed")

    __table_args__ = (
        Index("idx_secret_audits_secret_timestamp", "secret_id", "created_at"),
        Index("idx_secret_audits_user_action", "user_id", "action"),
        Index("idx_secret_audits_action_timestamp", "action", "created_at"),
    )

    secret = relationship("Secret", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<SecretAudit(id={self.id}, secret_id='{self.secret_id}', action='{self.action}', user_id='{self.user_id}')>"


Workspace.roles = relationship("Role", back_populates="workspace", cascade="all, delete-orphan")


__all__ = [
    "Workspace",
    "Project",
    "RepositoryLink",
    "Task",
    "TaskRun",
    "MetricSnapshot",
    "Artifact",
    "AgentDefinition",
    "AgentInstance",
    "AgentContext",
    "AgentContextVersion",
    "AgentMessage",
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowVariable",
    "WorkflowExecution",
    "WorkflowStepExecution",
    "SandboxExecution",
    "QualityGate",
    "GateExecution",
    "TaskStatus",
    "RunStatus",
    "MetricType",
    "ArtifactType",
    "RepositoryProvider",
    "RepositoryLinkStatus",
    "AgentStatus",
    "ContextRollbackState",
    "WorkflowStatus",
    "WorkflowStepStatus",
    "WorkflowStepType",
    "SandboxExecutionStatus",
    "SandboxExecutionLanguage",
    "QualityGateType",
    "QualityGateStatus",
    "GateSeverity",
    "Role",
    "UserRole",
    "Permission",
    "AuditLog",
    "Secret",
    "SecretAudit",
]
