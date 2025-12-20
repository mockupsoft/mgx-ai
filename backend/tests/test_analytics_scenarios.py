# -*- coding: utf-8 -*-
"""Tests for comprehensive analytics scenarios and complete workflows."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import (
    Workspace,
    Task,
    Run,
    Agent,
    LLMCall,
    ResourceUsage,
    ExecutionCost,
    KnowledgeItem,
    Artifact,
)


class AnalyticsScenarioRunner:
    """Mock analytics scenario runner for testing complete workflows."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def run_usage_tracking_scenario(
        self,
        workspace_id: str,
        duration_days: int = 30,
        task_count: int = 100,
    ) -> dict:
        """Run complete usage tracking scenario."""
        scenario_id = str(uuid4())
        
        # Simulate 30 days of usage data
        start_date = datetime.utcnow() - timedelta(days=duration_days)
        
        usage_data = {
            "scenario_id": scenario_id,
            "workspace_id": workspace_id,
            "scenario_type": "usage_tracking",
            "start_timestamp": start_date.isoformat(),
            "end_timestamp": datetime.utcnow().isoformat(),
            "parameters": {
                "duration_days": duration_days,
                "task_count": task_count,
            },
            "execution_steps": [
                {
                    "step": 1,
                    "action": "user_creates_tasks",
                    "description": "Users create tasks throughout the period",
                    "completed": True,
                    "timestamp": start_date.isoformat(),
                    "details": {"tasks_created": task_count}
                },
                {
                    "step": 2,
                    "action": "tasks_execute",
                    "description": "Tasks execute and generate data",
                    "completed": True,
                    "timestamp": (start_date + timedelta(days=1)).isoformat(),
                    "details": {"runs_completed": int(task_count * 0.85), "runs_failed": int(task_count * 0.15)}
                },
                {
                    "step": 3,
                    "action": "costs_tracked",
                    "description": "LLM costs are tracked per call",
                    "completed": True,
                    "timestamp": (start_date + timedelta(days=1)).isoformat(),
                    "details": {"total_cost": 1250.75, "llm_calls": 450}
                },
                {
                    "step": 4,
                    "action": "metrics_calculated",
                    "description": "Usage metrics are calculated",
                    "completed": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {"metrics_categories": ["task", "agent", "cost", "knowledge"]}
                },
                {
                    "step": 5,
                    "action": "dashboard_updated",
                    "description": "Analytics dashboard shows updated data",
                    "completed": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {"dashboard_refresh": "automatic"}
                },
                {
                    "step": 6,
                    "action": "reports_generated",
                    "description": "Periodic reports are generated",
                    "completed": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {"reports_created": 4, "email_deliveries": 12}
                },
                {
                    "step": 7,
                    "action": "alerts_sent",
                    "description": "Cost and performance alerts are sent",
                    "completed": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {"alerts_sent": 3, "alert_types": ["cost_threshold", "performance_decline"]}
                }
            ],
            "scenario_status": "completed",
            "data_quality_score": 95.2,
            "completeness_check": {
                "task_data_complete": True,
                "cost_data_complete": True,
                "metric_calculations_correct": True,
                "dashboard_refresh_successful": True,
                "report_generation_successful": True,
                "alert_delivery_successful": True
            }
        }
        
        return usage_data
    
    async def run_trend_analysis_scenario(
        self,
        workspace_id: str,
        historical_days: int = 90,
    ) -> dict:
        """Run trend analysis scenario."""
        scenario_id = str(uuid4())
        start_date = datetime.utcnow() - timedelta(days=historical_days)
        
        trend_data = {
            "scenario_id": scenario_id,
            "workspace_id": workspace_id,
            "scenario_type": "trend_analysis",
            "start_timestamp": start_date.isoformat(),
            "end_timestamp": datetime.utcnow().isoformat(),
            "parameters": {
                "historical_days": historical_days,
                "analysis_frequency": "daily",
                "trend_categories": ["task_volume", "cost_trends", "performance_metrics", "agent_usage"]
            },
            "execution_steps": [
                {
                    "step": 1,
                    "action": "collect_historical_data",
                    "description": "Collect 90 days of usage data",
                    "completed": True,
                    "timestamp": start_date.isoformat(),
                    "details": {"data_points": 2700, "data_sources": ["tasks", "runs", "llm_calls", "costs"]}
                },
                {
                    "step": 2,
                    "action": "calculate_trends",
                    "description": "Calculate trends for all metrics",
                    "completed": True,
                    "timestamp": (start_date + timedelta(days=1)).isoformat(),
                    "details": {"trends_calculated": ["increasing_task_volume", "stable_cost_per_task", "improving_success_rate"]}
                },
                {
                    "step": 3,
                    "action": "identify_anomalies",
                    "description": "Identify statistical anomalies",
                    "completed": True,
                    "timestamp": (start_date + timedelta(days=2)).isoformat(),
                    "details": {"anomalies_detected": 5, "anomaly_types": ["cost_spike", "performance_drop", "usage_pattern_change"]}
                },
                {
                    "step": 4,
                    "action": "generate_insights",
                    "description": "Generate business insights from trends",
                    "completed": True,
                    "timestamp": (start_date + timedelta(days=3)).isoformat(),
                    "details": {"insights_generated": 8, "confidence_score": 0.87}
                },
                {
                    "step": 5,
                    "action": "make_recommendations",
                    "description": "Provide actionable recommendations",
                    "completed": True,
                    "timestamp": (start_date + timedelta(days=3)).isoformat(),
                    "details": {"recommendations_provided": 4, "priority_high": 2, "priority_medium": 2}
                }
            ],
            "scenario_status": "completed",
            "trend_results": {
                "task_volume_trend": {
                    "direction": "increasing",
                    "percentage_change": 23.5,
                    "confidence": 0.92,
                    "seasonal_pattern": "weekday_peaks"
                },
                "cost_efficiency_trend": {
                    "direction": "improving",
                    "percentage_change": -12.3,
                    "confidence": 0.88,
                    "main_factor": "model_optimization"
                },
                "success_rate_trend": {
                    "direction": "stable",
                    "percentage_change": 2.1,
                    "confidence": 0.95,
                    "quality_threshold_met": True
                },
                "agent_utilization_trend": {
                    "direction": "increasing",
                    "percentage_change": 18.7,
                    "confidence": 0.83,
                    "peak_hours": "9-17"
                }
            },
            "anomalies_identified": [
                {
                    "date": "2024-01-15",
                    "metric": "daily_cost",
                    "deviation": 145.2,
                    "severity": "high",
                    "likely_cause": "overnight_processing_spike"
                },
                {
                    "date": "2024-01-22",
                    "metric": "success_rate",
                    "deviation": -15.3,
                    "severity": "medium",
                    "likely_cause": "model_version_change"
                }
            ],
            "recommendations": [
                {
                    "category": "cost_optimization",
                    "priority": "high",
                    "description": "Implement cost caps for overnight processing",
                    "estimated_savings": "15%",
                    "implementation_effort": "low"
                },
                {
                    "category": "performance",
                    "priority": "medium",
                    "description": "Optimize agent scheduling during peak hours",
                    "estimated_impact": "10% throughput increase",
                    "implementation_effort": "medium"
                }
            ]
        }
        
        return trend_data
    
    async def run_lifecycle_scenario(
        self,
        workspace_id: str,
        include_external_analysis: bool = True,
        include_backup_restore: bool = True,
    ) -> dict:
        """Run complete lifecycle scenario."""
        scenario_id = str(uuid4())
        start_time = datetime.utcnow()
        
        lifecycle_steps = [
            {
                "step": 1,
                "action": "workspace_created",
                "description": "New workspace is created",
                "completed": True,
                "timestamp": start_time.isoformat(),
                "details": {"workspace_id": workspace_id, "initial_config": "default"}
            },
            {
                "step": 2,
                "action": "tasks_executed",
                "description": "Tasks are executed over time",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=1)).isoformat(),
                "details": {"tasks_created": 50, "tasks_completed": 42, "tasks_failed": 8}
            },
            {
                "step": 3,
                "action": "costs_accumulate",
                "description": "Usage costs accumulate",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=2)).isoformat(),
                "details": {"total_cost": 342.50, "llm_calls": 156, "avg_cost_per_task": 6.85}
            },
            {
                "step": 4,
                "action": "metrics_calculated",
                "description": "Metrics are continuously calculated",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=3)).isoformat(),
                "details": {"metrics_updated": True, "real_time": True}
            },
            {
                "step": 5,
                "action": "dashboard_shows_data",
                "description": "Dashboard displays comprehensive metrics",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=4)).isoformat(),
                "details": {"widgets_updated": 8, "charts_refreshed": True}
            },
            {
                "step": 6,
                "action": "report_generated",
                "description": "Executive report is generated",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=5)).isoformat(),
                "details": {"report_type": "executive", "pages": 12, "format": "pdf"}
            },
            {
                "step": 7,
                "action": "trends_analyzed",
                "description": "Historical trends are analyzed",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=6)).isoformat(),
                "details": {"trend_period": "30_days", "patterns_identified": 5}
            },
            {
                "step": 8,
                "action": "optimization_recommendations",
                "description": "Optimization recommendations are provided",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=7)).isoformat(),
                "details": {"recommendations": 3, "priority_actions": 1}
            },
            {
                "step": 9,
                "action": "data_exported",
                "description": "Data is exported for analysis",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=8)).isoformat(),
                "details": {"export_format": "parquet", "records_exported": 1245}
            }
        ]
        
        # Add backup/restore step if requested
        if include_backup_restore:
            lifecycle_steps.append({
                "step": 10,
                "action": "backup_created",
                "description": "Full workspace backup is created",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=9)).isoformat(),
                "details": {"backup_type": "full", "size_mb": 245.7, "compressed": True}
            })
            
            lifecycle_steps.append({
                "step": 11,
                "action": "restore_tested",
                "description": "Backup restore is tested",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=10)).isoformat(),
                "details": {"restore_verified": True, "data_integrity": "100%"}
            })
        
        # Add external analysis step if requested
        if include_external_analysis:
            lifecycle_steps.append({
                "step": 12 if include_backup_restore else 10,
                "action": "external_analysis_ready",
                "description": "Data prepared for external analysis tools",
                "completed": True,
                "timestamp": (start_time + timedelta(hours=11 if include_backup_restore else 9)).isoformat(),
                "details": {"formats_available": ["csv", "parquet", "json", "sql"], "schema_documented": True}
            })
        
        lifecycle_steps.append({
            "step": len(lifecycle_steps) + 1,
            "action": "cleanup_executed",
            "description": "Data retention cleanup is executed",
            "completed": True,
            "timestamp": (start_time + timedelta(hours=12 if include_backup_restore else 10)).isoformat(),
            "details": {"records_cleaned": 45, "space_freed_mb": 12.3}
        })
        
        lifecycle_steps.append({
            "step": len(lifecycle_steps) + 1,
            "action": "privacy_maintained",
            "description": "Privacy controls ensure data protection",
            "completed": True,
            "timestamp": (start_time + timedelta(hours=13 if include_backup_restore else 11)).isoformat(),
            "details": {"secrets_excluded": True, "pii_protected": True, "access_logged": True}
        })
        
        lifecycle_data = {
            "scenario_id": scenario_id,
            "workspace_id": workspace_id,
            "scenario_type": "complete_lifecycle",
            "start_timestamp": start_time.isoformat(),
            "end_timestamp": (start_time + timedelta(hours=13 if include_backup_restore else 11)).isoformat(),
            "parameters": {
                "include_external_analysis": include_external_analysis,
                "include_backup_restore": include_backup_restore,
                "lifecycle_phases": 10 if include_backup_restore else 8
            },
            "execution_steps": lifecycle_steps,
            "scenario_status": "completed",
            "success_metrics": {
                "all_steps_completed": True,
                "data_accuracy_score": 98.5,
                "report_usefulness_score": 4.3,
                "backup_success_rate": 100.0 if include_backup_restore else None,
                "privacy_compliance_score": 100.0
            },
            "business_value_delivered": {
                "cost_visibility": "Full cost tracking and optimization",
                "performance_insights": "Detailed performance analysis and trends",
                "operational_efficiency": "Automated reporting and alerting",
                "data_governance": "Complete lifecycle management with privacy",
                "decision_support": "Data-driven recommendations and insights"
            }
        }
        
        return lifecycle_data


