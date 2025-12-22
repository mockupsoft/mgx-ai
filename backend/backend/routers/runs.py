# -*- coding: utf-8 -*-
"""Runs Router

REST API endpoints for task run management.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.db.models import Project, Task, TaskRun
from backend.db.models.enums import RunStatus
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import RunApprovalRequest, RunCreate, RunListResponse, RunResponse
from backend.services import get_task_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/", response_model=RunListResponse)
async def list_runs(
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RunListResponse:
    """List runs in the active workspace with pagination and filtering."""

    session = ctx.session

    logger.info(
        "Listing runs (workspace_id=%s, task_id=%s, status=%s)",
        ctx.workspace.id,
        task_id,
        status,
    )

    query = (
        select(TaskRun)
        .where(TaskRun.workspace_id == ctx.workspace.id)
        .options(selectinload(TaskRun.workspace), selectinload(TaskRun.project))
    )

    if task_id:
        query = query.where(TaskRun.task_id == task_id)

    if status:
        try:
            status_enum = RunStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query = query.where(TaskRun.status == status_enum)

    count_query = select(func.count()).select_from(TaskRun).where(TaskRun.workspace_id == ctx.workspace.id)
    if task_id:
        count_query = count_query.where(TaskRun.task_id == task_id)
    if status:
        count_query = count_query.where(TaskRun.status == status_enum)

    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(query.offset(skip).limit(limit))
    runs = result.scalars().all()

    return RunListResponse(
        items=[RunResponse.model_validate(run) for run in runs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=RunResponse, status_code=201)
async def create_run(
    run_create: RunCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RunResponse:
    """Create a new run for a task in the active workspace."""

    session = ctx.session

    logger.info("Creating run (workspace_id=%s) for task: %s", ctx.workspace.id, run_create.task_id)

    task_result = await session.execute(
        select(Task).where(Task.id == run_create.task_id, Task.workspace_id == ctx.workspace.id)
    )
    db_task = task_result.scalar_one_or_none()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    run_count = (
        await session.execute(select(func.count()).select_from(TaskRun).where(TaskRun.task_id == run_create.task_id))
    ).scalar_one()

    project_result = await session.execute(
        select(Project).where(Project.id == db_task.project_id, Project.workspace_id == db_task.workspace_id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=500, detail="Task project not found")

    db_run = TaskRun(
        task_id=db_task.id,
        workspace_id=db_task.workspace_id,
        project_id=db_task.project_id,
        run_number=run_count + 1,
        status=RunStatus.PENDING,
    )

    db_run.task = db_task
    db_run.workspace = ctx.workspace
    db_run.project = project

    session.add(db_run)
    await session.flush()

    db_task.total_runs = run_count + 1
    await session.flush()

    logger.info("Run created: %s", db_run.id)

    executor = get_task_executor()
    asyncio.create_task(
        executor.execute_task(
            task_id=db_task.id,
            run_id=db_run.id,
            task_description=db_task.description or db_task.name,
            max_rounds=db_task.max_rounds,
        )
    )

    return RunResponse.model_validate(db_run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RunResponse:
    """Get a specific run in the active workspace."""

    session = ctx.session

    logger.info("Getting run (workspace_id=%s): %s", ctx.workspace.id, run_id)

    result = await session.execute(
        select(TaskRun)
        .where(TaskRun.id == run_id, TaskRun.workspace_id == ctx.workspace.id)
        .options(selectinload(TaskRun.workspace), selectinload(TaskRun.project))
    )
    db_run = result.scalar_one_or_none()

    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse.model_validate(db_run)


@router.put("/{run_id}", response_model=RunResponse)
async def replace_run(
    run_id: str,
    status: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RunResponse:
    """Update a run's status in the active workspace (PUT alias)."""

    return await update_run(run_id=run_id, status=status, ctx=ctx)


@router.patch("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: str,
    status: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RunResponse:
    """Update a run's status in the active workspace."""

    session = ctx.session

    logger.info("Updating run (workspace_id=%s): %s", ctx.workspace.id, run_id)

    result = await session.execute(
        select(TaskRun)
        .where(TaskRun.id == run_id, TaskRun.workspace_id == ctx.workspace.id)
        .options(selectinload(TaskRun.workspace), selectinload(TaskRun.project))
    )
    db_run = result.scalar_one_or_none()

    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if status:
        try:
            status_enum = RunStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        db_run.status = status_enum
        await session.flush()

    logger.info("Run updated: %s", run_id)
    return RunResponse.model_validate(db_run)


@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Delete a run in the active workspace."""

    session = ctx.session

    logger.info("Deleting run (workspace_id=%s): %s", ctx.workspace.id, run_id)

    result = await session.execute(select(TaskRun).where(TaskRun.id == run_id, TaskRun.workspace_id == ctx.workspace.id))
    db_run = result.scalar_one_or_none()

    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    await session.delete(db_run)

    logger.info("Run deleted: %s", run_id)
    return {"status": "deleted", "run_id": run_id}


@router.post("/{run_id}/approve", response_model=RunResponse)
async def approve_plan(
    run_id: str,
    approval: RunApprovalRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RunResponse:
    """Approve or reject a plan for a run in the active workspace."""

    session = ctx.session

    logger.info(
        "Processing plan approval (workspace_id=%s, run_id=%s, approved=%s)",
        ctx.workspace.id,
        run_id,
        approval.approved,
    )

    result = await session.execute(
        select(TaskRun)
        .where(TaskRun.id == run_id, TaskRun.workspace_id == ctx.workspace.id)
        .options(selectinload(TaskRun.workspace), selectinload(TaskRun.project))
    )
    db_run = result.scalar_one_or_none()

    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    executor = get_task_executor()
    await executor.approve_plan(run_id, approved=approval.approved)

    logger.info("Approval decision submitted for run: %s", run_id)
    return RunResponse.model_validate(db_run)


@router.get("/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Get logs for a run in the active workspace."""

    session = ctx.session

    logger.info("Getting logs (workspace_id=%s) for run: %s", ctx.workspace.id, run_id)

    result = await session.execute(select(TaskRun).where(TaskRun.id == run_id, TaskRun.workspace_id == ctx.workspace.id))
    db_run = result.scalar_one_or_none()

    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "run_id": run_id,
        "logs": "Logs would be retrieved here",
    }


__all__ = ["router"]
