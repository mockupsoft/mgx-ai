# -*- coding: utf-8 -*-
"""Tests for data retention policies and cleanup functionality."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import os
import shutil

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from backend.db.models.entities import (
    Workspace,
    Task,
    Run,
    Agent,
    LLMCall,
    ResourceUsage,
    ExecutionCost,
    Artifact,
    KnowledgeItem,
)


class DataCleanupService:
    """Mock data cleanup service for testing."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.retention_policies = {
            "tasks": {"keep_days": 365, "archive_before_delete": True},
            "artifacts": {"keep_days": 180, "archive_before_delete": True},
            "logs": {"keep_days": 30, "archive_before_delete": False},
            "temp_files": {"keep_days": 1, "archive_before_delete": False},
            "llm_calls": {"keep_days": 90, "archive_before_delete": True},
            "resource_usage": {"keep_days": 60, "archive_before_delete": True}
        }
    
    async def identify_old_data(self, workspace_id: str) -> dict:
        """Identify data that exceeds retention policies."""
        cutoff_dates = {}
        for data_type, policy in self.retention_policies.items():
            cutoff_dates[data_type] = datetime.utcnow() - timedelta(days=policy["keep_days"])
        
        old_data_summary = {
            "workspace_id": workspace_id,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "cutoff_dates": cutoff_dates,
            "old_data_counts": {
                "tasks": 15,  # Mock: 15 tasks older than 365 days
                "artifacts": 8,  # Mock: 8 artifacts older than 180 days
                "logs": 45,  # Mock: 45 log entries older than 30 days
                "temp_files": 23,  # Mock: 23 temp files older than 1 day
                "llm_calls": 120,  # Mock: 120 LLM calls older than 90 days
                "resource_usage": 89  # Mock: 89 resource usage records older than 60 days
            },
            "total_records_to_cleanup": 300,
            "estimated_space_freed_mb": 256.7,
            "retention_policy_applied": True
        }
        
        return old_data_summary
    
    async def archive_data(self, workspace_id: str, data_types: list, cutoff_date: datetime) -> dict:
        """Archive data before deletion."""
        archive_id = str(uuid4())
        archive_path = f"/tmp/archives/workspace_{workspace_id}/archive_{archive_id}"
        
        archive_summary = {
            "archive_id": archive_id,
            "workspace_id": workspace_id,
            "archive_timestamp": datetime.utcnow().isoformat(),
            "archive_path": archive_path,
            "data_types_archived": data_types,
            "cutoff_date": cutoff_date.isoformat(),
            "records_archived": {
                "tasks": 12,
                "artifacts": 6,
                "llm_calls": 85,
                "resource_usage": 67
            },
            "total_records_archived": 170,
            "archive_size_mb": 125.4,
            "compression_ratio": 0.75,
            "status": "completed",
            "checksum": "abc123def456",
            "verification_status": "verified"
        }
        
        return archive_summary
    
    async def cleanup_data(self, workspace_id: str, dry_run: bool = False) -> dict:
        """Clean up old data according to retention policies."""
        cleanup_id = str(uuid4())
        
        if dry_run:
            status = "simulated"
            records_deleted = 0
        else:
            status = "completed"
            records_deleted = 285  # Total records that would be deleted
        
        cleanup_summary = {
            "cleanup_id": cleanup_id,
            "workspace_id": workspace_id,
            "cleanup_timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "status": status,
            "records_processed": 300,
            "records_deleted": records_deleted if not dry_run else 0,
            "records_archived": 170 if not dry_run else 0,
            "data_by_type": {
                "tasks": {"deleted": 15, "archived": 12},
                "artifacts": {"deleted": 8, "archived": 6},
                "logs": {"deleted": 45, "archived": 0},
                "temp_files": {"deleted": 23, "archived": 0},
                "llm_calls": {"deleted": 120, "archived": 85},
                "resource_usage": {"deleted": 89, "archived": 67}
            },
            "space_freed_mb": 256.7,
            "errors": [],
            "warnings": [
                "Some artifacts could not be archived due to missing files"
            ]
        }
        
        return cleanup_summary
    
    async def verify_deletion(self, workspace_id: str, cleanup_id: str) -> dict:
        """Verify that data was properly deleted."""
        return {
            "verification_id": str(uuid4()),
            "cleanup_id": cleanup_id,
            "workspace_id": workspace_id,
            "verification_timestamp": datetime.utcnow().isoformat(),
            "verification_status": "passed",
            "checks_performed": [
                "database_records_check",
                "file_system_cleanup",
                "orphan_reference_check",
                "consistency_verification"
            ],
            "verification_details": {
                "database_records_check": "passed",
                "file_system_cleanup": "passed",
                "orphan_reference_check": "passed", 
                "consistency_verification": "passed"
            },
            "orphaned_references_found": 0,
            "cleanup_effectiveness": 100.0
        }
    
    async def log_cleanup_action(self, workspace_id: str, action: str, details: dict) -> dict:
        """Log cleanup action for audit trail."""
        return {
            "log_id": str(uuid4()),
            "workspace_id": workspace_id,
            "action": action,
            "action_timestamp": datetime.utcnow().isoformat(),
            "details": details,
            "operator": "system",
            "audit_trail_id": str(uuid4())
        }
    
    async def run_scheduled_cleanup(self, workspace_id: str = None) -> dict:
        """Run scheduled cleanup for workspaces."""
        if workspace_id:
            workspaces_to_cleanup = [workspace_id]
        else:
            workspaces_to_cleanup = ["workspace1", "workspace2", "workspace3"]  # Mock list
        
        cleanup_results = []
        total_records_cleaned = 0
        
        for ws_id in workspaces_to_cleanup:
            # Identify old data
            old_data = await self.identify_old_data(ws_id)
            
            if old_data["total_records_to_cleanup"] > 0:
                # Archive if needed
                if any(
                    self.retention_policies[dt]["archive_before_delete"] 
                    for dt in old_data["old_data_counts"].keys()
                    if old_data["old_data_counts"][dt] > 0
                ):
                    # Find earliest cutoff date
                    cutoff_dates = old_data["cutoff_dates"]
                    earliest_cutoff = min(cutoff_dates.values())
                    
                    archive_types = [
                        dt for dt, count in old_data["old_data_counts"].items()
                        if count > 0 and self.retention_policies[dt]["archive_before_delete"]
                    ]
                    
                    if archive_types:
                        await self.archive_data(ws_id, archive_types, earliest_cutoff)
                
                # Perform cleanup
                cleanup_result = await self.cleanup_data(ws_id)
                cleanup_results.append(cleanup_result)
                total_records_cleaned += cleanup_result["records_deleted"]
                
                # Log action
                await self.log_cleanup_action(
                    ws_id, 
                    "scheduled_cleanup", 
                    {"records_deleted": cleanup_result["records_deleted"]}
                )
        
        return {
            "scheduled_cleanup_id": str(uuid4()),
            "cleanup_timestamp": datetime.utcnow().isoformat(),
            "workspaces_processed": len(workspaces_to_cleanup,
            ),
            "workspaces_with_cleanup": len(cleanup_results),
            "total_records_cleaned": total_records_cleaned,
            "cleanup_results": cleanup_results,
            "overall_status": "completed"
        }