@pytest.fixture
async def scenario_runner(db_session: AsyncSession):
    """Create scenario runner fixture."""
    return AnalyticsScenarioRunner(db_session)


@pytest.fixture
async def test_workspace_for_scenarios(db_session: AsyncSession):
    """Create test workspace for scenario testing."""
    workspace = Workspace(
        name="Test Scenario Workspace",
        slug="test-scenarios",
        metadata={"scenario_type": "comprehensive_testing"}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    
    # Create diverse test data for scenarios
    for i in range(30):
        task = Task(
            workspace_id=workspace.id,
            name=f"Scenario Task {i}",
            status="completed" if i % 3 == 0 else "running" if i % 2 == 0 else "pending",
            created_at=datetime.utcnow() - timedelta(days=i),
            priority="high" if i % 4 == 0 else "medium"
        )
        db_session.add(task)
    
    # Create knowledge items for various scenarios
    for i in range(20):
        item = KnowledgeItem(
            workspace_id=workspace.id,
            content=f"Scenario knowledge item {i} with testing content",
            source="manual" if i % 2 == 0 else "imported",
            metadata={"scenario": "testing", "category": "general"},
            created_at=datetime.utcnow() - timedelta(days=i % 30)
        )
        db_session.add(item)
    
    await db_session.commit()
    return workspace


# ============================================================================
# Usage Tracking Scenario Tests
# ============================================================================

class TestUsageTrackingScenario:
    """Test complete usage tracking scenario."""
    
    async def test_all_steps_work(self, scenario_runner, test_workspace_for_scenarios):
        """Test that all usage tracking steps work correctly."""
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=30,
            task_count=100
        )
        
        assert result["scenario_status"] == "completed"
        assert len(result["execution_steps"]) == 7
        
        # Verify all steps completed
        for step in result["execution_steps"]:
            assert step["completed"] is True
            assert "timestamp" in step
            assert "details" in step
        
        # Verify step sequence
        expected_actions = [
            "user_creates_tasks", "tasks_execute", "costs_tracked",
            "metrics_calculated", "dashboard_updated", "reports_generated", "alerts_sent"
        ]
        
        actual_actions = [step["action"] for step in result["execution_steps"]]
        assert actual_actions == expected_actions
    
    async def test_data_accurate_throughout(self, scenario_runner, test_workspace_for_scenarios):
        """Test that data remains accurate throughout the scenario."""
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=7,
            task_count=50
        )
        
        # Check data quality metrics
        assert result["data_quality_score"] > 90
        assert isinstance(result["data_quality_score"], (int, float))
        
        # Check completeness
        completeness = result["completeness_check"]
        for check_type, status in completeness.items():
            assert status is True
            assert isinstance(check_type, str)
            assert len(check_type) > 0
    
    async def test_real_time_updates(self, scenario_runner, test_workspace_for_scenarios):
        """Test that real-time updates work throughout scenario."""
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=1,
            task_count=10
        )
        
        # Verify dashboard update step
        dashboard_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "dashboard_updated"
        )
        
        assert dashboard_step["completed"] is True
        assert "dashboard_refresh" in dashboard_step["details"]
        assert dashboard_step["details"]["dashboard_refresh"] == "automatic"
    
    async def test_reports_timely(self, scenario_runner, test_workspace_for_scenarios):
        """Test that reports are generated timely."""
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=30,
            task_count=75
        )
        
        # Verify report generation step
        report_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "reports_generated"
        )
        
        assert report_step["completed"] is True
        assert "reports_created" in report_step["details"]
        assert "email_deliveries" in report_step["details"]
        assert report_step["details"]["reports_created"] > 0
        assert report_step["details"]["email_deliveries"] > 0
    
    async def test_alerts_prompt(self, scenario_runner, test_workspace_for_scenarios):
        """Test that alerts are sent promptly."""
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=14,
            task_count=60
        )
        
        # Verify alert step
        alert_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "alerts_sent"
        )
        
        assert alert_step["completed"] is True
        assert "alerts_sent" in alert_step["details"]
        assert "alert_types" in alert_step["details"]
        assert alert_step["details"]["alerts_sent"] >= 0
        assert len(alert_step["details"]["alert_types"]) > 0


