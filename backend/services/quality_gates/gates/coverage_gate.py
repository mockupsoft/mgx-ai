# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.coverage_gate

Quality gate for test coverage enforcement.
"""

import json
import subprocess
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import logging
import xml.etree.ElementTree as ET

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.COVERAGE)


class CoverageGate(BaseQualityGate):
    """Quality gate for test coverage enforcement."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.COVERAGE, config)
        self.logger = logging.getLogger(__name__)
    
    async def evaluate(
        self,
        workspace_id: str,
        project_id: str,
        task_id: Optional[str] = None,
        task_run_id: Optional[str] = None,
        sandbox_execution_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        **kwargs
    ) -> GateResult:
        """Evaluate coverage quality gate."""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Set execution context
            self.set_execution_context({
                "workspace_id": workspace_id,
                "project_id": project_id,
                "working_directory": working_directory or os.getcwd()
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
            overall_coverage = 0.0
            language_results = {}
            total_lines = 0
            covered_lines = 0
            
            # Process each supported language
            for language in self.get_supported_languages():
                language_config = self.config.threshold_config.get("tools", {}).get(language, {})
                
                if not language_config.get("enabled", False):
                    continue
                
                language_result = await self._evaluate_language_coverage(
                    language, language_config, working_directory or os.getcwd()
                )
                
                if language_result:
                    language_results[language] = language_result
                    overall_coverage = max(overall_coverage, language_result.get("coverage_percentage", 0))
                    total_lines += language_result.get("total_lines", 0)
                    covered_lines += language_result.get("covered_lines", 0)
            
            # If no coverage data found, determine if it's acceptable
            if not language_results:
                return GateResult(
                    gate_type=self.gate_type,
                    status=QualityGateStatus.WARNING,
                    passed=True,
                    passed_with_warnings=True,
                    details={"reason": "No test coverage tools found or configured"},
                    recommendations=["Consider adding test coverage tools to your project"]
                )
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Get thresholds
            min_percentage = self.get_threshold_value("min_percentage", 80.0)
            
            # Determine gate result
            passed = overall_coverage >= min_percentage
            passed_with_warnings = overall_coverage >= (min_percentage - 10)  # 10% grace period
            status = QualityGateStatus.PASSED
            
            if not passed:
                if passed_with_warnings:
                    status = QualityGateStatus.WARNING
                else:
                    status = QualityGateStatus.FAILED
            
            # Generate recommendations
            recommendations = self._generate_recommendations(overall_coverage, min_percentage, language_results)
            
            # Update context with results
            context = self.get_execution_context()
            context.update({
                "overall_coverage": overall_coverage,
                "language_results": language_results,
                "total_lines": total_lines,
                "covered_lines": covered_lines
            })
            
            result = GateResult(
                gate_type=self.gate_type,
                status=status,
                passed=passed,
                passed_with_warnings=passed_with_warnings,
                execution_time_ms=execution_time_ms,
                details={
                    "overall_coverage_percentage": overall_coverage,
                    "min_percentage_required": min_percentage,
                    "language_results": language_results,
                    "total_lines": total_lines,
                    "covered_lines": covered_lines,
                    "uncovered_lines": max(0, total_lines - covered_lines)
                },
                metrics={
                    "coverage_percentage": overall_coverage,
                    "lines_covered": covered_lines,
                    "lines_total": total_lines,
                    "gap_to_target": max(0, min_percentage - overall_coverage)
                },
                recommendations=recommendations,
                total_issues=max(0, total_lines - covered_lines),  # Uncovered lines as issues
                medium_issues=max(0, total_lines - covered_lines)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Coverage gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _evaluate_language_coverage(
        self,
        language: str,
        language_config: Dict[str, Any],
        working_directory: str
    ) -> Optional[Dict[str, Any]]:
        """Evaluate coverage for a specific language."""
        
        try:
            if language == "python":
                return await self._coverage_python(language_config, working_directory)
            elif language == "javascript":
                return await self._coverage_javascript(language_config, working_directory)
            elif language == "php":
                return await self._coverage_php(language_config, working_directory)
            else:
                self.logger.warning(f"Unsupported language for coverage: {language}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error evaluating {language} coverage: {str(e)}")
            return None
    
    async def _coverage_python(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Evaluate Python coverage using pytest-cov."""
        
        command = config.get("command", "pytest --cov --cov-report=json --cov-report=term")
        coverage_file = config.get("coverage_file", "coverage.json")
        
        try:
            # Run coverage command
            cmd_parts = command.split()
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            coverage_data = {}
            coverage_percentage = 0.0
            
            # Try to read coverage JSON file
            coverage_path = os.path.join(working_directory, coverage_file)
            if os.path.exists(coverage_path):
                try:
                    with open(coverage_path, 'r') as f:
                        coverage_data = json.load(f)
                    
                    # Extract coverage percentage from JSON structure
                    totals = coverage_data.get('totals', {})
                    coverage_percentage = totals.get('percent_covered', 0.0)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to read coverage JSON: {e}")
            
            # Parse terminal output if JSON failed
            if coverage_percentage == 0.0 and stdout:
                coverage_percentage = self._parse_coverage_terminal_output(stdout.decode())
            
            # Calculate lines
            total_lines = 0
            covered_lines = 0
            
            if coverage_data:
                files = coverage_data.get('files', {})
                for file_path, file_data in files.items():
                    summary = file_data.get('summary', {})
                    total_lines += summary.get('num_statements', 0)
                    covered_lines += summary.get('covered_lines', 0)
            
            return {
                "language": "python",
                "coverage_percentage": coverage_percentage,
                "total_lines": total_lines,
                "covered_lines": covered_lines,
                "uncovered_lines": max(0, total_lines - covered_lines),
                "command": command,
                "coverage_file": coverage_file,
                "raw_data": coverage_data,
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"Python coverage execution failed: {str(e)}")
            return {
                "language": "python",
                "coverage_percentage": 0.0,
                "total_lines": 0,
                "covered_lines": 0,
                "uncovered_lines": 0,
                "error": str(e)
            }
    
    async def _coverage_javascript(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Evaluate JavaScript coverage using Jest."""
        
        command = config.get("command", "npm test -- --coverage --coverageReporters=json --coverageReporters=text")
        coverage_file = config.get("coverage_file", "coverage/coverage-summary.json")
        
        try:
            # Run coverage command
            cmd_parts = command.split()
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            coverage_data = {}
            coverage_percentage = 0.0
            
            # Try to read coverage summary JSON file
            coverage_path = os.path.join(working_directory, coverage_file)
            if os.path.exists(coverage_path):
                try:
                    with open(coverage_path, 'r') as f:
                        coverage_data = json.load(f)
                    
                    # Extract overall coverage percentage
                    total = coverage_data.get('total', {})
                    coverage_percentage = total.get('lines', {}).get('pct', 0.0)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to read Jest coverage JSON: {e}")
            
            # Parse terminal output if JSON failed
            if coverage_percentage == 0.0 and stdout:
                coverage_percentage = self._parse_jest_coverage_output(stdout.decode())
            
            # Calculate lines
            total_lines = 0
            covered_lines = 0
            
            if coverage_data:
                total = coverage_data.get('total', {})
                total_lines = total.get('lines', {}).get('total', 0)
                covered_lines = total.get('lines', {}).get('covered', 0)
            
            return {
                "language": "javascript",
                "coverage_percentage": coverage_percentage,
                "total_lines": total_lines,
                "covered_lines": covered_lines,
                "uncovered_lines": max(0, total_lines - covered_lines),
                "command": command,
                "coverage_file": coverage_file,
                "raw_data": coverage_data,
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"JavaScript coverage execution failed: {str(e)}")
            return {
                "language": "javascript",
                "coverage_percentage": 0.0,
                "total_lines": 0,
                "covered_lines": 0,
                "uncovered_lines": 0,
                "error": str(e)
            }
    
    async def _coverage_php(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Evaluate PHP coverage using PHPUnit."""
        
        command = config.get("command", "phpunit --coverage-clover coverage.xml")
        coverage_file = config.get("coverage_file", "coverage.xml")
        
        try:
            # Run coverage command
            cmd_parts = command.split()
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            coverage_percentage = 0.0
            total_lines = 0
            covered_lines = 0
            
            # Try to read Clover XML coverage file
            coverage_path = os.path.join(working_directory, coverage_file)
            if os.path.exists(coverage_path):
                try:
                    tree = ET.parse(coverage_path)
                    root = tree.getroot()
                    
                    # Parse XML structure for coverage metrics
                    for package in root.findall('.//package'):
                        for clazz in package.findall('.//class'):
                            for line in clazz.findall('.//line'):
                                total_lines += 1
                                hits = int(line.get('hits', '0'))
                                covered_lines += 1 if hits > 0 else 0
                    
                    if total_lines > 0:
                        coverage_percentage = (covered_lines / total_lines) * 100
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse PHPUnit coverage XML: {e}")
            
            return {
                "language": "php",
                "coverage_percentage": coverage_percentage,
                "total_lines": total_lines,
                "covered_lines": covered_lines,
                "uncovered_lines": max(0, total_lines - covered_lines),
                "command": command,
                "coverage_file": coverage_file,
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"PHP coverage execution failed: {str(e)}")
            return {
                "language": "php",
                "coverage_percentage": 0.0,
                "total_lines": 0,
                "covered_lines": 0,
                "uncovered_lines": 0,
                "error": str(e)
            }
    
    def _parse_coverage_terminal_output(self, output: str) -> float:
        """Parse coverage percentage from terminal output."""
        # Look for coverage percentage in various formats
        patterns = [
            r'\[.*?\]\s+(\d+(?:\.\d+)?)%\s+covered',
            r'TOTAL.*?(\d+(?:\.\d+)?)%\s*',
            r'coverage.*?(\d+(?:\.\d+)?)%',
            r'covered:\s*(\d+(?:\.\d+)?)%'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return 0.0
    
    def _parse_jest_coverage_output(self, output: str) -> float:
        """Parse coverage percentage from Jest terminal output."""
        # Jest typically shows coverage in a table format
        lines = output.split('\n')
        
        for line in lines:
            if 'All files' in line or 'Lines' in line:
                # Look for percentage in the line
                match = re.search(r'(\d+(?:\.\d+)?)%', line)
                if match:
                    try:
                        return float(match.group(1))
                    except ValueError:
                        continue
        
        return 0.0
    
    def _generate_recommendations(
        self,
        overall_coverage: float,
        min_percentage: float,
        language_results: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on coverage results."""
        
        recommendations = []
        
        if overall_coverage < min_percentage:
            gap = min_percentage - overall_coverage
            
            recommendations.append(
                self.create_recommendation(
                    "Test Coverage",
                    f"Increase test coverage by {gap:.1f}% to meet the {min_percentage}% requirement",
                    GateSeverity.HIGH
                )
            )
            
            # Language-specific recommendations
            for language, result in language_results.items():
                coverage = result.get('coverage_percentage', 0)
                uncovered_lines = result.get('uncovered_lines', 0)
                
                if coverage < min_percentage:
                    recommendations.append(
                        f"Focus on {language} tests - currently at {coverage:.1f}% coverage with {uncovered_lines} uncovered lines"
                    )
            
            # General testing recommendations
            if uncovered_lines > 0:
                recommendations.append(
                    "Add unit tests for uncovered code paths and edge cases"
                )
                
            if overall_coverage < 50:
                recommendations.append(
                    "Consider implementing a test-driven development approach"
                )
        
        elif overall_coverage >= min_percentage:
            if overall_coverage >= min_percentage + 10:
                recommendations.append(
                    f"Excellent! {overall_coverage:.1f}% coverage exceeds the {min_percentage}% requirement"
                )
            else:
                recommendations.append(
                    f"Good! {overall_coverage:.1f}% coverage meets the {min_percentage}% requirement"
                )
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for coverage."""
        return ["python", "javascript", "php"]
    
    def validate_configuration(self) -> List[str]:
        """Validate coverage gate configuration."""
        errors = super().validate_configuration()
        
        # Check min_percentage threshold
        min_percentage = self.get_threshold_value("min_percentage")
        if min_percentage is not None:
            if not isinstance(min_percentage, (int, float)) or min_percentage < 0 or min_percentage > 100:
                errors.append("min_percentage must be a number between 0 and 100")
        
        # Check if any tools are configured
        tools_config = self.config.threshold_config.get("tools", {})
        if not tools_config:
            errors.append("At least one coverage tool must be configured")
            return errors
        
        # Validate each tool configuration
        for language, tool_config in tools_config.items():
            if not tool_config.get("enabled", False):
                continue
            
            command = tool_config.get("command", "")
            if not command:
                errors.append(f"Command is required for {language} coverage")
        
        return errors