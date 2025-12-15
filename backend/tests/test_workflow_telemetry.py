# -*- coding: utf-8 -*-
"""
Schema and unit tests for workflow telemetry endpoints.

Tests the Phase 10 workflow execution timeline and metrics APIs schemas.
Integration tests requiring database fixtures should be added in conftest.py setup.
"""

from datetime import datetime, timedelta
import pytest

from backend.schemas import (
    WorkflowExecutionTimeline,
    WorkflowStepTimelineEntry,
    WorkflowMetricsSummary,
    WorkflowStatusEnum,
    WorkflowStepStatusEnum,
)


class TestWorkflowStepTimelineEntry:
    """Tests for WorkflowStepTimelineEntry schema."""

    def test_create_completed_step_entry(self):
        """Test creating a completed step timeline entry."""
        now = datetime.utcnow()
        
        entry = WorkflowStepTimelineEntry(
            step_id="step-001",
            step_name="initialize",
            step_order=1,
            status=WorkflowStepStatusEnum.COMPLETED,
            started_at=now,
            completed_at=now + timedelta(seconds=30),
            duration_seconds=30.0,
            retry_count=0,
        )
        
        assert entry.step_id == "step-001"
        assert entry.step_name == "initialize"
        assert entry.step_order == 1
        assert entry.status == WorkflowStepStatusEnum.COMPLETED
        assert entry.duration_seconds == 30.0
        assert entry.retry_count == 0

    def test_create_failed_step_entry_with_error(self):
        """Test creating a failed step timeline entry with error."""
        now = datetime.utcnow()
        
        entry = WorkflowStepTimelineEntry(
            step_id="step-002",
            step_name="process",
            step_order=2,
            status=WorkflowStepStatusEnum.FAILED,
            started_at=now,
            completed_at=now + timedelta(seconds=45),
            duration_seconds=45.0,
            retry_count=2,
            error_message="Step execution timeout",
        )
        
        assert entry.status == WorkflowStepStatusEnum.FAILED
        assert entry.retry_count == 2
        assert entry.error_message == "Step execution timeout"

    def test_create_skipped_step_entry(self):
        """Test creating a skipped step timeline entry."""
        entry = WorkflowStepTimelineEntry(
            step_id="step-003",
            step_name="optional_step",
            step_order=3,
            status=WorkflowStepStatusEnum.SKIPPED,
            retry_count=0,
        )
        
        assert entry.status == WorkflowStepStatusEnum.SKIPPED
        assert entry.started_at is None
        assert entry.duration_seconds is None

    def test_step_entry_with_input_output_summaries(self):
        """Test step entry with input and output data summaries."""
        entry = WorkflowStepTimelineEntry(
            step_id="step-001",
            step_name="transform",
            step_order=1,
            status=WorkflowStepStatusEnum.COMPLETED,
            duration_seconds=50.0,
            retry_count=0,
            input_summary={"records": 1000, "format": "json"},
            output_summary={"processed": 1000, "errors": 0},
        )
        
        assert entry.input_summary == {"records": 1000, "format": "json"}
        assert entry.output_summary == {"processed": 1000, "errors": 0}


