# -*- coding: utf-8 -*-
"""
Backend Services Package

Shared services that integrate with the mgx_agent package:
- MGXTeamProvider: Wraps MGXStyleTeam for dependency injection
- BackgroundTaskRunner: Handles async task execution
- EventBroadcaster: Pub/sub for real-time events
"""

# Lazy import MGXTeamProvider to avoid Pydantic validation errors during module import
# Import will be done when needed in main.py lifespan
try:
    from .team_provider import MGXTeamProvider, get_team_provider, set_team_provider
except Exception:
    # If import fails, define placeholder functions
    MGXTeamProvider = None
    def get_team_provider():
        raise RuntimeError("MGXTeamProvider not available")
    def set_team_provider(provider):
        pass
from .background import BackgroundTaskRunner, BackgroundTask, TaskStatus, get_task_runner
from .events import EventBroadcaster, EventSubscriber, get_event_broadcaster
from .executor import TaskExecutor, ExecutionPhase, get_task_executor
from .git import GitService, get_git_service, set_git_service
from .agents import (
    BaseAgent,
    AgentRegistry,
    SharedContextService,
    AgentMessageBus,
    get_agent_message_bus,
)
from .sandbox import SandboxRunner, SandboxRunnerError, get_sandbox_runner
from .generator import (
    ProjectGenerator,
    TemplateManager,
    FileEngine,
    EnvEngine,
    DockerEngine,
    ScriptEngine,
)
from .pipeline import (
    ArtifactPipeline,
    ArtifactBuildConfig,
    ArtifactBuildResult,
    PublishTargets,
)

__all__ = [
    'MGXTeamProvider', 
    'get_team_provider',
    'set_team_provider',
    'BackgroundTaskRunner',
    'BackgroundTask',
    'TaskStatus',
    'get_task_runner',
    'EventBroadcaster',
    'EventSubscriber',
    'get_event_broadcaster',
    'TaskExecutor',
    'ExecutionPhase',
    'get_task_executor',
    'GitService',
    'get_git_service',
    'set_git_service',
    'BaseAgent',
    'AgentRegistry',
    'SharedContextService',
    'AgentMessageBus',
    'get_agent_message_bus',
    'SandboxRunner',
    'SandboxRunnerError',
    'ProjectGenerator',
    'TemplateManager',
    'FileEngine',
    'EnvEngine',
    'DockerEngine',
    'ScriptEngine',
    'ArtifactPipeline',
    'ArtifactBuildConfig',
    'ArtifactBuildResult',
    'PublishTargets',
]
