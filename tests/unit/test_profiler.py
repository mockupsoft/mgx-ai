# -*- coding: utf-8 -*-
"""Unit tests for performance profiler."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from mgx_agent.performance.profiler import (
    PerformanceProfiler,
    PhaseSnapshot,
    TimerStat,
    get_active_profiler,
)


class TestTimerStat:
    """Test TimerStat dataclass."""
    
    def test_add_duration(self):
        stat = TimerStat()
        stat.add(1.0)
        stat.add(2.0)
        stat.add(3.0)
        
        assert stat.count == 3
        assert stat.total_s == 6.0
        assert stat.max_s == 3.0
        assert stat.avg_s == 2.0
    
    def test_to_dict(self):
        stat = TimerStat()
        stat.add(1.5)
        stat.add(2.5)
        
        data = stat.to_dict()
        assert data["count"] == 2
        assert data["total_s"] == 4.0
        assert data["avg_s"] == 2.0
        assert data["max_s"] == 2.5


class TestPhaseSnapshot:
    """Test PhaseSnapshot dataclass."""
    
    def test_phase_snapshot_creation(self):
        snapshot = PhaseSnapshot(
            phase="test_phase",
            start_time=100.0,
            end_time=105.0,
            duration_s=5.0,
            rss_kb_before=1000,
            rss_kb_after=1500,
        )
        
        assert snapshot.phase == "test_phase"
        assert snapshot.duration_s == 5.0
        assert snapshot.rss_kb_after - snapshot.rss_kb_before == 500
    
    def test_to_dict(self):
        snapshot = PhaseSnapshot(
            phase="test_phase",
            start_time=100.0,
            end_time=105.0,
            duration_s=5.0,
            rss_kb_before=1000,
            rss_kb_after=1500,
            tracemalloc_peak_kb=2000.0,
        )
        
        data = snapshot.to_dict()
        assert data["phase"] == "test_phase"
        assert data["duration_s"] == 5.0
        assert data["rss_kb_delta"] == 500
        assert data["tracemalloc_peak_kb"] == 2000.0


class TestPerformanceProfiler:
    """Test PerformanceProfiler class."""
    
    @pytest.mark.asyncio
    async def test_profiler_context_manager(self):
        """Test profiler can be used as async context manager."""
        profiler = PerformanceProfiler("test_run")
        
        async with profiler as prof:
            assert prof is profiler
            assert prof._start_s is not None
            await asyncio.sleep(0.01)
        
        assert profiler._end_s is not None
        assert profiler.duration_s > 0
    
    @pytest.mark.asyncio
    async def test_profiler_active_context(self):
        """Test profiler sets active context."""
        profiler = PerformanceProfiler("test_run")
        
        assert get_active_profiler() is None
        
        async with profiler:
            assert get_active_profiler() is profiler
        
        assert get_active_profiler() is None
    
    @pytest.mark.asyncio
    async def test_record_timer(self):
        """Test timer recording."""
        profiler = PerformanceProfiler("test_run")
        
        async with profiler:
            profiler.record_timer("operation_1", 1.0)
            profiler.record_timer("operation_1", 2.0)
            profiler.record_timer("operation_2", 3.0)
        
        assert "operation_1" in profiler.timers
        assert "operation_2" in profiler.timers
        assert profiler.timers["operation_1"].count == 2
        assert profiler.timers["operation_1"].total_s == 3.0
        assert profiler.timers["operation_2"].count == 1
    
    @pytest.mark.asyncio
    async def test_record_cache(self):
        """Test cache recording."""
        profiler = PerformanceProfiler("test_run")
        
        async with profiler:
            profiler.record_cache(True)
            profiler.record_cache(True)
            profiler.record_cache(False)
        
        assert profiler.cache_hits == 2
        assert profiler.cache_misses == 1
        assert profiler.cache_hit_rate == pytest.approx(0.666, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_phase_profiling(self):
        """Test per-phase profiling."""
        profiler = PerformanceProfiler("test_run", enable_tracemalloc=False)
        
        async with profiler:
            profiler.start_phase("phase_1")
            await asyncio.sleep(0.01)
            profiler.end_phase()
            
            profiler.start_phase("phase_2")
            await asyncio.sleep(0.01)
            profiler.end_phase()
        
        assert len(profiler.phase_snapshots) == 2
        assert profiler.phase_snapshots[0].phase == "phase_1"
        assert profiler.phase_snapshots[1].phase == "phase_2"
        assert profiler.phase_snapshots[0].duration_s > 0
        assert profiler.phase_snapshots[1].duration_s > 0
    
    @pytest.mark.asyncio
    async def test_auto_end_phase(self):
        """Test automatic phase ending when starting new phase."""
        profiler = PerformanceProfiler("test_run")
        
        async with profiler:
            profiler.start_phase("phase_1")
            await asyncio.sleep(0.01)
            
            # Start new phase without ending previous
            profiler.start_phase("phase_2")
            await asyncio.sleep(0.01)
            profiler.end_phase()
        
        assert len(profiler.phase_snapshots) == 2
        assert profiler.phase_snapshots[0].phase == "phase_1"
        assert profiler.phase_snapshots[1].phase == "phase_2"
    
    @pytest.mark.asyncio
    async def test_to_run_metrics(self):
        """Test run metrics generation."""
        profiler = PerformanceProfiler("test_run")
        
        async with profiler:
            profiler.record_timer("op_1", 1.0)
            profiler.record_cache(True)
            profiler.start_phase("phase_1")
            await asyncio.sleep(0.01)
            profiler.end_phase()
        
        metrics = profiler.to_run_metrics()
        
        assert metrics["run_name"] == "test_run"
        assert metrics["duration_s"] > 0
        assert "cache" in metrics
        assert "memory" in metrics
        assert "timers" in metrics
        assert "phases" in metrics
        assert len(metrics["phases"]) == 1
    
    @pytest.mark.asyncio
    async def test_file_output_disabled(self):
        """Test that file output can be disabled."""
        profiler = PerformanceProfiler(
            "test_run",
            enable_file_output=False,
        )
        
        async with profiler:
            profiler.start_phase("phase_1")
            await asyncio.sleep(0.01)
            profiler.end_phase()
        
        # Should return None when file output is disabled
        assert profiler.write_detailed_report() is None
        assert profiler.write_summary_report() is None
    
    @pytest.mark.asyncio
    async def test_file_output_enabled(self, tmp_path):
        """Test detailed and summary report generation."""
        output_dir = tmp_path / "logs" / "performance"
        profiler = PerformanceProfiler(
            "test_run",
            enable_file_output=True,
            output_dir=str(output_dir),
        )
        
        async with profiler:
            profiler.start_phase("phase_1")
            await asyncio.sleep(0.01)
            profiler.end_phase()
        
        # Write detailed report
        timestamp = "test_20240101_120000"
        detailed_file = profiler.write_detailed_report(timestamp)
        
        assert detailed_file is not None
        assert detailed_file.exists()
        assert detailed_file.name == f"{timestamp}.json"
        
        # Verify content
        with open(detailed_file, 'r') as f:
            data = json.load(f)
        
        assert data["run_name"] == "test_run"
        assert data["timestamp"] == timestamp
        assert "phases" in data
        assert len(data["phases"]) == 1
    
    @pytest.mark.asyncio
    async def test_summary_report_generation(self, tmp_path, monkeypatch):
        """Test summary report to perf_reports/latest.json."""
        # Change working directory to tmp_path
        monkeypatch.chdir(tmp_path)
        
        profiler = PerformanceProfiler(
            "test_run",
            enable_file_output=True,
        )
        
        async with profiler:
            profiler.start_phase("analyze_and_plan")
            await asyncio.sleep(0.01)
            profiler.end_phase()
            
            profiler.start_phase("execute")
            await asyncio.sleep(0.01)
            profiler.end_phase()
        
        summary_file = profiler.write_summary_report()
        
        assert summary_file is not None
        assert summary_file.exists()
        assert summary_file.name == "latest.json"
        
        # Verify content
        with open(summary_file, 'r') as f:
            data = json.load(f)
        
        assert data["run_name"] == "test_run"
        assert "before" in data
        assert "after" in data
        assert "phases" in data
        assert len(data["phases"]) == 2
        assert data["phases"][0]["phase"] == "analyze_and_plan"
        assert data["phases"][1]["phase"] == "execute"


@pytest.mark.asyncio
async def test_profiler_no_memory_leaks():
    """Test profiler doesn't keep references after exit."""
    profiler = PerformanceProfiler("test_run")
    
    async with profiler:
        pass
    
    # Active profiler should be cleared
    assert get_active_profiler() is None


