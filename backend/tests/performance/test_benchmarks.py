# -*- coding: utf-8 -*-
"""Tests for performance benchmarks."""

import pytest
import asyncio
from pathlib import Path

from backend.tests.performance.benchmarks import BenchmarkSuite, BenchmarkScenario


@pytest.mark.performance
class TestBenchmarkSuite:
    """Tests for benchmark suite."""
    
    def test_benchmark_suite_initialization(self):
        """Test benchmark suite initialization."""
        suite = BenchmarkSuite()
        assert suite.baseline_path == Path("perf_reports/baseline.json")
        assert suite.results == []
    
    def test_get_standard_scenarios(self):
        """Test getting standard scenarios."""
        suite = BenchmarkSuite()
        scenarios = suite.get_standard_scenarios()
        
        assert len(scenarios) > 0
        assert all(isinstance(s, BenchmarkScenario) for s in scenarios)
        assert any(s.name == "simple_task" for s in scenarios)
    
    @pytest.mark.asyncio
    async def test_run_benchmark_success(self):
        """Test running a successful benchmark."""
        suite = BenchmarkSuite()
        scenario = BenchmarkScenario(
            name="test_scenario",
            description="Test scenario",
            task="Test task",
            complexity="XS",
        )
        
        async def executor(task: str) -> str:
            await asyncio.sleep(0.01)  # Simulate work
            return "result"
        
        result = await suite.run_benchmark(scenario, executor)
        
        assert result.name == "test_scenario"
        assert result.success is True
        assert result.duration_ms > 0
        assert result.error is None
        assert len(suite.results) == 1
    
    @pytest.mark.asyncio
    async def test_run_benchmark_failure(self):
        """Test running a failed benchmark."""
        suite = BenchmarkSuite()
        scenario = BenchmarkScenario(
            name="test_scenario",
            description="Test scenario",
            task="Test task",
            complexity="XS",
        )
        
        async def executor(task: str) -> str:
            raise Exception("Test error")
        
        result = await suite.run_benchmark(scenario, executor)
        
        assert result.name == "test_scenario"
        assert result.success is False
        assert result.error == "Test error"
    
    def test_compare_with_baseline_no_baseline(self):
        """Test comparison when no baseline exists."""
        suite = BenchmarkSuite()
        comparison = suite.compare_with_baseline()
        
        assert comparison["has_baseline"] is False
    
    def test_generate_report(self, tmp_path):
        """Test report generation."""
        suite = BenchmarkSuite()
        
        # Add mock results
        from backend.tests.performance.benchmarks import BenchmarkResult
        suite.results.append(BenchmarkResult(
            name="test",
            duration_ms=1000.0,
            success=True,
            metrics={},
        ))
        
        output_path = tmp_path / "report.md"
        report_path = suite.generate_report(output_path)
        
        assert report_path.exists()
        assert report_path == output_path
        
        content = report_path.read_text()
        assert "Performance Benchmark Report" in content
        assert "test" in content
    
    def test_save_results(self, tmp_path):
        """Test saving results to JSON."""
        suite = BenchmarkSuite()
        
        # Add mock results
        from backend.tests.performance.benchmarks import BenchmarkResult
        suite.results.append(BenchmarkResult(
            name="test",
            duration_ms=1000.0,
            success=True,
            metrics={},
        ))
        
        output_path = tmp_path / "results.json"
        saved_path = suite.save_results(output_path)
        
        assert saved_path.exists()
        assert saved_path == output_path
        
        import json
        data = json.loads(saved_path.read_text())
        assert "scenarios" in data
        assert "test" in data["scenarios"]




