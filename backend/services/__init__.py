# -*- coding: utf-8 -*-
"""
Backend Services Package

Shared services that integrate with the mgx_agent package:
- MGXTeamProvider: Wraps MGXStyleTeam for dependency injection
- BackgroundTaskRunner: Handles async task execution
"""

from .team_provider import MGXTeamProvider, get_team_provider, set_team_provider
from .background import BackgroundTaskRunner, BackgroundTask, TaskStatus, get_task_runner

__all__ = [
    'MGXTeamProvider', 
    'get_team_provider',
    'set_team_provider',
    'BackgroundTaskRunner',
    'BackgroundTask',
    'TaskStatus',
    'get_task_runner',
]
