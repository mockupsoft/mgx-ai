# -*- coding: utf-8 -*-
"""
Backend Services Package

Shared services that integrate with the mgx_agent package:
- MGXTeamProvider: Wraps MGXStyleTeam for dependency injection
- BackgroundTaskRunner: Handles async task execution
- EventBroadcaster: Pub/sub for real-time events
"""

from .team_provider import MGXTeamProvider, get_team_provider, set_team_provider
from .background import BackgroundTaskRunner, BackgroundTask, TaskStatus, get_task_runner
from .events import EventBroadcaster, EventSubscriber, get_event_broadcaster
from .executor import TaskExecutor, ExecutionPhase, get_task_executor
from .git import GitService, get_git_service, set_git_service

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
]
