# -*- coding: utf-8 -*-
"""
Shared Context Service

Manages persistent agent context with versioning and rollback support.
Enforces workspace/project isolation.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.db.models import AgentContext, AgentContextVersion, ContextRollbackState

logger = logging.getLogger(__name__)


class SharedContextService:
    """
    Service for managing shared agent context with versioning.

    Provides:
    - Reading and writing context
    - Version tracking and incrementing
    - Rollback capability
    - Workspace/project boundary enforcement
    """

    async def get_or_create_context(
        self,
        session: AsyncSession,
        instance_id: str,
        context_name: str,
        workspace_id: str,
        project_id: str,
    ) -> AgentContext:
        """
        Get or create a named context for an agent instance.

        Args:
            session: AsyncSession for database access
            instance_id: Agent instance ID
            context_name: Name/identifier of the context
            workspace_id: Workspace ID (for isolation)
            project_id: Project ID (for isolation)

        Returns:
            AgentContext instance
        """
        result = await session.execute(
            select(AgentContext).where(
                and_(
                    AgentContext.instance_id == instance_id,
                    AgentContext.name == context_name,
                )
            )
        )
        context = result.scalar_one_or_none()

        if context is not None:
            return context

        # Create new context
        context = AgentContext(
            instance_id=instance_id,
            name=context_name,
            workspace_id=workspace_id,
            project_id=project_id,
            current_version=0,
        )
        session.add(context)
        await session.flush()
        logger.info(f"Created new context: {context_name} for instance {instance_id}")
        return context

    async def read_context(
        self,
        session: AsyncSession,
        context_id: str,
        version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Read context data from a specific version.

        Args:
            session: AsyncSession for database access
            context_id: Context ID
            version: Specific version to read (None for current)

        Returns:
            Context data dictionary or None if not found
        """
        result = await session.execute(
            select(AgentContext).where(AgentContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if context is None:
            return None

        # Determine which version to read
        read_version = version if version is not None else context.current_version

        # Fetch the version
        result = await session.execute(
            select(AgentContextVersion).where(
                and_(
                    AgentContextVersion.context_id == context_id,
                    AgentContextVersion.version == read_version,
                )
            )
        )
        version_record = result.scalar_one_or_none()

        if version_record is None:
            logger.warning(f"Context version not found: {context_id} v{read_version}")
            return None

        logger.info(f"Read context {context_id} version {read_version}")
        return version_record.data

    async def write_context(
        self,
        session: AsyncSession,
        context_id: str,
        data: Dict[str, Any],
        change_description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> int:
        """
        Write updated context data, creating a new version.

        Args:
            session: AsyncSession for database access
            context_id: Context ID
            data: New context data
            change_description: Description of changes
            created_by: User/agent who made the changes

        Returns:
            New version number
        """
        result = await session.execute(
            select(AgentContext).where(AgentContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if context is None:
            raise ValueError(f"Context not found: {context_id}")

        # Increment version
        new_version = context.current_version + 1

        # Create version record
        version_record = AgentContextVersion(
            context_id=context_id,
            version=new_version,
            data=data,
            change_description=change_description,
            created_by=created_by,
        )
        session.add(version_record)

        # Update context current version
        context.current_version = new_version
        context.rollback_pointer = None
        context.rollback_state = None

        await session.flush()
        logger.info(f"Wrote context {context_id} version {new_version}")
        return new_version

    async def list_versions(
        self,
        session: AsyncSession,
        context_id: str,
    ) -> list[Dict[str, Any]]:
        """
        List all versions of a context.

        Args:
            session: AsyncSession for database access
            context_id: Context ID

        Returns:
            List of version metadata dictionaries
        """
        result = await session.execute(
            select(AgentContextVersion)
            .where(AgentContextVersion.context_id == context_id)
            .order_by(AgentContextVersion.version)
        )
        versions = result.scalars().all()

        return [
            {
                "version": v.version,
                "created_at": v.created_at.isoformat(),
                "change_description": v.change_description,
                "created_by": v.created_by,
            }
            for v in versions
        ]

    async def rollback_to_version(
        self,
        session: AsyncSession,
        context_id: str,
        target_version: int,
    ) -> bool:
        """
        Rollback context to a previous version.

        Args:
            session: AsyncSession for database access
            context_id: Context ID
            target_version: Version to rollback to

        Returns:
            True if rollback succeeded, False otherwise
        """
        result = await session.execute(
            select(AgentContext).where(AgentContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if context is None:
            return False

        # Check if target version exists
        result = await session.execute(
            select(AgentContextVersion).where(
                and_(
                    AgentContextVersion.context_id == context_id,
                    AgentContextVersion.version == target_version,
                )
            )
        )
        target_version_record = result.scalar_one_or_none()

        if target_version_record is None:
            logger.warning(f"Target version not found: {context_id} v{target_version}")
            return False

        try:
            # Update current version to target
            context.current_version = target_version
            context.rollback_pointer = target_version
            context.rollback_state = ContextRollbackState.SUCCESS

            await session.flush()
            logger.info(f"Rollback successful: {context_id} to v{target_version}")
            return True

        except Exception as e:
            context.rollback_state = ContextRollbackState.FAILED
            logger.error(f"Rollback failed for {context_id}: {str(e)}")
            return False

    async def check_workspace_isolation(
        self,
        session: AsyncSession,
        context_id: str,
        workspace_id: str,
    ) -> bool:
        """
        Verify that a context belongs to a specific workspace.

        Args:
            session: AsyncSession for database access
            context_id: Context ID
            workspace_id: Expected workspace ID

        Returns:
            True if context belongs to workspace, False otherwise
        """
        result = await session.execute(
            select(AgentContext).where(AgentContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if context is None:
            return False

        return context.workspace_id == workspace_id


__all__ = ["SharedContextService"]
