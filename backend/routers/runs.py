# -*- coding: utf-8 -*-
"""
Runs Router

REST API endpoints for task run management with database integration.
Handles run creation, status tracking, and plan approval flow.
"""

import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.session import get_session
from backend.db.models import Task, TaskRun
from backend.db.models.enums import RunStatus, TaskStatus
from backend.schemas import RunCreate, RunApprovalRequest, RunResponse, RunListResponse
from backend.services import get_task_executor, get_event_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/", response_model=RunListResponse)
async def list_runs(
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> RunListResponse:
    """
    List task runs with pagination and filtering.
    
    Args:
        task_id: Filter by task ID
        status: Filter by run status
        skip: Number of runs to skip
        limit: Maximum number of runs to return
        session: Database session
    
    Returns:
        List of runs with pagination info
    """
    logger.info(f"Listing runs (task_id={task_id}, status={status})")
    
    # Build query
    query = select(TaskRun)
    
    if task_id:
        query = query.where(TaskRun.task_id == task_id)
    
    if status:
        try:
            status_enum = RunStatus(status)
            query = query.where(TaskRun.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}"
            )
    
    # Get total count
    count_query = select(func.count()).select_from(TaskRun)
    if task_id:
        count_query = count_query.where(TaskRun.task_id == task_id)
    if status:
        count_query = count_query.where(TaskRun.status == status_enum)
    total = (await session.execute(count_query)).scalar_one()
    
    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
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
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """
    Create a new run for a task.
    
    Args:
        run_create: Run creation request with task_id
        session: Database session
    
    Returns:
        Created run object
    """
    logger.info(f"Creating run for task: {run_create.task_id}")
    
    # Verify task exists
    task_result = await session.execute(
        select(Task).where(Task.id == run_create.task_id)
    )
    db_task = task_result.scalar_one_or_none()
    
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get next run number
    run_count = (await session.execute(
        select(func.count()).select_from(TaskRun)
        .where(TaskRun.task_id == run_create.task_id)
    )).scalar_one()
    
    # Create new run
    db_run = TaskRun(
        task_id=run_create.task_id,
        run_number=run_count + 1,
        status=RunStatus.PENDING,
    )
    
    session.add(db_run)
    await session.flush()
    
    # Update task's total_runs count
    db_task.total_runs = run_count + 1
    await session.flush()
    
    logger.info(f"Run created: {db_run.id}")
    
    # Trigger background execution
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
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """
    Get a specific run.
    
    Args:
        run_id: Run ID
        session: Database session
    
    Returns:
        Run object or 404 if not found
    """
    logger.info(f"Getting run: {run_id}")
    
    result = await session.execute(
        select(TaskRun).where(TaskRun.id == run_id)
    )
    db_run = result.scalar_one_or_none()
    
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return RunResponse.model_validate(db_run)


@router.patch("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: str,
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """
    Update a run's status.
    
    Args:
        run_id: Run ID
        status: New status
        session: Database session
    
    Returns:
        Updated run object or 404 if not found
    """
    logger.info(f"Updating run: {run_id}")
    
    result = await session.execute(
        select(TaskRun).where(TaskRun.id == run_id)
    )
    db_run = result.scalar_one_or_none()
    
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if status:
        try:
            status_enum = RunStatus(status)
            db_run.status = status_enum
            await session.flush()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}"
            )
    
    logger.info(f"Run updated: {run_id}")
    return RunResponse.model_validate(db_run)


@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Delete a run.
    
    Args:
        run_id: Run ID
        session: Database session
    
    Returns:
        Deletion status or 404 if not found
    """
    logger.info(f"Deleting run: {run_id}")
    
    result = await session.execute(
        select(TaskRun).where(TaskRun.id == run_id)
    )
    db_run = result.scalar_one_or_none()
    
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    await session.delete(db_run)
    
    logger.info(f"Run deleted: {run_id}")
    return {"status": "deleted", "run_id": run_id}


@router.post("/{run_id}/approve", response_model=RunResponse)
async def approve_plan(
    run_id: str,
    approval: RunApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """
    Approve or reject a plan for a run.
    
    This endpoint handles the plan approval flow:
    1. Client receives plan_ready event
    2. User reviews the plan
    3. Client sends approval/rejection
    4. Executor continues or stops execution
    
    Args:
        run_id: Run ID
        approval: Approval decision (approved=True/False)
        session: Database session
    
    Returns:
        Updated run object
    """
    logger.info(f"Processing plan approval for run: {run_id} (approved={approval.approved})")
    
    result = await session.execute(
        select(TaskRun).where(TaskRun.id == run_id)
    )
    db_run = result.scalar_one_or_none()
    
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Notify executor of approval decision
    executor = get_task_executor()
    await executor.approve_plan(run_id, approved=approval.approved)
    
    logger.info(f"Approval decision submitted for run: {run_id}")
    return RunResponse.model_validate(db_run)


@router.get("/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get logs for a run.
    
    Args:
        run_id: Run ID
        session: Database session
    
    Returns:
        Run logs or 404 if not found
    """
    logger.info(f"Getting logs for run: {run_id}")
    
    result = await session.execute(
        select(TaskRun).where(TaskRun.id == run_id)
    )
    db_run = result.scalar_one_or_none()
    
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return {
        "run_id": run_id,
        "logs": "Logs would be retrieved here",
    }


__all__ = ['router']
