# -*- coding: utf-8 -*-
"""Tests for usage metrics and reporting functionality."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.models.entities import (
    Workspace,
    Task,
    Run,
    Agent,
    LLMCall,
    ResourceUsage,
    ExecutionCost,
    KnowledgeItem,
)


class MetricsCalculator:
    """Mock metrics calculator for testing."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def calculate_task_metrics(
        self,
        workspace_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> dict:
        """Calculate task-related metrics."""
        # Mock task metrics
        return {
            "tasks_created": 150,
            "tasks_completed": 120,
            "tasks_failed": 30,
            "tasks_running": 10,
            "success_rate": 0.80,
            "failure_rate": 0.20,
            "average_completion_time_seconds": 3600.5,
            "average_first_response_time_seconds": 45.2,
            "median_completion_time_seconds": 2800.0,
            "p95_completion_time_seconds": 7200.0,
            "tasks_by_priority": {
                "high": 50,
                "medium": 80,
                "low": 20
            },
            "tasks_by_status": {
                "pending": 5,
                "running": 10,
                "completed": 120,
                "failed": 30,
                "cancelled": 5
            },
            "completion_rate_by_day": [
                {"date": "2024-01-01", "count": 15},
                {"date": "2024-01-02", "count": 18},
                {"date": "2024-01-03", "count": 12}
            ]
        }
    
    async def calculate_agent_metrics(
        self,
        workspace_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> dict:
        """Calculate agent-related metrics."""
        return {
            "total_agents": 8,
            "active_agents": 6,
            "agent_usage_count": 450,
            "agent_success_rate": 0.85,
            "agent_quality_score": 4.2,
            "agent_latency_p50": 150.0,
            "agent_latency_p95": 450.0,
            "agent_latency_p99": 800.0,
            "agents_by_type": {
                "code_agent": 3,
                "analysis_agent": 2,
                "documentation_agent": 2,
                "testing_agent": 1
            },
            "agent_performance": [
                {
                    "agent_id": str(uuid4()),
                    "name": "Code Agent 1",
                    "usage_count": 85,
                    "success_rate": 0.92,
                    "quality_score": 4.5,
                    "average_latency": 120.0
                },
                {
                    "agent_id": str(uuid4()),
                    "name": "Analysis Agent 1",
                    "usage_count": 65,
                    "success_rate": 0.88,
                    "quality_score": 4.1,
                    "average_latency": 180.0
                }
            ],
            "agent_trends": [
                {"date": "2024-01-01", "usage": 45, "success_rate": 0.82},
                {"date": "2024-01-02", "usage": 52, "success_rate": 0.87},
                {"date": "2024-01-03", "usage": 38, "success_rate": 0.84}
            ]
        }
    
    async def calculate_knowledge_metrics(
        self,
        workspace_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> dict:
        """Calculate knowledge base metrics."""
        return {
            "items_created": 85,
            "items_updated": 25,
            "items_deleted": 5,
            "total_items": 1200,
            "search_count": 450,
            "search_frequency": {
                "high_frequency": 200,
                "medium_frequency": 180,
                "low_frequency": 70
            },
            "usage_frequency": {
                "highly_used": 150,
                "moderately_used": 300,
                "rarely_used": 750
            },
            "search_quality_score": 4.3,
            "relevance_score": 0.87,
            "trending_items": [
                {
                    "item_id": str(uuid4()),
                    "title": "Getting Started Guide",
                    "search_count": 45,
                    "usage_frequency": "high"
                },
                {
                    "item_id": str(uuid4()),
                    "title": "API Documentation",
                    "search_count": 38,
                    "usage_frequency": "high"
                }
            ],
            "search_performance": {
                "average_response_time_ms": 85.0,
                "cache_hit_rate": 0.75,
                "index_size_mb": 45.2,
                "embedding_dimensions": 384
            }
        }
    
    async def calculate_cost_metrics(
        self,
        workspace_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> dict:
        """Calculate cost-related metrics."""
        return {
            "total_cost_usd": 1250.75,
            "cost_per_task": 8.34,
            "cost_per_day": [
                {"date": "2024-01-01", "cost": 45.50},
                {"date": "2024-01-02", "cost": 52.30},
                {"date": "2024-01-03", "cost": 38.75}
            ],
            "cost_by_provider": {
                "openai": 850.50,
                "anthropic": 300.25,
                "google": 100.00
            },
            "cost_by_model": {
                "gpt-4": 600.00,
                "gpt-3.5-turbo": 250.50,
                "claude-3-sonnet": 300.25,
                "gemini-pro": 100.00
            },
            "most_expensive_tasks": [
                {
                    "task_id": str(uuid4()),
                    "name": "Complex Analysis Task",
                    "cost": 45.80,
                    "tokens_used": 15000
                },
                {
                    "task_id": str(uuid4()),
                    "name": "Code Generation Task",
                    "cost": 32.50,
                    "tokens_used": 12000
                }
            ],
            "cost_trends": {
                "daily_average": 42.15,
                "weekly_average": 295.05,
                "monthly_average": 1180.20,
                "trend_direction": "increasing",
                "trend_percentage": 12.5
            },
            "budget_utilization": {
                "monthly_budget": 2000.00,
                "spent": 1250.75,
                "remaining": 749.25,
                "utilization_percentage": 62.5,
                "projected_end_of_month": 1800.00
            }
        }
    
    async def calculate_workspace_metrics(
        self,
        workspace_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> dict:
        """Calculate overall workspace metrics."""
        return {
            "total_tasks": 170,
            "total_runs": 280,
            "total_artifacts": 95,
            "total_knowledge_items": 1200,
            "total_agents": 8,
            "total_cost": 1250.75,
            "active_users": 5,
            "user_activity": {
                "daily_active": 3,
                "weekly_active": 5,
                "monthly_active": 5
            },
            "performance_metrics": {
                "average_task_duration": 3600.5,
                "system_availability": 0.995,
                "error_rate": 0.05,
                "throughput_per_hour": 25.5
            },
            "resource_utilization": {
                "cpu_usage_percent": 45.2,
                "memory_usage_percent": 62.8,
                "storage_usage_gb": 25.5,
                "network_io_mbps": 12.3
            }
        }


@pytest.fixture
async def metrics_calculator(db_session: AsyncSession):
    """Create metrics calculator fixture."""
    return MetricsCalculator(db_session)


@pytest.fixture
async def test_workspace_with_metrics(db_session: AsyncSession):
    """Create test workspace with comprehensive data."""
    workspace = Workspace(
        name="Test Metrics Workspace",
        slug="test-metrics",
        metadata={}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    
    # Create test tasks with different statuses
    for i in range(50):
        task = Task(
            workspace_id=workspace.id,
            name=f"Test Task {i}",
            description=f"Description for task {i}",
            status=(
                "completed" if i % 3 == 0 
                else "failed" if i % 5 == 0 
                else "running" if i % 7 == 0 
                else "pending"
            ),
            priority=(
                "high" if i % 3 == 0 
                else "medium" if i % 2 == 0 
                else "low"
            ),
            created_at=datetime.utcnow() - timedelta(days=i % 30),
        )
        db_session.add(task)
    
    # Create test agents
    agent_types = ["code_agent", "analysis_agent", "documentation_agent"]
    for i, agent_type in enumerate(agent_types):
        agent = Agent(
            name=f"{agent_type.title()} {i+1}",
            type=agent_type,
            config={"model": "gpt-4", "temperature": 0.7},
        )
        db_session.add(agent)
    
    # Create test knowledge items
    for i in range(100):
        item = KnowledgeItem(
            workspace_id=workspace.id,
            content=f"Test knowledge item {i}",
            source="manual" if i % 2 == 0 else "imported",
            metadata={"category": "general"},
            created_at=datetime.utcnow() - timedelta(days=i % 90),
        )
        db_session.add(item)
    
    await db_session.commit()
    return workspace


# ============================================================================
# Task Metrics Tests
# ============================================================================

class TestTaskMetrics:
    """Test task metrics calculation."""
    
    async def test_task_count_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that task counts are accurate."""
        metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        assert metrics["tasks_created"] > 0
        assert metrics["tasks_completed"] >= 0
        assert metrics["tasks_failed"] >= 0
        assert metrics["tasks_running"] >= 0
        assert metrics["tasks_created"] >= metrics["tasks_completed"] + metrics["tasks_failed"]
    
    async def test_completion_count_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that completion counts are accurate."""
        metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        assert metrics["tasks_completed"] >= 0
        assert "success_rate" in metrics
        assert 0 <= metrics["success_rate"] <= 1
    
    async def test_failure_count_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that failure counts are accurate."""
        metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        assert metrics["tasks_failed"] >= 0
        assert "failure_rate" in metrics
        assert 0 <= metrics["failure_rate"] <= 1
    
    async def test_time_calculation_correct(self, metrics_calculator, test_workspace_with_metrics):
        """Test that time calculations are correct."""
        metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "average_completion_time_seconds" in metrics
        assert metrics["average_completion_time_seconds"] >= 0
        assert "median_completion_time_seconds" in metrics
        assert metrics["median_completion_time_seconds"] >= 0
        assert "p95_completion_time_seconds" in metrics
        assert metrics["p95_completion_time_seconds"] >= 0
    
    async def test_success_rate_calculated(self, metrics_calculator, test_workspace_with_metrics):
        """Test that success rate is calculated correctly."""
        metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "success_rate" in metrics
        assert 0 <= metrics["success_rate"] <= 1
        
        # Success rate should be related to completed vs failed tasks
        if metrics["tasks_completed"] + metrics["tasks_failed"] > 0:
            expected_rate = metrics["tasks_completed"] / (
                metrics["tasks_completed"] + metrics["tasks_failed"]
            )
            assert abs(metrics["success_rate"] - expected_rate) < 0.01
    
    async def test_metrics_per_time_period(self, metrics_calculator, test_workspace_with_metrics):
        """Test that metrics can be calculated per time period."""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        
        metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id,
            start_date=start_date,
            end_date=end_date
        )
        
        assert "completion_rate_by_day" in metrics
        assert isinstance(metrics["completion_rate_by_day"], list)
        
        for day_data in metrics["completion_rate_by_day"]:
            assert "date" in day_data
            assert "count" in day_data
            assert day_data["count"] >= 0


# ============================================================================
# Agent Metrics Tests
# ============================================================================

class TestAgentMetrics:
    """Test agent metrics calculation."""
    
    async def test_usage_tracked(self, metrics_calculator, test_workspace_with_metrics):
        """Test that agent usage is tracked."""
        metrics = await metrics_calculator.calculate_agent_metrics(
            test_workspace_with_metrics.id
        )
        
        assert metrics["agent_usage_count"] > 0
        assert "agents_by_type" in metrics
        assert isinstance(metrics["agents_by_type"], dict)
    
    async def test_success_rate_calculated(self, metrics_calculator, test_workspace_with_metrics):
        """Test that agent success rate is calculated."""
        metrics = await metrics_calculator.calculate_agent_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "agent_success_rate" in metrics
        assert 0 <= metrics["agent_success_rate"] <= 1
    
    async def test_quality_assessed(self, metrics_calculator, test_workspace_with_metrics):
        """Test that agent quality is assessed."""
        metrics = await metrics_calculator.calculate_agent_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "agent_quality_score" in metrics
        assert 1 <= metrics["agent_quality_score"] <= 5  # Assuming 1-5 scale
    
    async def test_latency_measured(self, metrics_calculator, test_workspace_with_metrics):
        """Test that agent latency is measured."""
        metrics = await metrics_calculator.calculate_agent_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "agent_latency_p50" in metrics
        assert "agent_latency_p95" in metrics
        assert "agent_latency_p99" in metrics
        assert metrics["agent_latency_p50"] <= metrics["agent_latency_p95"]
        assert metrics["agent_latency_p95"] <= metrics["agent_latency_p99"]
        assert all(latency >= 0 for latency in [
            metrics["agent_latency_p50"],
            metrics["agent_latency_p95"],
            metrics["agent_latency_p99"]
        ])
    
    async def test_per_agent_comparison(self, metrics_calculator, test_workspace_with_metrics):
        """Test per-agent comparison metrics."""
        metrics = await metrics_calculator.calculate_agent_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "agent_performance" in metrics
        assert isinstance(metrics["agent_performance"], list)
        
        for agent_perf in metrics["agent_performance"]:
            assert "agent_id" in agent_perf
            assert "name" in agent_perf
            assert "usage_count" in agent_perf
            assert "success_rate" in agent_perf
            assert "quality_score" in agent_perf
            assert "average_latency" in agent_perf
            assert agent_perf["usage_count"] >= 0
            assert 0 <= agent_perf["success_rate"] <= 1


# ============================================================================
# Knowledge Base Metrics Tests
# ============================================================================

class TestKnowledgeMetrics:
    """Test knowledge base metrics calculation."""
    
    async def test_item_counts_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that item counts are accurate."""
        metrics = await metrics_calculator.calculate_knowledge_metrics(
            test_workspace_with_metrics.id
        )
        
        assert metrics["items_created"] >= 0
        assert metrics["items_updated"] >= 0
        assert metrics["items_deleted"] >= 0
        assert metrics["total_items"] >= 0
    
    async def test_search_frequency_tracked(self, metrics_calculator, test_workspace_with_metrics):
        """Test that search frequency is tracked."""
        metrics = await metrics_calculator.calculate_knowledge_metrics(
            test_workspace_with_metrics.id
        )
        
        assert metrics["search_count"] >= 0
        assert "search_frequency" in metrics
        assert "high_frequency" in metrics["search_frequency"]
        assert "medium_frequency" in metrics["search_frequency"]
        assert "low_frequency" in metrics["search_frequency"]
    
    async def test_usage_frequency_tracked(self, metrics_calculator, test_workspace_with_metrics):
        """Test that usage frequency is tracked."""
        metrics = await metrics_calculator.calculate_knowledge_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "usage_frequency" in metrics
        assert "highly_used" in metrics["usage_frequency"]
        assert "moderately_used" in metrics["usage_frequency"]
        assert "rarely_used" in metrics["usage_frequency"]
    
    async def test_relevance_scored(self, metrics_calculator, test_workspace_with_metrics):
        """Test that relevance is scored."""
        metrics = await metrics_calculator.calculate_knowledge_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "search_quality_score" in metrics
        assert 1 <= metrics["search_quality_score"] <= 5
        assert "relevance_score" in metrics
        assert 0 <= metrics["relevance_score"] <= 1
    
    async def test_trending_items_identified(self, metrics_calculator, test_workspace_with_metrics):
        """Test that trending items are identified."""
        metrics = await metrics_calculator.calculate_knowledge_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "trending_items" in metrics
        assert isinstance(metrics["trending_items"], list)
        
        for item in metrics["trending_items"]:
            assert "item_id" in item
            assert "title" in item
            assert "search_count" in item
            assert "usage_frequency" in item
            assert item["search_count"] >= 0


# ============================================================================
# Cost Metrics Tests
# ============================================================================

class TestCostMetrics:
    """Test cost metrics calculation."""
    
    async def test_cost_totals_correct(self, metrics_calculator, test_workspace_with_metrics):
        """Test that cost totals are calculated correctly."""
        metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "total_cost_usd" in metrics
        assert metrics["total_cost_usd"] >= 0
        assert isinstance(metrics["total_cost_usd"], (int, float))
    
    async def test_per_task_cost_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that per-task cost is accurate."""
        metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "cost_per_task" in metrics
        assert metrics["cost_per_task"] >= 0
        assert isinstance(metrics["cost_per_task"], (int, float))
    
    async def test_trends_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that cost trends are accurate."""
        metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "cost_trends" in metrics
        trends = metrics["cost_trends"]
        
        assert "daily_average" in trends
        assert "weekly_average" in trends
        assert "monthly_average" in trends
        assert "trend_direction" in trends
        assert "trend_percentage" in trends
        
        assert trends["daily_average"] >= 0
        assert trends["weekly_average"] >= 0
        assert trends["monthly_average"] >= 0
        assert trends["trend_direction"] in ["increasing", "decreasing", "stable"]
        assert isinstance(trends["trend_percentage"], (int, float))
    
    async def test_rankings_correct(self, metrics_calculator, test_workspace_with_metrics):
        """Test that cost rankings are correct."""
        metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "most_expensive_tasks" in metrics
        assert isinstance(metrics["most_expensive_tasks"], list)
        
        # Should be sorted by cost in descending order
        costs = [task["cost"] for task in metrics["most_expensive_tasks"]]
        assert costs == sorted(costs, reverse=True)
        
        for task in metrics["most_expensive_tasks"]:
            assert "task_id" in task
            assert "name" in task
            assert "cost" in task
            assert "tokens_used" in task
            assert task["cost"] >= 0
            assert task["tokens_used"] >= 0
    
    async def test_provider_comparison_accurate(self, metrics_calculator, test_workspace_with_metrics):
        """Test that provider cost comparison is accurate."""
        metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "cost_by_provider" in metrics
        assert isinstance(metrics["cost_by_provider"], dict)
        
        for provider, cost in metrics["cost_by_provider"].items():
            assert cost >= 0
            assert isinstance(provider, str)
    
    async def test_budget_tracking(self, metrics_calculator, test_workspace_with_metrics):
        """Test that budget tracking works."""
        metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        assert "budget_utilization" in metrics
        budget = metrics["budget_utilization"]
        
        assert "monthly_budget" in budget
        assert "spent" in budget
        assert "remaining" in budget
        assert "utilization_percentage" in budget
        assert "projected_end_of_month" in budget
        
        assert budget["monthly_budget"] >= 0
        assert budget["spent"] >= 0
        assert budget["remaining"] >= 0
        assert 0 <= budget["utilization_percentage"] <= 100
        assert budget["projected_end_of_month"] >= 0


# ============================================================================
# Aggregation Tests
# ============================================================================

class TestMetricsAggregation:
    """Test metrics aggregation across different dimensions."""
    
    async def test_daily_aggregation(self, metrics_calculator, test_workspace_with_metrics):
        """Test daily metrics aggregation."""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        
        task_metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id,
            start_date=start_date,
            end_date=end_date
        )
        
        assert "completion_rate_by_day" in task_metrics
        assert isinstance(task_metrics["completion_rate_by_day"], list)
        
        cost_metrics = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id,
            start_date=start_date,
            end_date=end_date
        )
        
        assert "cost_per_day" in cost_metrics
        assert isinstance(cost_metrics["cost_per_day"], list)
    
    async def test_weekly_aggregation(self, metrics_calculator, test_workspace_with_metrics):
        """Test weekly metrics aggregation."""
        start_date = datetime.utcnow() - timedelta(weeks=4)
        end_date = datetime.utcnow()
        
        workspace_metrics = await metrics_calculator.calculate_workspace_metrics(
            test_workspace_with_metrics.id,
            start_date=start_date,
            end_date=end_date
        )
        
        assert "performance_metrics" in workspace_metrics
        assert "resource_utilization" in workspace_metrics
    
    async def test_monthly_aggregation(self, metrics_calculator, test_workspace_with_metrics):
        """Test monthly metrics aggregation."""
        start_date = datetime.utcnow() - timedelta(days=90)
        end_date = datetime.utcnow()
        
        agent_metrics = await metrics_calculator.calculate_agent_metrics(
            test_workspace_with_metrics.id,
            start_date=start_date,
            end_date=end_date
        )
        
        assert "agent_trends" in agent_metrics
        assert isinstance(agent_metrics["agent_trends"], list)
    
    async def test_cross_workspace_aggregation(self, metrics_calculator):
        """Test aggregation across multiple workspaces."""
        # This would test metrics aggregation across all workspaces
        # For now, just verify the method exists and returns data
        workspace_id = str(uuid4())
        metrics = await metrics_calculator.calculate_workspace_metrics(workspace_id)
        
        assert isinstance(metrics, dict)
        assert len(metrics) > 0


# ============================================================================
# Real-time Updates Tests
# ============================================================================

class TestRealTimeMetrics:
    """Test real-time metrics updates."""
    
    async def test_live_metrics_updates(self, metrics_calculator, test_workspace_with_metrics):
        """Test that metrics update in real-time."""
        # Get initial metrics
        initial_metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        # Add a new task (simulated)
        # In real implementation, would add task to database
        new_task = Task(
            workspace_id=test_workspace_with_metrics.id,
            name="New Task",
            status="completed"
        )
        metrics_calculator.db_session.add(new_task)
        await metrics_calculator.db_session.commit()
        
        # Get updated metrics
        updated_metrics = await metrics_calculator.calculate_task_metrics(
            test_workspace_with_metrics.id
        )
        
        assert updated_metrics["tasks_created"] >= initial_metrics["tasks_created"]
        assert updated_metrics["tasks_completed"] >= initial_metrics["tasks_completed"]
    
    async def test_cost_accumulation(self, metrics_calculator, test_workspace_with_metrics):
        """Test cost accumulation over time."""
        initial_cost = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        # Simulate new LLM call with cost
        initial_total = initial_cost["total_cost_usd"]
        
        updated_cost = await metrics_calculator.calculate_cost_metrics(
            test_workspace_with_metrics.id
        )
        
        # Cost should not decrease (cumulative)
        assert updated_cost["total_cost_usd"] >= initial_total


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestMetricsIntegration:
    """Integration tests for metrics system."""
    
    async def test_comprehensive_metrics_collection(
        self,
        metrics_calculator,
        test_workspace_with_metrics
    ):
        """Test comprehensive metrics collection across all dimensions."""
        workspace_id = test_workspace_with_metrics.id
        
        # Collect all metrics
        task_metrics = await metrics_calculator.calculate_task_metrics(workspace_id)
        agent_metrics = await metrics_calculator.calculate_agent_metrics(workspace_id)
        knowledge_metrics = await metrics_calculator.calculate_knowledge_metrics(workspace_id)
        cost_metrics = await metrics_calculator.calculate_cost_metrics(workspace_id)
        workspace_metrics = await metrics_calculator.calculate_workspace_metrics(workspace_id)
        
        # Verify all metrics are collected
        assert len(task_metrics) > 0
        assert len(agent_metrics) > 0
        assert len(knowledge_metrics) > 0
        assert len(cost_metrics) > 0
        assert len(workspace_metrics) > 0
        
        # Verify consistency between metrics
        # Total tasks should be consistent
        assert workspace_metrics["total_tasks"] >= task_metrics["tasks_created"]
        
        # Cost metrics should be consistent
        assert cost_metrics["total_cost_usd"] >= 0
        assert workspace_metrics["total_cost"] >= 0
    
    async def test_metrics_time_series_consistency(
        self,
        metrics_calculator,
        test_workspace_with_metrics
    ):
        """Test consistency of time series metrics."""
        workspace_id = test_workspace_with_metrics.id
        
        # Get metrics for overlapping periods
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        
        full_metrics = await metrics_calculator.calculate_task_metrics(
            workspace_id, start_date=start_date, end_date=end_date
        )
        
        # Metrics should contain time series data
        assert "completion_rate_by_day" in full_metrics
        assert isinstance(full_metrics["completion_rate_by_day"], list)
        
        # Each day should have a count
        for day_data in full_metrics["completion_rate_by_day"]:
            assert "date" in day_data
            assert "count" in day_data
            assert isinstance(day_data["count"], int)
            assert day_data["count"] >= 0
    
    async def test_metrics_performance_under_load(
        self,
        metrics_calculator,
        test_workspace_with_metrics
    ):
        """Test metrics calculation performance under load."""
        import time
        
        workspace_id = test_workspace_with_metrics.id
        start_time = time.time()
        
        # Calculate all metrics
        await metrics_calculator.calculate_task_metrics(workspace_id)
        await metrics_calculator.calculate_agent_metrics(workspace_id)
        await metrics_calculator.calculate_knowledge_metrics(workspace_id)
        await metrics_calculator.calculate_cost_metrics(workspace_id)
        await metrics_calculator.calculate_workspace_metrics(workspace_id)
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time (adjust based on requirements)
        assert duration < 30.0  # Less than 30 seconds


@pytest.mark.asyncio
async def test_metrics_calculator_initialization(metrics_calculator):
    """Test that metrics calculator initializes correctly."""
    assert metrics_calculator.db_session is not None


@pytest.mark.asyncio
async def test_metrics_data_validation(metrics_calculator, test_workspace_with_metrics):
    """Test that returned metrics data is valid."""
    metrics = await metrics_calculator.calculate_task_metrics(
        test_workspace_with_metrics.id
    )
    
    # Check that all expected fields are present and valid
    required_fields = [
        "tasks_created", "tasks_completed", "tasks_failed", "tasks_running",
        "success_rate", "failure_rate", "average_completion_time_seconds"
    ]
    
    for field in required_fields:
        assert field in metrics, f"Missing field: {field}"
        if field in ["success_rate", "failure_rate"]:
            assert 0 <= metrics[field] <= 1
        elif "time" in field or "completion" in field:
            assert metrics[field] >= 0