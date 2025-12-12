# -*- coding: utf-8 -*-
"""
Database session management for async SQLAlchemy operations.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from .engine import get_engine


class SessionManager:
    """Manager for database sessions with lifecycle support."""
    
    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        self.session_factory = session_factory
        
    async def create_session(self) -> AsyncSession:
        """Create a new async session."""
        if self.session_factory is None:
            from .engine import get_session_factory
            self.session_factory = await get_session_factory()
        return self.session_factory()
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for automatic session lifecycle."""
        session = await self.create_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def close(self):
        """Close the session manager and cleanup resources."""
        if self.session_factory:
            # The actual cleanup is handled by the engine
            pass


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection function for FastAPI routes."""
    async with get_session_manager().session() as session:
        yield session