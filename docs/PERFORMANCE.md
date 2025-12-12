# Performance & Profiling Guide (Phase 4)

This document describes the Phase 4 performance features: async execution patterns, response caching configuration, profiling/reporting, and the load-test workflow used in CI.

## Contents

- [Quick start](#quick-start)
- [Configuration flags](#configuration-flags)
- [Async patterns](#async-patterns)
- [Caching](#caching)
- [Profiling](#profiling)
- [Load testing & CI workflow](#load-testing--ci-workflow)
- [Best practices](#best-practices)

## Quick start

### Run the default test suite (performance tests excluded)

Performance tests are excluded by default via `pytest.ini` (`-m "not performance"`).

```bash
pytest
```

### Run the performance suite locally

Because `pytest.ini` defines `addopts` that excludes performance tests, override it:

```bash
pytest -o addopts='' -m performance tests/performance -v
```

Artifacts written by the performance suite:

- `perf_reports/latest.json` (generated)
- `perf_reports/before_after.md` (generated)

### Run the standalone load-test harness

```bash
python scripts/load_test.py --runs 20 --concurrency 10 --llm-latency 0.01
```

To update the committed baseline (do this only during a performance-baseline update / release process):

```bash
python scripts/load_test.py --runs 20 --concurrency 10 --llm-latency 0.01 --update-baseline
# commit perf_reports/baseline.json
```

## Configuration flags

All performance-related configuration is in `mgx_agent.config.TeamConfig`.

### Caching flags

| Flag | Type | Default | Notes |
|---|---|---:|---|
| `enable_caching` | bool | `True` | Master switch for caching |
| `cache_backend` | str | `"memory"` | `none` \| `memory` \| `redis` |
| `cache_max_entries` | int | `1024` | In-memory LRU capacity |
| `cache_ttl_seconds` | int | `3600` | TTL in seconds (0 disables TTL in-memory) |
| `redis_url` | str\|None | `None` | Required when `cache_backend="redis"` |
| `cache_log_hits` | bool | `False` | Log cache hits (noisy) |
| `cache_log_misses` | bool | `False` | Log cache misses (noisy) |

Example:

```python
from mgx_agent import MGXStyleTeam, TeamConfig

config = TeamConfig(
    enable_caching=True,
    cache_backend="memory",
    cache_max_entries=4096,
    cache_ttl_seconds=3600,
)
team = MGXStyleTeam(config=config)
```

Redis example:

```python
config = TeamConfig(
    enable_caching=True,
    cache_backend="redis",
    redis_url="redis://localhost:6379/0",
    cache_ttl_seconds=3600,
)
```

### Profiling flags

| Flag | Type | Default | Notes |
|---|---|---:|---|
| `enable_profiling` | bool | `False` | Enables the team profiler integration |
| `enable_profiling_tracemalloc` | bool | `False` | Enables tracemalloc-based memory sampling |

CLI flags:

```bash
python -m mgx_agent.cli --profile
python -m mgx_agent.cli --profile --profile-memory
```

### Environment variables

| Variable | Meaning |
|---|---|
| `MGX_GLOBAL_CACHE=1` | Use a shared in-memory cache instance across teams (used by the load test harness for stable hit-rate under concurrency) |

## Async patterns

Phase 4 introduces async utilities in `mgx_agent.performance.async_tools`:

- `AsyncTimer(name)`: async context manager that records span timings (and forwards to an active profiler if present)
- `bounded_gather(*awaitables, max_concurrent=N)`: `asyncio.gather` with concurrency limits
- `with_timeout(seconds)`: decorator around `asyncio.wait_for`
- `run_in_thread(func, *args, **kwargs)`: offload blocking work to the default threadpool

Example:

```python
from mgx_agent.performance import AsyncTimer, bounded_gather

async def fetch_all(urls: list[str]):
    async with AsyncTimer("fetch_all"):
        return await bounded_gather(*(fetch(u) for u in urls), max_concurrent=10)
```

## Caching

### What is cached?

The hottest path is plan generation (`AnalyzeTask + DraftPlan`) in `MGXStyleTeam.analyze_and_plan()`. The team also exposes a generic helper:

- `MGXStyleTeam.cached_llm_call(...)`

### Cache backends

- **none**: `NullCache` (no caching)
- **memory**: `InMemoryLRUTTLCache` (thread-safe, LRU + TTL)
- **redis**: `RedisCache` (optional dependency: `redis`)

### Operational helpers

`MGXStyleTeam` provides runtime cache utilities:

- `cache_inspect()` / `inspect_cache()`
- `cache_clear()` / `clear_cache()`
- `cache_warm()` / `warm_cache()`

## Profiling

### Using the profiler directly

For accurate async span tracking, use `PerformanceProfiler` as an async context manager:

```python
from mgx_agent.performance.profiler import PerformanceProfiler
from mgx_agent.performance.async_tools import AsyncTimer

async with PerformanceProfiler(
    "my_run",
    enable_tracemalloc=True,
    enable_file_output=True,
) as prof:
    async with AsyncTimer("phase_a"):
        await do_work()

# prof.to_run_metrics() -> dict
```

### Team-integrated profiling

When `TeamConfig(enable_profiling=True)` is enabled, `MGXStyleTeam._start_profiler()` / `_end_profiler()` can be used to produce report files.

Generated artifacts:

- `logs/performance/<timestamp>.json` (detailed)
- `perf_reports/latest.json` (summary)

## Load testing & CI workflow

### Baseline and regression gating

- `perf_reports/baseline.json` is committed and acts as the regression baseline.
- The performance test generates `perf_reports/latest.json` and `perf_reports/before_after.md`.
- CI uploads `perf_reports/` as artifacts.

### CI job

The GitHub Actions workflow includes a dedicated `performance` job that:

1. Runs `pytest -o addopts='' -m performance tests/performance`
2. Uploads `perf_reports` artifacts
3. Publishes the before/after table into the job summary

## Best practices

- Keep performance tests deterministic: mock latency, avoid real network/LLM calls.
- Use generous budgets in CI and rely on the baseline regression checks to detect slowdowns.
- Only update `perf_reports/baseline.json` intentionally (release cadence) and accompany it with an updated [PERFORMANCE_REPORT.md](../PERFORMANCE_REPORT.md).
- Prefer `bounded_gather` over unbounded `asyncio.gather` to avoid resource spikes.
- Offload blocking file/system operations via `run_in_thread()`.
