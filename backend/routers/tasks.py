# -*- coding: utf-8 -*-
"""
Tasks Router

REST API endpoints for task management with database integration.
Handles CRUD operations and task execution.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.session import get_session
from backend.db.models import Task
from backend.db.models.enums import TaskStatus
from backend.schemas import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from backend.services import get_task_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> TaskListResponse:
    """
    List all tasks with pagination and filtering.
    
    Args:
        skip: Number of tasks to skip
        limit: Maximum number of tasks to return
        status: Filter by task status
        session: Database session
    
    Returns:
        List of tasks with pagination info
    """
    logger.info(f"Listing tasks (skip={skip}, limit={limit}, status={status})")
    
    # Build query
    query = select(Task)
    
    if status:
        try:
            status_enum = TaskStatus(status)
            query = query.where(Task.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}"
            )
    
    # Get total count
    count_query = select(func.count()).select_from(Task)
    if status:
        count_query = count_query.where(Task.status == status_enum)
    total = (await session.execute(count_query)).scalar_one()
    
    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
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
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Create a new task.
    
    Args:
        task: Task creation request
        session: Database session
    
    Returns:
        Created task object
    """
    logger.info(f"Creating task: {task.name}")
    
    db_task = Task(
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
    
    session.add(db_task)
    await session.flush()
    
    logger.info(f"Task created: {db_task.id}")
    return TaskResponse.model_validate(db_task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Get a specific task.
    
    Args:
        task_id: Task ID
        session: Database session
    
    Returns:
        Task object or 404 if not found
    """
    logger.info(f"Getting task: {task_id}")
    
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    db_task = result.scalar_one_or_none()
    
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse.model_validate(db_task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Update a task.
    
    Args:
        task_id: Task ID
        task_update: Task update request
        session: Database session
    
    Returns:
        Updated task object or 404 if not found
    """
    logger.info(f"Updating task: {task_id}")
    
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    db_task = result.scalar_one_or_none()
    
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update fields if provided
    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    await session.flush()
    
    logger.info(f"Task updated: {task_id}")
    return TaskResponse.model_validate(db_task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Delete a task.
    
    Args:
        task_id: Task ID
        session: Database session
    
    Returns:
        Deletion status or 404 if not found
    """
    logger.info(f"Deleting task: {task_id}")
    
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    db_task = result.scalar_one_or_none()
    
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await session.delete(db_task)
    
    logger.info(f"Task deleted: {task_id}")
    return {"status": "deleted", "task_id": task_id}


__all__ = ['router']
