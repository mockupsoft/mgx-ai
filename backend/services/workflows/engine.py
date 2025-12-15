# -*- coding: utf-8 -*-
"""
Workflow Engine

Runtime workflow execution engine that:
- Loads workflow definitions from database
- Drives a state machine supporting sequential, parallel, and conditional branches
- Manages shared workflow context (inputs/outputs, variables)
- Handles step-level timeout, retry, and fallback policies
- Coordinates with MultiAgentController for agent assignments
- Persists execution state to database
- Emits real-time events for monitoring
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowExecution,
    WorkflowStepExecution,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
)
from backend.schemas import (
    EventPayload,
    EventTypeEnum,
    WorkflowStartedEvent,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowCancelledEvent,
    StepStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepSkippedEvent,
)
from backend.services.events import get_event_broadcaster
# Import MultiAgentController using TYPE_CHECKING to avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .controller import MultiAgentController
    
from backend.services.workflows.dependency_resolver import DependencyResolver

logger = logging.getLogger(__name__)


class WorkflowExecutionState(str, Enum):
    """Workflow execution state machine states."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_DEPENDENCIES = "waiting_for_dependencies"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class WorkflowStepExecutionState(str, Enum):
    """Individual step execution states."""
    PENDING = "pending"
    WAITING_FOR_DEPENDENCIES = "waiting_for_dependencies"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    TIMEOUT = "timeout"


@dataclass
class WorkflowContext:
    """Shared workflow execution context."""
    workflow_execution_id: str
    workspace_id: str
    project_id: str
    variables: Dict[str, Any]
    step_outputs: Dict[str, Any]  # step_id -> output_data
    step_statuses: Dict[str, str]  # step_id -> WorkflowStepStatus
    started_at: datetime
    parent_execution_id: Optional[str] = None
    
    def get_step_input(self, step_id: str, input_name: str, default: Any = None) -> Any:
        """Get input value for a step, resolving from workflow variables or previous step outputs."""
        # Check if it's a reference to another step's output
        if isinstance(input_name, str) and input_name.startswith("steps."):
            referenced_step_id = input_name.replace("steps.", "").split(".")[0]
            referenced_output = input_name.split(".", 2)[-1]
            
            if referenced_step_id in self.step_outputs:
                step_output = self.step_outputs[referenced_step_id]
                return step_output.get(referenced_output, default)
            return default
        
        # Check workflow variables
        if input_name in self.variables:
            return self.variables[input_name]
        
        return default
    
    def set_step_output(self, step_id: str, output_data: Dict[str, Any]):
        """Set output data for a completed step."""
        self.step_outputs[step_id] = output_data
        self.step_statuses[step_id] = WorkflowStepStatus.COMPLETED
    
    def set_step_failed(self, step_id: str, error_message: str):
        """Mark a step as failed."""
        self.step_statuses[step_id] = WorkflowStepStatus.FAILED
    
    def set_step_skipped(self, step_id: str):
        """Mark a step as skipped."""
        self.step_statuses[step_id] = WorkflowStepStatus.SKIPPED


