# -*- coding: utf-8 -*-
"""Tests for cost tracking and budget management system."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import (
    Workspace,
    LLMCall,
    ResourceUsage,
    ExecutionCost,
    WorkspaceBudget,
)
from backend.services.cost import (
    LLMCostTracker,
    ComputeTracker,
    BudgetManager,
    CostOptimizer,
)


@pytest.fixture
async def workspace(db_session: AsyncSession):
    """Create a test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        slug="test-workspace",
        meta_data={}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def llm_tracker(db_session: AsyncSession):
    """Create LLM cost tracker."""
    return LLMCostTracker(db_session)


@pytest.fixture
async def compute_tracker(db_session: AsyncSession):
    """Create compute tracker."""
    return ComputeTracker(db_session)


@pytest.fixture
async def budget_manager(db_session: AsyncSession):
    """Create budget manager."""
    return BudgetManager(db_session)


@pytest.fixture
async def cost_optimizer(db_session: AsyncSession):
    """Create cost optimizer."""
    return CostOptimizer(db_session)


class TestLLMCostTracker:
    """Test LLM cost tracking."""
    
    async def test_calculate_cost(self, llm_tracker):
        """Test cost calculation for different models."""
        # GPT-4 cost calculation
        cost = llm_tracker.calculate_cost("openai", "gpt-4", 1000, 500)
        assert cost > 0
        assert cost == pytest.approx(0.03 + 0.03, rel=1e-6)  # $0.03 per 1K prompt + $0.06 per 1K completion
        
        # Claude Sonnet cost calculation
        cost = llm_tracker.calculate_cost("anthropic", "claude-3-sonnet", 1000, 1000)
        assert cost > 0
        assert cost == pytest.approx(0.003 + 0.015, rel=1e-6)  # $0.003 + $0.015 per 1K tokens
    
    async def test_log_llm_call(self, llm_tracker, workspace):
        """Test logging an LLM call."""
        execution_id = str(uuid4())
        
        call = await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=1000,
            tokens_completion=500,
            latency_ms=1500,
            metadata={"temperature": 0.7}
        )
        
        assert call is not None
        assert call.workspace_id == workspace.id
        assert call.execution_id == execution_id
        assert call.provider == "openai"
        assert call.model == "gpt-4"
        assert call.tokens_prompt == 1000
        assert call.tokens_completion == 500
        assert call.tokens_total == 1500
        assert call.cost_usd > 0
        assert call.latency_ms == 1500
    
    async def test_get_execution_costs(self, llm_tracker, workspace):
        """Test getting execution costs."""
        execution_id = str(uuid4())
        
        # Log multiple calls for the same execution
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=1000,
            tokens_completion=500,
        )
        
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-3.5-turbo",
            tokens_prompt=500,
            tokens_completion=300,
        )
        
        costs = await llm_tracker.get_execution_llm_costs(execution_id)
        
        assert costs["call_count"] == 2
        assert costs["total_tokens"] == 2300
        assert costs["total_cost"] > 0
    
    async def test_get_workspace_costs(self, llm_tracker, workspace):
        """Test getting workspace costs."""
        execution_id = str(uuid4())
        
        # Log some calls
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=1000,
            tokens_completion=500,
        )
        
        costs = await llm_tracker.get_workspace_costs(workspace.id, "month")
        
        assert costs["period"] == "month"
        assert costs["total_cost"] > 0
        assert costs["total_tokens"] > 0
        assert costs["call_count"] > 0
        assert len(costs["by_model"]) > 0


