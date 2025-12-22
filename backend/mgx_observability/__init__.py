# -*- coding: utf-8 -*-
"""Shared observability utilities.

This module provides optional integrations for:
- OpenTelemetry tracing (FastAPI/SQLAlchemy/HTTPX + manual spans)
- LangSmith run logging for LLM calls

All functionality is best-effort and becomes a no-op when the corresponding
optional dependencies are not installed or when disabled via configuration.
"""

from .config import ObservabilityConfig
from .context import (
    get_current_context,
    set_current_context,
    observability_context,
)
from .spans import (
    start_span,
    set_span_attributes,
    record_exception,
    get_current_span_ids,
)
from .otel import initialize_otel
from .span_store import get_span_store
from .langsmith import get_langsmith_logger

__all__ = [
    "ObservabilityConfig",
    "initialize_otel",
    "get_span_store",
    "get_langsmith_logger",
    "start_span",
    "set_span_attributes",
    "record_exception",
    "get_current_span_ids",
    "get_current_context",
    "set_current_context",
    "observability_context",
]
