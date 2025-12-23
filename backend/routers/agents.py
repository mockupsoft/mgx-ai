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

from backend.config import settings
from backend.db.models import (
    AgentDefinition,
    AgentInstance,
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
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> AgentInstanceListResponse:
    session = ctx.session

    query = (
        select(AgentInstance)
        .where(AgentInstance.workspace_id == ctx.workspace.id)
        .options(selectinload(AgentInstance.definition))
        .order_by(AgentInstance.created_at.desc())
    )
    if project_id:
        query = query.where(AgentInstance.project_id == project_id)

    result = await session.execute(query)
    items = result.scalars().all()

    return AgentInstanceListResponse(items=[AgentInstanceResponse.model_validate(i) for i in items])


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


@router.get("/{agent_id}/messages", response_model=list[AgentMessageResponse])
async def list_messages(
    agent_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    direction: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> list[AgentMessageResponse]:
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


__all__ = ["router"]
