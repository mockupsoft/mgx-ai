# -*- coding: utf-8 -*-
"""
Agent Services Package

Core services for multi-agent system:
- BaseAgent: Abstract base class for agents
- AgentRegistry: Registry for agent definitions and instances
- SharedContextService: Persistent context with versioning
"""

from .base import BaseAgent
from .registry import AgentRegistry
from .context import SharedContextService
from .messages import AgentMessageBus, get_agent_message_bus
from .memory import AgentMemoryService

__all__ = [
    "BaseAgent",
    "AgentRegistry",
    "SharedContextService",
    "AgentMemoryService",
    "AgentMessageBus",
    "get_agent_message_bus",
]