@pytest.mark.asyncio
async def test_profiler_with_tracemalloc():
    """Test profiler with tracemalloc enabled."""
    profiler = PerformanceProfiler(
        "test_run",
        enable_tracemalloc=True,
    )
    
    async with profiler:
        # Allocate some memory
        data = [i for i in range(10000)]
        profiler.start_phase("memory_intensive")
        more_data = [i * 2 for i in range(10000)]
        profiler.end_phase()
    
    # Should have memory stats
    assert profiler.tracemalloc_peak_b > 0
    assert len(profiler.phase_snapshots) == 1
    # Note: tracemalloc values may be 0 in phases if memory wasn't significantly allocated


@pytest.mark.asyncio
async def test_profiler_expected_keys_in_report():
    """Test that profiling reports contain expected keys."""
    profiler = PerformanceProfiler("test_run", enable_file_output=True)
    
    async with profiler:
        profiler.start_phase("analyze_and_plan")
        await asyncio.sleep(0.01)
        profiler.end_phase()
        
        profiler.start_phase("execute")
        await asyncio.sleep(0.01)
        profiler.end_phase()
        
        profiler.record_timer("llm_call", 0.5)
        profiler.record_cache(True)
    
    metrics = profiler.to_run_metrics()
    
    # Check expected keys
    expected_keys = [
        "run_name",
        "duration_s",
        "cache",
        "memory",
        "timers",
        "phases",
    ]
    
    for key in expected_keys:
        assert key in metrics, f"Missing key: {key}"
    
    # Check cache keys
    assert "hits" in metrics["cache"]
    assert "misses" in metrics["cache"]
    assert "hit_rate" in metrics["cache"]
    
    # Check memory keys
    assert "tracemalloc_current_kb" in metrics["memory"]
    assert "tracemalloc_peak_kb" in metrics["memory"]
    assert "rss_max_kb" in metrics["memory"]
    
    # Check phases structure
    assert len(metrics["phases"]) == 2
    for phase in metrics["phases"]:
        assert "phase" in phase
        assert "duration_s" in phase
        assert "rss_kb_before" in phase
        assert "rss_kb_after" in phase
        assert "rss_kb_delta" in phase
