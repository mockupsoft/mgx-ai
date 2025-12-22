# -*- coding: utf-8 -*-
"""
Test Factories - Create Test Objects

Factory functions for creating commonly used test objects and fixtures.
These factories reduce boilerplate and make tests more readable.
"""

from typing import Any, Dict, List, Optional, Callable
from unittest.mock import AsyncMock, Mock
from .metagpt_stubs import (
    MockTeam,
    MockRole,
    MockAction,
    MockMemory,
    MockMessage,
    MockLLMResponse,
    MockContext,
)


# ============================================
# Team Factories
# ============================================

def create_fake_team(
    name: str = "TestTeam",
    num_roles: int = 4,
    role_names: Optional[List[str]] = None,
) -> MockTeam:
    """
    Create a fake team with mock roles.
    
    Args:
        name: Team name
        num_roles: Number of roles to create
        role_names: Custom role names (overrides num_roles)
    
    Returns:
        MockTeam instance with hired roles
    
    Example:
        >>> team = create_fake_team(num_roles=3)
        >>> assert len(team.roles) == 3
    """
    team = MockTeam(name=name)
    
    if role_names:
        names = role_names
    else:
        names = [f"Role_{i}" for i in range(num_roles)]
    
    for role_name in names:
        role = create_fake_role(name=role_name)
        team.hire(role)
    
    return team


# ============================================
# Role Factories
# ============================================

def create_fake_role(
    name: str = "TestRole",
    profile: str = "Test Profile",
    goal: str = "Test Goal",
    num_actions: int = 1,
) -> MockRole:
    """
    Create a fake role with mock actions.
    
    Args:
        name: Role name
        profile: Role profile description
        goal: Role goal
        num_actions: Number of actions to add
    
    Returns:
        MockRole instance with actions
    
    Example:
        >>> role = create_fake_role(name="Engineer", num_actions=2)
        >>> assert len(role.actions) == 2
    """
    role = MockRole(
        name=name,
        profile=profile,
        goal=goal,
    )
    
    for i in range(num_actions):
        action = create_fake_action(name=f"{name}_Action_{i}")
        role.add_action(action)
    
    return role


# ============================================
# Action Factories
# ============================================

def create_fake_action(
    name: str = "TestAction",
    profile: str = "Test Profile",
    run_result: str = "Success",
) -> MockAction:
    """
    Create a fake action.
    
    Args:
        name: Action name
        profile: Action profile
        run_result: Result to return from run()
    
    Returns:
        MockAction instance
    
    Example:
        >>> action = create_fake_action(name="WriteCode")
        >>> result = await action.run()
        >>> assert "WriteCode" in result
    """
    action = MockAction(name=name)
    action.profile = profile
    
    # Store original run for wrapping
    original_run = action.run
    
    async def mock_run(*args, **kwargs):
        await original_run(*args, **kwargs)
        return run_result
    
    action.run = mock_run
    return action


# ============================================
# Memory Store Factories
# ============================================

def create_fake_memory_store(
    initial_data: Optional[Dict[str, Any]] = None,
    initial_messages: Optional[List[MockMessage]] = None,
) -> MockMemory:
    """
    Create a fake memory store with optional initial data.
    
    Args:
        initial_data: Dictionary of initial key-value pairs
        initial_messages: List of initial messages
    
    Returns:
        MockMemory instance
    
    Example:
        >>> memory = create_fake_memory_store(
        ...     initial_data={"key": "value"},
        ...     initial_messages=[MockMessage("user", "Hello")]
        ... )
        >>> assert memory.get("key") == "value"
        >>> assert len(memory.get_messages()) == 1
    """
    memory = MockMemory()
    
    if initial_data:
        for key, value in initial_data.items():
            memory.add(key, value)
    
    if initial_messages:
        for msg in initial_messages:
            memory.add_message(msg)
    
    return memory


# ============================================
# LLM Response Factories
# ============================================

def create_fake_llm_response(
    content: str = "Mock LLM response",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    finish_reason: str = "stop",
) -> MockLLMResponse:
    """
    Create a fake LLM response.
    
    Args:
        content: Response content
        prompt_tokens: Prompt token count
        completion_tokens: Completion token count
        finish_reason: Finish reason (stop, max_tokens, etc.)
    
    Returns:
        MockLLMResponse instance
    
    Example:
        >>> response = create_fake_llm_response(
        ...     content="Generated code",
        ...     completion_tokens=50
        ... )
        >>> assert "Generated code" in response.content
        >>> assert response.usage['completion_tokens'] == 50
    """
    return MockLLMResponse(
        content=content,
        usage={
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
        },
        finish_reason=finish_reason,
    )


# ============================================
# Message Factories
# ============================================

def create_fake_message(
    role: str = "user",
    content: str = "Test message",
    name: Optional[str] = None,
) -> MockMessage:
    """
    Create a fake message.
    
    Args:
        role: Message role (user, assistant, system, etc.)
        content: Message content
        name: Optional sender name
    
    Returns:
        MockMessage instance
    
    Example:
        >>> msg = create_fake_message(role="assistant", content="Response")
        >>> assert msg.role == "assistant"
        >>> assert msg.content == "Response"
    """
    return MockMessage(
        role=role,
        content=content,
        name=name,
    )


# ============================================
# Async Mock Factories
# ============================================

def create_async_mock_llm(
    responses: Optional[List[str]] = None,
    raise_error: Optional[Exception] = None,
) -> AsyncMock:
    """
    Create an async mock LLM callable.
    
    Args:
        responses: List of responses to return sequentially
        raise_error: Exception to raise instead of returning
    
    Returns:
        AsyncMock instance
    
    Example:
        >>> mock_llm = create_async_mock_llm(
        ...     responses=["Response 1", "Response 2"]
        ... )
        >>> result = await mock_llm("prompt")
        >>> assert "Response 1" in result
    """
    mock = AsyncMock()
    
    if raise_error:
        mock.side_effect = raise_error
    elif responses:
        mock.side_effect = responses
    else:
        mock.return_value = "Mock LLM response"
    
    return mock


__all__ = [
    'create_fake_team',
    'create_fake_role',
    'create_fake_action',
    'create_fake_memory_store',
    'create_fake_llm_response',
    'create_fake_message',
    'create_async_mock_llm',
]
