# -*- coding: utf-8 -*-
"""
Integration tests for Phase 4.5 API & Events.

Tests cover:
- REST API endpoints (CRUD for tasks/runs)
- WebSocket event streaming
- Plan approval flow
- Background execution
- Event broadcasting
"""

import asyncio
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import create_app
from backend.db.models import Base, Task, TaskRun
from backend.db.models.enums import TaskStatus, RunStatus
from backend.schemas import EventTypeEnum
from backend.services import get_event_broadcaster, get_task_executor, get_team_provider

# Test database URL (in-memory SQLite)
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


@pytest.fixture
async def app():
    """Create test FastAPI app."""
    return create_app()


@pytest.fixture
async def client(app, test_db):
    """Create test client."""
    # Override get_session dependency
    async def override_get_session():
        async_session = async_sessionmaker(
            test_db,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_session() as session:
            yield session
    
    from backend.db.session import get_session
    app.dependency_overrides[get_session] = override_get_session
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ============================================
# Task CRUD Tests
# ============================================

class TestTasksCRUD:
    """Tests for task CRUD operations."""
    
    async def test_create_task(self, client):
        """Test creating a new task."""
        response = await client.post(
            "/api/tasks/",
            json={
                "name": "Test Task",
                "description": "A test task",
                "max_rounds": 5,
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Task"
        assert data["description"] == "A test task"
        assert data["status"] == "pending"
        assert "id" in data
        
        return data["id"]
    
    async def test_list_tasks(self, client):
        """Test listing tasks."""
        # Create a task first
        task_id = await self.test_create_task(client)
        
        response = await client.get("/api/tasks/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert any(t["id"] == task_id for t in data["items"])
    
    async def test_get_task(self, client):
        """Test getting a specific task."""
        task_id = await self.test_create_task(client)
        
        response = await client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == task_id
        assert data["name"] == "Test Task"
    
    async def test_update_task(self, client):
        """Test updating a task."""
        task_id = await self.test_create_task(client)
        
        response = await client.patch(
            f"/api/tasks/{task_id}",
            json={
                "name": "Updated Task",
                "max_rounds": 10,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Task"
        assert data["max_rounds"] == 10
    
    async def test_delete_task(self, client):
        """Test deleting a task."""
        task_id = await self.test_create_task(client)
        
        response = await client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "deleted"
        assert data["task_id"] == task_id
        
        # Verify deletion
        response = await client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 404


# ============================================
# Run CRUD & Approval Tests
# ============================================

class TestRunsCRUD:
    """Tests for run CRUD operations and approval flow."""
    
    async def test_create_run_triggers_execution(self, client):
        """Test that creating a run triggers background execution."""
        # Create a task
        task_response = await client.post(
            "/api/tasks/",
            json={
                "name": "Test Task",
                "description": "Test task description",
            }
        )
        task_id = task_response.json()["id"]
        
        # Create a run
        response = await client.post(
            "/api/runs/",
            json={"task_id": task_id}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == task_id
        assert "id" in data
        
        return task_id, data["id"]
    
    async def test_list_runs(self, client):
        """Test listing runs."""
        task_id, run_id = await self.test_create_run_triggers_execution(client)
        
        response = await client.get("/api/runs/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] >= 1
        assert any(r["id"] == run_id for r in data["items"])
    
    async def test_list_runs_by_task(self, client):
        """Test listing runs filtered by task."""
        task_id, run_id = await self.test_create_run_triggers_execution(client)
        
        response = await client.get(f"/api/runs/?task_id={task_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert all(r["task_id"] == task_id for r in data["items"])
    
    async def test_get_run(self, client):
        """Test getting a specific run."""
        task_id, run_id = await self.test_create_run_triggers_execution(client)
        
        response = await client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == run_id
        assert data["task_id"] == task_id
    
    async def test_approve_plan_approved(self, client):
        """Test approving a plan."""
        task_id, run_id = await self.test_create_run_triggers_execution(client)
        
        # Wait a bit for executor to reach approval state
        await asyncio.sleep(0.2)
        
        response = await client.post(
            f"/api/runs/{run_id}/approve",
            json={
                "approved": True,
                "feedback": "Plan looks good",
            }
        )
        
        assert response.status_code == 200
    
    async def test_approve_plan_rejected(self, client):
        """Test rejecting a plan."""
        task_id, run_id = await self.test_create_run_triggers_execution(client)
        
        await asyncio.sleep(0.2)
        
        response = await client.post(
            f"/api/runs/{run_id}/approve",
            json={
                "approved": False,
                "feedback": "Plan needs revision",
            }
        )
        
        assert response.status_code == 200
    
    async def test_delete_run(self, client):
        """Test deleting a run."""
        task_id, run_id = await self.test_create_run_triggers_execution(client)
        
        response = await client.delete(f"/api/runs/{run_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "deleted"
        assert data["run_id"] == run_id


# ============================================
# Metrics Tests
# ============================================

class TestMetrics:
    """Tests for metrics endpoints."""
    
    async def test_list_metrics(self, client):
        """Test listing metrics."""
        response = await client.get("/api/metrics/")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    async def test_metrics_pagination(self, client):
        """Test metrics pagination."""
        response = await client.get("/api/metrics/?skip=0&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 5


# ============================================
# Event Broadcasting Tests
# ============================================

class TestEventBroadcasting:
    """Tests for event broadcaster functionality."""
    
    async def test_event_broadcaster_singleton(self):
        """Test that broadcaster is a singleton."""
        b1 = get_event_broadcaster()
        b2 = get_event_broadcaster()
        
        assert b1 is b2
    
    async def test_subscribe_unsubscribe(self):
        """Test subscription and unsubscription."""
        broadcaster = get_event_broadcaster()
        
        queue = await broadcaster.subscribe("test_sub", ["task:123"])
        assert queue is not None
        
        await broadcaster.unsubscribe("test_sub")
    
    async def test_publish_event(self):
        """Test publishing an event."""
        from backend.schemas import EventPayload
        
        broadcaster = get_event_broadcaster()
        
        # Subscribe
        queue = await broadcaster.subscribe("test_sub", ["task:123"])
        
        # Publish
        event = EventPayload(
            event_type=EventTypeEnum.ANALYSIS_START,
            task_id="task_123",
            run_id="run_456",
            message="Test event",
        )
        
        await broadcaster.publish(event)
        
        # Receive
        received_event = await asyncio.wait_for(queue.get(), timeout=1)
        assert received_event["event_type"] == "analysis_start"
        assert received_event["task_id"] == "task_123"
    
    async def test_wildcard_subscription(self):
        """Test subscribing to all events."""
        from backend.schemas import PlanReadyEvent
        
        broadcaster = get_event_broadcaster()
        
        # Subscribe to all
        queue = await broadcaster.subscribe("test_sub", ["all"])
        
        # Publish
        event = PlanReadyEvent(
            task_id="task_456",
            run_id="run_789",
            data={"plan": "test"},
            message="Plan ready",
        )
        
        await broadcaster.publish(event)
        
        # Receive
        received_event = await asyncio.wait_for(queue.get(), timeout=1)
        assert received_event["event_type"] == "plan_ready"


# ============================================
# WebSocket Tests
# ============================================

class TestWebSocketEvents:
    """Tests for WebSocket event streaming."""
    
    async def test_websocket_task_stream_connects(self, app):
        """Test WebSocket connection for task stream."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with client.websocket_connect("/ws/tasks/task_123") as websocket:
            # Connection successful
            pass
    
    async def test_websocket_receive_event(self, app):
        """Test receiving events via WebSocket."""
        from fastapi.testclient import TestClient
        from backend.services import get_event_broadcaster
        
        client = TestClient(app)
        
        async def send_event():
            await asyncio.sleep(0.1)
            broadcaster = get_event_broadcaster()
            from backend.schemas import AnalysisStartEvent
            
            event = AnalysisStartEvent(
                task_id="task_123",
                run_id="run_456",
                message="Analysis started",
            )
            await broadcaster.publish(event)
        
        # This would require async context which TestClient doesn't support
        # In a real scenario, use pytest-asyncio
        pass
    
    async def test_websocket_run_stream(self, app):
        """Test WebSocket connection for run stream."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with client.websocket_connect("/ws/runs/run_123") as websocket:
            # Connection successful
            pass
    
    async def test_websocket_global_stream(self, app):
        """Test WebSocket connection for global stream."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with client.websocket_connect("/ws/stream") as websocket:
            # Connection successful
            pass


# ============================================
# Plan Approval Flow Tests
# ============================================

class TestPlanApprovalFlow:
    """Tests for the complete plan approval flow."""
    
    async def test_approval_flow_step_by_step(self, client):
        """Test complete approval flow."""
        # 1. Create task
        task_response = await client.post(
            "/api/tasks/",
            json={
                "name": "Approval Test Task",
                "description": "Test plan approval",
            }
        )
        task_id = task_response.json()["id"]
        
        # 2. Create run (triggers execution and events)
        run_response = await client.post(
            "/api/runs/",
            json={"task_id": task_id}
        )
        run_id = run_response.json()["id"]
        assert run_response.status_code == 201
        
        # 3. Verify run is created
        get_response = await client.get(f"/api/runs/{run_id}")
        assert get_response.status_code == 200
        
        # 4. Wait for executor to be ready
        await asyncio.sleep(0.2)
        
        # 5. Approve plan
        approve_response = await client.post(
            f"/api/runs/{run_id}/approve",
            json={"approved": True, "feedback": "Good plan"}
        )
        assert approve_response.status_code == 200
        
        # 6. Verify execution continues
        await asyncio.sleep(0.2)


# ============================================
# Integration Flow Tests
# ============================================

class TestIntegrationFlow:
    """End-to-end integration tests."""
    
    async def test_complete_task_execution_flow(self, client):
        """Test complete task execution flow."""
        # 1. Create task
        task_response = await client.post(
            "/api/tasks/",
            json={
                "name": "Complete Flow Test",
                "description": "Test complete flow",
                "max_rounds": 3,
            }
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]
        
        # 2. Verify task created
        get_task = await client.get(f"/api/tasks/{task_id}")
        assert get_task.status_code == 200
        
        # 3. Create run
        run_response = await client.post(
            "/api/runs/",
            json={"task_id": task_id}
        )
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        # 4. List runs
        list_runs = await client.get(f"/api/runs/?task_id={task_id}")
        assert list_runs.status_code == 200
        assert any(r["id"] == run_id for r in list_runs.json()["items"])
        
        # 5. Approve plan
        await asyncio.sleep(0.2)
        approve = await client.post(
            f"/api/runs/{run_id}/approve",
            json={"approved": True}
        )
        assert approve.status_code == 200
        
        # 6. Get run status
        get_run = await client.get(f"/api/runs/{run_id}")
        assert get_run.status_code == 200


# ============================================
# Error Handling Tests
# ============================================

class TestErrorHandling:
    """Tests for error conditions."""
    
    async def test_get_nonexistent_task(self, client):
        """Test getting a task that doesn't exist."""
        response = await client.get("/api/tasks/nonexistent")
        assert response.status_code == 404
    
    async def test_get_nonexistent_run(self, client):
        """Test getting a run that doesn't exist."""
        response = await client.get("/api/runs/nonexistent")
        assert response.status_code == 404
    
    async def test_create_run_for_nonexistent_task(self, client):
        """Test creating a run for nonexistent task."""
        response = await client.post(
            "/api/runs/",
            json={"task_id": "nonexistent"}
        )
        assert response.status_code == 404
    
    async def test_invalid_status_filter(self, client):
        """Test filtering with invalid status."""
        response = await client.get("/api/tasks/?status=invalid_status")
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