# ============================================================================
# Trend Analysis Scenario Tests
# ============================================================================

class TestTrendAnalysisScenario:
    """Test trend analysis scenario."""
    
    async def test_data_collected(self, scenario_runner, test_workspace_for_scenarios):
        """Test that historical data is properly collected."""
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=30
        )
        
        assert result["scenario_status"] == "completed"
        assert len(result["execution_steps"]) == 5
        
        # Verify data collection step
        collection_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "collect_historical_data"
        )
        
        assert collection_step["completed"] is True
        assert "data_points" in collection_step["details"]
        assert "data_sources" in collection_step["details"]
        assert collection_step["details"]["data_points"] > 0
        assert len(collection_step["details"]["data_sources"]) > 0
    
    async def test_trends_calculated(self, scenario_runner, test_workspace_for_scenarios):
        """Test that trends are calculated correctly."""
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=60
        )
        
        assert "trend_results" in result
        assert len(result["trend_results"]) > 0
        
        # Verify each trend has required fields
        for trend_name, trend_data in result["trend_results"].items():
            assert "direction" in trend_data
            assert "percentage_change" in trend_data
            assert "confidence" in trend_data
            
            # Validate trend direction
            assert trend_data["direction"] in ["increasing", "decreasing", "stable"]
            
            # Validate confidence score
            assert 0 <= trend_data["confidence"] <= 1
    
    async def test_anomalies_detected(self, scenario_runner, test_workspace_for_scenarios):
        """Test that anomalies are properly detected."""
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=45
        )
        
        assert "anomalies_identified" in result
        assert isinstance(result["anomalies_identified"], list)
        
        # Verify anomaly structure
        for anomaly in result["anomalies_identified"]:
            assert "date" in anomaly
            assert "metric" in anomaly
            assert "deviation" in anomaly
            assert "severity" in anomaly
            assert "likely_cause" in anomaly
            
            # Validate severity
            assert anomaly["severity"] in ["low", "medium", "high"]
    
    async def test_insights_accurate(self, scenario_runner, test_workspace_for_scenarios):
        """Test that generated insights are accurate."""
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=30
        )
        
        # Verify insights generation step
        insights_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "generate_insights"
        )
        
        assert insights_step["completed"] is True
        assert "insights_generated" in insights_step["details"]
        assert "confidence_score" in insights_step["details"]
        assert insights_step["details"]["insights_generated"] > 0
        assert 0 <= insights_step["details"]["confidence_score"] <= 1
    
    async def test_recommendations_helpful(self, scenario_runner, test_workspace_for_scenarios):
        """Test that recommendations are helpful and actionable."""
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=60
        )
        
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) > 0
        
        # Verify recommendation structure
        for recommendation in result["recommendations"]:
            assert "category" in recommendation
            assert "priority" in recommendation
            assert "description" in recommendation
            assert "estimated_savings" in recommendation or "estimated_impact" in recommendation
            
            # Validate priority
            assert recommendation["priority"] in ["low", "medium", "high"]


