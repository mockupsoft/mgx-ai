#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mgx_agent.performance.load_harness

Async load-test harness for stressing the MGXStyleTeam workflow using mocked
MetaGPT/LLM components.

This is intentionally lightweight and deterministic so it can run in CI.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from mgx_agent.config import TeamConfig
from mgx_agent.performance.profiler import PerformanceProfiler, merge_timer_stats
from mgx_agent.performance.reporting import write_json, read_json, write_before_after_report


@dataclass
class Scenario:
    runs: int = 10
    concurrency: int = 5
    llm_latency_s: float = 0.01
    task: str = "Write a tiny pure function and unit tests"


class MockPlanMessage:
    def __init__(self, content: str):
        self.role = "TeamLeader"
        self.content = content


class MockMike:
    """Mock TeamLeader role that returns a stable plan."""

    name = "Mike"
    profile = "TeamLeader"

    def __init__(self, *, latency_s: float = 0.01, complexity: str = "XS"):
        self.latency_s = latency_s
        self.complexity = complexity
        # Minimal attributes used by adapter/cleanup/token calculation paths.
        self.rc = type("RC", (), {"memory": None})()

    def complete_planning(self) -> None:
        return None

    async def analyze_task(self, task: str) -> MockPlanMessage:
        await asyncio.sleep(self.latency_s)
        # Keep JSON envelope consistent with MGXStyleTeam._get_complexity_from_plan
        content = (
            "---JSON_START---\n"
            f"{{\n  \"complexity\": \"{self.complexity}\",\n  \"task\": \"{task}\"\n}}\n"
            "---JSON_END---\n\n"
            "PLAN:\n- Step 1: Implement\n- Step 2: Test\n"
        )
        return MockPlanMessage(content=content)


class MockRole:
    def __init__(self, name: str, profile: str):
        self.name = name
        self.profile = profile
        self.rc = type("RC", (), {"memory": None})()

    def complete_planning(self) -> None:
        return None


class MockEnv:
    def __init__(self):
        self.roles: Dict[str, Any] = {}

    def publish_message(self, msg: Any) -> None:
        return None


class MockMetaGPTTeam:
    """Mock Team that simulates async work via sleep."""

    def __init__(self, *, llm_latency_s: float = 0.01):
        self.llm_latency_s = llm_latency_s
        self.env = MockEnv()

    def hire(self, roles: Sequence[Any]) -> None:
        for r in roles:
            self.env.roles[getattr(r, "name", str(id(r)))] = r

    def invest(self, investment: float) -> None:
        return None

    async def run(self, n_round: int = 1, **kwargs) -> str:
        await asyncio.sleep(self.llm_latency_s * max(1, int(n_round)))
        return "ok"


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * p
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


async def run_single_team(
    *,
    run_id: int,
    scenario: Scenario,
) -> PerformanceProfiler:
    from mgx_agent.team import MGXStyleTeam

    config = TeamConfig(
        max_rounds=2,
        max_revision_rounds=0,
        max_memory_size=50,
        enable_caching=True,
        enable_streaming=False,
        enable_progress_bar=False,
        enable_metrics=False,
        enable_memory_cleanup=True,
        human_reviewer=False,
        auto_approve_plan=True,
        cache_ttl_seconds=3600,
    )

    mock_team = MockMetaGPTTeam(llm_latency_s=scenario.llm_latency_s)
    roles = [
        MockMike(latency_s=scenario.llm_latency_s, complexity="XS"),
        MockRole("Alex", "Engineer"),
        MockRole("Bob", "Tester"),
        MockRole("Charlie", "Reviewer"),
    ]

    mgx = MGXStyleTeam(
        config=config,
        team_override=mock_team,
        roles_override=roles,
        output_dir_base=None,
    )

    # Make final collection deterministic and avoid filesystem I/O.
    mgx._collect_results = lambda: "summary"  # type: ignore[method-assign]

    async with PerformanceProfiler(f"run_{run_id}") as prof:
        await mgx.analyze_and_plan(scenario.task)
        await mgx.execute(n_round=2, max_revision_rounds=0)

    return prof


async def run_load_test(
    *,
    scenario: Scenario,
    reports_dir: Path,
    baseline_path: Optional[Path] = None,
) -> Dict[str, Any]:
    # Ensure consistent cache behavior across runs.
    import os
    from mgx_agent.team import MGXStyleTeam

    os.environ["MGX_GLOBAL_CACHE"] = "1"
    MGXStyleTeam._GLOBAL_ANALYSIS_CACHE.clear()
    # Prewarm cache once to enable stable cache hit-rate measurements under concurrency.
    await run_single_team(run_id=-1, scenario=scenario)

    import tracemalloc

    started_here = False
    if not tracemalloc.is_tracing():
        tracemalloc.start()
        started_here = True
    tracemalloc.reset_peak()

    start = time.perf_counter()

    semaphore = asyncio.Semaphore(scenario.concurrency)

    async def _bounded(i: int) -> PerformanceProfiler:
        async with semaphore:
            return await run_single_team(run_id=i, scenario=scenario)

    profilers = await asyncio.gather(*[_bounded(i) for i in range(scenario.runs)])

    wall_s = time.perf_counter() - start

    current_b, peak_b = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)
    if started_here and tracemalloc.is_tracing():
        tracemalloc.stop()
    mem_peak_kb = peak_b / 1024.0

    durations = [p.duration_s for p in profilers]
    cache_hits = sum(p.cache_hits for p in profilers)
    cache_misses = sum(p.cache_misses for p in profilers)

    merged_timers = merge_timer_stats(profilers)
    top_timers = sorted(
        (
            {
                "name": name,
                "total_s": stat.total_s,
                "count": stat.count,
                "avg_s": stat.avg_s,
                "max_s": stat.max_s,
            }
            for name, stat in merged_timers.items()
        ),
        key=lambda x: x["total_s"],
        reverse=True,
    )[:10]

    latest: Dict[str, Any] = {
        "schema_version": 1,
        "generated_at_s": time.time(),
        "scenario": {
            "runs": scenario.runs,
            "concurrency": scenario.concurrency,
            "llm_latency_s": scenario.llm_latency_s,
            "task": scenario.task,
        },
        "results": {
            "total_runs": scenario.runs,
            "wall_time_s": wall_s,
            "throughput_runs_per_s": (scenario.runs / wall_s) if wall_s else 0.0,
            "latency_s": {
                "mean": sum(durations) / len(durations) if durations else 0.0,
                "p50": _percentile(durations, 0.50),
                "p95": _percentile(durations, 0.95),
                "max": max(durations) if durations else 0.0,
            },
            "memory_kb": {
                "tracemalloc_peak_kb_p95": mem_peak_kb,
                "tracemalloc_peak_kb_max": mem_peak_kb,
            },
            "cache": {
                "hits": cache_hits,
                "misses": cache_misses,
                "hit_rate": (cache_hits / (cache_hits + cache_misses))
                if (cache_hits + cache_misses)
                else 0.0,
            },
            "top_timers": top_timers,
        },
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    latest_path = reports_dir / "latest.json"
    write_json(latest_path, latest)

    if baseline_path is not None and baseline_path.exists():
        baseline = read_json(baseline_path)
        write_before_after_report(reports_dir, baseline, latest)

    return latest
