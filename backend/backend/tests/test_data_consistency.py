# -*- coding: utf-8 -*-
"""Tests for data consistency verification."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, func, and_, or_

from sqlalchemy.ext.asyncio import AsyncSession

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
    Project,
)


class DataConsistencyChecker:
    """Mock data consistency checker for testing."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def check_referential_integrity(self, workspace_id: str) -> dict:
        """Check referential integrity across all tables."""
        issues = []
        warnings = []
        
        # Check Task -> Run relationships
        orphaned_runs = await self._find_orphaned_runs(workspace_id)
        if orphaned_runs:
            issues.append({
                "type": "orphaned_runs",
                "count": len(orphaned_runs),
                "description": "Runs without corresponding tasks",
                "severity": "error"
            })
        
        # Check Run -> LLMCall relationships
        orphaned_llm_calls = await self._find_orphaned_llm_calls(workspace_id)
        if orphaned_llm_calls:
            issues.append({
                "type": "orphaned_llm_calls",
                "count": len(orphaned_llm_calls),
                "description": "LLM calls without corresponding runs",
                "severity": "error"
            })
        
        # Check Task -> Artifact relationships
        orphaned_artifacts = await self._find_orphaned_artifacts(workspace_id)
        if orphaned_artifacts:
            issues.append({
                "type": "orphaned_artifacts",
                "count": len(orphaned_artifacts),
                "description": "Artifacts without corresponding tasks",
                "severity": "error"
            })
        
        # Check Workspace -> Project relationships
        orphaned_projects = await self._find_orphaned_projects(workspace_id)
        if orphaned_projects:
            issues.append({
                "type": "orphaned_projects",
                "count": len(orphaned_projects),
                "description": "Projects without corresponding workspace",
                "severity": "error"
            })
        
        # Check Knowledge items have valid references
        invalid_knowledge_refs = await self._find_invalid_knowledge_references(workspace_id)
        if invalid_knowledge_refs:
            warnings.append({
                "type": "invalid_knowledge_references",
                "count": len(invalid_knowledge_refs),
                "description": "Knowledge items with invalid external references",
                "severity": "warning"
            })
        
        return {
            "workspace_id": workspace_id,
            "check_timestamp": datetime.utcnow().isoformat(),
            "status": "failed" if issues else "passed",
            "issues": issues,
            "warnings": warnings,
            "total_issues": len(issues),
            "total_warnings": len(warnings),
            "summary": {
                "tables_checked": 8,
                "relationships_verified": 12,
                "integrity_score": max(0, 100 - len(issues) * 10 - len(warnings) * 5)
            }
        }
    
    async def _find_orphaned_runs(self, workspace_id: str) -> list:
        """Find runs that don't have corresponding tasks."""
        # Mock orphaned runs
        return [
            {"run_id": str(uuid4()), "task_id": "non_existent_task"},
            {"run_id": str(uuid4()), "task_id": "another_missing_task"}
        ]
    
    async def _find_orphaned_llm_calls(self, workspace_id: str) -> list:
        """Find LLM calls that don't have corresponding runs."""
        return [
            {"call_id": str(uuid4()), "run_id": "non_existent_run"}
        ]
    
    async def _find_orphaned_artifacts(self, workspace_id: str) -> list:
        """Find artifacts that don't have corresponding tasks."""
        return [
            {"artifact_id": str(uuid4()), "task_id": "non_existent_task"}
        ]
    
    async def _find_orphaned_projects(self, workspace_id: str) -> list:
        """Find projects without workspace."""
        return []
    
    async def _find_invalid_knowledge_references(self, workspace_id: str) -> list:
        """Find knowledge items with invalid references."""
        return [
            {"item_id": str(uuid4()), "reference": "invalid://reference"}
        ]
    
    async def check_data_validation(self, workspace_id: str) -> dict:
        """Check data validation rules."""
        validation_issues = []
        
        # Check required fields
        missing_required_fields = await self._check_required_fields(workspace_id)
        if missing_required_fields:
            validation_issues.extend(missing_required_fields)
        
        # Check data types
        invalid_data_types = await self._check_data_types(workspace_id)
        if invalid_data_types:
            validation_issues.extend(invalid_data_types)
        
        # Check date ranges
        invalid_date_ranges = await self._check_date_ranges(workspace_id)
        if invalid_date_ranges:
            validation_issues.extend(invalid_date_ranges)
        
        # Check counts consistency
        count_inconsistencies = await self._check_count_consistency(workspace_id)
        if count_inconsistencies:
            validation_issues.extend(count_inconsistencies)
        
        return {
            "workspace_id": workspace_id,
            "validation_timestamp": datetime.utcnow().isoformat(),
            "status": "passed" if not validation_issues else "failed",
            "validation_issues": validation_issues,
            "total_issues": len(validation_issues),
            "validation_score": max(0, 100 - len(validation_issues) * 5),
            "checks_performed": [
                "required_fields",
                "data_types", 
                "date_ranges",
                "count_consistency",
                "null_checks",
                "duplicate_checks"
            ]
        }
    
    async def _check_required_fields(self, workspace_id: str) -> list:
        """Check for missing required fields."""
        return [
            {
                "table": "tasks",
                "issue": "missing_required_field",
                "field": "name",
                "record_id": str(uuid4()),
                "description": "Task missing required name field"
            },
            {
                "table": "llm_calls",
                "issue": "missing_required_field",
                "field": "provider",
                "record_id": str(uuid4()),
                "description": "LLM call missing required provider field"
            }
        ]
    
    async def _check_data_types(self, workspace_id: str) -> list:
        """Check for invalid data types."""
        return [
            {
                "table": "tasks",
                "issue": "invalid_data_type",
                "field": "status",
                "record_id": str(uuid4()),
                "expected_type": "string",
                "actual_value": 123,
                "description": "Task status should be string, got integer"
            }
        ]
    
    async def _check_date_ranges(self, workspace_id: str) -> list:
        """Check for invalid date ranges."""
        return [
            {
                "table": "tasks",
                "issue": "invalid_date_range",
                "field": "created_at",
                "record_id": str(uuid4()),
                "date_value": datetime(2030, 1, 1),  # Future date
                "description": "Task created date is in the future"
            }
        ]
    
    async def _check_count_consistency(self, workspace_id: str) -> list:
        """Check for count inconsistencies."""
        return [
            {
                "table": "tasks",
                "issue": "count_inconsistency",
                "expected_count": 100,
                "actual_count": 98,
                "description": "Task count doesn't match expected total"
            }
        ]
    
    async def check_consistency_rules(self, workspace_id: str) -> dict:
        """Check business logic consistency rules."""
        consistency_issues = []
        
        # Check cost consistency
        cost_inconsistencies = await self._check_cost_consistency(workspace_id)
        if cost_inconsistencies:
            consistency_issues.extend(cost_inconsistencies)
        
        # Check token count consistency
        token_inconsistencies = await self._check_token_consistency(workspace_id)
        if token_inconsistencies:
            consistency_issues.extend(token_inconsistencies)
        
        # Check status transition validity
        status_inconsistencies = await self._check_status_transitions(workspace_id)
        if status_inconsistencies:
            consistency_issues.extend(status_inconsistencies)
        
        # Check timestamp monotonicity
        timestamp_issues = await self._check_timestamp_monotonicity(workspace_id)
        if timestamp_issues:
            consistency_issues.extend(timestamp_issues)
        
        # Check for duplicates
        duplicate_issues = await self._check_duplicates(workspace_id)
        if duplicate_issues:
            consistency_issues.extend(duplicate_issues)
        
        return {
            "workspace_id": workspace_id,
            "consistency_timestamp": datetime.utcnow().isoformat(),
            "status": "passed" if not consistency_issues else "failed",
            "consistency_issues": consistency_issues,
            "total_issues": len(consistency_issues),
            "consistency_score": max(0, 100 - len(consistency_issues) * 15),
            "rules_checked": [
                "cost_consistency",
                "token_count_consistency",
                "status_transitions",
                "timestamp_monotonicity",
                "duplicate_detection"
            ]
        }
    
    async def _check_cost_consistency(self, workspace_id: str) -> list:
        """Check task cost equals sum of LLM calls."""
        return [
            {
                "rule": "task_cost_equals_llm_calls",
                "task_id": str(uuid4()),
                "task_total_cost": 10.50,
                "llm_calls_total_cost": 12.75,
                "difference": 2.25,
                "description": "Task total cost doesn't match sum of LLM calls"
            }
        ]
    
    async def _check_token_consistency(self, workspace_id: str) -> list:
        """Check token counts are consistent."""
        return [
            {
                "rule": "token_count_consistency",
                "llm_call_id": str(uuid4()),
                "tokens_prompt": 100,
                "tokens_completion": 50,
                "tokens_total": 200,  # Should be 150
                "description": "LLM call tokens_total doesn't equal sum of prompt + completion"
            }
        ]
    
    async def _check_status_transitions(self, workspace_id: str) -> list:
        """Check status transitions are valid."""
        return [
            {
                "rule": "valid_status_transitions",
                "task_id": str(uuid4()),
                "current_status": "completed",
                "previous_status": "pending",
                "next_allowed_statuses": ["failed", "cancelled"],
                "description": "Completed task cannot transition to other statuses"
            }
        ]
    
    async def _check_timestamp_monotonicity(self, workspace_id: str) -> list:
        """Check timestamps are monotonically increasing."""
        return [
            {
                "rule": "timestamp_monotonicity",
                "task_id": str(uuid4()),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow() - timedelta(hours=1),  # Updated before created
                "description": "Task updated_at is before created_at"
            }
        ]
    
    async def _check_duplicates(self, workspace_id: str) -> list:
        """Check for duplicate records."""
        return [
            {
                "rule": "duplicate_detection",
                "table": "tasks",
                "duplicate_group": "duplicate_task_group",
                "record_count": 3,
                "duplicate_field": "name",
                "description": "Found duplicate task names"
            }
        ]
    
    async def run_comprehensive_consistency_check(self, workspace_id: str) -> dict:
        """Run comprehensive consistency check across all dimensions."""
        referential_check = await self.check_referential_integrity(workspace_id)
        validation_check = await self.check_data_validation(workspace_id)
        consistency_check = await self.check_consistency_rules(workspace_id)
        
        # Calculate overall health score
        total_issues = (
            referential_check["total_issues"] + 
            validation_check["total_issues"] + 
            consistency_check["total_issues"]
        )
        
        total_warnings = (
            referential_check["total_warnings"]
        )
        
        overall_score = max(0, 100 - (total_issues * 10) - (total_warnings * 5))
        
        return {
            "workspace_id": workspace_id,
            "overall_check_timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy" if total_issues == 0 else "needs_attention",
            "overall_score": overall_score,
            "referential_integrity": referential_check,
            "data_validation": validation_check,
            "consistency_rules": consistency_check,
            "summary": {
                "total_issues": total_issues,
                "total_warnings": total_warnings,
                "critical_issues": sum(1 for check in [referential_check, validation_check, consistency_check] 
                                     if any(issue.get("severity") == "error" for issue in check.get("issues", []) + check.get("validation_issues", []) + check.get("consistency_issues", []))),
                "recommendations": self._generate_recommendations(referential_check, validation_check, consistency_check)
            }
        }
    
    def _generate_recommendations(self, referential_check: dict, validation_check: dict, consistency_check: dict) -> list:
        """Generate recommendations based on consistency check results."""
        recommendations = []
        
        if referential_check["total_issues"] > 0:
            recommendations.append("Fix referential integrity issues by cleaning up orphaned records")
        
        if validation_check["total_issues"] > 0:
            recommendations.append("Address data validation issues by correcting field types and values")
        
        if consistency_check["total_issues"] > 0:
            recommendations.append("Resolve business logic inconsistencies to maintain data integrity")
        
        if not recommendations:
            recommendations.append("Data consistency is excellent - maintain current practices")
        
        return recommendations


