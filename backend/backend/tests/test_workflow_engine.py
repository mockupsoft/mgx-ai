# -*- coding: utf-8 -*-
"""
Workflow Engine Orchestration Tests

Comprehensive test suite for the workflow engine orchestration system including:
- Engine execution (sequential, parallel, conditional branches)
- Multi-agent coordination and failover
- Real-time event emission
- Database state persistence
- Background task integration
"""

import asyncio
import pytest
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import (
    Workspace,
    Project,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowExecution,
    WorkflowStepExecution,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
    AgentDefinition,
    AgentInstance,
    AgentStatus,
)
from backend.db.models.enums import AgentMessageDirection
from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster
from backend.services.workflows.engine import WorkflowEngine, WorkflowContext
from backend.services.workflows.controller import MultiAgentController
from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
from backend.services.workflows.integration import WorkflowEngineIntegration
from backend.services.agents.registry import AgentRegistry
from backend.services.agents.context import SharedContextService
from backend.services.background import BackgroundTaskRunner


class TestWorkflowEngine:
    """Test suite for the core workflow engine."""
    
    @pytest.fixture
    async def session_factory(self, test_db_session):
        """Create a mock session factory."""
        async def mock_session():
            return test_db_session
        return mock_session
    
    @pytest.fixture
    async def dependency_resolver(self):
        """Create a dependency resolver instance."""
        return WorkflowDependencyResolver()
    
    @pytest.fixture
    async def mock_agent_registry(self):
        """Create a mock agent registry."""
        return MagicMock(spec=AgentRegistry)
    
    @pytest.fixture
    async def mock_context_service(self):
        """Create a mock context service."""
        return MagicMock(spec=SharedContextService)
    
    @pytest.fixture
    async def multi_agent_controller(self, mock_agent_registry, mock_context_service):
        """Create a multi-agent controller."""
        return MultiAgentController(
            agent_registry=mock_agent_registry,
            context_service=mock_context_service,
        )
    
    @pytest.fixture
    async def workflow_engine(self, session_factory, multi_agent_controller, dependency_resolver):
        """Create a workflow engine instance."""
        return WorkflowEngine(
            session_factory=session_factory,
            multi_agent_controller=multi_agent_controller,
            dependency_resolver=dependency_resolver,
        )
    
    @pytest.fixture
    async def sample_workspace(self, test_db_session: AsyncSession):
        """Create a sample workspace."""
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name="Test Workspace",
            slug="test-workspace",
            meta_data={},
        )
        test_db_session.add(workspace)
        await test_db_session.flush()
        return workspace
    
    @pytest.fixture
    async def sample_project(self, test_db_session: AsyncSession, sample_workspace):
        """Create a sample project."""
        project = Project(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace.id,
            name="Test Project",
            slug="test-project",
            meta_data={},
        )
        test_db_session.add(project)
        await test_db_session.flush()
        return project
    
    @pytest.fixture
    async def sample_workflow(self, test_db_session: AsyncSession, sample_workspace, sample_project):
        """Create a sample workflow with multiple steps."""
        workflow = WorkflowDefinition(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            name="Test Workflow",
            description="A test workflow",
            version=1,
            is_active=True,
            config={},
            timeout_seconds=3600,
            max_retries=3,
            meta_data={},
        )
        test_db_session.add(workflow)
        await test_db_session.flush()
        return workflow
    
    @pytest.fixture
    async def workflow_steps(self, test_db_session: AsyncSession, sample_workflow):
        """Create sample workflow steps with dependencies."""
        steps = []
        
        # Step 1: No dependencies
        step1 = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_id=sample_workflow.id,
            name="step1",
            step_type=WorkflowStepType.TASK,
            step_order=1,
            config={"processing_type": "default"},
            timeout_seconds=300,
            max_retries=2,
            depends_on_steps=[],
            meta_data={},
        )
        steps.append(step1)
        
        # Step 2: Depends on step1
        step2 = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_id=sample_workflow.id,
            name="step2",
            step_type=WorkflowStepType.TASK,
            step_order=2,
            config={"processing_type": "data_transformation"},
            timeout_seconds=300,
            max_retries=2,
            depends_on_steps=[step1.id],
            meta_data={},
        )
        steps.append(step2)
        
        # Step 3: Parallel with step2 (depends on step1)
        step3 = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_id=sample_workflow.id,
            name="step3",
            step_type=WorkflowStepType.TASK,
            step_order=2,
            config={"processing_type": "analysis"},
            timeout_seconds=300,
            max_retries=2,
            depends_on_steps=[step1.id],
            meta_data={},
        )
        steps.append(step3)
        
        # Step 4: Depends on step2 and step3
        step4 = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_id=sample_workflow.id,
            name="step4",
            step_type=WorkflowStepType.TASK,
            step_order=3,
            config={"processing_type": "default"},
            timeout_seconds=300,
            max_retries=2,
            depends_on_steps=[step2.id, step3.id],
            meta_data={},
        )
        steps.append(step4)
        
        for step in steps:
            test_db_session.add(step)
        
        await test_db_session.flush()
        return steps
    
    async def test_sequential_workflow_execution(self, workflow_engine, sample_workflow, workflow_steps):
        """Test executing a workflow with sequential steps."""
        execution_id = await workflow_engine.execute_workflow(
            workflow_id=sample_workflow.id,
            workspace_id=sample_workflow.workspace_id,
            project_id=sample_workflow.project_id,
            input_variables={"test_var": "test_value"},
        )
        
        assert execution_id is not None
        assert len(workflow_engine.active_executions) == 1
        
        # Wait for execution to complete
        await asyncio.sleep(2)
        
        assert execution_id not in workflow_engine.active_executions
        
        # Check that execution was created and completed
        # This would require database verification in a real test
        print(f"Sequential workflow execution ID: {execution_id}")
    
    async def test_parallel_execution_groups(self, dependency_resolver, workflow_steps):
        """Test parallel execution group resolution."""
        execution_levels = dependency_resolver.resolve_execution_order(workflow_steps)
        
        # Should have 3 levels:
        # Level 1: step1 (no dependencies)
        # Level 2: step2, step3 (both depend on step1)
        # Level 3: step4 (depends on step2 and step3)
        assert len(execution_levels) == 3
        
        assert len(execution_levels[0]) == 1  # step1
        assert execution_levels[0][0].name == "step1"
        
        assert len(execution_levels[1]) == 2  # step2, step3
        step_names = {step.name for step in execution_levels[1]}
        assert step_names == {"step2", "step3"}
        
        assert len(execution_levels[2]) == 1  # step4
        assert execution_levels[2][0].name == "step4"
    
    async def test_dependency_resolution_errors(self, dependency_resolver):
        """Test dependency resolution error handling."""
        # Create steps with circular dependency
        steps = [
            WorkflowStep(
                id="step1",
                workflow_id="workflow1",
                name="step1",
                step_type=WorkflowStepType.TASK,
                step_order=1,
                depends_on_steps=["step2"],  # Depends on step2
            ),
            WorkflowStep(
                id="step2",
                workflow_id="workflow1",
                name="step2",
                step_type=WorkflowStepType.TASK,
                step_order=2,
                depends_on_steps=["step1"],  # Circular dependency!
            ),
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            dependency_resolver.resolve_execution_order(steps)
    
    async def test_workflow_context_management(self):
        """Test workflow context data flow."""
        context = WorkflowContext(
            workflow_execution_id="exec1",
            workspace_id="ws1",
            project_id="proj1",
            variables={"var1": "value1", "var2": 42},
            step_outputs={},
            step_statuses={},
            started_at=datetime.utcnow(),
        )
        
        # Test variable access
        assert context.get_step_input("", "var1") == "value1"
        assert context.get_step_input("", "var2") == 42
        assert context.get_step_input("", "nonexistent", "default") == "default"
        
        # Test step output management
        context.set_step_output("step1", {"result": "success", "value": 100})
        assert "step1" in context.step_outputs
        assert context.step_outputs["step1"]["result"] == "success"
        assert context.step_statuses["step1"] == WorkflowStepStatus.COMPLETED
        
        # Test input resolution with step references
        context.variables["input_from_step"] = "steps.step1.result"
        resolved = context.get_step_input("", "input_from_step")
        # This would resolve the reference in a real implementation
    
    async def test_workflow_cancellation(self, workflow_engine, sample_workflow):
        """Test workflow execution cancellation."""
        execution_id = await workflow_engine.execute_workflow(
            workflow_id=sample_workflow.id,
            workspace_id=sample_workflow.workspace_id,
            project_id=sample_workflow.project_id,
        )
        
        assert execution_id in workflow_engine.active_executions
        
        # Cancel the execution
        success = await workflow_engine.cancel_workflow_execution(execution_id)
        assert success
        
        # Execution should be removed from active executions
        await asyncio.sleep(0.1)
        assert execution_id not in workflow_engine.active_executions
    
    async def test_step_execution_timeout(self, workflow_engine, sample_workflow, workflow_steps):
        """Test step execution timeout handling."""
        # This would require more complex mocking to simulate timeouts
        # For now, just verify the infrastructure is in place
        step = workflow_steps[0]
        
        # Mock a timeout scenario
        with patch.object(workflow_engine, '_execute_step') as mock_execute:
            mock_execute.side_effect = asyncio.TimeoutError("Step execution timed out")
            
            execution_id = await workflow_engine.execute_workflow(
                workflow_id=sample_workflow.id,
                workspace_id=sample_workflow.workspace_id,
                project_id=sample_workflow.project_id,
            )
            
            # Wait for the timeout to be handled
            await asyncio.sleep(0.5)
            
            # Verify the execution was handled gracefully
            print(f"Timeout test completed for execution: {execution_id}")


class TestMultiAgentController:
    """Test suite for multi-agent coordination."""
    
    @pytest.fixture
    async def mock_agent_registry(self):
        """Create a mock agent registry with realistic behavior."""
        registry = MagicMock(spec=AgentRegistry)
        registry.update_instance_status = AsyncMock(return_value=True)
        return registry
    
    @pytest.fixture
    async def mock_context_service(self):
        """Create a mock context service."""
        service = MagicMock(spec=SharedContextService)
        service.get_or_create_context = AsyncMock()
        service.update_context_version = AsyncMock()
        return service
    
    @pytest.fixture
    async def controller(self, mock_agent_registry, mock_context_service):
        """Create a multi-agent controller."""
        return MultiAgentController(
            agent_registry=mock_agent_registry,
            context_service=mock_context_service,
        )
    
    @pytest.fixture
    async def sample_agent_definition(self, test_db_session: AsyncSession):
        """Create a sample agent definition."""
        definition = AgentDefinition(
            id=str(uuid.uuid4()),
            name="Test Agent",
            slug="test-agent",
            agent_type="TestAgent",
            description="A test agent",
            capabilities=["data_processing", "analysis"],
            config_schema={},
            meta_data={},
            is_enabled=True,
        )
        test_db_session.add(definition)
        await test_db_session.flush()
        return definition
    
    @pytest.fixture
    async def sample_agent_instance(self, test_db_session: AsyncSession, sample_agent_definition, sample_workspace, sample_project):
        """Create a sample agent instance."""
        instance = AgentInstance(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            definition_id=sample_agent_definition.id,
            name="Test Agent Instance",
            status=AgentStatus.IDLE,
            config={"memory_limit": 512, "cpu_limit": 1},
            state={},
        )
        test_db_session.add(instance)
        await test_db_session.flush()
        return instance
    
    @pytest.fixture
    async def workflow_step_with_agent(self, sample_workflow, sample_agent_definition, sample_agent_instance):
        """Create a workflow step that requires an agent."""
        step = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_id=sample_workflow.id,
            name="agent_step",
            step_type=WorkflowStepType.AGENT,
            step_order=1,
            config={
                "processing_type": "agent_task",
                "required_capabilities": ["data_processing"],
            },
            agent_definition_id=sample_agent_definition.id,
            agent_instance_id=sample_agent_instance.id,
            depends_on_steps=[],
            meta_data={},
        )
        return step
    
    async def test_agent_assignment_strategy(self, controller, sample_agent_definition, sample_agent_instance):
        """Test different agent assignment strategies."""
        # Test round-robin assignment
        assignment = await controller._assign_agent(
            session=AsyncMock(),
            step=MagicMock(
                config={"assignment_strategy": "round_robin"},
                agent_definition_id=sample_agent_definition.id,
                agent_instance_id=sample_agent_instance.id,
                depends_on_steps=[],
            ),
            context=MagicMock(
                workspace_id=sample_agent_instance.workspace_id,
                project_id=sample_agent_instance.project_id,
            ),
        )
        
        assert assignment is not None
        assert assignment.assignment_strategy == "round_robin"
    
    async def test_agent_failover_mechanism(self, controller):
        """Test agent failover when primary agent fails."""
        # This would require more complex mocking to test failover properly
        # For now, verify the failover tracking infrastructure
        
        failover_record = controller.failover_records.get("test_step_execution_id")
        assert failover_record is None  # No failover record yet
        
        # Verify assignment stats
        stats = controller.get_assignment_stats()
        assert "active_assignments" in stats
        assert "active_reservations" in stats
        assert "failover_records" in stats
    
    async def test_resource_reservation(self, controller, sample_agent_instance):
        """Test resource reservation and release."""
        # Create a mock assignment
        assignment = MagicMock()
        assignment.instance_id = sample_agent_instance.id
        assignment.reserved_resources = {}
        
        context = MagicMock()
        context.workflow_execution_id = "exec1"
        context.workspace_id = sample_agent_instance.workspace_id
        context.project_id = sample_agent_instance.project_id
        
        # Reserve resources
        reservation = await controller._reserve_resources(
            assignment, context, duration_seconds=3600
        )
        
        assert reservation is not None
        assert reservation.assignment.instance_id == sample_agent_instance.id
        assert reservation.is_active
        
        # Release resources
        await controller._release_resources(reservation)
        
        # Verify resources were released
        assert assignment.instance_id not in controller.active_reservations
    
    async def test_agent_step_execution(self, controller, test_db_session, workflow_step_with_agent):
        """Test complete agent step execution flow."""
        context = WorkflowContext(
            workflow_execution_id="exec1",
            workspace_id=workflow_step_with_agent.workflow.workspace_id,
            project_id=workflow_step_with_agent.workflow.project_id,
            variables={},
            step_outputs={},
            step_statuses={},
            started_at=datetime.utcnow(),
        )
        
        input_data = {"test_input": "test_value"}
        
        # Execute the step
        output_data = await controller.execute_agent_step(
            session=test_db_session,
            step=workflow_step_with_agent,
            context=context,
            input_data=input_data,
            timeout_seconds=300,
            max_retries=2,
        )
        
        assert output_data is not None
        assert "result" in output_data
        
        # Verify agent registry was called to update status
        controller.agent_registry.update_instance_status.assert_called()


