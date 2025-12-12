# -*- coding: utf-8 -*-
"""
Backend API Routers Package

Includes:
- health: Health check and status endpoints
- tasks: Task management endpoints (stub)
- runs: Task run management endpoints (stub)
"""

from .health import router as health_router
from .tasks import router as tasks_router
from .runs import router as runs_router

__all__ = ['health_router', 'tasks_router', 'runs_router']