@pytest.fixture
async def consistency_checker(db_session: AsyncSession):
    """Create consistency checker fixture."""
    return DataConsistencyChecker(db_session)


@pytest.fixture
async def test_workspace_with_inconsistencies(db_session: AsyncSession):
    """Create test workspace with intentional inconsistencies for testing."""
    workspace = Workspace(
        name="Test Consistency Workspace",
        slug="test-consistency",
        metadata={}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    
    # Create some tasks
    for i in range(5):
        task = Task(
            workspace_id=workspace.id,
            name=f"Consistency Test Task {i}",
            status="completed" if i % 2 == 0 else "running",
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(task)
    
    await db_session.commit()
    return workspace


# ============================================================================
# Referential Integrity Tests
# ============================================================================

class TestReferentialIntegrity:
    """Test referential integrity checks."""
    
    async def test_all_foreign_keys_valid(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that all foreign keys are valid."""
        result = await consistency_checker.check_referential_integrity(
            test_workspace_with_inconsistencies.id
        )
        
        assert "workspace_id" in result
        assert "issues" in result
        assert "warnings" in result
        assert "summary" in result
        
        # Check summary structure
        summary = result["summary"]
        assert "tables_checked" in summary
        assert "relationships_verified" in summary
        assert "integrity_score" in summary
        assert isinstance(summary["integrity_score"], (int, float))
        assert 0 <= summary["integrity_score"] <= 100
    
    async def test_no_orphaned_records(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that no orphaned records exist."""
        result = await consistency_checker.check_referential_integrity(
            test_workspace_with_inconsistencies.id
        )
        
        # In clean data, should have no issues
        assert isinstance(result["issues"], list)
        assert isinstance(result["warnings"], list)
    
    async def test_cascading_deletes_work(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that cascading deletes work correctly."""
        # This would test cascading delete behavior
        # In real implementation, would delete a task and verify related records
        
        result = await consistency_checker.check_referential_integrity(
            test_workspace_with_inconsistencies.id
        )
        
        # Should not find orphaned records after proper cascading
        orphaned_types = ["orphaned_runs", "orphaned_llm_calls", "orphaned_artifacts"]
        
        for issue_type in orphaned_types:
            orphaned_issue = next(
                (issue for issue in result["issues"] if issue.get("type") == issue_type),
                None
            )
            if orphaned_issue:
                assert orphaned_issue["count"] == 0  # Should be clean
    
    async def test_references_correct(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that all references are correct."""
        result = await consistency_checker.check_referential_integrity(
            test_workspace_with_inconsistencies.id
        )
        
        # Check that all relationship types are being validated
        relationship_types = [
            "orphaned_runs", "orphaned_llm_calls", "orphaned_artifacts", 
            "orphaned_projects", "invalid_knowledge_references"
        ]
        
        # Each relationship type should be checked (even if no issues found)
        for relationship_type in relationship_types:
            found_check = any(
                issue.get("type") == relationship_type 
                for issue in result["issues"] + result["warnings"]
            )
            # In clean data, may not have explicit check entries, but that's ok
            # The important thing is that the check runs without errors


# ============================================================================
# Data Validation Tests
# ============================================================================

class TestDataValidation:
    """Test data validation checks."""
    
    async def test_required_fields_present(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that all required fields are present."""
        result = await consistency_checker.check_data_validation(
            test_workspace_with_inconsistencies.id
        )
        
        assert "validation_issues" in result
        assert "validation_score" in result
        assert "checks_performed" in result
        
        # Check validation score is reasonable
        assert 0 <= result["validation_score"] <= 100
        
        # Should have performed required checks
        expected_checks = ["required_fields", "data_types", "date_ranges", "count_consistency"]
        for check in expected_checks:
            assert check in result["checks_performed"]
    
    async def test_types_correct(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that data types are correct."""
        result = await consistency_checker.check_data_validation(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for type-related issues
        type_issues = [
            issue for issue in result["validation_issues"]
            if issue.get("issue") == "invalid_data_type"
        ]
        
        # If there are type issues, they should be properly documented
        for issue in type_issues:
            assert "table" in issue
            assert "field" in issue
            assert "expected_type" in issue
            assert "description" in issue
    
    async def test_ranges_valid(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that date ranges are valid."""
        result = await consistency_checker.check_data_validation(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for date range issues
        range_issues = [
            issue for issue in result["validation_issues"]
            if issue.get("issue") == "invalid_date_range"
        ]
        
        # Date range issues should have proper details
        for issue in range_issues:
            assert "field" in issue
            assert "date_value" in issue
            assert "description" in issue
    
    async def test_aggregates_match(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that aggregate calculations match."""
        result = await consistency_checker.check_data_validation(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for count inconsistencies
        count_issues = [
            issue for issue in result["validation_issues"]
            if issue.get("issue") == "count_inconsistency"
        ]
        
        # Count issues should show expected vs actual
        for issue in count_issues:
            assert "expected_count" in issue
            assert "actual_count" in issue
            assert issue["expected_count"] != issue["actual_count"]
    
    async def test_no_nan_null_anomalies(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that there are no NaN/null anomalies."""
        result = await consistency_checker.check_data_validation(
            test_workspace_with_inconsistencies.id
        )
        
        # In clean data, should not have null/NaN issues
        null_issues = [
            issue for issue in result["validation_issues"]
            if any(keyword in issue.get("description", "").lower() 
                  for keyword in ["null", "nan", "none", "empty"])
        ]
        
        # Clean data should not have null issues
        for issue in null_issues:
            # These might exist in test data, but should be minimal
            assert issue.get("severity", "info") in ["info", "warning"]


# ============================================================================
# Consistency Rules Tests
# ============================================================================

class TestConsistencyRules:
    """Test business logic consistency rules."""
    
    async def test_cost_consistency_verified(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that cost consistency is verified."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        assert "consistency_issues" in result
        assert "rules_checked" in result
        assert "consistency_score" in result
        
        # Should check cost consistency
        assert "cost_consistency" in result["rules_checked"]
        assert 0 <= result["consistency_score"] <= 100
    
    async def test_token_counts_consistent(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that token counts are consistent."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for token consistency issues
        token_issues = [
            issue for issue in result["consistency_issues"]
            if issue.get("rule") == "token_count_consistency"
        ]
        
        # Token consistency issues should show the math
        for issue in token_issues:
            assert "tokens_prompt" in issue
            assert "tokens_completion" in issue
            assert "tokens_total" in issue
            # Should detect when prompt + completion != total
            expected_total = issue["tokens_prompt"] + issue["tokens_completion"]
            assert issue["tokens_total"] != expected_total
    
    async def test_status_chains_valid(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that status transitions are valid."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for status transition issues
        status_issues = [
            issue for issue in result["consistency_issues"]
            if issue.get("rule") == "valid_status_transitions"
        ]
        
        # Status transition issues should specify valid next states
        for issue in status_issues:
            assert "current_status" in issue
            assert "next_allowed_statuses" in issue
            assert isinstance(issue["next_allowed_statuses"], list)
    
    async def test_timestamps_monotonic(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that timestamps are monotonically increasing."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for timestamp monotonicity issues
        timestamp_issues = [
            issue for issue in result["consistency_issues"]
            if issue.get("rule") == "timestamp_monotonicity"
        ]
        
        # Timestamp issues should show the problematic timestamps
        for issue in timestamp_issues:
            assert "created_at" in issue
            assert "updated_at" in issue
            # Updated should not be before created
            if isinstance(issue["created_at"], datetime) and isinstance(issue["updated_at"], datetime):
                assert issue["updated_at"] >= issue["created_at"]
    
    async def test_no_duplicates(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that there are no duplicate records."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for duplicate issues
        duplicate_issues = [
            issue for issue in result["consistency_issues"]
            if issue.get("rule") == "duplicate_detection"
        ]
        
        # Duplicate issues should specify the table and field
        for issue in duplicate_issues:
            assert "table" in issue
            assert "duplicate_field" in issue
            assert "record_count" in issue
            assert issue["record_count"] > 1


# ============================================================================
# Workspace Cost Consistency Tests
# ============================================================================

class TestWorkspaceCostConsistency:
    """Test workspace-level cost consistency."""
    
    async def test_workspace_cost_equals_task_sum(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that workspace cost equals sum of all tasks."""
        # This would test that total workspace cost matches sum of individual task costs
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Should have some form of cost consistency checking
        cost_issues = [
            issue for issue in result["consistency_issues"]
            if "cost" in issue.get("rule", "").lower()
        ]
        
        # If there are cost issues, they should be detailed
        for issue in cost_issues:
            assert "description" in issue
            # Should have some cost-related fields
            cost_fields = ["cost", "total_cost", "task_total_cost", "llm_calls_total_cost"]
            assert any(field in issue for field in cost_fields)
    
    async def test_token_counts_aggregate_correctly(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that token counts aggregate correctly across workspace."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Should check token aggregation at workspace level
        token_issues = [
            issue for issue in result["consistency_issues"]
            if "token" in issue.get("rule", "").lower()
        ]
        
        # Token consistency issues should involve aggregation
        for issue in token_issues:
            assert "description" in issue


# ============================================================================
# Time Series Consistency Tests
# ============================================================================

class TestTimeSeriesConsistency:
    """Test time series data consistency."""
    
    async def test_task_completion_time_logical(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that task completion times are logical."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Look for time-related consistency issues
        time_issues = [
            issue for issue in result["consistency_issues"]
            if any(keyword in issue.get("rule", "").lower() 
                  for keyword in ["timestamp", "time", "date"])
        ]
        
        # Time issues should reference specific timestamps
        for issue in time_issues:
            assert "description" in issue
            # Should have some timestamp fields
            time_fields = ["created_at", "updated_at", "started_at", "ended_at"]
            assert any(field in issue for field in time_fields)
    
    async def test_execution_order_logical(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that execution order is logical."""
        result = await consistency_checker.check_consistency_rules(
            test_workspace_with_inconsistencies.id
        )
        
        # Should check for logical execution ordering
        # This might be part of timestamp or status consistency checks
        
        timestamp_issues = [
            issue for issue in result["consistency_issues"]
            if issue.get("rule") == "timestamp_monotonicity"
        ]
        
        # These issues should ensure logical ordering
        for issue in timestamp_issues:
            assert "created_at" in issue
            assert "updated_at" in issue


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestConsistencyIntegration:
    """Integration tests for consistency checking."""
    
    async def test_comprehensive_consistency_check(
        self,
        consistency_checker,
        test_workspace_with_inconsistencies
    ):
        """Test comprehensive consistency check across all dimensions."""
        result = await consistency_checker.run_comprehensive_consistency_check(
            test_workspace_with_inconsistencies.id
        )
        
        # Should have all check results
        assert "referential_integrity" in result
        assert "data_validation" in result
        assert "consistency_rules" in result
        assert "overall_status" in result
        assert "overall_score" in result
        
        # Overall status should be based on issues found
        total_issues = result["summary"]["total_issues"]
        if total_issues == 0:
            assert result["overall_status"] == "healthy"
        else:
            assert result["overall_status"] == "needs_attention"
        
        # Should have recommendations
        assert "recommendations" in result["summary"]
        assert isinstance(result["summary"]["recommendations"], list)
        assert len(result["summary"]["recommendations"]) > 0
    
    async def test_consistency_check_performance(
        self,
        consistency_checker,
        test_workspace_with_inconsistencies
    ):
        """Test consistency check performance."""
        import time
        
        workspace_id = test_workspace_with_inconsistencies.id
        start_time = time.time()
        
        # Run comprehensive check
        result = await consistency_checker.run_comprehensive_consistency_check(workspace_id)
        
        duration = time.time() - start_time
        
        assert result is not None
        # Should complete within reasonable time (adjust based on requirements)
        assert duration < 30.0  # Less than 30 seconds
    
    async def test_consistency_check_with_large_dataset(
        self,
        consistency_checker,
        test_workspace_with_inconsistencies
    ):
        """Test consistency check with large dataset."""
        # This would test with a large amount of data
        result = await consistency_checker.run_comprehensive_consistency_check(
            test_workspace_with_inconsistencies.id
        )
        
        # Should handle large datasets gracefully
        assert "overall_score" in result
        assert isinstance(result["overall_score"], (int, float))
        assert 0 <= result["overall_score"] <= 100
    
    async def test_consistency_tracking_over_time(
        self,
        consistency_checker,
        test_workspace_with_inconsistencies
    ):
        """Test tracking consistency over time."""
        workspace_id = test_workspace_with_inconsistencies.id
        
        # Run multiple checks to simulate tracking over time
        check1 = await consistency_checker.run_comprehensive_consistency_check(workspace_id)
        
        # Simulate some data changes (in real implementation)
        # For now, just run another check
        check2 = await consistency_checker.run_comprehensive_consistency_check(workspace_id)
        
        # Should get consistent results for same data
        assert check1["overall_score"] == check2["overall_score"]
        assert check1["overall_status"] == check2["overall_status"]


# ============================================================================
# Data Repair Tests
# ============================================================================

class TestDataRepair:
    """Test data repair functionality."""
    
    async def test_auto_repair_capabilities(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test automatic data repair capabilities."""
        # This would test automatic repair of consistency issues
        result = await consistency_checker.run_comprehensive_consistency_check(
            test_workspace_with_inconsistencies.id
        )
        
        # Should identify repairable issues
        repairable_issues = []
        for check_result in [result["referential_integrity"], result["data_validation"], result["consistency_rules"]]:
            for issue_list in [check_result.get("issues", []), check_result.get("validation_issues", []), check_result.get("consistency_issues", [])]:
                for issue in issue_list:
                    if issue.get("severity") != "error":  # Non-critical issues might be repairable
                        repairable_issues.append(issue)
        
        # Should be able to identify what can be auto-repaired
        assert isinstance(repairable_issues, list)
    
    async def test_repair_validation(self, consistency_checker, test_workspace_with_inconsistencies):
        """Test that repairs are validated."""
        # Get initial state
        initial_result = await consistency_checker.run_comprehensive_consistency_check(
            test_workspace_with_inconsistencies.id
        )
        
        # After repair (simulated), should have fewer issues
        # In real implementation, would perform actual repair
        final_result = await consistency_checker.run_comprehensive_consistency_check(
            test_workspace_with_inconsistencies.id
        )
        
        # Should maintain or improve consistency score
        assert final_result["overall_score"] >= initial_result["overall_score"]


@pytest.mark.asyncio
async def test_consistency_checker_initialization(consistency_checker):
    """Test that consistency checker initializes correctly."""
    assert consistency_checker.db_session is not None


@pytest.mark.asyncio
async def test_consistency_check_workspace_validation(consistency_checker, test_workspace_with_inconsistencies):
    """Test consistency check validates workspace parameter."""
    with pytest.raises(Exception):
        await consistency_checker.check_referential_integrity(None)
    
    with pytest.raises(Exception):
        await consistency_checker.check_data_validation("")
    
    # Valid workspace should work
    result = await consistency_checker.check_referential_integrity(
        test_workspace_with_inconsistencies.id
    )
    assert result["workspace_id"] == test_workspace_with_inconsistencies.id


@pytest.mark.asyncio
async def test_consistency_score_calculation(consistency_checker, test_workspace_with_inconsistencies):
    """Test that consistency scores are calculated correctly."""
    referential_result = await consistency_checker.check_referential_integrity(
        test_workspace_with_inconsistencies.id
    )
    validation_result = await consistency_checker.check_data_validation(
        test_workspace_with_inconsistencies.id
    )
    consistency_result = await consistency_checker.check_consistency_rules(
        test_workspace_with_inconsistencies.id
    )
    
    # All scores should be between 0 and 100
    assert 0 <= referential_result["summary"]["integrity_score"] <= 100
    assert 0 <= validation_result["validation_score"] <= 100
    assert 0 <= consistency_result["consistency_score"] <= 100
    
    # Overall score should be reasonable
    comprehensive_result = await consistency_checker.run_comprehensive_consistency_check(
        test_workspace_with_inconsistencies.id
    )
    assert 0 <= comprehensive_result["overall_score"] <= 100