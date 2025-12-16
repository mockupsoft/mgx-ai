# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.type_check_gate

Quality gate for type checking using TypeScript and MyPy.
"""

import json
import subprocess
import os
from typing import Dict, List, Optional, Any
import asyncio
import logging
import glob

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.TYPE_CHECK)


class TypeCheckGate(BaseQualityGate):
    """Quality gate for type checking."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.TYPE_CHECK, config)
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
        """Evaluate type checking quality gate."""
        
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
            total_errors = 0
            total_warnings = 0
            language_results = {}
            all_issues = []
            
            # Process each supported language
            for language in self.get_supported_languages():
                language_config = self.config.threshold_config.get("tools", {}).get(language, {})
                
                if not language_config.get("enabled", False):
                    continue
                
                language_result = await self._evaluate_language_type_check(
                    language, language_config, working_directory or os.getcwd()
                )
                
                if language_result:
                    language_results[language] = language_result
                    total_errors += language_result.get("errors", 0)
                    total_warnings += language_result.get("warnings", 0)
                    all_issues.extend(language_result.get("issues", []))
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Get thresholds
            strict_mode = self.get_threshold_value("strict_mode", False)
            
            # Determine gate result
            passed = total_errors == 0
            passed_with_warnings = total_errors == 0 and total_warnings == 0
            status = QualityGateStatus.PASSED
            
            if not passed:
                status = QualityGateStatus.FAILED
            elif not passed_with_warnings:
                status = QualityGateStatus.WARNING
            
            # Generate recommendations
            recommendations = self._generate_recommendations(total_errors, total_warnings, all_issues, strict_mode)
            
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
                    "strict_mode": strict_mode
                },
                metrics={
                    "type_errors": total_errors,
                    "type_warnings": total_warnings,
                    "files_checked": sum(r.get("files_checked", 0) for r in language_results.values())
                },
                recommendations=recommendations,
                total_issues=total_errors + total_warnings,
                critical_issues=total_errors,  # Type errors are critical
                high_issues=total_warnings  # Type warnings are high severity
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Type check gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _evaluate_language_type_check(
        self,
        language: str,
        language_config: Dict[str, Any],
        working_directory: str
    ) -> Optional[Dict[str, Any]]:
        """Evaluate type checking for a specific language."""
        
        try:
            if language == "typescript":
                return await self._typecheck_typescript(language_config, working_directory)
            elif language == "python":
                return await self._typecheck_python(language_config, working_directory)
            else:
                self.logger.warning(f"Unsupported language for type checking: {language}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error type checking {language}: {str(e)}")
            return None
    
    async def _typecheck_typescript(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Type check TypeScript code using tsc."""
        
        command = config.get("command", "npx tsc --noEmit --pretty")
        
        try:
            # Check if TypeScript files exist
            ts_files = await self._find_typescript_files(working_directory)
            
            if not ts_files:
                return {
                    "language": "typescript",
                    "errors": 0,
                    "warnings": 0,
                    "issues": [],
                    "files_checked": 0,
                    "message": "No TypeScript files found"
                }
            
            # Get strict mode setting
            strict_mode = config.get("strict_mode", self.get_threshold_value("strict_mode", False))
            
            # Build TypeScript compiler command
            cmd_parts = command.split()
            if strict_mode:
                cmd_parts.append("--strict")
            else:
                cmd_parts.extend(["--noImplicitAny", "false", "--strictPropertyInitialization", "false"])
            
            # Add files to check
            cmd_parts.extend(ts_files)
            
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
            
            # Parse TypeScript compiler output
            output_text = stdout.decode() + stderr.decode()
            
            if output_text:
                lines = output_text.split('\n')
                
                for line in lines:
                    # Parse TypeScript error lines
                    # Format: file.ts(line,col): error TS2304: Cannot find name 'x'.
                    if 'error TS' in line or 'warning TS' in line:
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            file_path = parts[0]
                            location_part = parts[1].strip()
                            severity_part = parts[2].strip()
                            message_part = parts[3].strip()
                            
                            # Parse line and column
                            line_col_match = location_part.split(',')
                            line_number = int(line_col_match[0]) if line_col_match[0].strip().isdigit() else 0
                            column_number = int(line_col_match[1]) if len(line_col_match) > 1 and line_col_match[1].strip().isdigit() else 0
                            
                            # Determine severity
                            is_error = 'error TS' in severity_part
                            severity = 'error' if is_error else 'warning'
                            
                            if is_error:
                                errors += 1
                            else:
                                warnings += 1
                            
                            issue = {
                                "file": file_path,
                                "line": line_number,
                                "column": column_number,
                                "message": message_part,
                                "severity": severity,
                                "type": "typescript"
                            }
                            issues.append(issue)
            
            return {
                "language": "typescript",
                "errors": errors,
                "warnings": warnings,
                "issues": issues,
                "files_checked": len(ts_files),
                "command": " ".join(cmd_parts),
                "strict_mode": strict_mode,
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"TypeScript type checking failed: {str(e)}")
            return {
                "language": "typescript",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "files_checked": 0,
                "error": str(e)
            }
    
    async def _typecheck_python(
        self,
        config: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """Type check Python code using MyPy."""
        
        command = config.get("command", "mypy --show-error-codes --show-column-numbers")
        
        try:
            # Check if Python files exist
            py_files = await self._find_python_files(working_directory)
            
            if not py_files:
                return {
                    "language": "python",
                    "errors": 0,
                    "warnings": 0,
                    "issues": [],
                    "files_checked": 0,
                    "message": "No Python files found"
                }
            
            # Get strict mode setting
            strict_mode = config.get("strict_mode", self.get_threshold_value("strict_mode", False))
            ignore_missing_imports = config.get("ignore_missing_imports", True)
            
            # Build MyPy command
            cmd_parts = command.split()
            
            if strict_mode:
                cmd_parts.append("--strict")
            
            if ignore_missing_imports:
                cmd_parts.append("--ignore-missing-imports")
            
            # Add files to check
            cmd_parts.extend(py_files)
            
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
            
            # Parse MyPy output
            output_text = stdout.decode()
            
            if output_text:
                lines = output_text.split('\n')
                
                for line in lines:
                    # Parse MyPy output lines
                    # Format: file.py:line:col: error: Cannot infer type of Name "x"  [attr-defined]
                    if ':' in line and ('error:' in line or 'note:' in line or 'warning:' in line):
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            file_path = parts[0]
                            line_part = parts[1].strip()
                            col_part = parts[2].strip()
                            message_part = parts[3].strip()
                            
                            # Parse line and column
                            line_number = int(line_part) if line_part.isdigit() else 0
                            column_number = int(col_part) if col_part.isdigit() else 0
                            
                            # Determine severity
                            if 'error:' in message_part:
                                severity = 'error'
                                errors += 1
                            elif 'warning:' in message_part:
                                severity = 'warning'
                                warnings += 1
                            else:
                                severity = 'note'
                            
                            # Extract error code if present [attr-defined]
                            error_code = ""
                            code_match = message_part.rfind('[')
                            if code_match != -1:
                                code_end = message_part.rfind(']')
                                if code_end != -1:
                                    error_code = message_part[code_match + 1:code_end]
                                    message_part = message_part[:code_match].strip()
                            
                            issue = {
                                "file": file_path,
                                "line": line_number,
                                "column": column_number,
                                "message": message_part,
                                "severity": severity,
                                "error_code": error_code,
                                "type": "python"
                            }
                            issues.append(issue)
            
            return {
                "language": "python",
                "errors": errors,
                "warnings": warnings,
                "issues": issues,
                "files_checked": len(py_files),
                "command": " ".join(cmd_parts),
                "strict_mode": strict_mode,
                "ignore_missing_imports": ignore_missing_imports,
                "exit_code": result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"Python type checking failed: {str(e)}")
            return {
                "language": "python",
                "errors": 0,
                "warnings": 0,
                "issues": [],
                "files_checked": 0,
                "error": str(e)
            }
    
    async def _find_typescript_files(self, working_directory: str) -> List[str]:
        """Find TypeScript files in the working directory."""
        
        patterns = ["**/*.ts", "**/*.tsx"]
        exclude_patterns = [
            "**/node_modules/**",
            "**/dist/**",
            "**/build/**",
            "**/.git/**",
            "**/generated/**"
        ]
        
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
    
    async def _find_python_files(self, working_directory: str) -> List[str]:
        """Find Python files in the working directory."""
        
        patterns = ["**/*.py"]
        exclude_patterns = [
            "**/__pycache__/**",
            "**/.venv/**",
            "**/venv/**",
            "**/.tox/**",
            "**/build/**",
            "**/dist/**",
            "**/.git/**",
            "**/generated/**"
        ]
        
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
        total_errors: int,
        total_warnings: int,
        issues: List[Dict[str, Any]],
        strict_mode: bool
    ) -> List[str]:
        """Generate type checking recommendations."""
        
        recommendations = []
        
        if total_errors == 0 and total_warnings == 0:
            if strict_mode:
                recommendations.append("Excellent! All type checks pass even in strict mode.")
            else:
                recommendations.append("Excellent! All type checks pass. Consider enabling strict mode for even better type safety.")
            return recommendations
        
        # Error recommendations
        if total_errors > 0:
            recommendations.append(
                self.create_recommendation(
                    "Type Safety",
                    f"Fix {total_errors} type errors to ensure type safety",
                    GateSeverity.HIGH
                )
            )
            
            # Group issues by error code or rule for actionable recommendations
            error_codes = {}
            files_with_errors = {}
            
            for issue in issues:
                if issue.get("severity") == "error":
                    # Group by error code
                    error_code = issue.get("error_code", "unknown")
                    error_codes[error_code] = error_codes.get(error_code, 0) + 1
                    
                    # Group by file
                    file_path = issue.get("file", "")
                    if file_path not in files_with_errors:
                        files_with_errors[file_path] = 0
                    files_with_errors[file_path] += 1
            
            # Most common error types
            if error_codes:
                top_errors = sorted(error_codes.items(), key=lambda x: x[1], reverse=True)[:3]
                for error_code, count in top_errors:
                    recommendations.append(f"Address type errors ({error_code}): {count} occurrences")
            
            # Files with most errors
            if files_with_errors:
                top_files = sorted(files_with_errors.items(), key=lambda x: x[1], reverse=True)[:3]
                for file_path, count in top_files:
                    filename = os.path.basename(file_path)
                    recommendations.append(f"Focus on {filename}: {count} type errors")
        
        # Warning recommendations
        if total_warnings > 0:
            recommendations.append(
                self.create_recommendation(
                    "Type Safety",
                    f"Address {total_warnings} type warnings to improve code quality",
                    GateSeverity.MEDIUM
                )
            )
            
            if not strict_mode:
                recommendations.append("Consider enabling strict type checking mode")
        
        # Language-specific recommendations
        typescript_issues = [i for i in issues if i.get("type") == "typescript"]
        python_issues = [i for i in issues if i.get("type") == "python"]
        
        if typescript_issues:
            ts_errors = len([i for i in typescript_issues if i.get("severity") == "error"])
            if ts_errors > 0:
                recommendations.append("TypeScript: Add proper type annotations to resolve type errors")
                recommendations.append("Consider using union types, interfaces, and generics for better type safety")
        
        if python_issues:
            py_errors = len([i for i in python_issues if i.get("severity") == "error"])
            if py_errors > 0:
                recommendations.append("Python: Add type hints to function parameters and return values")
                recommendations.append("Use TypedDict, NamedTuple, or dataclasses for complex data structures")
        
        # Strict mode recommendations
        if strict_mode and (total_errors > 0 or total_warnings > 0):
            recommendations.append("Strict mode is enabled - consider temporarily disabling for gradual type adoption")
        elif not strict_mode and total_errors == 0:
            recommendations.append("All checks pass in basic mode - enabling strict mode could catch more issues")
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for type checking."""
        return ["typescript", "python"]
    
    def validate_configuration(self) -> List[str]:
        """Validate type check gate configuration."""
        errors = super().validate_configuration()
        
        # Check if any tools are configured
        tools_config = self.config.threshold_config.get("tools", {})
        if not tools_config:
            errors.append("At least one type checking tool must be configured")
            return errors
        
        # Validate each tool configuration
        for language, tool_config in tools_config.items():
            if not tool_config.get("enabled", False):
                continue
            
            command = tool_config.get("command", "")
            if not command:
                errors.append(f"Command is required for {language} type checking")
        
        return errors