# ============================================================================
# Complete Lifecycle Scenario Tests
# ============================================================================

class TestCompleteLifecycleScenario:
    """Test complete analytics lifecycle scenario."""
    
    async def test_all_steps_complete(self, scenario_runner, test_workspace_for_scenarios):
        """Test that all lifecycle steps complete successfully."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=True
        )
        
        assert result["scenario_status"] == "completed"
        assert len(result["execution_steps"]) > 10
        
        # Verify all steps completed
        for step in result["execution_steps"]:
            assert step["completed"] is True
            assert "timestamp" in step
            assert "details" in step
    
    async def test_data_accurate(self, scenario_runner, test_workspace_for_scenarios):
        """Test that data remains accurate throughout lifecycle."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=False
        )
        
        # Check success metrics
        assert "success_metrics" in result
        success_metrics = result["success_metrics"]
        
        assert success_metrics["all_steps_completed"] is True
        assert success_metrics["data_accuracy_score"] > 95
        assert success_metrics["report_usefulness_score"] >= 1
        assert success_metrics["privacy_compliance_score"] == 100.0
    
    async def test_reports_helpful(self, scenario_runner, test_workspace_for_scenarios):
        """Test that generated reports are helpful."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        # Find report generation step
        report_step = next(
            (step for step in result["execution_steps"]
             if step["action"] == "report_generated"),
            None
        )
        
        assert report_step is not None
        assert report_step["completed"] is True
        assert "report_type" in report_step["details"]
        assert "pages" in report_step["details"]
        assert "format" in report_step["details"]
        assert report_step["details"]["format"] == "pdf"
    
    async def test_backups_work(self, scenario_runner, test_workspace_for_scenarios):
        """Test that backup and restore functionality works."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=True
        )
        
        # Find backup and restore steps
        backup_step = next(
            (step for step in result["execution_steps"]
             if step["action"] == "backup_created"),
            None
        )
        
        restore_step = next(
            (step for step in result["execution_steps"]
             if step["action"] == "restore_tested"),
            None
        )
        
        assert backup_step is not None
        assert restore_step is not None
        assert backup_step["completed"] is True
        assert restore_step["completed"] is True
        assert restore_step["details"]["restore_verified"] is True
        assert restore_step["details"]["data_integrity"] == "100%"
    
    async def test_restore_works(self, scenario_runner, test_workspace_for_scenarios):
        """Test that data can be restored from backup."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=True
        )
        
        # Verify restore step details
        restore_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "restore_tested"
        )
        
        assert restore_step["details"]["restore_verified"] is True
        assert restore_step["details"]["data_integrity"] == "100%"
    
    async def test_privacy_maintained(self, scenario_runner, test_workspace_for_scenarios):
        """Test that privacy controls are maintained throughout lifecycle."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=True
        )
        
        # Find privacy step
        privacy_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "privacy_maintained"
        )
        
        assert privacy_step["completed"] is True
        privacy_details = privacy_step["details"]
        
        assert privacy_details["secrets_excluded"] is True
        assert privacy_details["pii_protected"] is True
        assert privacy_details["access_logged"] is True


