# -*- coding: utf-8 -*-
"""Backend package initialization."""

from . import sandbox
from .quality_gates import router as quality_gates_router
from .rbac import router as rbac_router
from .audit import router as audit_router
from .secrets import router as secrets_router
from .generator import router as generator_router

# Legacy routers (kept for backwards compatibility)
try:
    from .health import router as health_router
    from .workspaces import router as workspaces_router
    from .projects import router as projects_router
    from .repositories import router as repositories_router
    from .tasks import router as tasks_router
    from .runs import router as runs_router
    from .metrics import router as metrics_router
    from .agents import router as agents_router
    from .workflows import router as workflows_router
    from .ws import router as ws_router
except ImportError:
    # Fallback if some routers don't exist yet
    health_router = None
    workspaces_router = None
    projects_router = None
    repositories_router = None
    tasks_router = None
    runs_router = None
    metrics_router = None
    agents_router = None
    workflows_router = None
    ws_router = None

__all__ = [
    "sandbox", 
    "quality_gates_router",
    "rbac_router", 
    "audit_router",
    "secrets_router",
    "generator_router",
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