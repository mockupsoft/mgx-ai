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
    
    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    
    # Sandbox execution events
    SANDBOX_EXECUTION_STARTED = "sandbox_execution_started"
    SANDBOX_EXECUTION_COMPLETED = "sandbox_execution_completed"
    SANDBOX_EXECUTION_FAILED = "sandbox_execution_failed"
    SANDBOX_EXECUTION_LOGS = "sandbox_execution_logs"


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


class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Workspace name")
    slug: Optional[str] = Field(None, min_length=1, max_length=255, description="Workspace slug (unique)")
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metadata", description="Workspace metadata")

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


class ProjectUpdate(BaseModel):
    """Schema for updating a project in the active workspace."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    slug: Optional[str] = Field(None, min_length=1, max_length=255, description="Project slug (unique within workspace)")
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metadata", description="Project metadata")

    run_branch_prefix: Optional[str] = Field(None, min_length=1, max_length=255)
    commit_template: Optional[str] = Field(None, max_length=4000)

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

    # Workflow scope (optional for non-workflow events)
    workflow_id: Optional[str] = Field(None, description="Associated workflow definition ID")
    workflow_execution_id: Optional[str] = Field(None, description="Associated workflow execution ID")
    workflow_step_id: Optional[str] = Field(None, description="Associated workflow step ID")

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


# Workflow Events
class WorkflowStartedEvent(EventPayload):
    """Event emitted when a workflow execution starts."""
    event_type: EventTypeEnum = EventTypeEnum.WORKFLOW_STARTED


class WorkflowCompletedEvent(EventPayload):
    """Event emitted when a workflow execution completes successfully."""
    event_type: EventTypeEnum = EventTypeEnum.WORKFLOW_COMPLETED


class WorkflowFailedEvent(EventPayload):
    """Event emitted when a workflow execution fails."""
    event_type: EventTypeEnum = EventTypeEnum.WORKFLOW_FAILED


class WorkflowCancelledEvent(EventPayload):
    """Event emitted when a workflow execution is cancelled."""
    event_type: EventTypeEnum = EventTypeEnum.WORKFLOW_CANCELLED


class StepStartedEvent(EventPayload):
    """Event emitted when a workflow step starts execution."""
    event_type: EventTypeEnum = EventTypeEnum.STEP_STARTED


class StepCompletedEvent(EventPayload):
    """Event emitted when a workflow step completes successfully."""
    event_type: EventTypeEnum = EventTypeEnum.STEP_COMPLETED


class StepFailedEvent(EventPayload):
    """Event emitted when a workflow step fails."""
    event_type: EventTypeEnum = EventTypeEnum.STEP_FAILED


class StepSkippedEvent(EventPayload):
    """Event emitted when a workflow step is skipped."""
    event_type: EventTypeEnum = EventTypeEnum.STEP_SKIPPED


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
# RBAC & Permission Schemas
# ============================================

class RoleCreate(BaseModel):
    """Schema for creating roles."""
    name: str = Field(..., min_length=1, max_length=100, description="Role name")
    permissions: List[str] = Field(default_factory=list, description="List of permission strings")
    description: Optional[str] = Field(None, max_length=500, description="Role description")


class RoleUpdate(BaseModel):
    """Schema for updating roles."""
    permissions: Optional[List[str]] = Field(None, description="List of permission strings")
    description: Optional[str] = Field(None, max_length=500, description="Role description")
    is_active: Optional[bool] = Field(None, description="Whether role is active")


class RoleResponse(BaseModel):
    """Schema for role responses."""
    id: str = Field(..., description="Role ID")
    workspace_id: str = Field(..., description="Workspace ID")
    name: str = Field(..., description="Role name")
    permissions: List[str] = Field(default_factory=list, description="List of permission strings")
    description: Optional[str] = Field(None, description="Role description")
    is_system_role: bool = Field(..., description="Whether this is a system role")
    is_active: bool = Field(..., description="Whether role is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Schema for role list responses."""
    roles: List[RoleResponse] = Field(..., description="List of roles")
    total: int = Field(..., description="Total number of roles")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")


class UserRoleCreate(BaseModel):
    """Schema for creating user role assignments."""
    user_id: str = Field(..., description="User ID to assign role to")
    role_id: str = Field(..., description="Role ID to assign")


class UserRoleUpdate(BaseModel):
    """Schema for updating user role assignments."""
    is_active: Optional[bool] = Field(None, description="Whether assignment is active")


class UserRoleResponse(BaseModel):
    """Schema for user role responses."""
    id: str = Field(..., description="Assignment ID")
    user_id: str = Field(..., description="User ID")
    workspace_id: str = Field(..., description="Workspace ID")
    role_id: str = Field(..., description="Role ID")
    assigned_at: datetime = Field(..., description="Assignment timestamp")
    assigned_by_user_id: Optional[str] = Field(None, description="User who assigned the role")
    is_active: bool = Field(..., description="Whether assignment is active")
    
    # Nested role information
    role: RoleResponse = Field(..., description="Role details")
    
    class Config:
        from_attributes = True


class UserRoleListResponse(BaseModel):
    """Schema for user role list responses."""
    assignments: List[UserRoleResponse] = Field(..., description="List of user role assignments")
    total: int = Field(..., description="Total number of assignments")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")


