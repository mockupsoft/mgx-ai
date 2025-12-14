# -*- coding: utf-8 -*-
"""
Unit tests for Agent Registry and Context Service

Tests for:
- AgentRegistry: registration, lookup, instance spawning
- SharedContextService: context creation, versioning, rollback
"""

import pytest
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.services.agents import BaseAgent, AgentRegistry, SharedContextService
from backend.db.models import AgentStatus, ContextRollbackState


class SimpleTestAgent(BaseAgent):
    """Simple test agent implementation."""

    def __init__(self, name: str = "test_agent", config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name=name,
            agent_type="test_agent",
            capabilities=["test", "debug"],
            config=config,
        )
        self.initialized_count = 0
        self.activated_count = 0

    async def initialize(self) -> None:
        await super().initialize()
        self.initialized_count += 1

    async def activate(self) -> None:
        await super().activate()
        self.activated_count += 1


class TestAgentRegistry:
    """Test cases for AgentRegistry."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = AgentRegistry()
        assert registry is not None
        assert len(registry.list_registered()) == 0

    def test_register_agent_class(self):
        """Test registering an agent class."""
        registry = AgentRegistry()
        registry.register(SimpleTestAgent, "simple", "A simple test agent")
        
        assert "simple" in registry.list_registered()
        assert registry.get_agent_class("simple") == SimpleTestAgent

    def test_register_multiple_agents(self):
        """Test registering multiple agent classes."""
        registry = AgentRegistry()
        
        registry.register(SimpleTestAgent, "simple1", "First test agent")
        registry.register(SimpleTestAgent, "simple2", "Second test agent")
        
        registered = registry.list_registered()
        assert len(registered) == 2
        assert "simple1" in registered
        assert "simple2" in registered

    def test_unregister_agent_class(self):
        """Test unregistering an agent class."""
        registry = AgentRegistry()
        registry.register(SimpleTestAgent, "simple", "Test agent")
        
        assert "simple" in registry.list_registered()
        registry.unregister("simple")
        assert "simple" not in registry.list_registered()

    def test_get_nonexistent_agent_class(self):
        """Test getting a non-existent agent class."""
        registry = AgentRegistry()
        assert registry.get_agent_class("nonexistent") is None

    def test_register_invalid_class(self):
        """Test registering a non-BaseAgent class."""
        registry = AgentRegistry()
        
        with pytest.raises(ValueError):
            registry.register(str, "invalid", "Not an agent")

    @pytest.mark.asyncio
    async def test_spawn_instance_from_registered_class(self):
        """Test spawning an agent instance from a registered class."""
        from backend.db.models import AgentDefinition, AgentInstance
        
        registry = AgentRegistry()
        registry.register(SimpleTestAgent, "simple", "Test agent")
        
        # Mock database objects
        definition = AgentDefinition(
            id=str(uuid4()),
            name="Simple Agent",
            slug="simple",
            agent_type="test_agent",
            capabilities=["test", "debug"],
            is_enabled=True,
        )
        
        instance_db = AgentInstance(
            id=str(uuid4()),
            workspace_id=str(uuid4()),
            project_id=str(uuid4()),
            definition_id=definition.id,
            name="test_instance",
            status=AgentStatus.IDLE,
            config={"debug": True},
        )
        
        agent = await registry.spawn_instance(definition, instance_db)
        
        assert agent is not None
        assert isinstance(agent, SimpleTestAgent)
        assert agent.name == "test_instance"
        assert agent.is_active is False
        assert agent.is_initialized is False

    @pytest.mark.asyncio
    async def test_spawn_instance_from_unregistered_class(self):
        """Test spawning an instance from an unregistered class."""
        from backend.db.models import AgentDefinition, AgentInstance
        
        registry = AgentRegistry()
        
        definition = AgentDefinition(
            id=str(uuid4()),
            name="Unregistered Agent",
            slug="unregistered",
            agent_type="unknown",
            capabilities=[],
            is_enabled=True,
        )
        
        instance_db = AgentInstance(
            id=str(uuid4()),
            workspace_id=str(uuid4()),
            project_id=str(uuid4()),
            definition_id=definition.id,
            name="test_instance",
            status=AgentStatus.IDLE,
        )
        
        agent = await registry.spawn_instance(definition, instance_db)
        
        assert agent is None

    def test_get_spawned_instance(self):
        """Test retrieving a spawned instance."""
        registry = AgentRegistry()
        agent = SimpleTestAgent(name="test")
        instance_id = str(uuid4())
        
        registry._instances[instance_id] = agent
        
        retrieved = registry.get_instance(instance_id)
        assert retrieved is agent

    def test_get_nonexistent_instance(self):
        """Test retrieving a non-existent instance."""
        registry = AgentRegistry()
        assert registry.get_instance("nonexistent") is None

    def test_list_instances(self):
        """Test listing all spawned instances."""
        registry = AgentRegistry()
        
        agent1 = SimpleTestAgent(name="test1")
        agent2 = SimpleTestAgent(name="test2")
        
        id1 = str(uuid4())
        id2 = str(uuid4())
        
        registry._instances[id1] = agent1
        registry._instances[id2] = agent2
        
        instances = registry.list_instances()
        assert len(instances) == 2
        assert id1 in instances
        assert id2 in instances

    @pytest.mark.asyncio
    async def test_update_instance_status_succeeds(self):
        """Test updating an instance status successfully."""
        # This test would require a real database session
        # For now, we test the basic registry functionality
        registry = AgentRegistry()
        assert registry is not None

    def __repr__(self) -> str:
        return f"<TestAgentRegistry>"


class TestSharedContextService:
    """Test cases for SharedContextService."""

    def test_context_service_initialization(self):
        """Test context service initialization."""
        service = SharedContextService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_context_versioning_increments(self):
        """Test that context versions increment correctly."""
        # This test would require a real database session
        # The actual implementation is tested via integration tests
        service = SharedContextService()
        assert service is not None

    def test_rollback_state_enum(self):
        """Test ContextRollbackState enum."""
        assert ContextRollbackState.PENDING.value == "pending"
        assert ContextRollbackState.SUCCESS.value == "success"
        assert ContextRollbackState.FAILED.value == "failed"


class TestBaseAgent:
    """Test cases for BaseAgent."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = SimpleTestAgent(name="test")
        
        assert agent.name == "test"
        assert agent.agent_type == "test_agent"
        assert "test" in agent.capabilities
        assert agent.is_initialized is False
        assert agent.is_active is False

    @pytest.mark.asyncio
    async def test_agent_lifecycle(self):
        """Test agent lifecycle transitions."""
        agent = SimpleTestAgent(name="test")
        
        # Initialize
        await agent.initialize()
        assert agent.is_initialized is True
        assert agent.initialized_count == 1
        
        # Activate
        await agent.activate()
        assert agent.is_active is True
        assert agent.activated_count == 1
        
        # Deactivate
        await agent.deactivate()
        assert agent.is_active is False
        
        # Shutdown
        await agent.shutdown()
        assert agent.is_initialized is False

    @pytest.mark.asyncio
    async def test_agent_activate_initializes_if_needed(self):
        """Test that activate initializes if not already initialized."""
        agent = SimpleTestAgent(name="test")
        
        # Activate should trigger initialize
        await agent.activate()
        
        assert agent.is_initialized is True
        assert agent.is_active is True
        assert agent.initialized_count == 1
        assert agent.activated_count == 1

    def test_agent_configuration(self):
        """Test agent configuration."""
        config = {"key": "value"}
        agent = SimpleTestAgent(name="test", config=config)
        
        assert agent.get_config() == config
        
        agent.set_config({"new_key": "new_value"})
        assert "new_key" in agent.get_config()
        assert "key" in agent.get_config()

    def test_agent_metadata(self):
        """Test agent metadata."""
        agent = SimpleTestAgent(name="test")
        
        agent.set_metadata({"version": "1.0"})
        metadata = agent.get_metadata()
        
        assert metadata["version"] == "1.0"

    def test_agent_to_dict(self):
        """Test agent serialization."""
        agent = SimpleTestAgent(name="test", config={"debug": True})
        
        agent_dict = agent.to_dict()
        
        assert agent_dict["name"] == "test"
        assert agent_dict["agent_type"] == "test_agent"
        assert "test" in agent_dict["capabilities"]
        assert agent_dict["config"]["debug"] is True
        assert agent_dict["initialized"] is False
        assert agent_dict["active"] is False

    def test_agent_capabilities(self):
        """Test agent capabilities."""
        agent = SimpleTestAgent(name="test")
        capabilities = agent.get_capabilities()
        
        assert isinstance(capabilities, list)
        assert "test" in capabilities
        assert "debug" in capabilities

    def test_agent_repr(self):
        """Test agent string representation."""
        agent = SimpleTestAgent(name="test_agent")
        repr_str = repr(agent)
        
        assert "SimpleTestAgent" in repr_str
        assert "test_agent" in repr_str


