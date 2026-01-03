"""
Shared fixtures for isolation tests
"""

import pytest
import uuid
from typing import Dict, Any
from fastapi.testclient import TestClient


@pytest.fixture
def workspace_a(db_session) -> Dict[str, Any]:
    """Create test workspace A"""
    workspace_id = f"test-workspace-a-{uuid.uuid4().hex[:8]}"
    workspace = {
        "id": workspace_id,
        "name": "Test Workspace A",
        "owner_id": f"user-a-{uuid.uuid4().hex[:8]}",
        "settings": {"quota_tasks": 100, "quota_storage_gb": 10},
        "created_at": "2025-01-03T00:00:00Z",
    }
    
    # Insert into database
    db_session.execute(
        """
        INSERT INTO workspaces (id, name, owner_id, settings, created_at)
        VALUES (:id, :name, :owner_id, :settings, :created_at)
        """,
        workspace
    )
    db_session.commit()
    
    yield workspace
    
    # Cleanup
    db_session.execute("DELETE FROM workspaces WHERE id = :id", {"id": workspace_id})
    db_session.commit()


@pytest.fixture
def workspace_b(db_session) -> Dict[str, Any]:
    """Create test workspace B"""
    workspace_id = f"test-workspace-b-{uuid.uuid4().hex[:8]}"
    workspace = {
        "id": workspace_id,
        "name": "Test Workspace B",
        "owner_id": f"user-b-{uuid.uuid4().hex[:8]}",
        "settings": {"quota_tasks": 100, "quota_storage_gb": 10},
        "created_at": "2025-01-03T00:00:00Z",
    }
    
    # Insert into database
    db_session.execute(
        """
        INSERT INTO workspaces (id, name, owner_id, settings, created_at)
        VALUES (:id, :name, :owner_id, :settings, :created_at)
        """,
        workspace
    )
    db_session.commit()
    
    yield workspace
    
    # Cleanup
    db_session.execute("DELETE FROM workspaces WHERE id = :id", {"id": workspace_id})
    db_session.commit()


@pytest.fixture
def user_a(workspace_a, db_session) -> Dict[str, Any]:
    """Create user for workspace A"""
    user_id = f"user-a-{uuid.uuid4().hex[:8]}"
    user = {
        "id": user_id,
        "email": f"user-a-{uuid.uuid4().hex[:8]}@test.com",
        "workspace_id": workspace_a["id"],
        "role": "admin",
    }
    
    # Insert into database
    db_session.execute(
        """
        INSERT INTO users (id, email, workspace_id, role)
        VALUES (:id, :email, :workspace_id, :role)
        """,
        user
    )
    db_session.commit()
    
    yield user
    
    # Cleanup
    db_session.execute("DELETE FROM users WHERE id = :id", {"id": user_id})
    db_session.commit()


@pytest.fixture
def user_b(workspace_b, db_session) -> Dict[str, Any]:
    """Create user for workspace B"""
    user_id = f"user-b-{uuid.uuid4().hex[:8]}"
    user = {
        "id": user_id,
        "email": f"user-b-{uuid.uuid4().hex[:8]}@test.com",
        "workspace_id": workspace_b["id"],
        "role": "admin",
    }
    
    # Insert into database
    db_session.execute(
        """
        INSERT INTO users (id, email, workspace_id, role)
        VALUES (:id, :email, :workspace_id, :role)
        """,
        user
    )
    db_session.commit()
    
    yield user
    
    # Cleanup
    db_session.execute("DELETE FROM users WHERE id = :id", {"id": user_id})
    db_session.commit()


@pytest.fixture
def token_a(user_a, workspace_a) -> str:
    """Generate JWT token for user A"""
    from app.core.auth import create_access_token
    
    token_data = {
        "sub": user_a["id"],
        "workspace_id": workspace_a["id"],
        "role": user_a["role"],
    }
    
    return create_access_token(data=token_data)


@pytest.fixture
def token_b(user_b, workspace_b) -> str:
    """Generate JWT token for user B"""
    from app.core.auth import create_access_token
    
    token_data = {
        "sub": user_b["id"],
        "workspace_id": workspace_b["id"],
        "role": user_b["role"],
    }
    
    return create_access_token(data=token_data)


@pytest.fixture
def task_in_workspace_a(workspace_a, db_session) -> Dict[str, Any]:
    """Create a task in workspace A"""
    task_id = f"task-a-{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "workspace_id": workspace_a["id"],
        "name": "Test Task A",
        "description": "Task belonging to workspace A",
        "status": "pending",
        "created_at": "2025-01-03T00:00:00Z",
    }
    
    # Insert into database
    db_session.execute(
        """
        INSERT INTO tasks (id, workspace_id, name, description, status, created_at)
        VALUES (:id, :workspace_id, :name, :description, :status, :created_at)
        """,
        task
    )
    db_session.commit()
    
    yield task
    
    # Cleanup
    db_session.execute("DELETE FROM tasks WHERE id = :id", {"id": task_id})
    db_session.commit()


@pytest.fixture
def task_in_workspace_b(workspace_b, db_session) -> Dict[str, Any]:
    """Create a task in workspace B"""
    task_id = f"task-b-{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "workspace_id": workspace_b["id"],
        "name": "Test Task B",
        "description": "Task belonging to workspace B",
        "status": "pending",
        "created_at": "2025-01-03T00:00:00Z",
    }
    
    # Insert into database
    db_session.execute(
        """
        INSERT INTO tasks (id, workspace_id, name, description, status, created_at)
        VALUES (:id, :workspace_id, :name, :description, :status, :created_at)
        """,
        task
    )
    db_session.commit()
    
    yield task
    
    # Cleanup
    db_session.execute("DELETE FROM tasks WHERE id = :id", {"id": task_id})
    db_session.commit()


@pytest.fixture
def api_client(app) -> TestClient:
    """Create FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def headers_workspace_a(token_a) -> Dict[str, str]:
    """HTTP headers for workspace A"""
    return {
        "Authorization": f"Bearer {token_a}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def headers_workspace_b(token_b) -> Dict[str, str]:
    """HTTP headers for workspace B"""
    return {
        "Authorization": f"Bearer {token_b}",
        "Content-Type": "application/json",
    }
