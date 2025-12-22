# -*- coding: utf-8 -*-
"""
Database engine configuration for async SQLAlchemy operations.
"""

import asyncio
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from ..config import settings


# Global engine and session maker instances
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_database_url() -> str:
    """Get async database URL from settings."""
    return settings.async_database_url


async def create_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    database_url = get_database_url()
    
    # Configure engine for async PostgreSQL
    engine = create_async_engine(
        database_url,
        # Connection pool settings
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Connection arguments for PostgreSQL async driver
        connect_args={
            "server_settings": {
                "jit": "off",  # Disable JIT for better performance
                "application_name": "mgx_agent_api"
            }
        },
        # Echo SQL queries in debug mode
        echo=settings.debug,
        # Pool pre-ping for connection validation
        pool_pre_ping=True,
        # Pool recycle time (2 hours)
        pool_recycle=7200,
    )
    
    return engine


def get_engine() -> AsyncEngine:
    """Get or create the global async engine."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the global session factory."""
    global _session_factory, _engine
    
    if _session_factory is None:
        if _engine is None:
            _engine = await create_engine()
        
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=True,
        )
    
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection function for FastAPI routes."""
    session_factory = await get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_test_engine() -> AsyncEngine:
    """Create test engine with SQLite in-memory database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.debug,
    )
    return engine


async def create_test_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create test session factory for in-memory SQLite."""
    engine = await create_test_engine()
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=True,
    )
    return session_factory


async def close_engine():
    """Close the global engine and cleanup resources."""
    global _engine, _session_factory
    
    if _session_factory is not None:
        # Dispose the session factory
        _session_factory = None
    
    if _engine is not None:
        # Dispose the engine and close all connections
        await _engine.dispose()
        _engine = None