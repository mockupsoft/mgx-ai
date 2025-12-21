# -*- coding: utf-8 -*-
"""
Escalation Tracker

Tracks escalation history and performance metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from backend.db.models import (
    EscalationEvent,
    EscalationMetric,
    EscalationStatus,
    EscalationSeverity,
    EscalationReason,
)

logger = logging.getLogger(__name__)


class EscalationStats:
    """Container for escalation statistics."""
    
    def __init__(
        self,
        total_escalations: int = 0,
        pending: int = 0,
        assigned: int = 0,
        in_progress: int = 0,
        resolved: int = 0,
        failed: int = 0,
        cancelled: int = 0,
        avg_time_to_assign_seconds: float = 0.0,
        avg_time_to_resolve_seconds: float = 0.0,
        resolution_rate: float = 0.0,
        by_severity: Optional[Dict[str, int]] = None,
        by_reason: Optional[Dict[str, int]] = None,
    ):
        self.total_escalations = total_escalations
        self.pending = pending
        self.assigned = assigned
        self.in_progress = in_progress
        self.resolved = resolved
        self.failed = failed
        self.cancelled = cancelled
        self.avg_time_to_assign_seconds = avg_time_to_assign_seconds
        self.avg_time_to_resolve_seconds = avg_time_to_resolve_seconds
        self.resolution_rate = resolution_rate
        self.by_severity = by_severity or {}
        self.by_reason = by_reason or {}


class EscalationTracker:
    """
    Tracks escalation history and performance metrics.
    
    Provides:
    - Escalation event tracking
    - Performance metrics collection
    - Historical analysis
    - Pattern detection
    """
    
    def __init__(self):
        """Initialize the escalation tracker."""
        logger.info("EscalationTracker initialized")
    
    async def record_metric(
        self,
        session: AsyncSession,
        escalation_event_id: str,
        workspace_id: str,
        metric_name: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
        metric_tags: Optional[Dict[str, Any]] = None,
    ) -> EscalationMetric:
        """
        Record a performance metric for an escalation.
        
        Args:
            session: Database session
            escalation_event_id: Escalation event ID
            workspace_id: Workspace ID
            metric_name: Metric name
            metric_value: Metric value
            metric_unit: Metric unit (optional)
            metric_tags: Additional tags (optional)
            
        Returns:
            Created metric record
        """
        metric = EscalationMetric(
            escalation_event_id=escalation_event_id,
            workspace_id=workspace_id,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            metric_tags=metric_tags or {},
        )
        
        session.add(metric)
        await session.flush()
        
        logger.debug(
            f"Recorded metric {metric_name}={metric_value} "
            f"for escalation {escalation_event_id}"
        )
        
        return metric
    
    async def get_escalation_stats(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> EscalationStats:
        """
        Get escalation statistics.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Project ID (optional)
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            Escalation statistics
        """
        # Build base query
        query = select(EscalationEvent).where(
            EscalationEvent.workspace_id == workspace_id
        )
        
        if project_id:
            query = query.where(EscalationEvent.project_id == project_id)
        
        if start_date:
            query = query.where(EscalationEvent.created_at >= start_date)
        
        if end_date:
            query = query.where(EscalationEvent.created_at <= end_date)
        
        # Get all events
        result = await session.execute(query)
        events = result.scalars().all()
        
        # Calculate statistics
        stats = EscalationStats()
        stats.total_escalations = len(events)
        
        if stats.total_escalations == 0:
            return stats
        
        # Count by status
        status_counts = {}
        for event in events:
            status = event.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        stats.pending = status_counts.get("pending", 0)
        stats.assigned = status_counts.get("assigned", 0)
        stats.in_progress = status_counts.get("in_progress", 0)
        stats.resolved = status_counts.get("resolved", 0)
        stats.failed = status_counts.get("failed", 0)
        stats.cancelled = status_counts.get("cancelled", 0)
        
        # Calculate resolution rate
        if stats.total_escalations > 0:
            stats.resolution_rate = stats.resolved / stats.total_escalations
        
        # Calculate average times
        assign_times = [
            e.time_to_assign_seconds for e in events
            if e.time_to_assign_seconds is not None
        ]
        if assign_times:
            stats.avg_time_to_assign_seconds = sum(assign_times) / len(assign_times)
        
        resolve_times = [
            e.time_to_resolve_seconds for e in events
            if e.time_to_resolve_seconds is not None
        ]
        if resolve_times:
            stats.avg_time_to_resolve_seconds = sum(resolve_times) / len(resolve_times)
        
        # Count by severity
        for event in events:
            severity = event.severity.value
            stats.by_severity[severity] = stats.by_severity.get(severity, 0) + 1
        
        # Count by reason
        for event in events:
            reason = event.reason.value
            stats.by_reason[reason] = stats.by_reason.get(reason, 0) + 1
        
        return stats
    
    async def get_escalation_history(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EscalationEvent]:
        """
        Get escalation history.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Project ID (optional)
            limit: Maximum number of records
            offset: Offset for pagination
            
        Returns:
            List of escalation events
        """
        query = select(EscalationEvent).where(
            EscalationEvent.workspace_id == workspace_id
        )
        
        if project_id:
            query = query.where(EscalationEvent.project_id == project_id)
        
        query = query.order_by(EscalationEvent.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        events = result.scalars().all()
        
        return events
    
    async def detect_patterns(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str] = None,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Detect patterns in escalation data.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Project ID (optional)
            lookback_days: Number of days to look back
            
        Returns:
            Dictionary of detected patterns
        """
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        query = select(EscalationEvent).where(
            EscalationEvent.workspace_id == workspace_id,
            EscalationEvent.created_at >= start_date,
        )
        
        if project_id:
            query = query.where(EscalationEvent.project_id == project_id)
        
        result = await session.execute(query)
        events = result.scalars().all()
        
        if not events:
            return {}
        
        patterns = {}
        
        # Detect frequently escalating agents
        source_agents = {}
        for event in events:
            if event.source_agent_id:
                source_agents[event.source_agent_id] = source_agents.get(
                    event.source_agent_id, 0
                ) + 1
        
        if source_agents:
            top_source = max(source_agents.items(), key=lambda x: x[1])
            patterns["most_escalating_agent"] = {
                "agent_id": top_source[0],
                "count": top_source[1],
            }
        
        # Detect most common reasons
        reasons = {}
        for event in events:
            reasons[event.reason.value] = reasons.get(event.reason.value, 0) + 1
        
        if reasons:
            top_reason = max(reasons.items(), key=lambda x: x[1])
            patterns["most_common_reason"] = {
                "reason": top_reason[0],
                "count": top_reason[1],
                "percentage": (top_reason[1] / len(events)) * 100,
            }
        
        # Detect peak hours
        hour_counts = {}
        for event in events:
            hour = event.created_at.hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        if hour_counts:
            peak_hour = max(hour_counts.items(), key=lambda x: x[1])
            patterns["peak_escalation_hour"] = {
                "hour": peak_hour[0],
                "count": peak_hour[1],
            }
        
        # Calculate trends
        patterns["total_escalations"] = len(events)
        patterns["average_per_day"] = len(events) / lookback_days
        
        # Resolution efficiency
        resolved = sum(1 for e in events if e.status == EscalationStatus.RESOLVED)
        patterns["resolution_rate"] = (resolved / len(events)) * 100
        
        logger.info(f"Detected {len(patterns)} escalation patterns")
        return patterns
    
    async def get_agent_performance(
        self,
        session: AsyncSession,
        agent_id: str,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific agent.
        
        Args:
            session: Database session
            agent_id: Agent instance ID
            lookback_days: Number of days to look back
            
        Returns:
            Agent performance metrics
        """
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get escalations where agent was the target (handled escalations)
        query = select(EscalationEvent).where(
            EscalationEvent.target_agent_id == agent_id,
            EscalationEvent.created_at >= start_date,
        )
        
        result = await session.execute(query)
        handled_events = result.scalars().all()
        
        if not handled_events:
            return {
                "agent_id": agent_id,
                "escalations_handled": 0,
                "resolution_rate": 0.0,
                "avg_resolution_time_seconds": 0.0,
            }
        
        # Calculate metrics
        total_handled = len(handled_events)
        resolved = sum(
            1 for e in handled_events
            if e.status == EscalationStatus.RESOLVED
        )
        
        resolution_times = [
            e.time_to_resolve_seconds
            for e in handled_events
            if e.time_to_resolve_seconds is not None
        ]
        
        return {
            "agent_id": agent_id,
            "escalations_handled": total_handled,
            "resolution_rate": (resolved / total_handled) * 100 if total_handled > 0 else 0.0,
            "avg_resolution_time_seconds": (
                sum(resolution_times) / len(resolution_times)
                if resolution_times else 0.0
            ),
            "resolved": resolved,
            "failed": sum(1 for e in handled_events if e.status == EscalationStatus.FAILED),
        }


__all__ = ["EscalationTracker", "EscalationStats"]
