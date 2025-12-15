# -*- coding: utf-8 -*-
"""
Pydantic schemas for API request/response models.

Defines DTOs for:
- Tasks (create, update, detail, list)
- Runs (create, update, detail, list)
- Metrics (list, detail)
- Plan approval
- Events and WebSocket messages
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field


# ============================================
# Enums (Response-compatible)
# ============================================

class TaskStatusEnum(str, Enum):
    """Task status for responses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class RunStatusEnum(str, Enum):
    """Run status for responses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class EventTypeEnum(str, Enum):
    """Types of events that can be broadcast."""
    ANALYSIS_START = "analysis_start"
    PLAN_READY = "plan_ready"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROGRESS = "progress"
    COMPLETION = "completion"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    
    # Git operation events
    GIT_BRANCH_CREATED = "git_branch_created"
    GIT_COMMIT_CREATED = "git_commit_created"
    GIT_PUSH_SUCCESS = "git_push_success"
    GIT_PUSH_FAILED = "git_push_failed"
    PULL_REQUEST_OPENED = "pull_request_opened"
    GIT_OPERATION_FAILED = "git_operation_failed"

    # Agent events
    AGENT_STATUS_CHANGED = "agent_status_changed"
    AGENT_ACTIVITY = "agent_activity"
    AGENT_MESSAGE = "agent_message"
    AGENT_CONTEXT_UPDATED = "agent_context_updated"


# ============================================
# Workspace & Project Schemas
# ============================================

class WorkspaceCreate(BaseModel):
    """Schema for creating a workspace."""

    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    slug: Optional[str] = Field(None, min_length=1, max_length=255, description="Workspace slug (unique)")
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata", description="Workspace metadata")

    class Config:
        allow_population_by_field_name = True


class WorkspaceSummary(BaseModel):
    """Small embedded representation of a workspace."""

    id: str
    name: str
    slug: str

    class Config:
        from_attributes = True


class WorkspaceResponse(WorkspaceSummary):
    """Workspace response schema."""

    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        from_attributes = True


class WorkspaceListResponse(BaseModel):
    items: List[WorkspaceResponse]
    total: int
    skip: int
    limit: int


class ProjectCreate(BaseModel):
    """Schema for creating a project in the active workspace."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    slug: Optional[str] = Field(None, min_length=1, max_length=255, description="Project slug (unique within workspace)")
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata", description="Project metadata")

    class Config:
        allow_population_by_field_name = True


class ProjectSummary(BaseModel):
    """Small embedded representation of a project."""

    id: str
    workspace_id: str
    name: str
    slug: str

    class Config:
        from_attributes = True


class ProjectResponse(ProjectSummary):
    repo_full_name: Optional[str] = Field(None, description="Primary linked repository full name (owner/repo)")
    default_branch: Optional[str] = Field(None, description="Reference/default branch for the primary repository")
    primary_repository_link_id: Optional[str] = Field(None, description="RepositoryLink id used as the project primary")
    
    run_branch_prefix: Optional[str] = Field("mgx", description="Branch prefix for task runs (e.g., 'mgx' -> mgx/task-name/run-1)")
    commit_template: Optional[str] = Field(None, description="Template for commit messages (supports {task_name}, {run_number} placeholders)")

    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        from_attributes = True


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    skip: int
    limit: int


# ============================================
# Repository Link Schemas
# ============================================

class RepositoryProviderEnum(str, Enum):
    GITHUB = "github"


