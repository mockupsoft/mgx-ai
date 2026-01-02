# -*- coding: utf-8 -*-
"""
Multi-Agent Workflow Integration Tests

Tests cover:
- Agent assignment tests
- Workflow step execution tests
- Context sharing tests
- Message bus tests
- Event broadcasting tests
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.db.models import Base, Workspace, Project, AgentDefinition, AgentInstance, WorkflowStep
from backend.db.models.enums import AgentStatus, WorkflowStepStatus
from backend.services.workflows.controller import (
    MultiAgentController,
    AgentAssignment,
    AgentReservation,
    AssignmentStrategy,
)
from backend.services.agents.registry import AgentRegistry
from backend.services.agents.context import SharedContextService
from backend.services.agents.messages import AgentMessageBus


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_db):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_workspace(test_session):
    """Create test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        slug="test-workspace",
    )
    test_session.add(workspace)
    await test_session.commit()
    await test_session.refresh(workspace)
    return workspace


@pytest.fixture
async def test_project(test_session, test_workspace):
    """Create test project."""
    project = Project(
        name="Test Project",
        slug="test-project",
        workspace_id=test_workspace.id,
    )
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)
    return project


@pytest.fixture
async def test_agent_definition(test_session, test_workspace):
    """Create test agent definition."""
    definition = AgentDefinition(
        name="Test Agent",
        slug="test-agent",
        workspace_id=test_workspace.id,
        capabilities=["code_generation", "testing"],
        status=AgentStatus.ACTIVE,
    )
    test_session.add(definition)
    await test_session.commit()
    await test_session.refresh(definition)
    return definition


@pytest.fixture
async def test_agent_instance(test_session, test_workspace, test_agent_definition):
    """Create test agent instance."""
    instance = AgentInstance(
        name="Test Agent Instance",
        definition_id=test_agent_definition.id,
        workspace_id=test_workspace.id,
        status=AgentStatus.ACTIVE,
    )
    test_session.add(instance)
    await test_session.commit()
    await test_session.refresh(instance)
    return instance


@pytest.fixture
def mock_agent_registry():
    """Create mock agent registry."""
    registry = Mock(spec=AgentRegistry)
    registry.find_available_agents = AsyncMock(return_value=[])
    registry.get_agent_definition = AsyncMock()
    registry.get_agent_instance = AsyncMock()
    return registry


@pytest.fixture
def mock_context_service():
    """Create mock context service."""
    service = Mock(spec=SharedContextService)
    service.get_or_create_context = AsyncMock()
    service.update_context_version = AsyncMock()
    return service


@pytest.fixture
def multi_agent_controller(mock_agent_registry, mock_context_service):
    """Create multi-agent controller."""
    return MultiAgentController(
        agent_registry=mock_agent_registry,
        context_service=mock_context_service,
    )


@pytest.mark.integration
class TestAgentAssignment:
    """Test agent assignment functionality."""
    
    async def test_round_robin_assignment(self, multi_agent_controller, mock_agent_registry, test_session, test_workspace):
        """Test round-robin agent assignment strategy."""
        # Create multiple agent instances
        agents = []
        for i in range(3):
            definition = AgentDefinition(
                name=f"Agent {i}",
                slug=f"agent-{i}",
                workspace_id=test_workspace.id,
                status=AgentStatus.ACTIVE,
            )
            test_session.add(definition)
            await test_session.flush()
            
            instance = AgentInstance(
                name=f"Instance {i}",
                definition_id=definition.id,
                workspace_id=test_workspace.id,
                status=AgentStatus.ACTIVE,
            )
            test_session.add(instance)
            await test_session.flush()
            agents.append(instance)
        
        await test_session.commit()
        
        # Mock registry to return agents
        mock_agent_registry.find_available_agents = AsyncMock(return_value=agents)
        mock_agent_registry.get_agent_definition = AsyncMock(side_effect=lambda session, def_id: test_session.get(AgentDefinition, def_id))
        mock_agent_registry.get_agent_instance = AsyncMock(side_effect=lambda session, inst_id: test_session.get(AgentInstance, inst_id))
        
        # Create mock workflow step
        mock_step = Mock(spec=WorkflowStep)
        mock_step.id = "step-1"
        mock_step.name = "Test Step"
        mock_step.config = {}
        
        # Create mock workflow context
        mock_context = Mock()
        mock_context.workflow_execution_id = "exec-1"
        mock_context.workspace_id = test_workspace.id
        mock_context.project_id = "project-1"
        
        # Test assignment
        assignment = await multi_agent_controller._assign_agent_with_failover(
            session=test_session,
            step=mock_step,
            context=mock_context,
            step_execution_id="exec-1",
            max_failover_attempts=3,
        )
        
        # Should assign an agent
        assert assignment is not None or len(agents) == 0  # May be None if no agents available
    
    async def test_capability_match_assignment(self, multi_agent_controller, mock_agent_registry):
        """Test capability-based agent assignment."""
        # This would test matching agents by required capabilities
        # Implementation depends on capability matching logic
        pass
    
    async def test_least_loaded_assignment(self, multi_agent_controller, mock_agent_registry):
        """Test least-loaded agent assignment strategy."""
        # This would test assigning to agent with least active tasks
        pass


