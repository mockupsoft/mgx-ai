# -*- coding: utf-8 -*-
"""
Backend-DB Integration Tests

Tests cover:
- Alembic migration tests
- Model CRUD operations
- Transaction rollback tests
- Connection pooling tests
- Async query tests
- Database constraint tests
"""

import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.db.models import Base
from backend.db.models.entities import (
    Workspace,
    Project,
    Task,
    TaskRun,
    AgentInstance,
    AgentDefinition,
    LLMCall,
    ExecutionCost,
)
from backend.db.models.enums import TaskStatus, RunStatus, AgentStatus


# Test database URL (in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test database with all tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_db):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.mark.integration
class TestAlembicMigrations:
    """Test Alembic migration functionality."""
    
    async def test_database_schema_creation(self, test_db):
        """Test that all tables are created correctly."""
        async with test_db.begin() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = [row[0] for row in result.fetchall()]
            
            # Check for key tables
            assert "workspaces" in tables
            assert "projects" in tables
            assert "tasks" in tables
            assert "task_runs" in tables
            assert "agent_instances" in tables
            assert "llm_calls" in tables
    
    async def test_table_columns_exist(self, test_db):
        """Test that required columns exist in tables."""
        async with test_db.begin() as conn:
            # Check workspaces table
            result = await conn.execute(
                text("PRAGMA table_info(workspaces)")
            )
            columns = [row[1] for row in result.fetchall()]
            assert "id" in columns
            assert "name" in columns
            assert "slug" in columns
            assert "created_at" in columns


@pytest.mark.integration
class TestModelCRUD:
    """Test CRUD operations on models."""
    
    async def test_workspace_create(self, test_session):
        """Test creating a workspace."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        assert workspace.id is not None
        assert workspace.name == "Test Workspace"
        assert workspace.slug == "test-workspace"
    
    async def test_workspace_read(self, test_session):
        """Test reading a workspace."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        workspace_id = workspace.id
        
        # Read back
        result = await test_session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        found = result.scalar_one()
        
        assert found.id == workspace_id
        assert found.name == "Test Workspace"
    
    async def test_workspace_update(self, test_session):
        """Test updating a workspace."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        # Update
        workspace.name = "Updated Workspace"
        await test_session.commit()
        
        # Verify
        result = await test_session.execute(
            select(Workspace).where(Workspace.id == workspace.id)
        )
        updated = result.scalar_one()
        assert updated.name == "Updated Workspace"
    
    async def test_workspace_delete(self, test_session):
        """Test deleting a workspace."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        workspace_id = workspace.id
        
        # Delete
        await test_session.delete(workspace)
        await test_session.commit()
        
        # Verify deleted
        result = await test_session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        assert result.scalar_one_or_none() is None
    
    async def test_project_create_with_workspace(self, test_session):
        """Test creating a project with workspace relationship."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        project = Project(
            name="Test Project",
            slug="test-project",
            workspace_id=workspace.id,
        )
        test_session.add(project)
        await test_session.commit()
        
        assert project.id is not None
        assert project.workspace_id == workspace.id
    
    async def test_task_create_with_project(self, test_session):
        """Test creating a task with project relationship."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        project = Project(
            name="Test Project",
            slug="test-project",
            workspace_id=workspace.id,
        )
        test_session.add(project)
        await test_session.commit()
        
        task = Task(
            title="Test Task",
            description="Test Description",
            project_id=project.id,
            workspace_id=workspace.id,
            status=TaskStatus.PENDING,
        )
        test_session.add(task)
        await test_session.commit()
        
        assert task.id is not None
        assert task.project_id == project.id
        assert task.status == TaskStatus.PENDING


@pytest.mark.integration
class TestTransactionRollback:
    """Test transaction rollback functionality."""
    
    async def test_transaction_rollback_on_error(self, test_session):
        """Test that transaction rollback works on error."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.flush()
        workspace_id = workspace.id
        
        # Try to create duplicate slug (should fail)
        duplicate = Workspace(
            name="Another Workspace",
            slug="test-workspace",  # Duplicate slug
        )
        test_session.add(duplicate)
        
        with pytest.raises(IntegrityError):
            await test_session.commit()
        
        # Rollback should have occurred
        await test_session.rollback()
        
        # Verify first workspace still exists
        result = await test_session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        assert result.scalar_one_or_none() is not None
    
    async def test_nested_transaction_rollback(self, test_session):
        """Test nested transaction rollback."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        # Start nested transaction
        async with test_session.begin():
            workspace.name = "Updated Name"
            await test_session.flush()
            
            # Rollback nested transaction
            await test_session.rollback()
        
        # Verify original name is still there
        await test_session.refresh(workspace)
        assert workspace.name == "Test Workspace"


