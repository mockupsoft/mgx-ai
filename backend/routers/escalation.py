# -*- coding: utf-8 -*-
"""
Escalation API Router

Provides endpoints for managing escalation rules and viewing escalation history.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    EscalationRule,
    EscalationEvent,
    EscalationRuleType,
    EscalationSeverity,
    EscalationReason,
    EscalationStatus,
)
from backend.routers.deps import get_db_session
from backend.services.agents.escalation import EscalationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/escalation", tags=["escalation"])


# ============================================
# Pydantic Schemas
# ============================================

class EscalationRuleCreate(BaseModel):
    """Schema for creating an escalation rule."""
    workspace_id: str
    project_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    rule_type: str = Field(..., description="Rule type (threshold, pattern, time_based, resource_based, composite)")
    condition: Dict[str, Any] = Field(..., description="Rule condition logic")
    severity: str = Field(..., description="Escalation severity (low, medium, high, critical)")
    reason: str = Field(..., description="Escalation reason")
    priority: int = Field(default=0, description="Rule priority (higher evaluated first)")
    target_agent_type: Optional[str] = Field(None, description="Target supervisor/manager agent type")
    auto_assign: bool = Field(default=True, description="Auto-assign to supervisor")
    notify_websocket: bool = Field(default=True, description="Send WebSocket notifications")
    notify_email: bool = Field(default=False, description="Send email notifications")
    notify_slack: bool = Field(default=False, description="Send Slack notifications")
    notification_config: Dict[str, Any] = Field(default_factory=dict, description="Notification configuration")


class EscalationRuleUpdate(BaseModel):
    """Schema for updating an escalation rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    reason: Optional[str] = None
    priority: Optional[int] = None
    target_agent_type: Optional[str] = None
    auto_assign: Optional[bool] = None
    is_enabled: Optional[bool] = None
    notify_websocket: Optional[bool] = None
    notify_email: Optional[bool] = None
    notify_slack: Optional[bool] = None
    notification_config: Optional[Dict[str, Any]] = None


class EscalationRuleResponse(BaseModel):
    """Schema for escalation rule response."""
    id: str
    workspace_id: str
    project_id: Optional[str]
    name: str
    description: Optional[str]
    rule_type: str
    condition: Dict[str, Any]
    severity: str
    reason: str
    priority: int
    target_agent_type: Optional[str]
    auto_assign: bool
    is_enabled: bool
    notify_websocket: bool
    notify_email: bool
    notify_slack: bool
    notification_config: Dict[str, Any]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class EscalationEventResponse(BaseModel):
    """Schema for escalation event response."""
    id: str
    workspace_id: str
    project_id: Optional[str]
    rule_id: Optional[str]
    task_id: Optional[str]
    task_run_id: Optional[str]
    workflow_execution_id: Optional[str]
    workflow_step_execution_id: Optional[str]
    source_agent_id: Optional[str]
    target_agent_id: Optional[str]
    severity: str
    reason: str
    status: str
    trigger_data: Dict[str, Any]
    context_data: Dict[str, Any]
    resolution_data: Optional[Dict[str, Any]]
    assigned_at: Optional[str]
    resolved_at: Optional[str]
    time_to_assign_seconds: Optional[int]
    time_to_resolve_seconds: Optional[int]
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class EscalationStatsResponse(BaseModel):
    """Schema for escalation statistics response."""
    total_escalations: int
    pending: int
    assigned: int
    in_progress: int
    resolved: int
    failed: int
    cancelled: int
    avg_time_to_assign_seconds: float
    avg_time_to_resolve_seconds: float
    resolution_rate: float
    by_severity: Dict[str, int]
    by_reason: Dict[str, int]


# ============================================
# Endpoints
# ============================================

