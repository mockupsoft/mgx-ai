# -*- coding: utf-8 -*-
"""Workflows Router

REST API endpoints for workflow management with database integration.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, and_
from sqlalchemy.orm import selectinload

from backend.db.models import Project, WorkflowDefinition, WorkflowExecution, WorkflowStep, WorkflowVariable, WorkflowStepExecution
from backend.db.models.enums import WorkflowStatus, WorkflowStepStatus, WorkflowStepType
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import (
    WorkflowCreate,
    WorkflowExecutionCreate,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowValidationResult,
    WorkflowStepTypeEnum,
    WorkflowMetricsSummary,
    WorkflowExecutionTimeline,
    WorkflowStepTimelineEntry,
    WorkflowExecutionDetailedResponse,
)
from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    project_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowListResponse:
    """List workflows in the active workspace with pagination and filtering."""

    session = ctx.session

    logger.info(
        "Listing workflows (workspace_id=%s, skip=%s, limit=%s, project_id=%s, is_active=%s)",
        ctx.workspace.id,
        skip,
        limit,
        project_id,
        is_active,
    )

    query = (
        select(WorkflowDefinition)
        .where(WorkflowDefinition.workspace_id == ctx.workspace.id)
        .options(
            selectinload(WorkflowDefinition.steps),
            selectinload(WorkflowDefinition.variables),
            selectinload(WorkflowDefinition.workspace),
            selectinload(WorkflowDefinition.project),
        )
    )

    if project_id:
        query = query.where(WorkflowDefinition.project_id == project_id)

    if is_active is not None:
        query = query.where(WorkflowDefinition.is_active == is_active)

    count_query = select(func.count()).select_from(WorkflowDefinition).where(
        WorkflowDefinition.workspace_id == ctx.workspace.id
    )

    if project_id:
        count_query = count_query.where(WorkflowDefinition.project_id == project_id)

    if is_active is not None:
        count_query = count_query.where(WorkflowDefinition.is_active == is_active)

    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(query.offset(skip).limit(limit))
    workflows = result.scalars().all()

    return WorkflowListResponse(
        items=[WorkflowResponse.model_validate(workflow) for workflow in workflows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    workflow: WorkflowCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowResponse:
    """Create a new workflow in the active workspace."""

    session = ctx.session

    project_id = workflow.project_id or ctx.default_project.id

    project_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == ctx.workspace.id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=400, detail="Invalid project_id for active workspace")

    # Validate workflow definition
    resolver = WorkflowDependencyResolver()
    validation_result = resolver.validate_workflow(workflow)
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Workflow validation failed",
                "errors": [error.model_dump() for error in validation_result.errors],
                "warnings": validation_result.warnings,
            }
        )

    logger.info("Creating workflow (workspace_id=%s): %s", ctx.workspace.id, workflow.name)

    # Check for existing workflow with same name and version
    existing_result = await session.execute(
        select(WorkflowDefinition).where(
            WorkflowDefinition.workspace_id == ctx.workspace.id,
            WorkflowDefinition.project_id == project.id,
            WorkflowDefinition.name == workflow.name,
            WorkflowDefinition.version == 1,  # For now, always use version 1
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail="A workflow with this name already exists in the project"
        )

    db_workflow = WorkflowDefinition(
        workspace_id=ctx.workspace.id,
        project_id=project.id,
        name=workflow.name,
        description=workflow.description,
        version=1,  # For now, always start with version 1
        is_active=True,
        config=workflow.config or {},
        timeout_seconds=workflow.timeout_seconds or 3600,
        max_retries=workflow.max_retries or 3,
        meta_data=workflow.meta_data or {},
    )

    db_workflow.workspace = ctx.workspace
    db_workflow.project = project

    # Add workflow to session first to get ID
    session.add(db_workflow)
    await session.flush()

    # Create workflow variables
    for variable_data in workflow.variables:
        db_variable = WorkflowVariable(
            workflow_id=db_workflow.id,
            name=variable_data.name,
            data_type=variable_data.data_type,
            is_required=variable_data.is_required,
            default_value=variable_data.default_value,
            description=variable_data.description,
            meta_data=variable_data.meta_data or {},
        )
        session.add(db_variable)

    # Create workflow steps
    for step_data in workflow.steps:
        db_step = WorkflowStep(
            workflow_id=db_workflow.id,
            name=step_data.name,
            step_type=WorkflowStepType(step_data.step_type.value),
            step_order=step_data.step_order,
            config=step_data.config or {},
            timeout_seconds=step_data.timeout_seconds,
            max_retries=step_data.max_retries,
            agent_definition_id=step_data.agent_definition_id,
            agent_instance_id=step_data.agent_instance_id,
            depends_on_steps=step_data.depends_on_steps,
            condition_expression=step_data.condition_expression,
            meta_data=step_data.meta_data or {},
        )
        session.add(db_step)

    await session.flush()

    # Reload workflow with relationships
    result = await session.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == db_workflow.id)
        .options(
            selectinload(WorkflowDefinition.steps),
            selectinload(WorkflowDefinition.variables),
            selectinload(WorkflowDefinition.workspace),
            selectinload(WorkflowDefinition.project),
        )
    )
    db_workflow = result.scalar_one()

    logger.info("Workflow created: %s", db_workflow.id)
    return WorkflowResponse.model_validate(db_workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    include_steps: bool = Query(True, description="Include workflow steps and variables"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowResponse:
    """Get a workflow by ID in the active workspace."""

    session = ctx.session

    logger.info("Getting workflow (workspace_id=%s): %s", ctx.workspace.id, workflow_id)

    query = select(WorkflowDefinition).where(
        WorkflowDefinition.id == workflow_id,
        WorkflowDefinition.workspace_id == ctx.workspace.id
    )

    if include_steps:
        query = query.options(
            selectinload(WorkflowDefinition.steps),
            selectinload(WorkflowDefinition.variables),
            selectinload(WorkflowDefinition.workspace),
            selectinload(WorkflowDefinition.project),
        )

    result = await session.execute(query)
    db_workflow = result.scalar_one_or_none()

    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowResponse.model_validate(db_workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowUpdate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowResponse:
    """Update a workflow in the active workspace."""

    session = ctx.session

    logger.info("Updating workflow (workspace_id=%s): %s", ctx.workspace.id, workflow_id)

    result = await session.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == workflow_id, WorkflowDefinition.workspace_id == ctx.workspace.id)
        .options(
            selectinload(WorkflowDefinition.steps),
            selectinload(WorkflowDefinition.variables),
            selectinload(WorkflowDefinition.workspace),
            selectinload(WorkflowDefinition.project),
        )
    )
    db_workflow = result.scalar_one_or_none()

    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = workflow_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_workflow, field, value)

    await session.flush()

    logger.info("Workflow updated: %s", workflow_id)
    return WorkflowResponse.model_validate(db_workflow)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Delete a workflow in the active workspace."""

    session = ctx.session

    logger.info("Deleting workflow (workspace_id=%s): %s", ctx.workspace.id, workflow_id)

    result = await session.execute(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == workflow_id,
            WorkflowDefinition.workspace_id == ctx.workspace.id
        )
    )
    db_workflow = result.scalar_one_or_none()

    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Check if workflow has running executions
    running_executions_result = await session.execute(
        select(func.count()).select_from(WorkflowExecution).where(
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.status == WorkflowStatus.RUNNING
        )
    )
    running_count = running_executions_result.scalar_one()

    if running_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete workflow with {running_count} running executions"
        )

    await session.delete(db_workflow)

    logger.info("Workflow deleted: %s", workflow_id)
    return {"status": "deleted", "workflow_id": workflow_id}


