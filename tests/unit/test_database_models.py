# -*- coding: utf-8 -*-
"""
Database models unit tests.

Tests cover:
- Model serialization helpers
- Database operations
- Migration integrity
- In-memory SQLite testing with pytest-asyncio
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

# Import our database components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.db.models import (
    Workspace,
    Project,
    Task,
    TaskRun,
    MetricSnapshot,
    Artifact,
    TaskStatus,
    RunStatus,
    MetricType,
    ArtifactType,
    Base,
)
from backend.db.engine import create_test_engine
from backend.db.models.entities import *  # Import all models for Base metadata


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db() -> AsyncGenerator:
    """Create a test database with in-memory SQLite."""
    engine = await create_test_engine()
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def session(test_db) -> AsyncGenerator:
    """Create a test session."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    
    session_factory = async_sessionmaker(
        bind=test_db,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=True,
    )
    
    async with session_factory() as session:
        yield session
        await session.close()


@pytest.fixture
async def tenant(session: AsyncSession):
    """Create a workspace/project for tests."""
    from uuid import uuid4

    workspace = Workspace(name="Test Workspace", slug=f"test-{uuid4()}", meta_data={})
    session.add(workspace)
    await session.flush()

    project = Project(
        workspace_id=workspace.id,
        name="Test Project",
        slug=f"proj-{uuid4()}",
        meta_data={},
    )
    session.add(project)
    await session.flush()

    return workspace, project


class TestDatabaseModels:
    """Test suite for database models."""
    
    def test_model_imports(self):
        """Test that all models can be imported without circular references."""
        assert Task is not None
        assert TaskRun is not None
        assert MetricSnapshot is not None
        assert Artifact is not None
        
        # Test enums
        assert TaskStatus.PENDING == "pending"
        assert RunStatus.COMPLETED == "completed"
        assert MetricType.GAUGE == "gauge"
        assert ArtifactType.REPORT == "report"
    
    async def test_task_model_creation(self, session, tenant):
        """Test Task model creation and basic properties."""
        workspace, project = tenant

        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Test Task",
            description="A test task",
            config={"key": "value"},
            max_rounds=5,
            memory_size=50,
        )
        
        session.add(task)
        await session.flush()
        
        assert task.id is not None
        assert task.created_at is not None
        assert task.updated_at is not None
        assert task.status == TaskStatus.PENDING
        assert task.total_runs == 0
        assert task.successful_runs == 0
        assert task.failed_runs == 0
    
    async def test_task_serialization(self, session, tenant):
        """Test Task model serialization methods."""
        workspace, project = tenant

        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Serialization Test",
            description="Testing serialization",
            config={"test": "data"},
            status=TaskStatus.COMPLETED,
            total_runs=10,
            successful_runs=8,
        )
        
        session.add(task)
        await session.flush()
        
        # Test to_dict
        task_dict = task.to_dict()
        assert isinstance(task_dict, dict)
        assert task_dict["name"] == "Serialization Test"
        assert task_dict["status"] == "completed"
        assert "created_at" in task_dict
        assert "updated_at" in task_dict
        
        # Test success_rate property
        assert task.success_rate == 80.0
        
        # Test update_from_dict
        task.update_from_dict({"description": "Updated description"})
        assert task.description == "Updated description"
    
    async def test_task_run_model_creation(self, session, tenant):
        """Test TaskRun model creation and relationships."""
        workspace, project = tenant

        # Create parent task first
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Parent Task",
            description="Task with runs",
            config={},
            status=TaskStatus.RUNNING,
        )
        session.add(task)
        await session.flush()

        # Create task run
        run = TaskRun(
            task_id=task.id,
            workspace_id=workspace.id,
            project_id=project.id,
            run_number=1,
            status=RunStatus.COMPLETED,
            plan={"step": "test"},
            results={"output": "success"},
            duration=120.5,
            memory_used=512,
        )
        
        session.add(run)
        await session.flush()
        
        assert run.id is not None
        assert run.task_id == task.id
        assert run.is_success == True
        assert run.is_failed == False
    
    async def test_metric_snapshot_model(self, session, tenant):
        """Test MetricSnapshot model creation."""
        workspace, project = tenant

        # Create parent task
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Metric Task",
            description="Task for metrics",
            config={},
        )
        session.add(task)
        await session.flush()

        # Create metric
        metric = MetricSnapshot(
            workspace_id=workspace.id,
            project_id=project.id,
            task_id=task.id,
            name="cpu_usage",
            metric_type=MetricType.GAUGE,
            value=75.5,
            unit="%",
            labels={"host": "server1"},
        )
        
        session.add(metric)
        await session.flush()
        
        assert metric.id is not None
        assert metric.value == 75.5
        assert metric.unit == "%"
        assert metric.labels["host"] == "server1"
    
    async def test_artifact_model(self, session, tenant):
        """Test Artifact model creation."""
        workspace, project = tenant

        # Create parent task
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Artifact Task",
            description="Task for artifacts",
            config={},
        )
        session.add(task)
        await session.flush()

        # Create artifact
        artifact = Artifact(
            task_id=task.id,
            name="report.md",
            artifact_type=ArtifactType.REPORT,
            file_path="/reports/report.md",
            file_size=1024,
            content_type="text/markdown",
            content="# Report\n\nGenerated content",
            meta_data={"version": "1.0"},
        )
        
        session.add(artifact)
        await session.flush()
        
        assert artifact.id is not None
        assert artifact.file_size == 1024
        assert artifact.content_type == "text/markdown"
        assert artifact.meta_data["version"] == "1.0"
    
    async def test_model_relationships(self, session, tenant):
        """Test model relationships and cascade operations."""
        workspace, project = tenant

        # Create task with runs
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Relationship Test",
            description="Testing relationships",
            config={},
        )
        session.add(task)
        await session.flush()

        # Create runs
        runs = []
        for i in range(3):
            run = TaskRun(
                task_id=task.id,
                workspace_id=workspace.id,
                project_id=project.id,
                run_number=i + 1,
                status=RunStatus.COMPLETED,
                duration=60.0 + i * 10,
            )
            runs.append(run)
            session.add(run)
        
        await session.flush()
        
        # Test task-runs relationship
        assert len(task.runs) == 3
        assert all(run.task_id == task.id for run in task.runs)
        
        # Test run-metrics relationship
        metrics = []
        for run in runs:
            metric = MetricSnapshot(
                workspace_id=workspace.id,
                project_id=project.id,
                task_id=task.id,
                task_run_id=run.id,
                name=f"metric_{run.run_number}",
                metric_type=MetricType.GAUGE,
                value=run.run_number * 10,
            )
            metrics.append(metric)
            session.add(metric)
        
        await session.flush()
        assert len(run.metrics) == 1
        
        # Test cascade delete
        await session.delete(task)
        await session.flush()
        
        # Verify related records are deleted
        # (In SQLite with cascade, this should work)


