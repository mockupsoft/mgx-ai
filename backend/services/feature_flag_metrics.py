# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
from collections import Counter, deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureFlagMetricsSnapshot:
    total_lookups: int
    total_fallbacks: int
    total_errors: int
    p99_lookup_ms: float | None
    lookups_by_flag: dict[str, int]


class FeatureFlagMetrics:
    """In-process metrics for feature flag lookups.

    This intentionally avoids depending on a specific metrics backend.
    """

    def __init__(self, *, max_latency_samples: int = 2000) -> None:
        self._lock = threading.Lock()
        self._latency_ms: deque[float] = deque(maxlen=max_latency_samples)
        self._fallbacks = 0
        self._errors = 0
        self._lookups_by_flag: Counter[str] = Counter()

    def record_lookup(self, flag_name: str, *, duration_ms: float) -> None:
        with self._lock:
            self._lookups_by_flag[flag_name] += 1
            self._latency_ms.append(float(duration_ms))

    def record_fallback(self, flag_name: str) -> None:
        with self._lock:
            self._fallbacks += 1
            self._lookups_by_flag[str(flag_name)] += 1

    def record_error(self, flag_name: str) -> None:
        with self._lock:
            self._errors += 1
            self._lookups_by_flag[str(flag_name)] += 1

    def snapshot(self) -> FeatureFlagMetricsSnapshot:
        with self._lock:
            p99 = _p99(self._latency_ms)
            return FeatureFlagMetricsSnapshot(
                total_lookups=sum(self._lookups_by_flag.values()),
                total_fallbacks=self._fallbacks,
                total_errors=self._errors,
                p99_lookup_ms=p99,
                lookups_by_flag=dict(self._lookups_by_flag),
            )


def _p99(samples: deque[float]) -> float | None:
    if not samples:
        return None

    if len(samples) == 1:
        return float(samples[0])

    ordered = sorted(samples)
    k = max(0, min(len(ordered) - 1, int(round(0.99 * (len(ordered) - 1)))))
    try:
        return float(ordered[k])
    except (IndexError, ValueError, TypeError):
        return None
