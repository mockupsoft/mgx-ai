# -*- coding: utf-8 -*-
"""Backend test configuration.

The upstream project test suite under ``backend/tests`` is intended to be runnable
without external services (Postgres, Docker daemon, hosted LLMs, GitHub).

This conftest provides:
- MetaGPT stubs (so importing ``mgx_agent`` does not require the real metagpt pkg)
- In-memory SQLite database fixtures for both async and sync SQLAlchemy
- A FastAPI TestClient with dependency overrides
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.db.models import Base
from backend.db.session import get_db, get_session


# ---------------------------------------------------------------------------
# MetaGPT stubs (shared with root tests)
# ---------------------------------------------------------------------------

from tests.helpers.metagpt_stubs import (  # noqa: E402
    MockAction,
    MockContext,
    MockMessage,
    MockMemory,
    MockRole,
    MockTeam,
    mock_logger,
)


class MetaGPTStub:
    Action = MockAction
    Role = MockRole
    Team = MockTeam


class MetaGPTActionsStub:
    Action = MockAction


class MetaGPTRolesStub:
    Role = MockRole


class MetaGPTTeamStub:
    Team = MockTeam


class MetaGPTLogsStub:
    logger = mock_logger


class MetaGPTTypesStub:
    Message = MockMessage


class MetaGPTSchemaStub:
    Message = MockMessage


class MetaGPTContextStub:
    Context = MockContext


class MetaGPTConfigStub:
    class Config:
        @staticmethod
        def from_home(filename: str):
            mock_config = MockContext()
            mock_config.model = f"mock-model-{filename}"
            return mock_config


sys.modules.setdefault("metagpt", MetaGPTStub())
sys.modules.setdefault("metagpt.actions", MetaGPTActionsStub())
sys.modules.setdefault("metagpt.roles", MetaGPTRolesStub())
sys.modules.setdefault("metagpt.team", MetaGPTTeamStub())
sys.modules.setdefault("metagpt.logs", MetaGPTLogsStub())
sys.modules.setdefault("metagpt.types", MetaGPTTypesStub())
sys.modules.setdefault("metagpt.schema", MetaGPTSchemaStub())
sys.modules.setdefault("metagpt.context", MetaGPTContextStub())
sys.modules.setdefault("metagpt.config", MetaGPTConfigStub())


@pytest.fixture(scope="session")
def sync_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="session")
def sync_session_factory(sync_engine) -> sessionmaker[Session]:
    return sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def sync_db(sync_session_factory) -> Generator[Session, None, None]:
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(scope="session")
def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(scope="session", autouse=True)
async def _create_async_schema(async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session")
def async_session_factory(async_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=async_engine, expire_on_commit=False, autoflush=True)


@pytest.fixture(scope="function")
async def db_session(async_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(scope="function")
async def test_db_session(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest.fixture(scope="function")
def app(sync_session_factory, async_session_factory):
    app = create_app()

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    # Disable lifespan side-effects (background workers, etc.) for unit/integration tests.
    app.router.lifespan_context = _no_lifespan

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_db() -> Generator[Session, None, None]:
        session = sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.fixture(scope="function")
def client(app):
    with TestClient(app) as client:
        yield client