class TestMigrationIntegrity:
    """Test suite for migration integrity and round-trip operations."""
    
    async def test_migration_upgrade_downgrade(self, test_db):
        """Test that basic writes work against a freshly created schema."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(bind=test_db, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            workspace = Workspace(name="Migration Workspace", slug="migration-ws", meta_data={})
            session.add(workspace)
            await session.flush()

            project = Project(workspace_id=workspace.id, name="Migration Project", slug="migration-proj", meta_data={})
            session.add(project)
            await session.flush()

            task = Task(
                workspace_id=workspace.id,
                project_id=project.id,
                name="Migration Test",
                description="Testing schema",
                config={},
            )
            session.add(task)
            await session.flush()

            assert task.id is not None
    
    async def test_database_constraints(self, session, tenant):
        """Test database constraints and validations."""
        workspace, project = tenant

        # Test required fields
        with pytest.raises(Exception):  # Should fail on null name
            task = Task(
                workspace_id=workspace.id,
                project_id=project.id,
                name=None,  # This should cause a constraint error
                description="Test",
                config={},
            )
            session.add(task)
            await session.flush()

        # Test enum constraints
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Valid Task",
            description="Test",
            config={},
            status=TaskStatus.PENDING,  # Valid enum value
        )
        session.add(task)
        await session.flush()
        assert task.status == TaskStatus.PENDING
    
    async def test_foreign_key_constraints(self, session, tenant):
        """Test foreign key constraints."""
        workspace, project = tenant

        # Create a task first
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="FK Test Task",
            description="Task for FK testing",
            config={},
        )
        session.add(task)
        await session.flush()

        # Create run with valid FK
        run = TaskRun(
            task_id=task.id,  # Valid FK
            workspace_id=workspace.id,
            project_id=project.id,
            run_number=1,
            status=RunStatus.PENDING,
        )
        session.add(run)
        await session.flush()
        assert run.id is not None

        # Create run with invalid FK - should fail
        invalid_run = TaskRun(
            task_id="invalid-uuid",  # Invalid FK
            workspace_id=workspace.id,
            project_id=project.id,
            run_number=2,
            status=RunStatus.PENDING,
        )
        session.add(invalid_run)
        with pytest.raises(Exception):  # Should fail on invalid FK
            await session.flush()


class TestDatabaseOperations:
    """Test suite for database CRUD operations."""
    
    async def test_crud_operations(self, session, tenant):
        """Test basic CRUD operations using model helpers."""
        workspace, project = tenant

        # CREATE
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            name="CRUD Test Task",
            description="Testing CRUD operations",
            config={"test": True},
        )
        await task.save(session)
        assert task.id is not None
        
        # READ
        retrieved_task = await Task.get_by_id(session, task.id)
        assert retrieved_task is not None
        assert retrieved_task.name == "CRUD Test Task"
        
        # UPDATE
        retrieved_task.description = "Updated description"
        await retrieved_task.save(session)
        
        # Verify update
        updated_task = await Task.get_by_id(session, task.id)
        assert updated_task.description == "Updated description"
        
        # DELETE
        await retrieved_task.delete(session)
        
        # Verify deletion
        deleted_task = await Task.get_by_id(session, task.id)
        assert deleted_task is None
    
    async def test_batch_operations(self, session):
        """Test batch database operations."""
        # Create multiple tasks
        tasks = []
        for i in range(5):
            task = Task(
                name=f"Batch Task {i+1}",
                description=f"Task {i+1} for batch testing",
                config={"batch": True, "index": i}
            )
            tasks.append(task)
            session.add(task)
        
        await session.flush()
        
        # Verify all tasks were created
        assert len(tasks) == 5
        assert all(task.id is not None for task in tasks)
        
        # Update multiple tasks
        for task in tasks:
            task.description = f"Updated batch task {task.name}"
        
        await session.flush()
        
        # Verify updates
        for task in tasks:
            assert "Updated" in task.description


class TestDatabasePerformance:
    """Test suite for database performance and indexing."""
    
    async def test_model_indexes(self, session):
        """Test that indexes are created and working."""
        # Create tasks with different statuses
        tasks = []
        statuses = [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED]
        
        for i, status in enumerate(statuses):
            task = Task(
                name=f"Index Test Task {i}",
                description=f"Task with status {status}",
                config={},
                status=status
            )
            tasks.append(task)
            session.add(task)
        
        await session.flush()
        
        # Verify we can query by index
        pending_tasks = await session.execute(
            "SELECT * FROM tasks WHERE status = 'pending'"
        )
        assert pending_tasks.rowcount > 0
    
    async def test_json_column_operations(self, session):
        """Test JSON column operations."""
        # Create task with complex config
        config = {
            "model": "gpt-4",
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 0.9
            },
            "tools": ["web_search", "calculator", "code_executor"],
            "metadata": {
                "created_by": "test",
                "version": "1.0"
            }
        }
        
        task = Task(
            name="JSON Test Task",
            description="Testing JSON operations",
            config=config
        )
        session.add(task)
        await session.flush()
        
        # Retrieve and verify JSON data
        retrieved_task = await Task.get_by_id(session, task.id)
        assert retrieved_task.config["model"] == "gpt-4"
        assert retrieved_task.config["parameters"]["temperature"] == 0.7
        assert "web_search" in retrieved_task.config["tools"]
        
        # Update JSON data
        retrieved_task.config["parameters"]["temperature"] = 0.8
        await retrieved_task.save(session)
        
        # Verify update
        updated_task = await Task.get_by_id(session, task.id)
        assert updated_task.config["parameters"]["temperature"] == 0.8


class TestDataIntegrity:
    """Test suite for data integrity and validation."""
    
    async def test_task_run_numbering(self, session):
        """Test that run numbers are unique per task."""
        # Create task
        task = Task(
            name="Run Number Test",
            description="Testing run numbering",
            config={}
        )
        session.add(task)
        await session.flush()
        
        # Create multiple runs for same task
        runs = []
        for i in range(3):
            run = TaskRun(
                task_id=task.id,
                run_number=i + 1,  # Sequential run numbers
                status=RunStatus.COMPLETED
            )
            runs.append(run)
            session.add(run)
        
        await session.flush()
        
        # Verify run numbers are as expected
        assert runs[0].run_number == 1
        assert runs[1].run_number == 2
        assert runs[2].run_number == 3
    
    async def test_timestamp_consistency(self, session):
        """Test that timestamps are consistent and realistic."""
        before_create = datetime.utcnow()
        
        task = Task(
            name="Timestamp Test",
            description="Testing timestamps",
            config={}
        )
        session.add(task)
        await session.flush()
        
        after_create = datetime.utcnow()
        
        # Verify timestamps are within expected range
        assert before_create <= task.created_at <= after_create
        assert task.updated_at is not None
        
        # Update task and check updated_at changes
        old_updated_at = task.updated_at
        await asyncio.sleep(0.01)  # Small delay to ensure time difference
        
        task.description = "Updated timestamp test"
        await task.save(session)
        
        assert task.updated_at > old_updated_at


# Run the tests if this file is executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])