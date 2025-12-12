# -*- coding: utf-8 -*-
"""
MGX Team Provider Service

Wraps MGXStyleTeam for FastAPI dependency injection without modifying
the public API of the original team class.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from mgx_agent import MGXStyleTeam, TeamConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class MGXTeamProvider:
    """
    Service provider for MGXStyleTeam instances.
    
    Manages team lifecycle and provides dependency injection for routers.
    Wraps MGXStyleTeam without modifying its public API.
    """
    
    def __init__(self, config: Optional[TeamConfig] = None):
        """
        Initialize the team provider.
        
        Args:
            config: TeamConfig instance. If None, uses DEFAULT_CONFIG.
        """
        self.config = config or DEFAULT_CONFIG
        self._team: Optional[MGXStyleTeam] = None
        self._lock = asyncio.Lock()
        logger.info(f"MGXTeamProvider initialized with config: {self.config}")
    
    async def get_team(self) -> MGXStyleTeam:
        """
        Get or create the team instance.
        
        Thread-safe lazy initialization with async lock.
        
        Returns:
            MGXStyleTeam instance
        """
        if self._team is None:
            async with self._lock:
                if self._team is None:
                    logger.info("Creating new MGXStyleTeam instance")
                    self._team = MGXStyleTeam(config=self.config)
        
        return self._team
    
    async def run_task(self, task: str, max_attempts: int = 3) -> Dict[str, Any]:
        """
        Run a task through the team.
        
        Args:
            task: Task description
            max_attempts: Maximum retry attempts
        
        Returns:
            Task execution result
        """
        team = await self.get_team()
        logger.info(f"Running task: {task[:50]}...")
        
        try:
            result = await team.run(task)
            logger.info(f"Task completed successfully")
            return {
                "status": "success",
                "result": result,
            }
        except Exception as e:
            logger.error(f"Task failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def shutdown(self):
        """Shutdown the team and cleanup resources."""
        if self._team is not None:
            logger.info("Shutting down MGXStyleTeam")
            # Add any cleanup logic if needed
            self._team = None
    
    @asynccontextmanager
    async def get_team_context(self):
        """
        Context manager for team operations.
        
        Usage:
            async with team_provider.get_team_context() as team:
                result = await team.run(task)
        """
        team = await self.get_team()
        try:
            yield team
        except Exception as e:
            logger.error(f"Team operation failed: {str(e)}")
            raise
    
    def __str__(self) -> str:
        """String representation."""
        return f"MGXTeamProvider(config={self.config})"


# Global provider instance (lazy-initialized)
_provider: Optional[MGXTeamProvider] = None


def get_team_provider() -> MGXTeamProvider:
    """
    Get the global team provider instance.
    
    Usage in FastAPI routers:
        from backend.services import get_team_provider
        
        @router.post("/tasks")
        async def create_task(task: str):
            provider = get_team_provider()
            result = await provider.run_task(task)
            return result
    """
    global _provider
    if _provider is None:
        _provider = MGXTeamProvider()
    return _provider


def set_team_provider(provider: MGXTeamProvider):
    """Set the global team provider instance (for testing)."""
    global _provider
    _provider = provider


__all__ = ['MGXTeamProvider', 'get_team_provider', 'set_team_provider']
