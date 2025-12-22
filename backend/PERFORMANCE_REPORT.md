# Performance Report (Phase 4)

This file is the release-facing performance report template + the current snapshot for this repository.

- Guide: [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
- Baseline source: `perf_reports/baseline.json` (committed)
- Latest source: produced by `pytest -m performance` or `python scripts/load_test.py`

## Report metadata

- **Date:** 2025-12-12
- **Scope:** mocked MGXStyleTeam workflow (deterministic CI harness)
- **Scenario:** `runs=10`, `concurrency=5`, `llm_latency_s=0.01`

## Budgets / gates

These are the budgets enforced in `tests/performance/test_load_suite.py`:

- `latency_s.p95` ≤ **2.0s**
- `memory_kb.tracemalloc_peak_kb_p95` ≤ **75,000 KiB**
- `cache.hit_rate` ≥ **0.8**
- `throughput_runs_per_s` ≥ **2.0**

In addition, regression is checked against `perf_reports/baseline.json` with generous multipliers to tolerate CI variance.

## Baseline vs latest

The table below is the required release artifact: baseline vs latest with deltas.

> Note: the baseline numbers in `perf_reports/baseline.json` are intentionally conservative (stable guard-rails). The latest numbers are produced by the deterministic mock harness and are expected to vary slightly by machine/CI runner.

# Performance report (baseline vs latest)

## Latency (seconds)
| Metric | Baseline | Latest | Δ | Δ% |
|---|---:|---:|---:|---:|
| mean | 0.5000 | 0.0367 | -0.4633 | -92.65% |
| p50 | 0.5000 | 0.0369 | -0.4631 | -92.62% |
| p95 | 1.0000 | 0.0397 | -0.9603 | -96.03% |
| max | 1.2000 | 0.0398 | -1.1602 | -96.68% |

## Throughput (runs/sec)
| Metric | Baseline | Latest | Δ | Δ% |
|---|---:|---:|---:|---:|
| throughput | 10.0000 | 129.2571 | +119.2571 | +1192.57% |

## Memory (KiB, tracemalloc)
| Metric | Baseline | Latest | Δ | Δ% |
|---|---:|---:|---:|---:|
| tracemalloc_peak_kb | 30000.0000 | 261.8809 | -29738.1191 | -99.13% |
| tracemalloc_peak_kb_max | 40000.0000 | 261.8809 | -39738.1191 | -99.35% |

## Cache
| Metric | Baseline | Latest | Δ | Δ% |
|---|---:|---:|---:|---:|
| hit_rate | 1.0000 | 1.0000 | +0.0000 | +0.00% |

## Top timers (latest)
| Timer | Total (s) | Count | Avg (s) | Max (s) |
|---|---:|---:|---:|---:|
| main_development_round | 0.3217 | 10 | 0.0322 | 0.0338 |
| final_operations | 0.0263 | 10 | 0.0026 | 0.0039 |
| cleanup_after_main | 0.0134 | 10 | 0.0013 | 0.0027 |
| analyze_and_plan_cache_hit | 0.0002 | 10 | 0.0000 | 0.0000 |

## How to update this report for a release

1. Run the performance suite locally:

   ```bash
   pytest -o addopts='' -m performance tests/performance -v
   ```

2. Copy the generated `perf_reports/before_after.md` content into this file.
3. If you intentionally update baselines, regenerate and commit:

   ```bash
   python scripts/load_test.py --runs 20 --concurrency 10 --llm-latency 0.01 --update-baseline
   ```

4. Open a PR that includes:
   - `perf_reports/baseline.json`
   - this `PERFORMANCE_REPORT.md`
   - any budget adjustments (if required)
