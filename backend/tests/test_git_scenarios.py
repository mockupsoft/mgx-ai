# -*- coding: utf-8 -*-
"""Git Integration E2E Scenario Tests.

Comprehensive end-to-end workflow testing covering complete GitHub integration scenarios
from OAuth through webhook processing. Tests realistic user workflows and edge cases.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import Mock, patch, AsyncMock

import pytest
import responses
from fastapi.testclient import TestClient

from backend.tests.fixtures.github_mocks import (
    generate_github_signature,
    generate_webhook_payload,
    MockGitHubAPI,
    MockGitRepoManager
)
from backend.schemas import EventTypeEnum


@pytest.fixture
def complete_workflow_data():
    """Complete workflow test data."""
    return {
        "workspace": {
            "name": "Test Workspace",
            "slug": "test-workspace"
        },
        "project": {
            "name": "E2E Test Project",
            "description": "Complete GitHub integration test"
        },
        "task": {
            "name": "Implement GitHub Integration",
            "description": "Add comprehensive GitHub integration support"
        },
        "repository": {
            "full_name": "test-org/test-repo",
            "default_branch": "main"
        }
    }


class TestCompleteGitWorkflow:
    """Test complete Git workflow from start to finish."""
    
    @responses.activate
    def test_complete_workflow_success(self, client, db_session, complete_workflow_data):
        """Test complete workflow from OAuth to merge."""
        # STEP 1: OAuth Flow
        responses.add(
            responses.POST,
            "https://github.com/login/oauth/access_token",
            json={"access_token": "gho_test_token_123", "token_type": "bearer"},
            status=200
        )
        
        # STEP 2: Connect Repository
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/test-org/test-repo",
            json={
                "id": 123456789,
                "full_name": "test-org/test-repo",
                "default_branch": "main",
                "private": False
            },
            status=200
        )
        
        workspace = client.post("/api/workspaces/", json=complete_workflow_data["workspace"]).json()
        project = client.post(
            "/api/projects/",
            json=complete_workflow_data["project"],
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Connect repository
        link_response = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": complete_workflow_data["repository"]["full_name"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert link_response.status_code == 201
        
        # STEP 3: Create Task
        task_response = client.post(
            "/api/tasks/",
            json={**complete_workflow_data["task"], "project_id": project["id"]},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert task_response.status_code == 201
        task = task_response.json()
        
        # STEP 4: Create Branch
        branch_response = client.post(
            f"/api/tasks/{task['id']}/branches",
            json={
                "task_name": task["name"],
                "base_branch": "main"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert branch_response.status_code in [200, 201]
        branch = branch_response.json()
        assert branch["branch_name"].startswith("mgx/")
        
        # STEP 5: Create Commit
        commit_response = client.post(
            f"/api/tasks/{task['id']}/commits",
            json={
                "message": "feat: Add GitHub integration\\n\\n[task #123] Implementation",
                "files": ["github.py", "tests/test_github.py"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert commit_response.status_code == 201
        commit = commit_response.json()
        assert "commit_sha" in commit
        
        # STEP 6: Push Branch
        push_response = client.post(
            "/api/git/push",
            json={"branch_name": branch["branch_name"]},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert push_response.status_code == 200
        
        # STEP 7: Create Pull Request
        pr_response = client.post(
            f"/api/tasks/{task['id']}/pull-request",
            json={
                "title": "feat: #{task['id']} GitHub Integration",
                "body": "Complete implementation",
                "branch_name": branch["branch_name"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert pr_response.status_code == 201
        pr = pr_response.json()
        assert pr["pr_number"] > 0
        
        # STEP 8: Webhook Processing Simulation
        webhook_payload = {
            "ref": f"refs/heads/{branch['branch_name']}",
            "after": commit["commit_sha"],
            "repository": {"full_name": "test-org/test-repo"}
        }
        
        # STEP 9: Verify Metadata Display
        task_detail = client.get(
            f"/api/tasks/{task['id']}",
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        assert "git_metadata" in task_detail
        assert task_detail["git_metadata"]["branch"] == branch["branch_name"]
        assert task_detail["git_metadata"]["commit_sha"] == commit["commit_sha"]
        assert task_detail["git_metadata"]["pr_number"] == pr["pr_number"]
    
    @responses.activate
    def test_branch_exists_on_github(self, client, db_session):
        """Verify branch was created on GitHub."""
        setup_github_mocks(responses, {
            'mock_branches': [
                {"name": "main", "protected": True},
                {"name": "mgx/test-feature/run-1", "protected": False}
            ]
        })
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Verify branch exists
        response = client.get(
            "/api/repositories/user/test-org/repos/test-repo/branches",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        branches = response.json()
        assert any(b["name"] == "mgx/test-feature/run-1" for b in branches)
    
    @responses.activate
    def test_commit_visible_on_github(self, client, db_session):
        """Verify commit is visible on GitHub."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+/commits",
            json=[
                {"sha": "abc123", "commit": {"message": "Test commit"}},
                {"sha": "def456", "commit": {"message": "Another commit"}}
            ],
            status=200
        )
        
        # Check commits
        response = client.get(
            "/api/repositories/user/test-org/repos/test-repo/commits",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        commits = response.json()
        assert len(commits) >= 2
    
    @responses.activate
    def test_pr_created_on_github(self, client, db_session):
        """Verify PR was created on GitHub."""
        mock_pr = {
            "id": 999999,
            "number": 99,
            "state": "open",
            "title": "feat: Test PR",
            "html_url": "https://github.com/test-org/test-repo/pull/99"
        }
        
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+/pulls",
            json=[mock_pr],
            status=200
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.get(
            "/api/repositories/user/test-org/repos/test-repo/pulls",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        prs = response.json()
        assert any(pr["number"] == 99 for pr in prs)
    
    @responses.activate
    def test_metadata_accuate(self, client, db_session, complete_workflow_data):
        """Test that all metadata is accurate across the workflow."""
        workspace = client.post("/api/workspaces/", json=complete_workflow_data["workspace"]).json()
        project = client.post(
            "/api/projects/",
            json=complete_workflow_data["project"],
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Create and connect repository
        link_response = client.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": complete_workflow_data["repository"]["full_name"]
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        link = link_response.json()
        
        # Verify metadata accuracy
        assert link["repo_full_name"] == complete_workflow_data["repository"]["full_name"]
        assert link["default_branch"] == complete_workflow_data["repository"]["default_branch"]
        assert link["provider"] == "github"


class TestErrorRecoveryScenarios:
    """Test error recovery and rollback scenarios."""
    
    @responses.activate
    def test_404_error_handled(self, client, db_session):
        """Test 404 error handling during API calls."""
        # Simulate repository not found
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            status=404,
            json={"message": "Not Found"}
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "non-existent/repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @responses.activate
    def test_403_error_shows_clear_message(self, client, db_session):
        """Test 403 error with clear message."""
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            status=403,
            json={"message": "Forbidden"}
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/private-repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 403
        assert "access denied" in response.json()["detail"].lower()
    
    @responses.activate
    def test_timeout_handled_gracefully(self, client, db_session):
        """Test network timeout handling."""
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            status=504,  # Gateway timeout
            json={"message": "Timeout"}
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code in [502, 504]
    
    @responses.activate
    def test_auth_expired_reauthenticate(self, client, db_session):
        """Test expired authentication triggers re-authentication."""
        # Old token returns 401
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            status=401,
            json={"message": "Bad credentials"}
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/test-repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 401
        # Should trigger re-authentication flow
        assert "re-authenticate" in response.json()["detail"] or "expired" in response.json()["detail"]
    
    @responses.activate
    def test_retry_mechanism_works(self, client, db_session):
        """Test retry mechanism on transient errors."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # First call fails with 503, second succeeds
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            status=503,  # Service unavailable
            json={"message": "Service temporarily unavailable"}
        )
        
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            json={
                "id": 123456789,
                "full_name": "test-user/test-repo",
                "default_branch": "main"
            },
            status=200
        )
        
        # First attempt
        response1 = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/test-repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response1.status_code == 503
        
        # Retry (should succeed)
        response2 = client.post(
            "/api/repositories/test",
            json={"repo_full_name": "test-user/test-repo"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response2.status_code == 200


class TestConcurrencyAndTimer:
    """Test concurrent operations and timing scenarios."""
    
    @patch('backend.services.git.GitPythonRepoManager')
    def test_concurrent_branches_creates_unique(self, mock_repo_manager, client, db_session):
        """Test concurrent branch creation results in unique names."""
        mock_manager = MockGitRepoManager()
        mock_repo_manager.return_value = mock_manager
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Concurrent Test Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Create multiple branches concurrently
        branches_created = []
        for i in range(5):
            response = client.post(
                f"/api/projects/{project['id']}/generate-branch-name",
                json={"task_name": f"Feature {i}"},
                headers={"X-Workspace-Id": workspace["id"]}
            )
            if response.status_code == 200:
                branches_created.append(response.json()["branch_name"])
        
        # All branch names should be unique
        assert len(set(branches_created)) == len(branches_created)
    
    def test_timeline_events_ordered_correctly(self, client, db_session):
        """Test timeline events are in correct chronological order."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Create events
        events = []
        for event_type in ["branch_created", "commit_pushed", "pr_opened"]:
            response = client.post(
                "/api/timeline/events",
                json={
                    "event_type": event_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                headers={"X-Workspace-Id": workspace["id"]}
            )
            if response.status_code == 201:
                events.append(response.json())
        
        # Verify ordering
        timeline_response = client.get(
            "/api/timeline",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert timeline_response.status_code == 200
        
        timeline = timeline_response.json()
        timestamps = [event["timestamp"] for event in timeline]
        assert timestamps == sorted(timestamps)
    
    @pytest.mark.asyncio
    async def test_webhook_flush_on_high_volume(self, client, db_session):
        """Test webhook processing under high volume."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Send multiple webhooks rapidly
        webhook_secret = "test_webhook_secret_12345"
        tasks = []
        
        for i in range(50):  # High volume
            payload = json.dumps({
                "ref": f"refs/heads/branch{i}",
                "after": f"sha{i:05d}",
                "repository": {"full_name": "test-repo"}
            })
            
            signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": f"delivery-{i}",
                "Content-Type": "application/json"
            }
            
            task = client.post("/api/webhooks/github", data=payload, headers=headers)
            tasks.append(task)
        
        # All should succeed
        assert all(task.status_code == 200 for task in tasks)
    
    def test_event_filtering_by_type(self, client, db_session):
        """Test timeline event filtering by type."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Create different event types
        event_types = ["push", "pr_open", "commit", "review"]
        for event_type in event_types:
            client.post(
                "/api/timeline/events",
                json={
                    "event_type": event_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                headers={"X-Workspace-Id": workspace["id"]}
            )
        
        # Filter by event type
        response = client.get(
            "/api/timeline?event_type=push",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response.status_code == 200
        
        filtered_events = response.json()
        assert all(event["event_type"] == "push" for event in filtered_events)
    
    def test_event_filtering_by_branch(self, client, db_session):
        """Test timeline event filtering by branch."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Create events for different branches
        branches = ["main", "develop", "feature-1", "feature-2"]
        for branch in branches:
            client.post(
                "/api/timeline/events",
                json={
                    "event_type": "push",
                    "branch": branch,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                headers={"X-Workspace-Id": workspace["id"]}
            )
        
        # Filter by branch
        response = client.get(
            "/api/timeline?branch=develop",
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response.status_code == 200
        
        filtered_events = response.json()
        assert all(event["branch"] == "develop" for event in filtered_events)


class TestMergeConflictResolution:
    """Test merge conflict detection and resolution."""
    
    @responses.activate
    def test_conflict_detected_on_push(self, client, db_session):
        """Test conflict detection during push."""
        # Simulate conflict
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            status=409,
            json={"message": "Update is not a fast forward"}
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/git/push",
            json={"branch_name": "conflict-branch"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 409
        data = response.json()
        assert "conflict" in data["detail"] or "fast forward" in data["detail"]
    
    @responses.activate
    def test_conflict_files_identified(self, client, db_session):
        """Test identification of conflicted files."""
        conflicted_files = ["README.md", "src/main.py", "tests/test_main.py"]
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        response = client.post(
            "/api/git/conflicts",
            json={
                "conflicted_files": conflicted_files,
                "branch_name": "feature-branch"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["conflicted_files"] == conflicted_files
        assert "manual_merge" in data
    
    @responses.activate
    def test_task_marked_needs_review(self, client, db_session):
        """Test task marked as needs_review on conflict."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        task_response = client.post(
            "/api/tasks/",
            json={"name": "Feature with conflicts", "description": "Will have conflicts"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert task_response.status_code == 201
        task = task_response.json()
        
        # Simulate conflict resolution
        response = client.patch(
            f"/api/tasks/{task['id']}",
            json={"status": "needs_review", "conflict_detected": True},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response.status_code == 200
        
        updated_task = response.json()
        assert updated_task["status"] == "needs_review"
        assert updated_task["conflict_detected"] is True
    
    @responses.activate
    def test_retry_after_resolution(self, client, db_session):
        """Test retry after conflict resolution."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # First attempt fails
        responses.add(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            status=409
        )
        
        response1 = client.post(
            "/api/git/push",
            json={"branch_name": "retry-branch"},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response1.status_code == 409
        
        # After resolution, retry succeeds
        responses.replace(
            responses.POST,
            r"https://api.github.com/repos/.+/git/refs",
            json={"ref": "refs/heads/retry-branch"},
            status=201
        )
        
        response2 = client.post(
            "/api/git/push",
            json={"branch_name": "retry-branch", "retry": True},
            headers={"X-Workspace-Id": workspace["id"]}
        )
        assert response2.status_code == 200


class TestPerformanceScenarios:
    """Test performance and scaling scenarios."""
    
    def test_large_commit_payload_handled(self, client, db_session):
        """Test handling of large commit payloads."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Create a commit with many files
        large_commit = {
            "message": "feat: Large feature implementation",
            "files": [f"file_{i}.py" for i in range(100)]  # 100 files
        }
        
        response = client.post(
            "/api/git/stage-and-commit",
            json={
                **large_commit,
                "repo_dir": "/tmp/test-repo"
            },
            headers={"X-Workspace-Id": workspace["id"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["file_count"] == 100
    
    def test_multiple_tasks_same_repo(self, client, db_session):
        """Test multiple tasks for the same repository."""
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        project = client.post(
            "/api/projects/",
            json={"name": "Multi-task Project"},
            headers={"X-Workspace-Id": workspace["id"]}
        ).json()
        
        # Create multiple tasks
        tasks = []
        for i in range(10):
            response = client.post(
                "/api/tasks/",
                json={
                    "name": f"Task {i}",
                    "description": f"Implementation {i}",
                    "project_id": project["id"]
                },
                headers={"X-Workspace-Id": workspace["id"]}
            )
            if response.status_code == 201:
                tasks.append(response.json())
        
        # All tasks should have unique IDs and branch names
        assert len(tasks) == 10
        branch_names = []
        for task in tasks:
            response = client.get(
                f"/api/tasks/{task['id']}/branch-name",
                headers={"X-Workspace-Id": workspace["id"]}
            )
            if response.status_code == 200:
                branch_name = response.json()["branch_name"]
                branch_names.append(branch_name)
        
        # All branch names should be unique
        assert len(set(branch_names)) == len(branch_names)
    
    @responses.activate
    def test_rate_limit_respected_under_load(self, client, db_session):
        """Test rate limit handling under high load."""
        # Set rate limit headers
        responses.add(
            responses.GET,
            r"https://api.github.com/repos/.+",
            json={"id": 123, "full_name": "test/repo"},
            status=200,
            headers={
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "5",
                "X-RateLimit-Reset": str(int(time.time()) + 3600)
            }
        )
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Make multiple requests
        responses = []
        for i in range(10):
            response = client.post(
                "/api/repositories/test",
                json={"repo_full_name": f"test/repo-{i}"},
                headers={"X-Workspace-Id": workspace["id"]}
            )
            responses.append(response.status_code)
        
        # After rate limit is hit, should get 429
        assert 429 in responses or all(status == 200 for status in responses)
    
    def test_memory_efficient_webhook_processing(self, client, db_session):
        """Test memory efficiency during webhook processing."""
        import tracemalloc
        
        tracemalloc.start()
        
        workspace = client.post("/api/workspaces/", json={"name": "Test Workspace"}).json()
        
        # Process many webhooks
        webhook_secret = "test_webhook_secret_12345"
        snapshot_before = tracemalloc.take_snapshot()
        
        for i in range(100):
            payload = json.dumps({
                "ref": f"refs/heads/branch{i}",
                "after": f"sha{i:05d}",
                "repository": {"full_name": "test-repo"}
            })
            
            signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": f"delivery-{i}",
                "Content-Type": "application/json"
            }
            
            response = client.post("/api/webhooks/github", data=payload, headers=headers)
            assert response.status_code == 200
        
        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')
        
        # Memory growth should be reasonable
        total_memory_increase = sum(stat.size_diff for stat in top_stats)
        assert total_memory_increase < 100 * 1024 * 1024  # < 100MB increase
        
        tracemalloc.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])