class PermissionResponse(BaseModel):
    """Schema for permission responses."""
    id: str = Field(..., description="Permission ID")
    workspace_id: str = Field(..., description="Workspace ID")
    role_id: str = Field(..., description="Role ID")
    resource: str = Field(..., description="Resource type")
    action: str = Field(..., description="Action type")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Permission conditions")
    is_active: bool = Field(..., description="Whether permission is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class PermissionListResponse(BaseModel):
    """Schema for permission list responses."""
    permissions: List[PermissionResponse] = Field(..., description="List of permissions")
    total: int = Field(..., description="Total number of permissions")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")


class PermissionCheck(BaseModel):
    """Schema for permission check requests."""
    user_id: str = Field(..., description="User ID to check")
    workspace_id: str = Field(..., description="Workspace ID")
    resource: str = Field(..., description="Resource type to check")
    action: str = Field(..., description="Action type to check")
    resource_id: Optional[str] = Field(None, description="Specific resource ID")


class PermissionResult(BaseModel):
    """Schema for permission check results."""
    has_permission: bool = Field(..., description="Whether permission is granted")
    required_permission: str = Field(..., description="Required permission string")
    user_roles: List[str] = Field(default_factory=list, description="User's roles")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


# ============================================
# Audit Logging Schemas
# ============================================

class AuditLogCreate(BaseModel):
    """Schema for creating audit log entries."""
    workspace_id: str = Field(..., description="Workspace ID")
    user_id: Optional[str] = Field(None, description="User ID (nullable for system actions)")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="Specific resource ID")
    changes: Optional[Dict[str, Any]] = Field(None, description="Before/after values")
    status: Optional[str] = Field("success", description="Operation status")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class AuditLogResponse(BaseModel):
    """Schema for audit log responses."""
    id: str = Field(..., description="Audit log ID")
    workspace_id: str = Field(..., description="Workspace ID")
    user_id: Optional[str] = Field(None, description="User ID")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="Specific resource ID")
    changes: Optional[Dict[str, Any]] = Field(None, description="Operation details")
    status: str = Field(..., description="Operation status")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Log timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Schema for audit log list responses."""
    logs: List[AuditLogResponse] = Field(..., description="List of audit logs")
    total: int = Field(..., description="Total number of logs")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")


class AuditLogFilter(BaseModel):
    """Schema for audit log filtering."""
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    action: Optional[str] = Field(None, description="Filter by action")
    resource_type: Optional[str] = Field(None, description="Filter by resource type")
    resource_id: Optional[str] = Field(None, description="Filter by resource ID")
    status: Optional[str] = Field(None, description="Filter by status")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    ip_address: Optional[str] = Field(None, description="Filter by IP address")


class AuditLogExportRequest(BaseModel):
    """Schema for audit log export requests."""
    filters: Optional[AuditLogFilter] = Field(None, description="Filter criteria")
    format: str = Field("json", description="Export format (json or csv)")
    limit: Optional[int] = Field(None, description="Maximum number of records")
    offset: Optional[int] = Field(None, description="Offset for pagination")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field(None, description="Sort order (asc or desc)")


class AuditLogExportResponse(BaseModel):
    """Schema for audit log export responses."""
    format: str = Field(..., description="Export format")
    record_count: int = Field(..., description="Number of records exported")
    exported_at: datetime = Field(..., description="Export timestamp")
    data: Any = Field(..., description="Exported data")


class AuditLogStatistics(BaseModel):
    """Schema for audit log statistics."""
    total_logs: int = Field(..., description="Total number of logs")
    date_range_days: int = Field(..., description="Analysis period in days")
    start_date: str = Field(..., description="Analysis start date")
    end_date: str = Field(..., description="Analysis end date")
    action_distribution: Dict[str, int] = Field(..., description="Logs by action type")
    status_distribution: Dict[str, int] = Field(..., description="Logs by status")
    daily_activity: Dict[str, int] = Field(..., description="Daily log counts")


# ============================================
# Workflow Schemas
# ============================================

class WorkflowVariableCreate(BaseModel):
    """Schema for creating workflow variables."""

    name: str = Field(..., min_length=1, max_length=255, description="Variable name")
    data_type: str = Field(..., description="Data type (string, int, float, bool, json)")
    is_required: bool = Field(False, description="Whether the variable is required")
    default_value: Optional[Any] = Field(None, description="Default value (any JSON type)")
    description: Optional[str] = Field(None, description="Variable description")
    meta_data: Dict[str, Any] = Field(default_factory=dict, alias="metadata")

    class Config:
        allow_population_by_field_name = True


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

    class Config:
        allow_population_by_field_name = True


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

    class Config:
        allow_population_by_field_name = True


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
    default_value: Optional[Any] = None
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


# ============================================
# Workflow Approval Schemas
# ============================================

class ApprovalStatusEnum(str, Enum):
    """Approval request status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUEST_CHANGES = "request_changes"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ApprovalRequest(BaseModel):
    """Schema for creating an approval request."""
    title: str = Field(..., min_length=1, max_length=500, description="Approval request title")
    description: Optional[str] = Field(None, description="Approval request description")
    approval_data: Dict[str, Any] = Field(default_factory=dict, description="Data to be approved")
    auto_approve_after_seconds: Optional[int] = Field(None, gt=0, description="Auto-approve after N seconds")
    required_approvers: List[str] = Field(default_factory=list, description="List of required approver IDs")
    expires_after_seconds: Optional[int] = Field(86400, gt=0, description="Expiration timeout in seconds")


class ApprovalResponse(BaseModel):
    """Schema for approval response."""
    approved: bool = Field(..., description="Whether approved or not")
    feedback: Optional[str] = Field(None, description="Feedback from approver")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")


