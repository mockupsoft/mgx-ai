### Backend/tests/fixtures/github_mocks.py
"""GitHub API Mocking Fixtures for E2E Tests.

This module provides comprehensive mock fixtures and utilities for testing GitHub integration
without making actual API calls. Includes mock responses for all GitHub API endpoints,
webhook events, and authentication flows.

Usage:
    from backend.tests.fixtures.github_mocks import (
        setup_github_mocks,
        MockGitHubAPI,
        MockGitRepoManager,
        generate_github_signature
    )
    
    @responses.activate
    def test_git_operation(client, db_session):
        setup_github_mocks(responses, mock_data)
        # ... test code
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock, patch


# Mock Data Classes
@dataclass
class MockRepoInfo:
    """Mock repository information."""
    id: int
    full_name: str
    default_branch: str
    private: bool = False
    html_url: str = None
    description: str = ""
    fork: bool = False
    archived: bool = False
    
    def __post_init__(self):
        if self.html_url is None:
            self.html_url = f"https://github.com/{self.full_name}"


@dataclass
class MockBranch:
    """Mock branch information."""
    name: str
    commit_sha: str
    protected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "commit": {
                "sha": self.commit_sha,
                "url": f"https://api.github.com/repos/test/repo/commits/{self.commit_sha}"
            },
            "protected": self.protected
        }


@dataclass
class MockPullRequest:
    """Mock pull request information."""
    id: int
    number: int
    state: str
    title: str
    body: str
    head_branch: str
    base_branch: str
    head_sha: str
    base_sha: str
    html_url: str
    draft: bool = False
    mergeable: bool = True
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "state": self.state,
            "title": self.title,
            "body": self.body,
            "user": {"login": "mgx-agent", "id": 99999},
            "head": {
                "ref": self.head_branch,
                "sha": self.head_sha,
                "repo": {"full_name": "test-org/test-repo"}
            },
            "base": {
                "ref": self.base_branch,
                "sha": self.base_sha,
                "repo": {"full_name": "test-org/test-repo"}
            },
            "html_url": self.html_url,
            "draft": self.draft,
            "mergeable": self.mergeable,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "labels": [{"name": "automated"}]
        }


@dataclass
class MockCommit:
    """Mock commit information."""
    sha: str
    message: str
    author_name: str
    author_email: str
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha": self.sha,
            "commit": {
                "message": self.message,
                "author": {
                    "name": self.author_name,
                    "email": self.author_email,
                    "date": self.timestamp
                }
            },
            "author": {
                "login": "mgx-agent",
                "id": 99999
            }
        }


# Utility Functions
def generate_github_signature(payload: str, secret: str, delivery_id: str = None) -> Dict[str, str]:
    """Generate GitHub webhook signature headers for testing.
    
    Args:
        payload: Webhook payload as string
        secret: Webhook secret for signature
        delivery_id: Optional delivery ID
        
    Returns:
        Dictionary with webhook headers
    """
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "X-Hub-Signature-256": f"sha256={signature}",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": delivery_id or f"{int(time.time())}-{id(payload) % 100000}",
        "X-GitHub-Hook-ID": "1",
        "Content-Type": "application/json"
    }


def generate_webhook_payload(event_type: str, **kwargs) -> Dict[str, Any]:
    """Generate webhook payload for testing.
    
    Args:
        event_type: Type of webhook event
        **kwargs: Event-specific parameters
        
    Returns:
        Dictionary with webhook payload
    """
    base_payload = {
        "repository": {
            "id": 123456789,
            "name": "test-repo",
            "full_name": "test-org/test-repo",
            "private": False,
            "html_url": "https://github.com/test-org/test-repo"
        },
        "sender": {
            "login": "mgx-agent",
            "id": 99999,
            "type": "Bot"
        }
    }
    
    if event_type == "push":
        base_payload.update({
            "ref": kwargs.get("ref", "refs/heads/mgx/test/run-1"),
            "before": kwargs.get("before", "0000000000000000000000000000000000000000"),
            "after": kwargs.get("after", "abc123def456789012345678901234567890abcd"),
            "pusher": {
                "name": "mgx-agent",
                "email": "agent@mgx.dev"
            },
            "commits": kwargs.get("commits", [
                {
                    "id": "abc123def456789012345678901234567890abcd",
                    "message": kwargs.get("message", "feat: Add new feature"),
                    "timestamp": kwargs.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "author": {
                        "name": "MGX Agent",
                        "email": "agent@mgx.dev"
                    }
                }
            ])
        })
    elif event_type == "pull_request":
        base_payload.update({
            "action": kwargs.get("action", "opened"),
            "number": kwargs.get("number", 42),
            "pull_request": {
                "id": kwargs.get("pr_id", 123456),
                "number": kwargs.get("number", 42),
                "state": kwargs.get("state", "open"),
                "title": kwargs.get("title", "feat: Implement feature"),
                "body": kwargs.get("body", "## Changes\\n- Add new feature"),
                "head": {
                    "ref": kwargs.get("head_branch", "mgx/test/run-1"),
                    "sha": kwargs.get("head_sha", "abc123def456"),
                    "repo": {"full_name": "test-org/test-repo"}
                },
                "base": {
                    "ref": kwargs.get("base_branch", "main"),
                    "sha": kwargs.get("base_sha", "def456abc123"),
                    "repo": {"full_name": "test-org/test-repo"}
                },
                "merged": kwargs.get("merged", False),
                "mergeable": kwargs.get("mergeable", True),
                "html_url": f"https://github.com/test-org/test-repo/pull/{kwargs.get('number', 42)}",
                "created_at": kwargs.get("created_at", datetime.now(timezone.utc).isoformat()),
                "labels": kwargs.get("labels", [{"name": "automated"}])
            }
        })
    
    return base_payload


# Mock GitHub API Classes
class MockGitHubAPI:
    """Mock GitHub API client for testing."""
    
    def __init__(self, token: str):
        self.token = token
        self.call_count = {}
        self.repo_info_cache = {}
        self.pr_cache = {}
        self.branch_cache = {}
    
    def _increment_call(self, method: str):
        """Increment method call counter."""
        self.call_count[method] = self.call_count.get(method, 0) + 1
    
    def get_repo_info(self, repo_full_name: str) -> Dict[str, Any]:
        """Get repository information."""
        self._increment_call('get_repo_info')
        
        if repo_full_name in self.repo_info_cache:
            return self.repo_info_cache[repo_full_name]
        
        repo_id = hash(repo_full_name) % 1000000000
        repo_info = {
            "id": repo_id,
            "node_id": f"MDEwOlJlcG9zaXRvcnk{repo_id}",
            "name": repo_full_name.split('/')[-1],
            "full_name": repo_full_name,
            "private": False,
            "owner": {
                "login": repo_full_name.split('/')[0],
                "id": hash(repo_full_name.split('/')[0]) % 1000000,
                "type": "User"
            },
            "html_url": f"https://github.com/{repo_full_name}",
            "default_branch": "main",
            "description": f"Test repository: {repo_full_name}",
            "fork": False,
            "archived": False,
            "language": "Python",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.repo_info_cache[repo_full_name] = repo_info
        return repo_info
    
    def create_pull_request(self, repo_full_name: str, title: str, body: str, 
                           head: str, base: str) -> str:
        """Create a pull request."""
        self._increment_call('create_pull_request')
        
        pr_number = len(self.pr_cache) + 1
        pr_key = f"{repo_full_name}:{head}:{base}"
        
        pr_info = {
            "id": 1000000 + pr_number,
            "node_id": f"MDExOlB1bGxSZXF1ZXN0{1000000 + pr_number}",
            "number": pr_number,
            "state": "open",
            "title": title,
            "body": body,
            "user": {"login": "mgx-agent", "id": 99999},
            "head": {
                "ref": head,
                "sha": f"sha_{head.replace('/', '_')}",
                "repo": {"full_name": repo_full_name}
            },
            "base": {
                "ref": base,
                "sha": f"sha_{base}",
                "repo": {"full_name": repo_full_name}
            },
            "merged": False,
            "mergeable": True,
            "html_url": f"https://github.com/{repo_full_name}/pull/{pr_number}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.pr_cache[pr_key] = pr_info
        return pr_info["html_url"]
    
    def list_user_repos(self, username: str = None) -> List[Dict[str, Any]]:
        """List user repositories."""
        self._increment_call('list_user_repos')
        
        return [
            {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "test-user/test-repo",
                "private": False,
                "html_url": "https://github.com/test-user/test-repo",
                "description": "Test repository",
                "fork": False,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    
    def list_org_repos(self, org_name: str) -> List[Dict[str, Any]]:
        """List organization repositories."""
        self._increment_call('list_org_repos')
        
        return [
            {
                "id": 111222333,
                "name": "org-repo",
                "full_name": f"{org_name}/org-repo",
                "private": False,
                "html_url": f"https://github.com/{org_name}/org-repo",
                "description": "Organization repository",
                "fork": False
            }
        ]
    
    def get_branches(self, repo_full_name: str) -> List[Dict[str, Any]]:
        """Get repository branches."""
        self._increment_call('get_branches')
        
        # Return default branches
        return [
            {
                "name": "main",
                "commit": {
                    "sha": "main_sha_abc123",
                    "url": f"https://api.github.com/repos/{repo_full_name}/commits/main_sha_abc123"
                },
                "protected": True
            },
            {
                "name": "develop",
                "commit": {
                    "sha": "dev_sha_def456",
                    "url": f"https://api.github.com/repos/{repo_full_name}/commits/dev_sha_def456"
                },
                "protected": False
            }
        ]


class MockGitRepoManager:
    """Mock Git repository manager for testing git operations."""
    
    def __init__(self):
        self.repo_state = {}
        self.commits = []
        self.branches = set(["main", "master"])
        self.current_branch = "main"
        self.cloned_repos = {}
        self.operation_log = []
    
    def _log_operation(self, operation: str, **kwargs):
        """Log git operation."""
        log_entry = {
            "operation": operation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "params": kwargs
        }
        self.operation_log.append(log_entry)
    
    def clone_or_update(self, clone_url: str, dest_dir: Path, default_branch: str) -> Path:
        """Clone or update repository."""
        self._log_operation("clone_or_update", clone_url=clone_url, dest_dir=str(dest_dir))
        
        if dest_dir.exists():
            return dest_dir
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock git structure
        git_dir = dest_dir / ".git"
        git_dir.mkdir()
        
        # Store repo info
        repo_key = dest_dir.name
        self.cloned_repos[repo_key] = {
            "clone_url": clone_url,
            "dest_dir": str(dest_dir),
            "default_branch": default_branch,
            "cloned_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Initialize default branch
        if default_branch not in self.branches:
            self.branches.add(default_branch)
            self.current_branch = default_branch
            
        self.repo_state[default_branch] = {
            "commits": [],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        return dest_dir
    
    def create_branch(self, repo_dir: Path, branch: str, base_branch: str) -> None:
        """Create new branch."""
        self._log_operation("create_branch", branch=branch, base_branch=base_branch)
        
        if branch in self.branches:
            raise Exception(f"Branch {branch} already exists")
        
        self.branches.add(branch)
        self.current_branch = branch
        
        # Initialize branch state
        self.repo_state[branch] = {
            "base_branch": base_branch,
            "base_commit": self.commits[-1]["sha"] if self.commits else "initial_commit",
            "commits": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    def push_branch(self, repo_dir: Path, branch: str) -> Dict[str, Any]:
        """Push branch to remote."""
        self._log_operation("push_branch", branch=branch)
        
        if branch not in self.branches:
            raise Exception(f"Branch {branch} does not exist")
        
        return {
            "pushed": True,
            "branch": branch,
            "remote_url": f"origin/{branch}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def stage_and_commit(self, repo_dir: Path, message: str, files: Optional[List[str]] = None) -> str:
        """Stage and commit changes."""
        self._log_operation("stage_and_commit", message=message, files=files)
        
        commit_sha = f"{len(self.commits):012x}"
        commit = {
            "sha": commit_sha,
            "message": message,
            "files": files or [],
            "branch": self.current_branch,
            "author": "MGX Agent",
            "author_email": "agent@mgx.dev",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "short_sha": commit_sha[:7]
        }
        
        self.commits.append(commit)
        
        # Add to branch state
        if self.current_branch in self.repo_state:
            self.repo_state[self.current_branch]["commits"].append(commit)
        
        return commit_sha
    
    def get_current_commit_sha(self, repo_dir: Path) -> str:
        """Get current commit SHA."""
        self._log_operation("get_current_commit_sha")
        
        if self.commits:
            return self.commits[-1]["sha"]
        return "initial_commit_sha"
    
    def cleanup_branch(self, repo_dir: Path, branch: str, delete_remote: bool = False) -> None:
        """Cleanup branch."""
        self._log_operation("cleanup_branch", branch=branch, delete_remote=delete_remote)
        
        if branch in self.branches:
            self.branches.remove(branch)
            
        if branch in self.repo_state:
            del self.repo_state[branch]


# Mock OAuth Flow
def generate_oauth_token_response(client_id: str, installation_id: Optional[int] = None) -> Dict[str, Any]:
    """Generate OAuth token response."""
    return {
        "access_token": f"gho_{client_id.replace('-', '')[:20]}",
        "token_type": "bearer",
        "scope": "repo,user,admin:org",
        "installation_id": installation_id
    }


# Setup Functions
def setup_github_mocks(responses_mock: Any, mock_data: Optional[Dict[str, Any]] = None) -> None:
    """Setup GitHub API mock responses.
    
    Args:
        responses_mock: responses library mock instance
        mock_data: Optional dictionary with mock data overrides
    """
    mock_data = mock_data or {}
    
    # OAuth token endpoint
    responses_mock.add(
        responses_mock.POST,
        "https://github.com/login/oauth/access_token",
        json=mock_data.get('oauth_token', generate_oauth_token_response("test-client-id")),
        status=200
    )
    
    # Repository info
    repo_info = mock_data.get('repo_info', MockRepoInfo(
        id=123456789,
        full_name="test-user/test-repo"
    ))
    
    responses_mock.add(
        responses_mock.GET,
        r"https://api.github.com/repos/.+",
        json=repo_info.to_dict() if hasattr(repo_info, 'to_dict') else repo_info,
        status=200
    )
    
    # User repositories
    responses_mock.add(
        responses_mock.GET,
        "https://api.github.com/user/repos",
        json=mock_data.get('user_repos', []),
        status=200
    )
    
    # Organization repositories
    responses_mock.add(
        responses_mock.GET,
        r"https://api.github.com/orgs/.+/repos",
        json=mock_data.get('org_repos', []),
        status=200
    )
    
    # Branches
    responses_mock.add(
        responses_mock.GET,
        r"https://api.github.com/repos/.+/branches", 
        json=mock_data.get('branches', []),
        status=200
    )
    
    # Branch protection
    responses_mock.add(
        responses_mock.GET,
        r"https://api.github.com/repos/.+/branches/.+/protection",
        json=mock_data.get('branch_protection', {}),
        status=200
    )
    
    # Create pull request
    pr_response = mock_data.get('pr_response', MockPullRequest(
        id=123456,
        number=42,
        state="open",
        title="Test PR",
        body="Test description",
        head_branch="feature",
        base_branch="main",
        head_sha="head_sha",
        base_sha="base_sha",
        html_url="https://github.com/test-org/test-repo/pull/42"
    ))
    
    responses_mock.add(
        responses_mock.POST,
        r"https://api.github.com/repos/.+/pulls",
        json=pr_response.to_dict() if hasattr(pr_response, 'to_dict') else pr_response,
        status=201
    )
    
    # Create branch ref
    responses_mock.add(
        responses_mock.POST,
        r"https://api.github.com/repos/.+/git/refs",
        json={"ref": "refs/heads/test-branch", "object": {"sha": "abc123"}},
        status=201
    )
    
    # List commits
    responses_mock.add(
        responses_mock.GET,
        r"https://api.github.com/repos/.+/commits",
        json=mock_data.get('commits', []),
        status=200
    )
    
    # Rate limit headers
    responses_mock.add(
        responses_mock.GET,
        r"https://api.github.com/rate_limit",
        json={
            "resources": {
                "core": {
                    "limit": 60,
                    "remaining": 60,
                    "reset": int(time.time()) + 3600
                }
            }
        },
        status=200
    )


# Export commonly used mocks and utilities
__all__ = [
    "generate_github_signature",
    "generate_webhook_payload",
    "setup_github_mocks",
    "MockGitHubAPI",
    "MockGitRepoManager",
    "MockRepoInfo",
    "MockBranch", 
    "MockPullRequest",
    "MockCommit",
    "generate_oauth_token_response"
]