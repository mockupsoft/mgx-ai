# -*- coding: utf-8 -*-
"""backend.db.models.enums

Database enums for status types and other constants.

These enums are used both by SQLAlchemy (as database enums) and by the API
layer (as response-friendly string values).
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"  # Task is queued for execution
    RUNNING = "running"  # Task is currently executing
    COMPLETED = "completed"  # Task completed successfully
    FAILED = "failed"  # Task failed with error
    CANCELLED = "cancelled"  # Task was cancelled
    TIMEOUT = "timeout"  # Task timed out


class RunStatus(str, Enum):
    """Task run execution status."""

    PENDING = "pending"  # Run is queued for execution
    RUNNING = "running"  # Run is currently executing
    COMPLETED = "completed"  # Run completed successfully
    FAILED = "failed"  # Run failed with error
    CANCELLED = "cancelled"  # Run was cancelled
    TIMEOUT = "timeout"  # Run timed out


class MetricType(str, Enum):
    """Types of metrics that can be captured."""

    COUNTER = "counter"  # Incrementing counter
    GAUGE = "gauge"  # Current value
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"  # Time-based measurement
    STATUS = "status"  # Status indicator
    ERROR_RATE = "error_rate"  # Error rate percentage
    THROUGHPUT = "throughput"  # Operations per time unit
    LATENCY = "latency"  # Response time
    CUSTOM = "custom"  # Custom metric type


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""

    DOCUMENT = "document"  # Document files (PDF, DOC, etc.)
    IMAGE = "image"  # Image files
    VIDEO = "video"  # Video files
    AUDIO = "audio"  # Audio files
    CODE = "code"  # Source code files
    DATA = "data"  # Data files (JSON, CSV, etc.)
    LOG = "log"  # Log files
    CONFIG = "config"  # Configuration files
    MODEL = "model"  # ML models
    REPORT = "report"  # Generated reports
    SUMMARY = "summary"  # Summary documents
    CHART = "chart"  # Charts and graphs


class RepositoryProvider(str, Enum):
    """Source control provider for a linked repository."""

    GITHUB = "github"


class RepositoryLinkStatus(str, Enum):
    """Status of a repository link."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    IDLE = "idle"  # Agent is idle, ready to accept work
    INITIALIZING = "initializing"  # Agent is initializing
    ACTIVE = "active"  # Agent is active and running
    BUSY = "busy"  # Agent is busy processing
    ERROR = "error"  # Agent encountered an error
    OFFLINE = "offline"  # Agent is offline or disconnected


class AgentMessageDirection(str, Enum):
    """Direction of an agent message in the message log."""

    INBOUND = "inbound"  # Client/user -> agent
    OUTBOUND = "outbound"  # Agent -> client/user
    SYSTEM = "system"  # System-generated lifecycle/event log


class ContextRollbackState(str, Enum):
    """State of context rollback operation."""

    PENDING = "pending"  # Rollback is pending
    SUCCESS = "success"  # Rollback succeeded
    FAILED = "failed"  # Rollback failed


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"  # Workflow is queued for execution
    RUNNING = "running"  # Workflow is currently executing
    COMPLETED = "completed"  # Workflow completed successfully
    FAILED = "failed"  # Workflow failed with error
    CANCELLED = "cancelled"  # Workflow was cancelled
    TIMEOUT = "timeout"  # Workflow timed out


class WorkflowStepStatus(str, Enum):
    """Workflow step execution status."""

    PENDING = "pending"  # Step is queued for execution
    RUNNING = "running"  # Step is currently executing
    COMPLETED = "completed"  # Step completed successfully
    FAILED = "failed"  # Step failed with error
    CANCELLED = "cancelled"  # Step was cancelled
    SKIPPED = "skipped"  # Step was skipped


class WorkflowStepType(str, Enum):
    """Types of workflow steps."""

    TASK = "task"  # Simple task execution
    CONDITION = "condition"  # Conditional branching
    PARALLEL = "parallel"  # Parallel execution
    SEQUENTIAL = "sequential"  # Sequential steps
    AGENT = "agent"  # Agent execution


class SandboxExecutionStatus(str, Enum):
    """Sandbox execution status."""

    PENDING = "pending"  # Execution is queued
    RUNNING = "running"  # Execution is currently running
    COMPLETED = "completed"  # Execution completed successfully
    FAILED = "failed"  # Execution failed with error
    CANCELLED = "cancelled"  # Execution was cancelled
    TIMEOUT = "timeout"  # Execution timed out


class SandboxExecutionLanguage(str, Enum):
    """Supported programming languages for sandbox execution."""

    JAVASCRIPT = "javascript"
    NODE = "node"
    PYTHON = "python"
    PHP = "php"
    DOCKER = "docker"


class QualityGateType(str, Enum):
    """Types of quality gates."""

    LINT = "lint"  # Code linting (ESLint, Ruff, Pint)
    COVERAGE = "coverage"  # Test coverage enforcement
    CONTRACT = "contract"  # API endpoint contract testing
    PERFORMANCE = "performance"  # Performance smoke tests
    SECURITY = "security"  # Security audit and vulnerability scanning
    COMPLEXITY = "complexity"  # Code complexity limits
    TYPE_CHECK = "type_check"  # Type checking (TypeScript, MyPy)


