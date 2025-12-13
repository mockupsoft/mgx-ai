# -*- coding: utf-8 -*-
"""
Integration tests for Git-aware task execution.

Tests:
- Git branch creation during task execution
- Commit and push after approval
- PR creation
- Git metadata persistence
- Error handling and cleanup
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import Task, TaskRun, Project, Workspace
from backend.db.models.enums import TaskStatus, RunStatus
from backend.services.executor import TaskExecutor
from backend.services.git import GitService, GitServiceError, RepoInfo
from backend.services.team_provider import MGXTeamProvider
from backend.services.events import EventBroadcaster


@pytest.fixture
def mock_git_service():
    """Mock GitService for testing."""
    service = Mock(spec=GitService)
    service.ensure_clone = AsyncMock(return_value=Path("/tmp/test-repo"))
    service.create_branch = AsyncMock()
    service.stage_and_commit = AsyncMock(return_value="abc123def456")
    service.push_branch = AsyncMock()
    service.create_pull_request = AsyncMock(return_value="https://github.com/owner/repo/pull/123")
    service.get_current_commit_sha = AsyncMock(return_value="abc123def456")
    service.cleanup_branch = AsyncMock()
    return service


@pytest.fixture
def mock_team_provider():
    """Mock MGXTeamProvider for testing."""
    provider = Mock(spec=MGXTeamProvider)
    team = AsyncMock()
    team.run = AsyncMock(return_value={"status": "success", "output": "Task completed"})
    provider.get_team = AsyncMock(return_value=team)
    return provider


@pytest.fixture
def event_broadcaster():
    """Create a real event broadcaster for testing."""
    return EventBroadcaster()


@pytest.fixture
def executor(mock_git_service, mock_team_provider):
    """Create TaskExecutor with mocked dependencies."""
    return TaskExecutor(
        team_provider=mock_team_provider,
        git_service=mock_git_service,
    )


@pytest.mark.asyncio
class TestGitAwareExecution:
    """Test git-aware task execution."""

    async def test_execute_with_git_branch_creation(self, executor, mock_git_service):
        """Test that a git branch is created after plan generation."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
            "run_branch_prefix": "mgx",
        }

        # Start execution in background
        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        # Wait a bit for plan generation
        await asyncio.sleep(0.2)

        # Approve the plan
        await executor.approve_plan("run_456", approved=True)

        # Wait for execution to complete
        result = await task

        # Verify git operations were called
        mock_git_service.ensure_clone.assert_called_once_with(
            repo_full_name="owner/repo",
            default_branch="main",
        )
        mock_git_service.create_branch.assert_called_once()
        
        call_args = mock_git_service.create_branch.call_args
        assert call_args[1]["branch"].startswith("mgx/test-task/run-")
        assert call_args[1]["base_branch"] == "main"

    async def test_execute_with_git_commit_and_push(self, executor, mock_git_service):
        """Test that changes are committed and pushed after execution."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
            "run_branch_prefix": "mgx",
            "commit_template": "MGX: {task_name} - Run #{run_number}",
        }

        # Start execution in background
        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        # Wait and approve
        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        result = await task

        # Verify commit and push were called
        mock_git_service.stage_and_commit.assert_called_once()
        commit_call = mock_git_service.stage_and_commit.call_args
        assert "MGX: test-task - Run #1" == commit_call[1]["message"]

        mock_git_service.push_branch.assert_called_once()

    async def test_execute_with_pr_creation(self, executor, mock_git_service):
        """Test that a PR is created after successful push."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
            "run_branch_prefix": "mgx",
        }

        # Start execution in background
        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        # Wait and approve
        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        result = await task

        # Verify PR was created
        mock_git_service.create_pull_request.assert_called_once()
        pr_call = mock_git_service.create_pull_request.call_args
        assert pr_call[1]["repo_full_name"] == "owner/repo"
        assert pr_call[1]["title"] == "MGX: test-task - Run #1"
        assert pr_call[1]["base"] == "main"

        # Verify result includes git metadata
        assert result["status"] == "completed"
        assert result["git_metadata"]["pr_url"] == "https://github.com/owner/repo/pull/123"
        assert result["git_metadata"]["commit_sha"] == "abc123def456"

    async def test_execute_without_git_config(self, executor, mock_git_service):
        """Test that execution works without git config."""
        # No project_config provided
        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
            )
        )

        # Wait and approve
        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        result = await task

        # Verify git operations were NOT called
        mock_git_service.ensure_clone.assert_not_called()
        mock_git_service.create_branch.assert_not_called()
        mock_git_service.stage_and_commit.assert_not_called()

    async def test_git_branch_creation_failure(self, executor, mock_git_service):
        """Test handling of git branch creation failure."""
        mock_git_service.create_branch.side_effect = GitServiceError("Failed to create branch")

        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        # Wait and approve
        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        result = await task

        # Execution should continue even if git setup fails
        assert result["status"] in ["completed", "failed"]

    async def test_git_push_failure(self, executor, mock_git_service):
        """Test handling of git push failure."""
        mock_git_service.push_branch.side_effect = GitServiceError("Failed to push")

        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        # Wait and approve
        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        result = await task

        # Task should still complete, but without PR
        assert result["status"] == "completed"
        # PR creation should not be attempted after push failure
        mock_git_service.create_pull_request.assert_not_called()

    async def test_git_cleanup_on_completion(self, executor, mock_git_service):
        """Test that git branches are cleaned up after execution."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        # Wait and approve
        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        await task

        # Verify cleanup was called
        mock_git_service.cleanup_branch.assert_called_once()
        cleanup_call = mock_git_service.cleanup_branch.call_args
        assert cleanup_call[1]["delete_remote"] is False

    async def test_branch_name_sanitization(self, executor):
        """Test that branch names are properly sanitized."""
        sanitized = executor._sanitize_branch_name("Test Task with Spaces & Special!@#")
        assert sanitized == "test-task-with-spaces-special"
        assert len(sanitized) <= 50

    async def test_custom_commit_template(self, executor, mock_git_service):
        """Test using a custom commit message template."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
            "commit_template": "Custom: {task_name} (Run {run_number})",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="my-task",
                run_number=42,
                project_config=project_config,
            )
        )

        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        await task

        commit_call = mock_git_service.stage_and_commit.call_args
        assert commit_call[1]["message"] == "Custom: my-task (Run 42)"

    async def test_custom_branch_prefix(self, executor, mock_git_service):
        """Test using a custom branch prefix."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
            "run_branch_prefix": "feature",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test",
                run_number=1,
                project_config=project_config,
            )
        )

        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        await task

        branch_call = mock_git_service.create_branch.call_args
        assert branch_call[1]["branch"].startswith("feature/")


@pytest.mark.asyncio
class TestGitMetadataPersistence:
    """Test persistence of git metadata to database."""

    async def test_git_metadata_saved_to_run(self, executor, mock_git_service):
        """Test that git metadata is returned in execution result."""
        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        result = await task

        # Verify git metadata in result
        assert "git_metadata" in result
        git_meta = result["git_metadata"]
        assert git_meta["branch_name"] is not None
        assert git_meta["commit_sha"] == "abc123def456"
        assert git_meta["pr_url"] == "https://github.com/owner/repo/pull/123"
        assert git_meta["git_status"] == "pr_opened"


@pytest.mark.asyncio
class TestEventEmission:
    """Test git-related event emission."""

    async def test_git_branch_created_event_emitted(self, executor, mock_git_service):
        """Test that git_branch_created event is emitted."""
        from backend.schemas import EventTypeEnum
        from backend.services.events import get_event_broadcaster

        events_received = []
        broadcaster = get_event_broadcaster()

        async def collect_events():
            async for event in broadcaster.subscribe("all"):
                events_received.append(event)
                if event.event_type == EventTypeEnum.COMPLETION:
                    break

        # Start event collector
        collector = asyncio.create_task(collect_events())

        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        await task
        await asyncio.sleep(0.1)  # Allow events to be collected
        collector.cancel()

        # Verify git events were emitted
        event_types = [e.event_type for e in events_received]
        assert EventTypeEnum.GIT_BRANCH_CREATED in event_types
        assert EventTypeEnum.GIT_COMMIT_CREATED in event_types
        assert EventTypeEnum.GIT_PUSH_SUCCESS in event_types
        assert EventTypeEnum.PULL_REQUEST_OPENED in event_types

    async def test_git_push_failed_event_emitted(self, executor, mock_git_service):
        """Test that git_push_failed event is emitted on push failure."""
        from backend.schemas import EventTypeEnum
        from backend.services.events import get_event_broadcaster

        mock_git_service.push_branch.side_effect = GitServiceError("Push failed")

        events_received = []
        broadcaster = get_event_broadcaster()

        async def collect_events():
            async for event in broadcaster.subscribe("all"):
                events_received.append(event)
                if event.event_type == EventTypeEnum.COMPLETION:
                    break

        collector = asyncio.create_task(collect_events())

        project_config = {
            "repo_full_name": "owner/repo",
            "default_branch": "main",
        }

        task = asyncio.create_task(
            executor.execute_task(
                task_id="task_123",
                run_id="run_456",
                task_description="Test task",
                task_name="test-task",
                run_number=1,
                project_config=project_config,
            )
        )

        await asyncio.sleep(0.2)
        await executor.approve_plan("run_456", approved=True)

        await task
        await asyncio.sleep(0.1)
        collector.cancel()

        event_types = [e.event_type for e in events_received]
        assert EventTypeEnum.GIT_PUSH_FAILED in event_types