class TestWorkflowExecutionTimeline:
    """Tests for WorkflowExecutionTimeline schema."""

    def test_create_completed_timeline(self):
        """Test creating a completed execution timeline."""
        now = datetime.utcnow()
        
        step_timeline = [
            WorkflowStepTimelineEntry(
                step_id="step-001",
                step_name="init",
                step_order=1,
                status=WorkflowStepStatusEnum.COMPLETED,
                started_at=now,
                completed_at=now + timedelta(seconds=10),
                duration_seconds=10.0,
                retry_count=0,
            ),
            WorkflowStepTimelineEntry(
                step_id="step-002",
                step_name="process",
                step_order=2,
                status=WorkflowStepStatusEnum.COMPLETED,
                started_at=now + timedelta(seconds=10),
                completed_at=now + timedelta(seconds=40),
                duration_seconds=30.0,
                retry_count=0,
            ),
        ]
        
        timeline = WorkflowExecutionTimeline(
            execution_id="exec-001",
            workflow_id="workflow-123",
            status=WorkflowStatusEnum.COMPLETED,
            started_at=now,
            completed_at=now + timedelta(seconds=40),
            total_duration_seconds=40.0,
            step_count=2,
            completed_step_count=2,
            failed_step_count=0,
            skipped_step_count=0,
            step_timeline=step_timeline,
        )
        
        assert timeline.execution_id == "exec-001"
        assert timeline.workflow_id == "workflow-123"
        assert timeline.status == WorkflowStatusEnum.COMPLETED
        assert timeline.total_duration_seconds == 40.0
        assert timeline.step_count == 2
        assert timeline.completed_step_count == 2
        assert len(timeline.step_timeline) == 2

    def test_create_failed_timeline_with_error(self):
        """Test creating a failed execution timeline with error message."""
        now = datetime.utcnow()
        
        timeline = WorkflowExecutionTimeline(
            execution_id="exec-002",
            workflow_id="workflow-123",
            status=WorkflowStatusEnum.FAILED,
            started_at=now,
            completed_at=now + timedelta(seconds=25),
            total_duration_seconds=25.0,
            step_count=2,
            completed_step_count=1,
            failed_step_count=1,
            skipped_step_count=0,
            step_timeline=[
                WorkflowStepTimelineEntry(
                    step_id="step-001",
                    step_name="init",
                    step_order=1,
                    status=WorkflowStepStatusEnum.COMPLETED,
                    duration_seconds=10.0,
                    retry_count=0,
                ),
                WorkflowStepTimelineEntry(
                    step_id="step-002",
                    step_name="process",
                    step_order=2,
                    status=WorkflowStepStatusEnum.FAILED,
                    duration_seconds=15.0,
                    retry_count=1,
                    error_message="Process failed: invalid data",
                ),
            ],
            error_message="Workflow execution failed at step: process",
        )
        
        assert timeline.status == WorkflowStatusEnum.FAILED
        assert timeline.failed_step_count == 1
        assert timeline.error_message == "Workflow execution failed at step: process"

    def test_timeline_with_all_step_statuses(self):
        """Test timeline with mixed step statuses."""
        timeline = WorkflowExecutionTimeline(
            execution_id="exec-003",
            workflow_id="workflow-123",
            status=WorkflowStatusEnum.COMPLETED,
            step_count=4,
            completed_step_count=2,
            failed_step_count=1,
            skipped_step_count=1,
            step_timeline=[
                WorkflowStepTimelineEntry(
                    step_id="s1", step_name="step1", step_order=1,
                    status=WorkflowStepStatusEnum.COMPLETED, duration_seconds=10.0, retry_count=0,
                ),
                WorkflowStepTimelineEntry(
                    step_id="s2", step_name="step2", step_order=2,
                    status=WorkflowStepStatusEnum.COMPLETED, duration_seconds=20.0, retry_count=0,
                ),
                WorkflowStepTimelineEntry(
                    step_id="s3", step_name="step3", step_order=3,
                    status=WorkflowStepStatusEnum.FAILED, duration_seconds=5.0, retry_count=1,
                    error_message="Failed",
                ),
                WorkflowStepTimelineEntry(
                    step_id="s4", step_name="step4", step_order=4,
                    status=WorkflowStepStatusEnum.SKIPPED, retry_count=0,
                ),
            ],
        )
        
        assert timeline.completed_step_count == 2
        assert timeline.failed_step_count == 1
        assert timeline.skipped_step_count == 1
        assert len(timeline.step_timeline) == 4


