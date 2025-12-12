#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mgx_agent.performance.profiler

A lightweight async-aware profiler used by the performance/load-test suite.

The goal is not to be a full statistical profiler. Instead, it aggregates
high-level timer spans (recorded via :class:`mgx_agent.performance.AsyncTimer`)
plus coarse memory/cache counters so tests can gate on stable performance
budgets.

Design notes:
- Uses a ContextVar so nested async calls can report timings without passing the
  profiler object around.
- Uses tracemalloc for allocation/peak memory since RSS is often noisy in CI.
"""

from __future__ import annotations

import contextvars
import time
import tracemalloc
import resource
from dataclasses import dataclass
from typing import Dict, Optional, Any, List


_active_profiler: contextvars.ContextVar[Optional["PerformanceProfiler"]] = contextvars.ContextVar(
    "mgx_agent_active_profiler", default=None
)


def get_active_profiler() -> Optional["PerformanceProfiler"]:
    return _active_profiler.get()


@dataclass
class TimerStat:
    count: int = 0
    total_s: float = 0.0
    max_s: float = 0.0

    def add(self, duration_s: float) -> None:
        self.count += 1
        self.total_s += duration_s
        if duration_s > self.max_s:
            self.max_s = duration_s

    @property
    def avg_s(self) -> float:
        return self.total_s / self.count if self.count else 0.0

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "total_s": self.total_s,
            "avg_s": self.avg_s,
            "max_s": self.max_s,
        }


class PerformanceProfiler:
    """Collect coarse-grained performance metrics for a single logical run."""

    def __init__(
        self,
        run_name: str,
        *,
        enable_tracemalloc: bool = False,
    ):
        self.run_name = run_name
        self.enable_tracemalloc = enable_tracemalloc

        self._token: Optional[contextvars.Token] = None
        self._start_s: Optional[float] = None
        self._end_s: Optional[float] = None

        self._started_tracemalloc: bool = False

        self.timers: Dict[str, TimerStat] = {}

        self.cache_hits: int = 0
        self.cache_misses: int = 0

        self.tracemalloc_current_b: int = 0
        self.tracemalloc_peak_b: int = 0

        self.rss_max_kb: int = 0

    async def __aenter__(self) -> "PerformanceProfiler":
        self._token = _active_profiler.set(self)
        self._start_s = time.perf_counter()

        self._started_tracemalloc = False
        if self.enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_tracemalloc = True

        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._end_s = time.perf_counter()

        if self.enable_tracemalloc and tracemalloc.is_tracing():
            current_b, peak_b = tracemalloc.get_traced_memory()
            self.tracemalloc_current_b = int(current_b)
            self.tracemalloc_peak_b = int(peak_b)
            if self._started_tracemalloc:
                tracemalloc.stop()

        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            # On Linux ru_maxrss is KB; on macOS it's bytes. We normalize to KB.
            rss = int(usage.ru_maxrss)
            self.rss_max_kb = rss if rss > 10_000 else int(rss / 1024)
        except Exception:
            self.rss_max_kb = 0

        if self._token is not None:
            _active_profiler.reset(self._token)

        return False

    @property
    def duration_s(self) -> float:
        if self._start_s is None:
            return 0.0
        end = self._end_s if self._end_s is not None else time.perf_counter()
        return end - self._start_s

    def record_timer(self, name: str, duration_s: float) -> None:
        stat = self.timers.get(name)
        if stat is None:
            stat = TimerStat()
            self.timers[name] = stat
        stat.add(duration_s)

    def record_cache(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total) if total else 0.0

    def to_run_metrics(self) -> dict:
        return {
            "run_name": self.run_name,
            "duration_s": self.duration_s,
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": self.cache_hit_rate,
            },
            "memory": {
                "tracemalloc_current_kb": self.tracemalloc_current_b / 1024.0,
                "tracemalloc_peak_kb": self.tracemalloc_peak_b / 1024.0,
                "rss_max_kb": self.rss_max_kb,
            },
            "timers": {name: stat.to_dict() for name, stat in self.timers.items()},
        }


def merge_timer_stats(runs: List[PerformanceProfiler]) -> Dict[str, TimerStat]:
    merged: Dict[str, TimerStat] = {}
    for prof in runs:
        for name, stat in prof.timers.items():
            m = merged.get(name)
            if m is None:
                m = TimerStat()
                merged[name] = m
            # Preserve count/total/max without biasing averages.
            m.count += stat.count
            m.total_s += stat.total_s
            if stat.max_s > m.max_s:
                m.max_s = stat.max_s
    return merged