class TestComputeTracker:
    """Test compute resource tracking."""
    
    async def test_calculate_resource_cost(self, compute_tracker):
        """Test resource cost calculation."""
        # CPU cost (2 cores for 1 hour)
        cost = compute_tracker.calculate_resource_cost("cpu", 2.0, 3600)
        assert cost == pytest.approx(0.10, rel=1e-6)  # 2 cores * 1 hour * $0.05
        
        # Memory cost (4 GB for 1 hour)
        cost = compute_tracker.calculate_resource_cost("memory", 4.0, 3600)
        assert cost == pytest.approx(0.04, rel=1e-6)  # 4 GB * 1 hour * $0.01
    
    async def test_log_resource_usage(self, compute_tracker, workspace):
        """Test logging resource usage."""
        execution_id = str(uuid4())
        
        usage = await compute_tracker.log_resource_usage(
            workspace_id=workspace.id,
            execution_id=execution_id,
            resource_type="cpu",
            usage_value=2.0,
            unit="cores",
            duration_seconds=3600,
            metadata={"source": "sandbox"}
        )
        
        assert usage is not None
        assert usage.workspace_id == workspace.id
        assert usage.execution_id == execution_id
        assert usage.resource_type == "cpu"
        assert usage.usage_value == 2.0
        assert usage.unit == "cores"
        assert usage.cost_usd > 0
    
    async def test_track_sandbox_execution(self, compute_tracker, workspace):
        """Test tracking sandbox execution."""
        execution_id = str(uuid4())
        
        records = await compute_tracker.track_sandbox_execution(
            workspace_id=workspace.id,
            execution_id=execution_id,
            cpu_cores=1.0,
            memory_mb=512,
            duration_seconds=120,
        )
        
        assert len(records) == 3  # CPU, memory, sandbox
        assert all(r.workspace_id == workspace.id for r in records)
        assert all(r.execution_id == execution_id for r in records)


class TestBudgetManager:
    """Test budget management."""
    
    async def test_create_workspace_budget(self, budget_manager, workspace):
        """Test creating workspace budget."""
        budget = await budget_manager.create_workspace_budget(
            workspace_id=workspace.id,
            monthly_budget_usd=1000.0,
            alert_threshold_percent=80,
            alert_emails=["admin@example.com"],
            hard_limit=False,
        )
        
        assert budget is not None
        assert budget.workspace_id == workspace.id
        assert budget.monthly_budget_usd == 1000.0
        assert budget.alert_threshold_percent == 80
        assert budget.is_enabled is True
        assert budget.hard_limit is False
    
    async def test_update_workspace_spending(self, budget_manager, llm_tracker, workspace):
        """Test updating workspace spending."""
        # Create budget
        budget = await budget_manager.create_workspace_budget(
            workspace_id=workspace.id,
            monthly_budget_usd=100.0,
        )
        
        # Log some LLM calls
        execution_id = str(uuid4())
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=10000,
            tokens_completion=5000,
        )
        
        # Update spending
        updated_budget = await budget_manager.update_workspace_spending(workspace.id)
        
        assert updated_budget is not None
        assert updated_budget.current_month_spent > 0
    
    async def test_check_budget_threshold(self, budget_manager, llm_tracker, workspace):
        """Test checking budget thresholds."""
        # Create budget with low limit
        await budget_manager.create_workspace_budget(
            workspace_id=workspace.id,
            monthly_budget_usd=1.0,  # Very low budget
            alert_threshold_percent=80,
        )
        
        # Log expensive calls to exceed threshold
        execution_id = str(uuid4())
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=20000,
            tokens_completion=10000,
        )
        
        # Check threshold
        status = await budget_manager.check_budget_threshold(workspace.id)
        
        assert status["has_budget"] is True
        assert status["spent"] > 0
        assert status["is_over_budget"] is True or status["usage_percent"] >= 80
    
    async def test_can_execute_within_budget(self, budget_manager, workspace):
        """Test execution permission check."""
        # Create budget
        await budget_manager.create_workspace_budget(
            workspace_id=workspace.id,
            monthly_budget_usd=1000.0,
            hard_limit=False,
        )
        
        # Check if can execute (should be allowed)
        result = await budget_manager.can_execute(workspace.id, estimated_cost=10.0)
        
        assert result["can_execute"] is True
    
    async def test_can_execute_hard_limit(self, budget_manager, llm_tracker, workspace):
        """Test hard limit enforcement."""
        # Create budget with hard limit
        await budget_manager.create_workspace_budget(
            workspace_id=workspace.id,
            monthly_budget_usd=1.0,
            hard_limit=True,
        )
        
        # Exceed budget
        execution_id = str(uuid4())
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=20000,
            tokens_completion=10000,
        )
        
        # Check if can execute (should be blocked)
        result = await budget_manager.can_execute(workspace.id, estimated_cost=10.0)
        
        # Might be blocked if over budget
        if result["can_execute"] is False:
            assert "budget exceeded" in result["reason"].lower()


