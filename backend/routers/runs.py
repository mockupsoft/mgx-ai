# -*- coding: utf-8 -*-
"""Runs Router

REST API endpoints for task run management.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from backend.db.models import Project, Task, TaskRun
from backend.db.models.enums import RunStatus
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import RunApprovalRequest, RunCreate, RunListResponse, RunResponse, RunStatusEnum, WorkspaceSummary, ProjectSummary
from backend.services import get_task_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def run_to_response(run: TaskRun, workspace=None, project=None) -> RunResponse:
    """Convert TaskRun ORM object to RunResponse schema manually to avoid async session issues."""
    # Convert status enum to string value
    status_value = run.status.value if hasattr(run.status, 'value') else str(run.status)
    
    # Build workspace summary if available
    workspace_summary = None
    if workspace:
        workspace_summary = WorkspaceSummary(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
        )
    elif hasattr(run, 'workspace') and run.workspace:
        workspace_summary = WorkspaceSummary(
            id=run.workspace.id,
            name=run.workspace.name,
            slug=run.workspace.slug,
        )
    
    # Build project summary if available
    project_summary = None
    if project:
        project_summary = ProjectSummary(
            id=project.id,
            workspace_id=project.workspace_id,
            name=project.name,
            slug=project.slug,
        )
    elif hasattr(run, 'project') and run.project:
        project_summary = ProjectSummary(
            id=run.project.id,
            workspace_id=run.project.workspace_id,
            name=run.project.name,
            slug=run.project.slug,
        )
    
    # Get created_at and updated_at safely (may be None for newly created runs)
    from datetime import datetime, timezone
    created_at = getattr(run, 'created_at', None)
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    
    updated_at = getattr(run, 'updated_at', None)
    if updated_at is None:
        updated_at = datetime.now(timezone.utc)
    
    return RunResponse(
        id=run.id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        task_id=run.task_id,
        run_number=run.run_number,
        status=RunStatusEnum(status_value),
        workspace=workspace_summary,
        project=project_summary,
        plan=getattr(run, 'plan', None),
        results=getattr(run, 'results', None),
        started_at=getattr(run, 'started_at', None),
        completed_at=getattr(run, 'completed_at', None),
        duration=getattr(run, 'duration', None),
        error_message=getattr(run, 'error_message', None),
        error_details=getattr(run, 'error_details', None),
        created_at=created_at,
        updated_at=updated_at,
    )


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
        items=[run_to_response(run) for run in runs],
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

    # Use raw SQL to avoid issues with missing columns in database (migration issue)
    from sqlalchemy import text
    project_result = await session.execute(
        text("""
            SELECT id, workspace_id, name, slug, metadata, created_at, updated_at
            FROM projects
            WHERE id = :project_id AND workspace_id = :workspace_id
            LIMIT 1
        """),
        {"project_id": db_task.project_id, "workspace_id": db_task.workspace_id}
    )
    row = project_result.first()
    if row is None:
        raise HTTPException(status_code=500, detail="Task project not found")
    
    # Manually construct Project object from row data
    project = Project(
        id=row[0],
        workspace_id=row[1],
        name=row[2],
        slug=row[3],
        meta_data=row[4] if row[4] else {},
    )

    db_run = TaskRun(
        task_id=db_task.id,
        workspace_id=db_task.workspace_id,
        project_id=db_task.project_id,
        run_number=run_count + 1,
        status=RunStatus.PENDING,
    )

    # Don't assign workspace/project objects to avoid SQLAlchemy trying to INSERT them
    # We only need the IDs which are already set above

    session.add(db_run)
    await session.flush()

    db_task.total_runs = run_count + 1
    await session.flush()

    logger.info("Run created: %s", db_run.id)

    # Get project config for executor
    project_config = {
        "repo_full_name": getattr(project, 'repo_full_name', None),
        "default_branch": getattr(project, 'default_branch', 'main'),
        "run_branch_prefix": db_task.run_branch_prefix or "mgx",
    }
    
    await session.commit()
    
    # After commit, start executor in background (it will create its own session)
    executor = get_task_executor()
    asyncio.create_task(
        executor.execute_task(
            task_id=db_task.id,
            run_id=db_run.id,
            task_description=db_task.description or db_task.name,
            max_rounds=db_task.max_rounds,
            task_name=db_task.name,
            run_number=db_run.run_number,
            project_config=project_config,
            session=None,  # Executor will create its own session
        )
    )

    return run_to_response(db_run, workspace=ctx.workspace, project=project)


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

    return run_to_response(db_run)


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

    await session.commit()

    logger.info("Run updated: %s", run_id)
    return run_to_response(db_run)


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

    # Query TaskRun without eager loading to avoid missing column issues
    result = await session.execute(
        select(TaskRun)
        .where(TaskRun.id == run_id, TaskRun.workspace_id == ctx.workspace.id)
        # Removed selectinload to avoid projects.repo_full_name error
    )
    db_run = result.scalar_one_or_none()

    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get project using raw SQL to avoid missing column issues
    project_result = await session.execute(
        text("""
            SELECT id, workspace_id, name, slug, metadata, created_at, updated_at
            FROM projects
            WHERE id = :project_id AND workspace_id = :workspace_id
            LIMIT 1
        """),
        {"project_id": db_run.project_id, "workspace_id": db_run.workspace_id}
    )
    row = project_result.first()
    if row is None:
        raise HTTPException(status_code=500, detail="Run project not found")
    
    # Manually construct Project object from row data
    project = Project(
        id=row[0],
        workspace_id=row[1],
        name=row[2],
        slug=row[3],
        meta_data=row[4] if row[4] else {},
    )

    executor = get_task_executor()
    await executor.approve_plan(run_id, approved=approval.approved)

    await session.commit()

    logger.info("Approval decision submitted for run: %s", run_id)
    return run_to_response(db_run, workspace=ctx.workspace, project=project)


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
