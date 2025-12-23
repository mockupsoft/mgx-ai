# -*- coding: utf-8 -*-
"""
Database Fixtures

Provides fixtures for database testing including:
- Test database setup/teardown
- Test data factories
- Transaction management
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from backend.db.models import Base
from backend.db.models.entities import Workspace, Project, Task, TaskRun, AgentDefinition, AgentInstance
from backend.db.models.enums import TaskStatus, RunStatus, AgentStatus


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_workspace(test_db_session):
    """Create a test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        slug="test-workspace",
    )
    test_db_session.add(workspace)
    await test_db_session.commit()
    await test_db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def test_project(test_db_session, test_workspace):
    """Create a test project."""
    project = Project(
        name="Test Project",
        slug="test-project",
        workspace_id=test_workspace.id,
    )
    test_db_session.add(project)
    await test_db_session.commit()
    await test_db_session.refresh(project)
    return project


@pytest.fixture
async def test_task(test_db_session, test_workspace, test_project):
    """Create a test task."""
    task = Task(
        title="Test Task",
        description="Test task description",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        status=TaskStatus.PENDING,
    )
    test_db_session.add(task)
    await test_db_session.commit()
    await test_db_session.refresh(task)
    return task


@pytest.fixture
async def test_agent_definition(test_db_session, test_workspace):
    """Create a test agent definition."""
    definition = AgentDefinition(
        name="Test Agent",
        slug="test-agent",
        workspace_id=test_workspace.id,
        capabilities=["code_generation", "testing"],
        status=AgentStatus.ACTIVE,
    )
    test_db_session.add(definition)
    await test_db_session.commit()
    await test_db_session.refresh(definition)
    return definition


@pytest.fixture
async def test_agent_instance(test_db_session, test_workspace, test_agent_definition):
    """Create a test agent instance."""
    instance = AgentInstance(
        name="Test Agent Instance",
        definition_id=test_agent_definition.id,
        workspace_id=test_workspace.id,
        status=AgentStatus.ACTIVE,
    )
    test_db_session.add(instance)
    await test_db_session.commit()
    await test_db_session.refresh(instance)
    return instance

