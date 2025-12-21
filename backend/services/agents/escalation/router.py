# -*- coding: utf-8 -*-
"""
Escalation Router

Routes escalations to appropriate supervisor/manager agents.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import (
    AgentDefinition,
    AgentInstance,
    AgentStatus,
    EscalationRule,
)

logger = logging.getLogger(__name__)


class AgentCandidate:
    """Represents a candidate agent for escalation."""
    
    def __init__(
        self,
        instance: AgentInstance,
        definition: AgentDefinition,
        match_score: float = 0.0,
    ):
        self.instance = instance
        self.definition = definition
        self.match_score = match_score


class EscalationRouter:
    """
    Routes escalations to appropriate supervisor/manager agents.
    
    Selects agents based on:
    - Agent capabilities
    - Current workload
    - Past performance
    - Specialization
    """
    
    def __init__(self):
        """Initialize the escalation router."""
        logger.info("EscalationRouter initialized")
    
    async def route_escalation(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str],
        rule: EscalationRule,
        trigger_data: Dict[str, Any],
    ) -> Optional[AgentInstance]:
        """
        Route an escalation to an appropriate agent.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Project ID (optional)
            rule: Escalation rule that triggered
            trigger_data: Data that triggered the escalation
            
        Returns:
            Selected agent instance or None if no suitable agent found
        """
        # Find candidate agents
        candidates = await self._find_candidate_agents(
            session, workspace_id, project_id, rule
        )
        
        if not candidates:
            logger.warning(f"No candidate agents found for escalation")
            return None
        
        # Score and rank candidates
        ranked_candidates = await self._rank_candidates(
            candidates, rule, trigger_data
        )
        
        if not ranked_candidates:
            return None
        
        # Select best candidate
        best_candidate = ranked_candidates[0]
        logger.info(
            f"Selected agent {best_candidate.instance.id} "
            f"(score: {best_candidate.match_score:.2f})"
        )
        
        return best_candidate.instance
    
    async def _find_candidate_agents(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str],
        rule: EscalationRule,
    ) -> List[AgentCandidate]:
        """Find candidate agents for escalation."""
        # Query for supervisor/manager agents
        query = select(AgentInstance).where(
            AgentInstance.workspace_id == workspace_id,
            AgentInstance.status.in_([AgentStatus.IDLE, AgentStatus.ACTIVE]),
        )
        
        if project_id:
            query = query.where(AgentInstance.project_id == project_id)
        
        result = await session.execute(query)
        instances = result.scalars().all()
        
        candidates = []
        for instance in instances:
            # Get agent definition
            def_result = await session.execute(
                select(AgentDefinition).where(
                    AgentDefinition.id == instance.definition_id
                )
            )
            definition = def_result.scalar_one_or_none()
            
            if not definition or not definition.is_enabled:
                continue
            
            # Check if agent is a supervisor/manager type
            agent_type = definition.agent_type.lower()
            is_supervisor = any(
                keyword in agent_type
                for keyword in ["supervisor", "manager", "lead", "senior"]
            )
            
            if not is_supervisor:
                continue
            
            # Check if agent matches target type if specified
            if rule.target_agent_type:
                if rule.target_agent_type.lower() not in agent_type:
                    continue
            
            candidates.append(AgentCandidate(instance, definition))
        
        logger.debug(f"Found {len(candidates)} candidate agents")
        return candidates
    
    async def _rank_candidates(
        self,
        candidates: List[AgentCandidate],
        rule: EscalationRule,
        trigger_data: Dict[str, Any],
    ) -> List[AgentCandidate]:
        """Rank candidates by suitability."""
        for candidate in candidates:
            score = await self._calculate_match_score(
                candidate, rule, trigger_data
            )
            candidate.match_score = score
        
        # Sort by score (highest first)
        ranked = sorted(candidates, key=lambda c: c.match_score, reverse=True)
        return [c for c in ranked if c.match_score > 0]
    
    async def _calculate_match_score(
        self,
        candidate: AgentCandidate,
        rule: EscalationRule,
        trigger_data: Dict[str, Any],
    ) -> float:
        """Calculate match score for a candidate."""
        score = 0.0
        
        # Base score for being available
        if candidate.instance.status == AgentStatus.IDLE:
            score += 0.3
        elif candidate.instance.status == AgentStatus.ACTIVE:
            score += 0.2
        
        # Score based on capabilities
        capabilities = candidate.definition.capabilities or []
        required_capabilities = trigger_data.get("required_capabilities", [])
        
        if required_capabilities:
            matching_caps = set(capabilities) & set(required_capabilities)
            if matching_caps:
                score += 0.3 * (len(matching_caps) / len(required_capabilities))
        else:
            # If no specific requirements, general capabilities are good
            score += 0.2
        
        # Score based on agent configuration
        config = candidate.instance.config or {}
        
        # Prefer agents with higher max concurrency
        max_concurrent = config.get("max_concurrent_tasks", 1)
        if max_concurrent > 5:
            score += 0.15
        elif max_concurrent > 3:
            score += 0.10
        elif max_concurrent > 1:
            score += 0.05
        
        # Prefer agents with specific escalation handling
        if config.get("handles_escalations", False):
            score += 0.25
        
        # Score based on past performance (if available in metadata)
        metadata = candidate.instance.meta_data or {}
        success_rate = metadata.get("escalation_success_rate", 0.5)
        score += 0.2 * success_rate
        
        return min(score, 1.0)
    
    async def get_escalation_queue_size(
        self,
        session: AsyncSession,
        agent_id: str,
    ) -> int:
        """
        Get the current escalation queue size for an agent.
        
        Args:
            session: Database session
            agent_id: Agent instance ID
            
        Returns:
            Number of pending escalations assigned to this agent
        """
        from backend.db.models import EscalationEvent, EscalationStatus
        
        query = select(EscalationEvent).where(
            EscalationEvent.target_agent_id == agent_id,
            EscalationEvent.status.in_([
                EscalationStatus.PENDING,
                EscalationStatus.ASSIGNED,
                EscalationStatus.IN_PROGRESS,
            ]),
        )
        
        result = await session.execute(query)
        events = result.scalars().all()
        
        return len(events)
    
    async def balance_load(
        self,
        candidates: List[AgentCandidate],
        session: AsyncSession,
    ) -> List[AgentCandidate]:
        """
        Balance load across candidate agents.
        
        Args:
            candidates: List of candidate agents
            session: Database session
            
        Returns:
            Load-balanced list of candidates
        """
        # Get current queue sizes
        for candidate in candidates:
            queue_size = await self.get_escalation_queue_size(
                session, candidate.instance.id
            )
            
            # Adjust score based on queue size
            load_penalty = min(queue_size * 0.1, 0.5)
            candidate.match_score -= load_penalty
        
        # Re-sort by adjusted score
        return sorted(
            candidates,
            key=lambda c: c.match_score,
            reverse=True
        )


__all__ = ["EscalationRouter", "AgentCandidate"]
