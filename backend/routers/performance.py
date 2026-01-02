# -*- coding: utf-8 -*-
"""Performance monitoring and metrics API endpoints."""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.engine import get_session
from backend.services.cost.llm_tracker import get_llm_tracker
from backend.services.cost.optimizer import get_cost_optimizer
# Lazy import to avoid Pydantic validation errors during module import
# from backend.mgx_agent.performance.profiler import get_active_profiler
from backend.routers.deps import get_workspace_context, WorkspaceContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/metrics")
async def get_performance_metrics(
    period: str = Query("day", regex="^(day|week|month)$"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> Dict:
    """
    Get real-time performance metrics.
    
    Returns:
        Dictionary with performance metrics
    """
    session = ctx.session
    tracker = get_llm_tracker(session)
    
    # Get workspace costs
    costs = await tracker.get_workspace_costs(ctx.workspace.id, period)
    
    # Get token usage patterns
    token_patterns = await tracker.analyze_token_usage_patterns(ctx.workspace.id, period)
    
    # Get active profiler metrics if available (lazy import)
    profiler_metrics = None
    try:
        from backend.mgx_agent.performance.profiler import get_active_profiler
        profiler = get_active_profiler()
        if profiler:
            profiler_metrics = profiler.to_run_metrics()
    except Exception as e:
        logger.debug(f"Profiler not available: {e}")
    
    return {
        "workspace_id": ctx.workspace.id,
        "period": period,
        "costs": costs,
        "token_patterns": token_patterns.get("patterns", {}),
        "anomalies": token_patterns.get("anomalies", []),
        "profiler": profiler_metrics,
    }


@router.get("/benchmarks")
async def get_benchmark_results(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> Dict:
    """
    Get benchmark results.
    
    Returns:
        Dictionary with benchmark results
    """
    from pathlib import Path
    import json
    
    latest_path = Path("perf_reports/latest.json")
    baseline_path = Path("perf_reports/baseline.json")
    
    latest = None
    baseline = None
    
    if latest_path.exists():
        try:
            with open(latest_path, 'r') as f:
                latest = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load latest benchmarks: {e}")
    
    if baseline_path.exists():
        try:
            with open(baseline_path, 'r') as f:
                baseline = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load baseline: {e}")
    
    return {
        "latest": latest,
        "baseline": baseline,
    }


@router.get("/optimizations")
async def get_optimization_recommendations(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> Dict:
    """
    Get optimization recommendations.
    
    Returns:
        Dictionary with optimization recommendations
    """
    session = ctx.session
    optimizer = get_cost_optimizer(session)
    tracker = get_llm_tracker(session)
    
    # Get cost optimization recommendations
    cost_recommendations = await optimizer.get_recommendations(ctx.workspace.id)
    
    # Get token optimization recommendations
    token_recommendations = await tracker.get_token_optimization_recommendations(ctx.workspace.id)
    
    # Get performance bottlenecks from profiler (lazy import)
    bottlenecks = []
    try:
        from backend.mgx_agent.performance.profiler import get_active_profiler
        profiler = get_active_profiler()
        if profiler:
            bottlenecks = profiler.get_performance_bottlenecks()
    except Exception as e:
        logger.debug(f"Profiler not available: {e}")
    
    return {
        "workspace_id": ctx.workspace.id,
        "cost_optimizations": cost_recommendations,
        "token_optimizations": token_recommendations,
        "performance_bottlenecks": bottlenecks,
    }


@router.get("/costs")
async def get_cost_analysis(
    period: str = Query("month", regex="^(day|week|month|all)$"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> Dict:
    """
    Get detailed cost analysis.
    
    Returns:
        Dictionary with cost analysis
    """
    session = ctx.session
    tracker = get_llm_tracker(session)
    optimizer = get_cost_optimizer(session)
    
    # Get workspace costs
    costs = await tracker.get_workspace_costs(ctx.workspace.id, period)
    
    # Get cost forecast
    forecast = await optimizer.forecast_monthly_cost(ctx.workspace.id)
    
    # Get daily costs
    days = 30 if period == "month" else 7 if period == "week" else 1
    daily_costs = await tracker.get_daily_costs(ctx.workspace.id, days)
    
    return {
        "workspace_id": ctx.workspace.id,
        "period": period,
        "summary": costs,
        "daily_breakdown": daily_costs,
        "forecast": forecast,
    }


