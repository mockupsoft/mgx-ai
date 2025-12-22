# -*- coding: utf-8 -*-
"""Integration tests for PR management endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.github.pr_manager import PRManager, PullRequestInfo


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_pr_manager():
    """Mock PR manager."""
    manager = MagicMock(spec=PRManager)
    manager.list_pull_requests = AsyncMock(return_value=[
        PullRequestInfo(
            number=1,
            title="Test PR",
            body="Test body",
            state="open",
            head_branch="feature/test",
            base_branch="main",
            head_sha="abc123",
            base_sha="def456",
            html_url="https://github.com/test/repo/pull/1",
            created_at="2024-01-01T12:00:00Z",
            updated_at="2024-01-01T12:00:00Z",
            merged_at=None,
            mergeable=True,
            mergeable_state="clean",
            author="test-user",
            labels=["bug"],
            review_count=0,
            comment_count=0,
        )
    ])
    manager.get_pull_request = AsyncMock(return_value=PullRequestInfo(
        number=1,
        title="Test PR",
        body="Test body",
        state="open",
        head_branch="feature/test",
        base_branch="main",
        head_sha="abc123",
        base_sha="def456",
        html_url="https://github.com/test/repo/pull/1",
        created_at="2024-01-01T12:00:00Z",
        updated_at="2024-01-01T12:00:00Z",
        merged_at=None,
        mergeable=True,
        mergeable_state="clean",
        author="test-user",
        labels=["bug"],
        review_count=0,
        comment_count=0,
    ))
    manager.merge_pull_request = AsyncMock(return_value={
        "merged": True,
        "message": "Merged successfully",
        "sha": "merged123",
    })
    return manager


class TestPRManagement:
    """Test PR management endpoints."""
    
    @patch('backend.routers.pull_requests.get_pr_manager')
    @patch('backend.routers.pull_requests._get_repository_link')
    def test_list_pull_requests(self, mock_get_link, mock_get_manager, client, mock_pr_manager):
        """Test listing pull requests."""
        mock_get_manager.return_value = mock_pr_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        # Mock workspace context and session
        with patch('backend.routers.pull_requests.get_workspace_context') as mock_ctx, \
             patch('backend.routers.pull_requests.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.get("/api/repositories/test-link-id/pull-requests?state=open")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0
            assert data[0]["number"] == 1
    
    @patch('backend.routers.pull_requests.get_pr_manager')
    @patch('backend.routers.pull_requests._get_repository_link')
    def test_get_pull_request(self, mock_get_link, mock_get_manager, client, mock_pr_manager):
        """Test getting pull request details."""
        mock_get_manager.return_value = mock_pr_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        with patch('backend.routers.pull_requests.get_workspace_context') as mock_ctx, \
             patch('backend.routers.pull_requests.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.get("/api/repositories/test-link-id/pull-requests/1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["number"] == 1
            assert data["title"] == "Test PR"
    
    @patch('backend.routers.pull_requests.get_pr_manager')
    @patch('backend.routers.pull_requests._get_repository_link')
    def test_merge_pull_request(self, mock_get_link, mock_get_manager, client, mock_pr_manager):
        """Test merging pull request."""
        mock_get_manager.return_value = mock_pr_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        with patch('backend.routers.pull_requests.get_workspace_context') as mock_ctx, \
             patch('backend.routers.pull_requests.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.post(
                "/api/repositories/test-link-id/pull-requests/1/merge?merge_method=merge"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["merged"] is True