class ApprovalResult(BaseModel):
    """Schema for approval result."""
    id: str = Field(..., description="Approval request ID")
    step_execution_id: str = Field(..., description="Step execution ID")
    workflow_execution_id: str = Field(..., description="Workflow execution ID")
    status: ApprovalStatusEnum = Field(..., description="Approval status")
    title: str = Field(..., description="Approval request title")
    description: Optional[str] = Field(None, description="Approval request description")
    approval_data: Dict[str, Any] = Field(default_factory=dict, description="Data that was approved")
    approved_by: Optional[str] = Field(None, description="User who approved/rejected")
    feedback: Optional[str] = Field(None, description="Feedback from approver")
    requested_at: datetime = Field(..., description="When approval was requested")
    responded_at: Optional[datetime] = Field(None, description="When approval was responded to")
    expires_at: Optional[datetime] = Field(None, description="When approval request expires")
    revision_count: int = Field(default=0, description="Number of revisions")
    parent_approval_id: Optional[str] = Field(None, description="Parent approval if this is a revision")

    class Config:
        from_attributes = True


class ApprovalListResponse(BaseModel):
    """Schema for list of pending approvals."""
    approvals: List[ApprovalResult] = Field(default_factory=list, description="List of approvals")
    total: int = Field(..., ge=0, description="Total number of approvals")


# ============================================
# Workflow Telemetry Schemas
# ============================================

class WorkflowMetricsSummary(BaseModel):
    """Summary of workflow execution metrics."""
    total_duration_seconds: float = Field(..., description="Total execution duration in seconds")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate as percentage")
    total_executions: int = Field(..., ge=0, description="Total number of executions")
    successful_executions: int = Field(..., ge=0, description="Number of successful executions")
    failed_executions: int = Field(..., ge=0, description="Number of failed executions")
    average_duration_seconds: float = Field(..., ge=0, description="Average execution duration")
    min_duration_seconds: Optional[float] = Field(None, ge=0, description="Minimum execution duration")
    max_duration_seconds: Optional[float] = Field(None, ge=0, description="Maximum execution duration")

    class Config:
        from_attributes = True


class WorkflowStepTimelineEntry(BaseModel):
    """Timeline entry for a single step execution."""
    step_id: str = Field(..., description="ID of the step")
    step_name: str = Field(..., description="Name of the step")
    step_order: int = Field(..., description="Order in workflow")
    status: WorkflowStepStatusEnum = Field(..., description="Step execution status")
    started_at: Optional[datetime] = Field(None, description="Step start time")
    completed_at: Optional[datetime] = Field(None, description="Step completion time")
    duration_seconds: Optional[float] = Field(None, ge=0, description="Step duration in seconds")
    retry_count: int = Field(default=0, ge=0, description="Number of retries")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    input_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of step input (truncated)")
    output_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of step output (truncated)")

    class Config:
        from_attributes = True


class WorkflowExecutionTimeline(BaseModel):
    """Complete timeline for a workflow execution."""
    execution_id: str = Field(..., description="Execution ID")
    workflow_id: str = Field(..., description="Workflow ID")
    status: WorkflowStatusEnum = Field(..., description="Overall execution status")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    total_duration_seconds: Optional[float] = Field(None, ge=0, description="Total execution duration")
    step_count: int = Field(..., ge=0, description="Total number of steps")
    completed_step_count: int = Field(..., ge=0, description="Number of completed steps")
    failed_step_count: int = Field(..., ge=0, description="Number of failed steps")
    skipped_step_count: int = Field(..., ge=0, description="Number of skipped steps")
    step_timeline: List[WorkflowStepTimelineEntry] = Field(default_factory=list, description="Timeline entries for each step")
    error_message: Optional[str] = Field(None, description="Execution error message if failed")

    class Config:
        from_attributes = True


class WorkflowExecutionDetailedResponse(WorkflowExecutionResponse):
    """Extended workflow execution response with full timeline and metrics."""
    timeline: Optional[WorkflowExecutionTimeline] = Field(None, description="Detailed execution timeline")
    step_timelines: List[WorkflowStepTimelineEntry] = Field(default_factory=list, description="Timeline entries for each step")

    class Config:
        from_attributes = True


# ============================================
# Sandbox Execution Schemas
# ============================================

class SandboxExecutionStatusEnum(str, Enum):
    """Sandbox execution status for responses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class SandboxExecutionLanguageEnum(str, Enum):
    """Supported languages for sandbox execution."""
    JAVASCRIPT = "javascript"
    NODE = "node"
    PYTHON = "python"
    PHP = "php"
    DOCKER = "docker"


class QualityGateTypeEnum(str, Enum):
    """Quality gate type for responses."""
    LINT = "lint"
    COVERAGE = "coverage"
    CONTRACT = "contract"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPLEXITY = "complexity"
    TYPE_CHECK = "type_check"


class QualityGateStatusEnum(str, Enum):
    """Quality gate status for responses."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


class ResourceUsage(BaseModel):
    """Resource usage information from execution."""
    max_memory_mb: Optional[int] = Field(None, ge=0, description="Maximum memory used in MB")
    cpu_percent: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    network_io: Optional[int] = Field(None, ge=0, description="Network I/O in bytes")
    disk_io: Optional[int] = Field(None, ge=0, description="Disk I/O in bytes")

    class Config:
        from_attributes = True


class ExecutionRequest(BaseModel):
    """Request schema for code execution."""
    code: str = Field(..., description="Source code to execute")
    command: str = Field(..., description="Command to run (e.g., 'npm test', 'pytest')")
    language: SandboxExecutionLanguageEnum = Field(..., description="Programming language")
    timeout: Optional[int] = Field(30, gt=0, le=300, description="Execution timeout in seconds")
    memory_limit_mb: Optional[int] = Field(512, gt=0, le=2048, description="Memory limit in megabytes")

    class Config:
        from_attributes = True