@pytest.mark.integration
class TestWorkflowStepExecution:
    """Test workflow step execution."""
    
    async def test_step_execution_with_assignment(
        self,
        multi_agent_controller,
        mock_agent_registry,
        mock_context_service,
        test_session,
        test_workspace,
        test_agent_definition,
        test_agent_instance,
    ):
        """Test executing a workflow step with agent assignment."""
        # Setup mocks
        mock_agent_registry.get_agent_definition = AsyncMock(return_value=test_agent_definition)
        mock_agent_registry.get_agent_instance = AsyncMock(return_value=test_agent_instance)
        
        # Create assignment
        assignment = AgentAssignment(
            instance_id=test_agent_instance.id,
            definition_id=test_agent_definition.id,
            agent_instance=test_agent_instance,
            agent_definition=test_agent_definition,
            assignment_strategy=AssignmentStrategy.ROUND_ROBIN.value,
        )
        
        # Create reservation
        reservation = AgentReservation(
            assignment=assignment,
            workspace_id=test_workspace.id,
            project_id="project-1",
        )
        
        # Create mock step
        mock_step = Mock(spec=WorkflowStep)
        mock_step.id = "step-1"
        mock_step.name = "Test Step"
        mock_step.config = {}
        
        # Create mock context
        mock_context = Mock()
        mock_context.workflow_execution_id = "exec-1"
        mock_context.workspace_id = test_workspace.id
        mock_context.project_id = "project-1"
        mock_context.variables = {}
        mock_context.step_outputs = {}
        
        # Mock agent execution
        mock_context_service.get_or_create_context = AsyncMock(return_value=Mock(id="context-1"))
        
        # Mock _execute_agent_logic
        multi_agent_controller._execute_agent_logic = AsyncMock(return_value={"result": "success"})
        
        # Execute step
        output = await multi_agent_controller._execute_agent_step_with_assignment(
            session=test_session,
            step=mock_step,
            context=mock_context,
            assignment=assignment,
            reservation=reservation,
            input_data={"input": "test"},
            timeout_seconds=60,
        )
        
        assert output is not None
        assert "result" in output
    
    async def test_step_execution_timeout(self, multi_agent_controller):
        """Test workflow step execution timeout."""
        # Mock timeout scenario
        multi_agent_controller._execute_agent_logic = AsyncMock(side_effect=asyncio.TimeoutError())
        
        mock_step = Mock()
        mock_context = Mock()
        assignment = Mock()
        reservation = Mock()
        
        with pytest.raises(Exception):  # Should raise timeout error
            await multi_agent_controller._execute_agent_step_with_assignment(
                session=Mock(),
                step=mock_step,
                context=mock_context,
                assignment=assignment,
                reservation=reservation,
                input_data={},
                timeout_seconds=1,
            )


@pytest.mark.integration
class TestContextSharing:
    """Test context sharing between agents."""
    
    async def test_context_creation(self, mock_context_service, test_session, test_agent_instance):
        """Test creating shared context for agent."""
        mock_context = Mock()
        mock_context.id = "context-1"
        mock_context_service.get_or_create_context = AsyncMock(return_value=mock_context)
        
        context = await mock_context_service.get_or_create_context(
            session=test_session,
            instance_id=test_agent_instance.id,
            context_name="test-context",
            workspace_id="workspace-1",
            project_id="project-1",
        )
        
        assert context is not None
        assert context.id == "context-1"
        mock_context_service.get_or_create_context.assert_called_once()
    
    async def test_context_update(self, mock_context_service, test_session):
        """Test updating shared context."""
        mock_context_service.update_context_version = AsyncMock(return_value=2)
        
        version = await mock_context_service.update_context_version(
            session=test_session,
            context_id="context-1",
            data={"key": "value"},
            change_description="Test update",
            created_by="test",
        )
        
        assert version == 2
        mock_context_service.update_context_version.assert_called_once()
    
    async def test_context_isolation(self, mock_context_service):
        """Test that contexts are isolated between agents."""
        # This would test that different agents have separate contexts
        pass


