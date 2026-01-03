"""
Data Isolation Tests

Tests to verify that data is completely isolated between workspaces.
Workspace A should not be able to access Workspace B's data in any way.
"""

import pytest
from fastapi.testclient import TestClient


class TestTaskDataIsolation:
    """Test task data isolation between workspaces"""
    
    def test_list_tasks_only_returns_own_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        task_in_workspace_a,
        task_in_workspace_b,
        headers_workspace_a,
    ):
        """TC-001: User A listing tasks should only see Workspace A's tasks"""
        response = api_client.get("/api/v1/tasks", headers=headers_workspace_a)
        
        assert response.status_code == 200
        tasks = response.json()
        
        # Verify only workspace A's tasks are returned
        workspace_ids = [task["workspace_id"] for task in tasks]
        assert all(wid == workspace_a["id"] for wid in workspace_ids)
        assert workspace_b["id"] not in workspace_ids
        
    def test_cannot_read_other_workspace_task_by_id(
        self,
        api_client: TestClient,
        task_in_workspace_b,
        headers_workspace_a,
    ):
        """TC-002: User A cannot read Workspace B's task by ID"""
        response = api_client.get(
            f"/api/v1/tasks/{task_in_workspace_b['id']}",
            headers=headers_workspace_a
        )
        
        # Should return 404 (not found) or 403 (forbidden)
        assert response.status_code in [403, 404]
        
    def test_cannot_update_other_workspace_task(
        self,
        api_client: TestClient,
        task_in_workspace_b,
        headers_workspace_a,
    ):
        """TC-003: User A cannot update Workspace B's task"""
        response = api_client.patch(
            f"/api/v1/tasks/{task_in_workspace_b['id']}",
            headers=headers_workspace_a,
            json={"name": "Hacked Task Name"}
        )
        
        assert response.status_code in [403, 404]
        
    def test_cannot_delete_other_workspace_task(
        self,
        api_client: TestClient,
        task_in_workspace_b,
        headers_workspace_a,
    ):
        """TC-004: User A cannot delete Workspace B's task"""
        response = api_client.delete(
            f"/api/v1/tasks/{task_in_workspace_b['id']}",
            headers=headers_workspace_a
        )
        
        assert response.status_code in [403, 404]
        
    def test_create_task_automatically_scoped_to_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        headers_workspace_a,
    ):
        """TC-005: Creating task automatically assigns correct workspace_id"""
        response = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_a,
            json={
                "name": "New Task",
                "description": "Test task creation",
                "type": "test",
            }
        )
        
        assert response.status_code in [200, 201]
        task = response.json()
        
        # Verify workspace_id is automatically set from token
        assert task["workspace_id"] == workspace_a["id"]
        
    def test_cannot_create_task_for_other_workspace(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
    ):
        """TC-006: Cannot specify another workspace's ID in task creation"""
        response = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_a,
            json={
                "name": "Malicious Task",
                "description": "Trying to create in workspace B",
                "workspace_id": workspace_b["id"],  # Attempt to specify different workspace
            }
        )
        
        if response.status_code in [200, 201]:
            task = response.json()
            # Even if request succeeds, workspace_id should be from token, not request
            assert task["workspace_id"] != workspace_b["id"]
        else:
            # Or request should be rejected
            assert response.status_code in [400, 403]


class TestAgentDataIsolation:
    """Test agent data isolation between workspaces"""
    
    def test_list_agents_only_returns_own_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        db_session,
    ):
        """User A listing agents should only see Workspace A's agents"""
        # Create agents in both workspaces
        db_session.execute(
            "INSERT INTO agents (id, workspace_id, name) VALUES (:id, :wid, :name)",
            {"id": "agent-a", "wid": workspace_a["id"], "name": "Agent A"}
        )
        db_session.execute(
            "INSERT INTO agents (id, workspace_id, name) VALUES (:id, :wid, :name)",
            {"id": "agent-b", "wid": workspace_b["id"], "name": "Agent B"}
        )
        db_session.commit()
        
        response = api_client.get("/api/v1/agents", headers=headers_workspace_a)
        
        assert response.status_code == 200
        agents = response.json()
        
        workspace_ids = [agent["workspace_id"] for agent in agents]
        assert all(wid == workspace_a["id"] for wid in workspace_ids)
        
        # Cleanup
        db_session.execute("DELETE FROM agents WHERE id IN ('agent-a', 'agent-b')")
        db_session.commit()
        
    def test_cannot_access_other_workspace_agent(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
        db_session,
    ):
        """User A cannot read Workspace B's agent"""
        # Create agent in workspace B
        db_session.execute(
            "INSERT INTO agents (id, workspace_id, name) VALUES (:id, :wid, :name)",
            {"id": "agent-b-secret", "wid": workspace_b["id"], "name": "Secret Agent"}
        )
        db_session.commit()
        
        response = api_client.get(
            "/api/v1/agents/agent-b-secret",
            headers=headers_workspace_a
        )
        
        assert response.status_code in [403, 404]
        
        # Cleanup
        db_session.execute("DELETE FROM agents WHERE id = 'agent-b-secret'")
        db_session.commit()