@pytest.mark.integration
class TestConnectionPooling:
    """Test connection pooling functionality."""
    
    async def test_multiple_concurrent_queries(self, test_db):
        """Test that connection pool handles concurrent queries."""
        async_session = async_sessionmaker(test_db, class_=AsyncSession)
        
        # Create test data
        async with async_session() as session:
            workspace = Workspace(
                name="Test Workspace",
                slug="test-workspace",
            )
            session.add(workspace)
            await session.commit()
        
        # Run concurrent queries
        async def query_workspace(session):
            result = await session.execute(
                select(Workspace).where(Workspace.slug == "test-workspace")
            )
            return result.scalar_one_or_none()
        
        async with async_session() as session1:
            async with async_session() as session2:
                results = await asyncio.gather(
                    query_workspace(session1),
                    query_workspace(session2),
                )
                
                assert all(r is not None for r in results)
                assert all(r.slug == "test-workspace" for r in results)


@pytest.mark.integration
class TestAsyncQueries:
    """Test async query functionality."""
    
    async def test_async_select_query(self, test_session):
        """Test async SELECT query."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        result = await test_session.execute(
            select(Workspace).where(Workspace.slug == "test-workspace")
        )
        found = result.scalar_one()
        
        assert found.name == "Test Workspace"
    
    async def test_async_join_query(self, test_session):
        """Test async JOIN query."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        project = Project(
            name="Test Project",
            slug="test-project",
            workspace_id=workspace.id,
        )
        test_session.add(project)
        await test_session.commit()
        
        # Join query
        result = await test_session.execute(
            select(Project, Workspace)
            .join(Workspace, Project.workspace_id == Workspace.id)
            .where(Project.slug == "test-project")
        )
        row = result.first()
        
        assert row is not None
        assert row[0].name == "Test Project"
        assert row[1].name == "Test Workspace"
    
    async def test_async_aggregate_query(self, test_session):
        """Test async aggregate query."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        # Create multiple projects
        for i in range(3):
            project = Project(
                name=f"Project {i}",
                slug=f"project-{i}",
                workspace_id=workspace.id,
            )
            test_session.add(project)
        await test_session.commit()
        
        # Count projects
        from sqlalchemy import func
        result = await test_session.execute(
            select(func.count(Project.id))
            .where(Project.workspace_id == workspace.id)
        )
        count = result.scalar()
        
        assert count == 3


@pytest.mark.integration
class TestDatabaseConstraints:
    """Test database constraints."""
    
    async def test_unique_constraint_violation(self, test_session):
        """Test unique constraint violation."""
        workspace1 = Workspace(
            name="Test Workspace 1",
            slug="test-workspace",
        )
        test_session.add(workspace1)
        await test_session.commit()
        
        # Try to create duplicate slug
        workspace2 = Workspace(
            name="Test Workspace 2",
            slug="test-workspace",  # Duplicate
        )
        test_session.add(workspace2)
        
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    async def test_foreign_key_constraint(self, test_session):
        """Test foreign key constraint."""
        # Try to create project with non-existent workspace_id
        project = Project(
            name="Test Project",
            slug="test-project",
            workspace_id="non-existent-id",
        )
        test_session.add(project)
        
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    async def test_not_null_constraint(self, test_session):
        """Test NOT NULL constraint."""
        # Try to create workspace without required fields
        workspace = Workspace()
        test_session.add(workspace)
        
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    async def test_cascade_delete(self, test_session):
        """Test cascade delete behavior."""
        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
        )
        test_session.add(workspace)
        await test_session.commit()
        
        project = Project(
            name="Test Project",
            slug="test-project",
            workspace_id=workspace.id,
        )
        test_session.add(project)
        await test_session.commit()
        project_id = project.id
        
        # Delete workspace (should cascade to project)
        await test_session.delete(workspace)
        await test_session.commit()
        
        # Verify project is also deleted
        result = await test_session.execute(
            select(Project).where(Project.id == project_id)
        )
        assert result.scalar_one_or_none() is None




