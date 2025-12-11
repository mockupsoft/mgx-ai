# -*- coding: utf-8 -*-
"""
MetaGPT Stubs for Testing

Lightweight stub implementations of MetaGPT components to allow tests to run
without the real MetaGPT package or network calls.
"""

import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from unittest.mock import Mock, AsyncMock


# ============================================
# Logger Stub
# ============================================

class MockLogger:
    """Mock logger that mimics MetaGPT logger interface."""
    
    def __init__(self):
        self._logger = logging.getLogger('tests.metagpt')
        self.messages = []
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self._logger.debug(msg, *args, **kwargs)
        self.messages.append(('DEBUG', msg))
    
    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self._logger.info(msg, *args, **kwargs)
        self.messages.append(('INFO', msg))
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self._logger.warning(msg, *args, **kwargs)
        self.messages.append(('WARNING', msg))
    
    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        self._logger.error(msg, *args, **kwargs)
        self.messages.append(('ERROR', msg))
    
    def clear(self):
        """Clear recorded messages."""
        self.messages = []


mock_logger = MockLogger()


# ============================================
# Message Stub
# ============================================

class MessageRole(str, Enum):
    """Message role enumeration."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


@dataclass
class MockMessage:
    """Mock Message class mimicking MetaGPT Message."""
    
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def __str__(self):
        return f"MockMessage(role={self.role}, content_len={len(self.content)})"
    
    def __repr__(self):
        return (f"MockMessage(role={self.role!r}, "
                f"content={self.content[:50]!r}..., "
                f"name={self.name!r})")


# ============================================
# Action Stub
# ============================================

class MockAction:
    """Mock Action class mimicking MetaGPT Action."""
    
    def __init__(self, name: str = "MockAction"):
        self.name = name
        self.profile = f"{name} Profile"
        self.desc = f"Description for {name}"
        self.called = False
        self.call_count = 0
        self.last_input = None
    
    async def run(self, *args, **kwargs) -> str:
        """Execute action with mock behavior."""
        self.called = True
        self.call_count += 1
        self.last_input = (args, kwargs)
        return f"{self.name} executed with args={args}, kwargs={kwargs}"
    
    def reset(self):
        """Reset call tracking."""
        self.called = False
        self.call_count = 0
        self.last_input = None


# ============================================
# Role Stub
# ============================================

@dataclass
class MockRole:
    """Mock Role class mimicking MetaGPT Role."""
    
    name: str = "MockRole"
    profile: str = "Mock role for testing"
    goal: str = "Complete test tasks"
    constraints: str = "Follow test constraints"
    
    def __post_init__(self):
        self.memory = MockMemory()
        self.actions: List[MockAction] = []
        self.watch: Set[str] = set()
        self.rc = MockContext()
        self._messages: List[MockMessage] = []
    
    async def _act(self) -> MockMessage:
        """Mock act method."""
        msg = MockMessage(
            role="assistant",
            content=f"{self.name} completed action",
            name=self.name
        )
        return msg
    
    async def _think(self):
        """Mock think method."""
        pass
    
    def add_action(self, action: MockAction):
        """Add action to role."""
        self.actions.append(action)
    
    def set_watch(self, watched: Set[str]):
        """Set watched roles."""
        self.watch = watched


# ============================================
# Context Stub
# ============================================

@dataclass
class MockContext:
    """Mock runtime context."""
    
    max_iterations: int = 10
    current_iteration: int = 0
    stopped: bool = False
    messages: List[MockMessage] = field(default_factory=list)
    
    def add_message(self, message: MockMessage):
        """Add message to context."""
        self.messages.append(message)


# ============================================
# Memory Stub
# ============================================

@dataclass
class MockMemory:
    """Mock memory store."""
    
    storage: Dict[str, Any] = field(default_factory=dict)
    messages: List[MockMessage] = field(default_factory=list)
    
    def add(self, key: str, value: Any):
        """Add item to memory."""
        self.storage[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get item from memory."""
        return self.storage.get(key, default)
    
    def add_message(self, message: MockMessage):
        """Add message to memory."""
        self.messages.append(message)
    
    def get_messages(self) -> List[MockMessage]:
        """Get all messages."""
        return self.messages.copy()
    
    def clear(self):
        """Clear memory."""
        self.storage.clear()
        self.messages.clear()


# ============================================
# Team Stub
# ============================================

class MockTeam:
    """Mock Team class mimicking MetaGPT Team."""
    
    def __init__(self, name: str = "MockTeam"):
        self.name = name
        self.roles: Dict[str, MockRole] = {}
        self.rc = MockContext()
        self.memory = MockMemory()
        self.is_running = False
        self.run_count = 0
    
    def hire(self, role: MockRole):
        """Hire a role to the team."""
        self.roles[role.name] = role
        role.rc = self.rc
        role.memory = self.memory
    
    def fire(self, role_name: str):
        """Remove a role from the team."""
        if role_name in self.roles:
            del self.roles[role_name]
    
    async def run(self, max_iterations: int = 5) -> str:
        """Run team with mock behavior."""
        self.is_running = True
        self.run_count += 1
        self.rc.max_iterations = max_iterations
        
        for iteration in range(max_iterations):
            self.rc.current_iteration = iteration
            
            for role in self.roles.values():
                msg = await role._act()
                self.memory.add_message(msg)
        
        self.is_running = False
        return f"{self.name} completed with {self.run_count} runs"
    
    def get_role(self, role_name: str) -> Optional[MockRole]:
        """Get role by name."""
        return self.roles.get(role_name)


# ============================================
# LLM Response Stub
# ============================================

@dataclass
class MockLLMResponse:
    """Mock LLM response."""
    
    content: str
    usage: Dict[str, int] = field(default_factory=lambda: {
        'prompt_tokens': 10,
        'completion_tokens': 20,
        'total_tokens': 30
    })
    finish_reason: str = "stop"
    
    def __str__(self):
        return self.content


# ============================================
# Configuration Stub
# ============================================

@dataclass
class MockConfig:
    """Mock configuration."""
    
    api_key: str = "mock-key"
    model: str = "mock-model"
    temperature: float = 0.7
    max_tokens: int = 2000
    
    def __getitem__(self, key: str) -> Any:
        """Dict-like access."""
        return getattr(self, key, None)


__all__ = [
    'mock_logger',
    'MockMessage',
    'MockAction',
    'MockRole',
    'MockTeam',
    'MockMemory',
    'MockContext',
    'MockLLMResponse',
    'MockConfig',
    'MessageRole',
]
