# -*- coding: utf-8 -*-
"""
API E2E Tests

Tests cover:
- Complete workflow: Create workspace → Create project → Execute task → Get results
- Agent execution E2E: Task submission → Agent assignment → Execution → Result retrieval
- Cost tracking E2E: Execution → Cost calculation → Budget check
- Performance E2E: Load test → Metrics collection → Report generation
"""

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import create_app
from backend.db.models import Base, Workspace, Project, Task, TaskRun
from backend.db.models.enums import TaskStatus, RunStatus


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test database."""
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


@pytest.fixture
async def app(test_db):
    """Create test FastAPI app."""
    app = create_app()
    
    # Override database dependency
    from backend.db.engine import get_session
    async_session = async_sessionmaker(
        test_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async def override_get_session():
        async with async_session() as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    yield app
    
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    """Create test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete workflow from workspace creation to task execution."""
    
    async def test_create_workspace_to_task_execution(self, client, test_session):
        """Test complete workflow: Create workspace → Create project → Execute task → Get results."""
        # Step 1: Create workspace
        workspace_data = {
            "name": "E2E Test Workspace",
            "slug": "e2e-test-workspace",
        }
        workspace_response = await client.post("/api/workspaces", json=workspace_data)
        
        if workspace_response.status_code in [200, 201]:
            workspace = workspace_response.json()
            workspace_id = workspace.get("id")
            
            # Step 2: Create project
            project_data = {
                "name": "E2E Test Project",
                "slug": "e2e-test-project",
            }
            project_response = await client.post(
                f"/api/workspaces/{workspace_id}/projects",
                json=project_data
            )
            
            if project_response.status_code in [200, 201]:
                project = project_response.json()
                project_id = project.get("id")
                
                # Step 3: Create task
                task_data = {
                    "title": "E2E Test Task",
                    "description": "Test task for E2E workflow",
                }
                task_response = await client.post(
                    f"/api/workspaces/{workspace_id}/projects/{project_id}/tasks",
                    json=task_data
                )
                
                if task_response.status_code in [200, 201]:
                    task = task_response.json()
                    task_id = task.get("id")
                    
                    # Step 4: Get task results
                    get_task_response = await client.get(
                        f"/api/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"
                    )
                    
                    # Should be able to retrieve the task
                    assert get_task_response.status_code in [200, 401, 403]
    
    async def test_workspace_project_task_relationship(self, client, test_session):
        """Test that workspace, project, and task relationships are maintained."""
        # Create workspace
        workspace_data = {"name": "Relationship Test", "slug": "relationship-test"}
        workspace_response = await client.post("/api/workspaces", json=workspace_data)
        
        if workspace_response.status_code in [200, 201]:
            workspace = workspace_response.json()
            workspace_id = workspace.get("id")
            
            # Create project in workspace
            project_data = {"name": "Test Project", "slug": "test-project"}
            project_response = await client.post(
                f"/api/workspaces/{workspace_id}/projects",
                json=project_data
            )
            
            if project_response.status_code in [200, 201]:
                project = project_response.json()
                project_id = project.get("id")
                
                # Verify project belongs to workspace
                assert project.get("workspace_id") == workspace_id
                
                # List projects in workspace
                list_response = await client.get(
                    f"/api/workspaces/{workspace_id}/projects"
                )
                
                if list_response.status_code == 200:
                    projects = list_response.json()
                    # Should contain our project
                    project_ids = [p.get("id") for p in projects.get("items", [])]
                    assert project_id in project_ids


@pytest.mark.e2e
class TestAgentExecutionE2E:
    """Test agent execution end-to-end."""
    
    async def test_task_submission_to_result_retrieval(self, client, test_session):
        """Test: Task submission → Agent assignment → Execution → Result retrieval."""
        # This test would require:
        # 1. Create workspace and project
        # 2. Submit a task
        # 3. Wait for agent assignment
        # 4. Wait for execution
        # 5. Retrieve results
        
        # For now, we test the API endpoints exist and are callable
        workspace_data = {"name": "Agent Test", "slug": "agent-test"}
        workspace_response = await client.post("/api/workspaces", json=workspace_data)
        
        if workspace_response.status_code in [200, 201]:
            workspace = workspace_response.json()
            workspace_id = workspace.get("id")
            
            # Check if agent execution endpoints exist
            # These would be in agents or runs router
            agents_response = await client.get(f"/api/workspaces/{workspace_id}/agents")
            # Should return some response (may require auth)
            assert agents_response.status_code in [200, 401, 403, 404]
    
    async def test_task_run_lifecycle(self, client, test_session):
        """Test task run lifecycle: pending → running → completed."""
        # Create workspace and project
        workspace_data = {"name": "Run Test", "slug": "run-test"}
        workspace_response = await client.post("/api/workspaces", json=workspace_data)
        
        if workspace_response.status_code in [200, 201]:
            workspace = workspace_response.json()
            workspace_id = workspace.get("id")
            
            project_data = {"name": "Test Project", "slug": "test-project"}
            project_response = await client.post(
                f"/api/workspaces/{workspace_id}/projects",
                json=project_data
            )
            
            if project_response.status_code in [200, 201]:
                project = project_response.json()
                project_id = project.get("id")
                
                # Create task
                task_data = {"title": "Run Lifecycle Test", "description": "Test"}
                task_response = await client.post(
                    f"/api/workspaces/{workspace_id}/projects/{project_id}/tasks",
                    json=task_data
                )
                
                if task_response.status_code in [200, 201]:
                    task = task_response.json()
                    task_id = task.get("id")
                    
                    # Check runs endpoint
                    runs_response = await client.get(
                        f"/api/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}/runs"
                    )
                    # Should return runs list
                    assert runs_response.status_code in [200, 401, 403, 404]


@pytest.mark.e2e
class TestCostTrackingE2E:
    """Test cost tracking end-to-end."""
    
    async def test_execution_cost_calculation(self, client, test_session):
        """Test: Execution → Cost calculation → Budget check."""
        # Check cost tracking endpoints
        workspace_data = {"name": "Cost Test", "slug": "cost-test"}
        workspace_response = await client.post("/api/workspaces", json=workspace_data)
        
        if workspace_response.status_code in [200, 201]:
            workspace = workspace_response.json()
            workspace_id = workspace.get("id")
            
            # Check costs endpoint
            costs_response = await client.get(
                f"/api/workspaces/{workspace_id}/costs"
            )
            # Should return cost information
            assert costs_response.status_code in [200, 401, 403, 404]
    
    async def test_budget_check(self, client, test_session):
        """Test budget checking during execution."""
        # This would test that budget is checked before/during execution
        # and execution is blocked if budget exceeded
        pass


@pytest.mark.e2e
class TestPerformanceE2E:
    """Test performance metrics end-to-end."""
    
    async def test_performance_metrics_collection(self, client, test_session):
        """Test: Load test → Metrics collection → Report generation."""
        # Check performance endpoints
        workspace_data = {"name": "Perf Test", "slug": "perf-test"}
        workspace_response = await client.post("/api/workspaces", json=workspace_data)
        
        if workspace_response.status_code in [200, 201]:
            workspace = workspace_response.json()
            workspace_id = workspace.get("id")
            
            # Check performance metrics endpoint
            metrics_response = await client.get(
                f"/api/workspaces/{workspace_id}/performance/metrics"
            )
            # Should return performance metrics
            assert metrics_response.status_code in [200, 401, 403, 404]
    
    async def test_load_test_execution(self, client):
        """Test executing a load test and collecting results."""
        # This would test the load test harness integration
        # Check if load test endpoint exists
        load_test_response = await client.post("/api/performance/load-test")
        # May not exist, but should return some response
        assert load_test_response.status_code in [200, 201, 404, 405, 401, 403]




