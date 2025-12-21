# -*- coding: utf-8 -*-

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Tuple

from .context import get_current_context


def _safe_import_otel():
    try:
        from opentelemetry import trace

        return trace
    except Exception:
        return None


@asynccontextmanager
async def start_span(
    name: str,
    *,
    attributes: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[Optional[object]]:
    trace = _safe_import_otel()
    if trace is None:
        yield None
        return

    tracer = trace.get_tracer("mgx")

    ctx = get_current_context()
    merged: Dict[str, Any] = {
        "workspace_id": ctx.workspace_id,
        "project_id": ctx.project_id,
        "agent_id": ctx.agent_id,
        "execution_id": ctx.execution_id,
        "task_id": ctx.task_id,
        "run_id": ctx.run_id,
        "git.branch": ctx.git_branch,
        "git.commit": ctx.git_commit,
    }
    if attributes:
        merged.update(attributes)

    merged = {k: v for k, v in merged.items() if v is not None}

    with tracer.start_as_current_span(name) as span:
        try:
            if merged:
                for k, v in merged.items():
                    try:
                        span.set_attribute(k, v)
                    except Exception:
                        continue
            yield span
        except Exception as e:
            try:
                span.record_exception(e)
            except Exception:
                pass
            raise


def set_span_attributes(span: Optional[object], attributes: Dict[str, Any]) -> None:
    if span is None:
        return
    for k, v in (attributes or {}).items():
        if v is None:
            continue
        try:
            span.set_attribute(k, v)
        except Exception:
            continue


def record_exception(span: Optional[object], exc: BaseException) -> None:
    if span is None:
        return
    try:
        span.record_exception(exc)
    except Exception:
        return


def get_current_span_ids() -> Tuple[Optional[str], Optional[str]]:
    trace = _safe_import_otel()
    if trace is None:
        return None, None

    span = trace.get_current_span()
    if span is None:
        return None, None

    try:
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")
        return trace_id, span_id
    except Exception:
        return None, None
