"""
Authentication & Authorization Isolation Tests

Tests to verify that authentication tokens are properly scoped to workspaces
and cannot be used to access other workspaces.
"""

import pytest
import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


class TestTokenScopeValidation:
    """Test that tokens are properly scoped to workspaces"""
    
    def test_token_cannot_access_other_workspace(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
    ):
        """TC-002: User A's token cannot access Workspace B's resources"""
        response = api_client.get(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers_workspace_a
        )
        
        assert response.status_code in [403, 404]
        
    def test_token_includes_workspace_id_claim(
        self,
        token_a,
        workspace_a,
    ):
        """Verify token includes workspace_id in JWT claims"""
        from app.core.auth import SECRET_KEY, ALGORITHM
        
        decoded = jwt.decode(token_a, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert "workspace_id" in decoded
        assert decoded["workspace_id"] == workspace_a["id"]
        
    def test_modified_token_is_rejected(
        self,
        api_client: TestClient,
        token_a,
        workspace_b,
    ):
        """Attempting to modify token's workspace_id should fail"""
        from app.core.auth import SECRET_KEY, ALGORITHM
        
        # Decode token
        decoded = jwt.decode(token_a, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Attempt to modify workspace_id
        decoded["workspace_id"] = workspace_b["id"]
        
        # Try to re-encode (will fail signature verification)
        # Note: This will create invalid signature
        tampered_token = jwt.encode(decoded, "wrong-secret", algorithm=ALGORITHM)
        
        # Attempt to use tampered token
        headers = {"Authorization": f"Bearer {tampered_token}"}
        response = api_client.get("/api/v1/workspaces", headers=headers)
        
        # Should be rejected due to invalid signature
        assert response.status_code == 401
        
    def test_expired_token_is_rejected(
        self,
        api_client: TestClient,
        user_a,
        workspace_a,
    ):
        """Expired tokens should be rejected"""
        from app.core.auth import SECRET_KEY, ALGORITHM
        
        # Create expired token
        expired_data = {
            "sub": user_a["id"],
            "workspace_id": workspace_a["id"],
            "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        }
        
        expired_token = jwt.encode(expired_data, SECRET_KEY, algorithm=ALGORITHM)
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = api_client.get("/api/v1/workspaces", headers=headers)
        
        assert response.status_code == 401
        
    def test_token_without_workspace_id_is_rejected(
        self,
        api_client: TestClient,
        user_a,
    ):
        """Token without workspace_id claim should be rejected"""
        from app.core.auth import SECRET_KEY, ALGORITHM
        
        # Create token without workspace_id
        token_data = {
            "sub": user_a["id"],
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        invalid_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        
        headers = {"Authorization": f"Bearer {invalid_token}"}
        response = api_client.get("/api/v1/workspaces", headers=headers)
        
        # Should be rejected or default to error
        assert response.status_code in [400, 401, 403]


class TestRBACIsolation:
    """Test that RBAC roles are workspace-scoped"""
    
    def test_admin_in_workspace_a_not_admin_in_workspace_b(
        self,
        api_client: TestClient,
        user_a,
        workspace_b,
        headers_workspace_a,
    ):
        """Admin role in Workspace A doesn't grant admin in Workspace B"""
        # User A is admin in Workspace A
        assert user_a["role"] == "admin"
        
        # Try to perform admin action in Workspace B
        response = api_client.delete(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers_workspace_a
        )
        
        # Should be rejected (not admin in workspace B)
        assert response.status_code in [403, 404]
        
    def test_member_cannot_access_other_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        db_session,
    ):
        """Member in Workspace A has no access to Workspace B"""
        from app.core.auth import create_access_token
        
        # Create member user in workspace A
        db_session.execute(
            """
            INSERT INTO users (id, email, workspace_id, role)
            VALUES (:id, :email, :wid, :role)
            """,
            {
                "id": "member-a",
                "email": "member-a@test.com",
                "wid": workspace_a["id"],
                "role": "member"
            }
        )
        db_session.commit()
        
        # Create token for member
        token = create_access_token({
            "sub": "member-a",
            "workspace_id": workspace_a["id"],
            "role": "member"
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access workspace B
        response = api_client.get(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers
        )
        
        assert response.status_code in [403, 404]
        
        # Cleanup
        db_session.execute("DELETE FROM users WHERE id = 'member-a'")
        db_session.commit()
        
    def test_viewer_role_is_workspace_scoped(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        db_session,
    ):
        """Viewer in Workspace A cannot view Workspace B"""
        from app.core.auth import create_access_token
        
        # Create viewer user in workspace A
        db_session.execute(
            """
            INSERT INTO users (id, email, workspace_id, role)
            VALUES (:id, :email, :wid, :role)
            """,
            {
                "id": "viewer-a",
                "email": "viewer-a@test.com",
                "wid": workspace_a["id"],
                "role": "viewer"
            }
        )
        db_session.commit()
        
        # Create token for viewer
        token = create_access_token({
            "sub": "viewer-a",
            "workspace_id": workspace_a["id"],
            "role": "viewer"
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Can view workspace A
        response_a = api_client.get(
            f"/api/v1/workspaces/{workspace_a['id']}",
            headers=headers
        )
        assert response_a.status_code == 200
        
        # Cannot view workspace B
        response_b = api_client.get(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers
        )
        assert response_b.status_code in [403, 404]
        
        # Cleanup
        db_session.execute("DELETE FROM users WHERE id = 'viewer-a'")
        db_session.commit()


class TestAPIKeyIsolation:
    """Test that API keys are workspace-scoped"""
    
    def test_api_key_scoped_to_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        db_session,
    ):
        """API key for Workspace A cannot access Workspace B"""
        # Create API key for workspace A
        db_session.execute(
            """
            INSERT INTO api_keys (id, workspace_id, key_hash, name)
            VALUES (:id, :wid, :hash, :name)
            """,
            {
                "id": "apikey-a",
                "wid": workspace_a["id"],
                "hash": "hash-a",
                "name": "Test API Key A"
            }
        )
        db_session.commit()
        
        # Use API key to access workspace A (should work)
        headers = {"X-API-Key": "hash-a"}
        response_a = api_client.get(
            f"/api/v1/workspaces/{workspace_a['id']}",
            headers=headers
        )
        assert response_a.status_code == 200
        
        # Try to access workspace B with same API key (should fail)
        response_b = api_client.get(
            f"/api/v1/workspaces/{workspace_b['id']}",
            headers=headers
        )
        assert response_b.status_code in [403, 404]
        
        # Cleanup
        db_session.execute("DELETE FROM api_keys WHERE id = 'apikey-a'")
        db_session.commit()
        
    def test_multiple_api_keys_per_workspace(
        self,
        api_client: TestClient,
        workspace_a,
        db_session,
    ):
        """Multiple API keys can exist for same workspace"""
        # Create multiple API keys for workspace A
        db_session.execute(
            """
            INSERT INTO api_keys (id, workspace_id, key_hash, name)
            VALUES (:id, :wid, :hash, :name)
            """,
            {
                "id": "apikey-a-1",
                "wid": workspace_a["id"],
                "hash": "hash-a-1",
                "name": "API Key 1"
            }
        )
        db_session.execute(
            """
            INSERT INTO api_keys (id, workspace_id, key_hash, name)
            VALUES (:id, :wid, :hash, :name)
            """,
            {
                "id": "apikey-a-2",
                "wid": workspace_a["id"],
                "hash": "hash-a-2",
                "name": "API Key 2"
            }
        )
        db_session.commit()
        
        # Both keys should work for workspace A
        headers1 = {"X-API-Key": "hash-a-1"}
        response1 = api_client.get(
            f"/api/v1/workspaces/{workspace_a['id']}",
            headers=headers1
        )
        assert response1.status_code == 200
        
        headers2 = {"X-API-Key": "hash-a-2"}
        response2 = api_client.get(
            f"/api/v1/workspaces/{workspace_a['id']}",
            headers=headers2
        )
        assert response2.status_code == 200
        
        # Cleanup
        db_session.execute(
            "DELETE FROM api_keys WHERE id IN ('apikey-a-1', 'apikey-a-2')"
        )
        db_session.commit()


class TestSecurityBypassAttempts:
    """Test attempts to bypass security and access other workspaces"""
    
    def test_sql_injection_workspace_bypass(
        self,
        api_client: TestClient,
        workspace_b,
        headers_workspace_a,
    ):
        """TC-005: Attempt SQL injection to bypass workspace filter"""
        # Attempt various SQL injection patterns
        injection_attempts = [
            f"/api/v1/tasks?workspace_id=' OR '1'='1",
            f"/api/v1/tasks/{workspace_b['id']}' OR '1'='1",
            f"/api/v1/tasks?workspace_id={workspace_b['id']}",
            f"/api/v1/tasks?workspace_id[]={workspace_b['id']}",
        ]
        
        for attempt in injection_attempts:
            response = api_client.get(attempt, headers=headers_workspace_a)
            
            # Should either be rejected or return only workspace A data
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Verify no workspace B data leaked
                    for item in data:
                        assert item.get("workspace_id") != workspace_b["id"]
            else:
                # Or request should fail safely
                assert response.status_code in [400, 403, 404]
                
    def test_parameter_tampering_workspace_id(
        self,
        api_client: TestClient,
        workspace_a,
        workspace_b,
        headers_workspace_a,
    ):
        """Attempting to specify workspace_id in request body should be ignored"""
        response = api_client.post(
            "/api/v1/tasks",
            headers=headers_workspace_a,
            json={
                "name": "Tampered Task",
                "workspace_id": workspace_b["id"],  # Attempt to specify wrong workspace
            }
        )
        
        if response.status_code in [200, 201]:
            task = response.json()
            # workspace_id should come from token, not request
            assert task["workspace_id"] == workspace_a["id"]
            assert task["workspace_id"] != workspace_b["id"]
            
    def test_header_injection_workspace_id(
        self,
        api_client: TestClient,
        workspace_b,
        token_a,
    ):
        """Attempting to specify workspace_id in headers should be ignored"""
        headers = {
            "Authorization": f"Bearer {token_a}",
            "X-Workspace-ID": workspace_b["id"],  # Attempt to override
            "Content-Type": "application/json",
        }
        
        response = api_client.get("/api/v1/tasks", headers=headers)
        
        assert response.status_code == 200
        tasks = response.json()
        
        # Should still only see workspace A tasks (from token)
        for task in tasks:
            assert task["workspace_id"] != workspace_b["id"]
