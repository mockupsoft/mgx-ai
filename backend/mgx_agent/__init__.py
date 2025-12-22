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

# Cache
from .cache import (
    CacheBackend,
    ResponseCache,
    InMemoryLRUTTLCache,
    NullCache,
    RedisCache,
    make_cache_key,
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

# Performance (Async Tools)
from .performance.async_tools import (
    AsyncTimer,
    bounded_gather,
    with_timeout,
    run_in_thread,
    PhaseTimings,
)

__all__ = [
    # Config
    'TaskComplexity',
    'LogLevel',
    'TeamConfig',
    'DEFAULT_CONFIG',
    
    # Cache
    'CacheBackend',
    'ResponseCache',
    'InMemoryLRUTTLCache',
    'NullCache',
    'RedisCache',
    'make_cache_key',

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
    
    # Performance
    'AsyncTimer',
    'bounded_gather',
    'with_timeout',
    'run_in_thread',
    'PhaseTimings',
]

__version__ = '1.0.0'
__author__ = 'MetaGPT Contributors'
