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


class ContextRollbackState(str, Enum):
    """State of context rollback operation."""

    PENDING = "pending"  # Rollback is pending
    SUCCESS = "success"  # Rollback succeeded
    FAILED = "failed"  # Rollback failed
