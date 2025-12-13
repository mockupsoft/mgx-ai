# -*- coding: utf-8 -*-
"""
Background execution service for running tasks and emitting events.

Orchestrates:
- Task execution via MGXStyleTeam
- Database state updates
- Event broadcasting for key hooks
- Plan approval flow
"""

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional, Callable, Any, Dict
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.enums import RunStatus as DBRunStatus
from backend.schemas import (
    EventPayload,
    EventTypeEnum,
    AnalysisStartEvent,
    PlanReadyEvent,
    ApprovalRequiredEvent,
    ApprovedEvent,
    ProgressEvent,
    CompletionEvent,
    FailureEvent,
    GitBranchCreatedEvent,
    GitCommitCreatedEvent,
    GitPushSuccessEvent,
    GitPushFailedEvent,
    PullRequestOpenedEvent,
    GitOperationFailedEvent,
)
from backend.services.events import get_event_broadcaster
from backend.services.team_provider import MGXTeamProvider
from backend.services.git import GitService, get_git_service, GitServiceError

logger = logging.getLogger(__name__)


class ExecutionPhase(str, Enum):
    """Execution phases for a run."""
    ANALYSIS = "analysis"
    PLANNING = "planning"
    APPROVAL = "approval"
    EXECUTION = "execution"
    COMPLETION = "completion"