class WorkflowEngine:
    """
    Core workflow execution engine.
    
    Manages workflow execution state, step coordination, and event emission.
    Designed to be resilient and handle complex workflow patterns.
    """
    
    def __init__(
        self,
        session_factory,
        multi_agent_controller,  # Type will be MultiAgentController at runtime
        dependency_resolver: DependencyResolver,
    ):
        """
        Initialize the workflow engine.
        
        Args:
            session_factory: SQLAlchemy async session factory
            multi_agent_controller: Controller for agent assignments
            dependency_resolver: Service for workflow validation
        """
        self.session_factory = session_factory
        self.multi_agent_controller = multi_agent_controller
        self.dependency_resolver = dependency_resolver
        self.active_executions: Dict[str, WorkflowContext] = {}
        self.execution_locks: Dict[str, asyncio.Lock] = {}
        
        logger.info("WorkflowEngine initialized")
    
    async def execute_workflow(
        self,
        workflow_id: str,
        workspace_id: str,
        project_id: str,
        input_variables: Optional[Dict[str, Any]] = None,
        parent_execution_id: Optional[str] = None,
        execution_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute a workflow definition.
        
        Args:
            workflow_id: Workflow definition ID
            workspace_id: Workspace ID
            project_id: Project ID
            input_variables: Input variables for the workflow
            parent_execution_id: Parent workflow execution ID (for sub-workflows)
            execution_metadata: Additional execution metadata
        
        Returns:
            Execution ID for the workflow execution
        """
        async with self.session_factory() as session:
            # Load workflow definition
            result = await session.execute(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.id == workflow_id,
                    WorkflowDefinition.workspace_id == workspace_id,
                    WorkflowDefinition.project_id == project_id,
                    WorkflowDefinition.is_active == True,
                )
            )
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found or inactive")
            
            # Create workflow execution record
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                project_id=project_id,
                execution_number=await self._get_next_execution_number(session, workflow_id),
                status=WorkflowStatus.PENDING,
                input_variables=input_variables or {},
                started_at=datetime.utcnow(),
                meta_data=execution_metadata or {},
            )
            
            session.add(execution)
            await session.flush()
            
            execution_id = execution.id
            
            # Create workflow context
            context = WorkflowContext(
                workflow_execution_id=execution_id,
                workspace_id=workspace_id,
                project_id=project_id,
                variables=input_variables or {},
                step_outputs={},
                step_statuses={},
                started_at=datetime.utcnow(),
                parent_execution_id=parent_execution_id,
            )
            
            self.active_executions[execution_id] = context
            self.execution_locks[execution_id] = asyncio.Lock()
            
            logger.info(f"Started workflow execution {execution_id} for workflow {workflow_id}")
            
            # Start execution in background
            asyncio.create_task(
                self._execute_workflow_async(execution_id, workflow, session)
            )
            
            return execution_id
    
    async def _execute_workflow_async(
        self,
        execution_id: str,
        workflow: WorkflowDefinition,
        session: AsyncSession,
    ):
        """Execute workflow asynchronously in the background."""
        context = self.active_executions.get(execution_id)
        if not context:
            logger.error(f"No context found for execution {execution_id}")
            return
        
        execution_lock = self.execution_locks[execution_id]
        async with execution_lock:
            try:
                # Update execution status to running
                await self._update_execution_status(
                    session, execution_id, WorkflowStatus.RUNNING
                )
                
                # Emit workflow started event
                await self._emit_workflow_event(
                    session,
                    WorkflowStartedEvent(
                        event_type=EventTypeEnum.WORKFLOW_STARTED,
                        workflow_id=workflow.id,
                        workflow_execution_id=execution_id,
                        workspace_id=context.workspace_id,
                        data={
                            "workflow_name": workflow.name,
                            "input_variables": context.variables,
                            "step_count": len(workflow.steps),
                        },
                        message=f"Workflow '{workflow.name}' started execution",
                    )
                )
                
                # Execute workflow steps
                await self._execute_workflow_steps(session, execution_id, workflow, context)
                
            except asyncio.CancelledError:
                logger.info(f"Workflow execution {execution_id} was cancelled")
                await self._handle_cancellation(session, execution_id, context)
            except Exception as e:
                logger.error(f"Workflow execution {execution_id} failed: {str(e)}")
                await self._handle_execution_error(session, execution_id, context, e)
            finally:
                # Cleanup
                self.active_executions.pop(execution_id, None)
                self.execution_locks.pop(execution_id, None)
    
    async def _execute_workflow_steps(
        self,
        session: AsyncSession,
        execution_id: str,
        workflow: WorkflowDefinition,
        context: WorkflowContext,
    ):
        """Execute all workflow steps according to their dependencies and flow control."""
        steps = list(workflow.steps)
        
        # Sort steps by order for initial execution
        steps.sort(key=lambda s: s.step_order)
        
        # Group steps by dependency levels
        dependency_levels = await self.dependency_resolver.resolve_execution_order(steps)
        
        # Execute steps level by level
        for level_steps in dependency_levels:
            # Check for cancellation
            if execution_id not in self.active_executions:
                break
            
            # Check if any step in this level is still running
            running_steps = []
            for step in level_steps:
                step_execution = await self._get_or_create_step_execution(
                    session, execution_id, step.id
                )
                
                if step_execution.status == WorkflowStepStatus.RUNNING:
                    running_steps.append((step, step_execution))
                elif step_execution.status == WorkflowStepStatus.PENDING:
                    # Check if dependencies are satisfied
                    if await self._are_dependencies_satisfied(session, step, context):
                        # Start step execution
                        asyncio.create_task(
                            self._execute_step(session, execution_id, step, context)
                        )
                    else:
                        # Mark as waiting for dependencies
                        await self._update_step_execution_status(
                            session, step_execution.id, WorkflowStepStatus.PENDING
                        )
            
            # Wait for current level to complete before moving to next level
            if level_steps:
                await self._wait_for_step_level_completion(session, execution_id, level_steps)
        
        # Check final execution status
        await self._finalize_workflow_execution(session, execution_id, context)
    
    async def _execute_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step: WorkflowStep,
        context: WorkflowContext,
    ):
        """Execute a single workflow step."""
        step_execution = await self._get_or_create_step_execution(session, execution_id, step.id)
        
        try:
            # Update step status to running
            await self._update_step_execution_status(
                session, step_execution.id, WorkflowStepStatus.RUNNING
            )
            
            # Emit step started event
            await self._emit_step_event(
                session,
                StepStartedEvent(
                    event_type=EventTypeEnum.STEP_STARTED,
                    workflow_id=step.workflow_id,
                    workflow_execution_id=execution_id,
                    workflow_step_id=step.id,
                    workspace_id=context.workspace_id,
                    agent_id=step.agent_instance_id,
                    data={
                        "step_name": step.name,
                        "step_type": step.step_type.value,
                        "step_order": step.step_order,
                        "config": step.config,
                    },
                    message=f"Step '{step.name}' started execution",
                )
            )
            
            # Execute step based on type
            if step.step_type == WorkflowStepType.TASK:
                await self._execute_task_step(session, execution_id, step, context, step_execution)
            elif step.step_type == WorkflowStepType.CONDITION:
                await self._execute_condition_step(session, execution_id, step, context, step_execution)
            elif step.step_type == WorkflowStepType.PARALLEL:
                await self._execute_parallel_step(session, execution_id, step, context, step_execution)
            elif step.step_type == WorkflowStepType.SEQUENTIAL:
                await self._execute_sequential_step(session, execution_id, step, context, step_execution)
            elif step.step_type == WorkflowStepType.AGENT:
                await self._execute_agent_step(session, execution_id, step, context, step_execution)
            else:
                raise ValueError(f"Unsupported step type: {step.step_type}")
            
        except asyncio.CancelledError:
            logger.info(f"Step execution {step_execution.id} was cancelled")
            await self._update_step_execution_status(
                session, step_execution.id, WorkflowStepStatus.CANCELLED
            )
        except Exception as e:
            logger.error(f"Step execution {step_execution.id} failed: {str(e)}")
            await self._handle_step_error(session, step_execution, context, e)
    
    async def _execute_task_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step: WorkflowStep,
        context: WorkflowContext,
        step_execution: WorkflowStepExecution,
    ):
        """Execute a task step (delegates to task execution system)."""
        # Get input data for the step
        input_data = self._resolve_step_inputs(step, context)
        
        # Update step execution with input data
        step_execution.input_data = input_data
        await session.flush()
        
        # TODO: Integrate with existing task execution system
        # For now, simulate task execution
        await asyncio.sleep(1)
        
        # Generate mock output
        output_data = {
            "result": f"Task step '{step.name}' completed",
            "timestamp": datetime.utcnow().isoformat(),
            "execution_id": execution_id,
        }
        
        # Complete the step
        await self._complete_step(session, step_execution, context, output_data)
    
    async def _execute_agent_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step: WorkflowStep,
        context: WorkflowContext,
        step_execution: WorkflowStepExecution,
    ):
        """Execute an agent step using the multi-agent controller."""
        # Get input data for the step
        input_data = self._resolve_step_inputs(step, context)
        
        # Update step execution with input data
        step_execution.input_data = input_data
        await session.flush()
        
        # Use multi-agent controller to execute the step
        try:
            agent_output = await self.multi_agent_controller.execute_agent_step(
                session=session,
                step=step,
                context=context,
                input_data=input_data,
                timeout_seconds=step.timeout_seconds or step.workflow.timeout_seconds,
                max_retries=step.max_retries or step.workflow.max_retries,
            )
            
            await self._complete_step(session, step_execution, context, agent_output)
            
        except asyncio.TimeoutError:
            raise Exception(f"Agent step '{step.name}' timed out")
        except Exception as e:
            raise Exception(f"Agent step '{step.name}' failed: {str(e)}")
    
    async def _execute_condition_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step: WorkflowStep,
        context: WorkflowContext,
        step_execution: WorkflowStepExecution,
    ):
        """Execute a conditional step."""
        # Evaluate the condition expression
        condition_result = self._evaluate_condition(step.condition_expression, context)
        
        if condition_result:
            # Condition is true, proceed normally
            await self._execute_task_step(session, execution_id, step, context, step_execution)
        else:
            # Condition is false, skip this step
            await self._skip_step(session, step_execution, context)
    
    async def _execute_parallel_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step: WorkflowStep,
        context: WorkflowContext,
        step_execution: WorkflowStepExecution,
    ):
        """Execute a parallel step (contains multiple sub-steps)."""
        # TODO: Implement parallel step execution
        # For now, treat as a regular task step
        await self._execute_task_step(session, execution_id, step, context, step_execution)
    
    async def _execute_sequential_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step: WorkflowStep,
        context: WorkflowContext,
        step_execution: WorkflowStepExecution,
    ):
        """Execute a sequential step (contains multiple sub-steps in sequence)."""
        # TODO: Implement sequential step execution
        # For now, treat as a regular task step
        await self._execute_task_step(session, execution_id, step, context, step_execution)
    
    def _resolve_step_inputs(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Resolve input references for a step."""
        resolved_inputs = {}
        
        for input_key, input_value in step.config.get("inputs", {}).items():
            resolved_inputs[input_key] = context.get_step_input(step.id, input_value)
        
        return resolved_inputs
    
    def _evaluate_condition(self, condition_expression: Optional[str], context: WorkflowContext) -> bool:
        """Evaluate a conditional expression."""
        if not condition_expression:
            return True
        
        try:
            # Simple evaluation - in a real implementation, use a proper expression parser
            # For now, support simple variable references
            if condition_expression.startswith("${") and condition_expression.endswith("}"):
                var_name = condition_expression[2:-1]
                return bool(context.get_step_input("", var_name, False))
            return condition_expression.lower() in ("true", "1", "yes", "on")
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition_expression}': {e}")
            return False
    
    async def _are_dependencies_satisfied(
        self,
        session: AsyncSession,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> bool:
        """Check if all dependencies for a step are satisfied."""
        for dependency_step_id in step.depends_on_steps:
            if dependency_step_id not in context.step_statuses:
                return False
            
            dependency_status = context.step_statuses[dependency_step_id]
            if dependency_status not in [WorkflowStepStatus.COMPLETED]:
                return False
        
        return True
    
    async def _wait_for_step_level_completion(
        self,
        session: AsyncSession,
        execution_id: str,
        level_steps: List[WorkflowStep],
    ):
        """Wait for all steps in a level to complete before proceeding."""
        while True:
            # Check if all steps in the level are done
            all_done = True
            for step in level_steps:
                step_execution = await self._get_or_create_step_execution(session, execution_id, step.id)
                if step_execution.status in [WorkflowStepStatus.PENDING, WorkflowStepStatus.RUNNING]:
                    all_done = False
                    break
            
            if all_done:
                break
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
    
    async def _complete_step(
        self,
        session: AsyncSession,
        step_execution: WorkflowStepExecution,
        context: WorkflowContext,
        output_data: Dict[str, Any],
    ):
        """Complete a step execution successfully."""
        # Update step execution
        step_execution.output_data = output_data
        step_execution.status = WorkflowStepStatus.COMPLETED
        step_execution.completed_at = datetime.utcnow()
        step_execution.duration = (
            step_execution.completed_at - step_execution.started_at
        ).total_seconds()
        
        await session.flush()
        
        # Update context
        context.set_step_output(step_execution.step_id, output_data)
        
        # Emit step completed event
        await self._emit_step_event(
            session,
            StepCompletedEvent(
                event_type=EventTypeEnum.STEP_COMPLETED,
                workflow_step_id=step_execution.step_id,
                workflow_execution_id=step_execution.execution_id,
                workspace_id=context.workspace_id,
                data={
                    "output_data": output_data,
                    "duration": step_execution.duration,
                },
                message=f"Step completed successfully",
            )
        )
    
    async def _skip_step(
        self,
        session: AsyncSession,
        step_execution: WorkflowStepExecution,
        context: WorkflowContext,
    ):
        """Skip a step execution."""
        step_execution.status = WorkflowStepStatus.SKIPPED
        step_execution.completed_at = datetime.utcnow()
        step_execution.duration = 0
        
        await session.flush()
        
        # Update context
        context.set_step_skipped(step_execution.step_id)
        
        # Emit step skipped event
        await self._emit_step_event(
            session,
            StepSkippedEvent(
                event_type=EventTypeEnum.STEP_SKIPPED,
                workflow_step_id=step_execution.step_id,
                workflow_execution_id=step_execution.execution_id,
                workspace_id=context.workspace_id,
                message=f"Step skipped",
            )
        )
    
    async def _handle_step_error(
        self,
        session: AsyncSession,
        step_execution: WorkflowStepExecution,
        context: WorkflowContext,
        error: Exception,
    ):
        """Handle a step execution error."""
        step_execution.status = WorkflowStepStatus.FAILED
        step_execution.error_message = str(error)
        step_execution.completed_at = datetime.utcnow()
        
        if step_execution.started_at:
            step_execution.duration = (
                step_execution.completed_at - step_execution.started_at
            ).total_seconds()
        
        await session.flush()
        
        # Update context
        context.set_step_failed(step_execution.step_id, str(error))
        
        # Emit step failed event
        await self._emit_step_event(
            session,
            StepFailedEvent(
                event_type=EventTypeEnum.STEP_FAILED,
                workflow_step_id=step_execution.step_id,
                workflow_execution_id=step_execution.execution_id,
                workspace_id=context.workspace_id,
                data={
                    "error_message": str(error),
                    "duration": step_execution.duration,
                },
                message=f"Step failed: {str(error)}",
            )
        )
    
    async def _get_or_create_step_execution(
        self,
        session: AsyncSession,
        execution_id: str,
        step_id: str,
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
    
    async def _update_step_execution_status(
        self,
        session: AsyncSession,
        step_execution_id: str,
        status: WorkflowStepStatus,
    ):
        """Update step execution status."""
        result = await session.execute(
            select(WorkflowStepExecution).where(WorkflowStepExecution.id == step_execution_id)
        )
        step_execution = result.scalar_one_or_none()
        
        if step_execution:
            step_execution.status = status
            await session.flush()
    
    async def _update_execution_status(
        self,
        session: AsyncSession,
        execution_id: str,
        status: WorkflowStatus,
    ):
        """Update workflow execution status."""
        result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        
        if execution:
            execution.status = status
            await session.flush()
    
    async def _get_next_execution_number(self, session: AsyncSession, workflow_id: str) -> int:
        """Get the next execution number for a workflow."""
        result = await session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.workflow_id == workflow_id
            ).order_by(WorkflowExecution.execution_number.desc())
        )
        last_execution = result.scalar_one_or_none()
        
        return (last_execution.execution_number + 1) if last_execution else 1
    
    async def _finalize_workflow_execution(
        self,
        session: AsyncSession,
        execution_id: str,
        context: WorkflowContext,
    ):
        """Finalize workflow execution and determine final status."""
        # Check if any step failed
        any_failed = any(
            status == WorkflowStepStatus.FAILED
            for status in context.step_statuses.values()
        )
        
        if any_failed:
            final_status = WorkflowStatus.FAILED
            event_class = WorkflowFailedEvent
            message = "Workflow failed due to step failures"
        else:
            final_status = WorkflowStatus.COMPLETED
            event_class = WorkflowCompletedEvent
            message = "Workflow completed successfully"
        
        # Update execution record
        await self._update_execution_status(session, execution_id, final_status)
        
        execution_result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = execution_result.scalar_one_or_none()
        
        if execution:
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
            execution.results = {
                "step_outputs": context.step_outputs,
                "step_statuses": context.step_statuses,
            }
            await session.flush()
        
        # Emit final event
        await self._emit_workflow_event(
            session,
            event_class(
                event_type=event_class.__fields__["event_type"].default,
                workflow_execution_id=execution_id,
                workflow_id=execution.workflow_id if execution else None,
                workspace_id=context.workspace_id,
                data={
                    "step_count": len(context.step_statuses),
                    "completed_steps": sum(
                        1 for status in context.step_statuses.values()
                        if status == WorkflowStepStatus.COMPLETED
                    ),
                    "failed_steps": sum(
                        1 for status in context.step_statuses.values()
                        if status == WorkflowStepStatus.FAILED
                    ),
                    "skipped_steps": sum(
                        1 for status in context.step_statuses.values()
                        if status == WorkflowStepStatus.SKIPPED
                    ),
                },
                message=message,
            )
        )
        
        logger.info(f"Workflow execution {execution_id} finalized with status {final_status}")
    
    async def _handle_cancellation(
        self,
        session: AsyncSession,
        execution_id: str,
        context: WorkflowContext,
    ):
        """Handle workflow execution cancellation."""
        await self._update_execution_status(session, execution_id, WorkflowStatus.CANCELLED)
        
        execution_result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = execution_result.scalar_one_or_none()
        
        if execution:
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
            await session.flush()
        
        # Emit cancellation event
        await self._emit_workflow_event(
            session,
            WorkflowCancelledEvent(
                event_type=EventTypeEnum.WORKFLOW_CANCELLED,
                workflow_execution_id=execution_id,
                workflow_id=execution.workflow_id if execution else None,
                workspace_id=context.workspace_id,
                message="Workflow execution was cancelled",
            )
        )
    
    async def _handle_execution_error(
        self,
        session: AsyncSession,
        execution_id: str,
        context: WorkflowContext,
        error: Exception,
    ):
        """Handle unexpected workflow execution error."""
        await self._update_execution_status(session, execution_id, WorkflowStatus.FAILED)
        
        execution_result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = execution_result.scalar_one_or_none()
        
        if execution:
            execution.completed_at = datetime.utcnow()
            execution.error_message = str(error)
            if execution.started_at:
                execution.duration = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
            await session.flush()
        
        # Emit failure event
        await self._emit_workflow_event(
            session,
            WorkflowFailedEvent(
                event_type=EventTypeEnum.WORKFLOW_FAILED,
                workflow_execution_id=execution_id,
                workflow_id=execution.workflow_id if execution else None,
                workspace_id=context.workspace_id,
                data={
                    "error_message": str(error),
                    "error_type": type(error).__name__,
                },
                message=f"Workflow execution failed: {str(error)}",
            )
        )
    
    async def _emit_workflow_event(self, session: AsyncSession, event: EventPayload):
        """Emit a workflow-related event."""
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(event)
        except Exception as e:
            logger.warning(f"Failed to emit workflow event: {e}")
    
    async def _emit_step_event(self, session: AsyncSession, event: EventPayload):
        """Emit a step-related event."""
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(event)
        except Exception as e:
            logger.warning(f"Failed to emit step event: {e}")
    
    async def cancel_workflow_execution(self, execution_id: str) -> bool:
        """
        Cancel a running workflow execution.
        
        Args:
            execution_id: Workflow execution ID to cancel
            
        Returns:
            True if cancellation was initiated, False if execution not found
        """
        if execution_id not in self.active_executions:
            return False
        
        # Mark execution as cancelled
        context = self.active_executions[execution_id]
        async with self.session_factory() as session:
            await self._handle_cancellation(session, execution_id, context)
        
        return True


__all__ = [
    "WorkflowEngine",
    "WorkflowContext",
    "WorkflowExecutionState",
    "WorkflowStepExecutionState",
]