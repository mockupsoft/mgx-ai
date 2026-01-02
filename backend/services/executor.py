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
    SandboxExecutionStartedEvent,
    SandboxExecutionCompletedEvent,
    SandboxExecutionFailedEvent,
)
from backend.services.events import get_event_broadcaster
from backend.services.team_provider import MGXTeamProvider
from backend.services.git import GitService, get_git_service, GitServiceError
from backend.db.models import AgentDefinition, AgentInstance, Task
from backend.db.models.enums import AgentStatus, AgentMessageDirection
from backend.services.agents.messages import get_agent_message_bus
from sqlalchemy import select

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
        session: Optional[AsyncSession] = None,
        auto_approve: bool = True,  # Auto-approve plans by default
    ) -> Dict[str, Any]:
        """
        Execute a task with full event lifecycle.
        
        Args:
            task_id: ID of the task
            run_id: ID of the specific run
            task_description: Description of task to execute
            auto_approve: If True, automatically approve the plan without waiting
            max_rounds: Maximum execution rounds
            task_name: Name of the task (for git branch naming)
            run_number: Run number (for git branch naming)
            project_config: Project configuration including git settings
            session: Optional database session for agent instance creation
        
        Returns:
            Execution result dict
        """
        broadcaster = get_event_broadcaster()
        repo_dir = None
        branch_name = None
        git_cleanup_needed = False
        agent_instance_id = None
        task_obj = None
        
        try:
            # Create or get agent instance for this task run
            # Always create a new session for agent operations to avoid session state issues
            db_session = None
            if self.session_factory:
                db_session = await self.session_factory()
            
            if db_session:
                try:
                    # Get task to get workspace_id and project_id
                    task_result = await db_session.execute(
                        select(Task).where(Task.id == task_id)
                    )
                    task_obj = task_result.scalar_one_or_none()
                    
                    if task_obj:
                        # Try to find existing agent instance for this task/run
                        existing_instance = await db_session.execute(
                            select(AgentInstance).where(
                                AgentInstance.workspace_id == task_obj.workspace_id,
                                AgentInstance.project_id == task_obj.project_id,
                            ).limit(1)
                        )
                        agent_instance = existing_instance.scalar_one_or_none()
                        
                        # If no instance exists, create a default one
                        if not agent_instance:
                            # Get or create a default agent definition
                            default_def = await db_session.execute(
                                select(AgentDefinition).where(
                                    AgentDefinition.slug == "default"
                                ).limit(1)
                            )
                            agent_def = default_def.scalar_one_or_none()
                            
                            if not agent_def:
                                # Create a minimal default agent definition
                                agent_def = AgentDefinition(
                                    name="Default Agent",
                                    slug="default",
                                    agent_type="base",
                                    description="Default agent for task execution",
                                    is_enabled=True,
                                )
                                db_session.add(agent_def)
                                await db_session.flush()
                            
                            # Create agent instance
                            agent_instance = AgentInstance(
                                workspace_id=task_obj.workspace_id,
                                project_id=task_obj.project_id,
                                definition_id=agent_def.id,
                                name=f"Task Agent - {task_name or task_id[:8]}",
                                status=AgentStatus.ACTIVE,  # Enum value is "active" (lowercase)
                                config={},
                            )
                            db_session.add(agent_instance)
                            await db_session.flush()
                            await db_session.commit()  # Commit to make instance available immediately
                            logger.info(f"Created agent instance {agent_instance.id} for task {task_id}")
                        
                        agent_instance_id = agent_instance.id
                        
                        # Close the session after creating agent instance
                        await db_session.close()
                        
                        # Send initial message via agent message bus (use a fresh session for message)
                        if self.session_factory:
                            try:
                                msg_session = await self.session_factory()
                                try:
                                    message_bus = get_agent_message_bus()
                                    await message_bus.append(
                                        msg_session,
                                        workspace_id=task_obj.workspace_id,
                                        project_id=task_obj.project_id,
                                        agent_instance_id=agent_instance_id,
                                        direction=AgentMessageDirection.SYSTEM,
                                        payload={
                                            "type": "task_started",
                                            "agent_name": "Mike",  # TeamLeader starts the task
                                            "role": "TeamLeader",
                                            "task_id": task_id,
                                            "run_id": run_id,
                                            "message": f"Task execution started: {task_description[:100]}",
                                            "content": f"Task execution started: {task_description[:100]}",
                                        },
                                        task_id=task_id,
                                        run_id=run_id,
                                        broadcast=True,
                                    )
                                    await msg_session.commit()
                                finally:
                                    await msg_session.close()
                            except Exception as msg_error:
                                logger.warning(f"Failed to send initial message: {msg_error}")
                except Exception as e:
                    logger.warning(f"Failed to create agent instance for task {task_id}: {e}", exc_info=True)
                    # Continue without agent instance
                    try:
                        await db_session.rollback()
                    except:
                        pass
                finally:
                    # Close the session if we created it
                    if db_session:
                        try:
                            await db_session.close()
                        except:
                            pass
            
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
            
            # Check if this is a simple question (chat mode) vs complex task (code generation)
            # Do this BEFORE plan generation to skip approval for simple questions
            is_simple = self.team_provider.is_simple_question(task_description)
            logger.info(f"Task type: {'simple chat' if is_simple else 'complex task'}")
            
            # Skip plan generation and approval for simple questions
            if is_simple:
                # Simple chat mode - direct LLM response
                try:
                    result = await self.team_provider.simple_chat(task_description)
                    
                    # Send the response as an agent message
                    if agent_instance_id and task_obj and self.session_factory:
                        try:
                            msg_session = await self.session_factory()
                            try:
                                message_bus = get_agent_message_bus()
                                response_content = result.get("response", "No response")
                                await message_bus.append(
                                    msg_session,
                                    workspace_id=task_obj.workspace_id,
                                    project_id=task_obj.project_id,
                                    agent_instance_id=agent_instance_id,
                                    direction=AgentMessageDirection.OUTBOUND,
                                    payload={
                                        "type": "chat_response",
                                        "agent_name": "AI Assistant",
                                        "role": "Assistant",
                                        "task_id": task_id,
                                        "run_id": run_id,
                                        "message": response_content,
                                        "content": response_content,
                                        "mode": "simple_chat",
                                    },
                                    task_id=task_id,
                                    run_id=run_id,
                                    broadcast=True,
                                )
                                await msg_session.commit()
                            finally:
                                await msg_session.close()
                        except Exception as msg_error:
                            logger.warning(f"Failed to send chat response: {msg_error}")
                    
                    # Emit completion event
                    await self._emit_event(
                        CompletionEvent(
                            task_id=task_id,
                            run_id=run_id,
                            data={"result": result},
                            message="Chat response completed",
                        ),
                        broadcaster=broadcaster,
                    )
                    
                    return {
                        "status": "completed",
                        "mode": "simple_chat",
                        "response": result.get("response"),
                    }
                except Exception as chat_error:
                    logger.error(f"Simple chat failed: {chat_error}", exc_info=True)
                    # Fall through to complex task execution
            
            # Complex task mode - full MGXStyleTeam execution
            try:
                # Send execution started message (create new session for message)
                if agent_instance_id and task_obj and self.session_factory:
                    try:
                        msg_session = await self.session_factory()
                        try:
                            message_bus = get_agent_message_bus()
                            await message_bus.append(
                                msg_session,
                                workspace_id=task_obj.workspace_id,
                                project_id=task_obj.project_id,
                                agent_instance_id=agent_instance_id,
                                direction=AgentMessageDirection.OUTBOUND,
                                payload={
                                    "type": "execution_started",
                                    "agent_name": "Mike",  # TeamLeader executes the plan
                                    "role": "TeamLeader",
                                    "task_id": task_id,
                                    "run_id": run_id,
                                    "message": f"Executing plan for task: {task_description[:100]}",
                                    "content": f"Executing plan for task: {task_description[:100]}",
                                },
                                task_id=task_id,
                                run_id=run_id,
                                broadcast=True,
                            )
                            await msg_session.commit()
                        finally:
                            await msg_session.close()
                    except Exception as msg_error:
                        logger.warning(f"Failed to send execution started message: {msg_error}")
                
                team = await self.team_provider.get_team()
                
                # Helper function to capture and send agent messages
                async def capture_and_send_messages(env, initial_count: int = 0):
                    """Capture agent messages from MetaGPT team environment and send them."""
                    if not agent_instance_id or not task_obj or not self.session_factory:
                        return
                    
                    try:
                        if not hasattr(env, 'messages'):
                            return
                        
                        # Get new messages since initial_count
                        all_messages = env.messages
                        new_messages = all_messages[initial_count:] if initial_count < len(all_messages) else all_messages
                        
                        if not new_messages:
                            return
                        
                        logger.info(f"Capturing {len(new_messages)} agent messages from team execution")
                        
                        # Map MetaGPT roles to agent names
                        role_name_map = {
                            "TeamLeader": "Mike",
                            "Engineer": "Alex", 
                            "Tester": "Bob",
                            "Reviewer": "Charlie",
                        }
                        
                        # Send each agent message
                        for msg in new_messages:
                            try:
                                # Extract agent name from message role
                                msg_role = msg.role if hasattr(msg, 'role') else None
                                agent_name = role_name_map.get(msg_role, msg_role) if msg_role else "Agent"
                                
                                # Get content
                                content = msg.content if hasattr(msg, 'content') else str(msg)
                                
                                # Skip empty or system messages
                                if not content or not content.strip():
                                    continue
                                
                                # Determine message type
                                msg_type = "agent_message"
                                if hasattr(msg, 'cause_by'):
                                    cause_by = str(msg.cause_by) if msg.cause_by else ""
                                    if "AnalyzeTask" in cause_by or "DraftPlan" in cause_by:
                                        msg_type = "planning"
                                    elif "WriteCode" in cause_by:
                                        msg_type = "coding"
                                    elif "WriteTest" in cause_by:
                                        msg_type = "testing"
                                    elif "ReviewCode" in cause_by:
                                        msg_type = "review"
                                
                                # Send message via agent message bus
                                msg_session = await self.session_factory()
                                try:
                                    message_bus = get_agent_message_bus()
                                    await message_bus.append(
                                        msg_session,
                                        workspace_id=task_obj.workspace_id,
                                        project_id=task_obj.project_id,
                                        agent_instance_id=agent_instance_id,
                                        direction=AgentMessageDirection.OUTBOUND,
                                        payload={
                                            "type": msg_type,
                                            "agent_name": agent_name,
                                            "role": msg_role or "assistant",
                                            "content": content,
                                            "task_id": task_id,
                                            "run_id": run_id,
                                            "message": content[:200] + "..." if len(content) > 200 else content,
                                        },
                                        task_id=task_id,
                                        run_id=run_id,
                                        broadcast=True,
                                    )
                                    await msg_session.commit()
                                    logger.debug(f"Sent agent message from {agent_name}: {content[:50]}...")
                                finally:
                                    await msg_session.close()
                            except Exception as msg_error:
                                logger.warning(f"Failed to send agent message: {msg_error}", exc_info=True)
                                continue
                    except Exception as capture_error:
                        logger.warning(f"Failed to capture agent messages: {capture_error}", exc_info=True)
                
                # Track agent messages during execution
                # MetaGPT stores messages in team.env.messages
                initial_message_count = 0
                if hasattr(team, 'env') and hasattr(team.env, 'messages'):
                    initial_message_count = len(team.env.messages)
                    logger.info(f"Initial message count: {initial_message_count}")
                
                # Create progress callback for real-time agent updates
                async def agent_progress_callback(agent_name: str, status: str, message: str):
                    """Broadcast agent progress as WebSocket events."""
                    if agent_instance_id and task_obj and self.session_factory:
                        try:
                            msg_session = await self.session_factory()
                            try:
                                message_bus = get_agent_message_bus()
                                await message_bus.append(
                                    msg_session,
                                    workspace_id=task_obj.workspace_id,
                                    project_id=task_obj.project_id,
                                    agent_instance_id=agent_instance_id,
                                    direction=AgentMessageDirection.OUTBOUND,
                                    payload={
                                        "type": "agent_progress",
                                        "agent_name": agent_name,
                                        "status": status,
                                        "task_id": task_id,
                                        "run_id": run_id,
                                        "message": message,
                                        "content": message,
                                    },
                                    task_id=task_id,
                                    run_id=run_id,
                                    broadcast=True,
                                )
                                await msg_session.commit()
                            finally:
                                await msg_session.close()
                        except Exception as cb_error:
                            logger.warning(f"Failed to send agent progress: {cb_error}")
                
                # Execute task via team_provider which calls analyze_and_plan and execute
                result = await self.team_provider.run_task(task_description)
                
                # Capture agent messages from team execution
                if hasattr(team, 'env') and hasattr(team.env, 'messages'):
                    await capture_and_send_messages(team.env, initial_message_count)
                
                # Send execution completed message
                if agent_instance_id and task_obj and self.session_factory:
                    try:
                        msg_session = await self.session_factory()
                        try:
                            message_bus = get_agent_message_bus()
                            
                            # Extract the actual result content for display
                            result_message = "Task execution completed successfully"
                            if isinstance(result, dict):
                                # If result has a 'result' key with actual content, show it
                                if result.get("result"):
                                    result_content = result.get("result")
                                    if isinstance(result_content, str):
                                        result_message = result_content
                                    elif isinstance(result_content, dict):
                                        # Try to get summary or description from result
                                        result_message = result_content.get("summary", 
                                            result_content.get("description",
                                                result_content.get("message", str(result_content))))
                                # If result has a 'plan' key, mention it
                                if result.get("plan"):
                                    plan = result.get("plan")
                                    if isinstance(plan, str) and len(plan) > 100:
                                        result_message = f"📋 Plan executed successfully.\n\n{result_message}"
                            
                            await message_bus.append(
                                msg_session,
                                workspace_id=task_obj.workspace_id,
                                project_id=task_obj.project_id,
                                agent_instance_id=agent_instance_id,
                                direction=AgentMessageDirection.OUTBOUND,
                                payload={
                                    "type": "execution_completed",
                                    "task_id": task_id,
                                    "run_id": run_id,
                                    "message": result_message,
                                    "content": result_message,  # Also add as content for frontend extraction
                                    "result": result if isinstance(result, dict) else {"status": "completed"},
                                },
                                task_id=task_id,
                                run_id=run_id,
                                broadcast=True,
                            )
                            await msg_session.commit()
                        finally:
                            await msg_session.close()
                    except Exception as msg_error:
                        logger.warning(f"Failed to send execution completed message: {msg_error}")
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                result = None
                
                # Send execution failed message
                if agent_instance_id and task_obj and self.session_factory:
                    try:
                        msg_session = await self.session_factory()
                        try:
                            message_bus = get_agent_message_bus()
                            await message_bus.append(
                                msg_session,
                                workspace_id=task_obj.workspace_id,
                                project_id=task_obj.project_id,
                                agent_instance_id=agent_instance_id,
                                direction=AgentMessageDirection.OUTBOUND,
                                payload={
                                    "type": "execution_failed",
                                    "task_id": task_id,
                                    "run_id": run_id,
                                    "message": f"Task execution failed: {str(e)}",
                                    "error": str(e),
                                },
                                task_id=task_id,
                                run_id=run_id,
                                broadcast=True,
                            )
                            await msg_session.commit()
                        finally:
                            await msg_session.close()
                    except Exception as msg_error:
                        logger.warning(f"Failed to send error message: {msg_error}")
            
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
                
                # Emit FILES_UPDATED event after completion
                try:
                    from pathlib import Path
                    output_base = Path("output")
                    if output_base.exists():
                        # Find the most recent mgx_team_* directory
                        mgx_dirs = sorted(
                            [d for d in output_base.iterdir() if d.is_dir() and d.name.startswith("mgx_team_")],
                            key=lambda p: p.stat().st_mtime,
                            reverse=True
                        )
                        if mgx_dirs:
                            # Count files in the directory
                            file_count = sum(1 for _ in mgx_dirs[0].rglob("*") if _.is_file())
                            await self._emit_event(
                                EventPayload(
                                    event_type=EventTypeEnum.FILES_UPDATED,
                                    task_id=task_id,
                                    run_id=run_id,
                                    workspace_id=task_obj.workspace_id if task_obj else None,
                                    data={
                                        "task_id": task_id,
                                        "run_id": run_id,
                                        "file_count": file_count,
                                        "output_dir": str(mgx_dirs[0]),
                                    },
                                    message=f"Files updated: {file_count} files in output directory",
                                ),
                                broadcaster=broadcaster,
                            )
                            logger.info(f"Emitted FILES_UPDATED event for task {task_id}, run {run_id}: {file_count} files")
                except Exception as files_error:
                    logger.warning(f"Failed to emit FILES_UPDATED event: {files_error}", exc_info=True)
                
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
        
        # Create a session factory callable that returns a new session
        async def session_factory():
            from backend.db.engine import get_session_factory
            factory = await get_session_factory()
            return factory()
        
        _executor = TaskExecutor(
            team_provider=team_provider,
            session_factory=session_factory,
        )
    return _executor


__all__ = [
    'TaskExecutor',
    'ExecutionPhase',
    'get_task_executor',
]
