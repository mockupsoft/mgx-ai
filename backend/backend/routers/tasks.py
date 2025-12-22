# -*- coding: utf-8 -*-
"""Tasks Router

REST API endpoints for task management with database integration.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.db.models import Project, Task
from backend.db.models.enums import TaskStatus
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskListResponse:
    """List tasks in the active workspace with pagination and filtering."""

    session = ctx.session

    logger.info(
        "Listing tasks (workspace_id=%s, skip=%s, limit=%s, status=%s)",
        ctx.workspace.id,
        skip,
        limit,
        status,
    )

    query = (
        select(Task)
        .where(Task.workspace_id == ctx.workspace.id)
        .options(selectinload(Task.workspace), selectinload(Task.project))
    )

    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query = query.where(Task.status == status_enum)

    count_query = select(func.count()).select_from(Task).where(Task.workspace_id == ctx.workspace.id)
    if status:
        count_query = count_query.where(Task.status == status_enum)

    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(query.offset(skip).limit(limit))
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[TaskResponse.model_validate(task) for task in tasks],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task: TaskCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskResponse:
    """Create a new task in the active workspace."""

    session = ctx.session

    project_id = task.project_id or ctx.default_project.id

    project_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == ctx.workspace.id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=400, detail="Invalid project_id for active workspace")

    logger.info("Creating task (workspace_id=%s): %s", ctx.workspace.id, task.name)

    db_task = Task(
        workspace_id=ctx.workspace.id,
        project_id=project.id,
        name=task.name,
        description=task.description,
        config=task.config or {},
        status=TaskStatus.PENDING,
        max_rounds=task.max_rounds or 5,
        max_revision_rounds=task.max_revision_rounds or 2,
        memory_size=task.memory_size or 50,
        total_runs=0,
        successful_runs=0,
        failed_runs=0,
    )

    db_task.workspace = ctx.workspace
    db_task.project = project

    session.add(db_task)
    await session.flush()

    logger.info("Task created: %s", db_task.id)
    return TaskResponse.model_validate(db_task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskResponse:
    """Get a task by ID in the active workspace."""

    session = ctx.session

    logger.info("Getting task (workspace_id=%s): %s", ctx.workspace.id, task_id)

    result = await session.execute(
        select(Task)
        .where(Task.id == task_id, Task.workspace_id == ctx.workspace.id)
        .options(selectinload(Task.workspace), selectinload(Task.project))
    )
    db_task = result.scalar_one_or_none()

    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse.model_validate(db_task)


@router.put("/{task_id}", response_model=TaskResponse)
async def replace_task(
    task_id: str,
    task_update: TaskUpdate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskResponse:
    """Update a task in the active workspace (PUT alias)."""

    return await update_task(task_id=task_id, task_update=task_update, ctx=ctx)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskResponse:
    """Update a task in the active workspace."""

    session = ctx.session

    logger.info("Updating task (workspace_id=%s): %s", ctx.workspace.id, task_id)

    result = await session.execute(
        select(Task)
        .where(Task.id == task_id, Task.workspace_id == ctx.workspace.id)
        .options(selectinload(Task.workspace), selectinload(Task.project))
    )
    db_task = result.scalar_one_or_none()

    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)

    await session.flush()

    logger.info("Task updated: %s", task_id)
    return TaskResponse.model_validate(db_task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Delete a task in the active workspace."""

    session = ctx.session

    logger.info("Deleting task (workspace_id=%s): %s", ctx.workspace.id, task_id)

    result = await session.execute(select(Task).where(Task.id == task_id, Task.workspace_id == ctx.workspace.id))
    db_task = result.scalar_one_or_none()

    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    await session.delete(db_task)

    logger.info("Task deleted: %s", task_id)
    return {"status": "deleted", "task_id": task_id}


__all__ = ["router"]
