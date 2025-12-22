# -*- coding: utf-8 -*-

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Iterator, Optional


@dataclass(frozen=True)
class ObservabilityContext:
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None


_CTX: ContextVar[ObservabilityContext] = ContextVar(
    "mgx_observability_context",
    default=ObservabilityContext(),
)


def get_current_context() -> ObservabilityContext:
    return _CTX.get()


def set_current_context(ctx: ObservabilityContext) -> None:
    _CTX.set(ctx)


@contextmanager
def observability_context(**kwargs) -> Iterator[ObservabilityContext]:
    prev = _CTX.get()
    new_ctx = replace(prev, **kwargs)
    token = _CTX.set(new_ctx)
    try:
        yield new_ctx
    finally:
        _CTX.reset(token)