class RepositoryLinkStatusEnum(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class RepositoryLinkConnectRequest(BaseModel):
    project_id: str = Field(..., description="Project ID")
    repo_full_name: str = Field(..., description="GitHub repository full name (owner/repo or URL)")

    installation_id: Optional[int] = Field(
        None,
        description="GitHub App installation id (optional; if omitted PAT fallback is used)",
    )
    reference_branch: Optional[str] = Field(
        None,
        description="Preferred/reference branch to use for the project (defaults to repo default)",
    )
    set_as_primary: bool = Field(True, description="Whether this link becomes the project's primary repository")


class RepositoryLinkUpdateRequest(BaseModel):
    reference_branch: Optional[str] = Field(None, description="Update preferred/reference branch")
    set_as_primary: Optional[bool] = Field(None, description="Mark this link as the project's primary repository")


class RepositoryLinkTestRequest(BaseModel):
    repo_full_name: str = Field(..., description="GitHub repository full name (owner/repo or URL)")
    installation_id: Optional[int] = Field(None, description="GitHub App installation id (optional)")


class RepositoryLinkTestResponse(BaseModel):
    ok: bool
    repo_full_name: str
    default_branch: str


class RepositoryLinkResponse(BaseModel):
    id: str
    project_id: str
    provider: RepositoryProviderEnum
    repo_full_name: str
    default_branch: Optional[str] = None
    status: RepositoryLinkStatusEnum
    last_validated_at: Optional[datetime] = None

    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        from_attributes = True


class RepositoryLinkListResponse(BaseModel):
    items: List[RepositoryLinkResponse]
    total: int
    skip: int
    limit: int


# ============================================
# Task Schemas
# ============================================

class TaskCreate(BaseModel):
    """Schema for creating a new task in the active workspace."""

    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    description: Optional[str] = Field(None, description="Task description")

    project_id: Optional[str] = Field(
        None,
        description=(
            "Project ID within the active workspace. If omitted, the workspace's default project is used."
        ),
    )

    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Task configuration")
    max_rounds: Optional[int] = Field(5, ge=1, le=100, description="Maximum execution rounds")
    max_revision_rounds: Optional[int] = Field(2, ge=0, le=50, description="Maximum revision rounds")
    memory_size: Optional[int] = Field(50, ge=1, le=1000, description="Team memory size")
    
    run_branch_prefix: Optional[str] = Field(None, description="Branch prefix for this task's runs (overrides project setting)")
    commit_template: Optional[str] = Field(None, description="Commit message template for this task (overrides project setting)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Analyze sales data",
                "description": "Analyze Q4 2024 sales performance",
                "max_rounds": 5,
                "max_revision_rounds": 2,
                "memory_size": 50,
            }
        }


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    max_rounds: Optional[int] = Field(None, ge=1, le=100)
    max_revision_rounds: Optional[int] = Field(None, ge=0, le=50)
    memory_size: Optional[int] = Field(None, ge=1, le=1000)
    run_branch_prefix: Optional[str] = None
    commit_template: Optional[str] = None


class TaskResponse(BaseModel):
    """Schema for task responses."""

    id: str
    workspace_id: str
    project_id: str

    name: str
    description: Optional[str]
    config: Dict[str, Any]
    status: TaskStatusEnum

    # Optional embedded summaries (populated when relationships are eager-loaded)
    workspace: Optional[WorkspaceSummary] = None
    project: Optional[ProjectSummary] = None
    max_rounds: int
    max_revision_rounds: int
    memory_size: int
    run_branch_prefix: Optional[str] = None
    commit_template: Optional[str] = None
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    last_run_at: Optional[datetime] = None
    last_run_duration: Optional[float] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema for task list responses."""
    items: List[TaskResponse]
    total: int
    skip: int
    limit: int


# ============================================
# Run Schemas
# ============================================

class RunCreate(BaseModel):
    """Schema for creating a new run."""
    task_id: str = Field(..., description="Parent task ID")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123",
            }
        }


class RunApprovalRequest(BaseModel):
    """Schema for approving a plan."""
    approved: bool = Field(..., description="Whether to approve the plan")
    feedback: Optional[str] = Field(None, description="Feedback on the plan")

    class Config:
        json_schema_extra = {
            "example": {
                "approved": True,
                "feedback": "Plan looks good, proceed with execution",
            }
        }


class RunResponse(BaseModel):
    """Schema for run responses."""

    id: str
    workspace_id: str
    project_id: str

    task_id: str
    run_number: int
    status: RunStatusEnum

    # Optional embedded summaries
    workspace: Optional[WorkspaceSummary] = None
    project: Optional[ProjectSummary] = None
    plan: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    memory_used: Optional[int] = None
    round_count: Optional[int] = None
    
    # Git metadata
    branch_name: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_url: Optional[str] = None
    git_status: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    """Schema for run list responses."""
    items: List[RunResponse]
    total: int
    skip: int
    limit: int


# ============================================
# Agent Schemas
# ============================================

class AgentStatusEnum(str, Enum):
    """Agent status for responses."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class AgentMessageDirectionEnum(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    SYSTEM = "system"


