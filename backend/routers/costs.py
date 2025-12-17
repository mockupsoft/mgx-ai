# -*- coding: utf-8 -*-
"""Cost tracking and budget management API endpoints."""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.services.cost import (
    get_llm_tracker,
    get_compute_tracker,
    get_budget_manager,
    get_cost_optimizer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["costs"])


# Request/Response Models
class BudgetCreateRequest(BaseModel):
    """Request model for creating/updating workspace budget."""
    
    monthly_budget_usd: float = Field(..., gt=0, description="Monthly budget limit in USD")
    alert_threshold_percent: int = Field(default=80, ge=0, le=100, description="Alert threshold percentage")
    alert_emails: List[str] = Field(default_factory=list, description="Email addresses for alerts")
    hard_limit: bool = Field(default=False, description="Whether to enforce hard limit")


class ProjectBudgetCreateRequest(BaseModel):
    """Request model for creating/updating project budget."""
    
    monthly_budget_usd: float = Field(..., gt=0, description="Monthly budget limit in USD")


class BudgetResponse(BaseModel):
    """Response model for budget information."""
    
    id: str
    workspace_id: str
    monthly_budget_usd: float
    current_month_spent: float
    budget_remaining: float
    budget_used_percent: float
    is_over_budget: bool
    alert_threshold_percent: int
    alert_emails: List[str]
    hard_limit: bool
    is_enabled: bool


class CostSummaryResponse(BaseModel):
    """Response model for cost summary."""
    
    period: str
    total_cost: float
    llm_cost: float
    compute_cost: float
    breakdown: Dict
    by_model: Optional[List[Dict]] = None
    by_resource: Optional[List[Dict]] = None
    trends: Optional[Dict] = None


class ExecutionCostResponse(BaseModel):
    """Response model for execution cost."""
    
    execution_id: str
    total_cost: float
    llm_cost: float
    compute_cost: float
    breakdown: Dict


class RecommendationResponse(BaseModel):
    """Response model for cost optimization recommendation."""
    
    type: str
    priority: str
    title: str
    description: str
    estimated_savings: Optional[float] = None
    impact: Optional[str] = None


