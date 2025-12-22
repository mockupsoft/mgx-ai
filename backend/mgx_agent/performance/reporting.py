#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mgx_agent.performance.reporting

Helpers for performance/load-test report artifacts.

Outputs:
- perf_reports/latest.json (generated)
- perf_reports/before_after.md (generated)

Baseline:
- perf_reports/baseline.json (committed)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Optional


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _fmt_delta(curr: float, base: float) -> Tuple[str, str]:
    delta = curr - base
    pct = (delta / base * 100.0) if base else 0.0
    return f"{delta:+.4f}", f"{pct:+.2f}%"


def _row(metric: str, base: float, curr: float, unit: str = "") -> str:
    delta_s, delta_pct = _fmt_delta(curr, base)
    return f"| {metric} | {base:.4f}{unit} | {curr:.4f}{unit} | {delta_s}{unit} | {delta_pct} |"


def generate_before_after_md(baseline: Dict[str, Any], latest: Dict[str, Any]) -> str:
    b = baseline.get("results", {})
    l = latest.get("results", {})

    b_lat = b.get("latency_s", {})
    l_lat = l.get("latency_s", {})

    b_mem = b.get("memory_kb", {})
    l_mem = l.get("memory_kb", {})

    b_cache = b.get("cache", {})
    l_cache = l.get("cache", {})

    lines = [
        "# Performance report (baseline vs latest)",
        "",
        "## Latency (seconds)",
        "| Metric | Baseline | Latest | Δ | Δ% |",
        "|---|---:|---:|---:|---:|",
        _row("mean", float(b_lat.get("mean", 0.0)), float(l_lat.get("mean", 0.0))),
        _row("p50", float(b_lat.get("p50", 0.0)), float(l_lat.get("p50", 0.0))),
        _row("p95", float(b_lat.get("p95", 0.0)), float(l_lat.get("p95", 0.0))),
        _row("max", float(b_lat.get("max", 0.0)), float(l_lat.get("max", 0.0))),
        "",
        "## Throughput (runs/sec)",
        "| Metric | Baseline | Latest | Δ | Δ% |",
        "|---|---:|---:|---:|---:|",
        _row(
            "throughput", float(b.get("throughput_runs_per_s", 0.0)), float(l.get("throughput_runs_per_s", 0.0))
        ),
        "",
        "## Memory (KiB, tracemalloc)",
        "| Metric | Baseline | Latest | Δ | Δ% |",
        "|---|---:|---:|---:|---:|",
        _row(
            "tracemalloc_peak_kb",
            float(b_mem.get("tracemalloc_peak_kb_p95", 0.0)),
            float(l_mem.get("tracemalloc_peak_kb_p95", 0.0)),
            unit="",
        ),
        _row(
            "tracemalloc_peak_kb_max",
            float(b_mem.get("tracemalloc_peak_kb_max", 0.0)),
            float(l_mem.get("tracemalloc_peak_kb_max", 0.0)),
            unit="",
        ),
        "",
        "## Cache", 
        "| Metric | Baseline | Latest | Δ | Δ% |",
        "|---|---:|---:|---:|---:|",
        _row(
            "hit_rate",
            float(b_cache.get("hit_rate", 0.0)),
            float(l_cache.get("hit_rate", 0.0)),
        ),
    ]

    top = latest.get("results", {}).get("top_timers", [])
    if top:
        lines += [
            "",
            "## Top timers (latest)",
            "| Timer | Total (s) | Count | Avg (s) | Max (s) |",
            "|---|---:|---:|---:|---:|",
        ]
        for item in top:
            lines.append(
                f"| {item['name']} | {float(item['total_s']):.4f} | {int(item['count'])} | {float(item['avg_s']):.4f} | {float(item['max_s']):.4f} |"
            )

    return "\n".join(lines) + "\n"


def write_before_after_report(reports_dir: Path, baseline: Dict[str, Any], latest: Dict[str, Any]) -> Path:
    report_md = generate_before_after_md(baseline, latest)
    out = reports_dir / "before_after.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_md, encoding="utf-8")
    return out
