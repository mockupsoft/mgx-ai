# -*- coding: utf-8 -*-
"""Performance benchmark suite for standardized performance testing."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    duration_ms: float
    success: bool
    metrics: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class BenchmarkScenario:
    """Benchmark scenario definition."""
    name: str
    description: str
    task: str
    complexity: str
    expected_duration_ms: Optional[float] = None
    expected_tokens: Optional[int] = None
    expected_cost_usd: Optional[float] = None


class BenchmarkSuite:
    """
    Standardized benchmark suite for performance testing.
    
    Features:
    - Standardized benchmark scenarios
    - Baseline performance metrics
    - Regression testing
    - Performance comparison reports
    """
    
    def __init__(self, baseline_path: Optional[Path] = None):
        """
        Initialize benchmark suite.
        
        Args:
            baseline_path: Path to baseline performance metrics JSON file
        """
        self.baseline_path = baseline_path or Path("perf_reports/baseline.json")
        self.baseline: Optional[Dict] = None
        self.results: List[BenchmarkResult] = []
        
        # Load baseline if exists
        if self.baseline_path.exists():
            try:
                with open(self.baseline_path, 'r') as f:
                    self.baseline = json.load(f)
                logger.info(f"Loaded baseline from {self.baseline_path}")
            except Exception as e:
                logger.warning(f"Failed to load baseline: {e}")
    
    def get_standard_scenarios(self) -> List[BenchmarkScenario]:
        """
        Get standard benchmark scenarios.
        
        Returns:
            List of benchmark scenarios
        """
        return [
            BenchmarkScenario(
                name="simple_task",
                description="Simple task (XS complexity)",
                task="Create a hello world function in Python",
                complexity="XS",
                expected_duration_ms=5000,
                expected_tokens=500,
                expected_cost_usd=0.001,
            ),
            BenchmarkScenario(
                name="medium_task",
                description="Medium task (M complexity)",
                task="Create a REST API with 3 endpoints: GET /users, POST /users, GET /users/:id",
                complexity="M",
                expected_duration_ms=15000,
                expected_tokens=2000,
                expected_cost_usd=0.005,
            ),
            BenchmarkScenario(
                name="complex_task",
                description="Complex task (L complexity)",
                task="Create a full-stack application with authentication, database, and API",
                complexity="L",
                expected_duration_ms=30000,
                expected_tokens=5000,
                expected_cost_usd=0.015,
            ),
        ]
    
    async def run_benchmark(
        self,
        scenario: BenchmarkScenario,
        executor_func,
    ) -> BenchmarkResult:
        """
        Run a single benchmark scenario.
        
        Args:
            scenario: Benchmark scenario
            executor_func: Async function that executes the task
        
        Returns:
            BenchmarkResult with metrics
        """
        logger.info(f"Running benchmark: {scenario.name}")
        
        start_time = time.perf_counter()
        metrics = {}
        error = None
        success = False
        
        try:
            result = await executor_func(scenario.task)
            success = True
            metrics["result_length"] = len(str(result)) if result else 0
        except Exception as e:
            error = str(e)
            logger.error(f"Benchmark {scenario.name} failed: {e}")
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        metrics.update({
            "duration_ms": duration_ms,
            "scenario": scenario.name,
            "complexity": scenario.complexity,
        })
        
        result = BenchmarkResult(
            name=scenario.name,
            duration_ms=duration_ms,
            success=success,
            metrics=metrics,
            error=error,
        )
        
        self.results.append(result)
        return result
    
    def compare_with_baseline(self) -> Dict[str, Any]:
        """
        Compare current results with baseline.
        
        Returns:
            Dictionary with comparison results
        """
        if not self.baseline:
            return {
                "has_baseline": False,
                "message": "No baseline available for comparison",
            }
        
        comparison = {
            "has_baseline": True,
            "scenarios": {},
        }
        
        baseline_scenarios = self.baseline.get("scenarios", {})
        
        for result in self.results:
            scenario_name = result.name
            baseline = baseline_scenarios.get(scenario_name)
            
            if not baseline:
                comparison["scenarios"][scenario_name] = {
                    "status": "no_baseline",
                    "message": "No baseline data for this scenario",
                }
                continue
            
            baseline_duration = baseline.get("duration_ms", 0)
            current_duration = result.duration_ms
            
            duration_delta = current_duration - baseline_duration
            duration_delta_pct = (duration_delta / baseline_duration * 100) if baseline_duration > 0 else 0
            
            # Determine regression status
            regression_threshold_pct = 20  # 20% slower is considered regression
            if duration_delta_pct > regression_threshold_pct:
                status = "regression"
            elif duration_delta_pct < -regression_threshold_pct:
                status = "improvement"
            else:
                status = "stable"
            
            comparison["scenarios"][scenario_name] = {
                "status": status,
                "baseline_duration_ms": baseline_duration,
                "current_duration_ms": current_duration,
                "delta_ms": duration_delta,
                "delta_percent": duration_delta_pct,
            }
        
        return comparison
    
    def generate_report(self, output_path: Optional[Path] = None) -> Path:
        """
        Generate performance comparison report.
        
        Args:
            output_path: Output file path (default: perf_reports/before_after.md)
        
        Returns:
            Path to generated report
        """
        if output_path is None:
            output_path = Path("perf_reports/before_after.md")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        comparison = self.compare_with_baseline()
        
        report_lines = [
            "# Performance Benchmark Report",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Results",
            "",
        ]
        
        if comparison.get("has_baseline"):
            report_lines.append("### Comparison with Baseline")
            report_lines.append("")
            
            for scenario_name, comp_data in comparison.get("scenarios", {}).items():
                status = comp_data.get("status", "unknown")
                status_emoji = {
                    "regression": "🔴",
                    "improvement": "🟢",
                    "stable": "🟡",
                    "no_baseline": "⚪",
                }.get(status, "⚪")
                
                report_lines.append(f"#### {status_emoji} {scenario_name}")
                report_lines.append("")
                
                if status != "no_baseline":
                    baseline_duration = comp_data.get("baseline_duration_ms", 0)
                    current_duration = comp_data.get("current_duration_ms", 0)
                    delta_pct = comp_data.get("delta_percent", 0)
                    
                    report_lines.append(f"- Baseline: {baseline_duration:.2f} ms")
                    report_lines.append(f"- Current: {current_duration:.2f} ms")
                    report_lines.append(f"- Delta: {delta_pct:+.2f}%")
                    report_lines.append("")
        else:
            report_lines.append("No baseline available for comparison.")
            report_lines.append("")
        
        report_lines.append("## Detailed Results")
        report_lines.append("")
        
        for result in self.results:
            report_lines.append(f"### {result.name}")
            report_lines.append("")
            report_lines.append(f"- Duration: {result.duration_ms:.2f} ms")
            report_lines.append(f"- Success: {result.success}")
            if result.error:
                report_lines.append(f"- Error: {result.error}")
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Generated benchmark report: {output_path}")
        return output_path
    
    def save_results(self, output_path: Optional[Path] = None) -> Path:
        """
        Save benchmark results to JSON.
        
        Args:
            output_path: Output file path (default: perf_reports/latest.json)
        
        Returns:
            Path to saved results
        """
        if output_path is None:
            output_path = Path("perf_reports/latest.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        results_data = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "scenarios": {
                result.name: {
                    "duration_ms": result.duration_ms,
                    "success": result.success,
                    "metrics": result.metrics,
                    "error": result.error,
                }
                for result in self.results
            },
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved benchmark results: {output_path}")
        return output_path