class ContextRollbackStateEnum(str, Enum):
    """Context rollback state for responses."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class WorkflowStatusEnum(str, Enum):
    """Workflow status for responses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class WorkflowStepStatusEnum(str, Enum):
    """Workflow step status for responses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class WorkflowStepTypeEnum(str, Enum):
    """Workflow step type for responses."""
    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    AGENT = "agent"


class AgentDefinitionResponse(BaseModel):
    id: str
    name: str
    slug: str
    agent_type: str
    description: Optional[str] = None

    capabilities: List[str] = Field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")

    is_enabled: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        from_attributes = True


class AgentInstanceResponse(BaseModel):
    id: str

    workspace_id: str
    project_id: str
    definition_id: str

    name: str
    status: AgentStatusEnum

    config: Dict[str, Any] = Field(default_factory=dict)
    state: Optional[Dict[str, Any]] = None

    last_heartbeat: Optional[datetime] = None
    last_error: Optional[str] = None

    definition: Optional[AgentDefinitionResponse] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentContextResponse(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    instance_id: str
    name: str

    current_version: int
    data: Dict[str, Any] = Field(default_factory=dict)

    rollback_pointer: Optional[int] = None
    rollback_state: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentMessageResponse(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    agent_instance_id: str

    direction: AgentMessageDirectionEnum
    payload: Dict[str, Any] = Field(default_factory=dict)

    correlation_id: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentDefinitionListResponse(BaseModel):
    items: List[AgentDefinitionResponse]


class AgentInstanceListResponse(BaseModel):
    items: List[AgentInstanceResponse]


class AgentCreateRequest(BaseModel):
    definition_id: Optional[str] = None
    definition_slug: Optional[str] = None

    name: Optional[str] = None
    project_id: Optional[str] = None

    config: Dict[str, Any] = Field(default_factory=dict)
    activate: bool = True


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[AgentStatusEnum] = None
    config: Optional[Dict[str, Any]] = None


class AgentContextUpdateRequest(BaseModel):
    context_name: str = Field("default")
    data: Dict[str, Any] = Field(default_factory=dict)
    change_description: Optional[str] = None
    created_by: Optional[str] = None


class AgentContextRollbackRequest(BaseModel):
    context_name: str = Field("default")
    target_version: int = Field(..., ge=0)


class AgentSendMessageRequest(BaseModel):
    direction: AgentMessageDirectionEnum = Field(AgentMessageDirectionEnum.INBOUND)
    payload: Dict[str, Any] = Field(default_factory=dict)

    correlation_id: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None


# ============================================
# Metrics Schemas
# ============================================

class MetricResponse(BaseModel):
    """Schema for metric responses."""

    id: str
    workspace_id: str
    project_id: str

    task_id: Optional[str] = None
    task_run_id: Optional[str] = None
    name: str
    metric_type: str
    value: float
    unit: Optional[str] = None
    labels: Optional[Dict[str, Any]] = None
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class MetricListResponse(BaseModel):
    """Schema for metric list responses."""
    items: List[MetricResponse]
    total: int
    skip: int
    limit: int


# ============================================
# Event Schemas
# ============================================

class EventPayload(BaseModel):
    """Base schema for all event payloads."""

    event_type: EventTypeEnum = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")

    # Optional routing metadata (used for pub/sub channel selection)
    workspace_id: Optional[str] = Field(None, description="Workspace scope (optional)")
    agent_id: Optional[str] = Field(None, description="Agent instance id (optional)")

    # Task/run scope (optional for non-task events)
    task_id: Optional[str] = Field(None, description="Associated task ID")
    run_id: Optional[str] = Field(None, description="Associated run ID")

    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    message: Optional[str] = Field(None, description="Human-readable message")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "plan_ready",
                "timestamp": "2024-01-01T12:00:00Z",
                "task_id": "task_123",
                "run_id": "run_456",
                "data": {"plan": "..."},
                "message": "Plan ready for approval",
            }
        }


class AnalysisStartEvent(EventPayload):
    """Event emitted when analysis starts."""
    event_type: EventTypeEnum = EventTypeEnum.ANALYSIS_START


class PlanReadyEvent(EventPayload):
    """Event emitted when plan is ready for review."""
    event_type: EventTypeEnum = EventTypeEnum.PLAN_READY


class ApprovalRequiredEvent(EventPayload):
    """Event emitted when approval is required."""
    event_type: EventTypeEnum = EventTypeEnum.APPROVAL_REQUIRED


class ApprovedEvent(EventPayload):
    """Event emitted when plan is approved."""
    event_type: EventTypeEnum = EventTypeEnum.APPROVED


class RejectedEvent(EventPayload):
    """Event emitted when plan is rejected."""
    event_type: EventTypeEnum = EventTypeEnum.REJECTED


class ProgressEvent(EventPayload):
    """Event emitted during execution progress."""
    event_type: EventTypeEnum = EventTypeEnum.PROGRESS


class CompletionEvent(EventPayload):
    """Event emitted on completion."""
    event_type: EventTypeEnum = EventTypeEnum.COMPLETION


class FailureEvent(EventPayload):
    """Event emitted on failure."""
    event_type: EventTypeEnum = EventTypeEnum.FAILURE


class CancelledEvent(EventPayload):
    """Event emitted when cancelled."""
    event_type: EventTypeEnum = EventTypeEnum.CANCELLED


class GitBranchCreatedEvent(EventPayload):
    """Event emitted when a git branch is created."""
    event_type: EventTypeEnum = EventTypeEnum.GIT_BRANCH_CREATED


class GitCommitCreatedEvent(EventPayload):
    """Event emitted when a git commit is created."""
    event_type: EventTypeEnum = EventTypeEnum.GIT_COMMIT_CREATED


class GitPushSuccessEvent(EventPayload):
    """Event emitted when git push succeeds."""
    event_type: EventTypeEnum = EventTypeEnum.GIT_PUSH_SUCCESS


class GitPushFailedEvent(EventPayload):
    """Event emitted when git push fails."""
    event_type: EventTypeEnum = EventTypeEnum.GIT_PUSH_FAILED


class PullRequestOpenedEvent(EventPayload):
    """Event emitted when a pull request is opened."""
    event_type: EventTypeEnum = EventTypeEnum.PULL_REQUEST_OPENED


class GitOperationFailedEvent(EventPayload):
    """Event emitted when a git operation fails."""
    event_type: EventTypeEnum = EventTypeEnum.GIT_OPERATION_FAILED


# ============================================
# Health Check Schemas
# ============================================

class HealthStatus(BaseModel):
    """Schema for health check responses."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "0.1.0"
    checks: Optional[Dict[str, Any]] = None