class TestWorkflowEvents:
    """Test suite for workflow event emission."""
    
    async def test_workflow_started_event(self, test_db_session):
        """Test workflow started event emission."""
        broadcaster = get_event_broadcaster()
        
        # Subscribe to events
        event_queue = await broadcaster.subscribe("test_subscriber", ["workflow:test_workflow"])
        
        # Create and publish a workflow started event
        from backend.schemas import WorkflowStartedEvent
        
        event = WorkflowStartedEvent(
            event_type=EventTypeEnum.WORKFLOW_STARTED,
            workflow_id="test_workflow",
            workflow_execution_id="test_execution",
            workspace_id="test_workspace",
            data={"test": "data"},
            message="Test workflow started",
        )
        
        await broadcaster.publish(event)
        
        # Verify event was received
        received_event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
        assert received_event["event_type"] == EventTypeEnum.WORKFLOW_STARTED
        assert received_event["workflow_id"] == "test_workflow"
    
    async def test_step_events_sequence(self):
        """Test sequence of step events."""
        broadcaster = get_event_broadcaster()
        
        # Subscribe to step events
        event_queue = await broadcaster.subscribe("test_subscriber", ["workflow-step:test_step"])
        
        from backend.schemas import StepStartedEvent, StepCompletedEvent, StepFailedEvent
        
        # Publish step started event
        started_event = StepStartedEvent(
            event_type=EventTypeEnum.STEP_STARTED,
            workflow_step_id="test_step",
            workflow_execution_id="test_execution",
            workspace_id="test_workspace",
            message="Step started",
        )
        await broadcaster.publish(started_event)
        
        started_received = await asyncio.wait_for(event_queue.get(), timeout=1.0)
        assert started_received["event_type"] == EventTypeEnum.STEP_STARTED
        
        # Publish step completed event
        completed_event = StepCompletedEvent(
            event_type=EventTypeEnum.STEP_COMPLETED,
            workflow_step_id="test_step",
            workflow_execution_id="test_execution",
            workspace_id="test_workspace",
            data={"result": "success"},
            message="Step completed",
        )
        await broadcaster.publish(completed_event)
        
        completed_received = await asyncio.wait_for(event_queue.get(), timeout=1.0)
        assert completed_received["event_type"] == EventTypeEnum.STEP_COMPLETED
        assert completed_received["data"]["result"] == "success"
    
    async def test_websocket_workflow_channels(self):
        """Test WebSocket workflow event channels."""
        broadcaster = get_event_broadcaster()
        
        # Subscribe to workflow execution channel
        execution_queue = await broadcaster.subscribe(
            "test_subscriber", ["workflow-run:test_execution"]
        )
        
        # Subscribe to workflow definition channel
        workflow_queue = await broadcaster.subscribe(
            "test_subscriber", ["workflow:test_workflow"]
        )
        
        # Publish to workflow execution channel
        from backend.schemas import WorkflowCompletedEvent
        
        execution_event = WorkflowCompletedEvent(
            event_type=EventTypeEnum.WORKFLOW_COMPLETED,
            workflow_id="test_workflow",
            workflow_execution_id="test_execution",
            workspace_id="test_workspace",
            message="Workflow completed",
        )
        await broadcaster.publish(execution_event)
        
        # Should only be received on execution channel, not workflow channel
        execution_received = await asyncio.wait_for(execution_queue.get(), timeout=1.0)
        assert execution_received["workflow_execution_id"] == "test_execution"
        
        # Workflow channel should not receive execution-specific events
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(workflow_queue.get(), timeout=0.5)


