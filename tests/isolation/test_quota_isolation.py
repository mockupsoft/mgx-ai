"""
Resource Quota Isolation Tests

Tests to verify that resource quotas are enforced per workspace
and one workspace hitting its quota doesn't affect other workspaces.
"""

import pytest
from fastapi.testclient import TestClient


class TestTaskQuotaIsolation:
    """Test that task quotas are enforced per workspace"""
    
    def test_workspace_a_quota_does_not_affect_workspace_b(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        headers_workspace_b,
        db_session,
    ):
        """TC-003: Workspace A hitting quota doesn't block Workspace B"""
        # Set workspace A to have quota of 5 tasks
        db_session.execute(
            """
            UPDATE workspaces
            SET settings = jsonb_set(settings, '{quota_tasks}', '5')
            WHERE id = :wid
            """,
            {"wid": workspace_a["id"]}
        )
        db_session.commit()
        
        # Create 5 tasks in workspace A (at quota)
        for i in range(5):
            response = api_client.post(
                "/api/v1/tasks",
                headers=headers_workspace_a,
                json={"name": f"Task {i}", "type": "test"}
            )
            assert response.status_code in [200, 201]
        
        # 6th task should fail (quota exceeded)
        response_fail = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_a,
            json={"name": "Task 6", "type": "test"}
        )
        assert response_fail.status_code in [403, 429]  # Quota exceeded
        
        # Workspace B should still be able to create tasks
        response_b = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_b,
            json={"name": "Workspace B Task", "type": "test"}
        )
        assert response_b.status_code in [200, 201]
        
    def test_quota_counters_are_workspace_specific(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        headers_workspace_b,
    ):
        """Quota counters are maintained separately per workspace"""
        # Get quota info for workspace A
        response_a = api_client.get(
            f"/api/v1/workspaces/{workspace_a['id']}/quota",
            headers=headers_workspace_a
        )
        assert response_a.status_code == 200
        quota_a = response_a.json()
        
        # Get quota info for workspace B
        response_b = api_client.get(
            f"/api/v1/workspaces/{workspace_b['id']}/quota",
            headers=headers_workspace_b
        )
        assert response_b.status_code == 200
        quota_b = response_b.json()
        
        # Quotas should be independent
        assert quota_a["workspace_id"] == workspace_a["id"]
        assert quota_b["workspace_id"] == workspace_b["id"]
        assert quota_a != quota_b  # Should have different usage


class TestStorageQuotaIsolation:
    """Test storage quota isolation between workspaces"""
    
    def test_storage_quota_isolation(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        headers_workspace_b,
        db_session,
    ):
        """Workspace A storage quota doesn't affect Workspace B"""
        # Set workspace A storage quota to 10MB
        db_session.execute(
            """
            UPDATE workspaces
            SET settings = jsonb_set(settings, '{quota_storage_gb}', '0.01')
            WHERE id = :wid
            """,
            {"wid": workspace_a["id"]}
        )
        db_session.commit()
        
        # Simulate workspace A reaching storage quota
        db_session.execute(
            """
            UPDATE workspace_usage
            SET storage_used_bytes = 11000000
            WHERE workspace_id = :wid
            """,
            {"wid": workspace_a["id"]}
        )
        db_session.commit()
        
        # Workspace A upload should fail
        response_a = api_client.post(
            "/api/v1/artifacts/upload",
            headers=headers_workspace_a,
            files={"file": ("test.txt", b"test data", "text/plain")}
        )
        assert response_a.status_code in [403, 413, 429]
        
        # Workspace B should still work
        response_b = api_client.post(
            "/api/v1/artifacts/upload",
            headers=headers_workspace_b,
            files={"file": ("test.txt", b"test data", "text/plain")}
        )
        assert response_b.status_code in [200, 201]


class TestRateLimitIsolation:
    """Test rate limiting isolation between workspaces"""
    
    def test_rate_limit_per_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        headers_workspace_b,
    ):
        """Workspace A hitting rate limit doesn't affect Workspace B"""
        # Make many rapid requests from workspace A
        responses_a = []
        for i in range(100):  # Exceed rate limit
            response = api_client.get(
                "/api/v1/tasks",
                headers=headers_workspace_a
            )
            responses_a.append(response)
        
        # Workspace A should eventually be rate limited
        rate_limited = any(r.status_code == 429 for r in responses_a)
        assert rate_limited, "Workspace A should be rate limited"
        
        # Workspace B should still work normally
        response_b = api_client.get(
            "/api/v1/tasks",
            headers=headers_workspace_b
        )
        assert response_b.status_code == 200


class TestComputeQuotaIsolation:
    """Test compute resource quota isolation"""
    
    def test_compute_quota_isolation(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
        headers_workspace_b,
        db_session,
    ):
        """Workspace A exhausting compute doesn't affect Workspace B"""
        # Set workspace A compute quota (e.g., max concurrent tasks)
        db_session.execute(
            """
            UPDATE workspaces
            SET settings = jsonb_set(settings, '{quota_concurrent_tasks}', '2')
            WHERE id = :wid
            """,
            {"wid": workspace_a["id"]}
        )
        db_session.commit()
        
        # Create 2 running tasks in workspace A (at limit)
        for i in range(2):
            db_session.execute(
                """
                INSERT INTO tasks (id, workspace_id, name, status)
                VALUES (:id, :wid, :name, 'running')
                """,
                {
                    "id": f"running-a-{i}",
                    "wid": workspace_a["id"],
                    "name": f"Running Task {i}"
                }
            )
        db_session.commit()
        
        # Workspace A should not be able to create another running task
        response_a = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_a,
            json={"name": "Task 3", "type": "test", "start_immediately": True}
        )
        assert response_a.status_code in [403, 429]
        
        # Workspace B should still work
        response_b = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_b,
            json={"name": "Workspace B Task", "type": "test", "start_immediately": True}
        )
        assert response_b.status_code in [200, 201]
        
        # Cleanup
        db_session.execute(
            "DELETE FROM tasks WHERE id LIKE 'running-a-%'"
        )
        db_session.commit()
