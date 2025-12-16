# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.lint_gate

Quality gate for code linting using ESLint, Ruff, and Pint.
"""

import json
import subprocess
import os
import re
from typing import Dict, List, Optional, Any
import asyncio
import logging

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.LINT)


class LintGate(BaseQualityGate):
    """Quality gate for code linting."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.LINT, config)
        self.logger = logging.getLogger(__name__)
    
    async def evaluate(
        self,
        workspace_id: str,
        project_id: str,
        task_id: Optional[str] = None,
        task_run_id: Optional[str] = None,
        sandbox_execution_id: Optional[str] = None,
        code_files: Optional[List[str]] = None,
        working_directory: Optional[str] = None,
        **kwargs
    ) -> GateResult:
        """Evaluate linting quality gate."""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Set execution context
            self.set_execution_context({
                "workspace_id": workspace_id,
                "project_id": project_id,
                "code_files": code_files or [],
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
            total_errors = 0
            total_warnings = 0
            all_issues = []
            language_results = {}
            
            # Process each supported language
            for language in self.get_supported_languages():
                language_config = self.config.threshold_config.get("tools", {}).get(language, {})
                
                if not language_config.get("enabled", False):
                    continue
                
                language_result = await self._evaluate_language_lint(
                    language, language_config, working_directory, code_files
                )
                
                if language_result:
                    language_results[language] = language_result
                    total_errors += language_result.get("errors", 0)
                    total_warnings += language_result.get("warnings", 0)
                    all_issues.extend(language_result.get("issues", []))
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Determine gate result based on thresholds
            fail_on_error = self.get_threshold_value("fail_on_error", True)
            fail_on_warning = self.get_threshold_value("fail_on_warning", False)
            max_warnings = self.get_threshold_value("max_warnings", 10)
            max_errors = self.get_threshold_value("max_errors", 0)
            
            passed = True
            passed_with_warnings = False
            status = QualityGateStatus.PASSED
            
            # Check error threshold
            if total_errors > max_errors:
                passed = False
                status = QualityGateStatus.FAILED
            elif fail_on_error and total_errors > 0:
                passed = False
                status = QualityGateStatus.FAILED
            
            # Check warning threshold
            elif total_warnings > max_warnings:
                passed_with_warnings = True
                status = QualityGateStatus.WARNING if not fail_on_warning else QualityGateStatus.FAILED
                if fail_on_warning:
                    passed = False
            
            # Generate recommendations
            recommendations = self._generate_recommendations(total_errors, total_warnings, all_issues)
            
            # Update context with results
            context = self.get_execution_context()
            context.update({
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "language_results": language_results,
                "issues": all_issues
            })
            
            result = GateResult(
                gate_type=self.gate_type,
                status=status,
                passed=passed,
                passed_with_warnings=passed_with_warnings,
                execution_time_ms=execution_time_ms,
                details={
                    "total_errors": total_errors,
                    "total_warnings": total_warnings,
                    "language_results": language_results,
                    "max_errors": max_errors,
                    "max_warnings": max_warnings,
                    "fail_on_error": fail_on_error,
                    "fail_on_warning": fail_on_warning
                },
                recommendations=recommendations,
                total_issues=total_errors + total_warnings,
                critical_issues=total_errors,  # All linting errors are considered critical
                high_issues=total_warnings  # All warnings are considered high severity
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Lint gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _evaluate_language_lint(
        self,
        language: str,
        language_config: Dict[str, Any],
        working_directory: str,
        code_files: Optional[List[str]]
    ) -> Optional[Dict[str, Any]]:
        """Evaluate linting for a specific language."""
        
        try:
            if language == "javascript":
                return await self._lint_javascript(language_config, working_directory, code_files)
            elif language == "python":
                return await self._lint_python(language_config, working_directory, code_files)
            elif language == "php":
                return await self._lint_php(language_config, working_directory, code_files)
            else:
                self.logger.warning(f"Unsupported language for linting: {language}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error linting {language} code: {str(e)}")
            return None
    
    async def _lint_javascript(
        self,
        config: Dict[str, Any],
        working_directory: str,
        code_files: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Lint JavaScript/TypeScript code using ESLint."""
        
        command = config.get("command", "npx eslint --format json")
        file_patterns = config.get("file_patterns", ["**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"])
        
        # Prepare file list
        files_to_lint = []
        if code_files:
            files_to_lint = [f for f in code_files if any(pattern.endswith(f.split('.')[-1]) for pattern in file_patterns)]
        else:
            # Use find to locate files
            files_to_lint = await self._find_files_by_pattern(working_directory, file_patterns)
        
        if not files_to_lint:
            return {
                "language": "javascript",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "message": "No JavaScript/TypeScript files found"
            }
        
        # Build ESLint command
        cmd_parts = command.split()
        if not cmd_parts[0].startswith("npx"):
            cmd_parts.insert(0, "npx")
        
        cmd_parts.extend(files_to_lint)
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            issues = []
            errors = 0
            warnings = 0
            
            if stdout:
                try:
                    eslint_output = json.loads(stdout.decode())
                    
                    for file_issues in eslint_output:
                        file_path = file_issues.get("filePath", "")
                        file_error_count = file_issues.get("errorCount", 0)
                        file_warning_count = file_issues.get("warningCount", 0)
                        
                        errors += file_error_count
                        warnings += file_warning_count
                        
                        # Process individual messages
                        for message in file_issues.get("messages", []):
                            severity = "error" if message.get("severity") == 2 else "warning"
                            issue = {
                                "file": file_path,
                                "line": message.get("line"),
                                "column": message.get("column"),
                                "message": message.get("message"),
                                "rule": message.get("ruleId"),
                                "severity": severity
                            }
                            issues.append(issue)
                            
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse ESLint output: {e}")
            
            if stderr:
                self.logger.warning(f"ESLint stderr: {stderr.decode()}")
            
            return {
                "language": "javascript",
                "errors": errors,
                "warnings": warnings,
                "issues": issues,
                "command": " ".join(cmd_parts),
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"ESLint execution failed: {str(e)}")
            return {
                "language": "javascript",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "error": str(e)
            }
    
    async def _lint_python(
        self,
        config: Dict[str, Any],
        working_directory: str,
        code_files: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Lint Python code using Ruff."""
        
        command = config.get("command", "ruff check --format json")
        file_patterns = config.get("file_patterns", ["**/*.py"])
        
        # Prepare file list
        files_to_lint = []
        if code_files:
            files_to_lint = [f for f in code_files if f.endswith('.py')]
        else:
            files_to_lint = await self._find_files_by_pattern(working_directory, file_patterns)
        
        if not files_to_lint:
            return {
                "language": "python",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "message": "No Python files found"
            }
        
        # Build Ruff command
        cmd_parts = command.split()
        cmd_parts.extend(files_to_lint)
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            issues = []
            errors = 0
            warnings = 0
            
            if stdout:
                try:
                    ruff_output = json.loads(stdout.decode())
                    
                    for issue in ruff_output:
                        severity = issue.get("severity", "error").lower()
                        issue_type = "error" if severity == "error" else "warning"
                        
                        if issue_type == "error":
                            errors += 1
                        else:
                            warnings += 1
                        
                        parsed_issue = {
                            "file": issue.get("filename", ""),
                            "line": issue.get("line"),
                            "column": issue.get("column"),
                            "message": issue.get("message", ""),
                            "rule": issue.get("code", ""),
                            "severity": issue_type
                        }
                        issues.append(parsed_issue)
                        
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse Ruff output: {e}")
            
            if stderr:
                self.logger.warning(f"Ruff stderr: {stderr.decode()}")
            
            return {
                "language": "python",
                "errors": errors,
                "warnings": warnings,
                "issues": issues,
                "command": " ".join(cmd_parts),
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"Ruff execution failed: {str(e)}")
            return {
                "language": "python",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "error": str(e)
            }
    
    async def _lint_php(
        self,
        config: Dict[str, Any],
        working_directory: str,
        code_files: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Lint PHP code using Pint."""
        
        command = config.get("command", "pint --format=json")
        file_patterns = config.get("file_patterns", ["**/*.php"])
        
        # Prepare file list
        files_to_lint = []
        if code_files:
            files_to_lint = [f for f in code_files if f.endswith('.php')]
        else:
            files_to_lint = await self._find_files_by_pattern(working_directory, file_patterns)
        
        if not files_to_lint:
            return {
                "language": "php",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "message": "No PHP files found"
            }
        
        # Build Pint command
        cmd_parts = command.split()
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                *files_to_lint,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            issues = []
            errors = 0
            warnings = 0
            
            # Pint is primarily a code formatter, so we'll check for formatting issues
            if stderr:
                pint_output = stderr.decode()
                if "error" in pint_output.lower() or "warning" in pint_output.lower():
                    errors += 1  # Pint typically reports formatting issues as errors
                    issue = {
                        "file": "multiple",
                        "message": pint_output.strip(),
                        "severity": "error"
                    }
                    issues.append(issue)
            
            return {
                "language": "php",
                "errors": errors,
                "warnings": warnings,
                "issues": issues,
                "command": " ".join(cmd_parts),
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"Pint execution failed: {str(e)}")
            return {
                "language": "php",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "error": str(e)
            }
    
    async def _find_files_by_pattern(
        self,
        working_directory: str,
        patterns: List[str]
    ) -> List[str]:
        """Find files matching given patterns."""
        import glob
        
        files = []
        for pattern in patterns:
            full_pattern = os.path.join(working_directory, pattern)
            matched_files = glob.glob(full_pattern, recursive=True)
            files.extend(matched_files)
        
        # Remove duplicates and filter for actual files
        unique_files = []
        for file_path in set(files):
            if os.path.isfile(file_path):
                unique_files.append(file_path)
        
        return unique_files
    
    def _generate_recommendations(
        self,
        total_errors: int,
        total_warnings: int,
        issues: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on linting results."""
        
        recommendations = []
        
        if total_errors > 0:
            recommendations.append(
                self.create_recommendation(
                    "Code Quality",
                    f"Fix {total_errors} linting errors found in your code",
                    GateSeverity.HIGH
                )
            )
            
            # Group issues by rule/file for better recommendations
            rule_counts = {}
            file_counts = {}
            
            for issue in issues:
                if issue.get("rule"):
                    rule_counts[issue["rule"]] = rule_counts.get(issue["rule"], 0) + 1
                if issue.get("file"):
                    file_counts[issue["file"]] = file_counts.get(issue["file"], 0) + 1
            
            # Top problematic rules
            if rule_counts:
                top_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                for rule, count in top_rules:
                    recommendations.append(
                        f"Address rule '{rule}' which appears in {count} locations"
                    )
            
            # Top problematic files
            if file_counts:
                top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                for file_path, count in top_files:
                    recommendations.append(
                        f"Review file '{file_path}' which has {count} linting issues"
                    )
        
        if total_warnings > 0:
            recommendations.append(
                self.create_recommendation(
                    "Code Quality",
                    f"Address {total_warnings} linting warnings to improve code quality",
                    GateSeverity.MEDIUM
                )
            )
        
        if total_errors == 0 and total_warnings == 0:
            recommendations.append("Excellent! No linting issues found.")
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for linting."""
        return ["javascript", "python", "php"]
    
    def validate_configuration(self) -> List[str]:
        """Validate lint gate configuration."""
        errors = super().validate_configuration()
        
        # Check if any tools are configured
        tools_config = self.config.threshold_config.get("tools", {})
        if not tools_config:
            errors.append("At least one linting tool must be configured")
            return errors
        
        # Validate each tool configuration
        for language, tool_config in tools_config.items():
            if not tool_config.get("enabled", False):
                continue
            
            command = tool_config.get("command", "")
            if not command:
                errors.append(f"Command is required for {language} linting")
            
            file_patterns = tool_config.get("file_patterns", [])
            if not file_patterns:
                errors.append(f"File patterns are required for {language} linting")
        
        return errors