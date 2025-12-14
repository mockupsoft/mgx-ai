# -*- coding: utf-8 -*-
"""
Agent Registry Service

Manages agent definitions and instances, including:
- Registering concrete agent classes
- Loading definitions from database
- Spawning agent instances
- Tracking status transitions
"""

import logging
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import AgentDefinition, AgentInstance, AgentStatus
from .base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for managing agent definitions and instances.

    Handles:
    - Registration of agent class definitions
    - Loading agent definitions from database
    - Spawning agent instances
    - Status tracking and transitions
    - Lookup and discovery helpers
    """

    def __init__(self):
        """Initialize the agent registry."""
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._instances: Dict[str, BaseAgent] = {}
        logger.info("AgentRegistry initialized")

    def register(
        self,
        agent_class: Type[BaseAgent],
        slug: str,
        description: Optional[str] = None,
    ) -> None:
        """
        Register an agent class.

        Args:
            agent_class: Agent class (subclass of BaseAgent)
            slug: Unique slug identifier for the agent
            description: Agent description
        """
        if not issubclass(agent_class, BaseAgent):
            raise ValueError(f"{agent_class} must be a subclass of BaseAgent")

        self._agent_classes[slug] = agent_class
        logger.info(f"Registered agent class: {slug} -> {agent_class.__name__}")

    def unregister(self, slug: str) -> None:
        """Unregister an agent class."""
        if slug in self._agent_classes:
            del self._agent_classes[slug]
            logger.info(f"Unregistered agent class: {slug}")

    def get_agent_class(self, slug: str) -> Optional[Type[BaseAgent]]:
        """
        Get a registered agent class by slug.

        Args:
            slug: Agent slug

        Returns:
            Agent class or None if not registered
        """
        return self._agent_classes.get(slug)

    def list_registered(self) -> Dict[str, Type[BaseAgent]]:
        """List all registered agent classes."""
        return self._agent_classes.copy()

    async def spawn_instance(
        self,
        definition: AgentDefinition,
        instance: AgentInstance,
    ) -> Optional[BaseAgent]:
        """
        Spawn an agent instance from a definition and database instance record.

        Args:
            definition: AgentDefinition from database
            instance: AgentInstance from database

        Returns:
            Spawned agent instance or None if class not found
        """
        agent_class = self.get_agent_class(definition.slug)
        if agent_class is None:
            logger.warning(f"Agent class not registered for definition: {definition.slug}")
            return None

        # Create agent instance
        agent = agent_class(
            name=instance.name,
            agent_type=definition.agent_type,
            capabilities=definition.capabilities or [],
            config=instance.config,
        )

        # Store in registry
        self._instances[instance.id] = agent
        logger.info(f"Spawned agent instance: {instance.id} ({instance.name})")

        return agent

    def get_instance(self, instance_id: str) -> Optional[BaseAgent]:
        """
        Get a spawned agent instance by ID.

        Args:
            instance_id: Instance ID

        Returns:
            Agent instance or None if not found
        """
        return self._instances.get(instance_id)

    def list_instances(self) -> Dict[str, BaseAgent]:
        """List all spawned agent instances."""
        return self._instances.copy()

    async def load_definitions(self, session: AsyncSession) -> Dict[str, AgentDefinition]:
        """
        Load all agent definitions from the database.

        Args:
            session: AsyncSession for database access

        Returns:
            Dictionary of definitions by slug
        """
        result = await session.execute(
            select(AgentDefinition).where(AgentDefinition.is_enabled == True)
        )
        definitions = result.scalars().all()
        logger.info(f"Loaded {len(definitions)} agent definitions from database")
        return {d.slug: d for d in definitions}

    async def load_instances(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, AgentInstance]:
        """
        Load agent instances for a workspace/project.

        Args:
            session: AsyncSession for database access
            workspace_id: Workspace ID
            project_id: Project ID (optional)

        Returns:
            Dictionary of instances by ID
        """
        query = select(AgentInstance).where(AgentInstance.workspace_id == workspace_id)
        if project_id:
            query = query.where(AgentInstance.project_id == project_id)

        result = await session.execute(query)
        instances = result.scalars().all()
        logger.info(f"Loaded {len(instances)} agent instances for workspace={workspace_id}")
        return {i.id: i for i in instances}

    async def update_instance_status(
        self,
        session: AsyncSession,
        instance_id: str,
        status: AgentStatus,
        error: Optional[str] = None,
    ) -> bool:
        """
        Update the status of an agent instance in the database.

        Args:
            session: AsyncSession for database access
            instance_id: Instance ID
            status: New status
            error: Optional error message

        Returns:
            True if updated, False if not found
        """
        result = await session.execute(
            select(AgentInstance).where(AgentInstance.id == instance_id)
        )
        instance = result.scalar_one_or_none()

        if instance is None:
            return False

        instance.status = status
        if error:
            instance.last_error = error

        await session.flush()
        logger.info(f"Updated instance {instance_id} status to {status}")
        return True

    def __repr__(self) -> str:
        return f"<AgentRegistry(registered={len(self._agent_classes)}, instances={len(self._instances)})>"


__all__ = ["AgentRegistry"]
