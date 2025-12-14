# -*- coding: utf-8 -*-
"""
Agent Core Base Classes

Defines BaseAgent abstract class for implementing custom agents with
lifecycle hooks and declared capabilities.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for implementing agents.

    Defines the lifecycle (initialize, activate, deactivate, shutdown)
    and requires subclasses to declare their capabilities and configurable metadata.
    """

    def __init__(
        self,
        name: str,
        agent_type: str,
        capabilities: List[str],
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the agent.

        Args:
            name: Agent name
            agent_type: Agent type/class identifier
            capabilities: List of capabilities this agent provides
            config: Configuration dictionary
            metadata: Additional metadata
        """
        self.name = name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.config = config or {}
        self.metadata = metadata or {}
        self._initialized = False
        self._active = False
        logger.info(f"Created agent: {name} (type={agent_type})")

    async def initialize(self) -> None:
        """
        Initialize the agent (setup resources, connections, etc).

        This is called once when the agent is first instantiated in a workspace/project.
        Subclasses should override to perform initialization tasks.
        """
        self._initialized = True
        logger.info(f"Agent {self.name} initialized")

    async def activate(self) -> None:
        """
        Activate the agent (start processing, connect to services, etc).

        Called when the agent should become active and start handling requests.
        Subclasses should override to perform activation tasks.
        """
        if not self._initialized:
            await self.initialize()
        self._active = True
        logger.info(f"Agent {self.name} activated")

    async def deactivate(self) -> None:
        """
        Deactivate the agent (stop processing, pause operations, etc).

        Called when the agent should pause or stop handling requests.
        Subclasses should override to perform deactivation tasks.
        """
        self._active = False
        logger.info(f"Agent {self.name} deactivated")

    async def shutdown(self) -> None:
        """
        Shutdown the agent (cleanup resources, close connections, etc).

        Called when the agent is being permanently shut down.
        Subclasses should override to perform cleanup tasks.
        """
        if self._active:
            await self.deactivate()
        self._initialized = False
        logger.info(f"Agent {self.name} shutdown")

    @property
    def is_initialized(self) -> bool:
        """Check if the agent has been initialized."""
        return self._initialized

    @property
    def is_active(self) -> bool:
        """Check if the agent is currently active."""
        return self._active

    def get_capabilities(self) -> List[str]:
        """Get the list of declared capabilities."""
        return self.capabilities

    def get_config(self) -> Dict[str, Any]:
        """Get the agent configuration."""
        return self.config

    def set_config(self, config: Dict[str, Any]) -> None:
        """Update the agent configuration."""
        self.config.update(config)
        logger.info(f"Agent {self.name} configuration updated")

    def get_metadata(self) -> Dict[str, Any]:
        """Get the agent metadata."""
        return self.metadata

    def set_metadata(self, metadata: Dict[str, Any]) -> None:
        """Update the agent metadata."""
        self.metadata.update(metadata)
        logger.info(f"Agent {self.name} metadata updated")

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation."""
        return {
            "name": self.name,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "config": self.config,
            "metadata": self.metadata,
            "initialized": self._initialized,
            "active": self._active,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', type='{self.agent_type}')>"


__all__ = ["BaseAgent"]