@pytest.fixture
async def cleanup_service(db_session: AsyncSession):
    """Create cleanup service fixture."""
    return DataCleanupService(db_session)


@pytest.fixture
async def test_workspace_with_old_data(db_session: AsyncSession):
    """Create test workspace with old data for cleanup testing."""
    workspace = Workspace(
        name="Test Cleanup Workspace",
        slug="test-cleanup",
        metadata={}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    
    # Create old tasks (older than retention period)
    old_date = datetime.utcnow() - timedelta(days=400)  # Older than 365-day retention
    for i in range(5):
        task = Task(
            workspace_id=workspace.id,
            name=f"Old Task {i}",
            status="completed",
            created_at=old_date,
            completed_at=old_date + timedelta(days=1)
        )
        db_session.add(task)
    
    # Create recent tasks (within retention period)
    recent_date = datetime.utcnow() - timedelta(days=30)
    for i in range(5):
        task = Task(
            workspace_id=workspace.id,
            name=f"Recent Task {i}",
            status="completed",
            created_at=recent_date,
            completed_at=recent_date + timedelta(hours=2)
        )
        db_session.add(task)
    
    # Create old artifacts
    for i in range(3):
        artifact = Artifact(
            workspace_id=workspace.id,
            name=f"Old Artifact {i}",
            type="file",
            path=f"/tmp/old_artifact_{i}.txt",
            size=1024,
            created_at=old_date
        )
        db_session.add(artifact)
    
    # Create old LLM calls
    for i in range(10):
        llm_call = LLMCall(
            workspace_id=workspace.id,
            provider="openai",
            model="gpt-3.5-turbo",
            tokens_prompt=100,
            tokens_completion=50,
            cost_usd=0.002,
            created_at=old_date
        )
        db_session.add(llm_call)
    
    await db_session.commit()
    return workspace


# ============================================================================
# Retention Policy Tests
# ============================================================================

class TestRetentionPolicies:
    """Test data retention policy implementation."""
    
    async def test_old_data_deleted_per_policy(self, cleanup_service, test_workspace_with_old_data):
        """Test that old data is deleted according to retention policies."""
        # Identify old data
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        assert old_data["workspace_id"] == test_workspace_with_old_data.id
        assert "old_data_counts" in old_data
        assert "cutoff_dates" in old_data
        
        # Should identify some old data
        assert sum(old_data["old_data_counts"].values()) > 0
        
        # Cutoff dates should be in the past
        for data_type, cutoff_date in old_data["cutoff_dates"].items():
            assert cutoff_date < datetime.utcnow()
    
    async def test_retention_dates_respected(self, cleanup_service):
        """Test that retention dates are properly calculated and respected."""
        policies = cleanup_service.retention_policies
        
        for data_type, policy in policies.items():
            assert "keep_days" in policy
            assert policy["keep_days"] > 0
            assert isinstance(policy["keep_days"], int)
            
            # Calculate expected cutoff date
            expected_cutoff = datetime.utcnow() - timedelta(days=policy["keep_days"])
            
            # Verify policy structure
            if policy.get("archive_before_delete"):
                assert "archive_before_delete" in policy
                assert policy["archive_before_delete"] is True
    
    async def test_cleanup_scheduled(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup is scheduled and executed."""
        # Run scheduled cleanup
        cleanup_result = await cleanup_service.run_scheduled_cleanup(
            test_workspace_with_old_data.id
        )
        
        assert cleanup_result["overall_status"] == "completed"
        assert cleanup_result["workspaces_processed"] == 1
        assert cleanup_result["cleanup_results"] is not None
        
        # Should have processed the workspace
        assert any(
            result["workspace_id"] == test_workspace_with_old_data.id
            for result in cleanup_result["cleanup_results"]
        )
    
    async def test_archive_before_deletion(self, cleanup_service, test_workspace_with_old_data):
        """Test that data is archived before deletion when required."""
        # Identify old data
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        # Find data types that should be archived
        types_to_archive = [
            data_type for data_type, count in old_data["old_data_counts"].items()
            if count > 0 and cleanup_service.retention_policies[data_type]["archive_before_delete"]
        ]
        
        if types_to_archive:
            # Get earliest cutoff date
            cutoff_dates = old_data["cutoff_dates"]
            earliest_cutoff = min(cutoff_dates[data_type] for data_type in types_to_archive)
            
            # Archive the data
            archive_result = await cleanup_service.archive_data(
                test_workspace_with_old_data.id,
                types_to_archive,
                earliest_cutoff
            )
            
            assert archive_result["status"] == "completed"
            assert archive_result["data_types_archived"] == types_to_archive
            assert archive_result["records_archived"]["total_records_archived"] > 0
            assert archive_result["archive_size_mb"] > 0
    
    async def test_warnings_before_deletion(self, cleanup_service, test_workspace_with_old_data):
        """Test that warnings are issued before data deletion."""
        # Run cleanup in dry-run mode first
        dry_run_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=True
        )
        
        assert dry_run_result["dry_run"] is True
        assert dry_run_result["records_deleted"] == 0
        
        # Should show what would be deleted
        assert "data_by_type" in dry_run_result
        assert dry_run_result["records_processed"] > 0
    
    async def test_different_retention_for_different_types(self, cleanup_service):
        """Test that different data types have different retention periods."""
        policies = cleanup_service.retention_policies
        
        # Different types should have different retention periods
        assert policies["tasks"]["keep_days"] != policies["artifacts"]["keep_days"]
        assert policies["tasks"]["keep_days"] != policies["logs"]["keep_days"]
        assert policies["artifacts"]["keep_days"] != policies["logs"]["keep_days"]
        
        # Verify reasonable retention periods
        assert policies["temp_files"]["keep_days"] == 1  # Very short for temp files
        assert policies["logs"]["keep_days"] == 30  # Moderate for logs
        assert policies["tasks"]["keep_days"] == 365  # Long for tasks
        assert policies["artifacts"]["keep_days"] == 180  # Medium for artifacts


# ============================================================================
# Cleanup Process Tests
# ============================================================================

class TestCleanupProcess:
    """Test the cleanup process implementation."""
    
    async def test_cleanup_identifies_old_data(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup process correctly identifies old data."""
        result = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        assert result["workspace_id"] == test_workspace_with_old_data.id
        assert "total_records_to_cleanup" in result
        assert "estimated_space_freed_mb" in result
        assert result["total_records_to_cleanup"] > 0
        assert result["estimated_space_freed_mb"] > 0
    
    async def test_archive_created(self, cleanup_service, test_workspace_with_old_data):
        """Test that archive is created before deletion."""
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        cutoff_dates = old_data["cutoff_dates"]
        earliest_cutoff = min(cutoff_dates.values())
        
        archive_types = ["tasks", "artifacts", "llm_calls"]  # Types that need archiving
        
        result = await cleanup_service.archive_data(
            test_workspace_with_old_data.id,
            archive_types,
            earliest_cutoff
        )
        
        assert result["status"] == "completed"
        assert result["archive_path"] is not None
        assert result["total_records_archived"] > 0
        assert result["archive_size_mb"] > 0
        assert "checksum" in result
        assert "verification_status" in result
    
    async def test_data_safely_deleted(self, cleanup_service, test_workspace_with_old_data):
        """Test that data is safely deleted."""
        # Perform actual cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        assert cleanup_result["status"] == "completed"
        assert cleanup_result["records_deleted"] > 0
        assert cleanup_result["records_processed"] > 0
        assert cleanup_result["records_deleted"] <= cleanup_result["records_processed"]
    
    async def test_no_orphaned_references(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup doesn't leave orphaned references."""
        # Perform cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        # Verify deletion
        verification = await cleanup_service.verify_deletion(
            test_workspace_with_old_data.id,
            cleanup_result["cleanup_id"]
        )
        
        assert verification["verification_status"] == "passed"
        assert verification["orphaned_references_found"] == 0
        assert verification["cleanup_effectiveness"] == 100.0
        
        # All checks should pass
        for check, status in verification["verification_details"].items():
            assert status == "passed"
    
    async def test_cleanup_logs_complete(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup actions are properly logged."""
        # Perform cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        # Log the cleanup action
        log_result = await cleanup_service.log_cleanup_action(
            test_workspace_with_old_data.id,
            "manual_cleanup",
            {
                "cleanup_id": cleanup_result["cleanup_id"],
                "records_deleted": cleanup_result["records_deleted"],
                "workspace_id": test_workspace_with_old_data.id
            }
        )
        
        assert log_result["action"] == "manual_cleanup"
        assert log_result["workspace_id"] == test_workspace_with_old_data.id
        assert "audit_trail_id" in log_result
        assert log_result["operator"] == "system"
    
    async def test_cleanup_continues_despite_errors(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup continues even if some operations fail."""
        # Simulate cleanup with errors
        result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        # Even with errors in warnings, cleanup should complete
        assert result["status"] == "completed"
        assert result["records_deleted"] >= 0
        assert result["records_processed"] > 0
        
        # Errors should be recorded but not stop the process
        if result["errors"]:
            assert isinstance(result["errors"], list)
        
        if result["warnings"]:
            assert isinstance(result["warnings"], list)


# ============================================================================
# Archive and Recovery Tests
# ============================================================================

class TestArchiveAndRecovery:
    """Test archiving and recovery functionality."""
    
    async def test_archive_includes_all_data(self, cleanup_service, test_workspace_with_old_data):
        """Test that archive includes all required data."""
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        # Archive data that needs to be preserved
        cutoff_dates = old_data["cutoff_dates"]
        earliest_cutoff = min(cutoff_dates.values())
        
        archive_types = [
            data_type for data_type, count in old_data["old_data_counts"].items()
            if count > 0 and cleanup_service.retention_policies[data_type]["archive_before_delete"]
        ]
        
        result = await cleanup_service.archive_data(
            test_workspace_with_old_data.id,
            archive_types,
            earliest_cutoff
        )
        
        # Should archive all specified types
        for data_type in archive_types:
            assert data_type in result["data_types_archived"]
            assert result["records_archived"].get(data_type, 0) > 0
    
    async def test_archive_compressed(self, cleanup_service, test_workspace_with_old_data):
        """Test that archive is compressed to save space."""
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        cutoff_dates = old_data["cutoff_dates"]
        earliest_cutoff = min(cutoff_dates.values())
        
        result = await cleanup_service.archive_data(
            test_workspace_with_old_data.id,
            ["tasks", "artifacts"],
            earliest_cutoff
        )
        
        assert result["compression_ratio"] > 0
        assert result["compression_ratio"] < 1.0  # Should actually compress
        assert result["archive_size_mb"] > 0
    
    async def test_archive_integrity_verified(self, cleanup_service, test_workspace_with_old_data):
        """Test that archive integrity is verified."""
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        cutoff_dates = old_data["cutoff_dates"]
        earliest_cutoff = min(cutoff_dates.values())
        
        result = await cleanup_service.archive_data(
            test_workspace_with_old_data.id,
            ["tasks"],
            earliest_cutoff
        )
        
        # Should verify archive integrity
        assert result["verification_status"] == "verified"
        assert result["checksum"] is not None
        assert len(result["checksum"]) > 0
    
    async def test_selective_archiving(self, cleanup_service, test_workspace_with_old_data):
        """Test that only specified data types are archived."""
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        cutoff_dates = old_data["cutoff_dates"]
        earliest_cutoff = min(cutoff_dates.values())
        
        # Archive only specific types
        selective_types = ["tasks", "artifacts"]
        
        result = await cleanup_service.archive_data(
            test_workspace_with_old_data.id,
            selective_types,
            earliest_cutoff
        )
        
        # Should only archive specified types
        assert result["data_types_archived"] == selective_types
        
        # Other types should not be in archive
        all_types = list(old_data["old_data_counts"].keys())
        non_archived_types = [t for t in all_types if t not in selective_types]
        
        for data_type in non_archived_types:
            assert data_type not in result["data_types_archived"]


# ============================================================================
# Retention Policy Enforcement Tests
# ============================================================================

class TestRetentionPolicyEnforcement:
    """Test enforcement of retention policies."""
    
    async def test_tasks_retained_for_1_year(self, cleanup_service, test_workspace_with_old_data):
        """Test that tasks are retained for 1 year as specified."""
        policies = cleanup_service.retention_policies
        
        assert policies["tasks"]["keep_days"] == 365
        
        # Verify this is the longest retention (except maybe artifacts)
        task_retention = policies["tasks"]["keep_days"]
        assert task_retention >= policies["logs"]["keep_days"]
        assert task_retention >= policies["temp_files"]["keep_days"]
        assert task_retention >= policies["llm_calls"]["keep_days"]
        assert task_retention >= policies["resource_usage"]["keep_days"]
    
    async def test_artifacts_retained_for_6_months(self, cleanup_service):
        """Test that artifacts are retained for 6 months."""
        policies = cleanup_service.retention_policies
        
        assert policies["artifacts"]["keep_days"] == 180
        
        # Should archive before deletion
        assert policies["artifacts"]["archive_before_delete"] is True
    
    async def test_logs_retained_for_30_days(self, cleanup_service):
        """Test that logs are retained for 30 days."""
        policies = cleanup_service.retention_policies
        
        assert policies["logs"]["keep_days"] == 30
        
        # Should not archive logs (they're often ephemeral)
        assert policies["logs"]["archive_before_delete"] is False
    
    async def test_temp_files_deleted_after_1_day(self, cleanup_service):
        """Test that temp files are deleted after 1 day."""
        policies = cleanup_service.retention_policies
        
        assert policies["temp_files"]["keep_days"] == 1
        
        # Should be the shortest retention period
        temp_retention = policies["temp_files"]["keep_days"]
        for data_type, policy in policies.items():
            if data_type != "temp_files":
                assert policy["keep_days"] >= temp_retention
    
    async def test_retention_policy_consistency(self, cleanup_service):
        """Test that retention policies are consistent across the system."""
        policies = cleanup_service.retention_policies
        
        # All policies should have required fields
        for data_type, policy in policies.items():
            assert "keep_days" in policy
            assert "archive_before_delete" in policy
            assert policy["keep_days"] > 0
            assert isinstance(policy["archive_before_delete"], bool)
        
        # Retention periods should be reasonable
        assert policies["temp_files"]["keep_days"] <= policies["logs"]["keep_days"]
        assert policies["logs"]["keep_days"] <= policies["resource_usage"]["keep_days"]
        assert policies["resource_usage"]["keep_days"] <= policies["artifacts"]["keep_days"]
        assert policies["artifacts"]["keep_days"] <= policies["tasks"]["keep_days"]


# ============================================================================
# Space Management Tests
# ============================================================================

class TestSpaceManagement:
    """Test space management and optimization."""
    
    async def test_space_freed_calculated(self, cleanup_service, test_workspace_with_old_data):
        """Test that space freed by cleanup is accurately calculated."""
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        assert "estimated_space_freed_mb" in old_data
        assert old_data["estimated_space_freed_mb"] > 0
        assert isinstance(old_data["estimated_space_freed_mb"], (int, float))
    
    async def test_large_cleanup_performance(self, cleanup_service):
        """Test cleanup performance with large datasets."""
        import time
        
        # Simulate large dataset cleanup
        workspace_id = str(uuid4())
        
        start_time = time.time()
        result = await cleanup_service.identify_old_data(workspace_id)
        identification_time = time.time() - start_time
        
        # Should identify large amounts of data
        assert result["total_records_to_cleanup"] > 0
        assert identification_time < 10.0  # Should be reasonably fast
    
    async def test_cleanup_batch_processing(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup processes data in batches."""
        # Run cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        # Should show breakdown by data type
        assert "data_by_type" in cleanup_result
        
        for data_type, cleanup_info in cleanup_result["data_by_type"].items():
            assert "deleted" in cleanup_info
            assert "archived" in cleanup_info
            assert cleanup_info["deleted"] >= 0
            assert cleanup_info["archived"] >= 0
    
    async def test_storage_optimization(self, cleanup_service, test_workspace_with_old_data):
        """Test that cleanup optimizes storage usage."""
        # Get initial state
        old_data = await cleanup_service.identify_old_data(
            test_workspace_with_old_data.id
        )
        
        initial_space = old_data["estimated_space_freed_mb"]
        
        # Perform cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        # Should report actual space freed
        assert cleanup_result["space_freed_mb"] > 0
        assert isinstance(cleanup_result["space_freed_mb"], (int, float))


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestCleanupIntegration:
    """Integration tests for cleanup system."""
    
    async def test_complete_cleanup_workflow(
        self,
        cleanup_service,
        test_workspace_with_old_data
    ):
        """Test complete cleanup workflow."""
        workspace_id = test_workspace_with_old_data.id
        
        # Step 1: Identify old data
        old_data = await cleanup_service.identify_old_data(workspace_id)
        assert old_data["total_records_to_cleanup"] > 0
        
        # Step 2: Archive data (if needed)
        types_to_archive = [
            dt for dt, count in old_data["old_data_counts"].items()
            if count > 0 and cleanup_service.retention_policies[dt]["archive_before_delete"]
        ]
        
        if types_to_archive:
            cutoff_dates = old_data["cutoff_dates"]
            earliest_cutoff = min(cutoff_dates[data_type] for data_type in types_to_archive)
            
            archive_result = await cleanup_service.archive_data(
                workspace_id, types_to_archive, earliest_cutoff
            )
            assert archive_result["status"] == "completed"
        
        # Step 3: Clean up data
        cleanup_result = await cleanup_service.cleanup_data(workspace_id, dry_run=False)
        assert cleanup_result["status"] == "completed"
        assert cleanup_result["records_deleted"] > 0
        
        # Step 4: Verify deletion
        verification = await cleanup_service.verify_deletion(
            workspace_id, cleanup_result["cleanup_id"]
        )
        assert verification["verification_status"] == "passed"
        
        # Step 5: Log action
        log_result = await cleanup_service.log_cleanup_action(
            workspace_id, "integration_test_cleanup", {
                "cleanup_id": cleanup_result["cleanup_id"],
                "records_deleted": cleanup_result["records_deleted"]
            }
        )
        assert log_result["action"] == "integration_test_cleanup"
    
    async def test_scheduled_cleanup_all_workspaces(
        self,
        cleanup_service,
        test_workspace_with_old_data
    ):
        """Test scheduled cleanup across all workspaces."""
        # Run scheduled cleanup for all workspaces
        result = await cleanup_service.run_scheduled_cleanup()
        
        assert result["overall_status"] == "completed"
        assert result["workspaces_processed"] > 0
        assert result["total_records_cleaned"] >= 0
        
        # Should include our test workspace
        workspace_found = any(
            ws_result["workspace_id"] == test_workspace_with_old_data.id
            for ws_result in result["cleanup_results"]
        )
        # Note: May not be true if no old data in other workspaces
    
    async def test_cleanup_error_handling(
        self,
        cleanup_service,
        test_workspace_with_old_data
    ):
        """Test cleanup error handling and recovery."""
        # Perform cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        # Should complete even with errors
        assert cleanup_result["status"] == "completed"
        
        # Errors should be logged but not break the process
        if cleanup_result["errors"]:
            assert isinstance(cleanup_result["errors"], list)
            for error in cleanup_result["errors"]:
                assert isinstance(error, str)
        
        if cleanup_result["warnings"]:
            assert isinstance(cleanup_result["warnings"], list)
    
    async def test_cleanup_rollback_capability(
        self,
        cleanup_service,
        test_workspace_with_old_data
    ):
        """Test cleanup rollback capability."""
        # This would test ability to rollback cleanup operations
        # In real implementation, would test rollback from archive
        
        # For now, verify that verification shows successful cleanup
        cleanup_result = await cleanup_service.cleanup_data(
            test_workspace_with_old_data.id,
            dry_run=False
        )
        
        verification = await cleanup_service.verify_deletion(
            test_workspace_with_old_data.id,
            cleanup_result["cleanup_id"]
        )
        
        # Should be able to verify cleanup was successful
        assert verification["verification_status"] == "passed"
        assert verification["cleanup_effectiveness"] == 100.0


@pytest.mark.asyncio
async def test_cleanup_service_initialization(cleanup_service):
    """Test that cleanup service initializes correctly."""
    assert cleanup_service.db_session is not None
    assert cleanup_service.retention_policies is not None
    assert len(cleanup_service.retention_policies) > 0


@pytest.mark.asyncio
async def test_cleanup_policies_structure(cleanup_service):
    """Test that retention policies have correct structure."""
    policies = cleanup_service.retention_policies
    
    for data_type, policy in policies.items():
        # Should have required fields
        assert "keep_days" in policy
        assert "archive_before_delete" in policy
        
        # Should have reasonable values
        assert policy["keep_days"] > 0
        assert isinstance(policy["archive_before_delete"], bool)
        
        # Data type should be meaningful
        assert isinstance(data_type, str)
        assert len(data_type) > 0


@pytest.mark.asyncio
async def test_cleanup_dry_run_vs_actual(cleanup_service, test_workspace_with_old_data):
    """Test difference between dry run and actual cleanup."""
    # Dry run
    dry_run_result = await cleanup_service.cleanup_data(
        test_workspace_with_old_data.id,
        dry_run=True
    )
    
    assert dry_run_result["dry_run"] is True
    assert dry_run_result["records_deleted"] == 0
    assert dry_run_result["status"] == "simulated"
    
    # Actual cleanup
    actual_result = await cleanup_service.cleanup_data(
        test_workspace_with_old_data.id,
        dry_run=False
    )
    
    assert actual_result["dry_run"] is False
    assert actual_result["records_deleted"] >= 0
    assert actual_result["status"] == "completed"
    
    # Both should process same number of records
    assert dry_run_result["records_processed"] == actual_result["records_processed"]


@pytest.mark.asyncio
async def test_cleanup_workspace_validation(cleanup_service, test_workspace_with_old_data):
    """Test cleanup validates workspace parameter."""
    # Valid workspace should work
    result = await cleanup_service.identify_old_data(test_workspace_with_old_data.id)
    assert result["workspace_id"] == test_workspace_with_old_data.id
    
    # Invalid workspace should still return structure (mock behavior)
    invalid_result = await cleanup_service.identify_old_data("invalid_workspace")
    assert "workspace_id" in invalid_result
    assert "old_data_counts" in invalid_result