# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.performance_gate

Quality gate for performance smoke tests and benchmarking.
"""

import json
import subprocess
import os
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
import logging
import statistics
import aiohttp
from concurrent.futures import ThreadPoolExecutor

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ....db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.PERFORMANCE)


class PerformanceGate(BaseQualityGate):
    """Quality gate for performance testing and monitoring."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.PERFORMANCE, config)
        self.logger = logging.getLogger(__name__)
    
    async def evaluate(
        self,
        workspace_id: str,
        project_id: str,
        task_id: Optional[str] = None,
        task_run_id: Optional[str] = None,
        sandbox_execution_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        application_url: Optional[str] = None,
        **kwargs
    ) -> GateResult:
        """Evaluate performance quality gate."""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Set execution context
            self.set_execution_context({
                "workspace_id": workspace_id,
                "project_id": project_id,
                "working_directory": working_directory or os.getcwd(),
                "application_url": application_url
            })
            
            # Validate configuration
            config_errors = self.validate_configuration()
            if config_errors:
                return GateResult(
                    gate_type=self.gate_type,
                    status=QualityGateStatus.ERROR,
                    passed=False,
                    error_message=f"Configuration errors: {', '.join(config_errors)}"
                )
            
            # Check if gate is enabled
            if not self.config.is_enabled:
                return GateResult(
                    gate_type=self.gate_type,
                    status=QualityGateStatus.SKIPPED,
                    passed=True,
                    passed_with_warnings=False,
                    details={"reason": "Gate disabled in configuration"}
                )
            
            # Initialize result metrics
            test_results = {}
            total_issues = 0
            high_issues = 0
            medium_issues = 0
            
            # Run response time tests
            if self.get_threshold_value(["tests", "response_time", "enabled"], True):
                response_time_result = await self._test_response_time(application_url)
                test_results["response_time"] = response_time_result
                if not response_time_result.get("passed", True):
                    total_issues += response_time_result.get("failures", 1)
                    high_issues += response_time_result.get("failures", 1)
            
            # Run throughput tests
            if self.get_threshold_value(["tests", "throughput", "enabled"], True):
                throughput_result = await self._test_throughput(application_url)
                test_results["throughput"] = throughput_result
                if not throughput_result.get("passed", True):
                    total_issues += 1
                    high_issues += 1
            
            # Run memory usage tests
            if self.get_threshold_value(["tests", "memory", "enabled"], True):
                memory_result = await self._test_memory_usage(working_directory or os.getcwd())
                test_results["memory"] = memory_result
                if not memory_result.get("passed", True):
                    total_issues += memory_result.get("failures", 1)
                    high_issues += memory_result.get("failures", 1)
            
            # Run CPU usage tests
            if self.get_threshold_value(["tests", "cpu", "enabled"], True):
                cpu_result = await self._test_cpu_usage(working_directory or os.getcwd())
                test_results["cpu"] = cpu_result
                if not cpu_result.get("passed", True):
                    total_issues += cpu_result.get("failures", 1)
                    medium_issues += cpu_result.get("failures", 1)
            
            # Run stress tests if configured
            if self.get_threshold_value(["tests", "stress_test", "enabled"], False):
                stress_result = await self._run_stress_test(application_url)
                test_results["stress_test"] = stress_result
                if not stress_result.get("passed", True):
                    total_issues += stress_result.get("failures", 1)
                    high_issues += stress_result.get("failures", 1)
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Get overall thresholds
            max_response_time_ms = self.get_threshold_value("max_response_time_ms", 500)
            min_throughput_rps = self.get_threshold_value("min_throughput_rps", 100)
            max_memory_mb = self.get_threshold_value("max_memory_mb", 512)
            max_cpu_percent = self.get_threshold_value("max_cpu_percent", 80)
            
            # Determine gate result
            passed = total_issues == 0
            passed_with_warnings = total_issues <= 2  # Allow up to 2 minor issues
            status = QualityGateStatus.PASSED
            
            if not passed:
                if high_issues > 0:
                    status = QualityGateStatus.FAILED
                elif medium_issues > 0:
                    passed_with_warnings = True
                    status = QualityGateStatus.WARNING
                else:
                    passed_with_warnings = True
                    status = QualityGateStatus.WARNING
            
            # Generate recommendations
            recommendations = self._generate_recommendations(test_results, max_response_time_ms, min_throughput_rps)
            
            # Update context with results
            context = self.get_execution_context()
            context.update({
                "test_results": test_results,
                "total_issues": total_issues
            })
            
            result = GateResult(
                gate_type=self.gate_type,
                status=status,
                passed=passed,
                passed_with_warnings=passed_with_warnings,
                execution_time_ms=execution_time_ms,
                details={
                    "test_results": test_results,
                    "thresholds": {
                        "max_response_time_ms": max_response_time_ms,
                        "min_throughput_rps": min_throughput_rps,
                        "max_memory_mb": max_memory_mb,
                        "max_cpu_percent": max_cpu_percent
                    },
                    "total_issues": total_issues
                },
                metrics={
                    "response_time_avg_ms": test_results.get("response_time", {}).get("average_ms", 0),
                    "throughput_rps": test_results.get("throughput", {}).get("measured_rps", 0),
                    "memory_usage_mb": test_results.get("memory", {}).get("peak_mb", 0),
                    "cpu_usage_percent": test_results.get("cpu", {}).get("average_percent", 0)
                },
                recommendations=recommendations,
                total_issues=total_issues,
                high_issues=high_issues,
                medium_issues=medium_issues
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Performance gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _test_response_time(self, application_url: Optional[str]) -> Dict[str, Any]:
        """Test API response times."""
        
        if not application_url:
            return {
                "test": "response_time",
                "passed": True,
                "message": "No application URL provided for testing",
                "measurements": []
            }
        
        threshold_ms = self.get_threshold_value(["tests", "response_time", "threshold_ms"], 500)
        concurrent_requests = self.get_threshold_value(["tests", "response_time", "concurrent_requests"], 5)
        duration_seconds = self.get_threshold_value(["tests", "response_time", "duration_seconds"], 30)
        
        measurements = []
        failures = 0
        timeout_failures = 0
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                while time.time() < end_time:
                    # Send concurrent requests
                    tasks = []
                    for _ in range(concurrent_requests):
                        if time.time() >= end_time:
                            break
                        
                        task = self._make_http_request(session, application_url)
                        tasks.append(task)
                    
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        for result in results:
                            if isinstance(result, Exception):
                                failures += 1
                                if "timeout" in str(result).lower():
                                    timeout_failures += 1
                            else:
                                measurements.append(result)
                    
                    # Small delay between batches
                    await asyncio.sleep(0.1)
            
            # Calculate statistics
            if measurements:
                response_times = [m["response_time_ms"] for m in measurements]
                avg_response_time = statistics.mean(response_times)
                p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else max(response_times)
                min_response_time = min(response_times)
                max_response_time = max(response_times)
                
                passed = avg_response_time <= threshold_ms and p95_response_time <= threshold_ms * 1.5
                
                return {
                    "test": "response_time",
                    "passed": passed,
                    "measurements": measurements,
                    "statistics": {
                        "average_ms": round(avg_response_time, 2),
                        "p95_ms": round(p95_response_time, 2),
                        "min_ms": round(min_response_time, 2),
                        "max_ms": round(max_response_time, 2),
                        "total_requests": len(measurements),
                        "failures": failures,
                        "timeout_failures": timeout_failures
                    },
                    "threshold_ms": threshold_ms
                }
            else:
                return {
                    "test": "response_time",
                    "passed": False,
                    "failures": failures,
                    "error": "No successful measurements taken"
                }
                
        except Exception as e:
            self.logger.error(f"Response time test failed: {str(e)}")
            return {
                "test": "response_time",
                "passed": False,
                "error": str(e),
                "failures": failures + 1
            }
    
    async def _make_http_request(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """Make a single HTTP request and measure timing."""
        
        try:
            start_time = time.time()
            
            async with session.get(url) as response:
                # Read response to ensure full processing
                await response.read()
                
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                return {
                    "url": url,
                    "status_code": response.status,
                    "response_time_ms": response_time_ms,
                    "timestamp": time.time()
                }
                
        except Exception as e:
            # Return exception for handling
            raise e
    
    async def _test_throughput(self, application_url: Optional[str]) -> Dict[str, Any]:
        """Test application throughput."""
        
        if not application_url:
            return {
                "test": "throughput",
                "passed": True,
                "message": "No application URL provided for testing"
            }
        
        min_rps = self.get_threshold_value(["tests", "throughput", "min_rps"], 100)
        duration_seconds = self.get_threshold_value(["tests", "throughput", "duration_seconds"], 60)
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        successful_requests = 0
        failed_requests = 0
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                while time.time() < end_time:
                    # Send requests as fast as possible
                    try:
                        async with session.get(application_url) as response:
                            await response.read()
                            if response.status == 200:
                                successful_requests += 1
                            else:
                                failed_requests += 1
                    except:
                        failed_requests += 1
                    
                    # Small delay to avoid overwhelming
                    await asyncio.sleep(0.001)  # 1ms delay
            
            # Calculate RPS
            actual_duration = end_time - start_time
            measured_rps = successful_requests / actual_duration if actual_duration > 0 else 0
            
            passed = measured_rps >= min_rps
            
            return {
                "test": "throughput",
                "passed": passed,
                "measured_rps": round(measured_rps, 2),
                "threshold_rps": min_rps,
                "total_duration_seconds": round(actual_duration, 2),
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": round((successful_requests / (successful_requests + failed_requests)) * 100, 2) if (successful_requests + failed_requests) > 0 else 100
            }
            
        except Exception as e:
            self.logger.error(f"Throughput test failed: {str(e)}")
            return {
                "test": "throughput",
                "passed": False,
                "error": str(e)
            }
    
    async def _test_memory_usage(self, working_directory: str) -> Dict[str, Any]:
        """Test memory usage during application execution."""
        
        max_memory_mb = self.get_threshold_value("max_memory_mb", 512)
        max_memory_bytes = max_memory_mb * 1024 * 1024
        
        measurements = []
        peak_memory = 0
        memory_violations = 0
        
        try:
            # Check if there's a running application to monitor
            processes = await self._find_running_processes(working_directory)
            
            if not processes:
                return {
                    "test": "memory",
                    "passed": True,
                    "message": "No running processes found to monitor"
                }
            
            # Monitor memory usage for a short period
            start_time = time.time()
            end_time = start_time + 30  # Monitor for 30 seconds
            
            while time.time() < end_time:
                current_memory = 0
                
                for proc_info in processes:
                    try:
                        # Get memory usage for this process
                        memory_mb = await self._get_process_memory_mb(proc_info["pid"])
                        current_memory += memory_mb
                    except:
                        continue
                
                measurements.append({
                    "timestamp": time.time(),
                    "memory_mb": current_memory
                })
                
                peak_memory = max(peak_memory, current_memory)
                
                if current_memory > max_memory_mb:
                    memory_violations += 1
                
                await asyncio.sleep(1)  # Sample every second
            
            passed = peak_memory <= max_memory_mb
            
            return {
                "test": "memory",
                "passed": passed,
                "peak_mb": round(peak_memory, 2),
                "threshold_mb": max_memory_mb,
                "average_mb": round(statistics.mean([m["memory_mb"] for m in measurements]), 2) if measurements else 0,
                "measurements": measurements,
                "violations": memory_violations,
                "failures": 1 if not passed else 0
            }
            
        except Exception as e:
            self.logger.error(f"Memory test failed: {str(e)}")
            return {
                "test": "memory",
                "passed": False,
                "error": str(e)
            }
    
    async def _test_cpu_usage(self, working_directory: str) -> Dict[str, Any]:
        """Test CPU usage during application execution."""
        
        max_cpu_percent = self.get_threshold_value("max_cpu_percent", 80)
        
        measurements = []
        peak_cpu = 0
        cpu_violations = 0
        
        try:
            # Check if there's a running application to monitor
            processes = await self._find_running_processes(working_directory)
            
            if not processes:
                return {
                    "test": "cpu",
                    "passed": True,
                    "message": "No running processes found to monitor"
                }
            
            # Monitor CPU usage for a short period
            start_time = time.time()
            end_time = start_time + 30  # Monitor for 30 seconds
            
            while time.time() < end_time:
                current_cpu = 0
                
                for proc_info in processes:
                    try:
                        # Get CPU usage for this process
                        cpu_percent = await self._get_process_cpu_percent(proc_info["pid"])
                        current_cpu += cpu_percent
                    except:
                        continue
                
                measurements.append({
                    "timestamp": time.time(),
                    "cpu_percent": current_cpu
                })
                
                peak_cpu = max(peak_cpu, current_cpu)
                
                if current_cpu > max_cpu_percent:
                    cpu_violations += 1
                
                await asyncio.sleep(1)  # Sample every second
            
            passed = peak_cpu <= max_cpu_percent
            
            return {
                "test": "cpu",
                "passed": passed,
                "peak_percent": round(peak_cpu, 2),
                "threshold_percent": max_cpu_percent,
                "average_percent": round(statistics.mean([m["cpu_percent"] for m in measurements]), 2) if measurements else 0,
                "measurements": measurements,
                "violations": cpu_violations,
                "failures": 1 if not passed else 0
            }
            
        except Exception as e:
            self.logger.error(f"CPU test failed: {str(e)}")
            return {
                "test": "cpu",
                "passed": False,
                "error": str(e)
            }
    
    async def _run_stress_test(self, application_url: Optional[str]) -> Dict[str, Any]:
        """Run basic stress test with increasing load."""
        
        if not application_url:
            return {
                "test": "stress_test",
                "passed": True,
                "message": "No application URL provided for testing"
            }
        
        # Start with low load and increase
        concurrent_levels = [5, 10, 25, 50, 100]
        max_requests_per_level = 20
        test_results = []
        
        try:
            for concurrent_requests in concurrent_levels:
                level_start_time = time.time()
                successful_requests = 0
                failed_requests = 0
                response_times = []
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    for i in range(max_requests_per_level):
                        try:
                            start_time = time.time()
                            
                            # Create concurrent requests for this level
                            tasks = []
                            for _ in range(concurrent_requests):
                                task = self._make_http_request(session, application_url)
                                tasks.append(task)
                            
                            results = await asyncio.gather(*tasks, return_exceptions=True)
                            
                            # Process results
                            for result in results:
                                if isinstance(result, dict) and "response_time_ms" in result:
                                    successful_requests += 1
                                    response_times.append(result["response_time_ms"])
                                else:
                                    failed_requests += 1
                            
                            level_duration = time.time() - level_start_time
                            
                            # Calculate RPS for this level
                            level_rps = successful_requests / level_duration if level_duration > 0 else 0
                            
                            level_result = {
                                "concurrent_requests": concurrent_requests,
                                "successful_requests": successful_requests,
                                "failed_requests": failed_requests,
                                "level_rps": round(level_rps, 2),
                                "avg_response_time": round(statistics.mean(response_times), 2) if response_times else 0,
                                "duration_seconds": round(level_duration, 2)
                            }
                            
                            test_results.append(level_result)
                            
                            # If this level is failing significantly, stop the test
                            if successful_requests < (concurrent_requests * max_requests_per_level) * 0.7:
                                break
                            
                        except Exception:
                            failed_requests += 1
                            if failed_requests > successful_requests:
                                break
                
                # If we have too many failures, stop the test
                if failed_requests > successful_requests:
                    break
            
            # Determine if stress test passed
            # Pass if we can handle at least 50 concurrent requests with reasonable performance
            passed = any(
                result["concurrent_requests"] >= 50 and 
                result["avg_response_time"] < 1000 and 
                result["failed_requests"] == 0
                for result in test_results
            )
            
            return {
                "test": "stress_test",
                "passed": passed,
                "levels": test_results,
                "max_concurrent_supported": max([r["concurrent_requests"] for r in test_results], default=0)
            }
            
        except Exception as e:
            self.logger.error(f"Stress test failed: {str(e)}")
            return {
                "test": "stress_test",
                "passed": False,
                "error": str(e)
            }
    
    async def _find_running_processes(self, working_directory: str) -> List[Dict[str, Any]]:
        """Find running processes related to the working directory."""
        
        try:
            # Use ps to find processes
            result = await asyncio.create_subprocess_exec(
                "ps", "aux",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            processes = []
            working_dir_basename = os.path.basename(working_directory)
            
            if stdout:
                lines = stdout.decode().split('\n')
                
                for line in lines[1:]:  # Skip header
                    if working_dir_basename in line and "ps aux" not in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                pid = int(parts[1])
                                processes.append({
                                    "pid": pid,
                                    "command": ' '.join(parts[10:]) if len(parts) > 10 else ' '.join(parts[2:])
                                })
                            except (ValueError, IndexError):
                                continue
            
            return processes
            
        except Exception as e:
            self.logger.debug(f"Failed to find running processes: {e}")
            return []
    
    async def _get_process_memory_mb(self, pid: int) -> float:
        """Get memory usage of a process in MB."""
        
        try:
            with open(f"/proc/{pid}/status", 'r') as f:
                content = f.read()
                
            # Extract VmRSS (Resident Set Size)
            for line in content.split('\n'):
                if line.startswith('VmRSS:'):
                    # VmRSS is in kB
                    memory_kb = int(line.split()[1])
                    return memory_kb / 1024.0
            
            return 0.0
            
        except (FileNotFoundError, PermissionError, ValueError):
            return 0.0
    
    async def _get_process_cpu_percent(self, pid: int) -> float:
        """Get CPU usage percentage of a process."""
        
        try:
            with open(f"/proc/{pid}/stat", 'r') as f:
                stat_data = f.read().split()
                
            if len(stat_data) >= 42:
                # Extract utime (14) and stime (15) - CPU time used
                utime = int(stat_data[13])
                stime = int(stat_data[14])
                
                # Get system uptime
                with open("/proc/uptime", 'r') as f:
                    uptime_seconds = float(f.read().split()[0])
                
                # Calculate CPU usage (simplified)
                cpu_usage = (utime + stime) / (uptime_seconds * 100)  # Approximation
                return min(cpu_usage, 100.0)  # Cap at 100%
            
            return 0.0
            
        except (FileNotFoundError, PermissionError, ValueError, IndexError):
            return 0.0
    
    def _generate_recommendations(
        self,
        test_results: Dict[str, Any],
        max_response_time_ms: int,
        min_throughput_rps: int
    ) -> List[str]:
        """Generate performance recommendations."""
        
        recommendations = []
        
        # Response time recommendations
        response_time_result = test_results.get("response_time", {})
        if not response_time_result.get("passed", True):
            avg_time = response_time_result.get("statistics", {}).get("average_ms", 0)
            p95_time = response_time_result.get("statistics", {}).get("p95_ms", 0)
            
            if avg_time > max_response_time_ms:
                recommendations.append(
                    self.create_recommendation(
                        "Response Time",
                        f"Average response time ({avg_time:.0f}ms) exceeds threshold ({max_response_time_ms}ms)",
                        GateSeverity.HIGH
                    )
                )
                recommendations.append("Optimize database queries and reduce API response payload size")
                recommendations.append("Consider implementing caching strategies for frequently accessed data")
            
            if p95_time > max_response_time_ms * 1.5:
                recommendations.append("High P95 response times detected - investigate performance bottlenecks")
        
        # Throughput recommendations
        throughput_result = test_results.get("throughput", {})
        if not throughput_result.get("passed", True):
            measured_rps = throughput_result.get("measured_rps", 0)
            
            if measured_rps < min_throughput_rps:
                recommendations.append(
                    self.create_recommendation(
                        "Throughput",
                        f"Throughput ({measured_rps:.0f} RPS) below threshold ({min_throughput_rps} RPS)",
                        GateSeverity.HIGH
                    )
                )
                recommendations.append("Scale application horizontally or optimize code for better throughput")
        
        # Memory recommendations
        memory_result = test_results.get("memory", {})
        if not memory_result.get("passed", True):
            peak_memory = memory_result.get("peak_mb", 0)
            recommendations.append(
                self.create_recommendation(
                    "Memory Usage",
                    f"Peak memory usage ({peak_memory:.0f}MB) is high",
                    GateSeverity.MEDIUM
                )
            )
            recommendations.append("Profile memory usage and identify memory leaks")
            recommendations.append("Optimize data structures and caching strategies")
        
        # CPU recommendations
        cpu_result = test_results.get("cpu", {})
        if not cpu_result.get("passed", True):
            peak_cpu = cpu_result.get("peak_percent", 0)
            recommendations.append(
                self.create_recommendation(
                    "CPU Usage",
                    f"Peak CPU usage ({peak_cpu:.0f}%) is high",
                    GateSeverity.MEDIUM
                )
            )
            recommendations.append("Profile CPU usage and optimize hot code paths")
            recommendations.append("Consider algorithmic improvements for CPU-intensive operations")
        
        # Stress test recommendations
        stress_result = test_results.get("stress_test", {})
        if not stress_result.get("passed", True):
            max_concurrent = stress_result.get("max_concurrent_supported", 0)
            if max_concurrent < 50:
                recommendations.append("Application fails under concurrent load - investigate scalability issues")
        
        # General recommendations if no specific issues
        if not test_results or all(result.get("passed", True) for result in test_results.values()):
            recommendations.append("Performance metrics look good - continue monitoring in production")
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for performance testing."""
        return ["javascript", "python", "php", "java", "go", "ruby"]
    
    def validate_configuration(self) -> List[str]:
        """Validate performance gate configuration."""
        errors = super().validate_configuration()
        
        # Check threshold values
        thresholds = [
            ("max_response_time_ms", "positive number"),
            ("min_throughput_rps", "positive number"),
            ("max_memory_mb", "positive number"),
            ("max_cpu_percent", "number between 0 and 100")
        ]
        
        for threshold, description in thresholds:
            value = self.get_threshold_value(threshold)
            if value is not None:
                if threshold == "max_response_time_ms" and (not isinstance(value, (int, float)) or value <= 0):
                    errors.append(f"{threshold} must be a positive number")
                elif threshold == "min_throughput_rps" and (not isinstance(value, (int, float)) or value <= 0):
                    errors.append(f"{threshold} must be a positive number")
                elif threshold == "max_memory_mb" and (not isinstance(value, (int, float)) or value <= 0):
                    errors.append(f"{threshold} must be a positive number")
                elif threshold == "max_cpu_percent" and (not isinstance(value, (int, float)) or not 0 <= value <= 100):
                    errors.append(f"{threshold} must be a number between 0 and 100")
        
        return errors