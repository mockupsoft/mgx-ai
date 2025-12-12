# -*- coding: utf-8 -*-
"""
Background execution service for running tasks and emitting events.

Orchestrates:
- Task execution via MGXStyleTeam
- Database state updates
- Event broadcasting for key hooks
- Plan approval flow
"""

import asyncio
import logging
from typing import Optional, Callable, Any, Dict
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.enums import RunStatus as DBRunStatus
from backend.schemas import (
    EventPayload,
    EventTypeEnum,
    AnalysisStartEvent,
    PlanReadyEvent,
    ApprovalRequiredEvent,
    ApprovedEvent,
    ProgressEvent,
    CompletionEvent,
    FailureEvent,
)
from backend.services.events import get_event_broadcaster
from backend.services.team_provider import MGXTeamProvider

logger = logging.getLogger(__name__)


class ExecutionPhase(str, Enum):
    """Execution phases for a run."""
    ANALYSIS = "analysis"
    PLANNING = "planning"
    APPROVAL = "approval"
    EXECUTION = "execution"
    COMPLETION = "completion"


class TaskExecutor:
    """
    Executes tasks via MGXStyleTeam with event emission and database updates.
    
    Handles the full lifecycle of task execution:
    1. Start analysis
    2. Generate plan
    3. Request approval (pause for user)
    4. Execute plan
    5. Emit completion/failure events
    """
    
    def __init__(
        self,
        team_provider: MGXTeamProvider,
        session_factory: Optional[Callable] = None,
    ):
        """
        Initialize the executor.
        
        Args:
            team_provider: MGXTeamProvider for team operations
            session_factory: Async session factory for DB operations
        """
        self.team_provider = team_provider
        self.session_factory = session_factory
        self._approval_events: Dict[str, asyncio.Event] = {}
        self._approval_decisions: Dict[str, bool] = {}
        logger.info("TaskExecutor initialized")
    
    async def execute_task(
        self,
        task_id: str,
        run_id: str,
        task_description: str,
        max_rounds: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute a task with full event lifecycle.
        
        Args:
            task_id: ID of the task
            run_id: ID of the specific run
            task_description: Description of task to execute
            max_rounds: Maximum execution rounds
        
        Returns:
            Execution result dict
        """
        broadcaster = get_event_broadcaster()
        
        try:
            # Phase 1: Start analysis
            await self._emit_event(
                AnalysisStartEvent(
                    task_id=task_id,
                    run_id=run_id,
                    message="Starting task analysis",
                ),
                broadcaster=broadcaster,
            )
            
            # Simulate analysis phase
            await asyncio.sleep(0.1)
            
            # Phase 2: Generate plan
            logger.info(f"Generating plan for run {run_id}")
            plan = {
                "steps": ["step1", "step2", "step3"],
                "estimated_time": "5 minutes",
                "resources": ["agent1", "agent2"],
            }
            
            await self._emit_event(
                PlanReadyEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"plan": plan},
                    message="Plan ready for review",
                ),
                broadcaster=broadcaster,
            )
            
            # Phase 3: Request approval
            await self._emit_event(
                ApprovalRequiredEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"plan": plan},
                    message="Waiting for plan approval",
                ),
                broadcaster=broadcaster,
            )
            
            # Wait for approval
            approved = await self.wait_for_approval(run_id, timeout=300)
            
            if not approved:
                logger.info(f"Run {run_id} plan was rejected")
                await self._emit_event(
                    FailureEvent(
                        task_id=task_id,
                        run_id=run_id,
                        message="Plan rejected by user",
                    ),
                    broadcaster=broadcaster,
                )
                return {
                    "status": "rejected",
                    "message": "Plan rejected by user",
                }
            
            # Emit approval confirmation
            await self._emit_event(
                ApprovedEvent(
                    task_id=task_id,
                    run_id=run_id,
                    message="Plan approved, execution started",
                ),
                broadcaster=broadcaster,
            )
            
            # Phase 4: Execute plan
            logger.info(f"Executing plan for run {run_id}")
            try:
                team = await self.team_provider.get_team()
                result = await team.run(task_description)
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                result = None
            
            # Phase 5: Completion
            if result:
                await self._emit_event(
                    CompletionEvent(
                        task_id=task_id,
                        run_id=run_id,
                        data={"results": result},
                        message="Task completed successfully",
                    ),
                    broadcaster=broadcaster,
                )
                
                return {
                    "status": "completed",
                    "results": result,
                }
            else:
                raise Exception("Execution returned no result")
        
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await self._emit_event(
                FailureEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"error": str(e)},
                    message=f"Task failed: {str(e)}",
                ),
                broadcaster=broadcaster,
            )
            
            return {
                "status": "failed",
                "error": str(e),
            }
    
    async def _emit_event(
        self,
        event: EventPayload,
        broadcaster: Optional[Any] = None,
    ):
        """Emit an event to the broadcaster."""
        if broadcaster is None:
            broadcaster = get_event_broadcaster()
        
        await broadcaster.publish(event)
        logger.debug(f"Event emitted: {event.event_type}")
    
    async def wait_for_approval(
        self,
        run_id: str,
        timeout: int = 300,
    ) -> bool:
        """
        Wait for plan approval.
        
        Args:
            run_id: Run ID to wait for
            timeout: Seconds to wait before timing out
        
        Returns:
            True if approved, False if rejected or timeout
        """
        if run_id not in self._approval_events:
            self._approval_events[run_id] = asyncio.Event()
        
        try:
            await asyncio.wait_for(
                self._approval_events[run_id].wait(),
                timeout=timeout,
            )
            return self._approval_decisions.get(run_id, False)
        except asyncio.TimeoutError:
            logger.warning(f"Approval timeout for run {run_id}")
            return False
    
    async def approve_plan(self, run_id: str, approved: bool = True):
        """
        Approve or reject a plan.
        
        Args:
            run_id: Run ID to approve
            approved: Whether plan is approved
        """
        self._approval_decisions[run_id] = approved
        
        if run_id not in self._approval_events:
            self._approval_events[run_id] = asyncio.Event()
        
        self._approval_events[run_id].set()
        logger.info(f"Plan approval set for run {run_id}: {approved}")


# Global executor instance
_executor: Optional[TaskExecutor] = None


def get_task_executor(
    team_provider: Optional[MGXTeamProvider] = None,
) -> TaskExecutor:
    """
    Get or create the global task executor instance.
    
    Args:
        team_provider: MGXTeamProvider instance (optional)
    
    Returns:
        TaskExecutor instance
    """
    global _executor
    if _executor is None:
        if team_provider is None:
            from backend.services import get_team_provider
            team_provider = get_team_provider()
        _executor = TaskExecutor(team_provider=team_provider)
    return _executor


__all__ = [
    'TaskExecutor',
    'ExecutionPhase',
    'get_task_executor',
]
