# -*- coding: utf-8 -*-
"""
Escalation Service

Main orchestration service for escalation logic.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    EscalationEvent,
    EscalationRule,
    EscalationStatus,
    EscalationSeverity,
    EscalationReason,
    AgentInstance,
)

from .rules_engine import EscalationRulesEngine, RuleEvaluationContext, RuleMatch
from .priority_scorer import PriorityScorer, ComplexityMetrics
from .router import EscalationRouter
from .notifier import EscalationNotifier
from .tracker import EscalationTracker, EscalationStats

logger = logging.getLogger(__name__)


class EscalationService:
    """
    Main escalation service orchestrating the escalation workflow.
    
    Workflow:
    1. Evaluate rules against context
    2. Score task complexity and priority
    3. Route to appropriate supervisor agent
    4. Send notifications
    5. Track metrics and history
    """
    
    def __init__(
        self,
        rules_engine: Optional[EscalationRulesEngine] = None,
        priority_scorer: Optional[PriorityScorer] = None,
        router: Optional[EscalationRouter] = None,
        notifier: Optional[EscalationNotifier] = None,
        tracker: Optional[EscalationTracker] = None,
    ):
        """
        Initialize the escalation service.
        
        Args:
            rules_engine: Rules engine (optional, creates default if None)
            priority_scorer: Priority scorer (optional, creates default if None)
            router: Escalation router (optional, creates default if None)
            notifier: Escalation notifier (optional, creates default if None)
            tracker: Escalation tracker (optional, creates default if None)
        """
        self.rules_engine = rules_engine or EscalationRulesEngine()
        self.priority_scorer = priority_scorer or PriorityScorer()
        self.router = router or EscalationRouter()
        self.notifier = notifier or EscalationNotifier()
        self.tracker = tracker or EscalationTracker()
        
        logger.info("EscalationService initialized")
    
    async def check_escalation(
        self,
        session: AsyncSession,
        context: RuleEvaluationContext,
        task_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[EscalationEvent]:
        """
        Check if a task should be escalated and create escalation if needed.
        
        Args:
            session: Database session
            context: Rule evaluation context
            task_data: Task data for complexity scoring (optional)
            
        Returns:
            Created escalation event or None if no escalation needed
        """
        # Evaluate rules
        matches = await self.rules_engine.evaluate_rules(session, context)
        
        if not matches:
            logger.debug("No escalation rules matched")
            return None
        
        # Take highest priority match
        rule_match = matches[0]
        
        logger.info(
            f"Escalation triggered by rule '{rule_match.rule.name}' "
            f"(severity: {rule_match.rule.severity.value})"
        )
        
        # Create escalation event
        event = await self._create_escalation_event(
            session, context, rule_match
        )
        
        # Route to supervisor agent if auto-assign is enabled
        if rule_match.rule.auto_assign:
            target_agent = await self.router.route_escalation(
                session,
                context.workspace_id,
                context.project_id,
                rule_match.rule,
                rule_match.trigger_data,
            )
            
            if target_agent:
                await self.assign_escalation(session, event, target_agent)
        
        # Send notifications
        await self.notifier.notify_escalation_created(event, rule_match.rule)
        
        # Record metrics
        if task_data:
            complexity = self.priority_scorer.calculate_complexity(task_data)
            await self.tracker.record_metric(
                session,
                event.id,
                context.workspace_id,
                "complexity_score",
                complexity.overall_score,
            )
        
        return event
    
    async def _create_escalation_event(
        self,
        session: AsyncSession,
        context: RuleEvaluationContext,
        rule_match: RuleMatch,
    ) -> EscalationEvent:
        """Create an escalation event."""
        event = EscalationEvent(
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            rule_id=rule_match.rule.id,
            task_id=context.task_id,
            task_run_id=context.task_run_id,
            workflow_execution_id=context.workflow_execution_id,
            workflow_step_execution_id=context.workflow_step_execution_id,
            severity=rule_match.rule.severity,
            reason=rule_match.rule.reason,
            status=EscalationStatus.PENDING,
            trigger_data=rule_match.trigger_data,
            context_data={
                "complexity_score": context.complexity_score,
                "error_count": context.error_count,
                "error_rate": context.error_rate,
                "retry_count": context.retry_count,
                "execution_duration_seconds": context.execution_duration_seconds,
                "resource_usage": context.resource_usage,
                "custom_metrics": context.custom_metrics,
                "matched_conditions": rule_match.matched_conditions,
            },
        )
        
        session.add(event)
        await session.flush()
        
        logger.info(f"Created escalation event {event.id}")
        return event
    
    async def assign_escalation(
        self,
        session: AsyncSession,
        event: EscalationEvent,
        target_agent: AgentInstance,
    ) -> None:
        """
        Assign an escalation to a supervisor agent.
        
        Args:
            session: Database session
            event: Escalation event
            target_agent: Target agent instance
        """
        event.target_agent_id = target_agent.id
        event.status = EscalationStatus.ASSIGNED
        event.assigned_at = datetime.utcnow()
        
        # Calculate time to assign
        if event.created_at:
            delta = event.assigned_at - event.created_at
            event.time_to_assign_seconds = int(delta.total_seconds())
        
        await session.flush()
        
        # Send notification
        await self.notifier.notify_escalation_assigned(event, target_agent.id)
        
        # Record metric
        if event.time_to_assign_seconds:
            await self.tracker.record_metric(
                session,
                event.id,
                event.workspace_id,
                "time_to_assign",
                event.time_to_assign_seconds,
                "seconds",
            )
        
        logger.info(
            f"Assigned escalation {event.id} to agent {target_agent.id}"
        )
    
    async def resolve_escalation(
        self,
        session: AsyncSession,
        event_id: str,
        resolution_data: Dict[str, Any],
    ) -> None:
        """
        Mark an escalation as resolved.
        
        Args:
            session: Database session
            event_id: Escalation event ID
            resolution_data: Resolution details
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(EscalationEvent).where(EscalationEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            logger.warning(f"Escalation event {event_id} not found")
            return
        
        event.status = EscalationStatus.RESOLVED
        event.resolved_at = datetime.utcnow()
        event.resolution_data = resolution_data
        
        # Calculate time to resolve
        if event.created_at:
            delta = event.resolved_at - event.created_at
            event.time_to_resolve_seconds = int(delta.total_seconds())
        
        await session.flush()
        
        # Send notification
        await self.notifier.notify_escalation_resolved(event, resolution_data)
        
        # Record metrics
        if event.time_to_resolve_seconds:
            await self.tracker.record_metric(
                session,
                event.id,
                event.workspace_id,
                "time_to_resolve",
                event.time_to_resolve_seconds,
                "seconds",
            )
        
        logger.info(f"Resolved escalation {event.id}")
    
    async def fail_escalation(
        self,
        session: AsyncSession,
        event_id: str,
        error_message: str,
    ) -> None:
        """
        Mark an escalation as failed.
        
        Args:
            session: Database session
            event_id: Escalation event ID
            error_message: Error message
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(EscalationEvent).where(EscalationEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            logger.warning(f"Escalation event {event_id} not found")
            return
        
        event.status = EscalationStatus.FAILED
        event.error_message = error_message
        event.resolved_at = datetime.utcnow()
        
        # Calculate time to failure
        if event.created_at:
            delta = event.resolved_at - event.created_at
            event.time_to_resolve_seconds = int(delta.total_seconds())
        
        await session.flush()
        
        # Send notification
        await self.notifier.notify_escalation_failed(event, error_message)
        
        logger.warning(f"Failed escalation {event.id}: {error_message}")
    
    async def cancel_escalation(
        self,
        session: AsyncSession,
        event_id: str,
    ) -> None:
        """
        Cancel an escalation.
        
        Args:
            session: Database session
            event_id: Escalation event ID
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(EscalationEvent).where(EscalationEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            logger.warning(f"Escalation event {event_id} not found")
            return
        
        event.status = EscalationStatus.CANCELLED
        await session.flush()
        
        logger.info(f"Cancelled escalation {event.id}")
    
    async def get_stats(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str] = None,
    ) -> EscalationStats:
        """
        Get escalation statistics.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Project ID (optional)
            
        Returns:
            Escalation statistics
        """
        return await self.tracker.get_escalation_stats(
            session, workspace_id, project_id
        )
    
    async def create_rule(
        self,
        session: AsyncSession,
        workspace_id: str,
        name: str,
        rule_type: str,
        condition: Dict[str, Any],
        severity: str,
        reason: str,
        project_id: Optional[str] = None,
        description: Optional[str] = None,
        priority: int = 0,
        target_agent_type: Optional[str] = None,
        auto_assign: bool = True,
        notify_websocket: bool = True,
        notify_email: bool = False,
        notify_slack: bool = False,
        notification_config: Optional[Dict[str, Any]] = None,
    ) -> EscalationRule:
        """
        Create a new escalation rule.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            name: Rule name
            rule_type: Rule type
            condition: Rule condition
            severity: Escalation severity
            reason: Escalation reason
            project_id: Project ID (optional)
            description: Rule description (optional)
            priority: Rule priority (default: 0)
            target_agent_type: Target agent type (optional)
            auto_assign: Auto-assign to supervisor (default: True)
            notify_websocket: Send WebSocket notifications (default: True)
            notify_email: Send email notifications (default: False)
            notify_slack: Send Slack notifications (default: False)
            notification_config: Notification configuration (optional)
            
        Returns:
            Created escalation rule
        """
        from backend.db.models import EscalationRuleType
        
        rule = EscalationRule(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            description=description,
            rule_type=EscalationRuleType(rule_type),
            condition=condition,
            severity=EscalationSeverity(severity),
            reason=EscalationReason(reason),
            priority=priority,
            target_agent_type=target_agent_type,
            auto_assign=auto_assign,
            notify_websocket=notify_websocket,
            notify_email=notify_email,
            notify_slack=notify_slack,
            notification_config=notification_config or {},
        )
        
        session.add(rule)
        await session.flush()
        
        logger.info(f"Created escalation rule {rule.id}: {name}")
        return rule
    
    async def update_rule(
        self,
        session: AsyncSession,
        rule_id: str,
        **updates: Any,
    ) -> Optional[EscalationRule]:
        """
        Update an escalation rule.
        
        Args:
            session: Database session
            rule_id: Rule ID
            **updates: Fields to update
            
        Returns:
            Updated rule or None if not found
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(EscalationRule).where(EscalationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            logger.warning(f"Escalation rule {rule_id} not found")
            return None
        
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        await session.flush()
        
        logger.info(f"Updated escalation rule {rule_id}")
        return rule
    
    async def delete_rule(
        self,
        session: AsyncSession,
        rule_id: str,
    ) -> bool:
        """
        Delete an escalation rule.
        
        Args:
            session: Database session
            rule_id: Rule ID
            
        Returns:
            True if deleted, False if not found
        """
        from sqlalchemy import select, delete
        
        result = await session.execute(
            select(EscalationRule).where(EscalationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            logger.warning(f"Escalation rule {rule_id} not found")
            return False
        
        await session.execute(
            delete(EscalationRule).where(EscalationRule.id == rule_id)
        )
        await session.flush()
        
        logger.info(f"Deleted escalation rule {rule_id}")
        return True


__all__ = ["EscalationService"]
