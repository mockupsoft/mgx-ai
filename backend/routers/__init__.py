# -*- coding: utf-8 -*-
"""backend.routers

FastAPI router registrations.
"""

from .health import router as health_router
from .metrics import router as metrics_router
from .projects import router as projects_router
from .repositories import router as repositories_router
from .runs import router as runs_router
from .tasks import router as tasks_router
from .agents import router as agents_router
from .workspaces import router as workspaces_router
from .workflows import router as workflows_router
from .ws import router as ws_router

__all__ = [
    "health_router",
    "workspaces_router",
    "projects_router",
    "repositories_router",
    "tasks_router",
    "runs_router",
    "metrics_router",
    "agents_router",
    "workflows_router",
    "ws_router",
]
