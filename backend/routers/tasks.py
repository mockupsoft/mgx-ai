# -*- coding: utf-8 -*-
"""Tasks Router

REST API endpoints for task management with database integration.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text

from backend.db.models import Project, Task, TaskRun
from backend.db.models.enums import TaskStatus
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate, TaskStatusEnum

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def task_to_response(task: Task) -> TaskResponse:
    """Convert Task ORM object to TaskResponse schema manually to avoid async session issues."""
    from datetime import datetime
    
    # Calculate success_rate
    success_rate = 0.0
    if task.total_runs > 0:
        success_rate = (task.successful_runs / task.total_runs) * 100
    
    # Convert status enum to string value
    status_value = task.status.value if hasattr(task.status, 'value') else str(task.status)
    
    # Safely access created_at and updated_at to avoid MissingGreenlet
    created_at = getattr(task, 'created_at', None)
    updated_at = getattr(task, 'updated_at', None)
    if created_at is None:
        created_at = datetime.utcnow()
    if updated_at is None:
        updated_at = datetime.utcnow()
    
    return TaskResponse(
        id=task.id,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        name=task.name,
        description=task.description,
        config=task.config or {},
        status=TaskStatusEnum(status_value),
        max_rounds=task.max_rounds,
        max_revision_rounds=task.max_revision_rounds,
        memory_size=task.memory_size,
        run_branch_prefix=task.run_branch_prefix,
        commit_template=task.commit_template,
        total_runs=task.total_runs,
        successful_runs=task.successful_runs,
        failed_runs=task.failed_runs,
        success_rate=success_rate,
        last_run_at=task.last_run_at,
        last_run_duration=task.last_run_duration,
        last_error=task.last_error,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskListResponse:
    """List tasks in the active workspace with pagination and filtering."""
    try:
        logger.info(
            "[list_tasks] Starting - workspace_id=%s, skip=%s, limit=%s, status=%s",
            ctx.workspace.id,
            skip,
            limit,
            status,
        )

        session = ctx.session

        query = (
            select(Task)
            .where(Task.workspace_id == ctx.workspace.id)
        )

        if status:
            try:
                status_enum = TaskStatus(status)
            except ValueError:
                logger.warning("[list_tasks] Invalid status: %s", status)
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
            query = query.where(Task.status == status_enum)

        count_query = select(func.count()).select_from(Task).where(Task.workspace_id == ctx.workspace.id)
        if status:
            count_query = count_query.where(Task.status == status_enum)

        logger.debug("[list_tasks] Executing count query")
        total = (await session.execute(count_query)).scalar_one()
        logger.debug("[list_tasks] Total tasks: %s", total)

        logger.debug("[list_tasks] Executing tasks query")
        result = await session.execute(query.offset(skip).limit(limit))
        tasks = result.scalars().all()
        logger.debug("[list_tasks] Found %s tasks", len(tasks))

        logger.debug("[list_tasks] Converting tasks to response")
        task_responses = [task_to_response(task) for task in tasks]

        logger.info("[list_tasks] Success - returning %s tasks (total=%s)", len(task_responses), total)
        return TaskListResponse(
            items=task_responses,
            total=total,
            skip=skip,
            limit=limit,
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("[list_tasks] Error: %s", e, exc_info=True)
        raise


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task: TaskCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskResponse:
    """Create a new task in the active workspace."""
    try:
        logger.info(
            "[create_task] Starting - workspace_id=%s, project_id=%s, name=%s",
            ctx.workspace.id,
            task.project_id,
            task.name,
        )

        session = ctx.session

        project_id = task.project_id or ctx.default_project.id
        logger.debug("[create_task] Using project_id: %s", project_id)

        # Use raw SQL to avoid issues with missing columns in database (migration issue)
        logger.debug("[create_task] Fetching project from database")
        project_result = await session.execute(
            text("""
                SELECT id, workspace_id, name, slug, metadata, created_at, updated_at
                FROM projects
                WHERE id = :project_id AND workspace_id = :workspace_id
                LIMIT 1
            """),
            {"project_id": project_id, "workspace_id": ctx.workspace.id}
        )
        row = project_result.first()
        if row is None:
            logger.error("[create_task] Project not found - project_id=%s, workspace_id=%s", project_id, ctx.workspace.id)
            raise HTTPException(status_code=400, detail="Invalid project_id for active workspace")
        
        logger.debug("[create_task] Project found: %s", row[2])
        
        # Manually construct Project object from row data
        project = Project(
            id=row[0],
            workspace_id=row[1],
            name=row[2],
            slug=row[3],
            meta_data=row[4] if row[4] else {},
        )

        logger.debug("[create_task] Creating Task object")
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

        logger.debug("[create_task] Adding task to session")
        session.add(db_task)
        await session.flush()
        await session.commit()  # Explicitly commit the transaction

        logger.info("[create_task] Success - Task created: %s", db_task.id)
        return task_to_response(db_task)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("[create_task] Error: %s", e, exc_info=True)
        raise


@router.get("/{task_id}/files")
async def get_task_files(
    task_id: str,
    run_id: Optional[str] = Query(None, description="Specific run ID to get files for"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> Dict[str, Any]:
    """
    Get files generated for a task.
    
    Looks for files in the output directory associated with the task/run.
    Only returns files from directories created after the task was created.
    """
    from datetime import datetime
    
    session = ctx.session
    
    # Verify task exists and belongs to workspace
    result = await session.execute(
        select(Task).where(Task.id == task_id, Task.workspace_id == ctx.workspace.id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get task creation time
    task_created_at = task.created_at if hasattr(task, 'created_at') and task.created_at else None
    task_updated_at = task.updated_at if hasattr(task, 'updated_at') and task.updated_at else None
    
    # Determine output directory
    # MGXStyleTeam saves files to output/mgx_team_{timestamp}/
    # We'll search for directories created after task creation
    output_base = Path("output")
    files: List[Dict[str, Any]] = []
    
    if output_base.exists():
        # Find all mgx_team_* directories
        mgx_dirs = [
            d for d in output_base.iterdir() 
            if d.is_dir() and d.name.startswith("mgx_team_")
        ]
        
        # Parse timestamp from directory name and filter by task creation time
        target_dir = None
        
        if task_created_at:
            # Convert task_created_at to datetime if it's not already
            if isinstance(task_created_at, str):
                try:
                    task_created_at = datetime.fromisoformat(task_created_at.replace('Z', '+00:00'))
                except:
                    task_created_at = None
            
            if task_created_at:
                # Parse timestamp from directory names (format: mgx_team_YYYYMMDD_HHMMSS)
                valid_dirs = []
                for dir_path in mgx_dirs:
                    try:
                        # Extract timestamp from directory name
                        timestamp_str = dir_path.name.replace("mgx_team_", "")
                        dir_timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        
                        # Only consider directories created after task creation
                        if dir_timestamp >= task_created_at:
                            # If task_updated_at exists, prefer directories created before task update
                            if task_updated_at:
                                if isinstance(task_updated_at, str):
                                    try:
                                        task_updated_at = datetime.fromisoformat(task_updated_at.replace('Z', '+00:00'))
                                    except:
                                        task_updated_at = None
                                
                                if task_updated_at and dir_timestamp <= task_updated_at:
                                    valid_dirs.append((dir_path, dir_timestamp))
                            else:
                                valid_dirs.append((dir_path, dir_timestamp))
                    except (ValueError, AttributeError) as e:
                        # Skip directories with invalid timestamp format
                        logger.debug(f"Skipping directory {dir_path.name}: {e}")
                        continue
                
                # Sort by timestamp (newest first) and select the most recent one
                if valid_dirs:
                    valid_dirs.sort(key=lambda x: x[1], reverse=True)
                    target_dir = valid_dirs[0][0]
        
        # Fallback: if no valid directory found based on timestamp, return empty
        # This prevents showing files from other tasks
        if not target_dir:
            logger.debug(f"No valid output directory found for task {task_id} created at {task_created_at}")
            return {
                "files": [],
                "count": 0,
                "task_id": task_id,
                "run_id": run_id,
            }
        
        # Read all files in the directory
        for file_path in target_dir.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    file_ext = file_path.suffix.lower()
                    
                    file_type = "other"
                    if file_ext in [".html", ".htm"]:
                        file_type = "html"
                    elif file_ext == ".css":
                        file_type = "css"
                    elif file_ext in [".js", ".jsx", ".ts", ".tsx"]:
                        file_type = "js"
                    
                    files.append({
                        "name": file_path.name,
                        "path": str(file_path.relative_to(target_dir)),
                        "content": content,
                        "type": file_type,
                        "size": len(content),
                    })
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")
                    # Still include the file but without content
                    files.append({
                        "name": file_path.name,
                        "path": str(file_path.relative_to(target_dir)),
                        "content": "",
                        "type": "other",
                        "size": 0,
                        "error": str(e),
                    })
    
    return {
        "files": files,
        "count": len(files),
        "task_id": task_id,
        "run_id": run_id,
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> TaskResponse:
    """Get a task by ID in the active workspace."""
    try:
        logger.info("[get_task] Starting - workspace_id=%s, task_id=%s", ctx.workspace.id, task_id)

        session = ctx.session

        logger.debug("[get_task] Executing query")
        result = await session.execute(
            select(Task)
            .where(Task.id == task_id, Task.workspace_id == ctx.workspace.id)
        )
        db_task = result.scalar_one_or_none()

        if db_task is None:
            logger.warning("[get_task] Task not found - task_id=%s, workspace_id=%s", task_id, ctx.workspace.id)
            raise HTTPException(status_code=404, detail="Task not found")

        logger.info("[get_task] Success - Task found: %s", task_id)
        return task_to_response(db_task)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("[get_task] Error: %s", e, exc_info=True)
        raise


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
    try:
        session = ctx.session

        logger.info("Updating task (workspace_id=%s): %s", ctx.workspace.id, task_id)

        result = await session.execute(
            select(Task)
            .where(Task.id == task_id, Task.workspace_id == ctx.workspace.id)
        )
        db_task = result.scalar_one_or_none()

        if db_task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        update_data = task_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_task, field, value)

        # Get created_at and updated_at BEFORE flush to avoid MissingGreenlet
        created_at = db_task.created_at
        updated_at = db_task.updated_at
        
        await session.flush()
        
        # Manually construct response to avoid async session issues
        # Use the values we captured before flush
        from datetime import datetime
        success_rate = 0.0
        if db_task.total_runs > 0:
            success_rate = (db_task.successful_runs / db_task.total_runs) * 100
        
        status_value = db_task.status.value if hasattr(db_task.status, 'value') else str(db_task.status)
        
        response = TaskResponse(
            id=db_task.id,
            workspace_id=db_task.workspace_id,
            project_id=db_task.project_id,
            name=db_task.name,
            description=db_task.description,
            config=db_task.config or {},
            status=TaskStatusEnum(status_value),
            max_rounds=db_task.max_rounds,
            max_revision_rounds=db_task.max_revision_rounds,
            memory_size=db_task.memory_size,
            run_branch_prefix=db_task.run_branch_prefix,
            commit_template=db_task.commit_template,
            total_runs=db_task.total_runs,
            successful_runs=db_task.successful_runs,
            failed_runs=db_task.failed_runs,
            success_rate=success_rate,
            last_run_at=db_task.last_run_at,
            last_run_duration=db_task.last_run_duration,
            last_error=db_task.last_error,
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow(),
        )
        
        await session.commit()  # Explicitly commit the transaction

        logger.info("Task updated: %s", task_id)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[update_task] Error: %s", e, exc_info=True)
        raise


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
