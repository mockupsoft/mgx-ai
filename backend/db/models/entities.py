# -*- coding: utf-8 -*-
"""
Database models for tasks, runs, metrics, and artifacts.

These models represent the core data entities for the dashboard:
- Task: Individual task definitions and configuration
- TaskRun: Individual executions/runs of tasks
- MetricSnapshot: Performance and system metrics
- Artifact: Generated files and outputs from tasks/runs
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, JSON, Boolean, Integer, DateTime, 
    ForeignKey, Index, Enum as SQLEnum, Float, BigInteger,
    func, select
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, SerializationMixin
from .enums import TaskStatus, RunStatus, MetricType, ArtifactType


class Task(Base, TimestampMixin, SerializationMixin):
    """Task model representing individual task definitions."""
    
    __tablename__ = "tasks"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Basic task information
    name = Column(String(255), nullable=False, index=True, comment="Task name")
    description = Column(Text, comment="Task description")
    
    # Task configuration (JSON blob for flexible configuration)
    config = Column(JSON, nullable=False, default=dict, comment="Task configuration")
    
    # Task state
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    
    # MGX-specific settings
    max_rounds = Column(Integer, default=5, comment="Maximum execution rounds")
    max_revision_rounds = Column(Integer, default=2, comment="Maximum revision rounds")
    memory_size = Column(Integer, default=50, comment="Team memory size")
    
    # Execution tracking
    total_runs = Column(Integer, default=0, comment="Total number of runs")
    successful_runs = Column(Integer, default=0, comment="Successful runs count")
    failed_runs = Column(Integer, default=0, comment="Failed runs count")
    
    # Last execution information
    last_run_at = Column(DateTime(timezone=True), comment="Last run timestamp")
    last_run_duration = Column(Float, comment="Last run duration in seconds")
    last_error = Column(Text, comment="Last execution error message")
    
    # Relationships
    runs = relationship("TaskRun", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, name='{self.name}', status='{self.status}')>"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100


class TaskRun(Base, TimestampMixin, SerializationMixin):
    """TaskRun model representing individual executions of tasks."""
    
    __tablename__ = "task_runs"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Foreign key to parent task
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    
    # Run information
    run_number = Column(Integer, nullable=False, comment="Sequence number within task")
    
    # Execution status and results
    status = Column(SQLEnum(RunStatus), nullable=False, default=RunStatus.PENDING, index=True)
    
    # MGX execution data
    plan = Column(JSON, comment="Execution plan")
    results = Column(JSON, comment="Execution results")
    
    # Timing information
    started_at = Column(DateTime(timezone=True), comment="Run start time")
    completed_at = Column(DateTime(timezone=True), comment="Run completion time")
    duration = Column(Float, comment="Duration in seconds")
    
    # Error information
    error_message = Column(Text, comment="Error message if failed")
    error_details = Column(JSON, comment="Detailed error information")
    
    # Memory and resource usage
    memory_used = Column(Integer, comment="Memory used in MB")
    round_count = Column(Integer, comment="Number of rounds executed")
    
    # Relationships
    task = relationship("Task", back_populates="runs")
    metrics = relationship("MetricSnapshot", back_populates="task_run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="task_run", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<TaskRun(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"
    
    @property
    def is_success(self) -> bool:
        """Check if run completed successfully."""
        return self.status == RunStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if run failed."""
        return self.status == RunStatus.FAILED


class MetricSnapshot(Base, TimestampMixin, SerializationMixin):
    """MetricSnapshot model for storing performance and system metrics."""
    
    __tablename__ = "metric_snapshots"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Foreign key relationships
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    task_run_id = Column(String(36), ForeignKey("task_runs.id"), nullable=True, index=True)
    
    # Metric information
    name = Column(String(255), nullable=False, index=True, comment="Metric name")
    metric_type = Column(SQLEnum(MetricType), nullable=False, comment="Type of metric")
    value = Column(Float, nullable=False, comment="Metric value")
    unit = Column(String(50), comment="Unit of measurement")
    
    # Additional metric data
    labels = Column(JSON, comment="Metric labels/tags")
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now(), comment="Measurement timestamp")
    
    # Relationships
    task = relationship("Task")
    task_run = relationship("TaskRun", back_populates="metrics")
    
    def __repr__(self) -> str:
        return f"<MetricSnapshot(id={self.id}, name='{self.name}', value={self.value})>"


class Artifact(Base, TimestampMixin, SerializationMixin):
    """Artifact model for storing generated files and outputs."""
    
    __tablename__ = "artifacts"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Foreign key relationships
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    task_run_id = Column(String(36), ForeignKey("task_runs.id"), nullable=True, index=True)
    
    # Artifact information
    name = Column(String(255), nullable=False, comment="Artifact name")
    artifact_type = Column(SQLEnum(ArtifactType), nullable=False, comment="Type of artifact")
    
    # File information
    file_path = Column(Text, comment="File path or URL")
    file_size = Column(BigInteger, comment="File size in bytes")
    file_hash = Column(String(64), comment="SHA256 hash for integrity")
    
    # Content information
    content_type = Column(String(100), comment="MIME type")
    content = Column(Text, comment="Text content or metadata")
    
    # Metadata
    meta_data = Column(JSON, comment="Additional metadata")
    
    # Relationships
    task = relationship("Task")
    task_run = relationship("TaskRun", back_populates="artifacts")
    
    def __repr__(self) -> str:
        return f"<Artifact(id={self.id}, name='{self.name}', type='{self.artifact_type}')>"


# Create indexes for performance optimization
Index('idx_task_runs_task_id_status', TaskRun.task_id, TaskRun.status)
Index('idx_task_runs_started_at', TaskRun.started_at)
Index('idx_metric_snapshots_task_run_timestamp', MetricSnapshot.task_run_id, MetricSnapshot.timestamp)
Index('idx_metric_snapshots_name_timestamp', MetricSnapshot.name, MetricSnapshot.timestamp)
Index('idx_artifacts_task_run_type', Artifact.task_run_id, Artifact.artifact_type)
Index('idx_artifacts_file_hash', Artifact.file_hash)


# Export all models and enums
__all__ = [
    'Task', 'TaskRun', 'MetricSnapshot', 'Artifact',
    'TaskStatus', 'RunStatus', 'MetricType', 'ArtifactType'
]