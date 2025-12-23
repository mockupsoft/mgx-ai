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
- Supports per-phase profiling with file output to logs/performance/ and perf_reports/
"""

from __future__ import annotations

import contextvars
import time
import tracemalloc
try:
    import resource
except ImportError:
    # resource module is not available on Windows
    resource = None
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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
    min_s: float = float('inf')
    durations: List[float] = field(default_factory=list)

    def add(self, duration_s: float) -> None:
        self.count += 1
        self.total_s += duration_s
        if duration_s > self.max_s:
            self.max_s = duration_s
        if duration_s < self.min_s:
            self.min_s = duration_s
        # Store durations for percentile calculation (limit to last 1000)
        self.durations.append(duration_s)
        if len(self.durations) > 1000:
            self.durations = self.durations[-1000:]

    @property
    def avg_s(self) -> float:
        return self.total_s / self.count if self.count else 0.0
    
    @property
    def min_s_safe(self) -> float:
        return self.min_s if self.min_s != float('inf') else 0.0
    
    def percentile(self, p: float) -> float:
        """Calculate percentile (0.0-1.0)."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * p)
        index = min(index, len(sorted_durations) - 1)
        return sorted_durations[index]
    
    @property
    def p50(self) -> float:
        """50th percentile (median)."""
        return self.percentile(0.50)
    
    @property
    def p95(self) -> float:
        """95th percentile."""
        return self.percentile(0.95)
    
    @property
    def p99(self) -> float:
        """99th percentile."""
        return self.percentile(0.99)

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "total_s": self.total_s,
            "avg_s": self.avg_s,
            "min_s": self.min_s_safe,
            "max_s": self.max_s,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
        }


@dataclass
class PhaseSnapshot:
    """Memory and timing snapshot for a specific phase."""
    phase: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_s: float = 0.0
    rss_kb_before: int = 0
    rss_kb_after: int = 0
    tracemalloc_current_kb: float = 0.0
    tracemalloc_peak_kb: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_s": self.duration_s,
            "rss_kb_before": self.rss_kb_before,
            "rss_kb_after": self.rss_kb_after,
            "rss_kb_delta": self.rss_kb_after - self.rss_kb_before,
            "tracemalloc_current_kb": self.tracemalloc_current_kb,
            "tracemalloc_peak_kb": self.tracemalloc_peak_kb,
        }


