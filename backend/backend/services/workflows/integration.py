# -*- coding: utf-8 -*-
"""
Workflow Engine Integration

Wires the workflow engine into the existing BackgroundTaskRunner and provides
execution entry points for the workflow API.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.services.background import BackgroundTaskRunner, get_task_runner
from backend.services.agents.registry import AgentRegistry
from backend.services.agents.context import SharedContextService
from backend.services.workflows.engine import WorkflowEngine
from backend.services.workflows.controller import MultiAgentController
from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver

logger = logging.getLogger(__name__)


class WorkflowEngineIntegration:
    """
    Integration service that wires the workflow engine into the background task system.
    
    Provides a single entry point for executing workflows through the API.
    """
    
    def __init__(
        self,
        session_factory: async_sessionmaker,
        agent_registry: AgentRegistry,
        context_service: SharedContextService,
        task_runner: Optional[BackgroundTaskRunner] = None,
    ):
        """
        Initialize the workflow engine integration.
        
        Args:
            session_factory: SQLAlchemy async session factory
            agent_registry: Agent registry for agent management
            context_service: Shared context service for agent coordination
            task_runner: Background task runner (uses global if None)
        """
        self.session_factory = session_factory
        self.agent_registry = agent_registry
        self.context_service = context_service
        self.task_runner = task_runner or get_task_runner()
        
        # Initialize workflow components
        self.dependency_resolver = WorkflowDependencyResolver()
        self.multi_agent_controller = MultiAgentController(
            agent_registry=agent_registry,
            context_service=context_service,
        )
        self.workflow_engine = WorkflowEngine(
            session_factory=session_factory,
            multi_agent_controller=self.multi_agent_controller,
            dependency_resolver=self.dependency_resolver,
        )
        
        logger.info("WorkflowEngineIntegration initialized")
    
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
        Execute a workflow in the background task system.
        
        Args:
            workflow_id: Workflow definition ID
            workspace_id: Workspace ID
            project_id: Project ID
            input_variables: Input variables for the workflow
            parent_execution_id: Parent workflow execution ID (for sub-workflows)
            execution_metadata: Additional execution metadata
        
        Returns:
            Execution ID for tracking the workflow execution
        """
        # Submit workflow execution as a background task
        task_id = await self.task_runner.submit(
            coro=self._execute_workflow_async(
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                project_id=project_id,
                input_variables=input_variables or {},
                parent_execution_id=parent_execution_id,
                execution_metadata=execution_metadata or {},
            ),
            name=f"workflow_execution_{workflow_id}"
        )
        
        logger.info(f"Submitted workflow execution {task_id} for workflow {workflow_id}")
        return task_id
    
    async def _execute_workflow_async(
        self,
        workflow_id: str,
        workspace_id: str,
        project_id: str,
        input_variables: Dict[str, Any],
        parent_execution_id: Optional[str],
        execution_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute workflow asynchronously and return execution results.
        
        This method is designed to be run as a background task and will
        handle all database operations and error management internally.
        
        Returns:
            Dictionary containing execution results
        """
        execution_id = None
        try:
            # Execute the workflow using the engine
            execution_id = await self.workflow_engine.execute_workflow(
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                project_id=project_id,
                input_variables=input_variables,
                parent_execution_id=parent_execution_id,
                execution_metadata=execution_metadata,
            )
            
            # Wait for execution to complete (or timeout)
            # In a real implementation, you might want to return immediately
            # and let the client monitor via WebSocket
            result = await self._wait_for_execution_completion(execution_id)
            
            return {
                "execution_id": execution_id,
                "status": "completed",
                "result": result,
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            return {
                "execution_id": execution_id,
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def _wait_for_execution_completion(
        self,
        execution_id: str,
        timeout_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """
        Wait for workflow execution to complete.
        
        Args:
            execution_id: Workflow execution ID
            timeout_seconds: Maximum time to wait for completion
            
        Returns:
            Execution results
        """
        # For now, implement a simple polling mechanism
        # In production, you might want to use WebSocket events or callbacks
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            async with self.session_factory() as session:
                from sqlalchemy import select
                from backend.db.models import WorkflowExecution, WorkflowStatus
                
                try:
                    result = await session.execute(
                        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
                    )
                    execution = result.scalar_one_or_none()
                    
                    if execution:
                        if execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
                            return {
                                "status": execution.status.value,
                                "results": execution.results,
                                "duration": execution.duration,
                                "error_message": execution.error_message,
                            }
                except Exception as e:
                    logger.warning(f"Error checking execution status: {e}")
                    # Continue polling despite temporary errors
                
            # Wait before next poll
            await asyncio.sleep(2)
        
        # Timeout
        raise TimeoutError(f"Workflow execution {execution_id} timed out after {timeout_seconds} seconds")
    
    async def cancel_workflow_execution(self, execution_id: str) -> bool:
        """
        Cancel a running workflow execution.
        
        Args:
            execution_id: Workflow execution ID to cancel
            
        Returns:
            True if cancellation was initiated, False if execution not found
        """
        return await self.workflow_engine.cancel_workflow_execution(execution_id)
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics for monitoring."""
        return {
            "engine_stats": {
                "active_executions": len(self.workflow_engine.active_executions),
                "execution_locks": len(self.workflow_engine.execution_locks),
            },
            "controller_stats": self.multi_agent_controller.get_assignment_stats(),
            "task_runner_stats": self.task_runner.get_stats(),
        }


# Global integration instance
_integration_instance: Optional[WorkflowEngineIntegration] = None


def get_workflow_engine_integration(
    session_factory,
    agent_registry,
    context_service,
) -> WorkflowEngineIntegration:
    """
    Get or create the global workflow engine integration instance.
    
    Args:
        session_factory: SQLAlchemy async session factory
        agent_registry: Agent registry instance
        context_service: Shared context service instance
        
    Returns:
        WorkflowEngineIntegration instance
    """
    global _integration_instance
    
    if _integration_instance is None:
        _integration_instance = WorkflowEngineIntegration(
            session_factory=session_factory,
            agent_registry=agent_registry,
            context_service=context_service,
        )
    
    return _integration_instance


async def initialize_workflow_integration(
    session_factory,
    agent_registry,
    context_service,
    task_runner: Optional[BackgroundTaskRunner] = None,
) -> WorkflowEngineIntegration:
    """
    Initialize the workflow engine integration and start required services.
    
    Args:
        session_factory: SQLAlchemy async session factory
        agent_registry: Agent registry instance
        context_service: Shared context service instance
        task_runner: Background task runner (optional)
        
    Returns:
        Initialized WorkflowEngineIntegration instance
    """
    integration = get_workflow_engine_integration(
        session_factory=session_factory,
        agent_registry=agent_registry,
        context_service=context_service,
    )
    
    # Start background task runner if not already running
    if task_runner and not task_runner._running:
        await task_runner.start()
    
    logger.info("Workflow engine integration initialized and services started")
    return integration


__all__ = [
    "WorkflowEngineIntegration",
    "get_workflow_engine_integration", 
    "initialize_workflow_integration",
]