class ExecutionResult(BaseModel):
    """Result schema for code execution."""
    success: bool = Field(..., description="Whether execution was successful")
    stdout: str = Field("", description="Standard output")
    stderr: str = Field("", description="Standard error")
    exit_code: Optional[int] = Field(None, description="Process exit code")
    duration_ms: Optional[int] = Field(None, ge=0, description="Execution duration in milliseconds")
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage, description="Resource usage information")
    error_type: Optional[str] = Field(None, description="Error type if failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    container_id: Optional[str] = Field(None, description="Docker container ID")

    class Config:
        from_attributes = True


class SandboxExecutionResponse(BaseModel):
    """Response schema for sandbox execution."""
    id: str = Field(..., description="Execution ID")
    workspace_id: str = Field(..., description="Workspace ID")
    project_id: str = Field(..., description="Project ID")
    execution_type: SandboxExecutionLanguageEnum = Field(..., description="Execution type")
    status: SandboxExecutionStatusEnum = Field(..., description="Execution status")
    command: str = Field(..., description="Command executed")
    code: Optional[str] = Field(None, description="Source code executed")
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")
    exit_code: Optional[int] = Field(None, description="Process exit code")
    success: Optional[bool] = Field(None, description="Execution success status")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    max_memory_mb: Optional[int] = Field(None, description="Maximum memory used in MB")
    cpu_percent: Optional[float] = Field(None, description="CPU usage percentage")
    network_io: Optional[int] = Field(None, description="Network I/O in bytes")
    disk_io: Optional[int] = Field(None, description="Disk I/O in bytes")
    error_type: Optional[str] = Field(None, description="Error type")
    error_message: Optional[str] = Field(None, description="Error message")
    timeout_seconds: Optional[int] = Field(None, description="Execution timeout in seconds")
    container_id: Optional[str] = Field(None, description="Docker container ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True


class SandboxExecutionListResponse(BaseModel):
    """Response schema for listing sandbox executions."""
    executions: List[SandboxExecutionResponse] = Field(..., description="List of executions")
    total: int = Field(..., description="Total number of executions")
    offset: int = Field(..., description="Offset for pagination")
    limit: int = Field(..., description="Limit for pagination")

    class Config:
        from_attributes = True


class SandboxExecutionLogsEvent(BaseModel):
    """Event schema for sandbox execution logs."""
    execution_id: str = Field(..., description="Execution ID")
    logs: str = Field(..., description="Execution logs")
    timestamp: datetime = Field(..., description="Log timestamp")

    class Config:
        from_attributes = True


class SandboxExecutionStartedEvent(BaseModel):
    """Event schema for sandbox execution started."""
    execution_id: str = Field(..., description="Execution ID")
    workspace_id: str = Field(..., description="Workspace ID")
    project_id: str = Field(..., description="Project ID")
    execution_type: SandboxExecutionLanguageEnum = Field(..., description="Execution type")
    command: str = Field(..., description="Command to execute")
    timeout_seconds: int = Field(..., description="Timeout in seconds")

    class Config:
        from_attributes = True


class SandboxExecutionCompletedEvent(BaseModel):
    """Event schema for sandbox execution completed."""
    execution_id: str = Field(..., description="Execution ID")
    success: bool = Field(..., description="Execution success status")
    duration_ms: int = Field(..., description="Execution duration in milliseconds")
    exit_code: Optional[int] = Field(None, description="Process exit code")
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage, description="Resource usage")
    error_type: Optional[str] = Field(None, description="Error type if failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        from_attributes = True


class SandboxExecutionFailedEvent(BaseModel):
    """Event schema for sandbox execution failed."""
    execution_id: str = Field(..., description="Execution ID")
    error_type: str = Field(..., description="Error type")
    error_message: str = Field(..., description="Error message")
    duration_ms: int = Field(..., description="Execution duration in milliseconds")

    class Config:
        from_attributes = True


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
    'SandboxExecutionStatusEnum',
    'SandboxExecutionLanguageEnum',
    'QualityGateTypeEnum',
    'QualityGateStatusEnum',
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
    'WorkflowMetricsSummary',
    'WorkflowStepTimelineEntry',
    'WorkflowExecutionTimeline',
    'WorkflowExecutionDetailedResponse',
    # Sandbox schemas
    'ResourceUsage',
    'ExecutionRequest',
    'ExecutionResult',
    'SandboxExecutionResponse',
    'SandboxExecutionListResponse',
    'SandboxExecutionLogsEvent',
    'SandboxExecutionStartedEvent',
    'SandboxExecutionCompletedEvent',
    'SandboxExecutionFailedEvent',
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
    # RBAC schemas
    'RoleCreate',
    'RoleUpdate',
    'RoleResponse',
    'RoleListResponse',
    'UserRoleCreate',
    'UserRoleUpdate',
    'UserRoleResponse',
    'UserRoleListResponse',
    'PermissionResponse',
    'PermissionListResponse',
    'PermissionCheck',
    'PermissionResult',
    # Audit logging schemas
    'AuditLogCreate',
    'AuditLogResponse',
    'AuditLogListResponse',
    'AuditLogFilter',
    'AuditLogExportRequest',
    'AuditLogExportResponse',
    'AuditLogStatistics',
]

# ============================================
# Secret Management Schemas
# ============================================


class SecretCreateRequest(BaseModel):
    """Schema for creating a secret."""

    name: str = Field(..., min_length=1, max_length=255, description="Secret name")
    secret_type: str = Field(..., description="Type of secret")
    value: str = Field(..., description="Secret value to encrypt")
    usage: Optional[str] = Field(None, max_length=1000, description="Description of what the secret is used for")
    rotation_policy: str = Field(default="manual", description="Rotation policy")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorizing secrets")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class SecretUpdateRequest(BaseModel):
    """Schema for updating a secret."""

    value: Optional[str] = Field(None, description="New secret value (if updating)")
    usage: Optional[str] = Field(None, max_length=1000, description="Description of what the secret is used for")
    rotation_policy: Optional[str] = Field(None, description="Rotation policy")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing secrets")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SecretRotationRequest(BaseModel):
    """Schema for rotating a secret."""

    new_value: str = Field(..., description="New secret value")


class SecretResponse(BaseModel):
    """Schema for secret response (includes encrypted value)."""

    id: str
    workspace_id: str
    name: str
    secret_type: str
    usage: Optional[str]
    encrypted_value: str
    rotation_policy: str
    last_rotated_at: Optional[datetime]
    rotation_due_at: Optional[datetime]
    created_by_user_id: Optional[str]
    updated_by_user_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    tags: List[str]
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True

    @classmethod
    def from_secret_model(cls, secret) -> 'SecretResponse':
        """Create response from Secret model."""
        return cls(
            id=secret.id,
            workspace_id=secret.workspace_id,
            name=secret.name,
            secret_type=secret.secret_type.value if hasattr(secret.secret_type, 'value') else secret.secret_type,
            usage=secret.usage,
            encrypted_value=secret.encrypted_value,
            rotation_policy=secret.rotation_policy.value if hasattr(secret.rotation_policy, 'value') else secret.rotation_policy,
            last_rotated_at=secret.last_rotated_at,
            rotation_due_at=secret.rotation_due_at,
            created_by_user_id=secret.created_by_user_id,
            updated_by_user_id=secret.updated_by_user_id,
            created_at=secret.created_at,
            updated_at=secret.updated_at,
            is_active=secret.is_active,
            tags=secret.tags or [],
            metadata=secret.meta_data or {}
        )


class SecretMetadataResponse(BaseModel):
    """Schema for secret metadata response (no encrypted value)."""

    id: str
    name: str
    secret_type: str
    usage: Optional[str]
    rotation_policy: str
    last_rotated_at: Optional[datetime]
    rotation_due_at: Optional[datetime]
    created_by_user_id: Optional[str]
    updated_by_user_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    tags: List[str]
    metadata: Dict[str, Any]
    is_rotation_due: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_secret_metadata(cls, secret_metadata) -> 'SecretMetadataResponse':
        """Create response from SecretMetadata object."""
        return cls(
            id=secret_metadata.id,
            name=secret_metadata.name,
            secret_type=secret_metadata.secret_type.value if hasattr(secret_metadata.secret_type, 'value') else secret_metadata.secret_type,
            usage=secret_metadata.usage,
            rotation_policy=secret_metadata.rotation_policy.value if hasattr(secret_metadata.rotation_policy, 'value') else secret_metadata.rotation_policy,
            last_rotated_at=secret_metadata.last_rotated_at,
            rotation_due_at=secret_metadata.rotation_due_at,
            created_by_user_id=secret_metadata.created_by_user_id,
            updated_by_user_id=secret_metadata.updated_by_user_id,
            created_at=secret_metadata.created_at,
            updated_at=secret_metadata.updated_at,
            is_active=secret_metadata.is_active,
            tags=secret_metadata.tags,
            metadata=secret_metadata.metadata,
            is_rotation_due=secret_metadata.is_rotation_due
        )


class SecretListResponse(BaseModel):
    """Schema for listing secrets response."""

    secrets: List[SecretMetadataResponse]
    total: int
    limit: int
    offset: int


class SecretAuditLogResponse(BaseModel):
    """Schema for secret audit logs response."""

    audit_logs: List[Dict[str, Any]]  # Simplified - could be enhanced with proper audit log model
    total: int
    limit: int
    offset: int


class SecretStatisticsResponse(BaseModel):
    """Schema for secret statistics response."""

    total_secrets: int
    secrets_by_type: Dict[str, int]
    secrets_by_rotation_policy: Dict[str, int]
    rotation_due_count: int
    last_updated: str


# Update __all__ to include new schemas
__all__ += [
    'SecretCreateRequest',
    'SecretUpdateRequest',
    'SecretRotationRequest',
    'SecretResponse',
    'SecretMetadataResponse',
    'SecretListResponse',
    'SecretAuditLogResponse',
    'SecretStatisticsResponse',
]


# ============================================
# Template & Prompt Library Schemas
# ============================================

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field
from backend.db.models.enums import TemplateCategory, PromptOutputFormat, TemplateVisibility, ADRStatus


class ModuleTemplateCreateRequest(BaseModel):
    """Request schema for creating module templates."""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., description="Template category")
    description: Optional[str] = None
    version: str = Field(default="1.0.0", max_length=50)
    tech_stacks: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    documentation: Optional[str] = None
    params: List[Dict[str, Any]] = Field(default_factory=list)
    author: Optional[str] = None
    visibility: str = Field(default="private")
    tags: List[str] = Field(default_factory=list)
    files: Optional[List[Dict[str, Any]]] = None
    parameters: Optional[List[Dict[str, Any]]] = None