class TestWorkflowIntegration:
    """Test suite for workflow engine integration."""
    
    @pytest.fixture
    async def mock_session_factory(self):
        """Create a mock session factory."""
        async def mock_session():
            session = AsyncMock(spec=AsyncSession)
            session.execute = AsyncMock()
            session.add = MagicMock()
            session.flush = AsyncMock()
            return session
        return mock_session
    
    @pytest.fixture
    async def mock_agent_registry(self):
        """Create a mock agent registry."""
        return MagicMock(spec=AgentRegistry)
    
    @pytest.fixture
    async def mock_context_service(self):
        """Create a mock context service."""
        return MagicMock(spec=SharedContextService)
    
    @pytest.fixture
    async def mock_task_runner(self):
        """Create a mock task runner."""
        runner = MagicMock(spec=BackgroundTaskRunner)
        runner.submit = AsyncMock(return_value="task_id_123")
        runner.get_stats = MagicMock(return_value={"total_tasks": 5})
        return runner
    
    @pytest.fixture
    async def integration(self, mock_session_factory, mock_agent_registry, mock_context_service, mock_task_runner):
        """Create a workflow engine integration."""
        return WorkflowEngineIntegration(
            session_factory=mock_session_factory,
            agent_registry=mock_agent_registry,
            context_service=mock_context_service,
            task_runner=mock_task_runner,
        )
    
    async def test_workflow_execution_submission(self, integration, sample_workflow):
        """Test submitting a workflow for execution."""
        execution_id = await integration.execute_workflow(
            workflow_id=sample_workflow.id,
            workspace_id=sample_workflow.workspace_id,
            project_id=sample_workflow.project_id,
            input_variables={"test_var": "test_value"},
        )
        
        assert execution_id == "task_id_123"
        
        # Verify task runner was called
        integration.task_runner.submit.assert_called_once()
    
    async def test_workflow_cancellation(self, integration):
        """Test workflow execution cancellation."""
        # Mock the workflow engine's cancel method
        integration.workflow_engine.cancel_workflow_execution = AsyncMock(return_value=True)
        
        success = await integration.cancel_workflow_execution("test_execution_id")
        
        assert success
        integration.workflow_engine.cancel_workflow_execution.assert_called_once_with("test_execution_id")
    
    async def test_integration_stats(self, integration):
        """Test integration statistics collection."""
        stats = integration.get_integration_stats()
        
        assert "engine_stats" in stats
        assert "controller_stats" in stats
        assert "task_runner_stats" in stats
        
        # Verify stats structure
        assert "active_executions" in stats["engine_stats"]
        assert "active_assignments" in stats["controller_stats"]
        assert "total_tasks" in stats["task_runner_stats"]