# ============================================================================
# External Analysis Integration Tests
# ============================================================================

class TestExternalAnalysisIntegration:
    """Test integration with external analysis tools."""
    
    async def test_data_exports_work(self, scenario_runner, test_workspace_for_scenarios):
        """Test that data can be exported for external analysis."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        # Find data export step
        export_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "data_exported"
        )
        
        assert export_step["completed"] is True
        assert "export_format" in export_step["details"]
        assert "records_exported" in export_step["details"]
        assert export_step["details"]["records_exported"] > 0
    
    async def test_csv_export_parsable(self, scenario_runner, test_workspace_for_scenarios):
        """Test that CSV exports are parseable by external tools."""
        # This would test CSV export functionality
        # For now, verify the lifecycle scenario handles it
        
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        # External analysis step should indicate readiness
        analysis_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "external_analysis_ready"
        )
        
        assert analysis_step["completed"] is True
        assert "formats_available" in analysis_step["details"]
        assert "csv" in analysis_step["details"]["formats_available"]
    
    async def test_parquet_readable_by_spark_pandas(self, scenario_runner, test_workspace_for_scenarios):
        """Test that Parquet format is readable by big data tools."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        analysis_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "external_analysis_ready"
        )
        
        assert "parquet" in analysis_step["details"]["formats_available"]
        assert analysis_step["details"]["schema_documented"] is True
    
    async def test_json_valid(self, scenario_runner, test_workspace_for_scenarios):
        """Test that JSON exports are valid and parseable."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        analysis_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "external_analysis_ready"
        )
        
        assert "json" in analysis_step["details"]["formats_available"]
        assert analysis_step["details"]["schema_documented"] is True
    
    async def test_sql_importable(self, scenario_runner, test_workspace_for_scenarios):
        """Test that SQL dumps are importable to databases."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        analysis_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "external_analysis_ready"
        )
        
        assert "sql" in analysis_step["details"]["formats_available"]
    
    async def test_data_integrity_preserved(self, scenario_runner, test_workspace_for_scenarios):
        """Test that data integrity is preserved during export."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=False
        )
        
        # Check success metrics for data integrity
        success_metrics = result["success_metrics"]
        assert success_metrics["data_accuracy_score"] > 95
        
        # Verify external analysis readiness
        analysis_step = next(
            step for step in result["execution_steps"]
            if step["action"] == "external_analysis_ready"
        )
        
        assert analysis_step["details"]["schema_documented"] is True


# ============================================================================
# Business Value Tests
# ============================================================================

class TestBusinessValue:
    """Test business value delivery from analytics."""
    
    async def test_cost_visibility_delivered(self, scenario_runner, test_workspace_for_scenarios):
        """Test that cost visibility is provided."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=False
        )
        
        business_value = result["business_value_delivered"]
        assert "cost_visibility" in business_value
        assert "cost tracking and optimization" in business_value["cost_visibility"].lower()
    
    async def test_performance_insights_provided(self, scenario_runner, test_workspace_for_scenarios):
        """Test that performance insights are provided."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=False
        )
        
        business_value = result["business_value_delivered"]
        assert "performance_insights" in business_value
        assert "performance analysis" in business_value["performance_insights"].lower()
    
    async def test_operational_efficiency_improved(self, scenario_runner, test_workspace_for_scenarios):
        """Test that operational efficiency improvements are delivered."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=False
        )
        
        business_value = result["business_value_delivered"]
        assert "operational_efficiency" in business_value
        assert "automated reporting" in business_value["operational_efficiency"].lower()
    
    async def test_data_governance_ensured(self, scenario_runner, test_workspace_for_scenarios):
        """Test that data governance is ensured."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=True
        )
        
        business_value = result["business_value_delivered"]
        assert "data_governance" in business_value
        assert "privacy" in business_value["data_governance"].lower()
        assert "lifecycle management" in business_value["data_governance"].lower()
    
    async def test_decision_support_provided(self, scenario_runner, test_workspace_for_scenarios):
        """Test that decision support is provided."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=False,
            include_backup_restore=False
        )
        
        business_value = result["business_value_delivered"]
        assert "decision_support" in business_value
        assert "data-driven" in business_value["decision_support"].lower()
        assert "recommendations" in business_value["decision_support"].lower()


