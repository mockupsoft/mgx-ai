# -*- coding: utf-8 -*-
"""Metrics Router

REST API endpoints for metrics retrieval and aggregation.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from backend.db.models import MetricSnapshot
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import MetricListResponse, MetricResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/", response_model=MetricListResponse)
async def list_metrics(
    task_id: Optional[str] = Query(None),
    task_run_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None, description="Filter by project ID (within active workspace)"),
    name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> MetricListResponse:
    """List metrics in the active workspace with pagination and filtering."""

    session = ctx.session

    logger.info(
        "Listing metrics (workspace_id=%s, task_id=%s, task_run_id=%s)",
        ctx.workspace.id,
        task_id,
        task_run_id,
    )

    query = select(MetricSnapshot).where(MetricSnapshot.workspace_id == ctx.workspace.id)

    if project_id:
        query = query.where(MetricSnapshot.project_id == project_id)

    if task_id:
        query = query.where(MetricSnapshot.task_id == task_id)

    if task_run_id:
        query = query.where(MetricSnapshot.task_run_id == task_run_id)

    if name:
        query = query.where(MetricSnapshot.name.ilike(f"%{name}%"))

    count_query = select(func.count()).select_from(MetricSnapshot).where(MetricSnapshot.workspace_id == ctx.workspace.id)
    if project_id:
        count_query = count_query.where(MetricSnapshot.project_id == project_id)
    if task_id:
        count_query = count_query.where(MetricSnapshot.task_id == task_id)
    if task_run_id:
        count_query = count_query.where(MetricSnapshot.task_run_id == task_run_id)
    if name:
        count_query = count_query.where(MetricSnapshot.name.ilike(f"%{name}%"))

    total = (await session.execute(count_query)).scalar_one()

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
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> MetricResponse:
    """Get a specific metric in the active workspace."""

    session = ctx.session

    logger.info("Getting metric (workspace_id=%s): %s", ctx.workspace.id, metric_id)

    result = await session.execute(
        select(MetricSnapshot).where(
            MetricSnapshot.id == metric_id,
            MetricSnapshot.workspace_id == ctx.workspace.id,
        )
    )
    metric = result.scalar_one_or_none()

    if metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    return MetricResponse.model_validate(metric)


@router.get("/task/{task_id}/summary")
async def get_task_metrics_summary(
    task_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Get metrics summary for a task in the active workspace."""

    session = ctx.session

    logger.info("Getting metrics summary (workspace_id=%s) for task: %s", ctx.workspace.id, task_id)

    result = await session.execute(
        select(MetricSnapshot).where(
            MetricSnapshot.workspace_id == ctx.workspace.id,
            MetricSnapshot.task_id == task_id,
        )
    )
    metrics = result.scalars().all()

    if not metrics:
        return {"task_id": task_id, "metric_count": 0, "metrics": []}

    metrics_by_name: dict[str, list[float]] = {}
    for metric in metrics:
        metrics_by_name.setdefault(metric.name, []).append(metric.value)

    summary = {"task_id": task_id, "metric_count": len(metrics), "metrics": {}}

    for metric_name, values in metrics_by_name.items():
        summary["metrics"][metric_name] = {
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
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Get metrics summary for a run in the active workspace."""

    session = ctx.session

    logger.info("Getting metrics summary (workspace_id=%s) for run: %s", ctx.workspace.id, run_id)

    result = await session.execute(
        select(MetricSnapshot).where(
            MetricSnapshot.workspace_id == ctx.workspace.id,
            MetricSnapshot.task_run_id == run_id,
        )
    )
    metrics = result.scalars().all()

    if not metrics:
        return {"run_id": run_id, "metric_count": 0, "metrics": []}

    metrics_by_name: dict[str, list[dict]] = {}
    for metric in metrics:
        metrics_by_name.setdefault(metric.name, []).append(
            {"value": metric.value, "unit": metric.unit, "timestamp": metric.timestamp}
        )

    return {"run_id": run_id, "metric_count": len(metrics), "metrics": metrics_by_name}


__all__ = ["router"]
