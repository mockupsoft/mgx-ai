# -*- coding: utf-8 -*-
"""
Database enums for status types and other constants.
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"      # Task is queued for execution
    RUNNING = "running"      # Task is currently executing
    COMPLETED = "completed"  # Task completed successfully
    FAILED = "failed"        # Task failed with error
    CANCELLED = "cancelled"  # Task was cancelled
    TIMEOUT = "timeout"      # Task timed out


class RunStatus(str, Enum):
    """Task run execution status."""
    PENDING = "pending"      # Run is queued for execution
    RUNNING = "running"      # Run is currently executing
    COMPLETED = "completed"  # Run completed successfully
    FAILED = "failed"        # Run failed with error
    CANCELLED = "cancelled"  # Run was cancelled
    TIMEOUT = "timeout"      # Run timed out


class MetricType(str, Enum):
    """Types of metrics that can be captured."""
    COUNTER = "counter"              # Incrementing counter
    GAUGE = "gauge"                  # Current value
    HISTOGRAM = "histogram"          # Distribution of values
    TIMER = "timer"                  # Time-based measurement
    STATUS = "status"                # Status indicator
    ERROR_RATE = "error_rate"        # Error rate percentage
    THROUGHPUT = "throughput"        # Operations per time unit
    LATENCY = "latency"              # Response time
    CUSTOM = "custom"                # Custom metric type


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""
    DOCUMENT = "document"            # Document files (PDF, DOC, etc.)
    IMAGE = "image"                  # Image files
    VIDEO = "video"                  # Video files
    AUDIO = "audio"                  # Audio files
    CODE = "code"                    # Source code files
    DATA = "data"                    # Data files (JSON, CSV, etc.)
    LOG = "log"                      # Log files
    CONFIG = "config"                # Configuration files
    MODEL = "model"                  # ML models
    REPORT = "report"                # Generated reports
    SUMMARY = "summary"              # Summary documents
    CHART = "chart"                  # Charts and graphs