# ============================================
# Workflow Schemas
# ============================================

class WorkflowVariableCreate(BaseModel):
    """Schema for creating workflow variables."""
    name: str = Field(..., min_length=1, max_length=255, description="Variable name")
    data_type: str = Field(..., description="Data type (string, int, float, bool, json)")
    is_required: bool = Field(False, description="Whether the variable is required")
    default_value: Optional[Dict[str, Any]] = Field(None, description="Default value")
    description: Optional[str] = Field(None, description="Variable description")
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")


class WorkflowStepCreate(BaseModel):
    """Schema for creating workflow steps."""
    name: str = Field(..., min_length=1, max_length=255, description="Step name")
    step_type: WorkflowStepTypeEnum = Field(..., description="Type of step")
    step_order: int = Field(..., ge=1, description="Order in execution sequence")
    
    config: Dict[str, Any] = Field(default_factory=dict, description="Step configuration")
    timeout_seconds: Optional[int] = Field(None, description="Step-specific timeout override")
    max_retries: Optional[int] = Field(None, description="Step-specific retry override")
    
    # Agent requirements
    agent_definition_id: Optional[str] = Field(None, description="Required agent definition ID")
    agent_instance_id: Optional[str] = Field(None, description="Required agent instance ID")
    
    # Dependencies
    depends_on_steps: List[str] = Field(default_factory=list, description="List of step IDs this step depends on")
    condition_expression: Optional[str] = Field(None, description="Conditional expression for step execution")
    
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")


class WorkflowCreate(BaseModel):
    """Schema for creating workflows."""
    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    
    project_id: Optional[str] = Field(None, description="Project ID within the active workspace")
    
    config: Dict[str, Any] = Field(default_factory=dict, description="Workflow configuration")
    timeout_seconds: Optional[int] = Field(3600, ge=1, description="Default timeout in seconds")
    max_retries: Optional[int] = Field(3, ge=0, description="Default maximum retries per step")
    
    # Steps and variables
    steps: List[WorkflowStepCreate] = Field(default_factory=list, description="Workflow steps")
    variables: List[WorkflowVariableCreate] = Field(default_factory=list, description="Workflow variables")
    
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")


