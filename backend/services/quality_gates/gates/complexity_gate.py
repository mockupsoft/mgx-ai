# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.complexity_gate

Quality gate for code complexity analysis and limits.
"""

import json
import subprocess
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import logging
import glob
from pathlib import Path

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.COMPLEXITY)


class ComplexityGate(BaseQualityGate):
    """Quality gate for code complexity analysis."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.COMPLEXITY, config)
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
        """Evaluate complexity quality gate."""
        
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
            file_results = {}
            language_results = {}
            total_functions = 0
            functions_above_threshold = 0
            files_above_threshold = 0
            total_issues = 0
            
            # Process each supported language
            for language in self.get_supported_languages():
                language_config = self.config.threshold_config.get("tools", {}).get(language, {})
                
                if not language_config.get("enabled", False):
                    continue
                
                language_result = await self._analyze_language_complexity(
                    language, language_config, working_directory or os.getcwd()
                )
                
                if language_result:
                    language_results[language] = language_result
                    total_functions += language_result.get("total_functions", 0)
                    functions_above_threshold += language_result.get("functions_above_threshold", 0)
                    files_above_threshold += language_result.get("files_above_threshold", 0)
                    
                    for file_path, file_data in language_result.get("file_details", {}).items():
                        file_results[file_path] = file_data
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Get thresholds
            max_cyclomatic = self.get_threshold_value("max_cyclomatic", 10)
            max_cognitive = self.get_threshold_value("max_cognitive", 15)
            max_lines_per_function = self.get_threshold_value("max_lines_per_function", 50)
            max_nesting_level = self.get_threshold_value("max_nesting_level", 4)
            
            # Determine gate result
            total_issues = functions_above_threshold
            passed = total_issues == 0
            passed_with_warnings = total_issues <= 5  # Allow up to 5 minor issues
            status = QualityGateStatus.PASSED
            
            if not passed:
                if functions_above_threshold > 10:
                    status = QualityGateStatus.FAILED
                elif functions_above_threshold > 5:
                    passed_with_warnings = True
                    status = QualityGateStatus.WARNING
                else:
                    passed_with_warnings = True
                    status = QualityGateStatus.WARNING
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                total_functions, functions_above_threshold, files_above_threshold,
                language_results, max_cyclomatic, max_cognitive, max_lines_per_function
            )
            
            # Update context with results
            context = self.get_execution_context()
            context.update({
                "total_functions": total_functions,
                "functions_above_threshold": functions_above_threshold,
                "files_above_threshold": files_above_threshold,
                "language_results": language_results,
                "file_results": file_results
            })
            
            result = GateResult(
                gate_type=self.gate_type,
                status=status,
                passed=passed,
                passed_with_warnings=passed_with_warnings,
                execution_time_ms=execution_time_ms,
                details={
                    "total_functions": total_functions,
                    "functions_above_threshold": functions_above_threshold,
                    "files_above_threshold": files_above_threshold,
                    "pass_rate": round(((total_functions - functions_above_threshold) / total_functions) * 100, 2) if total_functions > 0 else 100,
                    "thresholds": {
                        "max_cyclomatic": max_cyclomatic,
                        "max_cognitive": max_cognitive,
                        "max_lines_per_function": max_lines_per_function,
                        "max_nesting_level": max_nesting_level
                    },
                    "language_results": language_results,
                    "file_results": file_results
                },
                metrics={
                    "total_functions": total_functions,
                    "complex_functions": functions_above_threshold,
                    "complex_files": files_above_threshold,
                    "complexity_violations": total_issues
                },
                recommendations=recommendations,
                total_issues=total_issues,
                medium_issues=functions_above_threshold,  # Medium severity for complexity violations
                low_issues=files_above_threshold - functions_above_threshold if files_above_threshold > functions_above_threshold else 0
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Complexity gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _analyze_language_complexity(
        self,
        language: str,
        language_config: Dict[str, Any],
        working_directory: str
    ) -> Optional[Dict[str, Any]]:
        """Analyze complexity for a specific language."""
        
        try:
            if language == "python":
                return await self._analyze_python_complexity(language_config, working_directory)
            elif language == "javascript":
                return await self._analyze_javascript_complexity(language_config, working_directory)
            elif language == "php":
                return await self._analyze_php_complexity(language_config, working_directory)
            else:
                self.logger.warning(f"Unsupported language for complexity analysis: {language}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error analyzing {language} complexity: {str(e)}")
            return None
    
    async def _analyze_python_complexity(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Analyze Python complexity using Radon."""
        
        command = config.get("command", "radon cc --show-complexity --average")
        
        try:
            # Find Python files to analyze
            python_files = await self._find_python_files(working_directory)
            
            if not python_files:
                return {
                    "language": "python",
                    "total_functions": 0,
                    "functions_above_threshold": 0,
                    "files_above_threshold": 0,
                    "file_details": {},
                    "message": "No Python files found"
                }
            
            # Run radon command
            cmd_parts = command.split()
            cmd_parts.extend(python_files)
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            # Parse radon output
            functions = []
            file_details = {}
            
            if stdout:
                output_text = stdout.decode()
                functions = self._parse_radon_output(output_text)
            
            # Calculate metrics
            total_functions = len(functions)
            functions_above_threshold = 0
            
            max_cyclomatic = self.get_threshold_value("max_cyclomatic", 10)
            max_cognitive = self.get_threshold_value("max_cognitive", 15)
            max_lines_per_function = self.get_threshold_value("max_lines_per_function", 50)
            max_nesting_level = self.get_threshold_value("max_nesting_level", 4)
            
            # Group by file
            file_complexities = {}
            
            for func in functions:
                file_path = func.get("file", "")
                cyclomatic = func.get("cyclomatic", 0)
                cognitive = func.get("cognitive", cyclomatic)  # Default to cyclomatic if cognitive not available
                lines = func.get("lines", 0)
                nesting = func.get("nesting", 1)  # Default nesting level
                
                # Count violations
                if (cyclomatic > max_cyclomatic or 
                    cognitive > max_cognitive or 
                    lines > max_lines_per_function or 
                    nesting > max_nesting_level):
                    functions_above_threshold += 1
                
                # Group by file
                if file_path not in file_complexities:
                    file_complexities[file_path] = {
                        "functions": [],
                        "max_cyclomatic": 0,
                        "max_cognitive": 0,
                        "total_functions": 0,
                        "complex_functions": 0
                    }
                
                file_complexities[file_path]["functions"].append(func)
                file_complexities[file_path]["max_cyclomatic"] = max(file_complexities[file_path]["max_cyclomatic"], cyclomatic)
                file_complexities[file_path]["max_cognitive"] = max(file_complexities[file_path]["max_cognitive"], cognitive)
                file_complexities[file_path]["total_functions"] += 1
                
                if (cyclomatic > max_cyclomatic or 
                    cognitive > max_cognitive or 
                    lines > max_lines_per_function or 
                    nesting > max_nesting_level):
                    file_complexities[file_path]["complex_functions"] += 1
            
            files_above_threshold = sum(1 for f in file_complexities.values() if f["complex_functions"] > 0)
            
            return {
                "language": "python",
                "total_functions": total_functions,
                "functions_above_threshold": functions_above_threshold,
                "files_above_threshold": files_above_threshold,
                "file_details": file_complexities,
                "raw_functions": functions,
                "command": command,
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"Python complexity analysis failed: {str(e)}")
            return {
                "language": "python",
                "total_functions": 0,
                "functions_above_threshold": 0,
                "files_above_threshold": 0,
                "file_details": {},
                "error": str(e)
            }
    
    async def _analyze_javascript_complexity(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Analyze JavaScript complexity using ESLint complexity rule."""
        
        # Use ESLint to analyze complexity
        command = config.get("command", "npx eslint --format json --rule 'complexity: [\"error\", 10]' --no-eslintrc")
        
        try:
            # Find JavaScript/TypeScript files to analyze
            js_files = await self._find_javascript_files(working_directory)
            
            if not js_files:
                return {
                    "language": "javascript",
                    "total_functions": 0,
                    "functions_above_threshold": 0,
                    "files_above_threshold": 0,
                    "file_details": {},
                    "message": "No JavaScript/TypeScript files found"
                }
            
            # Run ESLint command
            cmd_parts = command.split()
            cmd_parts.extend(js_files)
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            # Parse ESLint output
            functions = []
            file_details = {}
            
            if stdout:
                try:
                    eslint_output = json.loads(stdout.decode())
                    
                    for file_issues in eslint_output:
                        file_path = file_issues.get("filePath", "")
                        complexity_messages = [
                            msg for msg in file_issues.get("messages", []) 
                            if msg.get("ruleId") == "complexity"
                        ]
                        
                        for message in complexity_messages:
                            # Extract complexity value from message
                            message_text = message.get("message", "")
                            complexity_match = re.search(r'complexity of (\d+)', message_text)
                            complexity = int(complexity_match.group(1)) if complexity_match else 10
                            
                            function_info = {
                                "file": file_path,
                                "line": message.get("line"),
                                "complexity": complexity,
                                "type": "function"  # ESLint doesn't distinguish function types easily
                            }
                            functions.append(function_info)
                            
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse ESLint complexity output")
            
            # Calculate metrics
            total_functions = len(functions)
            functions_above_threshold = 0
            
            max_cyclomatic = self.get_threshold_value("max_cyclomatic", 10)
            max_cognitive = self.get_threshold_value("max_cognitive", 15)
            
            # Group by file
            file_complexities = {}
            
            for func in functions:
                file_path = func.get("file", "")
                cyclomatic = func.get("complexity", 0)
                
                # Count violations
                if cyclomatic > max_cyclomatic:
                    functions_above_threshold += 1
                
                # Group by file
                if file_path not in file_complexities:
                    file_complexities[file_path] = {
                        "functions": [],
                        "max_cyclomatic": 0,
                        "max_cognitive": 0,
                        "total_functions": 0,
                        "complex_functions": 0
                    }
                
                file_complexities[file_path]["functions"].append(func)
                file_complexities[file_path]["max_cyclomatic"] = max(file_complexities[file_path]["max_cyclomatic"], cyclomatic)
                file_complexities[file_path]["total_functions"] += 1
                
                if cyclomatic > max_cyclomatic:
                    file_complexities[file_path]["complex_functions"] += 1
            
            files_above_threshold = sum(1 for f in file_complexities.values() if f["complex_functions"] > 0)
            
            return {
                "language": "javascript",
                "total_functions": total_functions,
                "functions_above_threshold": functions_above_threshold,
                "files_above_threshold": files_above_threshold,
                "file_details": file_complexities,
                "raw_functions": functions,
                "command": " ".join(cmd_parts),
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"JavaScript complexity analysis failed: {str(e)}")
            return {
                "language": "javascript",
                "total_functions": 0,
                "functions_above_threshold": 0,
                "files_above_threshold": 0,
                "file_details": {},
                "error": str(e)
            }
    
    async def _analyze_php_complexity(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Analyze PHP complexity using PHPMD (mess detector)."""
        
        try:
            # Find PHP files to analyze
            php_files = await self._find_php_files(working_directory)
            
            if not php_files:
                return {
                    "language": "php",
                    "total_functions": 0,
                    "functions_above_threshold": 0,
                    "files_above_threshold": 0,
                    "file_details": {},
                    "message": "No PHP files found"
                }
            
            # Use PHPMD for complexity analysis
            command = "phpmd php xml codesize --minimumpriority=5"
            
            cmd_parts = command.split()
            cmd_parts.extend(php_files)
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            # Parse PHPMD XML output
            functions = []
            file_details = {}
            
            if stdout:
                import xml.etree.ElementTree as ET
                
                try:
                    root = ET.fromstring(stdout.decode())
                    
                    for file_elem in root.findall(".//file"):
                        file_path = file_elem.get("name", "")
                        
                        for violation in file_elem.findall(".//violation"):
                            rule = violation.get("rule", "")
                            priority = int(violation.get("priority", "3"))
                            
                            # Only consider cyclomatic complexity violations
                            if "cyclomatic" in rule.lower() or "complexity" in rule.lower():
                                line = int(violation.get("beginline", 0))
                                message = violation.text or ""
                                
                                # Extract complexity from message
                                complexity_match = re.search(r'complexity of (\d+)', message)
                                complexity = int(complexity_match.group(1)) if complexity_match else 10
                                
                                function_info = {
                                    "file": file_path,
                                    "line": line,
                                    "complexity": complexity,
                                    "rule": rule,
                                    "message": message
                                }
                                functions.append(function_info)
                                
                except ET.ParseError:
                    self.logger.warning("Failed to parse PHPMD XML output")
            
            # Calculate metrics
            total_functions = len(functions)
            functions_above_threshold = 0
            
            max_cyclomatic = self.get_threshold_value("max_cyclomatic", 10)
            
            # Group by file
            file_complexities = {}
            
            for func in functions:
                file_path = func.get("file", "")
                cyclomatic = func.get("complexity", 0)
                
                # Count violations
                if cyclomatic > max_cyclomatic:
                    functions_above_threshold += 1
                
                # Group by file
                if file_path not in file_complexities:
                    file_complexities[file_path] = {
                        "functions": [],
                        "max_cyclomatic": 0,
                        "max_cognitive": 0,
                        "total_functions": 0,
                        "complex_functions": 0
                    }
                
                file_complexities[file_path]["functions"].append(func)
                file_complexities[file_path]["max_cyclomatic"] = max(file_complexities[file_path]["max_cyclomatic"], cyclomatic)
                file_complexities[file_path]["total_functions"] += 1
                
                if cyclomatic > max_cyclomatic:
                    file_complexities[file_path]["complex_functions"] += 1
            
            files_above_threshold = sum(1 for f in file_complexities.values() if f["complex_functions"] > 0)
            
            return {
                "language": "php",
                "total_functions": total_functions,
                "functions_above_threshold": functions_above_threshold,
                "files_above_threshold": files_above_threshold,
                "file_details": file_complexities,
                "raw_functions": functions,
                "command": " ".join(cmd_parts),
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"PHP complexity analysis failed: {str(e)}")
            return {
                "language": "php",
                "total_functions": 0,
                "functions_above_threshold": 0,
                "files_above_threshold": 0,
                "file_details": {},
                "error": str(e)
            }
    
    def _parse_radon_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse Radon output to extract function complexity information."""
        
        functions = []
        lines = output.strip().split('\n')
        
        for line in lines:
            # Radon output format: file:function:line:cyclomatic:cognitive:nesting:lines:rank
            if ':' in line and '/' in line:
                parts = line.split(':')
                if len(parts) >= 6:
                    file_path = parts[0]
                    function_name = parts[1]
                    line_number = int(parts[2]) if parts[2].isdigit() else 0
                    cyclomatic = int(parts[3]) if parts[3].isdigit() else 0
                    cognitive = int(parts[4]) if parts[4].isdigit() else 0
                    nesting = int(parts[5]) if parts[5].isdigit() else 1
                    lines_count = int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 0
                    rank = parts[-1] if len(parts) > 7 else "A"
                    
                    function_info = {
                        "file": file_path,
                        "function": function_name,
                        "line": line_number,
                        "cyclomatic": cyclomatic,
                        "cognitive": cognitive,
                        "nesting": nesting,
                        "lines": lines_count,
                        "rank": rank
                    }
                    functions.append(function_info)
        
        return functions
    
    async def _find_python_files(self, working_directory: str) -> List[str]:
        """Find Python files in the working directory."""
        
        patterns = ["**/*.py"]
        exclude_patterns = self.get_threshold_value("exclude_patterns", [
            "**/generated/**", "**/tests/**", "**/__pycache__/**", "**/.venv/**"
        ])
        
        files = []
        
        for pattern in patterns:
            pattern_files = glob.glob(os.path.join(working_directory, pattern), recursive=True)
            files.extend(pattern_files)
        
        # Filter out excluded patterns
        filtered_files = []
        for file_path in set(files):
            should_exclude = False
            for exclude_pattern in exclude_patterns:
                if exclude_pattern.endswith('**'):
                    exclude_pattern = exclude_pattern[:-2]
                if exclude_pattern in file_path:
                    should_exclude = True
                    break
            if not should_exclude:
                filtered_files.append(file_path)
        
        return filtered_files
    
    async def _find_javascript_files(self, working_directory: str) -> List[str]:
        """Find JavaScript/TypeScript files in the working directory."""
        
        patterns = ["**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        exclude_patterns = self.get_threshold_value("exclude_patterns", [
            "**/generated/**", "**/node_modules/**", "**/bower_components/**"
        ])
        
        files = []
        
        for pattern in patterns:
            pattern_files = glob.glob(os.path.join(working_directory, pattern), recursive=True)
            files.extend(pattern_files)
        
        # Filter out excluded patterns
        filtered_files = []
        for file_path in set(files):
            should_exclude = False
            for exclude_pattern in exclude_patterns:
                if exclude_pattern.endswith('**'):
                    exclude_pattern = exclude_pattern[:-2]
                if exclude_pattern in file_path:
                    should_exclude = True
                    break
            if not should_exclude:
                filtered_files.append(file_path)
        
        return filtered_files
    
    async def _find_php_files(self, working_directory: str) -> List[str]:
        """Find PHP files in the working directory."""
        
        patterns = ["**/*.php"]
        exclude_patterns = self.get_threshold_value("exclude_patterns", [
            "**/generated/**", "**/vendor/**"
        ])
        
        files = []
        
        for pattern in patterns:
            pattern_files = glob.glob(os.path.join(working_directory, pattern), recursive=True)
            files.extend(pattern_files)
        
        # Filter out excluded patterns
        filtered_files = []
        for file_path in set(files):
            should_exclude = False
            for exclude_pattern in exclude_patterns:
                if exclude_pattern.endswith('**'):
                    exclude_pattern = exclude_pattern[:-2]
                if exclude_pattern in file_path:
                    should_exclude = True
                    break
            if not should_exclude:
                filtered_files.append(file_path)
        
        return filtered_files
    
    def _generate_recommendations(
        self,
        total_functions: int,
        functions_above_threshold: int,
        files_above_threshold: int,
        language_results: Dict[str, Any],
        max_cyclomatic: int,
        max_cognitive: int,
        max_lines_per_function: int
    ) -> List[str]:
        """Generate complexity recommendations."""
        
        recommendations = []
        
        if total_functions == 0:
            recommendations.append("No functions found for complexity analysis")
            return recommendations
        
        violation_rate = (functions_above_threshold / total_functions) * 100
        
        # Overall recommendations
        if functions_above_threshold > 0:
            if violation_rate > 20:
                recommendations.append(
                    self.create_recommendation(
                        "Code Complexity",
                        f"High complexity rate: {functions_above_threshold}/{total_functions} functions ({violation_rate:.1f}%) exceed thresholds",
                        GateSeverity.HIGH
                    )
                )
            else:
                recommendations.append(
                    self.create_recommendation(
                        "Code Complexity",
                        f"Moderate complexity: {functions_above_threshold}/{total_functions} functions need attention",
                        GateSeverity.MEDIUM
                    )
                )
            
            recommendations.append("Consider refactoring complex functions into smaller, more manageable pieces")
        
        # Language-specific recommendations
        for language, result in language_results.items():
            complex_functions = result.get("functions_above_threshold", 0)
            total_lang_functions = result.get("total_functions", 0)
            
            if complex_functions > 0:
                lang_violation_rate = (complex_functions / total_lang_functions) * 100 if total_lang_functions > 0 else 0
                
                if lang_violation_rate > 25:
                    recommendations.append(f"{language.title()}: {complex_functions} complex functions found - refactor high-complexity code")
                elif lang_violation_rate > 10:
                    recommendations.append(f"{language.title()}: {complex_functions} functions exceed complexity thresholds")
        
        # Function-level recommendations
        for language, result in language_results.items():
            file_details = result.get("file_details", {})
            
            # Find most complex files
            complex_files = [(file, data) for file, data in file_details.items() if data.get("complex_functions", 0) > 0]
            complex_files.sort(key=lambda x: x[1]["complex_functions"], reverse=True)
            
            if complex_files:
                recommendations.append(f"{language.title()}: Focus on these complex files:")
                for file_path, file_data in complex_files[:3]:  # Top 3 files
                    complex_count = file_data["complex_functions"]
                    total_count = file_data["total_functions"]
                    max_complexity = file_data["max_cyclomatic"]
                    
                    filename = os.path.basename(file_path)
                    recommendations.append(f"  - {filename}: {complex_count}/{total_count} functions complex (max: {max_complexity})")
                
                if len(complex_files) > 3:
                    recommendations.append(f"  ... and {len(complex_files) - 3} more complex files")
        
        # Specific recommendations based on thresholds
        if max_cyclomatic <= 5:
            recommendations.append("Strict cyclomatic complexity limit - consider more granular function design")
        elif max_cyclomatic >= 15:
            recommendations.append("Higher complexity limit - ensure adequate testing and documentation")
        
        # Positive feedback
        if functions_above_threshold == 0:
            recommendations.append("Excellent! All functions are within complexity thresholds.")
        elif violation_rate < 5:
            recommendations.append("Low complexity violation rate - code quality is good.")
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for complexity analysis."""
        return ["python", "javascript", "php"]
    
    def validate_configuration(self) -> List[str]:
        """Validate complexity gate configuration."""
        errors = super().validate_configuration()
        
        # Check threshold values
        thresholds = [
            ("max_cyclomatic", "positive integer"),
            ("max_cognitive", "positive integer"),
            ("max_lines_per_function", "positive integer"),
            ("max_nesting_level", "positive integer")
        ]
        
        for threshold, description in thresholds:
            value = self.get_threshold_value(threshold)
            if value is not None and (not isinstance(value, int) or value <= 0):
                errors.append(f"{threshold} must be a positive integer")
        
        # Check if any tools are configured
        tools_config = self.config.threshold_config.get("tools", {})
        if not tools_config:
            errors.append("At least one complexity analysis tool must be configured")
            return errors
        
        # Validate each tool configuration
        for language, tool_config in tools_config.items():
            if not tool_config.get("enabled", False):
                continue
            
            command = tool_config.get("command", "")
            if not command:
                errors.append(f"Command is required for {language} complexity analysis")
        
        return errors