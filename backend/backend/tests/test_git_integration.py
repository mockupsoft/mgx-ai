# -*- coding: utf-8 -*-
"""Git Integration E2E Tests.

Comprehensive testing of GitHub integration, repository management, branch operations,
commit automation, and Git operations without making actual GitHub API calls.

All GitHub API interactions are mocked using responses library to ensure tests are fast,
repeatable, and don't depend on external services.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock, patch

import pytest
import responses
from fastapi.testclient import TestClient

from backend.db.models import Project, RepositoryLink
from backend.db.models.enums import RepositoryLinkStatus, RepositoryProvider
from backend.services.git import GitService, get_git_service, set_git_service
from backend.schemas import EventTypeEnum


@pytest.fixture
def mock_github_token():
    """Mock OAuth token."""
    return "gho_test1234567890abcdef"


@pytest.fixture
def mock_installation_id():
    """Mock GitHub App installation ID."""
    return 12345678


@pytest.fixture
def mock_repo_info():
    """Mock repository information."""
    return {
        "id": 123456789,
        "node_id": "MDEwOlJlcG9zaXRvcnkxMjM0NTY3ODk=",
        "name": "test-repo",
        "full_name": "test-user/test-repo",
        "private": False,
        "owner": {
            "login": "test-user",
            "id": 1,
            "node_id": "MDQ6VXNlcjE=",
            "type": "User"
        },
        "html_url": "https://github.com/test-user/test-repo",
        "default_branch": "main",
        "description": "Test repository for MGX integration",
        "fork": False,
        "archived": False,
        "language": "Python"
    }


@pytest.fixture
def mock_user_repos():
    """Mock list of user repositories."""
    return [
        {
            "id": 123456789,
            "name": "test-repo",
            "full_name": "test-user/test-repo",
            "private": False,
            "html_url": "https://github.com/test-user/test-repo",
            "description": "Test repository",
            "fork": False
        },
        {
            "id": 987654321,
            "name": "another-repo",
            "full_name": "test-user/another-repo",
            "private": False,
            "html_url": "https://github.com/test-user/another-repo",
            "description": "Another test repository",
            "fork": False
        }
    ]


@pytest.fixture
def mock_org_repos():
    """Mock list of organization repositories."""
    return [
        {
            "id": 111222333,
            "name": "org-repo",
            "full_name": "org-name/org-repo",
            "private": False,
            "html_url": "https://github.com/org-name/org-repo",
            "description": "Organization repository",
            "fork": False
        }
    ]


@pytest.fixture
def mock_branches():
    """Mock list of branches."""
    return [
        {
            "name": "main",
            "commit": {
                "sha": "abc123def456",
                "url": "https://api.github.com/repos/test-user/test-repo/commits/abc123def456"
            },
            "protected": True,
            "protection": {
                "required_status_checks": {
                    "enforcement_level": "off"
                }
            }
        },
        {
            "name": "feature-branch",
            "commit": {
                "sha": "def456abc123",
                "url": "https://api.github.com/repos/test-user/test-repo/commits/def456abc123"
            },
            "protected": False
        }
    ]


@pytest.fixture
def mock_branch_protection():
    """Mock branch protection rules."""
    return {
        "url": "https://api.github.com/repos/test-user/test-repo/branches/main/protection",
        "required_status_checks": {
            "strict": True,
            "contexts": ["continuous-integration/travis-ci"],
            "checks": [
                {
                    "context": "continuous-integration/travis-ci",
                    "app_id": 123
                }
            ]
        },
        "required_pull_request_reviews": {
            "url": "https://api.github.com/repos/test-user/test-repo/branches/main/protection/required_pull_request_reviews",
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "required_approving_review_count": 1
        },
        "enforce_admins": {
            "url": "https://api.github.com/repos/test-user/test-repo/branches/main/protection/admin_enforce",
            "enabled": False
        },
        "restrictions": {
            "url": "https://api.github.com/repos/test-user/test-repo/branches/main/protection/restrictions",
            "users": [],
            "teams": [],
            "apps": []
        }
    }


@pytest.fixture
def mock_pr_response():
    """Mock pull request response."""
    return {
        "id": 123456,
        "node_id": "MDExOlB1bGxSZXF1ZXN0MTIzNDU2",
        "number": 42,
        "state": "open",
        "title": "feat: Implement authentication",
        "body": "## Task\n[Link to task]\n\n## Changes\n- Add login endpoint\n- Add JWT token validation",
        "user": {
            "login": "mgx-agent",
            "id": 999
        },
        "head": {
            "ref": "mgx/add-auth/run-1",
            "sha": "abc123def456",
            "repo": {
                "full_name": "test-user/test-repo"
            }
        },
        "base": {
            "ref": "main",
            "sha": "def456abc123",
            "repo": {
                "full_name": "test-user/test-repo"
            }
        },
        "merged": False,
        "mergeable": True,
        "html_url": "https://github.com/test-user/test-repo/pull/42",
        "merged_at": None,
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:30:00Z"
    }


@pytest.fixture
def mock_push_event():
    """Mock GitHub push webhook event."""
    return {
        "ref": "refs/heads/mgx/add-auth/run-1",
        "before": "0000000000000000000000000000000000000000",
        "after": "abc123def456789012345678901234567890abcd",
        "repository": {
            "id": 123456789,
            "name": "test-repo",
            "full_name": "test-user/test-repo",
            "private": False
        },
        "pusher": {
            "name": "mgx-agent",
            "email": "agent@mgx.dev"
        },
        "sender": {
            "login": "mgx-agent",
            "id": 99999
        },
        "commits": [
            {
                "id": "abc123def456789012345678901234567890abcd",
                "message": "feat(auth): Add login endpoint\n\nImplement feature: [Task #123]\n- Add POST /auth/login endpoint\n- Add JWT token generation\n\nGenerated by MGX Agent",
                "timestamp": "2024-01-01T12:00:00Z",
                "url": "https://github.com/test-user/test-repo/commit/abc123def456789012345678901234567890abcd",
                "author": {
                    "name": "MGX Agent",
                    "email": "agent@mgx.dev"
                }
            }
        ]
    }


@pytest.fixture
def mock_pr_event():
    """Mock GitHub pull request webhook event."""
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "id": 123456,
            "number": 42,
            "state": "open",
            "title": "feat: Implement authentication",
            "body": "## Task\n[Link to task]\n\n## Changes\n- Add login endpoint\n- Add JWT token validation\n\nGenerated by MGX Agent\nTask: https://app.mgx.dev/tasks/123",
            "user": {
                "login": "mgx-agent",
                "id": 999
            },
            "head": {
                "ref": "mgx/add-auth/run-1",
                "sha": "abc123def456"
            },
            "base": {
                "ref": "main",
                "sha": "def456abc123"
            },
            "merged": False,
            "mergeable": True,
            "html_url": "https://github.com/test-user/test-repo/pull/42",
            "created_at": "2024-01-01T12:00:00Z"
        },
        "repository": {
            "id": 123456789,
            "name": "test-repo",
            "full_name": "test-user/test-repo"
        },
        "sender": {
            "login": "mgx-agent",
            "id": 99999
        }
    }


class MockGitHubAPI:
    """Mock GitHub API for testing without network calls."""
    
    def __init__(self, token: str):
        self.token = token
        self.call_count = {}
    
    def _increment_call(self, method: str):
        self.call_count[method] = self.call_count.get(method, 0) + 1
    
    def get_repo_info(self, repo_full_name: str):
        self._increment_call('get_repo_info')
        return {
            "id": 123456789,
            "full_name": repo_full_name,
            "default_branch": "main",
            "private": False,
            "html_url": f"https://github.com/{repo_full_name}"
        }
    
    def create_pull_request(self, repo_full_name: str, title: str, body: str, head: str, base: str):
        self._increment_call('create_pull_request')
        return "https://github.com/test-user/test-repo/pull/42"
    
    def list_user_repos(self):
        self._increment_call('list_user_repos')
        return [
            {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "test-user/test-repo",
                "private": False,
                "html_url": "https://github.com/test-user/test-repo"
            }
        ]
    
    def list_org_repos(self, org_name: str):
        self._increment_call('list_org_repos')
        return [
            {
                "id": 111222333,
                "name": "org-repo",
                "full_name": f"{org_name}/org-repo",
                "private": False
            }
        ]
    
    def get_branches(self, repo_full_name: str):
        self._increment_call('get_branches')
        return [
            {
                "name": "main",
                "commit": {"sha": "abc123def456"},
                "protected": True
            }
        ]
    
    def get_branch_protection(self, repo_full_name: str, branch: str):
        self._increment_call('get_branch_protection')
        return {
            "required_status_checks": {"strict": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1}
        }


class MockGitRepoManager:
    """Mock Git repository manager for testing git operations."""
    
    def __init__(self):
        self.repo_state = {}
        self.commits = []
        self.branches = set(["main", "master"])
        self.current_branch = "main"
        self.cloned_repos = {}
    
    def clone_or_update(self, clone_url: str, dest_dir: Path, default_branch: str):
        if dest_dir.exists():
            return dest_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        repo_key = clone_url.split("/")[-1].replace(".git", "")
        self.cloned_repos[repo_key] = {
            "clone_url": clone_url,
            "dest_dir": str(dest_dir),
            "default_branch": default_branch
        }
        return dest_dir
    
    def create_branch(self, repo_dir: Path, branch: str, base_branch: str):
        self.branches.add(branch)
        self.repo_state[branch] = {
            "base_branch": base_branch,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "commits": []
        }
    
    def push_branch(self, repo_dir: Path, branch: str):
        if branch not in self.branches:
            raise Exception(f"Branch {branch} does not exist")
        return {"pushed": True, "branch": branch}
    
    def stage_and_commit(self, repo_dir: Path, message: str, files: Optional[list[str]] = None):
        commit_sha = f"{len(self.commits):012x}"
        commit = {
            "sha": commit_sha,
            "message": message,
            "files": files or [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.commits.append(commit)
        self.repo_state[self.current_branch]["commits"].append(commit)
        return commit_sha
    
    def get_current_commit_sha(self, repo_dir: Path):
        if self.commits:
            return self.commits[-1]["sha"]
        return "initial_commit_sha"
    
    def cleanup_branch(self, repo_dir: Path, branch: str, delete_remote: bool = False):
        if branch in self.branches:
            self.branches.remove(branch)
            if branch in self.repo_state:
                del self.repo_state[branch]


class MockGitService:
    """Mock Git service for testing."""
    
    def __init__(self):
        self.api_calls = []
        self.operations = []
    
    def _log_call(self, method: str, **kwargs):
        self.api_calls.append({"method": method, "args": kwargs})
        self.operations.append(method)
    
    async def fetch_repo_info(self, repo_full_name: str, installation_id: Optional[int] = None, token_override: Optional[str] = None):
        self._log_call('fetch_repo_info', repo_full_name=repo_full_name)
        return {
            "full_name": repo_full_name,
            "default_branch": "main",
            "private": False,
            "html_url": f"https://github.com/{repo_full_name}"
        }
    
    async def ensure_clone(self, repo_full_name: str, default_branch: str, installation_id: Optional[int] = None, token_override: Optional[str] = None):
        self._log_call('ensure_clone', repo_full_name=repo_full_name)
        return Path(f"/tmp/test-repos/{repo_full_name.replace('/', '__')}")
    
    async def create_branch(self, repo_dir: Path, branch: str, base_branch: str):
        self._log_call('create_branch', branch=branch, base_branch=base_branch)
        return True
    
    async def push_branch(self, repo_dir: Path, branch: str):
        self._log_call('push_branch', branch=branch)
        return {"pushed": True, "branch": branch}
    
    async def stage_and_commit(self, repo_dir: Path, message: str, files: Optional[list[str]] = None):
        self._log_call('stage_and_commit', message=message)
        return f"commit_{len(self.api_calls)}"
    
    async def get_current_commit_sha(self, repo_dir: Path):
        self._log_call('get_current_commit_sha')
        return f"sha_{len(self.api_calls)}"
    
    async def create_pull_request(self, repo_full_name: str, title: str, body: str, head: str, base: str, installation_id: Optional[int] = None, token_override: Optional[str] = None):
        self._log_call('create_pull_request', title=title, head=head, base=base)
        return f"https://github.com/{repo_full_name}/pull/1"
    
    async def cleanup_branch(self, repo_dir: Path, branch: str, delete_remote: bool = False):
        self._log_call('cleanup_branch', branch=branch)
        return True


def setup_github_mocks(responses_mock, mock_data):
    """Setup GitHub API mock responses."""
    
    # OAuth token endpoint
    responses_mock.add(
        responses.POST,
        "https://github.com/login/oauth/access_token",
        json={
            "access_token": mock_data.get('mock_github_token'),
            "token_type": "bearer",
            "scope": "repo"
        },
        status=200
    )
    
    # Repository info
    responses_mock.add(
        responses.GET,
        r"https://api.github.com/repos/.+",
        json=mock_data.get('mock_repo_info', {}),
        status=200
    )
    
    # User repositories
    responses_mock.add(
        responses.GET,
        "https://api.github.com/user/repos",
        json=mock_data.get('mock_user_repos', []),
        status=200
    )
    
    # Organization repositories
    responses_mock.add(
        responses.GET,
        r"https://api.github.com/orgs/.+/repos",
        json=mock_data.get('mock_org_repos', []),
        status=200
    )
    
    # Branches
    responses_mock.add(
        responses.GET,
        r"https://api.github.com/repos/.+/branches",
        json=mock_data.get('mock_branches', []),
        status=200
    )
    
    # Branch protection
    responses_mock.add(
        responses.GET,
        r"https://api.github.com/repos/.+/branches/.+/protection",
        json=mock_data.get('mock_branch_protection', {}),
        status=200
    )
    
    # Create pull request
    responses_mock.add(
        responses.POST,
        r"https://api.github.com/repos/.+/pulls",
        json=mock_data.get('mock_pr_response', {}),
        status=201
    )
    
    # Create branch ref
    responses_mock.add(
        responses.POST,
        r"https://api.github.com/repos/.+/git/refs",
        json={"ref": "refs/heads/mgx/test-branch"},
        status=201
    )
    
    # List commits
    responses_mock.add(
        responses.GET,
        r"https://api.github.com/repos/.+/commits",
        json=[{"sha": "abc123", "commit": {"message": "Test commit"}}],
        status=200
    )


class TestGitHubOAuth:
    """Test GitHub OAuth flow."""
    
    @responses.activate
    def test_oauth_flow(self, client, db_session, mock_github_token):
        """Test complete OAuth flow."""
        # Arrange
        setup_github_mocks(responses, {'mock_github_token': mock_github_token})
        
        # Act - OAuth callback
        response = client.post(
            "/api/repositories/oauth/callback",
            json={
                "code": "test_code",
                "state": "test_state"
            }
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == mock_github_token
        assert data["token_type"] == "bearer"
    
    @responses.activate
    def test_token_storage_and_encryption(self, client, db_session, mock_github_token):
        """Test token storage with encryption."""
        setup_github_mocks(responses, {'mock_github_token': mock_github_token})
        
        # Create workspace and project
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Connect repository - token should be stored encrypted
        response = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/test-repo",
                "installation_id": 12345678
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        link = response.json()
        assert link["status"] == "connected"
        assert "auth_payload" in link
        # Verify token is not stored in plain text
        auth_payload = link["auth_payload"]
        if isinstance(auth_payload, dict) and "token" in auth_payload:
            assert auth_payload["token"] != mock_github_token  # Should be encrypted
    
    @responses.activate
    def test_token_refresh(self, client, db_session):
        """Test token refresh before expiry."""
        setup_github_mocks(responses, {
            'mock_github_token': 'refreshed_token_12345'
        })
        
        # Simulate token nearing expiry
        responses.add(
            responses.POST,
            "https://github.com/login/oauth/access_token",
            json={
                "access_token": "refreshed_token_12345",
                "token_type": "bearer",
                "scope": "repo"
            },
            status=200
        )
        
        response = client.post(
            "/api/repositories/oauth/refresh",
            json={"refresh_token": "old_refresh_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "refreshed_token_12345"
    
    @responses.activate
    def test_token_revocation(self, client, db_session, mock_github_token):
        """Test token revocation."""
        setup_github_mocks(responses, {'mock_github_token': mock_github_token})
        
        responses.add(
            responses.DELETE,
            "https://api.github.com/applications/client_id/token",
            status=204
        )
        
        response = client.post(
            "/api/repositories/oauth/revoke",
            json={"token": mock_github_token}
        )
        
        assert response.status_code == 200
        assert response.json()["revoked"] is True
    
    @responses.activate
    def test_rate_limit_respected(self, client, db_session):
        """Test rate limit handling."""
        setup_github_mocks(responses, {})
        
        # Simulate rate limit exceeded
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            status=429,
            headers={
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1234567890"
            }
        )
        
        response = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/test-repo"}
        )
        
        assert response.status_code == 429
        data = response.json()
        assert "rate limit" in data["detail"].lower()


class TestRepositoryDiscovery:
    """Test repository discovery operations."""
    
    @responses.activate
    def test_list_user_repositories(self, client, db_session, mock_user_repos):
        """Test listing user repositories."""
        setup_github_mocks(responses, {'mock_user_repos': mock_user_repos})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.get(
            "/api/repositories/user/repos",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        repos = response.json()
        assert len(repos) == 2
        assert repos[0]["full_name"] == "test-user/test-repo"
        assert repos[1]["full_name"] == "test-user/another-repo"
    
    @responses.activate
    def test_list_organization_repositories(self, client, db_session, mock_org_repos):
        """Test listing organization repositories."""
        setup_github_mocks(responses, {'mock_org_repos': mock_org_repos})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.get(
            "/api/repositories/orgs/test-org/repos",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        repos = response.json()
        assert len(repos) == 1
        assert repos[0]["full_name"] == "org-name/org-repo"
    
    @responses.activate
    def test_search_repositories(self, client, db_session, mock_user_repos):
        """Test searching repositories."""
        setup_github_mocks(responses, {'mock_user_repos': mock_user_repos})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.get(
            "/api/repositories/search",
            params={"q": "test"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0
        assert "search_results" in results
    
    @responses.activate
    def test_pagination_support(self, client, db_session, mock_user_repos):
        """Test pagination support for repository listing."""
        setup_github_mocks(responses, {'mock_user_repos': mock_user_repos * 5})  # Multiple repos
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Test first page
        response = client.get(
            "/api/repositories/user/repos",
            params={"limit": 2, "offset": 0},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        page1 = response.json()
        assert len(page1) <= 2
        
        # Test second page
        response = client.get(
            "/api/repositories/user/repos",
            params={"limit": 2, "offset": 2},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        page2 = response.json()
        assert len(page2) <= 2
        
        # Ensure pages are different (if enough data)
        if len(page1) > 0 and len(page2) > 0:
            assert page1[0]["id"] != page2[0]["id"]


class TestRepositoryManagement:
    """Test repository linking and management."""
    
    @responses.activate
    def test_connect_repository(self, client, db_session, mock_repo_info):
        """Test connecting a repository to a project."""
        setup_github_mocks(responses, {'mock_repo_info': mock_repo_info})
        
        # Create workspace and project
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Connect repository
        response = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/test-repo",
                "installation_id": 12345678
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        link = response.json()
        assert link["repo_full_name"] == "test-user/test-repo"
        assert link["status"] == "connected"
        assert link["provider"] == "github"
    
    @responses.activate
    def test_repository_access_verification(self, client, db_session, mock_repo_info):
        """Test repository access verification."""
        setup_github_mocks(responses, {'mock_repo_info': mock_repo_info})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Test access verification
        response = client.post(
            "/api/repositories/test",
            json={
                "repo_full_name": "test-user/test-repo",
                "installation_id": 12345678
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["repo_full_name"] == "test-user/test-repo"
        assert data["default_branch"] == "main"
    
    @responses.activate
    def test_multiple_repos_per_project(self, client, db_session):
        """Test multiple repositories per project."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Multi-Repo Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Connect first repository
        response1 = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/repo-1"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response1.status_code == 201
        
        # Connect second repository
        response2 = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/repo-2"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response2.status_code == 201
        
        # List repositories for project
        response = client.get(
            f"/api/repositories/?project_id={project['id']}",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response.status_code == 200
        links = response.json()
        assert links["total"] == 2
    
    @responses.activate
    def test_unlink_repository(self, client, db_session, mock_repo_info):
        """Test repository unlinking."""
        setup_github_mocks(responses, {'mock_repo_info': mock_repo_info})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Connect repository
        link = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/test-repo"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Unlink repository
        response = client.delete(
            f"/api/repositories/{link['id']}/disconnect",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disconnected"
        assert data["auth_payload"] == {}
    
    @responses.activate
    def test_relink_repository(self, client, db_session):
        """Test repository re-linking."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Link and unlink
        link = client.post(
            "/api/repositories/connect",
            json={"project_id": project["id"], "repo_full_name": "test-user/test-repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        client.delete(
            f"/api/repositories/{link['id']}/disconnect",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        # Relink with same repo
        response = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/test-repo"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        assert response.json()["repo_full_name"] == "test-user/test-repo"
    
    @responses.activate
    def test_repository_settings_update(self, client, db_session, mock_repo_info):
        """Test repository settings update."""
        setup_github_mocks(responses, {'mock_repo_info': mock_repo_info})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        link = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "test-user/test-repo"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Update repository settings
        response = client.patch(
            f"/api/repositories/{link['id']}",
            json={
                "reference_branch": "develop",
                "set_as_primary": True
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        updated_link = response.json()
        assert updated_link["default_branch"] == "develop"


class TestBranchManagement:
    """Test branch management operations."""
    
    @responses.activate
    def test_get_default_branch(self, client, db_session, mock_repo_info):
        """Test default branch identification."""
        setup_github_mocks(responses, {'mock_repo_info': mock_repo_info})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/test-repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["default_branch"] in ["main", "master"]
    
    @responses.activate
    def test_list_all_branches(self, client, db_session, mock_branches):
        """Test listing all branches."""
        setup_github_mocks(responses, {'mock_branches': mock_branches})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.get(
            "/api/repositories/user/test-user/repos/test-repo/branches",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        branches = response.json()
        assert len(branches) >= 2
        branch_names = [b["name"] for b in branches]
        assert "main" in branch_names
        assert "feature-branch" in branch_names
    
    @responses.activate
    def test_get_branch_protection_rules(self, client, db_session, mock_branch_protection):
        """Test getting branch protection rules."""
        setup_github_mocks(responses, {'mock_branch_protection': mock_branch_protection})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.get(
            "/api/repositories/repos/test-user/test-repo/branches/main/protection",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        protection = response.json()
        assert "required_status_checks" in protection
        assert "required_pull_request_reviews" in protection
    
    @responses.activate
    def test_branch_existence_verification(self, client, db_session):
        """Test branch existence verification."""
        mock_data = {
            "mock_branches": [{"name": "main"}, {"name": "develop"}]
        }
        setup_github_mocks(responses, mock_data)
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Verify existing branch
        response = client.post(
            "/api/repositories/branches/verify",
            json={
                "repo_full_name": "test-user/test-repo",
                "branch": "main"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["branch"] == "main"
        
        # Verify non-existing branch
        response = client.post(
            "/api/repositories/branches/verify",
            json={
                "repo_full_name": "test-user/test-repo",
                "branch": "non-existent"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 404


class TestAutomatedBranchCreation:
    """Test automated branch creation for tasks."""
    
    @responses.activate
    def test_branch_created_for_task(self, client, db_session):
        """Test branch creation for task execution."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        task = client.post(
            "/api/tasks/",
            json={
                "name": "Add authentication",
                "description": "Implement authentication system",
                "project_id": project["id"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Simulate branch creation as part of task execution
        task_slug = "add-authentication"
        branch_name = f"mgx/{task_slug}/run-1"
        
        response = client.post(
            f"/api/tasks/{task['id']}/branches",
            json={"branch_name": branch_name, "base_branch": "main"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["branch_name"].startswith("mgx/")
        assert "run-" in data["branch_name"]
    
    @responses.activate
    def test_branch_name_pattern(self, client, db_session):
        """Test branch name pattern compliance."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        task_name = "Implement user authentication and authorization"
        response = client.post(
            f"/api/projects/{project['id']}/generate-branch-name",
            json={"task_name": task_name},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        branch_name = data["branch_name"]
        
        # Verify pattern: mgx/{sanitized-task-name}/run-{n}
        assert branch_name.startswith("mgx/")
        assert "/run-" in branch_name
        parts = branch_name.split("/")
        assert len(parts) == 3
        assert parts[0] == "mgx"
        assert parts[2].startswith("run-")
    
    @responses.activate
    def test_branch_unique_per_run(self, client, db_session):
        """Test branch uniqueness per task run."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # First run
        response1 = client.get(
            f"/api/projects/{project['id']}/next-branch-name",
            params={"task_name": "Add authentication"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        # Second run (should be different)
        response2 = client.get(
            f"/api/projects/{project['id']}/next-branch-name",
            params={"task_name": "Add authentication"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        branch1 = response1.json()["branch_name"]
        branch2 = response2.json()["branch_name"]
        
        # Should be different (different run numbers)
        assert branch1 != branch2
        assert "run-1" in branch1
        assert "run-2" in branch2


class TestCommitAutomation:
    """Test commit automation operations."""
    
    @responses.activate
    @patch('backend.services.git.GitPythonRepoManager')
    def test_files_staged_correctly(self, mock_repo_manager, client, db_session):
        """Test proper file staging."""
        mock_manager = MockGitRepoManager()
        mock_repo_manager.return_value = mock_manager
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/git/stage-and-commit",
            json={
                "repo_dir": "/tmp/test-repo",
                "message": "Add authentication",
                "files": ["auth.py", "models/user.py"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "commit_sha" in data
        
        # Verify staging was called with correct files
        assert len(mock_manager.commits) > 0
        last_commit = mock_manager.commits[-1]
        assert "auth.py" in last_commit.get("files", [])
    
    @responses.activate
    def test_commit_message_formatting(self, client, db_session):
        """Test commit message includes task reference."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        task_id = "123"
        task_name = "Implement authentication"
        commit_message = f"""feat(auth): Add login endpoint\n\nImplement feature: [Task #{task_id}]\n- Add POST /auth/login endpoint\n- Add JWT token generation\n- Add user model\n\nGenerated by MGX Agent\nTask: https://app.mgx.dev/tasks/{task_id}"""
        
        response = client.post(
            "/api/git/validate-commit-message",
            json={
                "message": commit_message,
                "task_id": task_id,
                "task_name": task_name
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is True
        assert "Task #123" in result["formatted_message"]
        assert "https://app.mgx.dev/tasks/123" in result["formatted_message"]
    
    @responses.activate
    def test_multiple_commits_per_task(self, client, db_session):
        """Test multiple commits for the same task."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        task = client.post(
            "/api/tasks/",
            json={"name": "Add authentication", "description": "Auth system"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # First commit
        response1 = client.post(
            f"/api/tasks/{task['id']}/commits",
            json={"message": "Add login endpoint", "files": ["auth.py"]},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response1.status_code == 201
        
        # Second commit
        response2 = client.post(
            f"/api/tasks/{task['id']}/commits",
            json={"message": "Add JWT validation", "files": ["jwt.py"]},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response2.status_code == 201
        
        # Verify history
        response = client.get(
            f"/api/tasks/{task['id']}/commits",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response.status_code == 200
        commits = response.json()
        assert len(commits) == 2
        assert commits[0]["message"] == "Add JWT validation"
        assert commits[1]["message"] == "Add login endpoint"
    
    @responses.activate
    def test_commit_linked_to_task_run(self, client, db_session):
        """Test commit linkage to task run."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        task = client.post(
            "/api/tasks/",
            json={"name": "Add authentication", "project_id": project["id"]},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        run = client.post(
            f"/api/tasks/{task['id']}/runs",
            json={"description": "Test run"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Create commit linked to run
        response = client.post(
            f"/api/runs/{run['id']}/commits",
            json={
                "message": "Add authentication",
                "task_id": task["id"],
                "files": ["auth.py"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        commit = response.json()
        assert commit["run_id"] == run["id"]
        assert commit["task_id"] == task["id"]


class TestPushOperations:
    """Test push operations to GitHub."""
    
    @responses.activate
    @patch('backend.services.git.GitPythonRepoManager')
    def test_branch_pushed_successfully(self, mock_repo_manager, client, db_session):
        """Test successful branch push."""
        mock_manager = MockGitRepoManager()
        mock_repo_manager.return_value = mock_manager
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            json={"ref": "refs/heads/test-branch"},
            status=201
        )
        
        response = client.post(
            "/api/git/push",
            json={
                "repo_dir": "/tmp/test-repo",
                "branch_name": "test-branch",
                "force": False
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["pushed"] is True
        assert data["branch"] == "test-branch"
    
    @responses.activate
    def push_with_multiple_commits(self, client, db_session):
        """Test push with multiple commits."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+/commits",
            json=[
                {"sha": "commit1", "commit": {"message": "First commit"}},
                {"sha": "commit2", "commit": {"message": "Second commit"}},
                {"sha": "commit3", "commit": {"message": "Third commit"}}
            ],
            status=200
        )
        
        response = client.post(
            "/api/git/push",
            json={
                "repo_full_name": "test-user/test-repo",
                "branch_name": "feature-branch",
                "num_commits": 3
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["commits_pushed"] == 3
    
    @responses.activate
    def test_push_conflict_handling(self, client, db_session):
        """Test push conflict detection and handling."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Simulate conflict error
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            status=409,  # Conflict
            json={
                "message": "Update is not a fast forward",
                "documentation_url": "https://docs.github.com/rest/git/refs"
            }
        )
        
        response = client.post(
            "/api/git/push",
            json={
                "repo_dir": "/tmp/test-repo",
                "branch_name": "conflict-branch"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 409
        data = response.json()
        assert "conflict" in data["detail"].lower() or "fast forward" in data["detail"].lower()
    
    @responses.activate
    def test_auth_error_during_push(self, client, db_session):
        """Test authentication error during push."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Simulate auth error
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            status=401,  # Unauthorized
            json={"message": "Bad credentials"}
        )
        
        response = client.post(
            "/api/git/push",
            json={
                "repo_dir": "/tmp/test-repo",
                "branch_name": "test-branch"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "authentication" in data["detail"].lower() or "credentials" in data["detail"].lower()
    
    @responses.activate
    def test_rate_limit_during_push(self, client, db_session):
        """Test rate limit handling during push."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Simulate rate limit
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            status=429,
            headers={
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "0"
            }
        )
        
        response = client.post(
            "/api/git/push",
            json={
                "repo_dir": "/tmp/test-repo",
                "branch_name": "test-branch"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 429


class TestPullRequestCreation:
    """Test pull request creation and management."""
    
    @responses.activate
    def test_pr_created_successfully(self, client, db_session, mock_pr_response):
        """Test successful PR creation."""
        setup_github_mocks(responses, {'mock_pr_response': mock_pr_response})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/pulls",
            json={
                "repo_full_name": "test-user/test-repo",
                "title": "feat: Implement authentication",
                "body": "## Task\\n[Link to task]\\n\\n## Changes\\n- Add login endpoint\\n- Add JWT validation",
                "head": "mgx/add-auth/run-1",
                "base": "main"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        pr = response.json()
        assert "html_url" in pr
        assert pr["number"] == 42
        assert pr["state"] == "open"
    
    @responses.activate
    def test_pr_title_includes_task(self, client, db_session):
        """Test PR title includes task reference."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        task = client.post(
            "/api/tasks/",
            json={"name": "Add authentication", "description": "Auth system"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        response = client.post(
            "/api/tasks/{task_id}/pull-request".format(task_id=task["id"]),
            json={
                "branch_name": "mgx/add-auth/run-1",
                "base_branch": "main"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        pr = response.json()
        assert "#" + task["id"] in pr["title"]
    
    @responses.activate
    def test_pr_body_includes_context(self, client, db_session, mock_pr_response):
        """Test PR body includes proper context."""
        setup_github_mocks(responses, {'mock_pr_response': mock_pr_response})
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/pulls",
            json={
                "repo_full_name": "test-user/test-repo",
                "title": "feat: Add authentication",
                "body": "## Task\\n[Link to task]\\n\\n## Changes\\n- Add login endpoint\\n- Add JWT validation\\n- Add password hashing\\n\\n## Testing\\n- Unit tests added\\n- Integration tests added\\n\\nGenerated by MGX Agent",
                "head": "feature-branch",
                "base": "main"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        pr = response.json()
        
        # Verify comprehensive PR body
        pr_body = pr.get("body", "")
        assert "## Task" in pr_body
        assert "## Changes" in pr_body
        assert "## Testing" in pr_body
        assert "Generated by MGX Agent" in pr_body
    
    @responses.activate
    def test_pr_labels_assignees_and_reviewers(self, client, db_session):
        """Test PR labels, assignees, and reviewers."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/issues/.+/labels",
            json=[{"name": "enhancement"}, {"name": "automated"}],
            status=200
        )
        
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/pulls/.+/requested_reviewers",
            json={"message": "Reviewers assigned successfully"},
            status=201
        )
        
        response = client.post(
            "/api/repositories/pulls",
            json={
                "repo_full_name": "test-user/test-repo",
                "title": "feat: Add feature",
                "body": "Feature description",
                "head": "feature-branch",
                "base": "main",
                "labels": ["enhancement", "automated"],
                "assignees": ["mgx-agent"],
                "reviewers": ["team-lead", "security-team"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
    
    @responses.activate
    def test_pr_draft_mode(self, client, db_session):
        """Test PR draft mode creation."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        mock_draft_pr = mock_pr_response.copy()
        mock_draft_pr["draft"] = True
        
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/pulls",
            json=mock_draft_pr,
            status=201
        )
        
        response = client.post(
            "/api/repositories/pulls",
            json={
                "repo_full_name": "test-user/test-repo",
                "title": "feat: Work in progress",
                "body": "WIP: This is a draft PR",
                "head": "wip-branch",
                "base": "main",
                "draft": True
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 201
        pr = response.json()
        assert pr.get("draft") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"]