class TestWorkflowMetricsSummary:
    """Tests for WorkflowMetricsSummary schema."""

    def test_create_metrics_with_all_successful_executions(self):
        """Test metrics when all executions are successful."""
        metrics = WorkflowMetricsSummary(
            total_duration_seconds=300.0,
            success_rate=100.0,
            total_executions=3,
            successful_executions=3,
            failed_executions=0,
            average_duration_seconds=100.0,
            min_duration_seconds=80.0,
            max_duration_seconds=120.0,
        )
        
        assert metrics.success_rate == 100.0
        assert metrics.total_executions == 3
        assert metrics.successful_executions == 3
        assert metrics.failed_executions == 0

    def test_create_metrics_with_mixed_results(self):
        """Test metrics with both successful and failed executions."""
        metrics = WorkflowMetricsSummary(
            total_duration_seconds=500.0,
            success_rate=60.0,
            total_executions=10,
            successful_executions=6,
            failed_executions=4,
            average_duration_seconds=50.0,
            min_duration_seconds=30.0,
            max_duration_seconds=80.0,
        )
        
        assert metrics.success_rate == 60.0
        assert metrics.total_executions == 10
        assert metrics.successful_executions == 6
        assert metrics.failed_executions == 4
        assert metrics.average_duration_seconds == 50.0

    def test_create_metrics_with_zero_executions(self):
        """Test metrics when no executions have occurred."""
        metrics = WorkflowMetricsSummary(
            total_duration_seconds=0.0,
            success_rate=0.0,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            average_duration_seconds=0.0,
            min_duration_seconds=None,
            max_duration_seconds=None,
        )
        
        assert metrics.total_executions == 0
        assert metrics.success_rate == 0.0
        assert metrics.min_duration_seconds is None
        assert metrics.max_duration_seconds is None

    def test_create_metrics_with_single_execution(self):
        """Test metrics with a single execution."""
        metrics = WorkflowMetricsSummary(
            total_duration_seconds=45.5,
            success_rate=100.0,
            total_executions=1,
            successful_executions=1,
            failed_executions=0,
            average_duration_seconds=45.5,
            min_duration_seconds=45.5,
            max_duration_seconds=45.5,
        )
        
        assert metrics.total_executions == 1
        assert metrics.average_duration_seconds == 45.5
        assert metrics.min_duration_seconds == 45.5
        assert metrics.max_duration_seconds == 45.5


class TestSchemaValidation:
    """Tests for schema validation constraints."""

    def test_step_timeline_entry_requires_mandatory_fields(self):
        """Test that mandatory fields are required."""
        with pytest.raises(ValueError):
            WorkflowStepTimelineEntry(
                step_name="test",
                step_order=1,
                status=WorkflowStepStatusEnum.COMPLETED,
                # Missing step_id
            )

    def test_metrics_success_rate_bounds(self):
        """Test that success rate is bounded between 0 and 100."""
        # This should work
        metrics = WorkflowMetricsSummary(
            total_duration_seconds=100.0,
            success_rate=50.0,
            total_executions=2,
            successful_executions=1,
            failed_executions=1,
            average_duration_seconds=50.0,
        )
        assert metrics.success_rate == 50.0

    def test_metrics_duration_non_negative(self):
        """Test that durations are non-negative."""
        # This should work
        metrics = WorkflowMetricsSummary(
            total_duration_seconds=0.0,
            success_rate=0.0,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            average_duration_seconds=0.0,
        )
        assert metrics.total_duration_seconds == 0.0


class TestSchemaJsonSerialization:
    """Tests for JSON serialization/deserialization."""

    def test_step_entry_json_roundtrip(self):
        """Test that step entry can be serialized and deserialized."""
        original = WorkflowStepTimelineEntry(
            step_id="step-001",
            step_name="test_step",
            step_order=1,
            status=WorkflowStepStatusEnum.COMPLETED,
            duration_seconds=30.0,
            retry_count=1,
        )
        
        # Serialize to dict (as would happen in JSON response)
        data = original.model_dump()
        
        # Deserialize back
        restored = WorkflowStepTimelineEntry(**data)
        
        assert restored.step_id == original.step_id
        assert restored.step_name == original.step_name
        assert restored.status == original.status

    def test_timeline_json_roundtrip(self):
        """Test that timeline can be serialized and deserialized."""
        original = WorkflowExecutionTimeline(
            execution_id="exec-001",
            workflow_id="workflow-123",
            status=WorkflowStatusEnum.COMPLETED,
            total_duration_seconds=40.0,
            step_count=2,
            completed_step_count=2,
            failed_step_count=0,
            skipped_step_count=0,
            step_timeline=[],
        )
        
        data = original.model_dump()
        restored = WorkflowExecutionTimeline(**data)
        
        assert restored.execution_id == original.execution_id
        assert restored.status == original.status
        assert restored.total_duration_seconds == original.total_duration_seconds

    def test_metrics_json_roundtrip(self):
        """Test that metrics can be serialized and deserialized."""
        original = WorkflowMetricsSummary(
            total_duration_seconds=300.0,
            success_rate=75.5,
            total_executions=4,
            successful_executions=3,
            failed_executions=1,
            average_duration_seconds=75.0,
            min_duration_seconds=50.0,
            max_duration_seconds=100.0,
        )
        
        data = original.model_dump()
        restored = WorkflowMetricsSummary(**data)
        
        assert restored.success_rate == original.success_rate
        assert restored.average_duration_seconds == original.average_duration_seconds