class QualityGateStatus(str, Enum):
    """Quality gate evaluation status."""

    PENDING = "pending"  # Gate evaluation is queued
    RUNNING = "running"  # Gate is currently being evaluated
    PASSED = "passed"  # Gate passed all checks
    FAILED = "failed"  # Gate failed one or more checks
    WARNING = "warning"  # Gate passed but has warnings
    SKIPPED = "skipped"  # Gate was skipped due to configuration
    ERROR = "error"  # Gate evaluation encountered an error
    TIMEOUT = "timeout"  # Gate evaluation timed out


class GateSeverity(str, Enum):
    """Severity levels for gate failures."""

    CRITICAL = "critical"  # Blocking failure
    HIGH = "high"  # Blocking failure
    MEDIUM = "medium"  # Warning level
    LOW = "low"  # Info level


class RoleName(str, Enum):
    """System-defined role names."""

    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class PermissionResource(str, Enum):
    """Resource types for permissions."""

    TASKS = "tasks"
    WORKFLOWS = "workflows"
    REPOSITORIES = "repositories"
    REPOS = "repos"
    AGENTS = "agents"
    SETTINGS = "settings"
    USERS = "users"
    AUDIT = "audit"
    METRICS = "metrics"
    WORKSPACES = "workspaces"
    PROJECTS = "projects"


class PermissionAction(str, Enum):
    """Action types for permissions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    MANAGE = "manage"
    CONNECT = "connect"


class AuditAction(str, Enum):
    """Audit log action types."""

    # User management
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    
    # Role and permission management
    ROLE_CREATED = "ROLE_CREATED"
    ROLE_UPDATED = "ROLE_UPDATED"
    ROLE_DELETED = "ROLE_DELETED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REVOKED = "ROLE_REVOKED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    
    # Workspace management
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_UPDATED = "WORKSPACE_UPDATED"
    WORKSPACE_DELETED = "WORKSPACE_DELETED"
    WORKSPACE_ACCESS_GRANTED = "WORKSPACE_ACCESS_GRANTED"
    WORKSPACE_ACCESS_REVOKED = "WORKSPACE_ACCESS_REVOKED"
    
    # Project management
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    PROJECT_DELETED = "PROJECT_DELETED"
    
    # Task management
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_DELETED = "TASK_DELETED"
    TASK_EXECUTED = "TASK_EXECUTED"
    TASK_RUN_STARTED = "TASK_RUN_STARTED"
    TASK_RUN_COMPLETED = "TASK_RUN_COMPLETED"
    TASK_RUN_FAILED = "TASK_RUN_FAILED"
    
    # Workflow management
    WORKFLOW_CREATED = "WORKFLOW_CREATED"
    WORKFLOW_UPDATED = "WORKFLOW_UPDATED"
    WORKFLOW_DELETED = "WORKFLOW_DELETED"
    WORKFLOW_EXECUTED = "WORKFLOW_EXECUTED"
    WORKFLOW_STEP_EXECUTED = "WORKFLOW_STEP_EXECUTED"
    
    # Repository management
    REPOSITORY_CONNECTED = "REPOSITORY_CONNECTED"
    REPOSITORY_DISCONNECTED = "REPOSITORY_DISCONNECTED"
    REPOSITORY_ACCESS_GRANTED = "REPOSITORY_ACCESS_GRANTED"
    
    # Agent management
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_DELETED = "AGENT_DELETED"
    AGENT_ENABLED = "AGENT_ENABLED"
    AGENT_DISABLED = "AGENT_DISABLED"
    AGENT_MESSAGE_SENT = "AGENT_MESSAGE_SENT"
    
    # System and settings
    SETTINGS_CHANGED = "SETTINGS_CHANGED"
    SYSTEM_BACKUP_CREATED = "SYSTEM_BACKUP_CREATED"
    SYSTEM_MAINTENANCE_MODE_ENABLED = "SYSTEM_MAINTENANCE_MODE_ENABLED"
    
    # Security events
    UNAUTHORIZED_ACCESS_ATTEMPT = "UNAUTHORIZED_ACCESS_ATTEMPT"
    SECURITY_VIOLATION_DETECTED = "SECURITY_VIOLATION_DETECTED"
    
    # Data operations
    DATA_EXPORTED = "DATA_EXPORTED"
    DATA_IMPORTED = "DATA_IMPORTED"
    BULK_OPERATION_PERFORMED = "BULK_OPERATION_PERFORMED"
    
    # Sandbox operations
    SANDBOX_EXECUTION_STARTED = "SANDBOX_EXECUTION_STARTED"
    SANDBOX_EXECUTION_COMPLETED = "SANDBOX_EXECUTION_COMPLETED"
    SANDBOX_EXECUTION_FAILED = "SANDBOX_EXECUTION_FAILED"


class AuditLogStatus(str, Enum):
    """Status of audit log entries."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    WARNING = "warning"