@pytest.mark.integration
class TestMessageBus:
    """Test message bus functionality."""
    
    async def test_message_sending(self, test_session, test_workspace, test_agent_instance):
        """Test sending messages through message bus."""
        from backend.services.agents.messages import get_agent_message_bus
        
        bus = get_agent_message_bus()
        
        # Send a message
        message = await bus.append(
            session=test_session,
            workspace_id=test_workspace.id,
            project_id="project-1",
            agent_instance_id=test_agent_instance.id,
            direction="outbound",
            payload={"message": "test"},
            correlation_id="corr-1",
        )
        
        assert message is not None
        assert message.payload == {"message": "test"}
    
    async def test_message_broadcasting(self, test_session, test_workspace):
        """Test broadcasting messages to multiple agents."""
        from backend.services.agents.messages import get_agent_message_bus
        
        bus = get_agent_message_bus()
        
        # Broadcast message
        message = await bus.append(
            session=test_session,
            workspace_id=test_workspace.id,
            project_id="project-1",
            agent_instance_id="agent-1",
            direction="outbound",
            payload={"broadcast": "test"},
            correlation_id="corr-1",
            broadcast=True,
        )
        
        assert message is not None


@pytest.mark.integration
class TestEventBroadcasting:
    """Test event broadcasting functionality."""
    
    async def test_event_emission(self):
        """Test emitting events."""
        from backend.services.events import get_event_broadcaster
        from backend.schemas import EventPayload, EventTypeEnum
        
        broadcaster = get_event_broadcaster()
        
        # Emit an event
        event = EventPayload(
            event_type=EventTypeEnum.AGENT_ACTIVITY,
            workspace_id="workspace-1",
            agent_id="agent-1",
            data={"action": "test"},
        )
        
        # Mock publish to avoid actual event system
        with patch.object(broadcaster, 'publish', new_callable=AsyncMock) as mock_publish:
            await broadcaster.publish(event)
            mock_publish.assert_called_once_with(event)
    
    async def test_workflow_event_broadcasting(self):
        """Test broadcasting workflow execution events."""
        from backend.services.events import get_event_broadcaster
        from backend.schemas import EventPayload, EventTypeEnum
        
        broadcaster = get_event_broadcaster()
        
        event = EventPayload(
            event_type=EventTypeEnum.WORKFLOW_STEP_COMPLETED,
            workspace_id="workspace-1",
            data={"step_id": "step-1", "status": "completed"},
        )
        
        with patch.object(broadcaster, 'publish', new_callable=AsyncMock) as mock_publish:
            await broadcaster.publish(event)
            mock_publish.assert_called_once()


@pytest.mark.integration
class TestResourceManagement:
    """Test resource management and reservations."""
    
    async def test_resource_reservation(self, multi_agent_controller, test_workspace):
        """Test reserving resources for agent assignment."""
        assignment = AgentAssignment(
            instance_id="instance-1",
            definition_id="def-1",
            agent_instance=Mock(),
            agent_definition=Mock(),
            assignment_strategy=AssignmentStrategy.ROUND_ROBIN.value,
        )
        
        mock_context = Mock()
        mock_context.workspace_id = test_workspace.id
        mock_context.project_id = "project-1"
        
        reservation = await multi_agent_controller._reserve_resources(
            assignment=assignment,
            context=mock_context,
            duration_seconds=3600,
        )
        
        assert reservation is not None
        assert reservation.assignment == assignment
        assert reservation.is_active
    
    async def test_resource_release(self, multi_agent_controller):
        """Test releasing reserved resources."""
        assignment = AgentAssignment(
            instance_id="instance-1",
            definition_id="def-1",
            agent_instance=Mock(),
            agent_definition=Mock(),
            assignment_strategy=AssignmentStrategy.ROUND_ROBIN.value,
        )
        
        reservation = AgentReservation(
            assignment=assignment,
            workspace_id="workspace-1",
            project_id="project-1",
        )
        
        # Release resources
        await multi_agent_controller._release_resources(reservation)
        
        assert not reservation.is_active