class TaskExecutor:
    """
    Executes tasks via MGXStyleTeam with event emission and database updates.
    
    Handles the full lifecycle of task execution:
    1. Start analysis
    2. Generate plan
    3. Request approval (pause for user)
    4. Execute plan
    5. Emit completion/failure events
    """
    
    def __init__(
        self,
        team_provider: MGXTeamProvider,
        session_factory: Optional[Callable] = None,
        git_service: Optional[GitService] = None,
    ):
        """
        Initialize the executor.
        
        Args:
            team_provider: MGXTeamProvider for team operations
            session_factory: Async session factory for DB operations
            git_service: GitService for Git operations
        """
        self.team_provider = team_provider
        self.session_factory = session_factory
        self.git_service = git_service or get_git_service()
        self._approval_events: Dict[str, asyncio.Event] = {}
        self._approval_decisions: Dict[str, bool] = {}
        logger.info("TaskExecutor initialized")
    
    async def execute_task(
        self,
        task_id: str,
        run_id: str,
        task_description: str,
        max_rounds: int = 5,
        task_name: Optional[str] = None,
        run_number: Optional[int] = None,
        project_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a task with full event lifecycle.
        
        Args:
            task_id: ID of the task
            run_id: ID of the specific run
            task_description: Description of task to execute
            max_rounds: Maximum execution rounds
            task_name: Name of the task (for git branch naming)
            run_number: Run number (for git branch naming)
            project_config: Project configuration including git settings
        
        Returns:
            Execution result dict
        """
        broadcaster = get_event_broadcaster()
        repo_dir = None
        branch_name = None
        git_cleanup_needed = False
        
        try:
            # Phase 1: Start analysis
            await self._emit_event(
                AnalysisStartEvent(
                    task_id=task_id,
                    run_id=run_id,
                    message="Starting task analysis",
                ),
                broadcaster=broadcaster,
            )
            
            # Simulate analysis phase
            await asyncio.sleep(0.1)
            
            # Phase 2: Generate plan
            logger.info(f"Generating plan for run {run_id}")
            plan = {
                "steps": ["step1", "step2", "step3"],
                "estimated_time": "5 minutes",
                "resources": ["agent1", "agent2"],
            }
            
            await self._emit_event(
                PlanReadyEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"plan": plan},
                    message="Plan ready for review",
                ),
                broadcaster=broadcaster,
            )
            
            # Phase 2.5: Git setup (clone repo and create branch)
            git_metadata = {}
            if project_config and project_config.get("repo_full_name"):
                try:
                    git_metadata = await self._setup_git_branch(
                        run_id=run_id,
                        task_id=task_id,
                        task_name=task_name or "task",
                        run_number=run_number or 1,
                        project_config=project_config,
                        broadcaster=broadcaster,
                    )
                    repo_dir = git_metadata.get("repo_dir")
                    branch_name = git_metadata.get("branch_name")
                    git_cleanup_needed = True
                except GitServiceError as e:
                    logger.error(f"Git setup failed: {e}")
                    await self._emit_event(
                        GitOperationFailedEvent(
                            task_id=task_id,
                            run_id=run_id,
                            data={"error": str(e), "operation": "branch_creation"},
                            message=f"Git setup failed: {str(e)}",
                        ),
                        broadcaster=broadcaster,
                    )
            
            # Phase 3: Request approval
            await self._emit_event(
                ApprovalRequiredEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"plan": plan},
                    message="Waiting for plan approval",
                ),
                broadcaster=broadcaster,
            )
            
            # Wait for approval
            approved = await self.wait_for_approval(run_id, timeout=300)
            
            if not approved:
                logger.info(f"Run {run_id} plan was rejected")
                await self._emit_event(
                    FailureEvent(
                        task_id=task_id,
                        run_id=run_id,
                        message="Plan rejected by user",
                    ),
                    broadcaster=broadcaster,
                )
                return {
                    "status": "rejected",
                    "message": "Plan rejected by user",
                }
            
            # Emit approval confirmation
            await self._emit_event(
                ApprovedEvent(
                    task_id=task_id,
                    run_id=run_id,
                    message="Plan approved, execution started",
                ),
                broadcaster=broadcaster,
            )
            
            # Phase 4: Execute plan
            logger.info(f"Executing plan for run {run_id}")
            try:
                team = await self.team_provider.get_team()
                result = await team.run(task_description)
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                result = None
            
            # Phase 4.5: Git commit and push (if git was setup)
            if result and repo_dir and branch_name:
                try:
                    git_result = await self._commit_and_push_changes(
                        run_id=run_id,
                        task_id=task_id,
                        task_name=task_name or "task",
                        run_number=run_number or 1,
                        repo_dir=repo_dir,
                        branch_name=branch_name,
                        project_config=project_config or {},
                        broadcaster=broadcaster,
                    )
                    git_metadata.update(git_result)
                except GitServiceError as e:
                    logger.error(f"Git commit/push failed: {e}")
                    await self._emit_event(
                        GitPushFailedEvent(
                            task_id=task_id,
                            run_id=run_id,
                            data={"error": str(e), "branch": branch_name},
                            message=f"Git push failed: {str(e)}",
                        ),
                        broadcaster=broadcaster,
                    )
            
            # Phase 5: Completion
            if result:
                await self._emit_event(
                    CompletionEvent(
                        task_id=task_id,
                        run_id=run_id,
                        data={"results": result, "git_metadata": git_metadata},
                        message="Task completed successfully",
                    ),
                    broadcaster=broadcaster,
                )
                
                return {
                    "status": "completed",
                    "results": result,
                    "git_metadata": git_metadata,
                }
            else:
                raise Exception("Execution returned no result")
        
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await self._emit_event(
                FailureEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"error": str(e)},
                    message=f"Task failed: {str(e)}",
                ),
                broadcaster=broadcaster,
            )
            
            return {
                "status": "failed",
                "error": str(e),
            }
        finally:
            if git_cleanup_needed and repo_dir and branch_name:
                try:
                    await self.git_service.cleanup_branch(repo_dir, branch_name, delete_remote=False)
                    logger.info(f"Cleaned up local branch: {branch_name}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup branch {branch_name}: {e}")
    
    async def _emit_event(
        self,
        event: EventPayload,
        broadcaster: Optional[Any] = None,
    ):
        """Emit an event to the broadcaster."""
        if broadcaster is None:
            broadcaster = get_event_broadcaster()
        
        await broadcaster.publish(event)
        logger.debug(f"Event emitted: {event.event_type}")
    
    async def wait_for_approval(
        self,
        run_id: str,
        timeout: int = 300,
    ) -> bool:
        """
        Wait for plan approval.
        
        Args:
            run_id: Run ID to wait for
            timeout: Seconds to wait before timing out
        
        Returns:
            True if approved, False if rejected or timeout
        """
        if run_id not in self._approval_events:
            self._approval_events[run_id] = asyncio.Event()
        
        try:
            await asyncio.wait_for(
                self._approval_events[run_id].wait(),
                timeout=timeout,
            )
            return self._approval_decisions.get(run_id, False)
        except asyncio.TimeoutError:
            logger.warning(f"Approval timeout for run {run_id}")
            return False
    
    async def approve_plan(self, run_id: str, approved: bool = True):
        """
        Approve or reject a plan.
        
        Args:
            run_id: Run ID to approve
            approved: Whether plan is approved
        """
        self._approval_decisions[run_id] = approved
        
        if run_id not in self._approval_events:
            self._approval_events[run_id] = asyncio.Event()
        
        self._approval_events[run_id].set()
        logger.info(f"Plan approval set for run {run_id}: {approved}")
    
    def _sanitize_branch_name(self, name: str) -> str:
        """Sanitize a string for use in git branch names."""
        sanitized = re.sub(r'[^a-zA-Z0-9-_]', '-', name.lower())
        sanitized = re.sub(r'-+', '-', sanitized)
        sanitized = sanitized.strip('-')
        return sanitized[:50]
    
    async def _setup_git_branch(
        self,
        run_id: str,
        task_id: str,
        task_name: str,
        run_number: int,
        project_config: Dict[str, Any],
        broadcaster: Any,
    ) -> Dict[str, Any]:
        """
        Clone repository and create a feature branch for the run.
        
        Args:
            run_id: Run ID
            task_id: Task ID
            task_name: Task name
            run_number: Run number
            project_config: Project configuration with git settings
            broadcaster: Event broadcaster
        
        Returns:
            Dictionary with git metadata (repo_dir, branch_name)
        """
        repo_full_name = project_config.get("repo_full_name")
        default_branch = project_config.get("default_branch", "main")
        branch_prefix = project_config.get("run_branch_prefix", "mgx")
        
        task_slug = self._sanitize_branch_name(task_name)
        branch_name = f"{branch_prefix}/{task_slug}/run-{run_number}"
        
        logger.info(f"Setting up Git branch: {branch_name} for {repo_full_name}")
        
        repo_dir = await self.git_service.ensure_clone(
            repo_full_name=repo_full_name,
            default_branch=default_branch,
        )
        
        await self.git_service.create_branch(
            repo_dir=repo_dir,
            branch=branch_name,
            base_branch=default_branch,
        )
        
        await self._emit_event(
            GitBranchCreatedEvent(
                task_id=task_id,
                run_id=run_id,
                data={
                    "branch_name": branch_name,
                    "base_branch": default_branch,
                    "repo_full_name": repo_full_name,
                },
                message=f"Git branch created: {branch_name}",
            ),
            broadcaster=broadcaster,
        )
        
        return {
            "repo_dir": repo_dir,
            "branch_name": branch_name,
            "git_status": "branch_created",
        }
    
    async def _commit_and_push_changes(
        self,
        run_id: str,
        task_id: str,
        task_name: str,
        run_number: int,
        repo_dir: Path,
        branch_name: str,
        project_config: Dict[str, Any],
        broadcaster: Any,
    ) -> Dict[str, Any]:
        """
        Stage, commit, and push changes, then open a PR.
        
        Args:
            run_id: Run ID
            task_id: Task ID
            task_name: Task name
            run_number: Run number
            repo_dir: Repository directory
            branch_name: Branch name
            project_config: Project configuration with git settings
            broadcaster: Event broadcaster
        
        Returns:
            Dictionary with git metadata (commit_sha, pr_url, git_status)
        """
        commit_template = project_config.get("commit_template", "MGX Task: {task_name} - Run #{run_number}")
        commit_message = commit_template.format(task_name=task_name, run_number=run_number)
        
        logger.info(f"Committing changes to {branch_name}")
        
        commit_sha = await self.git_service.stage_and_commit(
            repo_dir=repo_dir,
            message=commit_message,
        )
        
        await self._emit_event(
            GitCommitCreatedEvent(
                task_id=task_id,
                run_id=run_id,
                data={
                    "commit_sha": commit_sha,
                    "branch_name": branch_name,
                    "commit_message": commit_message,
                },
                message=f"Git commit created: {commit_sha[:8]}",
            ),
            broadcaster=broadcaster,
        )
        
        logger.info(f"Pushing branch {branch_name}")
        
        try:
            await self.git_service.push_branch(repo_dir=repo_dir, branch=branch_name)
            
            await self._emit_event(
                GitPushSuccessEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={
                        "branch_name": branch_name,
                        "commit_sha": commit_sha,
                    },
                    message=f"Git push successful: {branch_name}",
                ),
                broadcaster=broadcaster,
            )
        except GitServiceError as e:
            logger.error(f"Push failed: {e}")
            await self._emit_event(
                GitPushFailedEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"error": str(e), "branch": branch_name},
                    message=f"Git push failed: {str(e)}",
                ),
                broadcaster=broadcaster,
            )
            raise
        
        pr_url = None
        try:
            repo_full_name = project_config.get("repo_full_name")
            default_branch = project_config.get("default_branch", "main")
            pr_title = f"MGX: {task_name} - Run #{run_number}"
            pr_body = f"Automated changes from MGX task execution.\n\n**Task:** {task_name}\n**Run:** #{run_number}\n**Commit:** {commit_sha}"
            
            pr_url = await self.git_service.create_pull_request(
                repo_full_name=repo_full_name,
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=default_branch,
            )
            
            await self._emit_event(
                PullRequestOpenedEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={
                        "pr_url": pr_url,
                        "branch_name": branch_name,
                        "commit_sha": commit_sha,
                    },
                    message=f"Pull request opened: {pr_url}",
                ),
                broadcaster=broadcaster,
            )
        except GitServiceError as e:
            logger.warning(f"Failed to create PR: {e}")
            await self._emit_event(
                GitOperationFailedEvent(
                    task_id=task_id,
                    run_id=run_id,
                    data={"error": str(e), "operation": "create_pr"},
                    message=f"PR creation failed: {str(e)}",
                ),
                broadcaster=broadcaster,
            )
        
        return {
            "commit_sha": commit_sha,
            "pr_url": pr_url,
            "git_status": "pr_opened" if pr_url else "pushed",
        }


# Global executor instance
_executor: Optional[TaskExecutor] = None


def get_task_executor(
    team_provider: Optional[MGXTeamProvider] = None,
) -> TaskExecutor:
    """
    Get or create the global task executor instance.
    
    Args:
        team_provider: MGXTeamProvider instance (optional)
    
    Returns:
        TaskExecutor instance
    """
    global _executor
    if _executor is None:
        if team_provider is None:
            from backend.services import get_team_provider
            team_provider = get_team_provider()
        _executor = TaskExecutor(team_provider=team_provider)
    return _executor


__all__ = [
    'TaskExecutor',
    'ExecutionPhase',
    'get_task_executor',
]
