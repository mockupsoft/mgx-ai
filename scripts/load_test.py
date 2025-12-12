#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Load test harness.

Examples:
    python scripts/load_test.py --runs 20 --concurrency 10

This script runs the mocked MGXStyleTeam async pipeline concurrently and writes
performance artifacts into perf_reports/.

By default the script registers lightweight MetaGPT stubs (the same ones used in
pytest) so it can run without network/API keys.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _register_metagpt_stubs(repo_root: Path) -> None:
    if os.getenv("MGX_LOAD_TEST_USE_STUBS", "1") not in {"1", "true", "True"}:
        return

    sys.path.insert(0, str(repo_root))

    try:
        from tests.helpers.metagpt_stubs import (
            MockAction,
            MockRole,
            MockTeam,
            MockMessage,
            mock_logger,
            MockContext,
        )
    except Exception:
        return

    class MetaGPTStub:
        Action = MockAction
        Role = MockRole
        Team = MockTeam

    class MetaGPTActionsStub:
        Action = MockAction

    class MetaGPTRolesStub:
        Role = MockRole

    class MetaGPTTeamStub:
        Team = MockTeam

    class MetaGPTLogsStub:
        logger = mock_logger

    class MetaGPTTypesStub:
        Message = MockMessage

    class MetaGPTSchemaStub:
        Message = MockMessage

    class MetaGPTContextStub:
        Context = MockContext

    class MetaGPTConfigStub:
        class Config:
            @staticmethod
            def from_home(filename: str):
                mock_config = MockContext()
                mock_config.model = f"mock-model-{filename}"
                return mock_config

    sys.modules["metagpt"] = MetaGPTStub()
    sys.modules["metagpt.actions"] = MetaGPTActionsStub()
    sys.modules["metagpt.roles"] = MetaGPTRolesStub()
    sys.modules["metagpt.team"] = MetaGPTTeamStub()
    sys.modules["metagpt.logs"] = MetaGPTLogsStub()
    sys.modules["metagpt.types"] = MetaGPTTypesStub()
    sys.modules["metagpt.schema"] = MetaGPTSchemaStub()
    sys.modules["metagpt.context"] = MetaGPTContextStub()
    sys.modules["metagpt.config"] = MetaGPTConfigStub()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mocked MGXStyleTeam load test")
    p.add_argument("--runs", type=int, default=10, help="Number of concurrent MGXStyleTeam runs")
    p.add_argument("--concurrency", type=int, default=5, help="Max in-flight runs")
    p.add_argument("--llm-latency", type=float, default=0.01, help="Simulated LLM latency per round (seconds)")
    p.add_argument(
        "--reports-dir",
        type=str,
        default="perf_reports",
        help="Where to write perf artifacts (baseline.json, latest.json, before_after.md)",
    )
    p.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite perf_reports/baseline.json with the latest metrics",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _register_metagpt_stubs(repo_root)

    from mgx_agent.performance.load_harness import Scenario, run_load_test
    from mgx_agent.performance.reporting import write_json

    reports_dir = (repo_root / args.reports_dir).resolve()
    baseline_path = reports_dir / "baseline.json"

    scenario = Scenario(
        runs=args.runs,
        concurrency=args.concurrency,
        llm_latency_s=args.llm_latency,
    )

    latest = asyncio.run(run_load_test(scenario=scenario, reports_dir=reports_dir, baseline_path=baseline_path))

    if args.update_baseline:
        write_json(baseline_path, latest)

    results = latest["results"]
    print("\n=== Load test complete ===")
    print(f"runs: {scenario.runs}  concurrency: {scenario.concurrency}")
    print(f"wall_time_s: {results['wall_time_s']:.4f}")
    print(f"throughput_runs_per_s: {results['throughput_runs_per_s']:.2f}")
    print(f"latency_p95_s: {results['latency_s']['p95']:.4f}")
    print(f"cache_hit_rate: {results['cache']['hit_rate']:.2%}")
    print(f"\nArtifacts: {reports_dir}")


if __name__ == "__main__":
    main()