class WorkflowUpdate(BaseModel):
    """Schema for updating workflows."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1)
    max_retries: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    meta_data: Optional[Dict[str, Any]] = None


class WorkflowVariableResponse(BaseModel):
    """Schema for workflow variable responses."""
    id: str
    workflow_id: str
    name: str
    data_type: str
    is_required: bool
    default_value: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowStepResponse(BaseModel):
    """Schema for workflow step responses."""
    id: str
    workflow_id: str
    name: str
    step_type: WorkflowStepTypeEnum
    step_order: int
    config: Dict[str, Any]
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    agent_definition_id: Optional[str] = None
    agent_instance_id: Optional[str] = None
    depends_on_steps: List[str]
    condition_expression: Optional[str] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowResponse(BaseModel):
    """Schema for workflow responses."""
    id: str
    workspace_id: str
    project_id: str
    name: str
    description: Optional[str] = None
    version: int
    is_active: bool
    config: Dict[str, Any]
    timeout_seconds: int
    max_retries: int
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    # Optional embedded data
    steps: List[WorkflowStepResponse] = Field(default_factory=list)
    variables: List[WorkflowVariableResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    """Schema for workflow list responses."""
    items: List[WorkflowResponse]
    total: int
    skip: int
    limit: int


class WorkflowExecutionCreate(BaseModel):
    """Schema for creating workflow executions."""
    input_variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Input variables for the workflow")


class WorkflowStepExecutionResponse(BaseModel):
    """Schema for workflow step execution responses."""
    id: str
    execution_id: str
    step_id: str
    status: WorkflowStepStatusEnum
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    retry_count: int
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    # Optional embedded data
    step: Optional[WorkflowStepResponse] = None

    class Config:
        from_attributes = True


class WorkflowExecutionResponse(BaseModel):
    """Schema for workflow execution responses."""
    id: str
    workflow_id: str
    workspace_id: str
    project_id: str
    execution_number: int
    status: WorkflowStatusEnum
    input_variables: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime
    updated_at: datetime

    # Optional embedded data
    definition: Optional[WorkflowResponse] = None
    step_executions: List[WorkflowStepExecutionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkflowExecutionListResponse(BaseModel):
    """Schema for workflow execution list responses."""
    items: List[WorkflowExecutionResponse]
    total: int
    skip: int
    limit: int


class WorkflowValidationError(BaseModel):
    """Schema for workflow validation errors."""
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None


class WorkflowValidationResult(BaseModel):
    """Schema for workflow validation results."""
    is_valid: bool
    errors: List[WorkflowValidationError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


__all__ = [
    # Enums
    'TaskStatusEnum',
    'RunStatusEnum',
    'EventTypeEnum',
    'AgentStatusEnum',
    'AgentMessageDirectionEnum',
    'ContextRollbackStateEnum',
    'WorkflowStatusEnum',
    'WorkflowStepStatusEnum',
    'WorkflowStepTypeEnum',
    # Workspace/Project schemas
    'WorkspaceCreate',
    'WorkspaceSummary',
    'WorkspaceResponse',
    'WorkspaceListResponse',
    'ProjectCreate',
    'ProjectSummary',
    'ProjectResponse',
    'ProjectListResponse',
    # Task schemas
    'TaskCreate',
    'TaskUpdate',
    'TaskResponse',
    'TaskListResponse',
    # Run schemas
    'RunCreate',
    'RunApprovalRequest',
    'RunResponse',
    'RunListResponse',
    # Agent schemas
    'AgentDefinitionResponse',
    'AgentInstanceResponse',
    'AgentContextResponse',
    'AgentMessageResponse',
    'AgentDefinitionListResponse',
    'AgentInstanceListResponse',
    'AgentCreateRequest',
    'AgentUpdateRequest',
    'AgentContextUpdateRequest',
    'AgentContextRollbackRequest',
    'AgentSendMessageRequest',
    # Workflow schemas
    'WorkflowVariableCreate',
    'WorkflowStepCreate',
    'WorkflowCreate',
    'WorkflowUpdate',
    'WorkflowVariableResponse',
    'WorkflowStepResponse',
    'WorkflowResponse',
    'WorkflowListResponse',
    'WorkflowExecutionCreate',
    'WorkflowStepExecutionResponse',
    'WorkflowExecutionResponse',
    'WorkflowExecutionListResponse',
    'WorkflowValidationError',
    'WorkflowValidationResult',
    # Metric schemas
    'MetricResponse',
    'MetricListResponse',
    # Event schemas
    'EventPayload',
    'AnalysisStartEvent',
    'PlanReadyEvent',
    'ApprovalRequiredEvent',
    'ApprovedEvent',
    'RejectedEvent',
    'ProgressEvent',
    'CompletionEvent',
    'FailureEvent',
    'CancelledEvent',
    # Health
    'HealthStatus',
]