@router.post("/rules", response_model=EscalationRuleResponse)
async def create_escalation_rule(
    rule_data: EscalationRuleCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Create a new escalation rule.
    
    Args:
        rule_data: Rule data
        session: Database session
        
    Returns:
        Created escalation rule
    """
    try:
        escalation_service = EscalationService()
        
        rule = await escalation_service.create_rule(
            session=session,
            workspace_id=rule_data.workspace_id,
            project_id=rule_data.project_id,
            name=rule_data.name,
            description=rule_data.description,
            rule_type=rule_data.rule_type,
            condition=rule_data.condition,
            severity=rule_data.severity,
            reason=rule_data.reason,
            priority=rule_data.priority,
            target_agent_type=rule_data.target_agent_type,
            auto_assign=rule_data.auto_assign,
            notify_websocket=rule_data.notify_websocket,
            notify_email=rule_data.notify_email,
            notify_slack=rule_data.notify_slack,
            notification_config=rule_data.notification_config,
        )
        
        await session.commit()
        
        logger.info(f"Created escalation rule: {rule.id}")
        return rule
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create escalation rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules", response_model=List[EscalationRuleResponse])
async def list_escalation_rules(
    workspace_id: str = Query(..., description="Workspace ID"),
    project_id: Optional[str] = Query(None, description="Project ID"),
    is_enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List escalation rules.
    
    Args:
        workspace_id: Workspace ID
        project_id: Project ID (optional)
        is_enabled: Filter by enabled status (optional)
        session: Database session
        
    Returns:
        List of escalation rules
    """
    try:
        from sqlalchemy import select, or_
        
        query = select(EscalationRule).where(
            EscalationRule.workspace_id == workspace_id
        )
        
        if project_id:
            query = query.where(
                or_(
                    EscalationRule.project_id == project_id,
                    EscalationRule.project_id.is_(None),
                )
            )
        
        if is_enabled is not None:
            query = query.where(EscalationRule.is_enabled == is_enabled)
        
        query = query.order_by(EscalationRule.priority.desc())
        
        result = await session.execute(query)
        rules = result.scalars().all()
        
        return rules
        
    except Exception as e:
        logger.error(f"Failed to list escalation rules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules/{rule_id}", response_model=EscalationRuleResponse)
async def get_escalation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get an escalation rule by ID.
    
    Args:
        rule_id: Rule ID
        session: Database session
        
    Returns:
        Escalation rule
    """
    try:
        from sqlalchemy import select
        
        result = await session.execute(
            select(EscalationRule).where(EscalationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
        
        return rule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get escalation rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rules/{rule_id}", response_model=EscalationRuleResponse)
async def update_escalation_rule(
    rule_id: str,
    rule_data: EscalationRuleUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Update an escalation rule.
    
    Args:
        rule_id: Rule ID
        rule_data: Updated rule data
        session: Database session
        
    Returns:
        Updated escalation rule
    """
    try:
        escalation_service = EscalationService()
        
        # Convert to dict, exclude None values
        updates = rule_data.dict(exclude_unset=True)
        
        rule = await escalation_service.update_rule(session, rule_id, **updates)
        
        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
        
        await session.commit()
        
        logger.info(f"Updated escalation rule: {rule_id}")
        return rule
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update escalation rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_escalation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete an escalation rule.
    
    Args:
        rule_id: Rule ID
        session: Database session
        
    Returns:
        Success message
    """
    try:
        escalation_service = EscalationService()
        
        success = await escalation_service.delete_rule(session, rule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
        
        await session.commit()
        
        logger.info(f"Deleted escalation rule: {rule_id}")
        return {"message": "Rule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete escalation rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events", response_model=List[EscalationEventResponse])
async def list_escalation_events(
    workspace_id: str = Query(..., description="Workspace ID"),
    project_id: Optional[str] = Query(None, description="Project ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List escalation events.
    
    Args:
        workspace_id: Workspace ID
        project_id: Project ID (optional)
        status: Filter by status (optional)
        severity: Filter by severity (optional)
        limit: Maximum number of events
        offset: Offset for pagination
        session: Database session
        
    Returns:
        List of escalation events
    """
    try:
        from sqlalchemy import select
        
        query = select(EscalationEvent).where(
            EscalationEvent.workspace_id == workspace_id
        )
        
        if project_id:
            query = query.where(EscalationEvent.project_id == project_id)
        
        if status:
            query = query.where(EscalationEvent.status == EscalationStatus(status))
        
        if severity:
            query = query.where(EscalationEvent.severity == EscalationSeverity(severity))
        
        query = query.order_by(EscalationEvent.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        events = result.scalars().all()
        
        return events
        
    except Exception as e:
        logger.error(f"Failed to list escalation events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_id}", response_model=EscalationEventResponse)
async def get_escalation_event(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get an escalation event by ID.
    
    Args:
        event_id: Event ID
        session: Database session
        
    Returns:
        Escalation event
    """
    try:
        from sqlalchemy import select
        
        result = await session.execute(
            select(EscalationEvent).where(EscalationEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        return event
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get escalation event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/{event_id}/resolve")
async def resolve_escalation_event(
    event_id: str,
    resolution_data: Dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
):
    """
    Resolve an escalation event.
    
    Args:
        event_id: Event ID
        resolution_data: Resolution details
        session: Database session
        
    Returns:
        Success message
    """
    try:
        escalation_service = EscalationService()
        
        await escalation_service.resolve_escalation(session, event_id, resolution_data)
        await session.commit()
        
        logger.info(f"Resolved escalation event: {event_id}")
        return {"message": "Escalation resolved successfully"}
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to resolve escalation event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/{event_id}/fail")
async def fail_escalation_event(
    event_id: str,
    error_message: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Mark an escalation event as failed.
    
    Args:
        event_id: Event ID
        error_message: Error message
        session: Database session
        
    Returns:
        Success message
    """
    try:
        escalation_service = EscalationService()
        
        await escalation_service.fail_escalation(session, event_id, error_message)
        await session.commit()
        
        logger.info(f"Failed escalation event: {event_id}")
        return {"message": "Escalation marked as failed"}
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to fail escalation event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=EscalationStatsResponse)
async def get_escalation_stats(
    workspace_id: str = Query(..., description="Workspace ID"),
    project_id: Optional[str] = Query(None, description="Project ID"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get escalation statistics.
    
    Args:
        workspace_id: Workspace ID
        project_id: Project ID (optional)
        session: Database session
        
    Returns:
        Escalation statistics
    """
    try:
        escalation_service = EscalationService()
        
        stats = await escalation_service.get_stats(session, workspace_id, project_id)
        
        return {
            "total_escalations": stats.total_escalations,
            "pending": stats.pending,
            "assigned": stats.assigned,
            "in_progress": stats.in_progress,
            "resolved": stats.resolved,
            "failed": stats.failed,
            "cancelled": stats.cancelled,
            "avg_time_to_assign_seconds": stats.avg_time_to_assign_seconds,
            "avg_time_to_resolve_seconds": stats.avg_time_to_resolve_seconds,
            "resolution_rate": stats.resolution_rate,
            "by_severity": stats.by_severity,
            "by_reason": stats.by_reason,
        }
        
    except Exception as e:
        logger.error(f"Failed to get escalation stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