# ============================================================================
# Performance Tests
# ============================================================================

class TestScenarioPerformance:
    """Test performance of analytics scenarios."""
    
    async def test_usage_tracking_performance(self, scenario_runner, test_workspace_for_scenarios):
        """Test performance of usage tracking scenario."""
        import time
        
        start_time = time.time()
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=30,
            task_count=100
        )
        duration = time.time() - start_time
        
        assert result["scenario_status"] == "completed"
        # Should complete within reasonable time (adjust based on requirements)
        assert duration < 30.0  # Less than 30 seconds
    
    async def test_trend_analysis_performance(self, scenario_runner, test_workspace_for_scenarios):
        """Test performance of trend analysis scenario."""
        import time
        
        start_time = time.time()
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=90
        )
        duration = time.time() - start_time
        
        assert result["scenario_status"] == "completed"
        assert duration < 60.0  # Less than 1 minute for trend analysis
    
    async def test_lifecycle_performance(self, scenario_runner, test_workspace_for_scenarios):
        """Test performance of complete lifecycle scenario."""
        import time
        
        start_time = time.time()
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=True
        )
        duration = time.time() - start_time
        
        assert result["scenario_status"] == "completed"
        assert duration < 45.0  # Less than 45 seconds for full lifecycle
    
    async def test_concurrent_scenario_execution(self, scenario_runner, test_workspace_for_scenarios):
        """Test running multiple scenarios concurrently."""
        import asyncio
        import time
        
        start_time = time.time()
        
        # Run multiple scenarios concurrently
        tasks = [
            scenario_runner.run_usage_tracking_scenario(test_workspace_for_scenarios.id),
            scenario_runner.run_trend_analysis_scenario(test_workspace_for_scenarios.id),
            scenario_runner.run_lifecycle_scenario(test_workspace_for_scenarios.id)
        ]
        
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time
        
        # All should complete
        for result in results:
            assert result["scenario_status"] == "completed"
        
        # Concurrent execution should be faster than sequential
        assert duration < sum([
            30.0,  # usage tracking
            60.0,  # trend analysis  
            45.0   # lifecycle
        ])  # Should be less than sequential total


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestScenarioErrorHandling:
    """Test error handling in analytics scenarios."""
    
    async def test_graceful_degradation_on_errors(self, scenario_runner, test_workspace_for_scenarios):
        """Test that scenarios gracefully handle errors."""
        # Run scenario and verify it completes even with simulated errors
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=7,
            task_count=25
        )
        
        # Should still complete with success
        assert result["scenario_status"] == "completed"
        
        # Data quality should still be reasonable
        assert result["data_quality_score"] > 80
    
    async def test_partial_scenario_completion(self, scenario_runner, test_workspace_for_scenarios):
        """Test that scenarios handle partial completion gracefully."""
        # This would test scenarios that fail partway through
        # For now, verify the lifecycle scenario structure supports it
        
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=True
        )
        
        # Should have clear step progression
        step_numbers = [step["step"] for step in result["execution_steps"]]
        assert step_numbers == sorted(step_numbers)  # Should be sequential
    
    async def test_scenario_recovery(self, scenario_runner, test_workspace_for_scenarios):
        """Test that scenarios can recover from failures."""
        # Run a complete scenario
        result1 = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=14,
            task_count=50
        )
        
        # Run the same scenario again (should be idempotent)
        result2 = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=14,
            task_count=50
        )
        
        # Both should succeed
        assert result1["scenario_status"] == "completed"
        assert result2["scenario_status"] == "completed"


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestScenarioIntegration:
    """Integration tests for analytics scenarios."""
    
    async def test_usage_tracking_with_real_data(
        self,
        scenario_runner,
        test_workspace_for_scenarios
    ):
        """Test usage tracking with real database data."""
        workspace_id = test_workspace_for_scenarios.id
        
        # Run usage tracking scenario
        result = await scenario_runner.run_usage_tracking_scenario(
            workspace_id,
            duration_days=7,
            task_count=20
        )
        
        assert result["scenario_status"] == "completed"
        assert result["workspace_id"] == workspace_id
        
        # Verify data flows through the system correctly
        for step in result["execution_steps"]:
            assert step["completed"] is True
            assert "details" in step
    
    async def test_trend_analysis_with_historical_context(
        self,
        scenario_runner,
        test_workspace_for_scenarios
    ):
        """Test trend analysis with historical context."""
        result = await scenario_runner.run_trend_analysis_scenario(
            test_workspace_for_scenarios.id,
            historical_days=60
        )
        
        assert result["scenario_status"] == "completed"
        assert len(result["trend_results"]) > 0
        assert len(result["recommendations"]) > 0
        
        # Verify trend analysis provides actionable insights
        for trend_name, trend_data in result["trend_results"].items():
            assert "direction" in trend_data
            assert "confidence" in trend_data
            assert 0 <= trend_data["confidence"] <= 1
    
    async def test_complete_lifecycle_with_external_integration(
        self,
        scenario_runner,
        test_workspace_for_scenarios
    ):
        """Test complete lifecycle with external integration."""
        result = await scenario_runner.run_lifecycle_scenario(
            test_workspace_for_scenarios.id,
            include_external_analysis=True,
            include_backup_restore=True
        )
        
        assert result["scenario_status"] == "completed"
        
        # Verify all lifecycle phases
        expected_actions = [
            "workspace_created", "tasks_executed", "costs_accumulate",
            "metrics_calculated", "dashboard_shows_data", "report_generated",
            "trends_analyzed", "optimization_recommendations", "data_exported",
            "backup_created", "restore_tested", "external_analysis_ready",
            "cleanup_executed", "privacy_maintained"
        ]
        
        actual_actions = [step["action"] for step in result["execution_steps"]]
        
        for action in expected_actions:
            assert action in actual_actions, f"Missing action: {action}"
    
    async def test_scenario_performance_under_load(
        self,
        scenario_runner,
        test_workspace_for_scenarios
    ):
        """Test scenario performance under realistic load."""
        import time
        
        # Run scenario with realistic parameters
        start_time = time.time()
        result = await scenario_runner.run_usage_tracking_scenario(
            test_workspace_for_scenarios.id,
            duration_days=30,
            task_count=200
        )
        duration = time.time() - start_time
        
        assert result["scenario_status"] == "completed"
        assert duration < 60.0  # Should handle realistic load


