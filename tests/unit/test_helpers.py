# -*- coding: utf-8 -*-
"""
Unit tests for test helpers and stubs.

Verifies that the test infrastructure is properly set up and functional.
"""

import pytest
from tests.helpers import (
    MockAction,
    MockRole,
    MockTeam,
    MockMessage,
    mock_logger,
    create_fake_team,
    create_fake_role,
    create_fake_action,
    create_fake_memory_store,
    create_fake_llm_response,
)


class TestMockLogger:
    """Test MockLogger functionality."""
    
    def test_logger_creation(self):
        """Test logger can be created and used."""
        logger = mock_logger
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'debug')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'error')
    
    def test_logger_recording(self):
        """Test logger records messages."""
        mock_logger.clear()
        mock_logger.info("Test message")
        
        assert len(mock_logger.messages) > 0
        assert any("Test message" in msg[1] for msg in mock_logger.messages)


class TestMockMessage:
    """Test MockMessage functionality."""
    
    def test_message_creation(self):
        """Test message can be created."""
        msg = MockMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
    
    def test_message_with_name(self):
        """Test message with name."""
        msg = MockMessage(role="assistant", content="Response", name="TestRole")
        assert msg.name == "TestRole"
        assert msg.role == "assistant"
    
    def test_message_string_representation(self):
        """Test message string representation."""
        msg = MockMessage(role="user", content="Test content")
        str_repr = str(msg)
        assert "MockMessage" in str_repr
        assert "user" in str_repr


class TestMockAction:
    """Test MockAction functionality."""
    
    def test_action_creation(self):
        """Test action can be created."""
        action = MockAction(name="TestAction")
        assert action.name == "TestAction"
        assert action.profile is not None
        assert action.desc is not None
    
    def test_action_reset(self):
        """Test action reset works."""
        action = MockAction()
        action.called = True
        action.call_count = 5
        
        action.reset()
        
        assert action.called is False
        assert action.call_count == 0
    
    @pytest.mark.asyncio
    async def test_action_run(self):
        """Test action run method."""
        action = MockAction(name="TestAction")
        result = await action.run("arg1", kwarg1="value1")
        
        assert action.called is True
        assert action.call_count == 1
        assert "TestAction" in result


class TestMockRole:
    """Test MockRole functionality."""
    
    def test_role_creation(self):
        """Test role can be created."""
        role = MockRole(name="TestRole", goal="Test Goal")
        assert role.name == "TestRole"
        assert role.goal == "Test Goal"
        assert role.memory is not None
        assert isinstance(role.actions, list)
    
    def test_role_add_action(self):
        """Test adding action to role."""
        role = MockRole()
        action = MockAction(name="TestAction")
        
        role.add_action(action)
        
        assert len(role.actions) == 1
        assert role.actions[0].name == "TestAction"
    
    def test_role_set_watch(self):
        """Test setting watched roles."""
        role = MockRole()
        watched = {"Role1", "Role2"}
        
        role.set_watch(watched)
        
        assert role.watch == watched


class TestMockTeam:
    """Test MockTeam functionality."""
    
    def test_team_creation(self):
        """Test team can be created."""
        team = MockTeam(name="TestTeam")
        assert team.name == "TestTeam"
        assert isinstance(team.roles, dict)
        assert len(team.roles) == 0
    
    def test_team_hire_role(self):
        """Test hiring roles."""
        team = MockTeam()
        role = MockRole(name="TestRole")
        
        team.hire(role)
        
        assert len(team.roles) == 1
        assert "TestRole" in team.roles
    
    def test_team_fire_role(self):
        """Test firing roles."""
        team = MockTeam()
        role = MockRole(name="TestRole")
        
        team.hire(role)
        assert len(team.roles) == 1
        
        team.fire("TestRole")
        assert len(team.roles) == 0
    
    def test_team_get_role(self):
        """Test getting role by name."""
        team = MockTeam()
        role = MockRole(name="TestRole")
        team.hire(role)
        
        retrieved = team.get_role("TestRole")
        
        assert retrieved is not None
        assert retrieved.name == "TestRole"
    
    @pytest.mark.asyncio
    async def test_team_run(self):
        """Test team run method."""
        team = MockTeam()
        role = MockRole(name="TestRole")
        team.hire(role)
        
        result = await team.run(max_iterations=2)
        
        assert team.is_running is False
        assert team.run_count == 1
        assert "TestTeam" in result


class TestFactories:
    """Test factory functions."""
    
    def test_create_fake_team(self):
        """Test fake team creation."""
        team = create_fake_team(num_roles=3)
        
        assert len(team.roles) == 3
        assert team is not None
    
    def test_create_fake_role(self):
        """Test fake role creation."""
        role = create_fake_role(name="Engineer", num_actions=2)
        
        assert role.name == "Engineer"
        assert len(role.actions) == 2
    
    def test_create_fake_action(self):
        """Test fake action creation."""
        action = create_fake_action(name="WriteCode", run_result="Code")
        
        assert action.name == "WriteCode"
        assert action is not None
    
    def test_create_fake_memory_store(self):
        """Test fake memory creation."""
        initial_data = {"key": "value"}
        memory = create_fake_memory_store(initial_data=initial_data)
        
        assert memory.get("key") == "value"
    
    def test_create_fake_memory_with_messages(self):
        """Test fake memory with messages."""
        messages = [MockMessage(role="user", content="Hello")]
        memory = create_fake_memory_store(initial_messages=messages)
        
        assert len(memory.get_messages()) == 1
    
    def test_create_fake_llm_response(self):
        """Test fake LLM response creation."""
        response = create_fake_llm_response(
            content="Generated code",
            completion_tokens=50
        )
        
        assert response.content == "Generated code"
        assert response.usage['completion_tokens'] == 50


class TestMockMemory:
    """Test MockMemory functionality."""
    
    def test_memory_creation(self):
        """Test memory can be created."""
        from tests.helpers.metagpt_stubs import MockMemory
        memory = MockMemory()
        
        assert isinstance(memory.storage, dict)
        assert isinstance(memory.messages, list)
    
    def test_memory_add_and_get(self):
        """Test memory add and get."""
        from tests.helpers.metagpt_stubs import MockMemory
        memory = MockMemory()
        
        memory.add("key", "value")
        assert memory.get("key") == "value"
    
    def test_memory_add_message(self):
        """Test adding messages to memory."""
        from tests.helpers.metagpt_stubs import MockMemory
        memory = MockMemory()
        msg = MockMessage(role="user", content="Test")
        
        memory.add_message(msg)
        
        assert len(memory.get_messages()) == 1
    
    def test_memory_clear(self):
        """Test memory clear."""
        from tests.helpers.metagpt_stubs import MockMemory
        memory = MockMemory()
        memory.add("key", "value")
        memory.add_message(MockMessage(role="user", content="Test"))
        
        memory.clear()
        
        assert len(memory.storage) == 0
        assert len(memory.messages) == 0


class TestStubImports:
    """Test that stubs can be imported from sys.modules."""
    
    def test_metagpt_stub_import(self):
        """Test MetaGPT stub is registered in sys.modules."""
        import sys
        
        assert 'metagpt' in sys.modules
        assert hasattr(sys.modules['metagpt'], 'Action')
        assert hasattr(sys.modules['metagpt'], 'Role')
        assert hasattr(sys.modules['metagpt'], 'Team')
    
    def test_metagpt_logs_stub_import(self):
        """Test MetaGPT logs stub is registered in sys.modules."""
        import sys
        
        assert 'metagpt.logs' in sys.modules
        assert hasattr(sys.modules['metagpt.logs'], 'logger')