class PerformanceProfiler:
    """Collect coarse-grained performance metrics for a single logical run."""

    def __init__(
        self,
        run_name: str,
        *,
        enable_tracemalloc: bool = False,
        enable_file_output: bool = False,
        output_dir: Optional[str] = None,
    ):
        self.run_name = run_name
        self.enable_tracemalloc = enable_tracemalloc
        self.enable_file_output = enable_file_output
        self.output_dir = output_dir or "logs/performance"

        self._token: Optional[contextvars.Token] = None
        self._start_s: Optional[float] = None
        self._end_s: Optional[float] = None

        self._started_tracemalloc: bool = False

        self.timers: Dict[str, TimerStat] = {}
        
        # Latency breakdown tracking
        self.latency_breakdown: Dict[str, Dict[str, float]] = {}
        self.slow_queries: List[Dict[str, Any]] = []
        self.slow_query_threshold_ms: float = 5000.0  # 5 seconds

        self.cache_hits: int = 0
        self.cache_misses: int = 0

        self.tracemalloc_current_b: int = 0
        self.tracemalloc_peak_b: int = 0

        self.rss_max_kb: int = 0
        
        # Per-phase profiling
        self.phase_snapshots: List[PhaseSnapshot] = []
        self._current_phase: Optional[PhaseSnapshot] = None

    def start(self) -> None:
        """Start profiling.

        This is intentionally synchronous so callers that are already inside an
        event loop (e.g. the CLI/team integration) can enable profiling without
        needing an async context manager.
        """

        if self._token is not None:
            return

        self._token = _active_profiler.set(self)
        self._start_s = time.perf_counter()
        self._end_s = None

        self._started_tracemalloc = False
        if self.enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_tracemalloc = True

    def stop(self) -> None:
        """Stop profiling and capture end-of-run memory/timing metrics."""

        self._end_s = time.perf_counter()

        if self.enable_tracemalloc and tracemalloc.is_tracing():
            current_b, peak_b = tracemalloc.get_traced_memory()
            self.tracemalloc_current_b = int(current_b)
            self.tracemalloc_peak_b = int(peak_b)
            if self._started_tracemalloc:
                tracemalloc.stop()

        try:
            if resource is not None:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                # On Linux ru_maxrss is KB; on macOS it's bytes. We normalize to KB.
                rss = int(usage.ru_maxrss)
                self.rss_max_kb = rss if rss > 10_000 else int(rss / 1024)
            else:
                self.rss_max_kb = 0
        except Exception:
            self.rss_max_kb = 0

        if self._token is not None:
            _active_profiler.reset(self._token)
            self._token = None

    async def __aenter__(self) -> "PerformanceProfiler":
        self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.stop()
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
    
    def record_latency_breakdown(
        self,
        operation: str,
        network_ms: float = 0.0,
        processing_ms: float = 0.0,
        llm_api_ms: float = 0.0,
        total_ms: Optional[float] = None,
    ) -> None:
        """
        Record detailed latency breakdown for an operation.
        
        Args:
            operation: Operation name (e.g., "llm_call", "database_query")
            network_ms: Network latency in milliseconds
            processing_ms: Processing time in milliseconds
            llm_api_ms: LLM API call time in milliseconds
            total_ms: Total time (calculated if not provided)
        """
        if total_ms is None:
            total_ms = network_ms + processing_ms + llm_api_ms
        
        self.latency_breakdown[operation] = {
            "network_ms": network_ms,
            "processing_ms": processing_ms,
            "llm_api_ms": llm_api_ms,
            "total_ms": total_ms,
        }
        
        # Track slow queries
        if total_ms > self.slow_query_threshold_ms:
            self.slow_queries.append({
                "operation": operation,
                "total_ms": total_ms,
                "network_ms": network_ms,
                "processing_ms": processing_ms,
                "llm_api_ms": llm_api_ms,
                "timestamp": time.time(),
            })
    
    def get_performance_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        Identify performance bottlenecks based on latency breakdown.
        
        Returns:
            List of bottleneck descriptions
        """
        bottlenecks = []
        
        for operation, breakdown in self.latency_breakdown.items():
            total = breakdown["total_ms"]
            if total == 0:
                continue
            
            # Calculate percentages
            network_pct = (breakdown["network_ms"] / total) * 100
            processing_pct = (breakdown["processing_ms"] / total) * 100
            llm_api_pct = (breakdown["llm_api_ms"] / total) * 100
            
            # Identify bottlenecks (>50% of total time)
            if network_pct > 50:
                bottlenecks.append({
                    "operation": operation,
                    "type": "network",
                    "percentage": network_pct,
                    "time_ms": breakdown["network_ms"],
                    "recommendation": "Consider connection pooling or reducing network round trips",
                })
            
            if processing_pct > 50:
                bottlenecks.append({
                    "operation": operation,
                    "type": "processing",
                    "percentage": processing_pct,
                    "time_ms": breakdown["processing_ms"],
                    "recommendation": "Optimize processing logic or use caching",
                })
            
            if llm_api_pct > 50:
                bottlenecks.append({
                    "operation": operation,
                    "type": "llm_api",
                    "percentage": llm_api_pct,
                    "time_ms": breakdown["llm_api_ms"],
                    "recommendation": "Consider using faster models or prompt optimization",
                })
        
        return sorted(bottlenecks, key=lambda x: x["percentage"], reverse=True)

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total) if total else 0.0

    def _get_rss_kb(self) -> int:
        """Get current RSS in KB."""
        try:
            if resource is not None:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                rss = int(usage.ru_maxrss)
                # On Linux ru_maxrss is KB; on macOS it's bytes. Normalize to KB.
                return rss if rss > 10_000 else int(rss / 1024)
            else:
                return 0
        except Exception:
            return 0
    
    def start_phase(self, phase_name: str) -> None:
        """Start profiling a specific phase."""
        if self._current_phase is not None:
            # End previous phase if it wasn't ended
            self.end_phase()
        
        snapshot = PhaseSnapshot(
            phase=phase_name,
            start_time=time.time(),
            rss_kb_before=self._get_rss_kb(),
        )
        self._current_phase = snapshot
    
    def end_phase(self) -> Optional[PhaseSnapshot]:
        """End the current phase and capture metrics."""
        if self._current_phase is None:
            return None
        
        snapshot = self._current_phase
        snapshot.end_time = time.time()
        snapshot.duration_s = snapshot.end_time - snapshot.start_time
        snapshot.rss_kb_after = self._get_rss_kb()
        
        if self.enable_tracemalloc and tracemalloc.is_tracing():
            current_b, peak_b = tracemalloc.get_traced_memory()
            snapshot.tracemalloc_current_kb = current_b / 1024.0
            snapshot.tracemalloc_peak_kb = peak_b / 1024.0
        
        self.phase_snapshots.append(snapshot)
        self._current_phase = None
        return snapshot

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
            "latency_breakdown": self.latency_breakdown,
            "slow_queries": self.slow_queries[-10:],  # Last 10 slow queries
            "bottlenecks": self.get_performance_bottlenecks(),
            "phases": [snapshot.to_dict() for snapshot in self.phase_snapshots],
        }
    
    def write_detailed_report(self, timestamp: Optional[str] = None) -> Path:
        """Write detailed performance report to logs/performance/<timestamp>.json"""
        if not self.enable_file_output:
            return None
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        detailed_file = output_path / f"{timestamp}.json"
        metrics = self.to_run_metrics()
        metrics["timestamp"] = timestamp
        
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        return detailed_file
    
    def write_summary_report(self) -> Path:
        """Write summary report to perf_reports/latest.json"""
        if not self.enable_file_output:
            return None
        
        output_path = Path("perf_reports")
        output_path.mkdir(parents=True, exist_ok=True)
        
        summary_file = output_path / "latest.json"
        
        # Create before/after snapshots
        before_snapshot = {
            "timestamp": self._start_s,
            "rss_kb": self.phase_snapshots[0].rss_kb_before if self.phase_snapshots else 0,
        }
        
        after_snapshot = {
            "timestamp": self._end_s,
            "rss_kb": self.phase_snapshots[-1].rss_kb_after if self.phase_snapshots else self.rss_max_kb,
            "tracemalloc_peak_kb": self.tracemalloc_peak_b / 1024.0,
        }
        
        summary = {
            "run_name": self.run_name,
            "before": before_snapshot,
            "after": after_snapshot,
            "total_duration_s": self.duration_s,
            "phases": [
                {
                    "phase": snapshot.phase,
                    "duration_s": snapshot.duration_s,
                    "rss_kb_delta": snapshot.rss_kb_after - snapshot.rss_kb_before,
                    "tracemalloc_peak_kb": snapshot.tracemalloc_peak_kb,
                }
                for snapshot in self.phase_snapshots
            ],
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": self.cache_hit_rate,
            },
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary_file


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