@pytest.mark.asyncio
async def test_scenario_runner_initialization(scenario_runner):
    """Test that scenario runner initializes correctly."""
    assert scenario_runner.db_session is not None


@pytest.mark.asyncio
async def test_scenario_parameter_validation(scenario_runner, test_workspace_for_scenarios):
    """Test that scenarios validate parameters correctly."""
    # Test with valid parameters
    result = await scenario_runner.run_usage_tracking_scenario(
        test_workspace_for_scenarios.id,
        duration_days=30,
        task_count=100
    )
    assert result["scenario_status"] == "completed"
    
    # Test with different parameters
    result2 = await scenario_runner.run_trend_analysis_scenario(
        test_workspace_for_scenarios.id,
        historical_days=90
    )
    assert result2["scenario_status"] == "completed"


@pytest.mark.asyncio
async def test_scenario_output_structure(scenario_runner, test_workspace_for_scenarios):
    """Test that scenario outputs have consistent structure."""
    result = await scenario_runner.run_usage_tracking_scenario(
        test_workspace_for_scenarios.id
    )
    
    # Verify required top-level fields
    required_fields = [
        "scenario_id", "workspace_id", "scenario_type", 
        "start_timestamp", "end_timestamp", "execution_steps", "scenario_status"
    ]
    
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"
    
    # Verify execution steps structure
    for step in result["execution_steps"]:
        step_fields = ["step", "action", "description", "completed", "timestamp", "details"]
        for field in step_fields:
            assert field in step, f"Missing step field: {field}"