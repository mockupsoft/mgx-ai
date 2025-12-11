# -*- coding: utf-8 -*-
"""
MGX Agent Package

Modular implementation of MGX Style Multi-Agent Team using MetaGPT.
"""

# Config & Constants
from .config import (
    TaskComplexity,
    LogLevel,
    TeamConfig,
    DEFAULT_CONFIG,
)

# Metrics
from .metrics import TaskMetrics

# Actions
from .actions import (
    AnalyzeTask,
    DraftPlan,
    WriteCode,
    WriteTest,
    ReviewCode,
    llm_retry,
    print_step_progress,
    print_phase_header,
)

# Adapter
from .adapter import MetaGPTAdapter

# Roles & Mixins
from .roles import (
    RelevantMemoryMixin,
    Mike,
    Alex,
    Bob,
    Charlie,
)

# Team
from .team import MGXStyleTeam

__all__ = [
    # Config
    'TaskComplexity',
    'LogLevel',
    'TeamConfig',
    'DEFAULT_CONFIG',
    
    # Metrics
    'TaskMetrics',
    
    # Actions
    'AnalyzeTask',
    'DraftPlan',
    'WriteCode',
    'WriteTest',
    'ReviewCode',
    'llm_retry',
    'print_step_progress',
    'print_phase_header',
    
    # Adapter
    'MetaGPTAdapter',
    
    # Roles
    'RelevantMemoryMixin',
    'Mike',
    'Alex',
    'Bob',
    'Charlie',
    
    # Team
    'MGXStyleTeam',
]

__version__ = '1.0.0'
__author__ = 'MetaGPT Contributors'
