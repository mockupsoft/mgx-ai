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
