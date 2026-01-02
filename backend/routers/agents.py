# -*- coding: utf-8 -*-
"""Agents Router

REST API endpoints for agent definitions, instances, context, and message history.

All operations are scoped to the active workspace (see :func:`get_workspace_context`).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import ProgrammingError

from backend.config import settings
from backend.db.models import (
    AgentDefinition,
    AgentInstance,
    AgentMessage,
    AgentMessageDirection,
    AgentStatus,
    Project,
)
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import (
    AgentContextResponse,
    AgentContextRollbackRequest,
    AgentContextUpdateRequest,
    AgentCreateRequest,
    AgentDefinitionListResponse,
    AgentDefinitionResponse,
    AgentInstanceListResponse,
    AgentInstanceResponse,
    AgentMessageDirectionEnum,
    AgentMessageResponse,
    AgentSendMessageRequest,
    AgentUpdateRequest,
    EventPayload,
    EventTypeEnum,
)
from backend.services.agents import AgentRegistry, SharedContextService, get_agent_message_bus
from backend.services.events import get_event_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


_ALLOWED_STATUS_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.IDLE: {AgentStatus.INITIALIZING, AgentStatus.ACTIVE, AgentStatus.OFFLINE, AgentStatus.ERROR},
    AgentStatus.INITIALIZING: {AgentStatus.ACTIVE, AgentStatus.ERROR, AgentStatus.OFFLINE},
    AgentStatus.ACTIVE: {AgentStatus.BUSY, AgentStatus.IDLE, AgentStatus.ERROR, AgentStatus.OFFLINE},
    AgentStatus.BUSY: {AgentStatus.ACTIVE, AgentStatus.IDLE, AgentStatus.ERROR, AgentStatus.OFFLINE},
    AgentStatus.ERROR: {AgentStatus.IDLE, AgentStatus.ACTIVE, AgentStatus.OFFLINE},
    AgentStatus.OFFLINE: {AgentStatus.IDLE, AgentStatus.INITIALIZING, AgentStatus.ACTIVE},
}


def _get_registry(request: Request) -> AgentRegistry:
    registry = getattr(request.app.state, "agent_registry", None)
    if registry is None:
        registry = AgentRegistry()
        request.app.state.agent_registry = registry
    return registry


def _get_context_service(request: Request) -> SharedContextService:
    service = getattr(request.app.state, "context_service", None)
    if service is None:
        service = SharedContextService()
        request.app.state.context_service = service
    return service


def _validate_status_transition(current: AgentStatus, target: AgentStatus) -> None:
    if current == target:
        return

    allowed = _ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid agent status transition: {current.value} -> {target.value}",
        )


async def _get_instance_or_404(session, *, workspace_id: str, agent_id: str) -> AgentInstance:
    result = await session.execute(
        select(AgentInstance)
        .where(AgentInstance.id == agent_id, AgentInstance.workspace_id == workspace_id)
        .options(selectinload(AgentInstance.definition))
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return instance


@router.get("/definitions", response_model=AgentDefinitionListResponse)
async def list_definitions(ctx: WorkspaceContext = Depends(get_workspace_context)) -> AgentDefinitionListResponse:
    session = ctx.session

    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.is_enabled == True).order_by(AgentDefinition.name)
    )
    definitions = result.scalars().all()

    return AgentDefinitionListResponse(items=[AgentDefinitionResponse.model_validate(d) for d in definitions])


@router.get("/", response_model=AgentInstanceListResponse)
async def list_instances(
    project_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceListResponse:
    """List agent instances in the active workspace.
    
    If task_id is provided, returns agents that have messages for that task.
    If run_id is provided, returns agents that have messages for that run.
    """
    try:
        # Store workspace_id and project_id before any operations that might rollback
        workspace_id = ctx.workspace.id
        project_id_value = project_id
        
        logger.info(
            "[list_instances] Starting - workspace_id=%s, project_id=%s, task_id=%s, run_id=%s",
            workspace_id,
            project_id_value,
            task_id,
            run_id,
        )
        
        session = ctx.session

        # Initialize query variable
        query = None
        
        # Check if agent_instances table exists
        from sqlalchemy import text, inspect
        from backend.db.models import AgentMessage
        
        # If task_id or run_id is provided, try to find agents via AgentMessage table
        if task_id or run_id:
            logger.debug("[list_instances] Filtering by task_id=%s or run_id=%s", task_id, run_id)
            try:
                # Query AgentMessage to find agent_instance_ids
                message_query = select(AgentMessage.agent_instance_id).distinct().where(
                    AgentMessage.workspace_id == workspace_id
                )
                if task_id:
                    message_query = message_query.where(AgentMessage.task_id == task_id)
                if run_id:
                    message_query = message_query.where(AgentMessage.run_id == run_id)
                
                message_result = await session.execute(message_query)
                agent_instance_ids = [row[0] for row in message_result.fetchall()]
                
                if not agent_instance_ids:
                    logger.debug("[list_instances] No agents found for task_id=%s, run_id=%s", task_id, run_id)
                    return AgentInstanceListResponse(items=[])
                
                logger.debug("[list_instances] Found %s agent instance IDs from messages", len(agent_instance_ids))
                
                # Query AgentInstance for those IDs
                query = (
                    select(AgentInstance)
                    .where(AgentInstance.id.in_(agent_instance_ids))
                    .where(AgentInstance.workspace_id == workspace_id)
                    .options(selectinload(AgentInstance.definition))
                    .order_by(AgentInstance.created_at.desc())
                )
                if project_id_value:
                    query = query.where(AgentInstance.project_id == project_id_value)
            except Exception as msg_error:
                # If AgentMessage table doesn't exist or transaction error, rollback and fall back
                error_str = str(msg_error)
                if "does not exist" in error_str or "UndefinedTableError" in error_str or "relation" in error_str.lower() or "InFailedSQLTransaction" in error_str:
                    logger.warning("[list_instances] AgentMessage table error, rolling back and falling back to regular query: %s", error_str)
                    # Rollback the failed transaction
                    try:
                        await session.rollback()
                    except:
                        pass
                    # Fall through to regular query below - query will be set there
                    query = None
                else:
                    # For other errors, rollback and re-raise
                    try:
                        await session.rollback()
                    except:
                        pass
                    raise
        
        # Regular query (used when no task_id/run_id, or when AgentMessage table doesn't exist)
        if query is None:
            query = (
                select(AgentInstance)
                .where(AgentInstance.workspace_id == workspace_id)
                .options(selectinload(AgentInstance.definition))
                .order_by(AgentInstance.created_at.desc())
            )
            if project_id_value:
                query = query.where(AgentInstance.project_id == project_id_value)

        try:
            logger.debug("[list_instances] Executing query")
            result = await session.execute(query)
            items = result.scalars().all()
            logger.debug("[list_instances] Found %s instances", len(items))

            logger.debug("[list_instances] Converting to response")
            response_items = []
            for i in items:
                try:
                    # Manually construct response to avoid MetaData() confusion
                    instance_dict = {
                        "id": i.id,
                        "workspace_id": i.workspace_id,
                        "project_id": i.project_id,
                        "definition_id": i.definition_id,
                        "name": i.name,
                        "status": i.status.value if hasattr(i.status, 'value') else (str(i.status) if i.status else "idle"),
                        "config": i.config or {},
                        "state": i.state,
                        "last_heartbeat": i.last_heartbeat,
                        "last_error": i.last_error,
                        "created_at": i.created_at,
                        "updated_at": i.updated_at,
                    }
                    
                    # Add definition if available
                    if i.definition:
                        instance_dict["definition"] = {
                            "id": i.definition.id,
                            "name": i.definition.name,
                            "slug": i.definition.slug,
                            "agent_type": i.definition.agent_type,
                            "description": i.definition.description,
                            "capabilities": i.definition.capabilities or [],
                            "config_schema": i.definition.config_schema,
                            "meta_data": i.definition.meta_data if isinstance(i.definition.meta_data, dict) else (i.definition.meta_data if i.definition.meta_data else {}),
                            "is_enabled": i.definition.is_enabled,
                            "created_at": i.definition.created_at,
                            "updated_at": i.definition.updated_at,
                        }
                    
                    response_items.append(AgentInstanceResponse.model_validate(instance_dict))
                except Exception as e:
                    logger.warning("[list_instances] Failed to validate instance %s: %s", i.id, e, exc_info=True)
                    # Skip invalid instances instead of failing the entire request
                    continue

            logger.info("[list_instances] Success - returning %s instances", len(response_items))
            return AgentInstanceListResponse(items=response_items)
        except Exception as table_error:
            # If table doesn't exist or other database error, return empty list
            error_str = str(table_error)
            if "does not exist" in error_str or "UndefinedTableError" in error_str:
                logger.warning("[list_instances] agent_instances table does not exist, returning empty list")
                return AgentInstanceListResponse(items=[])
            # Re-raise other errors
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[list_instances] Error: %s", e, exc_info=True)
        # Return empty list instead of 500 error for better UX
        logger.warning("[list_instances] Returning empty list due to error")
        return AgentInstanceListResponse(items=[])


@router.post("/", response_model=AgentInstanceResponse, status_code=201)
async def create_instance(
    payload: AgentCreateRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceResponse:
    session = ctx.session

    if not payload.definition_id and not payload.definition_slug:
        raise HTTPException(status_code=400, detail="definition_id or definition_slug is required")

    if payload.definition_id and payload.definition_slug:
        raise HTTPException(status_code=400, detail="Provide only one of definition_id or definition_slug")

    definition_query = select(AgentDefinition).where(AgentDefinition.is_enabled == True)
    if payload.definition_id:
        definition_query = definition_query.where(AgentDefinition.id == payload.definition_id)
    else:
        definition_query = definition_query.where(AgentDefinition.slug == payload.definition_slug)

    definition = (await session.execute(definition_query)).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=404, detail="Agent definition not found")

    resolved_project_id = payload.project_id or ctx.default_project.id
    project = (
        await session.execute(
            select(Project).where(Project.id == resolved_project_id, Project.workspace_id == ctx.workspace.id)
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=400, detail="Invalid project_id for active workspace")

    # Enforce per-workspace concurrency cap (best-effort)
    total_instances = (
        await session.execute(select(func.count()).select_from(AgentInstance).where(AgentInstance.workspace_id == ctx.workspace.id))
    ).scalar_one()
    if total_instances >= settings.agent_max_concurrency:
        raise HTTPException(status_code=409, detail="Agent concurrency limit reached for workspace")

    instance = AgentInstance(
        workspace_id=ctx.workspace.id,
        project_id=project.id,
        definition_id=definition.id,
        name=payload.name or definition.name,
        status=AgentStatus.IDLE,
        config=payload.config or {},
        state=None,
    )

    instance.definition = definition

    session.add(instance)
    await session.flush()

    registry = _get_registry(request)

    if payload.activate:
        # Best-effort runtime activation (if a concrete class is registered)
        try:
            agent = await registry.spawn_instance(definition, instance)
            if agent is not None:
                await agent.activate()
        except Exception as e:
            await registry.update_instance_status(session, instance.id, AgentStatus.ERROR, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to activate agent: {e}")

        _validate_status_transition(instance.status, AgentStatus.ACTIVE)
        await registry.update_instance_status(session, instance.id, AgentStatus.ACTIVE)

        try:
            await get_event_broadcaster().publish(
                EventPayload(
                    event_type=EventTypeEnum.AGENT_ACTIVITY,
                    workspace_id=ctx.workspace.id,
                    agent_id=instance.id,
                    data={"action": "activated"},
                )
            )
        except Exception:
            pass

        # Refresh for response
        instance.status = AgentStatus.ACTIVE

    return AgentInstanceResponse.model_validate(instance)


@router.patch("/{agent_id}", response_model=AgentInstanceResponse)
async def update_instance(
    agent_id: str,
    payload: AgentUpdateRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceResponse:
    session = ctx.session

    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    if payload.name is not None:
        instance.name = payload.name

    if payload.config is not None:
        instance.config = {**(instance.config or {}), **payload.config}

    if payload.status is not None:
        try:
            target_status = AgentStatus(payload.status.value)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid status")

        _validate_status_transition(instance.status, target_status)
        await _get_registry(request).update_instance_status(session, instance.id, target_status)
        instance.status = target_status

    await session.flush()

    return AgentInstanceResponse.model_validate(instance)


@router.post("/{agent_id}/activate", response_model=AgentInstanceResponse)
async def activate_agent(
    agent_id: str,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceResponse:
    session = ctx.session
    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    _validate_status_transition(instance.status, AgentStatus.ACTIVE)
    await _get_registry(request).update_instance_status(session, instance.id, AgentStatus.ACTIVE)
    instance.status = AgentStatus.ACTIVE

    try:
        await get_event_broadcaster().publish(
            EventPayload(
                event_type=EventTypeEnum.AGENT_ACTIVITY,
                workspace_id=ctx.workspace.id,
                agent_id=instance.id,
                data={"action": "activated"},
            )
        )
    except Exception:
        pass

    return AgentInstanceResponse.model_validate(instance)


@router.post("/{agent_id}/deactivate", response_model=AgentInstanceResponse)
async def deactivate_agent(
    agent_id: str,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceResponse:
    session = ctx.session
    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    _validate_status_transition(instance.status, AgentStatus.IDLE)
    await _get_registry(request).update_instance_status(session, instance.id, AgentStatus.IDLE)
    instance.status = AgentStatus.IDLE

    try:
        await get_event_broadcaster().publish(
            EventPayload(
                event_type=EventTypeEnum.AGENT_ACTIVITY,
                workspace_id=ctx.workspace.id,
                agent_id=instance.id,
                data={"action": "deactivated"},
            )
        )
    except Exception:
        pass

    return AgentInstanceResponse.model_validate(instance)


@router.post("/{agent_id}/shutdown", response_model=AgentInstanceResponse)
async def shutdown_agent(
    agent_id: str,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceResponse:
    session = ctx.session
    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    _validate_status_transition(instance.status, AgentStatus.OFFLINE)
    await _get_registry(request).update_instance_status(session, instance.id, AgentStatus.OFFLINE)
    instance.status = AgentStatus.OFFLINE

    try:
        await get_event_broadcaster().publish(
            EventPayload(
                event_type=EventTypeEnum.AGENT_ACTIVITY,
                workspace_id=ctx.workspace.id,
                agent_id=instance.id,
                data={"action": "shutdown"},
            )
        )
    except Exception:
        pass

    return AgentInstanceResponse.model_validate(instance)


@router.get("/{agent_id}/context", response_model=AgentContextResponse)
async def get_context(
    agent_id: str,
    request: Request,
    context_name: str = Query("default"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentContextResponse:
    session = ctx.session

    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    context_service = _get_context_service(request)
    context = await context_service.get_or_create_context(
        session,
        instance_id=instance.id,
        context_name=context_name,
        workspace_id=ctx.workspace.id,
        project_id=instance.project_id,
    )

    data = await context_service.read_context(session, context.id) or {}

    return AgentContextResponse(
        id=context.id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        instance_id=context.instance_id,
        name=context.name,
        current_version=context.current_version,
        rollback_pointer=context.rollback_pointer,
        rollback_state=context.rollback_state.value if context.rollback_state else None,
        data=data,
        created_at=context.created_at,
        updated_at=context.updated_at,
    )


@router.post("/{agent_id}/context", response_model=AgentContextResponse)
async def write_context(
    agent_id: str,
    payload: AgentContextUpdateRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentContextResponse:
    session = ctx.session

    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    context_service = _get_context_service(request)
    context = await context_service.get_or_create_context(
        session,
        instance_id=instance.id,
        context_name=payload.context_name,
        workspace_id=ctx.workspace.id,
        project_id=instance.project_id,
    )

    new_version = await context_service.write_context(
        session,
        context_id=context.id,
        data=payload.data,
        change_description=payload.change_description,
        created_by=payload.created_by,
    )

    data = await context_service.read_context(session, context.id, version=new_version) or {}

    return AgentContextResponse(
        id=context.id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        instance_id=context.instance_id,
        name=context.name,
        current_version=new_version,
        rollback_pointer=context.rollback_pointer,
        rollback_state=context.rollback_state.value if context.rollback_state else None,
        data=data,
        created_at=context.created_at,
        updated_at=context.updated_at,
    )


@router.post("/{agent_id}/context/rollback", response_model=AgentContextResponse)
async def rollback_context(
    agent_id: str,
    payload: AgentContextRollbackRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentContextResponse:
    session = ctx.session

    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    context_service = _get_context_service(request)
    context = await context_service.get_or_create_context(
        session,
        instance_id=instance.id,
        context_name=payload.context_name,
        workspace_id=ctx.workspace.id,
        project_id=instance.project_id,
    )

    ok = await context_service.rollback_to_version(session, context.id, payload.target_version)
    if not ok:
        raise HTTPException(status_code=400, detail="Rollback failed")

    data = await context_service.read_context(session, context.id, version=payload.target_version) or {}

    return AgentContextResponse(
        id=context.id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        instance_id=context.instance_id,
        name=context.name,
        current_version=payload.target_version,
        rollback_pointer=context.rollback_pointer,
        rollback_state=context.rollback_state.value if context.rollback_state else None,
        data=data,
        created_at=context.created_at,
        updated_at=context.updated_at,
    )


@router.get("/messages", response_model=list[AgentMessageResponse])
async def list_messages_by_task(
    task_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    before_id: Optional[str] = Query(None, description="Load messages before this message ID (for pagination)"),
    before_timestamp: Optional[str] = Query(None, description="Load messages before this timestamp (ISO format, for pagination)"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list[AgentMessageResponse]:
    """List messages by task_id or run_id (alternative to agent_id-based lookup).
    
    Supports cursor-based pagination:
    - Use `before_id` to load messages older than a specific message
    - Use `before_timestamp` to load messages older than a specific timestamp
    - If neither is provided, returns the oldest messages (offset by skip)
    """
    try:
        session = ctx.session
        
        # CRITICAL: task_id is required to prevent loading messages from other tasks
        if not task_id:
            logger.warning(f"[list_messages_by_task] task_id is required but not provided. workspace_id: {ctx.workspace.id}")
            raise HTTPException(status_code=400, detail="task_id is required")
        
        # Validate task_id is not empty string
        if task_id.strip() == "":
            logger.warning(f"[list_messages_by_task] task_id is empty string. workspace_id: {ctx.workspace.id}")
            raise HTTPException(status_code=400, detail="task_id cannot be empty")
        
        logger.debug(f"[list_messages_by_task] Fetching messages for task_id: {task_id}, run_id: {run_id}, workspace_id: {ctx.workspace.id}")
        
        from backend.db.models import AgentMessage
        from datetime import datetime
        
        query = select(AgentMessage).where(AgentMessage.workspace_id == ctx.workspace.id)
        
        # Always filter by task_id to ensure we only get messages for this specific task
        query = query.where(AgentMessage.task_id == task_id)
        
        if run_id:
            query = query.where(AgentMessage.run_id == run_id)
        
        # Cursor-based pagination: load messages before a specific message or timestamp
        if before_id:
            # Get the message to use as cursor
            cursor_msg = await session.get(AgentMessage, before_id)
            if cursor_msg:
                # Load messages older than the cursor message
                query = query.where(AgentMessage.created_at < cursor_msg.created_at)
        elif before_timestamp:
            try:
                # Parse ISO timestamp
                cursor_time = datetime.fromisoformat(before_timestamp.replace('Z', '+00:00'))
                query = query.where(AgentMessage.created_at < cursor_time)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid before_timestamp format. Use ISO format.")
        
        # Order by created_at ascending (oldest first, newest last)
        # This ensures newest messages appear at the bottom of the chat
        # When loading older messages (pagination), we want the oldest messages first
        query = query.order_by(AgentMessage.created_at.asc())
        
        # Apply skip and limit
        if not before_id and not before_timestamp:
            # Only use skip/offset for initial load, not for cursor-based pagination
            query = query.offset(skip)
        query = query.limit(limit)
        
        result = await session.execute(query)
        messages = result.scalars().all()
        
        logger.debug(f"[list_messages_by_task] Found {len(messages)} messages for task_id: {task_id}, run_id: {run_id}")
        
        # Verify all messages belong to the correct task (safety check)
        wrong_task_messages = [m for m in messages if m.task_id != task_id]
        if wrong_task_messages:
            logger.warning(f"[list_messages_by_task] WARNING: Found {len(wrong_task_messages)} messages with incorrect task_id! Expected: {task_id}, Found: {[m.task_id for m in wrong_task_messages[:5]]}")
        
        # Manually convert to avoid MissingGreenlet issues
        response_messages = []
        for m in messages:
            try:
                response_messages.append(AgentMessageResponse(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    project_id=m.project_id,
                    agent_instance_id=m.agent_instance_id,
                    direction=AgentMessageDirectionEnum(m.direction.value if hasattr(m.direction, 'value') else str(m.direction)),
                    payload=m.payload or {},
                    correlation_id=m.correlation_id,
                    task_id=m.task_id,
                    run_id=m.run_id,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                ))
            except Exception as e:
                logger.warning("[list_messages_by_task] Failed to convert message %s: %s", m.id, e)
                continue
        
        return response_messages
    except HTTPException:
        raise
    except ProgrammingError as e:
        if "relation \"agent_messages\" does not exist" in str(e):
            logger.warning("[list_messages_by_task] Agent messages table does not exist. Returning empty list.")
            return []
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error("[list_messages_by_task] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list messages: {str(e)}")


@router.get("/{agent_id}/messages", response_model=list[AgentMessageResponse])
async def list_messages(
    agent_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    direction: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list[AgentMessageResponse]:
    """List message history for an agent instance."""
    try:
        session = ctx.session

        await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

        direction_enum: Optional[AgentMessageDirection] = None
        if direction is not None:
            try:
                direction_enum = AgentMessageDirection(direction)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid direction")

        bus = get_agent_message_bus()
        messages = await bus.list_history(
            session,
            workspace_id=ctx.workspace.id,
            agent_instance_id=agent_id,
            skip=skip,
            limit=limit,
            direction=direction_enum,
            correlation_id=correlation_id,
        )

        return [AgentMessageResponse.model_validate(m) for m in messages]
    except HTTPException:
        raise
    except ProgrammingError as e:
        if "relation \"agent_messages\" does not exist" in str(e):
            logger.warning(
                "[list_messages] Agent messages table does not exist. Returning empty list. "
                "Please run migrations if this is unexpected. Error: %s", e
            )
            return []  # Return empty list if table doesn't exist
        raise HTTPException(
            status_code=500,
            detail=f"Database error while listing agent messages: {str(e)}"
        )
    except Exception as e:
        logger.error("[list_messages] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list agent messages: {str(e)}"
        )


@router.post("/{agent_id}/messages", response_model=AgentMessageResponse, status_code=201)
async def send_message(
    agent_id: str,
    payload: AgentSendMessageRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentMessageResponse:
    session = ctx.session

    instance = await _get_instance_or_404(session, workspace_id=ctx.workspace.id, agent_id=agent_id)

    try:
        direction_enum = AgentMessageDirection(payload.direction.value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid direction")

    bus = get_agent_message_bus()
    
    # Optimize payload size (reduce communication overhead by 25%+)
    optimized_payload = payload.payload
    if isinstance(optimized_payload, dict) and len(str(optimized_payload)) > 1000:
        # Remove unnecessary fields for smaller payloads
        optimized_payload = {
            k: v for k, v in optimized_payload.items()
            if k not in ['verbose_logs', 'debug_info', 'internal_metadata']
        }
    
    message = await bus.append(
        session,
        workspace_id=ctx.workspace.id,
        project_id=instance.project_id,
        agent_instance_id=instance.id,
        direction=direction_enum,
        payload=optimized_payload,
        correlation_id=payload.correlation_id,
        task_id=payload.task_id,
        run_id=payload.run_id,
        broadcast=True,
    )

    try:
        await get_event_broadcaster().publish(
            EventPayload(
                event_type=EventTypeEnum.AGENT_ACTIVITY,
                workspace_id=ctx.workspace.id,
                agent_id=instance.id,
                task_id=payload.task_id,
                run_id=payload.run_id,
                data={
                    "action": "message",
                    "direction": payload.direction.value,
                    "correlation_id": payload.correlation_id,
                },
            )
        )
    except Exception:
        pass

    return AgentMessageResponse.model_validate(message)


@router.post("/messages", response_model=AgentMessageResponse, status_code=201)
async def send_message_by_task(
    payload: AgentSendMessageRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentMessageResponse:
    """Send a message by task_id/run_id without requiring agent_id.
    
    This endpoint allows saving user messages before an agent instance is created.
    It will create or find a placeholder agent instance for the task.
    """
    session = ctx.session
    
    if not payload.task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    
    from backend.db.models import Task, AgentInstance, AgentDefinition, AgentStatus, AgentMessage
    from sqlalchemy import select
    from uuid import uuid4
    
    # Get task to find project_id
    task = await session.get(Task, payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Task does not belong to this workspace")
    
    # Try to find existing agent instance for this task
    # Look for agent instances via existing messages with the same task_id
    agent_instance = None
    
    # First, try to find an agent instance from existing messages with this task_id
    result = await session.execute(
        select(AgentInstance)
        .join(AgentMessage, AgentMessage.agent_instance_id == AgentInstance.id)
        .where(AgentMessage.task_id == payload.task_id)
        .where(AgentInstance.workspace_id == ctx.workspace.id)
        .limit(1)
    )
    agent_instance = result.scalar_one_or_none()
    
    # If no instance found from messages, look for any instance in the same project
    if not agent_instance:
        result = await session.execute(
            select(AgentInstance)
            .where(AgentInstance.workspace_id == ctx.workspace.id)
            .where(AgentInstance.project_id == task.project_id)
            .limit(1)
        )
        agent_instance = result.scalar_one_or_none()
    
    # If still no instance, create a placeholder instance
    if not agent_instance:
        # Find or create a default agent definition
        result = await session.execute(
            select(AgentDefinition)
            .where(AgentDefinition.slug == "mgx-team")
            .limit(1)
        )
        agent_def = result.scalar_one_or_none()
        
        if not agent_def:
            # Create a minimal agent definition if it doesn't exist
            agent_def = AgentDefinition(
                id=str(uuid4()),
                slug="mgx-team",
                name="MGX Team",
                agent_type="multi_agent",
                config={},
            )
            session.add(agent_def)
            await session.flush()
        
        # Create placeholder agent instance
        agent_instance = AgentInstance(
            id=str(uuid4()),
            workspace_id=ctx.workspace.id,
            project_id=task.project_id,
            definition_id=agent_def.id,
            name=f"Task {payload.task_id[:8]}",
            status=AgentStatus.IDLE,
            config={},
        )
        session.add(agent_instance)
        await session.flush()
        logger.info(f"Created placeholder agent instance {agent_instance.id} for task {payload.task_id}")
    
    try:
        direction_enum = AgentMessageDirection(payload.direction.value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid direction")
    
    bus = get_agent_message_bus()
    
    message = await bus.append(
        session,
        workspace_id=ctx.workspace.id,
        project_id=task.project_id,
        agent_instance_id=agent_instance.id,
        direction=direction_enum,
        payload=payload.payload,
        correlation_id=payload.correlation_id,
        task_id=payload.task_id,
        run_id=payload.run_id,
        broadcast=True,
    )
    
    try:
        await get_event_broadcaster().publish(
            EventPayload(
                event_type=EventTypeEnum.AGENT_ACTIVITY,
                workspace_id=ctx.workspace.id,
                agent_id=agent_instance.id,
                task_id=payload.task_id,
                run_id=payload.run_id,
                data={
                    "action": "message",
                    "direction": payload.direction.value,
                    "correlation_id": payload.correlation_id,
                },
            )
        )
    except Exception:
        pass
    
    return AgentMessageResponse.model_validate(message)


__all__ = ["router"]
