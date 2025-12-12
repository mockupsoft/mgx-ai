# -*- coding: utf-8 -*-
"""
Metrics Router

REST API endpoints for metrics retrieval and aggregation.
Handles metric queries and analytics.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.session import get_session
from backend.db.models import MetricSnapshot
from backend.schemas import MetricResponse, MetricListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/", response_model=MetricListResponse)
async def list_metrics(
    task_id: Optional[str] = Query(None),
    task_run_id: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> MetricListResponse:
    """
    List metrics with pagination and filtering.
    
    Args:
        task_id: Filter by task ID
        task_run_id: Filter by task run ID
        name: Filter by metric name (partial match)
        skip: Number of metrics to skip
        limit: Maximum number of metrics to return
        session: Database session
    
    Returns:
        List of metrics with pagination info
    """
    logger.info(f"Listing metrics (task_id={task_id}, task_run_id={task_run_id})")
    
    # Build query
    query = select(MetricSnapshot)
    
    if task_id:
        query = query.where(MetricSnapshot.task_id == task_id)
    
    if task_run_id:
        query = query.where(MetricSnapshot.task_run_id == task_run_id)
    
    if name:
        query = query.where(MetricSnapshot.name.ilike(f"%{name}%"))
    
    # Get total count
    count_query = select(func.count()).select_from(MetricSnapshot)
    if task_id:
        count_query = count_query.where(MetricSnapshot.task_id == task_id)
    if task_run_id:
        count_query = count_query.where(MetricSnapshot.task_run_id == task_run_id)
    if name:
        count_query = count_query.where(MetricSnapshot.name.ilike(f"%{name}%"))
    total = (await session.execute(count_query)).scalar_one()
    
    # Get paginated results (ordered by timestamp desc)
    query = query.order_by(MetricSnapshot.timestamp.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    metrics = result.scalars().all()
    
    return MetricListResponse(
        items=[MetricResponse.model_validate(metric) for metric in metrics],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{metric_id}", response_model=MetricResponse)
async def get_metric(
    metric_id: str,
    session: AsyncSession = Depends(get_session),
) -> MetricResponse:
    """
    Get a specific metric.
    
    Args:
        metric_id: Metric ID
        session: Database session
    
    Returns:
        Metric object or 404 if not found
    """
    logger.info(f"Getting metric: {metric_id}")
    
    result = await session.execute(
        select(MetricSnapshot).where(MetricSnapshot.id == metric_id)
    )
    metric = result.scalar_one_or_none()
    
    if metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    return MetricResponse.model_validate(metric)


@router.get("/task/{task_id}/summary")
async def get_task_metrics_summary(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get metrics summary for a task.
    
    Aggregates metrics across all runs for the task.
    
    Args:
        task_id: Task ID
        session: Database session
    
    Returns:
        Aggregated metrics summary
    """
    logger.info(f"Getting metrics summary for task: {task_id}")
    
    result = await session.execute(
        select(MetricSnapshot).where(MetricSnapshot.task_id == task_id)
    )
    metrics = result.scalars().all()
    
    if not metrics:
        return {
            "task_id": task_id,
            "metric_count": 0,
            "metrics": [],
        }
    
    # Group metrics by name and calculate stats
    metrics_by_name = {}
    for metric in metrics:
        if metric.name not in metrics_by_name:
            metrics_by_name[metric.name] = []
        metrics_by_name[metric.name].append(metric.value)
    
    summary = {
        "task_id": task_id,
        "metric_count": len(metrics),
        "metrics": {},
    }
    
    for name, values in metrics_by_name.items():
        summary["metrics"][name] = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "last": values[-1],
        }
    
    return summary


@router.get("/run/{run_id}/summary")
async def get_run_metrics_summary(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get metrics summary for a run.
    
    Args:
        run_id: Run ID
        session: Database session
    
    Returns:
        Run metrics summary
    """
    logger.info(f"Getting metrics summary for run: {run_id}")
    
    result = await session.execute(
        select(MetricSnapshot).where(MetricSnapshot.task_run_id == run_id)
    )
    metrics = result.scalars().all()
    
    if not metrics:
        return {
            "run_id": run_id,
            "metric_count": 0,
            "metrics": [],
        }
    
    # Group metrics by name
    metrics_by_name = {}
    for metric in metrics:
        if metric.name not in metrics_by_name:
            metrics_by_name[metric.name] = []
        metrics_by_name[metric.name].append({
            "value": metric.value,
            "unit": metric.unit,
            "timestamp": metric.timestamp,
        })
    
    return {
        "run_id": run_id,
        "metric_count": len(metrics),
        "metrics": metrics_by_name,
    }


__all__ = ['router']