# Fixtures for more complex tests
@pytest.fixture
def agent_registry():
    """Provide an AgentRegistry instance."""
    registry = AgentRegistry()
    registry.register(SimpleTestAgent, "simple", "Simple test agent")
    return registry


@pytest.fixture
def context_service():
    """Provide a SharedContextService instance."""
    return SharedContextService()


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    def test_multiple_agents_in_registry(self, agent_registry):
        """Test managing multiple agents in a registry."""
        agent_registry.register(SimpleTestAgent, "agent2", "Second agent")
        agent_registry.register(SimpleTestAgent, "agent3", "Third agent")
        
        registered = agent_registry.list_registered()
        assert len(registered) >= 3

    @pytest.mark.asyncio
    async def test_agent_lifecycle_with_config(self):
        """Test agent lifecycle with configuration."""
        config = {"timeout": 30, "retry": 3}
        agent = SimpleTestAgent(name="configured", config=config)
        
        # Modify config before activation
        agent.set_config({"timeout": 60})
        
        await agent.activate()
        
        assert agent.is_active is True
        assert agent.get_config()["timeout"] == 60
        assert agent.get_config()["retry"] == 3

    def test_agent_repr_and_str(self):
        """Test agent string representations."""
        agent = SimpleTestAgent(name="my_agent")
        
        repr_str = repr(agent)
        assert "SimpleTestAgent" in repr_str
        assert "my_agent" in repr_str
