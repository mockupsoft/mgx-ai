# -*- coding: utf-8 -*-
"""Integration tests for Issues management endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.github.issues_manager import IssuesManager, IssueInfo


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_issues_manager():
    """Mock Issues manager."""
    manager = MagicMock(spec=IssuesManager)
    manager.list_issues = AsyncMock(return_value=[
        IssueInfo(
            number=1,
            title="Test Issue",
            body="Test body",
            state="open",
            html_url="https://github.com/test/repo/issues/1",
            created_at="2024-01-01T12:00:00Z",
            updated_at="2024-01-01T12:00:00Z",
            closed_at=None,
            author="test-user",
            labels=["bug"],
            assignees=["test-user"],
            comment_count=0,
        )
    ])
    manager.get_issue = AsyncMock(return_value=IssueInfo(
        number=1,
        title="Test Issue",
        body="Test body",
        state="open",
        html_url="https://github.com/test/repo/issues/1",
        created_at="2024-01-01T12:00:00Z",
        updated_at="2024-01-01T12:00:00Z",
        closed_at=None,
        author="test-user",
        labels=["bug"],
        assignees=["test-user"],
        comment_count=0,
    ))
    manager.create_issue = AsyncMock(return_value=IssueInfo(
        number=2,
        title="New Issue",
        body="New body",
        state="open",
        html_url="https://github.com/test/repo/issues/2",
        created_at="2024-01-01T12:00:00Z",
        updated_at="2024-01-01T12:00:00Z",
        closed_at=None,
        author="test-user",
        labels=[],
        assignees=[],
        comment_count=0,
    ))
    manager.close_issue = AsyncMock(return_value=IssueInfo(
        number=1,
        title="Test Issue",
        body="Test body",
        state="closed",
        html_url="https://github.com/test/repo/issues/1",
        created_at="2024-01-01T12:00:00Z",
        updated_at="2024-01-01T12:00:00Z",
        closed_at="2024-01-01T13:00:00Z",
        author="test-user",
        labels=["bug"],
        assignees=["test-user"],
        comment_count=0,
    ))
    return manager


class TestIssuesManagement:
    """Test Issues management endpoints."""
    
    @patch('backend.routers.issues.get_issues_manager')
    @patch('backend.routers.issues._get_repository_link')
    def test_list_issues(self, mock_get_link, mock_get_manager, client, mock_issues_manager):
        """Test listing issues."""
        mock_get_manager.return_value = mock_issues_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        with patch('backend.routers.issues.get_workspace_context') as mock_ctx, \
             patch('backend.routers.issues.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.get("/api/repositories/test-link-id/issues?state=open")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0
            assert data[0]["number"] == 1
    
    @patch('backend.routers.issues.get_issues_manager')
    @patch('backend.routers.issues._get_repository_link')
    def test_get_issue(self, mock_get_link, mock_get_manager, client, mock_issues_manager):
        """Test getting issue details."""
        mock_get_manager.return_value = mock_issues_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        with patch('backend.routers.issues.get_workspace_context') as mock_ctx, \
             patch('backend.routers.issues.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.get("/api/repositories/test-link-id/issues/1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["number"] == 1
            assert data["title"] == "Test Issue"
    
    @patch('backend.routers.issues.get_issues_manager')
    @patch('backend.routers.issues._get_repository_link')
    def test_create_issue(self, mock_get_link, mock_get_manager, client, mock_issues_manager):
        """Test creating issue."""
        mock_get_manager.return_value = mock_issues_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        with patch('backend.routers.issues.get_workspace_context') as mock_ctx, \
             patch('backend.routers.issues.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.post(
                "/api/repositories/test-link-id/issues",
                json={
                    "title": "New Issue",
                    "body": "New body",
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["number"] == 2
            assert data["title"] == "New Issue"
    
    @patch('backend.routers.issues.get_issues_manager')
    @patch('backend.routers.issues._get_repository_link')
    def test_close_issue(self, mock_get_link, mock_get_manager, client, mock_issues_manager):
        """Test closing issue."""
        mock_get_manager.return_value = mock_issues_manager
        mock_get_link.return_value = MagicMock(
            repo_full_name="test/repo",
            auth_payload={},
        )
        
        with patch('backend.routers.issues.get_workspace_context') as mock_ctx, \
             patch('backend.routers.issues.get_session') as mock_session:
            mock_ctx.return_value = MagicMock(workspace=MagicMock(id="ws-1"))
            mock_session.return_value = MagicMock()
            
            response = client.post("/api/repositories/test-link-id/issues/1/close")
            
            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "closed"