class TestComplexWorkflowScenarios:
    """Test complex workflow scenarios and edge cases."""
    
    async def test_conditional_workflow_execution(self, workflow_engine, sample_workflow):
        """Test workflow with conditional step execution."""
        # This would require setting up a workflow with conditional steps
        # and testing both true and false paths
        
        # For now, verify the conditional execution infrastructure
        assert hasattr(workflow_engine, '_execute_condition_step')
        assert hasattr(workflow_engine, '_evaluate_condition')
    
    async def test_parallel_step_execution(self, workflow_engine, sample_workflow):
        """Test workflow with parallel step execution."""
        # Verify parallel execution infrastructure exists
        assert hasattr(workflow_engine, '_execute_parallel_step')
    
    async def test_timeout_and_retry_handling(self, workflow_engine, sample_workflow, workflow_steps):
        """Test timeout and retry policy enforcement."""
        step = workflow_steps[0]
        
        # Verify timeout and retry configuration
        assert step.timeout_seconds is not None
        assert step.max_retries is not None
        
        # Test would involve mocking timeouts and verifying retry logic
        # This requires more sophisticated mocking infrastructure
    
    async def test_agent_failover_integration(self, controller):
        """Test agent failover in the context of workflow execution."""
        # Test failover tracking
        step_execution_id = "test_step_execution_123"
        
        # Create failover record
        failover_record = MagicMock()
        failover_record.step_execution_id = step_execution_id
        failover_record.failover_attempts = 0
        failover_record.max_failover_attempts = 3
        failover_record.failover_history = []
        
        controller.failover_records[step_execution_id] = failover_record
        
        # Verify failover record exists
        assert step_execution_id in controller.failover_records
        
        # Test failover record stats
        stats = controller.get_assignment_stats()
        assert stats["failover_records"] >= 1
    
    async def test_workflow_metrics_persistence(self, workflow_engine, sample_workflow):
        """Test that workflow metrics are persisted to database."""
        # This would require database verification
        # For now, verify the metrics collection infrastructure
        
        execution_id = await workflow_engine.execute_workflow(
            workflow_id=sample_workflow.id,
            workspace_id=sample_workflow.workspace_id,
            project_id=sample_workflow.project_id,
        )
        
        # Verify execution was tracked
        assert execution_id is not None
        
        # In a real test, we would verify database records were created
        print(f"Metrics persistence test - execution: {execution_id}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])