# -*- coding: utf-8 -*-
"""
Backend API Routers Package

Includes:
- health: Health check and status endpoints
- tasks: Task management endpoints with CRUD
- runs: Task run management endpoints with execution
- metrics: Metrics retrieval and aggregation
- ws: WebSocket endpoints for real-time events
"""

from .health import router as health_router
from .tasks import router as tasks_router
from .runs import router as runs_router
from .metrics import router as metrics_router
from .ws import router as ws_router

__all__ = ['health_router', 'tasks_router', 'runs_router', 'metrics_router', 'ws_router']