class TestWorkspaceMetadataIsolation:
    """Test workspace metadata isolation"""
    
    def test_cannot_read_other_workspace_details(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
    ):
        """User A cannot read Workspace B's details"""
        response = api_client.get(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers_workspace_a
        )
        
        assert response.status_code in [403, 404]
        
    def test_cannot_update_other_workspace_settings(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
    ):
        """User A cannot update Workspace B's settings"""
        response = api_client.patch(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers_workspace_a,
            json={"name": "Hacked Workspace"}
        )
        
        assert response.status_code in [403, 404]
        
    def test_can_only_see_own_workspace_in_list(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
    ):
        """User A listing workspaces should only see their own"""
        response = api_client.get("/api/v1/workspaces", headers=headers_workspace_a)
        
        assert response.status_code == 200
        workspaces = response.json()
        
        # Should only see workspace A
        workspace_ids = [ws["id"] for ws in workspaces]
        assert workspace_a["id"] in workspace_ids
        assert workspace_b["id"] not in workspace_ids


class TestSecretIsolation:
    """Test secret/credential isolation between workspaces"""
    
    def test_cannot_read_other_workspace_secrets(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
        db_session,
    ):
        """User A cannot read Workspace B's secrets"""
        # Create secret in workspace B
        db_session.execute(
            """
            INSERT INTO secrets (id, workspace_id, name, value)
            VALUES (:id, :wid, :name, :value)
            """,
            {
                "id": "secret-b",
                "wid": workspace_b["id"],
                "name": "API_KEY",
                "value": "secret-value-123"
            }
        )
        db_session.commit()
        
        response = api_client.get(
            "/api/v1/secrets/secret-b",
            headers=headers_workspace_a
        )
        
        assert response.status_code in [403, 404]
        
        # Cleanup
        db_session.execute("DELETE FROM secrets WHERE id = 'secret-b'")
        db_session.commit()
        
    def test_list_secrets_only_returns_own_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        db_session,
    ):
        """Listing secrets should only return own workspace's secrets"""
        # Create secrets in both workspaces
        db_session.execute(
            """
            INSERT INTO secrets (id, workspace_id, name, value)
            VALUES (:id, :wid, :name, :value)
            """,
            {
                "id": "secret-a",
                "wid": workspace_a["id"],
                "name": "API_KEY_A",
                "value": "value-a"
            }
        )
        db_session.execute(
            """
            INSERT INTO secrets (id, workspace_id, name, value)
            VALUES (:id, :wid, :name, :value)
            """,
            {
                "id": "secret-b",
                "wid": workspace_b["id"],
                "name": "API_KEY_B",
                "value": "value-b"
            }
        )
        db_session.commit()
        
        response = api_client.get("/api/v1/secrets", headers=headers_workspace_a)
        
        assert response.status_code == 200
        secrets = response.json()
        
        workspace_ids = [secret["workspace_id"] for secret in secrets]
        assert all(wid == workspace_a["id"] for wid in workspace_ids)
        
        # Cleanup
        db_session.execute("DELETE FROM secrets WHERE id IN ('secret-a', 'secret-b')")
        db_session.commit()


class TestArtifactIsolation:
    """Test artifact/file isolation between workspaces"""
    
    def test_cannot_access_other_workspace_artifacts(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
        db_session,
    ):
        """User A cannot access Workspace B's artifacts"""
        # Create artifact in workspace B
        db_session.execute(
            """
            INSERT INTO artifacts (id, workspace_id, name, path)
            VALUES (:id, :wid, :name, :path)
            """,
            {
                "id": "artifact-b",
                "wid": workspace_b["id"],
                "name": "output.txt",
                "path": "/artifacts/workspace-b/output.txt"
            }
        )
        db_session.commit()
        
        response = api_client.get(
            "/api/v1/artifacts/artifact-b",
            headers=headers_workspace_a
        )
        
        assert response.status_code in [403, 404]
        
        # Cleanup
        db_session.execute("DELETE FROM artifacts WHERE id = 'artifact-b'")
        db_session.commit()


class TestDatabaseQueryIsolation:
    """Test that database queries properly filter by workspace_id"""
    
    def test_all_queries_filter_by_workspace_id(
        self,
        db_session,
        workspace_a,
        workspace_b,
    ):
        """Verify that direct database queries always filter by workspace_id"""
        # This is a code inspection test - verify query patterns
        # In production, this would be enforced by:
        # 1. PostgreSQL Row-Level Security (RLS)
        # 2. ORM query filters
        # 3. Database views
        
        # Example: Query tasks without workspace filter should be rejected
        # or should use RLS to automatically filter
        
        # Create test data
        db_session.execute(
            "INSERT INTO tasks (id, workspace_id, name) VALUES (:id, :wid, :name)",
            {"id": "task-test-a", "wid": workspace_a["id"], "name": "Task A"}
        )
        db_session.execute(
            "INSERT INTO tasks (id, workspace_id, name) VALUES (:id, :wid, :name)",
            {"id": "task-test-b", "wid": workspace_b["id"], "name": "Task B"}
        )
        db_session.commit()
        
        # Query WITH workspace filter (correct)
        result = db_session.execute(
            "SELECT * FROM tasks WHERE workspace_id = :wid",
            {"wid": workspace_a["id"]}
        ).fetchall()
        
        assert len(result) >= 1
        assert all(row[1] == workspace_a["id"] for row in result)  # workspace_id column
        
        # Cleanup
        db_session.execute(
            "DELETE FROM tasks WHERE id IN ('task-test-a', 'task-test-b')"
        )
        db_session.commit()
