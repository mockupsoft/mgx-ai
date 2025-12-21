# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from mgx_observability import observability_context


def _get_header_or_query(request: Request, header_name: str, query_name: str) -> Optional[str]:
    val = request.headers.get(header_name)
    if val:
        return val
    return request.query_params.get(query_name)


class ObservabilityContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        workspace_id = _get_header_or_query(request, "X-Workspace-Id", "workspace_id")
        project_id = _get_header_or_query(request, "X-Project-Id", "project_id")
        agent_id = _get_header_or_query(request, "X-Agent-Id", "agent_id")
        execution_id = _get_header_or_query(request, "X-Execution-Id", "execution_id")
        run_id = _get_header_or_query(request, "X-Run-Id", "run_id")

        with observability_context(
            workspace_id=workspace_id,
            project_id=project_id,
            agent_id=agent_id,
            execution_id=execution_id,
            run_id=run_id,
        ):
            return await call_next(request)


__all__ = ["ObservabilityContextMiddleware"]