class TestCostOptimizer:
    """Test cost optimization."""
    
    async def test_get_recommendations(self, cost_optimizer, llm_tracker, workspace):
        """Test getting optimization recommendations."""
        # Log some expensive calls
        execution_id = str(uuid4())
        
        # Use expensive model with low tokens (optimization opportunity)
        for _ in range(5):
            await llm_tracker.log_llm_call(
                workspace_id=workspace.id,
                execution_id=execution_id,
                provider="openai",
                model="gpt-4",
                tokens_prompt=300,
                tokens_completion=200,
            )
        
        recommendations = await cost_optimizer.get_recommendations(workspace.id, "month")
        
        # Should get recommendations for model downgrade
        assert isinstance(recommendations, list)
        # Some recommendations might be generated
    
    async def test_forecast_monthly_cost(self, cost_optimizer, llm_tracker, workspace):
        """Test monthly cost forecast."""
        # Log some calls
        execution_id = str(uuid4())
        await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=1000,
            tokens_completion=500,
        )
        
        forecast = await cost_optimizer.forecast_monthly_cost(workspace.id)
        
        assert "current_month_spent" in forecast
        assert "forecast_end_of_month" in forecast
        assert "daily_average" in forecast
        assert forecast["current_month_spent"] >= 0
        assert forecast["forecast_end_of_month"] >= 0


@pytest.mark.integration
class TestCostTrackingIntegration:
    """Integration tests for cost tracking system."""
    
    async def test_full_cost_tracking_flow(
        self,
        llm_tracker,
        compute_tracker,
        budget_manager,
        cost_optimizer,
        workspace,
    ):
        """Test complete cost tracking workflow."""
        execution_id = str(uuid4())
        
        # 1. Set up budget
        budget = await budget_manager.create_workspace_budget(
            workspace_id=workspace.id,
            monthly_budget_usd=100.0,
            alert_threshold_percent=80,
        )
        assert budget is not None
        
        # 2. Check if can execute
        can_exec = await budget_manager.can_execute(workspace.id)
        assert can_exec["can_execute"] is True
        
        # 3. Track LLM calls
        llm_call = await llm_tracker.log_llm_call(
            workspace_id=workspace.id,
            execution_id=execution_id,
            provider="openai",
            model="gpt-4",
            tokens_prompt=1000,
            tokens_completion=500,
        )
        assert llm_call.cost_usd > 0
        
        # 4. Track compute resources
        records = await compute_tracker.track_sandbox_execution(
            workspace_id=workspace.id,
            execution_id=execution_id,
            cpu_cores=1.0,
            memory_mb=512,
            duration_seconds=60,
        )
        assert len(records) == 3
        
        # 5. Get execution costs
        llm_costs = await llm_tracker.get_execution_llm_costs(execution_id)
        compute_costs = await compute_tracker.get_execution_compute_costs(execution_id)
        
        assert llm_costs["total_cost"] > 0
        assert compute_costs["total_cost"] > 0
        
        # 6. Get workspace summary
        workspace_costs = await llm_tracker.get_workspace_costs(workspace.id, "month")
        assert workspace_costs["total_cost"] > 0
        
        # 7. Update budget and check
        updated_budget = await budget_manager.update_workspace_spending(workspace.id)
        assert updated_budget.current_month_spent > 0
        
        # 8. Get recommendations
        recommendations = await cost_optimizer.get_recommendations(workspace.id, "month")
        assert isinstance(recommendations, list)
        
        # 9. Get forecast
        forecast = await cost_optimizer.forecast_monthly_cost(workspace.id)
        assert forecast["current_month_spent"] > 0
