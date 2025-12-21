# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional


@dataclass(frozen=True)
class SpanRecord:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    kind: str
    start_time: str
    end_time: str
    duration_ms: float
    attributes: Dict[str, Any]
    status_code: Optional[str]
    status_description: Optional[str]
    resource: Dict[str, Any]


class SpanStore:
    def __init__(self, maxlen: int = 2000):
        self._lock = threading.Lock()
        self._spans: Deque[SpanRecord] = deque(maxlen=maxlen)

    def set_maxlen(self, maxlen: int) -> None:
        with self._lock:
            old = list(self._spans)
            self._spans = deque(old, maxlen=maxlen)

    def add(self, record: SpanRecord) -> None:
        with self._lock:
            self._spans.append(record)

    def list(self, *, limit: int = 100, trace_id: Optional[str] = None) -> List[SpanRecord]:
        with self._lock:
            spans = list(self._spans)

        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]

        spans = list(reversed(spans))
        return spans[: max(0, limit)]

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()


_STORE = SpanStore()


def get_span_store() -> SpanStore:
    return _STORE


def _to_hex(value: int, width: int) -> str:
    return format(value, f"0{width}x")


def _ns_to_iso(ns: int) -> str:
    dt = datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)
    return dt.isoformat()


try:
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
except Exception:  # pragma: no cover
    SpanExporter = object  # type: ignore
    SpanExportResult = None  # type: ignore


class InMemorySpanExporter(SpanExporter):
    """Span exporter storing spans in memory for debugging APIs."""

    def export(self, spans):
        store = get_span_store()

        for span in spans:
            try:
                ctx = span.get_span_context()
                trace_id = _to_hex(ctx.trace_id, 32)
                span_id = _to_hex(ctx.span_id, 16)
                parent_span_id = None
                if getattr(span, "parent", None) is not None:
                    parent_span_id = _to_hex(span.parent.span_id, 16)

                start_ns = int(span.start_time)
                end_ns = int(span.end_time or start_ns)
                duration_ms = max(0.0, (end_ns - start_ns) / 1e6)

                status = getattr(span, "status", None)
                status_code = getattr(getattr(status, "status_code", None), "name", None)
                status_description = getattr(status, "description", None)

                resource_attrs: Dict[str, Any] = {}
                try:
                    resource = getattr(span, "resource", None)
                    if resource is not None:
                        resource_attrs = dict(resource.attributes)
                except Exception:
                    resource_attrs = {}

                rec = SpanRecord(
                    name=str(getattr(span, "name", "")),
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    kind=str(getattr(getattr(span, "kind", None), "name", "")),
                    start_time=_ns_to_iso(start_ns),
                    end_time=_ns_to_iso(end_ns),
                    duration_ms=duration_ms,
                    attributes=dict(getattr(span, "attributes", {}) or {}),
                    status_code=status_code,
                    status_description=status_description,
                    resource=resource_attrs,
                )
                store.add(rec)
            except Exception:
                continue

        if SpanExportResult is None:  # pragma: no cover
            return None
        return SpanExportResult.SUCCESS

    def shutdown(self):
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
