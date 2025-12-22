# -*- coding: utf-8 -*-
"""
Agent Memory Service

Manages persistent agent memory across workflow steps with LRU pruning and context threading.
"""

import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from backend.db.models import (
    AgentContext,
    AgentContextVersion,
    AgentInstance,
)
from backend.services.agents.context import SharedContextService

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """
    Service for managing agent memory persistence across workflow steps.
    
    Features:
    - Memory persistence across workflow steps
    - LRU (Least Recently Used) pruning
    - Context threading between agents
    - Memory snapshots and restoration
    - Memory size management
    """
    
    def __init__(
        self,
        context_service: SharedContextService,
        max_memory_size_mb: int = 100,
        max_memory_entries: int = 1000,
        memory_ttl_hours: int = 24,
    ):
        """
        Initialize the agent memory service.
        
        Args:
            context_service: Shared context service
            max_memory_size_mb: Maximum memory size per agent in MB
            max_memory_entries: Maximum number of memory entries per agent
            memory_ttl_hours: Memory TTL in hours
        """
        self.context_service = context_service
        self.max_memory_size_mb = max_memory_size_mb
        self.max_memory_entries = max_memory_entries
        self.memory_ttl_hours = memory_ttl_hours
        
        # In-memory LRU cache for hot memory access
        self.memory_cache: Dict[str, OrderedDict] = {}
        
        logger.info("AgentMemoryService initialized")
    
    async def store_memory(
        self,
        session: AsyncSession,
        agent_instance_id: str,
        workspace_id: str,
        project_id: str,
        memory_key: str,
        memory_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a memory entry for an agent.
        
        Args:
            session: Database session
            agent_instance_id: Agent instance ID
            workspace_id: Workspace ID
            project_id: Project ID
            memory_key: Memory key (e.g., "workflow_context", "task_history")
            memory_data: Memory data to store
            metadata: Optional metadata
            
        Returns:
            Context ID
        """
        # Get or create context for this memory key
        context = await self.context_service.get_or_create_context(
            session,
            instance_id=agent_instance_id,
            context_name=f"memory:{memory_key}",
            workspace_id=workspace_id,
            project_id=project_id,
        )
        
        # Prepare memory entry
        timestamp = datetime.utcnow()
        memory_entry = {
            "data": memory_data,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {},
        }
        
        # Read current memory
        current_memory = await self.context_service.read_context(session, context.id)
        if current_memory is None:
            current_memory = {"entries": [], "total_size_bytes": 0}
        
        # Add new entry
        entries = current_memory.get("entries", [])
        entries.append(memory_entry)
        
        # Apply LRU pruning if needed
        entries = await self._apply_lru_pruning(entries)
        
        # Calculate total size
        import sys
        total_size = sys.getsizeof(str(entries))
        
        # Update memory context
        updated_memory = {
            "entries": entries,
            "total_size_bytes": total_size,
            "last_updated": timestamp.isoformat(),
        }
        
        await self.context_service.write_context(
            session,
            context_id=context.id,
            data=updated_memory,
            change_description=f"Stored memory: {memory_key}",
            created_by=agent_instance_id,
        )
        
        # Update in-memory cache
        cache_key = f"{agent_instance_id}:{memory_key}"
        if cache_key not in self.memory_cache:
            self.memory_cache[cache_key] = OrderedDict()
        
        self.memory_cache[cache_key][timestamp.isoformat()] = memory_entry
        self.memory_cache[cache_key].move_to_end(timestamp.isoformat())
        
        logger.info(f"Stored memory for agent {agent_instance_id}, key: {memory_key}")
        return context.id
    
    async def retrieve_memory(
        self,
        session: AsyncSession,
        agent_instance_id: str,
        workspace_id: str,
        memory_key: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memory entries for an agent.
        
        Args:
            session: Database session
            agent_instance_id: Agent instance ID
            workspace_id: Workspace ID
            memory_key: Memory key
            limit: Maximum number of entries to return
            
        Returns:
            List of memory entries
        """
        # Check in-memory cache first
        cache_key = f"{agent_instance_id}:{memory_key}"
        if cache_key in self.memory_cache:
            cached_entries = list(self.memory_cache[cache_key].values())
            if limit:
                cached_entries = cached_entries[-limit:]
            return cached_entries
        
        # Query context
        result = await session.execute(
            select(AgentContext).where(
                and_(
                    AgentContext.instance_id == agent_instance_id,
                    AgentContext.name == f"memory:{memory_key}",
                    AgentContext.workspace_id == workspace_id,
                )
            )
        )
        context = result.scalar_one_or_none()
        
        if not context:
            return []
        
        # Read memory
        memory_data = await self.context_service.read_context(session, context.id)
        
        if not memory_data:
            return []
        
        entries = memory_data.get("entries", [])
        
        if limit:
            entries = entries[-limit:]
        
        # Update cache
        if cache_key not in self.memory_cache:
            self.memory_cache[cache_key] = OrderedDict()
        
        for entry in entries:
            timestamp = entry.get("timestamp", datetime.utcnow().isoformat())
            self.memory_cache[cache_key][timestamp] = entry
        
        return entries
    
    async def thread_context_between_steps(
        self,
        session: AsyncSession,
        from_agent_id: str,
        to_agent_id: str,
        workspace_id: str,
        project_id: str,
        context_keys: List[str],
    ) -> Dict[str, Any]:
        """
        Thread context from one agent to another.
        
        Args:
            session: Database session
            from_agent_id: Source agent instance ID
            to_agent_id: Target agent instance ID
            workspace_id: Workspace ID
            project_id: Project ID
            context_keys: List of context keys to thread
            
        Returns:
            Threaded context data
        """
        threaded_context = {}
        
        for key in context_keys:
            # Retrieve from source agent
            entries = await self.retrieve_memory(
                session,
                agent_instance_id=from_agent_id,
                workspace_id=workspace_id,
                memory_key=key,
            )
            
            if entries:
                # Store to target agent
                latest_entry = entries[-1]
                await self.store_memory(
                    session,
                    agent_instance_id=to_agent_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    memory_key=key,
                    memory_data=latest_entry.get("data"),
                    metadata={
                        "threaded_from": from_agent_id,
                        "threaded_at": datetime.utcnow().isoformat(),
                    },
                )
                
                threaded_context[key] = latest_entry.get("data")
        
        logger.info(
            f"Threaded context from agent {from_agent_id} to {to_agent_id}, "
            f"keys: {context_keys}"
        )
        return threaded_context
    
    async def clear_memory(
        self,
        session: AsyncSession,
        agent_instance_id: str,
        workspace_id: str,
        memory_key: Optional[str] = None,
    ):
        """
        Clear memory for an agent.
        
        Args:
            session: Database session
            agent_instance_id: Agent instance ID
            workspace_id: Workspace ID
            memory_key: Optional memory key to clear (None = clear all)
        """
        if memory_key:
            # Clear specific key
            context_name = f"memory:{memory_key}"
            result = await session.execute(
                select(AgentContext).where(
                    and_(
                        AgentContext.instance_id == agent_instance_id,
                        AgentContext.name == context_name,
                        AgentContext.workspace_id == workspace_id,
                    )
                )
            )
            context = result.scalar_one_or_none()
            
            if context:
                await self.context_service.write_context(
                    session,
                    context_id=context.id,
                    data={"entries": [], "total_size_bytes": 0},
                    change_description=f"Cleared memory: {memory_key}",
                    created_by=agent_instance_id,
                )
            
            # Clear cache
            cache_key = f"{agent_instance_id}:{memory_key}"
            self.memory_cache.pop(cache_key, None)
        else:
            # Clear all memory for agent
            result = await session.execute(
                select(AgentContext).where(
                    and_(
                        AgentContext.instance_id == agent_instance_id,
                        AgentContext.workspace_id == workspace_id,
                        AgentContext.name.like("memory:%"),
                    )
                )
            )
            contexts = result.scalars().all()
            
            for context in contexts:
                await self.context_service.write_context(
                    session,
                    context_id=context.id,
                    data={"entries": [], "total_size_bytes": 0},
                    change_description="Cleared all memory",
                    created_by=agent_instance_id,
                )
            
            # Clear cache
            cache_keys_to_remove = [
                key for key in self.memory_cache.keys()
                if key.startswith(f"{agent_instance_id}:")
            ]
            for key in cache_keys_to_remove:
                self.memory_cache.pop(key, None)
        
        logger.info(f"Cleared memory for agent {agent_instance_id}, key: {memory_key or 'all'}")
    
    async def get_memory_stats(
        self,
        session: AsyncSession,
        agent_instance_id: str,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """
        Get memory statistics for an agent.
        
        Args:
            session: Database session
            agent_instance_id: Agent instance ID
            workspace_id: Workspace ID
            
        Returns:
            Memory statistics
        """
        result = await session.execute(
            select(AgentContext).where(
                and_(
                    AgentContext.instance_id == agent_instance_id,
                    AgentContext.workspace_id == workspace_id,
                    AgentContext.name.like("memory:%"),
                )
            )
        )
        contexts = result.scalars().all()
        
        total_size = 0
        total_entries = 0
        memory_keys = []
        
        for context in contexts:
            memory_data = await self.context_service.read_context(session, context.id)
            if memory_data:
                total_size += memory_data.get("total_size_bytes", 0)
                total_entries += len(memory_data.get("entries", []))
                memory_keys.append(context.name.replace("memory:", ""))
        
        return {
            "agent_instance_id": agent_instance_id,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "total_entries": total_entries,
            "memory_keys": memory_keys,
            "memory_key_count": len(memory_keys),
        }
    
    async def _apply_lru_pruning(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply LRU pruning to memory entries.
        
        Args:
            entries: Memory entries
            
        Returns:
            Pruned entries
        """
        # Sort by timestamp (oldest first)
        sorted_entries = sorted(
            entries,
            key=lambda e: e.get("timestamp", ""),
        )
        
        # Keep only the most recent entries
        if len(sorted_entries) > self.max_memory_entries:
            pruned_entries = sorted_entries[-self.max_memory_entries:]
            logger.info(f"Pruned {len(sorted_entries) - len(pruned_entries)} old memory entries")
            return pruned_entries
        
        # Prune by age
        cutoff_time = datetime.utcnow() - timedelta(hours=self.memory_ttl_hours)
        recent_entries = [
            entry for entry in sorted_entries
            if datetime.fromisoformat(entry.get("timestamp", "")) > cutoff_time
        ]
        
        if len(recent_entries) < len(sorted_entries):
            logger.info(f"Pruned {len(sorted_entries) - len(recent_entries)} expired memory entries")
        
        return recent_entries


__all__ = ["AgentMemoryService"]
