# -*- coding: utf-8 -*-
"""
Structured Logging Middleware

Provides JSON structured logging with correlation IDs for request/response tracking.
"""

import logging
import uuid
import time
from typing import Callable, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured logging with correlation IDs.

    Features:
    - Adds correlation ID to each request
    - Logs request and response details
    - Tracks request duration
    - Extracts context from headers
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log with structured data.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler
        """
        # Generate or extract correlation ID
        correlation_id = self._get_correlation_id(request)
        request_id = str(uuid.uuid4())

        # Extract context from headers
        context = self._extract_context(request)

        # Start timer
        start_time = time.time()

        # Add context to structlog
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            **context
        )

        # Log request
        logger.info(
            "request_started",
            client_host=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log successful response
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration for failed request
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )

            # Re-raise exception
            raise

        finally:
            # Clear context
            structlog.contextvars.clear_contextvars()

    def _get_correlation_id(self, request: Request) -> str:
        """
        Get or generate correlation ID.

        Priority:
        1. X-Correlation-ID header
        2. X-Request-ID header
        3. Generate new UUID

        Args:
            request: Incoming request

        Returns:
            Correlation ID string
        """
        # Try to get from headers
        correlation_id = (
            request.headers.get("X-Correlation-ID") or
            request.headers.get("X-Request-ID") or
            str(uuid.uuid4())
        )
        return correlation_id

    def _extract_context(self, request: Request) -> dict:
        """
        Extract context from request headers and path parameters.

        Args:
            request: Incoming request

        Returns:
            Context dictionary
        """
        context = {}

        # Extract workspace/project context from path
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) >= 1:
            # Try to extract workspace_id from path
            # This is a heuristic - adjust based on your routing
            if "workspaces" in path_parts:
                try:
                    idx = path_parts.index("workspaces")
                    if idx + 1 < len(path_parts):
                        context["workspace_id"] = path_parts[idx + 1]
                except (ValueError, IndexError):
                    pass

        # Extract from headers
        if "X-Workspace-ID" in request.headers:
            context["workspace_id"] = request.headers["X-Workspace-ID"]

        if "X-Project-ID" in request.headers:
            context["project_id"] = request.headers["X-Project-ID"]

        if "X-Task-ID" in request.headers:
            context["task_id"] = request.headers["X-Task-ID"]

        if "X-Agent-ID" in request.headers:
            context["agent_id"] = request.headers["X-Agent-ID"]

        if "X-Run-ID" in request.headers:
            context["run_id"] = request.headers["X-Run-ID"]

        # Extract from query parameters
        if "workspace_id" in request.query_params:
            context["workspace_id"] = request.query_params["workspace_id"]

        if "task_id" in request.query_params:
            context["task_id"] = request.query_params["task_id"]

        return context


def setup_logging(log_level: str = "INFO") -> None:
    """
    Setup structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure standard logging to redirect to structlog
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


__all__ = [
    'StructuredLoggingMiddleware',
    'setup_logging',
    'get_logger',
]
