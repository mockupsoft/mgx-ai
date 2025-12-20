# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Multi-Agent Controller

Coordinates agent assignments, resource management, and failover logic for workflow steps.
Interfaces with AgentRegistry and SharedContextService to provide robust multi-agent execution.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import (
    AgentDefinition,
    AgentInstance,
    WorkflowStep,
    WorkflowStepExecution,
    WorkflowStepStatus,
    AgentStatus,
)
from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster
from backend.services.agents.registry import AgentRegistry
from backend.services.agents.context import SharedContextService

# Import WorkflowContext using TYPE_CHECKING to avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .engine import WorkflowContext

logger = logging.getLogger(__name__)


class AssignmentStrategy(str, Enum):
    """Agent assignment strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    RESOURCE_BASED = "resource_based"


class AgentAssignment:
    """Represents an agent assignment for a workflow step."""
    
    def __init__(
        self,
        instance_id: str,
        definition_id: str,
        agent_instance: AgentInstance,
        agent_definition: AgentDefinition,
        assignment_strategy: str,
    ):
        self.instance_id = instance_id
        self.definition_id = definition_id
        self.agent_instance = agent_instance
        self.agent_definition = agent_definition
        self.assignment_strategy = assignment_strategy
        self.assigned_at = datetime.utcnow()
        self.reserved_resources: Dict[str, Any] = {}


class AgentReservation:
    """Represents resource reservations for an agent assignment."""
    
    def __init__(
        self,
        assignment: AgentAssignment,
        workspace_id: str,
        project_id: str,
        duration_seconds: int = 3600,
    ):
        self.assignment = assignment
        self.workspace_id = workspace_id
        self.project_id = project_id
        self.started_at = datetime.utcnow()
        self.expires_at = self.started_at + timedelta(seconds=duration_seconds)
        self.is_active = True


class AgentFailoverRecord:
    """Tracks agent assignment failures and failover attempts."""
    
    def __init__(
        self,
        step_execution_id: str,
        original_assignment: AgentAssignment,
        failure_reason: str,
        failover_attempts: int = 0,
        max_failover_attempts: int = 3,
    ):
        self.step_execution_id = step_execution_id
        self.original_assignment = original_assignment
        self.failure_reason = failure_reason
        self.failover_attempts = failover_attempts
        self.max_failover_attempts = max_failover_attempts
        self.failover_history: List[AgentAssignment] = []
        self.created_at = datetime.utcnow()


class MultiAgentController:
    """
    Coordinates agent assignments and resource management for workflow steps.
    
    Features:
    - Intelligent agent assignment based on capabilities and load
    - Resource reservation and quota management
    - Automatic failover on agent failures
    - Context sharing between agent executions
    - Performance monitoring and metrics
    """
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        context_service: SharedContextService,
    ):
        """
        Initialize the multi-agent controller.
        
        Args:
            agent_registry: Registry for agent definitions and instances
            context_service: Service for shared agent context management
        """
        self.agent_registry = agent_registry
        self.context_service = context_service
        
        # Assignment tracking
        self.active_assignments: Dict[str, AgentAssignment] = {}
        self.active_reservations: Dict[str, AgentReservation] = {}
        self.failover_records: Dict[str, AgentFailoverRecord] = {}
        
        # Assignment strategy state
        self.round_robin_counters: Dict[str, int] = {}
        
        logger.info("MultiAgentController initialized")
    
    async def execute_agent_step(
        self,
        session: AsyncSession,
        step: WorkflowStep,
        context: "WorkflowContext",
        input_data: Dict[str, Any],
        timeout_seconds: int = 3600,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Execute a workflow step using agent coordination.
        
        Args:
            session: Database session
            step: Workflow step definition
            context: Workflow execution context
            input_data: Input data for the step
            timeout_seconds: Execution timeout
            max_retries: Maximum retry attempts
            
        Returns:
            Output data from agent execution
        """
        step_execution = await self._get_or_create_step_execution(session, step.id, context.workflow_execution_id)
        
        try:
            # Attempt agent assignment with failover
            assignment = await self._assign_agent_with_failover(
                session, step, context, step_execution.id, max_retries
            )
            
            if not assignment:
                raise Exception(f"No suitable agent found for step '{step.name}'")
            
            # Reserve resources for the assignment
            reservation = await self._reserve_resources(
                assignment, context, timeout_seconds
            )
            
            try:
                # Execute the agent step
                output_data = await self._execute_agent_step_with_assignment(
                    session, step, context, assignment, reservation, input_data, timeout_seconds
                )
                
                return output_data
                
            finally:
                # Release resources
                await self._release_resources(reservation)
                
        except Exception as e:
            logger.error(f"Agent step execution failed for step {step.id}: {str(e)}")
            raise
    
    async def _assign_agent_with_failover(
        self,
        session: AsyncSession,
        step: WorkflowStep,
        context: "WorkflowContext",
        step_execution_id: str,
        max_failover_attempts: int,
    ) -> Optional[AgentAssignment]:
        """
        Assign an agent with automatic failover on failures.
        
        Args:
            session: Database session
            step: Workflow step
            context: Workflow context
            step_execution_id: Step execution ID
            max_failover_attempts: Maximum failover attempts
            
        Returns:
            Agent assignment or None if all assignments fail
        """
        failover_record = AgentFailoverRecord(
            step_execution_id=step_execution_id,
            original_assignment=None,  # Will be set during assignment
            failure_reason="Initial assignment",
            max_failover_attempts=max_failover_attempts,
        )
        
        # Try primary assignment first
        assignment = await self._assign_agent(session, step, context)
        failover_record.original_assignment = assignment
        
        if not assignment:
            logger.warning(f"No agent available for step {step.id}")
            return None
        
        attempts = 0
        while attempts <= max_failover_attempts:
            try:
                # Validate assignment
                if await self._validate_assignment(session, assignment):
                    # Assignment is valid, use it
                    if attempts > 0:
                        logger.info(f"Failover successful for step {step.id} after {attempts} attempts")
                    
                    # Track the assignment
                    self.active_assignments[step_execution_id] = assignment
                    return assignment
                
                else:
                    raise Exception("Assignment validation failed")
                    
            except Exception as e:
                attempts += 1
                logger.warning(f"Agent assignment failed for step {step.id} (attempt {attempts}): {str(e)}")
                
                if attempts > max_failover_attempts:
                    # Record final failure
                    self.failover_records[step_execution_id] = failover_record
                    break
                
                # Attempt failover to another agent
                failover_record.failover_attempts = attempts
                failover_record.failover_history.append(assignment)
                
                # Find alternative agent
                assignment = await self._find_failover_agent(session, step, context, assignment)
                
                if not assignment:
                    logger.error(f"No failover agent available for step {step.id}")
                    break
        
        # All attempts failed
        self.failover_records[step_execution_id] = failover_record
        return None
    
    async def _assign_agent(
        self,
        session: AsyncSession,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> Optional[AgentAssignment]:
        """
        Assign an agent to a workflow step.
        
        Args:
            session: Database session
            step: Workflow step
            context: Workflow context
            
        Returns:
            Agent assignment or None if no suitable agent found
        """
        # Load available agents for the workspace/project
        instances_result = await session.execute(
            select(AgentInstance).where(
                AgentInstance.workspace_id == context.workspace_id,
                AgentInstance.project_id == context.project_id,
                AgentInstance.status == AgentStatus.IDLE,
            )
        )
        available_instances = instances_result.scalars().all()
        
        if not available_instances:
            logger.warning(f"No available agents found for workspace {context.workspace_id}")
            return None
        
        # Filter agents based on step requirements
        suitable_agents = []
        for instance in available_instances:
            # Get agent definition
            def_result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == instance.definition_id)
            )
            definition = def_result.scalar_one_or_none()
            
            if not definition or not definition.is_enabled:
                continue
            
            # Check capability requirements
            if step.agent_instance_id and instance.id != step.agent_instance_id:
                continue
            
            if step.agent_definition_id and instance.definition_id != step.agent_definition_id:
                continue
            
            # Check capability matches
            required_capabilities = step.config.get("required_capabilities", [])
            if required_capabilities and not any(
                cap in (definition.capabilities or []) for cap in required_capabilities
            ):
                continue
            
            suitable_agents.append((instance, definition))
        
        if not suitable_agents:
            logger.warning(f"No suitable agents found for step '{step.name}' requirements")
            return None
        
        # Select agent using strategy
        assignment_strategy = step.config.get("assignment_strategy", "capability_match")
        selected_agent = await self._select_agent_by_strategy(
            suitable_agents, assignment_strategy, context, step
        )
        
        if not selected_agent:
            return None
        
        instance, definition = selected_agent
        
        # Update agent status to busy
        await self.agent_registry.update_instance_status(
            session, instance.id, AgentStatus.BUSY
        )
        
        return AgentAssignment(
            instance_id=instance.id,
            definition_id=definition.id,
            agent_instance=instance,
            agent_definition=definition,
            assignment_strategy=assignment_strategy,
        )
    
    async def _select_agent_by_strategy(
        self,
        suitable_agents: List[Tuple[AgentInstance, AgentDefinition]],
        strategy: str,
        context: WorkflowContext,
        step: WorkflowStep,
    ) -> Optional[Tuple[AgentInstance, AgentDefinition]]:
        """
        Select an agent based on the specified strategy.
        
        Args:
            suitable_agents: List of (instance, definition) tuples
            strategy: Assignment strategy
            context: Workflow context
            step: Workflow step
            
        Returns:
            Selected (instance, definition) or None
        """
        if not suitable_agents:
            return None
        
        if strategy == AssignmentStrategy.ROUND_ROBIN:
            counter_key = f"{context.workspace_id}:{context.project_id}"
            counter = self.round_robin_counters.get(counter_key, 0)
            selected = suitable_agents[counter % len(suitable_agents)]
            self.round_robin_counters[counter_key] = counter + 1
            return selected
        
        elif strategy == AssignmentStrategy.LEAST_LOADED:
            # TODO: Implement load-based selection
            # For now, select randomly among suitable agents
            import random
            return random.choice(suitable_agents)
        
        elif strategy == AssignmentStrategy.CAPABILITY_MATCH:
            # Prioritize agents with best capability match
            best_match = None
            best_score = -1
            
            required_capabilities = step.config.get("required_capabilities", [])
            
            for instance, definition in suitable_agents:
                capabilities = definition.capabilities or []
                if required_capabilities:
                    # Score based on capability overlap
                    overlap = len(set(capabilities) & set(required_capabilities))
                    score = overlap / len(required_capabilities) if required_capabilities else 1
                else:
                    score = 1  # All agents equally suitable if no specific requirements
                
                if score > best_score:
                    best_score = score
                    best_match = (instance, definition)
            
            return best_match
        
        elif strategy == AssignmentStrategy.RESOURCE_BASED:
            # TODO: Implement resource-based selection
            # For now, use capability match
            return await self._select_agent_by_strategy(
                suitable_agents, AssignmentStrategy.CAPABILITY_MATCH, context, step
            )
        
        else:
            # Default to first available
            return suitable_agents[0]
    
    async def _find_failover_agent(
        self,
        session: AsyncSession,
        step: WorkflowStep,
        context: WorkflowContext,
        failed_assignment: AgentAssignment,
    ) -> Optional[AgentAssignment]:
        """
        Find an alternative agent for failover.
        
        Args:
            session: Database session
            step: Workflow step
            context: Workflow context
            failed_assignment: Failed assignment
            
        Returns:
            Alternative agent assignment or None
        """
        # Mark failed agent as error
        await self.agent_registry.update_instance_status(
            session, failed_assignment.instance_id, AgentStatus.ERROR,
            error=f"Failed during step execution: {step.name}"
        )
        
        # Try to find another agent
        return await self._assign_agent(session, step, context)
    
    async def _validate_assignment(
        self,
        session: AsyncSession,
        assignment: AgentAssignment,
    ) -> bool:
        """
        Validate that an agent assignment is still valid.
        
        Args:
            session: Database session
            assignment: Agent assignment
            
        Returns:
            True if assignment is valid
        """
        # Check if agent instance still exists and is available
        result = await session.execute(
            select(AgentInstance).where(AgentInstance.id == assignment.instance_id)
        )
        instance = result.scalar_one_or_none()
        
        if not instance:
            return False
        
        # Check if agent is still in a suitable state
        if instance.status not in [AgentStatus.IDLE, AgentStatus.BUSY]:
            return False
        
        # Check if definition is still enabled
        def_result = await session.execute(
            select(AgentDefinition).where(AgentDefinition.id == instance.definition_id)
        )
        definition = def_result.scalar_one_or_none()
        
        if not definition or not definition.is_enabled:
            return False
        
        return True
    
    async def _reserve_resources(
        self,
        assignment: AgentAssignment,
        context: WorkflowContext,
        duration_seconds: int,
    ) -> AgentReservation:
        """
        Reserve resources for an agent assignment.
        
        Args:
            assignment: Agent assignment
            context: Workflow context
            duration_seconds: Expected reservation duration
            
        Returns:
            Resource reservation
        """
        reservation = AgentReservation(
            assignment=assignment,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            duration_seconds=duration_seconds,
        )
        
        self.active_reservations[assignment.instance_id] = reservation
        
        # Update assignment with reserved resources
        assignment.reserved_resources = {
            "memory_mb": assignment.agent_instance.config.get("memory_limit", 512),
            "cpu_cores": assignment.agent_instance.config.get("cpu_limit", 1),
            "workspace_id": context.workspace_id,
            "project_id": context.project_id,
        }
        
        logger.info(f"Reserved resources for agent {assignment.instance_id}: {assignment.reserved_resources}")
        
        return reservation
    
    async def _release_resources(self, reservation: AgentReservation):
        """
        Release resources from an agent reservation.
        
        Args:
            reservation: Resource reservation to release
        """
        if reservation.assignment.instance_id in self.active_reservations:
            del self.active_reservations[reservation.assignment.instance_id]
        
        logger.info(f"Released resources for agent {reservation.assignment.instance_id}")
    
    async def _execute_agent_step_with_assignment(
        self,
        session: AsyncSession,
        step: WorkflowStep,
        context: WorkflowContext,
        assignment: AgentAssignment,
        reservation: AgentReservation,
        input_data: Dict[str, Any],
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        """
        Execute a workflow step using the assigned agent.
        
        Args:
            session: Database session
            step: Workflow step
            context: Workflow context
            assignment: Agent assignment
            reservation: Resource reservation
            input_data: Step input data
            timeout_seconds: Execution timeout
            
        Returns:
            Output data from agent execution
        """
        agent_instance = assignment.agent_instance
        agent_definition = assignment.agent_definition
        
        logger.info(f"Executing step '{step.name}' on agent {agent_instance.name} ({agent_instance.id})")
        
        try:
            # Get or create agent context
            agent_context = await self.context_service.get_or_create_context(
                session=session,
                instance_id=agent_instance.id,
                context_name=step.config.get("context_name", f"workflow_{context.workflow_execution_id}"),
                workspace_id=context.workspace_id,
                project_id=context.project_id,
            )
            
            # Prepare agent execution input
            agent_input = {
                "step_name": step.name,
                "step_config": step.config,
                "workflow_context": {
                    "execution_id": context.workflow_execution_id,
                    "variables": context.variables,
                    "previous_outputs": context.step_outputs,
                },
                "input_data": input_data,
                "metadata": {
                    "assignment_strategy": assignment.assignment_strategy,
                    "reserved_resources": assignment.reserved_resources,
                },
            }
            
            # Execute agent step with timeout
            try:
                agent_output = await asyncio.wait_for(
                    self._execute_agent_logic(agent_instance, agent_input),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                raise Exception(f"Agent execution timed out after {timeout_seconds} seconds")
            
            # Update agent context with new state
            if agent_output.get("context_updates"):
                await self.context_service.update_context_version(
                    session=session,
                    context_id=agent_context.id,
                    data=agent_output["context_updates"],
                    change_description=f"Updated by workflow step '{step.name}'",
                    created_by=f"workflow:{context.workflow_execution_id}",
                )
            
            # Emit agent activity event
            await self._emit_agent_activity_event(
                session,
                agent_instance.id,
                context.workspace_id,
                "step_execution_completed",
                {
                    "step_id": step.id,
                    "step_name": step.name,
                    "execution_id": context.workflow_execution_id,
                    "output_summary": {k: str(type(v)) for k, v in agent_output.items()},
                }
            )
            
            return agent_output
            
        except Exception as e:
            # Mark agent as error
            await self.agent_registry.update_instance_status(
                session, agent_instance.id, AgentStatus.ERROR, error=str(e)
            )
            
            logger.error(f"Agent step execution failed: {str(e)}")
            raise
    
    async def _execute_agent_logic(
        self,
        agent_instance: AgentInstance,
        agent_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the actual agent logic (placeholder implementation).
        
        Args:
            agent_instance: Agent instance to execute on
            agent_input: Agent execution input
            
        Returns:
            Agent execution output
        """
        # TODO: Integrate with actual agent execution system
        # For now, simulate agent execution
        
        # Simulate some processing time
        await asyncio.sleep(0.5)
        
        # Generate mock output
        output = {
            "result": f"Agent '{agent_instance.name}' successfully processed step '{agent_input['step_name']}'",
            "processed_at": datetime.utcnow().isoformat(),
            "agent_id": agent_instance.id,
            "context_updates": {
                "last_step_executed": agent_input["step_name"],
                "execution_count": 1,
            },
        }
        
        # Add step-specific processing based on config
        step_config = agent_input.get("step_config", {})
        processing_type = step_config.get("processing_type", "default")
        
        if processing_type == "data_transformation":
            input_data = agent_input.get("input_data", {})
            output["transformed_data"] = {f"{k}_processed": v for k, v in input_data.items()}
        elif processing_type == "analysis":
            output["analysis_results"] = {
                "summary": "Analysis completed successfully",
                "confidence": 0.95,
                "details": "Mock analysis results",
            }
        
        return output
    
    async def _get_or_create_step_execution(
        self,
        session: AsyncSession,
        step_id: str,
        execution_id: str,
    ) -> WorkflowStepExecution:
        """Get or create a step execution record."""
        result = await session.execute(
            select(WorkflowStepExecution).where(
                WorkflowStepExecution.execution_id == execution_id,
                WorkflowStepExecution.step_id == step_id,
            )
        )
        step_execution = result.scalar_one_or_none()
        
        if not step_execution:
            step_execution = WorkflowStepExecution(
                execution_id=execution_id,
                step_id=step_id,
                status=WorkflowStepStatus.PENDING,
                started_at=datetime.utcnow(),
            )
            session.add(step_execution)
            await session.flush()
        
        return step_execution
    
    async def _emit_agent_activity_event(
        self,
        session: AsyncSession,
        agent_id: str,
        workspace_id: str,
        activity_type: str,
        data: Dict[str, Any],
    ):
        """Emit an agent activity event."""
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.AGENT_ACTIVITY,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    data={
                        "activity_type": activity_type,
                        **data,
                    },
                    message=f"Agent activity: {activity_type}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to emit agent activity event: {e}")
    
    async def cleanup_stale_assignments(self):
        """Clean up stale agent assignments and reservations."""
        current_time = datetime.utcnow()
        
        # Clean up expired reservations
        expired_reservations = [
            instance_id for instance_id, reservation in self.active_reservations.items()
            if reservation.expires_at < current_time
        ]
        
        for instance_id in expired_reservations:
            reservation = self.active_reservations.pop(instance_id, None)
            if reservation:
                logger.warning(f"Cleaning up expired reservation for agent {instance_id}")
        
        # Clean up stale failover records
        cutoff_time = current_time - timedelta(hours=24)
        stale_failover_records = [
            step_id for step_id, record in self.failover_records.items()
            if record.created_at < cutoff_time
        ]
        
        for step_id in stale_failover_records:
            self.failover_records.pop(step_id, None)
            logger.debug(f"Cleaned up stale failover record for step {step_id}")
    
    def get_assignment_stats(self) -> Dict[str, Any]:
        """Get assignment statistics for monitoring."""
        return {
            "active_assignments": len(self.active_assignments),
            "active_reservations": len(self.active_reservations),
            "failover_records": len(self.failover_records),
            "round_robin_counters": len(self.round_robin_counters),
        }


__all__ = [
    "MultiAgentController",
    "AgentAssignment",
    "AgentReservation",
    "AgentFailoverRecord",
    "AssignmentStrategy",
]