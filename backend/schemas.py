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


# ============================================
# Task Schemas
# ============================================

class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Task configuration")
    max_rounds: Optional[int] = Field(5, ge=1, le=100, description="Maximum execution rounds")
    max_revision_rounds: Optional[int] = Field(2, ge=0, le=50, description="Maximum revision rounds")
    memory_size: Optional[int] = Field(50, ge=1, le=1000, description="Team memory size")

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


class TaskResponse(BaseModel):
    """Schema for task responses."""
    id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    status: TaskStatusEnum
    max_rounds: int
    max_revision_rounds: int
    memory_size: int
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
    task_id: str
    run_number: int
    status: RunStatusEnum
    plan: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    memory_used: Optional[int] = None
    round_count: Optional[int] = None
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
# Metrics Schemas
# ============================================

class MetricResponse(BaseModel):
    """Schema for metric responses."""
    id: str
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
    task_id: str = Field(..., description="Associated task ID")
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


# ============================================
# Health Check Schemas
# ============================================

class HealthStatus(BaseModel):
    """Schema for health check responses."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "0.1.0"
    checks: Optional[Dict[str, Any]] = None


__all__ = [
    # Enums
    'TaskStatusEnum',
    'RunStatusEnum',
    'EventTypeEnum',
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
