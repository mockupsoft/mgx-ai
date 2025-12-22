# -*- coding: utf-8 -*-
"""Performance/load tests.

Run explicitly:
    pytest tests/performance -m performance

These tests are excluded from the default suite via pytest.ini addopts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mgx_agent.performance.load_harness import Scenario, run_load_test
from mgx_agent.performance.reporting import read_json


@pytest.mark.performance
@pytest.mark.asyncio
async def test_mgxstyleteam_concurrent_load_generates_reports_and_meets_budgets():
    repo_root = Path(__file__).resolve().parents[2]
    reports_dir = repo_root / "perf_reports"
    baseline_path = reports_dir / "baseline.json"

    baseline = read_json(baseline_path)
    scenario_data = baseline.get("scenario", {})
    scenario = Scenario(
        runs=int(scenario_data.get("runs", 10)),
        concurrency=int(scenario_data.get("concurrency", 5)),
        llm_latency_s=float(scenario_data.get("llm_latency_s", 0.01)),
        task=str(scenario_data.get("task", "Write a tiny pure function and unit tests")),
    )

    latest = await run_load_test(
        scenario=scenario,
        reports_dir=reports_dir,
        baseline_path=baseline_path,
    )

    assert (reports_dir / "latest.json").exists()
    assert (reports_dir / "before_after.md").exists()

    results = latest["results"]

    # Absolute budgets (kept generous for CI stability; tighten as the pipeline matures).
    assert results["latency_s"]["p95"] <= 2.0
    assert results["memory_kb"]["tracemalloc_peak_kb_p95"] <= 75_000.0
    assert results["cache"]["hit_rate"] >= 0.8
    assert results["throughput_runs_per_s"] >= 2.0

    # Regression checks vs committed baseline (allow some noise).
    b = baseline["results"]
    assert results["latency_s"]["p95"] <= float(b["latency_s"]["p95"]) * 1.75
    assert results["memory_kb"]["tracemalloc_peak_kb_p95"] <= float(
        b["memory_kb"]["tracemalloc_peak_kb_p95"]
    ) * 1.75
    assert results["cache"]["hit_rate"] >= float(b["cache"]["hit_rate"]) - 0.25
