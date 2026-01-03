# -*- coding: utf-8 -*-

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.core.feature_flag_fallback import safe_is_enabled
from backend.services.feature_flag_service import get_feature_flag_service


class FeatureFlagContextMiddleware(BaseHTTPMiddleware):
    """Attach feature flag context to each request.

    - Resolves user_id and workspace_id from headers
    - Injects FeatureFlagService into request.state
    - Binds decisions into structlog contextvars for request-scoped logs
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        user_id = request.headers.get("X-User-ID")
        workspace_id = request.headers.get("X-Workspace-ID")

        service = get_feature_flag_service()
        request.state.feature_flag_service = service
        request.state.user_id = user_id
        request.state.workspace_id = workspace_id

        decisions: dict[str, bool] = {}
        ab_groups: dict[str, str] = {}

        for flag in service.list_flags():
            enabled = safe_is_enabled(service, flag.name, user_id=user_id, workspace_id=workspace_id, default=False)
            decisions[flag.name] = enabled

            if 0 < flag.rollout_percentage < 100:
                ab_groups[flag.name] = "treatment" if enabled else "control"

        structlog.contextvars.bind_contextvars(
            feature_flags=decisions,
            ab_groups=ab_groups,
        )

        return await call_next(request)