class ModuleTemplateResponse(BaseModel):
    """Response schema for module templates."""
    id: str
    name: str
    category: str
    description: Optional[str]
    version: str
    tech_stacks: List[str]
    dependencies: List[str]
    documentation: Optional[str]
    params: List[Dict[str, Any]]
    author: Optional[str]
    usage_count: int
    rating: float
    visibility: str
    is_active: bool
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class FileTemplateResponse(BaseModel):
    """Response schema for file templates."""
    id: str
    module_id: str
    path: str
    content: str
    language: Optional[str]
    is_test: bool
    is_config: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParameterResponse(BaseModel):
    """Response schema for template parameters."""
    id: str
    module_id: str
    name: str
    param_type: str
    default_value: Optional[Any]
    description: Optional[str]
    required: bool
    validation_rules: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModuleTemplateDetailResponse(BaseModel):
    """Response schema for module template details."""
    module: ModuleTemplateResponse
    files: List[FileTemplateResponse]
    parameters: List[ParameterResponse]
    total_files: int
    total_parameters: int


class ApplyModuleTemplateRequest(BaseModel):
    """Request schema for applying module templates."""
    project_id: str = Field(..., min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ApplyModuleTemplateResponse(BaseModel):
    """Response schema for module template application."""
    module_name: str
    files_generated: int
    files: List[Dict[str, Any]]
    parameters_used: Dict[str, Any]


class PromptTemplateCreateRequest(BaseModel):
    """Request schema for creating prompt templates."""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., description="Template category")
    template: str = Field(..., description="Prompt template with {{variables}}")
    context_required: List[str] = Field(default_factory=list)
    output_format: str = Field(..., description="Expected output format")
    examples: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    version: str = Field(default="1.0.0", max_length=50)
    visibility: str = Field(default="public")
    tags: List[str] = Field(default_factory=list)


