# -*- coding: utf-8 -*-
"""
Sandbox execution API router.

Provides endpoints for:
- Executing code in secure sandboxes
- Managing executions
- Streaming logs via WebSocket
- Retrieving execution history and metrics
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc

from backend.db.session import get_async_session
from backend.db.models.entities import SandboxExecution, Workspace, Project
from backend.schemas import (
    ExecutionRequest,
    ExecutionResult,
    SandboxExecutionResponse,
    SandboxExecutionListResponse,
    SandboxExecutionLogsEvent,
    SandboxExecutionStartedEvent,
    SandboxExecutionCompletedEvent,
    SandboxExecutionFailedEvent,
    EventTypeEnum,
)
from backend.services.events import get_event_broadcaster
from backend.services.sandbox import SandboxRunner, SandboxRunnerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

# Global sandbox runner instance
_sandbox_runner: Optional[SandboxRunner] = None

# Active WebSocket connections
_active_connections: Dict[str, WebSocket] = {}


def get_sandbox_runner() -> SandboxRunner:
    """Get global sandbox runner instance."""
    global _sandbox_runner
    if _sandbox_runner is None:
        _sandbox_runner = SandboxRunner()
    return _sandbox_runner


@router.post("/execute", response_model=ExecutionResult)
async def execute_code(
    execution_request: ExecutionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    workspace_id: str = "default-workspace",  # TODO: Get from auth context
    project_id: str = "default-project",  # TODO: Get from auth context
    runner: SandboxRunner = Depends(get_sandbox_runner),
):
    """
    Execute code in a secure sandbox environment.
    
    This endpoint:
    1. Creates a sandbox execution record
    2. Spawns a Docker container with security hardening
    3. Runs the specified command in the container
    4. Captures output, errors, and resource usage
    5. Returns execution results
    
    Args:
        execution_request: Code execution request with language, command, and options
        background_tasks: Background task handler
        session: Database session
        workspace_id: Workspace ID (from auth context)
        project_id: Project ID (from auth context)
        runner: Sandbox runner instance
    
    Returns:
        ExecutionResult with success status, output, and metrics
    """
    execution_id = str(uuid4())
    
    logger.info(f"Starting sandbox execution {execution_id} for {execution_request.language}")
    
    # Validate workspace and project exist
    workspace = await session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    try:
        # Create sandbox execution record
        sandbox_execution = SandboxExecution(
            id=execution_id,
            workspace_id=workspace_id,
            project_id=project_id,
            execution_type=execution_request.language.value,
            status="pending",
            command=execution_request.command,
            code=execution_request.code,
            timeout_seconds=execution_request.timeout,
        )
        
        session.add(sandbox_execution)
        await session.commit()
        
        # Emit execution started event
        broadcaster = get_event_broadcaster()
        start_event = SandboxExecutionStartedEvent(
            execution_id=execution_id,
            workspace_id=workspace_id,
            project_id=project_id,
            execution_type=execution_request.language,
            command=execution_request.command,
            timeout_seconds=execution_request.timeout,
        )
        
        await broadcaster.publish(
            event=EventPayload(
                event_type=EventTypeEnum.SANDBOX_EXECUTION_STARTED,
                payload=start_event.dict(),
                source="sandbox_api",
            )
        )
        
        # Execute code in sandbox (background task)
        background_tasks.add_task(
            _execute_code_background,
            execution_id=execution_id,
            request=execution_request,
            session=session,
            runner=runner,
            broadcaster=broadcaster,
        )
        
        # Return immediate response while execution runs in background
        return ExecutionResult(
            success=False,  # Will be updated when execution completes
            stdout="",
            stderr="",
            exit_code=None,
            duration_ms=None,
            resource_usage={},
            error_message="Execution started in background",
        )
        
    except Exception as e:
        logger.error(f"Failed to start execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start execution: {str(e)}")


async def _execute_code_background(
    execution_id: str,
    request: ExecutionRequest,
    session: AsyncSession,
    runner: SandboxRunner,
    broadcaster: Any,
):
    """Background task for executing code in sandbox."""
    
    try:
        # Update status to running
        sandbox_execution = await session.get(SandboxExecution, execution_id)
        if sandbox_execution:
            sandbox_execution.status = "running"
            await session.commit()
        
        # Execute code
        result = await runner.execute_code(
            execution_id=execution_id,
            code=request.code,
            command=request.command,
            language=request.language.value,
            timeout=request.timeout,
            memory_limit_mb=request.memory_limit_mb,
            workspace_id=sandbox_execution.workspace_id if sandbox_execution else None,
            project_id=sandbox_execution.project_id if sandbox_execution else None,
        )
        
        # Update execution record with results
        if sandbox_execution:
            sandbox_execution.status = "completed" if result["success"] else "failed"
            sandbox_execution.stdout = result.get("stdout", "")
            sandbox_execution.stderr = result.get("stderr", "")
            sandbox_execution.exit_code = result.get("exit_code")
            sandbox_execution.success = result["success"]
            sandbox_execution.duration_ms = result.get("duration_ms")
            sandbox_execution.max_memory_mb = result.get("resource_usage", {}).get("max_memory_mb")
            sandbox_execution.cpu_percent = result.get("resource_usage", {}).get("cpu_percent")
            sandbox_execution.network_io = result.get("resource_usage", {}).get("network_io")
            sandbox_execution.disk_io = result.get("resource_usage", {}).get("disk_io")
            sandbox_execution.error_type = result.get("error_type")
            sandbox_execution.error_message = result.get("error_message")
            sandbox_execution.container_id = result.get("container_id")
            
            await session.commit()
            
            # Emit completion event
            if result["success"]:
                completion_event = SandboxExecutionCompletedEvent(
                    execution_id=execution_id,
                    success=result["success"],
                    duration_ms=result.get("duration_ms", 0),
                    exit_code=result.get("exit_code"),
                    resource_usage=result.get("resource_usage", {}),
                    error_type=result.get("error_type"),
                    error_message=result.get("error_message"),
                )
                
                await broadcaster.publish(
                    event=EventPayload(
                        event_type=EventTypeEnum.SANDBOX_EXECUTION_COMPLETED,
                        payload=completion_event.dict(),
                        source="sandbox_api",
                    )
                )
            else:
                failure_event = SandboxExecutionFailedEvent(
                    execution_id=execution_id,
                    error_type=result.get("error_type", "UnknownError"),
                    error_message=result.get("error_message", "Execution failed"),
                    duration_ms=result.get("duration_ms", 0),
                )
                
                await broadcaster.publish(
                    event=EventPayload(
                        event_type=EventTypeEnum.SANDBOX_EXECUTION_FAILED,
                        payload=failure_event.dict(),
                        source="sandbox_api",
                    )
                )
        
        # Broadcast logs if available
        if result.get("stdout") or result.get("stderr"):
            logs_event = SandboxExecutionLogsEvent(
                execution_id=execution_id,
                logs=f"STDOUT:\n{result.get('stdout', '')}\n\nSTDERR:\n{result.get('stderr', '')}",
                timestamp=datetime.utcnow(),
            )
            
            await broadcaster.publish(
                event=EventPayload(
                    event_type=EventTypeEnum.SANDBOX_EXECUTION_LOGS,
                    payload=logs_event.dict(),
                    source="sandbox_api",
                )
            )
            
    except Exception as e:
        logger.error(f"Background execution failed for {execution_id}: {e}")
        
        # Update execution record with error
        sandbox_execution = await session.get(SandboxExecution, execution_id)
        if sandbox_execution:
            sandbox_execution.status = "failed"
            sandbox_execution.error_type = type(e).__name__
            sandbox_execution.error_message = str(e)
            await session.commit()
        
        # Emit failure event
        failure_event = SandboxExecutionFailedEvent(
            execution_id=execution_id,
            error_type=type(e).__name__,
            error_message=str(e),
            duration_ms=0,
        )
        
        try:
            await broadcaster.publish(
                event=EventPayload(
                    event_type=EventTypeEnum.SANDBOX_EXECUTION_FAILED,
                    payload=failure_event.dict(),
                    source="sandbox_api",
                )
            )
        except Exception as broadcast_error:
            logger.error(f"Failed to broadcast failure event: {broadcast_error}")


@router.get("/executions/{execution_id}", response_model=SandboxExecutionResponse)
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get details of a specific sandbox execution.
    
    Args:
        execution_id: Execution identifier
        session: Database session
    
    Returns:
        Sandbox execution details
    """
    execution = await session.get(SandboxExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    return SandboxExecutionResponse.from_orm(execution)


@router.get("/executions", response_model=SandboxExecutionListResponse)
async def list_executions(
    offset: int = 0,
    limit: int = 50,
    workspace_id: str = "default-workspace",  # TODO: Get from auth context
    project_id: Optional[str] = None,  # TODO: Get from auth context
    status: Optional[str] = None,
    execution_type: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    List sandbox executions with filtering and pagination.
    
    Args:
        offset: Pagination offset
        limit: Maximum results per page
        workspace_id: Workspace ID filter
        project_id: Project ID filter (optional)
        status: Status filter (optional)
        execution_type: Language filter (optional)
        session: Database session
    
    Returns:
        Paginated list of executions
    """
    query = select(SandboxExecution).where(
        SandboxExecution.workspace_id == workspace_id
    )
    
    # Apply filters
    if project_id:
        query = query.where(SandboxExecution.project_id == project_id)
    
    if status:
        query = query.where(SandboxExecution.status == status)
    
    if execution_type:
        query = query.where(SandboxExecution.execution_type == execution_type)
    
    # Add ordering and pagination
    query = query.order_by(desc(SandboxExecution.created_at)).offset(offset).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    executions = result.scalars().all()
    
    # Get total count for pagination
    count_query = select(SandboxExecution).where(
        SandboxExecution.workspace_id == workspace_id
    )
    
    if project_id:
        count_query = count_query.where(SandboxExecution.project_id == project_id)
    if status:
        count_query = count_query.where(SandboxExecution.status == status)
    if execution_type:
        count_query = count_query.where(SandboxExecution.execution_type == execution_type)
    
    count_result = await session.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Convert to response format
    execution_responses = [
        SandboxExecutionResponse.from_orm(exec) for exec in executions
    ]
    
    return SandboxExecutionListResponse(
        executions=execution_responses,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.delete("/executions/{execution_id}")
async def stop_execution(
    execution_id: str,
    runner: SandboxRunner = Depends(get_sandbox_runner),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stop a running sandbox execution.
    
    Args:
        execution_id: Execution identifier
        runner: Sandbox runner instance
        session: Database session
    
    Returns:
        Success status
    """
    # Stop the execution
    success = await runner.stop_execution(execution_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found or not running")
    
    # Update status in database
    execution = await session.get(SandboxExecution, execution_id)
    if execution:
        execution.status = "cancelled"
        await session.commit()
    
    return {"status": "stopped", "execution_id": execution_id}


@router.websocket("/executions/{execution_id}/logs")
async def websocket_execution_logs(
    execution_id: str,
    websocket: WebSocket,
):
    """
    WebSocket endpoint for streaming execution logs.
    
    Args:
        execution_id: Execution identifier
        websocket: WebSocket connection
    """
    await websocket.accept()
    _active_connections[execution_id] = websocket
    
    try:
        # Keep connection alive and stream logs
        while True:
            # Get logs from runner
            runner = get_sandbox_runner()
            logs = await runner.get_execution_logs(execution_id)
            
            if logs:
                await websocket.send_text(logs)
            
            # Wait before next update
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error for execution {execution_id}: {e}")
        await websocket.close()
    finally:
        # Clean up connection
        if execution_id in _active_connections:
            del _active_connections[execution_id]


@router.get("/metrics")
async def get_execution_metrics(
    workspace_id: str = "default-workspace",  # TODO: Get from auth context
    project_id: Optional[str] = None,  # TODO: Get from auth context
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get execution metrics and statistics.
    
    Args:
        workspace_id: Workspace ID
        project_id: Project ID (optional)
        session: Database session
    
    Returns:
        Execution metrics and statistics
    """
    # Build base query
    query = select(SandboxExecution).where(
        SandboxExecution.workspace_id == workspace_id
    )
    
    if project_id:
        query = query.where(SandboxExecution.project_id == project_id)
    
    # Get all executions
    result = await session.execute(query)
    executions = result.scalars().all()
    
    if not executions:
        return {
            "total_executions": 0,
            "success_rate": 0.0,
            "avg_duration_ms": 0,
            "avg_memory_mb": 0,
            "language_breakdown": {},
            "status_breakdown": {},
        }
    
    # Calculate metrics
    total_executions = len(executions)
    successful_executions = len([e for e in executions if e.success])
    success_rate = successful_executions / total_executions if total_executions > 0 else 0.0
    
    # Duration stats (only for completed executions)
    completed_executions = [e for e in executions if e.duration_ms]
    avg_duration_ms = sum(e.duration_ms for e in completed_executions) / len(completed_executions) if completed_executions else 0
    
    # Memory stats
    memory_executions = [e for e in executions if e.max_memory_mb]
    avg_memory_mb = sum(e.max_memory_mb for e in memory_executions) / len(memory_executions) if memory_executions else 0
    
    # Language breakdown
    language_counts = {}
    for execution in executions:
        lang = execution.execution_type
        language_counts[lang] = language_counts.get(lang, 0) + 1
    
    # Status breakdown
    status_counts = {}
    for execution in executions:
        status = execution.status
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "total_executions": total_executions,
        "success_rate": round(success_rate, 3),
        "avg_duration_ms": round(avg_duration_ms, 2),
        "avg_memory_mb": round(avg_memory_mb, 2),
        "language_breakdown": language_counts,
        "status_breakdown": status_counts,
    }