@router.post("/{workflow_id}/execute", response_model=dict)
async def execute_workflow(
    workflow_id: str,
    execution_request: WorkflowExecutionCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Start a workflow execution using the workflow engine."""

    session = ctx.session

    logger.info("Executing workflow (workspace_id=%s): %s", ctx.workspace.id, workflow_id)

    # Get workflow
    result = await session.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == workflow_id, WorkflowDefinition.workspace_id == ctx.workspace.id)
        .options(
            selectinload(WorkflowDefinition.steps),
            selectinload(WorkflowDefinition.variables),
        )
    )
    db_workflow = result.scalar_one_or_none()

    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if not db_workflow.is_active:
        raise HTTPException(status_code=400, detail="Cannot execute inactive workflow")

    # Check if workflow integration is available
    if not hasattr(ctx.app.state, 'workflow_integration') or ctx.app.state.workflow_integration is None:
        raise HTTPException(status_code=503, detail="Workflow engine not available")

    try:
        # Execute workflow using the integration service
        execution_result = await ctx.app.state.workflow_integration.execute_workflow(
            workflow_id=workflow_id,
            workspace_id=ctx.workspace.id,
            project_id=db_workflow.project_id,
            input_variables=execution_request.input_variables,
            execution_metadata={
                "requested_by": execution_request.metadata.get("requested_by", "api"),
                "source": "api_endpoint",
            },
        )

        logger.info("Workflow execution submitted: %s", execution_result)

        return {
            "status": "submitted",
            "execution_id": execution_result,
            "message": "Workflow execution started successfully",
            "workflow_id": workflow_id,
        }

    except Exception as e:
        logger.error(f"Failed to execute workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to execute workflow: {str(e)}")


@router.post("/executions/{execution_id}/cancel", response_model=dict)
async def cancel_workflow_execution(
    execution_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Cancel a running workflow execution."""

    logger.info("Cancelling workflow execution (workspace_id=%s): %s", ctx.workspace.id, execution_id)

    # Check if workflow integration is available
    if not hasattr(ctx.app.state, 'workflow_integration') or ctx.app.state.workflow_integration is None:
        raise HTTPException(status_code=503, detail="Workflow engine not available")

    try:
        # Cancel workflow execution
        success = await ctx.app.state.workflow_integration.cancel_workflow_execution(execution_id)

        if success:
            return {
                "status": "cancelled",
                "execution_id": execution_id,
                "message": "Workflow execution cancelled successfully",
            }
        else:
            raise HTTPException(status_code=404, detail="Workflow execution not found or not running")

    except Exception as e:
        logger.error(f"Failed to cancel workflow execution {execution_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow execution: {str(e)}")


@router.get("/executions/{execution_id}/status", response_model=dict)
async def get_workflow_execution_status(
    execution_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Get the status of a workflow execution."""

    session = ctx.session

    logger.info("Getting workflow execution status (workspace_id=%s): %s", ctx.workspace.id, execution_id)

    # Get execution from database
    result = await session.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workspace_id == ctx.workspace.id
        )
    )
    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    return {
        "execution_id": execution.id,
        "workflow_id": execution.workflow_id,
        "status": execution.status.value,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "duration": execution.duration,
        "error_message": execution.error_message,
        "results": execution.results,
    }


@router.get("/executions/stats", response_model=dict)
async def get_workflow_execution_stats(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    """Get workflow execution statistics."""

    session = ctx.session

    logger.info("Getting workflow execution stats (workspace_id=%s)", ctx.workspace.id)

    # Get execution counts by status
    status_counts_result = await session.execute(
        select(WorkflowExecution.status, func.count(WorkflowExecution.id))
        .where(WorkflowExecution.workspace_id == ctx.workspace.id)
        .group_by(WorkflowExecution.status)
    )
    status_counts = dict(status_counts_result.all())

    # Get total executions
    total_result = await session.execute(
        select(func.count(WorkflowExecution.id))
        .where(WorkflowExecution.workspace_id == ctx.workspace.id)
    )
    total_executions = total_result.scalar()

    # Get recent executions (last 24 hours)
    recent_result = await session.execute(
        select(func.count(WorkflowExecution.id))
        .where(
            WorkflowExecution.workspace_id == ctx.workspace.id,
            WorkflowExecution.started_at >= datetime.utcnow() - timedelta(hours=24)
        )
    )
    recent_executions = recent_result.scalar()

    return {
        "total_executions": total_executions,
        "recent_executions_24h": recent_executions,
        "status_counts": {status.value: count for status, count in status_counts.items()},
        "workflow_engine_stats": getattr(ctx.app.state, 'workflow_integration', {}).get_integration_stats() 
                                if hasattr(ctx.app.state, 'workflow_integration') and ctx.app.state.workflow_integration 
                                else {},
    }


@router.get("/{workflow_id}/executions", response_model=WorkflowExecutionListResponse)
async def list_workflow_executions(
    workflow_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowExecutionListResponse:
    """List executions for a workflow."""

    session = ctx.session

    logger.info(
        "Listing workflow executions (workflow_id=%s, workspace_id=%s, skip=%s, limit=%s, status=%s)",
        workflow_id,
        ctx.workspace.id,
        skip,
        limit,
        status,
    )

    # Verify workflow exists and belongs to workspace
    workflow_result = await session.execute(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == workflow_id,
            WorkflowDefinition.workspace_id == ctx.workspace.id
        )
    )
    workflow = workflow_result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    query = (
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .options(selectinload(WorkflowExecution.definition))
    )

    if status:
        try:
            status_enum = WorkflowStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query = query.where(WorkflowExecution.status == status_enum)

    count_query = select(func.count()).select_from(WorkflowExecution).where(
        WorkflowExecution.workflow_id == workflow_id
    )

    if status:
        count_query = count_query.where(WorkflowExecution.status == status_enum)

    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(query.offset(skip).limit(limit))
    executions = result.scalars().all()

    return WorkflowExecutionListResponse(
        items=[WorkflowExecutionResponse.model_validate(execution) for execution in executions],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    execution_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowExecutionResponse:
    """Get a workflow execution by ID."""

    session = ctx.session

    logger.info("Getting workflow execution (workspace_id=%s): %s", ctx.workspace.id, execution_id)

    result = await session.execute(
        select(WorkflowExecution)
        .where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workspace_id == ctx.workspace.id
        )
        .options(selectinload(WorkflowExecution.definition))
    )
    db_execution = result.scalar_one_or_none()

    if db_execution is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    return WorkflowExecutionResponse.model_validate(db_execution)


@router.get("/executions/{execution_id}/timeline", response_model=WorkflowExecutionTimeline)
async def get_workflow_execution_timeline(
    execution_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowExecutionTimeline:
    """Get detailed timeline and metrics for a workflow execution."""

    session = ctx.session

    logger.info("Getting workflow execution timeline (workspace_id=%s): %s", ctx.workspace.id, execution_id)

    result = await session.execute(
        select(WorkflowExecution)
        .where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workspace_id == ctx.workspace.id
        )
        .options(
            selectinload(WorkflowExecution.definition),
            selectinload(WorkflowExecution.step_executions).selectinload(WorkflowStepExecution.step),
        )
    )
    db_execution = result.scalar_one_or_none()

    if db_execution is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    # Calculate timeline entries for each step
    step_timeline = []
    completed_count = 0
    failed_count = 0
    skipped_count = 0

    for step_exec in sorted(db_execution.step_executions, key=lambda x: x.step.step_order):
        duration = None
        if step_exec.started_at and step_exec.completed_at:
            duration = (step_exec.completed_at - step_exec.started_at).total_seconds()

        if step_exec.status == WorkflowStepStatus.COMPLETED:
            completed_count += 1
        elif step_exec.status == WorkflowStepStatus.FAILED:
            failed_count += 1
        elif step_exec.status == WorkflowStepStatus.SKIPPED:
            skipped_count += 1

        step_timeline.append(
            WorkflowStepTimelineEntry(
                step_id=step_exec.step_id,
                step_name=step_exec.step.name,
                step_order=step_exec.step.step_order,
                status=step_exec.status.value,
                started_at=step_exec.started_at,
                completed_at=step_exec.completed_at,
                duration_seconds=duration,
                retry_count=step_exec.retry_count,
                error_message=step_exec.error_message,
                input_summary=step_exec.input_data,
                output_summary=step_exec.output_data,
            )
        )

    total_duration = None
    if db_execution.started_at and db_execution.completed_at:
        total_duration = (db_execution.completed_at - db_execution.started_at).total_seconds()

    return WorkflowExecutionTimeline(
        execution_id=db_execution.id,
        workflow_id=db_execution.workflow_id,
        status=db_execution.status.value,
        started_at=db_execution.started_at,
        completed_at=db_execution.completed_at,
        total_duration_seconds=total_duration,
        step_count=len(db_execution.step_executions),
        completed_step_count=completed_count,
        failed_step_count=failed_count,
        skipped_step_count=skipped_count,
        step_timeline=step_timeline,
        error_message=db_execution.error_message,
    )


@router.get("/{workflow_id}/metrics", response_model=WorkflowMetricsSummary)
async def get_workflow_metrics(
    workflow_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowMetricsSummary:
    """Get aggregated metrics and statistics for a workflow."""

    session = ctx.session

    logger.info("Getting workflow metrics (workspace_id=%s): %s", ctx.workspace.id, workflow_id)

    # Verify workflow exists and belongs to workspace
    workflow_result = await session.execute(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == workflow_id,
            WorkflowDefinition.workspace_id == ctx.workspace.id
        )
    )
    workflow = workflow_result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get all executions for the workflow
    executions_result = await session.execute(
        select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
    )
    executions = executions_result.scalars().all()

    # Calculate metrics
    total_executions = len(executions)
    successful_executions = sum(1 for e in executions if e.status == WorkflowStatus.COMPLETED)
    failed_executions = sum(1 for e in executions if e.status == WorkflowStatus.FAILED)

    success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0

    # Calculate durations
    durations = [e.duration for e in executions if e.duration is not None]
    total_duration = sum(durations) if durations else 0.0
    average_duration = total_duration / len(durations) if durations else 0.0
    min_duration = min(durations) if durations else None
    max_duration = max(durations) if durations else None

    return WorkflowMetricsSummary(
        total_duration_seconds=total_duration,
        success_rate=success_rate,
        total_executions=total_executions,
        successful_executions=successful_executions,
        failed_executions=failed_executions,
        average_duration_seconds=average_duration,
        min_duration_seconds=min_duration,
        max_duration_seconds=max_duration,
    )


@router.post("/validate", response_model=WorkflowValidationResult)
async def validate_workflow_definition(
    workflow: WorkflowCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowValidationResult:
    """Validate a workflow definition without saving it."""

    logger.info("Validating workflow definition (workspace_id=%s): %s", ctx.workspace.id, workflow.name)

    resolver = WorkflowDependencyResolver()
    return resolver.validate_workflow(workflow)


@router.get("/templates")
async def list_workflow_templates(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list:
    """List available workflow templates."""

    logger.info("Listing workflow templates (workspace_id=%s)", ctx.workspace.id)

    # For now, return basic templates. In a real implementation, these could be stored in DB
    templates = [
        {
            "id": "basic_sequence",
            "name": "Basic Sequence",
            "description": "A simple sequential workflow with 3 steps",
            "steps": [
                {
                    "name": "initialize",
                    "step_type": "task",
                    "step_order": 1,
                    "config": {"description": "Initialize the workflow"},
                    "depends_on_steps": [],
                },
                {
                    "name": "process",
                    "step_type": "task",
                    "step_order": 2,
                    "config": {"description": "Process data"},
                    "depends_on_steps": ["initialize"],
                },
                {
                    "name": "finalize",
                    "step_type": "task",
                    "step_order": 3,
                    "config": {"description": "Finalize and output results"},
                    "depends_on_steps": ["process"],
                },
            ],
            "variables": [
                {
                    "name": "input_data",
                    "data_type": "json",
                    "is_required": True,
                    "description": "Input data for processing",
                },
                {
                    "name": "output_format",
                    "data_type": "string",
                    "is_required": False,
                    "default_value": "json",
                    "description": "Desired output format",
                },
            ],
        },
        {
            "id": "parallel_processing",
            "name": "Parallel Processing",
            "description": "A workflow that processes data in parallel branches",
            "steps": [
                {
                    "name": "data_preparation",
                    "step_type": "task",
                    "step_order": 1,
                    "config": {"description": "Prepare data for parallel processing"},
                    "depends_on_steps": [],
                },
                {
                    "name": "branch_a",
                    "step_type": "task",
                    "step_order": 2,
                    "config": {"description": "Process branch A"},
                    "depends_on_steps": ["data_preparation"],
                },
                {
                    "name": "branch_b",
                    "step_type": "task",
                    "step_order": 2,
                    "config": {"description": "Process branch B"},
                    "depends_on_steps": ["data_preparation"],
                },
                {
                    "name": "merge_results",
                    "step_type": "task",
                    "step_order": 3,
                    "config": {"description": "Merge results from parallel branches"},
                    "depends_on_steps": ["branch_a", "branch_b"],
                },
            ],
            "variables": [
                {
                    "name": "input_data",
                    "data_type": "json",
                    "is_required": True,
                    "description": "Input data for parallel processing",
                },
            ],
        },
    ]

    return templates


__all__ = ["router"]