class PromptTemplateResponse(BaseModel):
    """Response schema for prompt templates."""
    id: str
    name: str
    category: str
    template: str
    context_required: List[str]
    output_format: str
    examples: List[str]
    created_by: Optional[str]
    version: str
    usage_count: int
    rating: float
    visibility: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GeneratePromptRequest(BaseModel):
    """Request schema for generating prompts."""
    variables: Dict[str, Any] = Field(..., description="Variables for template substitution")


class GeneratePromptResponse(BaseModel):
    """Response schema for prompt generation."""
    prompt: str
    template_id: str
    variables_used: Dict[str, Any]


class ADRCreateRequest(BaseModel):
    """Request schema for creating ADRs."""
    title: str = Field(..., min_length=1, max_length=500)
    context: str = Field(..., description="Context of the decision")
    decision: str = Field(..., description="Decision made")
    consequences: str = Field(..., description="Consequences of the decision")
    status: str = Field(default="proposed")
    alternatives_considered: List[str] = Field(default_factory=list)
    related_adrs: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ADRResponse(BaseModel):
    """Response schema for ADRs."""
    id: str
    workspace_id: str
    title: str
    status: str
    context: str
    decision: str
    consequences: str
    alternatives_considered: List[str]
    related_adrs: List[str]
    tags: List[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ADRTimelineItem(BaseModel):
    """Schema for ADR timeline items."""
    id: str
    title: str
    status: str
    date: str
    summary: str


class ADRTimelineResponse(BaseModel):
    """Response schema for ADR timeline."""
    timeline: List[ADRTimelineItem]


class TemplateSearchRequest(BaseModel):
    """Request schema for template search."""
    query: str = Field(..., min_length=1)
    template_type: str = Field(default="all", description="all, module, prompt")
    category: Optional[str] = None
    limit: int = Field(default=20, le=100)


class TemplateSearchResult(BaseModel):
    """Schema for template search results."""
    type: str
    id: str
    name: str
    description: str
    category: str
    rating: float
    usage_count: int


class TemplateSearchResponse(BaseModel):
    """Response schema for template search."""
    results: List[TemplateSearchResult]
    total: int
    query: str


class TemplateListResponse(BaseModel):
    """Response schema for template lists."""
    items: List[Union[ModuleTemplateResponse, PromptTemplateResponse]]
    total: int
    limit: int
    offset: int
    template_type: str


class RateTemplateRequest(BaseModel):
    """Request schema for rating templates."""
    rating: float = Field(..., ge=0, le=5, description="Rating from 0 to 5")


class RateTemplateResponse(BaseModel):
    """Response schema for template rating."""
    template_id: str
    template_type: str
    new_rating: float
    previous_rating: float


# ============================================
# Template Enhancement Schemas
# ============================================

class TemplateEnhancementRequest(BaseModel):
    """Request schema for enhancing projects with templates."""
    project_id: str = Field(..., min_length=1)
    modules: List[str] = Field(..., description="List of module template names to apply")
    parameters: Optional[Dict[str, Dict[str, Any]]] = None


class TemplateEnhancementResult(BaseModel):
    """Schema for template enhancement results."""
    module: str
    success: bool
    files_generated: Optional[int] = None
    error: Optional[str] = None


class TemplateEnhancementResponse(BaseModel):
    """Response schema for template enhancement."""
    project_id: str
    templates_applied: int
    results: List[TemplateEnhancementResult]


class MarketplaceTemplate(BaseModel):
    """Schema for marketplace templates."""
    id: str
    name: str
    description: str
    category: str
    author: Optional[str]
    version: str
    rating: float
    usage_count: int
    tags: List[str]
    visibility: str


class MarketplaceResponse(BaseModel):
    """Response schema for template marketplace."""
    popular_modules: List[MarketplaceTemplate]
    popular_prompts: List[MarketplaceTemplate]
    categories: List[str]
    total_templates: int


# ============================================
# Knowledge Base & RAG Schemas
# ============================================

class KnowledgeItemCreate(BaseModel):
    """Schema for creating a knowledge item."""
    
    title: str = Field(..., min_length=1, max_length=500, description="Knowledge item title")
    content: str = Field(..., min_length=1, description="Knowledge item content")
    category: str = Field(..., description="Knowledge category")
    language: Optional[str] = Field(None, description="Programming language")
    tags: List[str] = Field(default_factory=list, description="Item tags")
    source: str = Field(..., description="Source type")
    author: Optional[str] = Field(None, description="Item author")
    
    class Config:
        schema_extra = {
            "example": {
                "title": "JWT Authentication Pattern",
                "content": "Here's a standard JWT authentication implementation...",
                "category": "code_pattern",
                "language": "python",
                "tags": ["authentication", "jwt", "security"],
                "source": "manual_entry",
                "author": "John Doe"
            }
        }


class KnowledgeItemUpdate(BaseModel):
    """Schema for updating a knowledge item."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=500, description="Knowledge item title")
    content: Optional[str] = Field(None, min_length=1, description="Knowledge item content")
    category: Optional[str] = Field(None, description="Knowledge category")
    language: Optional[str] = Field(None, description="Programming language")
    tags: Optional[List[str]] = Field(None, description="Item tags")
    status: Optional[str] = Field(None, description="Item status")


class KnowledgeItemResponse(BaseModel):
    """Schema for knowledge item response."""
    
    id: str = Field(..., description="Knowledge item ID")
    workspace_id: str = Field(..., description="Workspace ID")
    title: str = Field(..., description="Knowledge item title")
    content: str = Field(..., description="Knowledge item content")
    category: str = Field(..., description="Knowledge category")
    language: Optional[str] = Field(None, description="Programming language")
    tags: List[str] = Field(..., description="Item tags")
    source: str = Field(..., description="Source type")
    author: Optional[str] = Field(None, description="Item author")
    status: str = Field(..., description="Item status")
    relevance_score: float = Field(..., description="Relevance score")
    usage_count: int = Field(..., description="Usage count")
    embedding_id: Optional[str] = Field(None, description="Vector database embedding ID")
    file_path: Optional[str] = Field(None, description="Original file path")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "workspace_id": "456e7890-e89b-12d3-a456-426614174000",
                "title": "JWT Authentication Pattern",
                "content": "Here's a standard JWT authentication implementation...",
                "category": "code_pattern",
                "language": "python",
                "tags": ["authentication", "jwt", "security"],
                "source": "manual_entry",
                "author": "John Doe",
                "status": "active",
                "relevance_score": 0.95,
                "usage_count": 15,
                "embedding_id": "pinecone_abc123",
                "file_path": "backend/auth/jwt.py",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z"
            }
        }


class KnowledgeSearchRequest(BaseModel):
    """Schema for knowledge search request."""
    
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to return")
    category_filter: Optional[str] = Field(None, description="Filter by category")
    language_filter: Optional[str] = Field(None, description="Filter by language")
    tags_filter: Optional[List[str]] = Field(None, description="Filter by tags")
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum relevance score")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "How to implement JWT authentication?",
                "top_k": 5,
                "category_filter": "code_pattern",
                "language_filter": "python",
                "min_relevance_score": 0.5
            }
        }


class KnowledgeSearchResult(BaseModel):
    """Schema for knowledge search result."""
    
    id: str = Field(..., description="Knowledge item ID")
    title: str = Field(..., description="Knowledge item title")
    content_preview: str = Field(..., description="Content preview")
    category: str = Field(..., description="Knowledge category")
    language: Optional[str] = Field(None, description="Programming language")
    tags: List[str] = Field(..., description="Item tags")
    author: Optional[str] = Field(None, description="Item author")
    relevance_score: float = Field(..., description="Relevance score")
    source: str = Field(..., description="Source type")
    file_path: Optional[str] = Field(None, description="Original file path")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "JWT Authentication Pattern",
                "content_preview": "Here's a standard JWT authentication implementation...",
                "category": "code_pattern",
                "language": "python",
                "tags": ["authentication", "jwt", "security"],
                "author": "John Doe",
                "relevance_score": 0.95,
                "source": "manual_entry",
                "file_path": "backend/auth/jwt.py"
            }
        }


class KnowledgeSearchResponse(BaseModel):
    """Schema for knowledge search response."""
    
    items: List[KnowledgeSearchResult] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total number of matching items")
    search_time_ms: float = Field(..., description="Search time in milliseconds")
    metadata: Dict[str, Any] = Field(..., description="Search metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "JWT Authentication Pattern",
                        "content_preview": "Here's a standard JWT authentication implementation...",
                        "category": "code_pattern",
                        "language": "python",
                        "tags": ["authentication", "jwt", "security"],
                        "author": "John Doe",
                        "relevance_score": 0.95,
                        "source": "manual_entry",
                        "file_path": "backend/auth/jwt.py"
                    }
                ],
                "total_count": 1,
                "search_time_ms": 45.2,
                "metadata": {
                    "query": "JWT authentication",
                    "vector_results_count": 1,
                    "final_results": 1
                }
            }
        }


class EnhancedPromptRequest(BaseModel):
    """Schema for enhanced prompt request."""
    
    base_prompt: str = Field(..., description="Original prompt to enhance")
    query: str = Field(..., description="Search query for finding relevant knowledge")
    num_examples: int = Field(default=3, ge=1, le=10, description="Number of examples to include")
    category_filter: Optional[str] = Field(None, description="Filter by category")
    language_filter: Optional[str] = Field(None, description="Filter by language")
    
    class Config:
        schema_extra = {
            "example": {
                "base_prompt": "Write a function to authenticate users",
                "query": "JWT authentication implementation patterns",
                "num_examples": 3,
                "category_filter": "code_pattern",
                "language_filter": "python"
            }
        }


class EnhancedPromptResponse(BaseModel):
    """Schema for enhanced prompt response."""
    
    original_prompt: str = Field(..., description="Original prompt")
    enhanced_prompt: str = Field(..., description="Enhanced prompt with knowledge examples")
    retrieved_items: List[Dict[str, Any]] = Field(..., description="Retrieved knowledge items")
    search_metadata: Dict[str, Any] = Field(..., description="Search metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "original_prompt": "Write a function to authenticate users",
                "enhanced_prompt": "Write a function to authenticate users\n\n## Relevant Knowledge Examples:\n### Example 1: JWT Authentication Pattern\n...",
                "retrieved_items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "JWT Authentication Pattern",
                        "category": "code_pattern",
                        "content_preview": "Here's a standard JWT authentication implementation...",
                        "relevance_score": 0.95,
                        "tags": ["authentication", "jwt", "security"],
                        "author": "John Doe"
                    }
                ],
                "search_metadata": {
                    "search_time_ms": 45.2,
                    "total_found": 1,
                    "num_examples_included": 1
                }
            }
        }


class IngestionRequest(BaseModel):
    """Schema for knowledge ingestion request."""
    
    source_type: str = Field(..., description="Type of source to ingest")
    source_path: str = Field(..., description="Path to the source")
    auto_update: bool = Field(default=True, description="Whether to auto-update existing items")
    
    class Config:
        schema_extra = {
            "example": {
                "source_type": "documentation",
                "source_path": "/path/to/documentation",
                "auto_update": True
            }
        }


class IngestionResponse(BaseModel):
    """Schema for ingestion response."""
    
    job_id: str = Field(..., description="Ingestion job ID")
    status: str = Field(..., description="Job status")
    progress: float = Field(..., description="Job progress (0-1)")
    items_processed: int = Field(..., description="Number of items processed")
    items_created: int = Field(..., description="Number of items created")
    items_updated: int = Field(..., description="Number of items updated")
    error_message: Optional[str] = Field(None, description="Error message if job failed")
    created_at: datetime = Field(..., description="Job creation timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "789e1234-e89b-12d3-a456-426614174000",
                "status": "completed",
                "progress": 1.0,
                "items_processed": 10,
                "items_created": 8,
                "items_updated": 2,
                "created_at": "2024-01-01T10:00:00Z"
            }
        }


class KnowledgeStatsResponse(BaseModel):
    """Schema for knowledge base statistics response."""
    
    total_items: int = Field(..., description="Total number of knowledge items")
    category_distribution: Dict[str, int] = Field(..., description="Items by category")
    status_distribution: Dict[str, int] = Field(..., description="Items by status")
    top_used_items: List[Dict[str, Any]] = Field(..., description="Most used items")
    recent_items: List[Dict[str, Any]] = Field(..., description="Recently added items")
    embedding_stats: Dict[str, Any] = Field(..., description="Embedding-related statistics")
    
    class Config:
        schema_extra = {
            "example": {
                "total_items": 150,
                "category_distribution": {
                    "code_pattern": 50,
                    "best_practice": 30,
                    "standard": 20
                },
                "status_distribution": {
                    "active": 140,
                    "draft": 10
                },
                "top_used_items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "JWT Authentication Pattern",
                        "usage_count": 25,
                        "category": "code_pattern"
                    }
                ],
                "recent_items": [
                    {
                        "id": "456e7890-e89b-12d3-a456-426614174000",
                        "title": "API Rate Limiting",
                        "created_at": "2024-01-01T10:00:00Z",
                        "category": "best_practice"
                    }
                ],
                "embedding_stats": {
                    "items_with_embeddings": 140,
                    "items_without_embeddings": 10,
                    "embedding_coverage": 0.93
                }
            }
        }


# Update __all__ to include new schemas
__all__ += [
    'ModuleTemplateCreateRequest',
    'ModuleTemplateResponse',
    'FileTemplateResponse',
    'ParameterResponse',
    'ModuleTemplateDetailResponse',
    'ApplyModuleTemplateRequest',
    'ApplyModuleTemplateResponse',
    'PromptTemplateCreateRequest',
    'PromptTemplateResponse',
    'GeneratePromptRequest',
    'GeneratePromptResponse',
    'ADRCreateRequest',
    'ADRResponse',
    'ADRTimelineItem',
    'ADRTimelineResponse',
    'TemplateSearchRequest',
    'TemplateSearchResult',
    'TemplateSearchResponse',
    'TemplateListResponse',
    'RateTemplateRequest',
    'RateTemplateResponse',
    'TemplateEnhancementRequest',
    'TemplateEnhancementResult',
    'TemplateEnhancementResponse',
    'MarketplaceTemplate',
    'MarketplaceResponse',
    # Knowledge Base & RAG Schemas
    'KnowledgeItemCreate',
    'KnowledgeItemUpdate', 
    'KnowledgeItemResponse',
    'KnowledgeSearchRequest',
    'KnowledgeSearchResult',
    'KnowledgeSearchResponse',
    'EnhancedPromptRequest',
    'EnhancedPromptResponse',
    'IngestionRequest',
    'IngestionResponse',
    'KnowledgeStatsResponse',
]