# Workspace Costs
@router.get("/workspaces/{workspace_id}/costs", response_model=CostSummaryResponse)
async def get_workspace_costs(
    workspace_id: str,
    period: str = Query(default="month", regex="^(day|week|month|all)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cost summary for a workspace.
    
    - **workspace_id**: Workspace identifier
    - **period**: Time period (day, week, month, all)
    
    Returns detailed cost breakdown including:
    - Total costs (LLM + compute)
    - Breakdown by model/provider
    - Breakdown by resource type
    - Daily trends
    """
    try:
        llm_tracker = get_llm_tracker(db)
        compute_tracker = get_compute_tracker(db)
        optimizer = get_cost_optimizer(db)
        
        # Get LLM costs
        llm_costs = await llm_tracker.get_workspace_costs(workspace_id, period)
        
        # Get compute costs
        compute_costs = await compute_tracker.get_workspace_usage(workspace_id, period)
        
        # Get daily trends
        daily_costs = await llm_tracker.get_daily_costs(workspace_id, days=30)
        
        # Get forecast
        forecast = await optimizer.forecast_monthly_cost(workspace_id)
        
        return CostSummaryResponse(
            period=period,
            total_cost=llm_costs["total_cost"] + compute_costs["total_cost"],
            llm_cost=llm_costs["total_cost"],
            compute_cost=compute_costs["total_cost"],
            breakdown={
                "llm": {
                    "total": llm_costs["total_cost"],
                    "tokens": llm_costs["total_tokens"],
                    "calls": llm_costs["call_count"],
                },
                "compute": {
                    "total": compute_costs["total_cost"],
                    "records": compute_costs["record_count"],
                },
            },
            by_model=llm_costs["by_model"],
            by_resource=compute_costs["by_type"],
            trends={
                "daily": daily_costs,
                "forecast_eom": forecast["forecast_end_of_month"],
                "forecast_confidence": forecast["projection_accuracy"],
            },
        )
        
    except Exception as e:
        logger.error(f"Error getting workspace costs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve costs: {str(e)}")


# Execution Costs
@router.get("/executions/{execution_id}/costs", response_model=ExecutionCostResponse)
async def get_execution_costs(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get cost breakdown for a specific execution.
    
    - **execution_id**: Task run or workflow execution identifier
    
    Returns:
    - Total cost (LLM + compute)
    - Breakdown by phase
    - Token usage statistics
    """
    try:
        llm_tracker = get_llm_tracker(db)
        compute_tracker = get_compute_tracker(db)
        
        # Get LLM costs
        llm_costs = await llm_tracker.get_execution_llm_costs(execution_id)
        
        # Get compute costs
        compute_costs = await compute_tracker.get_execution_compute_costs(execution_id)
        
        return ExecutionCostResponse(
            execution_id=execution_id,
            total_cost=llm_costs["total_cost"] + compute_costs["total_cost"],
            llm_cost=llm_costs["total_cost"],
            compute_cost=compute_costs["total_cost"],
            breakdown={
                "llm": {
                    "cost": llm_costs["total_cost"],
                    "tokens": llm_costs["total_tokens"],
                    "calls": llm_costs["call_count"],
                },
                "compute": {
                    "cost": compute_costs["total_cost"],
                    "by_type": compute_costs.get("by_type", {}),
                },
            },
        )
        
    except Exception as e:
        logger.error(f"Error getting execution costs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve execution costs: {str(e)}")


# Budget Management
@router.get("/workspaces/{workspace_id}/budget", response_model=BudgetResponse)
async def get_workspace_budget(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get budget information for a workspace.
    
    - **workspace_id**: Workspace identifier
    """
    try:
        manager = get_budget_manager(db)
        budget = await manager.get_workspace_budget(workspace_id)
        
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        # Update spending
        budget = await manager.update_workspace_spending(workspace_id)
        
        return BudgetResponse(
            id=budget.id,
            workspace_id=budget.workspace_id,
            monthly_budget_usd=budget.monthly_budget_usd,
            current_month_spent=budget.current_month_spent,
            budget_remaining=budget.budget_remaining,
            budget_used_percent=budget.budget_used_percent,
            is_over_budget=budget.is_over_budget,
            alert_threshold_percent=budget.alert_threshold_percent,
            alert_emails=budget.alert_emails,
            hard_limit=budget.hard_limit,
            is_enabled=budget.is_enabled,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workspace budget: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve budget: {str(e)}")


@router.post("/workspaces/{workspace_id}/budget", response_model=BudgetResponse)
async def create_workspace_budget(
    workspace_id: str,
    request: BudgetCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update workspace budget.
    
    - **workspace_id**: Workspace identifier
    - **request**: Budget configuration
    """
    try:
        manager = get_budget_manager(db)
        
        budget = await manager.create_workspace_budget(
            workspace_id=workspace_id,
            monthly_budget_usd=request.monthly_budget_usd,
            alert_threshold_percent=request.alert_threshold_percent,
            alert_emails=request.alert_emails,
            hard_limit=request.hard_limit,
        )
        
        return BudgetResponse(
            id=budget.id,
            workspace_id=budget.workspace_id,
            monthly_budget_usd=budget.monthly_budget_usd,
            current_month_spent=budget.current_month_spent,
            budget_remaining=budget.budget_remaining,
            budget_used_percent=budget.budget_used_percent,
            is_over_budget=budget.is_over_budget,
            alert_threshold_percent=budget.alert_threshold_percent,
            alert_emails=budget.alert_emails,
            hard_limit=budget.hard_limit,
            is_enabled=budget.is_enabled,
        )
        
    except Exception as e:
        logger.error(f"Error creating workspace budget: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create budget: {str(e)}")


@router.get("/workspaces/{workspace_id}/budget/status")
async def check_budget_status(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check budget status and alert conditions.
    
    - **workspace_id**: Workspace identifier
    """
    try:
        manager = get_budget_manager(db)
        status = await manager.check_and_alert(workspace_id)
        return status
        
    except Exception as e:
        logger.error(f"Error checking budget status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check budget: {str(e)}")


# Project Budget
@router.post("/projects/{project_id}/budget", response_model=Dict)
async def create_project_budget(
    project_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    request: ProjectBudgetCreateRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update project budget.
    
    - **project_id**: Project identifier
    - **workspace_id**: Workspace identifier
    - **request**: Budget configuration
    """
    try:
        manager = get_budget_manager(db)
        
        budget = await manager.create_project_budget(
            project_id=project_id,
            workspace_id=workspace_id,
            monthly_budget_usd=request.monthly_budget_usd,
        )
        
        return {
            "id": budget.id,
            "project_id": budget.project_id,
            "workspace_id": budget.workspace_id,
            "monthly_budget_usd": budget.monthly_budget_usd,
            "current_month_spent": budget.current_month_spent,
            "budget_remaining": budget.budget_remaining,
            "budget_used_percent": budget.budget_used_percent,
            "is_enabled": budget.is_enabled,
        }
        
    except Exception as e:
        logger.error(f"Error creating project budget: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project budget: {str(e)}")


# Cost Optimization
@router.get("/workspaces/{workspace_id}/cost-optimization", response_model=List[RecommendationResponse])
async def get_cost_recommendations(
    workspace_id: str,
    period: str = Query(default="month", regex="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cost optimization recommendations for a workspace.
    
    - **workspace_id**: Workspace identifier
    - **period**: Analysis period (day, week, month)
    
    Returns actionable recommendations for:
    - Model selection optimization
    - Token usage reduction
    - Resource efficiency improvements
    - Execution pattern optimization
    """
    try:
        optimizer = get_cost_optimizer(db)
        recommendations = await optimizer.get_recommendations(workspace_id, period)
        
        return [RecommendationResponse(**rec) for rec in recommendations]
        
    except Exception as e:
        logger.error(f"Error getting cost recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/workspaces/{workspace_id}/cost-forecast")
async def get_cost_forecast(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get cost forecast for end of month.
    
    - **workspace_id**: Workspace identifier
    """
    try:
        optimizer = get_cost_optimizer(db)
        forecast = await optimizer.forecast_monthly_cost(workspace_id)
        return forecast
        
    except Exception as e:
        logger.error(f"Error getting cost forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get forecast: {str(e)}")


# Statistics
@router.get("/workspaces/{workspace_id}/cost-stats")
async def get_cost_statistics(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive cost statistics for a workspace.
    
    - **workspace_id**: Workspace identifier
    """
    try:
        llm_tracker = get_llm_tracker(db)
        compute_tracker = get_compute_tracker(db)
        optimizer = get_cost_optimizer(db)
        manager = get_budget_manager(db)
        
        # Get current costs
        llm_costs_month = await llm_tracker.get_workspace_costs(workspace_id, "month")
        compute_costs_month = await compute_tracker.get_workspace_usage(workspace_id, "month")
        
        # Get budget
        budget = await manager.get_workspace_budget(workspace_id)
        if budget:
            await manager.update_workspace_spending(workspace_id)
        
        # Get forecast
        forecast = await optimizer.forecast_monthly_cost(workspace_id)
        
        # Get recommendations
        recommendations = await optimizer.get_recommendations(workspace_id, "month")
        
        return {
            "current_month": {
                "llm_cost": llm_costs_month["total_cost"],
                "compute_cost": compute_costs_month["total_cost"],
                "total_cost": llm_costs_month["total_cost"] + compute_costs_month["total_cost"],
            },
            "budget": {
                "has_budget": budget is not None,
                "budget_usd": budget.monthly_budget_usd if budget else None,
                "spent": budget.current_month_spent if budget else None,
                "remaining": budget.budget_remaining if budget else None,
                "usage_percent": budget.budget_used_percent if budget else None,
            } if budget else None,
            "forecast": forecast,
            "recommendations_count": len(recommendations),
            "top_recommendations": recommendations[:3] if recommendations else [],
        }
        
    except Exception as e:
        logger.error(f"Error getting cost statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")
