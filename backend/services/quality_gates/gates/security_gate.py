# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.security_gate

Quality gate for security audit and vulnerability scanning.
"""

import json
import subprocess
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import logging
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.SECURITY)


class SecurityGate(BaseQualityGate):
    """Quality gate for security audit and vulnerability scanning."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.SECURITY, config)
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
        """Evaluate security quality gate."""
        
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
            total_vulnerabilities = 0
            critical_vulnerabilities = 0
            high_vulnerabilities = 0
            medium_vulnerabilities = 0
            low_vulnerabilities = 0
            all_issues = []
            tool_results = {}
            
            # Run dependency audit if enabled
            if self.get_threshold_value(["tools", "dependency_audit", "enabled"], False):
                dependency_result = await self._run_dependency_audit(working_directory or os.getcwd())
                if dependency_result:
                    tool_results["dependency_audit"] = dependency_result
                    total_vulnerabilities += dependency_result.get("total_vulnerabilities", 0)
                    critical_vulnerabilities += dependency_result.get("critical_vulnerabilities", 0)
                    high_vulnerabilities += dependency_result.get("high_vulnerabilities", 0)
                    medium_vulnerabilities += dependency_result.get("medium_vulnerabilities", 0)
                    low_vulnerabilities += dependency_result.get("low_vulnerabilities", 0)
                    all_issues.extend(dependency_result.get("issues", []))
            
            # Run code security scan if enabled
            if self.get_threshold_value(["tools", "code_scan", "enabled"], False):
                code_scan_result = await self._run_code_security_scan(working_directory or os.getcwd())
                if code_scan_result:
                    tool_results["code_scan"] = code_scan_result
                    total_vulnerabilities += code_scan_result.get("total_issues", 0)
                    critical_vulnerabilities += code_scan_result.get("critical_issues", 0)
                    high_vulnerabilities += code_scan_result.get("high_issues", 0)
                    medium_vulnerabilities += code_scan_result.get("medium_issues", 0)
                    low_vulnerabilities += code_scan_result.get("low_issues", 0)
                    all_issues.extend(code_scan_result.get("issues", []))
            
            # Run license check if enabled
            if self.get_threshold_value(["tools", "license_check", "enabled"], False):
                license_result = await self._run_license_check(working_directory or os.getcwd())
                if license_result:
                    tool_results["license_check"] = license_result
                    license_issues = license_result.get("issues", [])
                    all_issues.extend(license_issues)
                    
                    # License violations are typically medium severity
                    if license_result.get("violations", 0) > 0:
                        medium_vulnerabilities += license_result.get("violations", 0)
                        total_vulnerabilities += license_result.get("violations", 0)
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Get thresholds
            critical_threshold = self.get_threshold_value(["tools", "dependency_audit", "critical_vulnerabilities"], 0)
            high_threshold = self.get_threshold_value(["tools", "dependency_audit", "high_vulnerabilities"], 0)
            medium_threshold = self.get_threshold_value(["tools", "dependency_audit", "medium_vulnerabilities"], 5)
            low_threshold = self.get_threshold_value(["tools", "dependency_audit", "low_vulnerabilities"], 10)
            
            # Determine gate result
            passed = True
            passed_with_warnings = False
            status = QualityGateStatus.PASSED
            
            # Check critical vulnerabilities
            if critical_vulnerabilities > critical_threshold:
                passed = False
                status = QualityGateStatus.FAILED
            
            # Check high vulnerabilities  
            elif high_vulnerabilities > high_threshold:
                passed = False
                status = QualityGateStatus.FAILED
            
            # Check medium vulnerabilities
            elif medium_vulnerabilities > medium_threshold:
                passed_with_warnings = True
                status = QualityGateStatus.WARNING
            
            # Check low vulnerabilities
            elif low_vulnerabilities > low_threshold:
                passed_with_warnings = True
                status = QualityGateStatus.WARNING
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                total_vulnerabilities, critical_vulnerabilities, high_vulnerabilities,
                medium_vulnerabilities, low_vulnerabilities, all_issues
            )
            
            # Update context with results
            context = self.get_execution_context()
            context.update({
                "total_vulnerabilities": total_vulnerabilities,
                "vulnerability_breakdown": {
                    "critical": critical_vulnerabilities,
                    "high": high_vulnerabilities,
                    "medium": medium_vulnerabilities,
                    "low": low_vulnerabilities
                },
                "tool_results": tool_results,
                "issues": all_issues
            })
            
            result = GateResult(
                gate_type=self.gate_type,
                status=status,
                passed=passed,
                passed_with_warnings=passed_with_warnings,
                execution_time_ms=execution_time_ms,
                details={
                    "total_vulnerabilities": total_vulnerabilities,
                    "vulnerability_breakdown": {
                        "critical": critical_vulnerabilities,
                        "high": high_vulnerabilities,
                        "medium": medium_vulnerabilities,
                        "low": low_vulnerabilities
                    },
                    "thresholds": {
                        "critical": critical_threshold,
                        "high": high_threshold,
                        "medium": medium_threshold,
                        "low": low_threshold
                    },
                    "tool_results": tool_results
                },
                metrics={
                    "total_issues": total_vulnerabilities,
                    "critical_issues": critical_vulnerabilities,
                    "high_issues": high_vulnerabilities,
                    "medium_issues": medium_vulnerabilities,
                    "low_issues": low_vulnerabilities
                },
                recommendations=recommendations,
                total_issues=total_vulnerabilities,
                critical_issues=critical_vulnerabilities,
                high_issues=high_vulnerabilities,
                medium_issues=medium_vulnerabilities,
                low_issues=low_vulnerabilities
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Security gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _run_dependency_audit(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Run dependency vulnerability audit."""
        
        tool_results = []
        
        # NPM audit
        if self.get_threshold_value(["tools", "dependency_audit", "npm_audit"], True):
            npm_result = await self._npm_audit(working_directory)
            if npm_result:
                tool_results.append(npm_result)
        
        # Pip audit
        if self.get_threshold_value(["tools", "dependency_audit", "pip_audit"], True):
            pip_result = await self._pip_audit(working_directory)
            if pip_result:
                tool_results.append(pip_result)
        
        # Composer audit
        if self.get_threshold_value(["tools", "dependency_audit", "composer_audit"], True):
            composer_result = await self._composer_audit(working_directory)
            if composer_result:
                tool_results.append(composer_result)
        
        # Aggregate results
        if not tool_results:
            return None
        
        total_vulnerabilities = sum(r.get("vulnerabilities", 0) for r in tool_results)
        critical_vulnerabilities = sum(r.get("critical", 0) for r in tool_results)
        high_vulnerabilities = sum(r.get("high", 0) for r in tool_results)
        medium_vulnerabilities = sum(r.get("medium", 0) for r in tool_results)
        low_vulnerabilities = sum(r.get("low", 0) for r in tool_results)
        
        all_issues = []
        for tool_result in tool_results:
            all_issues.extend(tool_result.get("issues", []))
        
        return {
            "tool": "dependency_audit",
            "total_vulnerabilities": total_vulnerabilities,
            "critical_vulnerabilities": critical_vulnerabilities,
            "high_vulnerabilities": high_vulnerabilities,
            "medium_vulnerabilities": medium_vulnerabilities,
            "low_vulnerabilities": low_vulnerabilities,
            "tool_results": tool_results,
            "issues": all_issues
        }
    
    async def _npm_audit(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Run npm audit."""
        
        try:
            # Check if package.json exists
            package_json = os.path.join(working_directory, "package.json")
            if not os.path.exists(package_json):
                return None
            
            # Run npm audit
            result = await asyncio.create_subprocess_exec(
                "npm", "audit", "--json",
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return {
                    "tool": "npm",
                    "vulnerabilities": 0,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "issues": [],
                    "message": "No vulnerabilities found"
                }
            
            # Parse npm audit output
            try:
                audit_data = json.loads(stdout.decode())
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract from stderr
                stderr_text = stderr.decode()
                return {
                    "tool": "npm",
                    "vulnerabilities": 1,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 1,
                    "issues": [{"message": stderr_text, "severity": "info"}]
                }
            
            vulnerabilities = audit_data.get("vulnerabilities", {})
            issues = []
            critical = high = medium = low = 0
            
            for pkg, vuln_info in vulnerabilities.items():
                severity = vuln_info.get("severity", "low").lower()
                via = vuln_info.get("via", [])
                
                for vuln in via:
                    issue = {
                        "package": pkg,
                        "title": vuln.get("title", ""),
                        "url": vuln.get("url", ""),
                        "severity": severity,
                        "range": vuln.get("range", "")
                    }
                    issues.append(issue)
                    
                    if severity == "critical":
                        critical += 1
                    elif severity == "high":
                        high += 1
                    elif severity == "moderate":
                        medium += 1
                    else:
                        low += 1
            
            return {
                "tool": "npm",
                "vulnerabilities": len(issues),
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
                "issues": issues,
                "raw_data": audit_data
            }
            
        except Exception as e:
            self.logger.error(f"NPM audit failed: {str(e)}")
            return {
                "tool": "npm",
                "vulnerabilities": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "error": str(e)
            }
    
    async def _pip_audit(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Run pip audit."""
        
        try:
            # Check if requirements.txt or setup.py/pyproject.toml exists
            req_files = ["requirements.txt", "pyproject.toml", "setup.py"]
            has_python_deps = any(os.path.exists(os.path.join(working_directory, f)) for f in req_files)
            
            if not has_python_deps:
                return None
            
            # Run pip audit
            result = await asyncio.create_subprocess_exec(
                "pip", "audit", "--format=json",
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            issues = []
            critical = high = medium = low = 0
            
            if stdout:
                try:
                    audit_data = json.loads(stdout.decode())
                    vulnerabilities = audit_data.get("vulnerabilities", [])
                    
                    for vuln in vulnerabilities:
                        severity = vuln.get("severity", "low").lower()
                        
                        issue = {
                            "package": vuln.get("package", ""),
                            "id": vuln.get("id", ""),
                            "description": vuln.get("description", ""),
                            "severity": severity,
                            "fixed_versions": vuln.get("fixed_versions", [])
                        }
                        issues.append(issue)
                        
                        if severity == "critical":
                            critical += 1
                        elif severity == "high":
                            high += 1
                        elif severity == "medium":
                            medium += 1
                        else:
                            low += 1
                            
                except json.JSONDecodeError:
                    # Fallback parsing
                    stderr_text = stderr.decode()
                    if "vulnerability" in stderr_text.lower():
                        medium += 1
                        issues.append({"message": stderr_text, "severity": "medium"})
            
            return {
                "tool": "pip",
                "vulnerabilities": len(issues),
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
                "issues": issues
            }
            
        except Exception as e:
            self.logger.error(f"PIP audit failed: {str(e)}")
            return {
                "tool": "pip",
                "vulnerabilities": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "error": str(e)
            }
    
    async def _composer_audit(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Run composer audit."""
        
        try:
            # Check if composer.json exists
            composer_json = os.path.join(working_directory, "composer.json")
            if not os.path.exists(composer_json):
                return None
            
            # Run composer audit
            result = await asyncio.create_subprocess_exec(
                "composer", "audit", "--format=json",
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            issues = []
            critical = high = medium = low = 0
            
            if stdout:
                try:
                    audit_data = json.loads(stdout.decode())
                    
                    for package_name, package_data in audit_data.get("packages", {}).items():
                        advisories = package_data.get("advisories", [])
                        
                        for advisory in advisories:
                            severity = advisory.get("severity", "medium").lower()
                            
                            issue = {
                                "package": package_name,
                                "title": advisory.get("title", ""),
                                "severity": severity,
                                "url": advisory.get("link", "")
                            }
                            issues.append(issue)
                            
                            if severity == "critical":
                                critical += 1
                            elif severity == "high":
                                high += 1
                            elif severity == "medium":
                                medium += 1
                            else:
                                low += 1
                                
                except json.JSONDecodeError:
                    # Fallback
                    stderr_text = stderr.decode()
                    if "security" in stderr_text.lower():
                        medium += 1
                        issues.append({"message": stderr_text, "severity": "medium"})
            
            return {
                "tool": "composer",
                "vulnerabilities": len(issues),
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
                "issues": issues
            }
            
        except Exception as e:
            self.logger.error(f"Composer audit failed: {str(e)}")
            return {
                "tool": "composer",
                "vulnerabilities": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "error": str(e)
            }
    
    async def _run_code_security_scan(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Run code security scanning."""
        
        issues = []
        critical_issues = high_issues = medium_issues = low_issues = 0
        
        # Semgrep scan
        if self.get_threshold_value(["tools", "code_scan", "semgrep", "enabled"], False):
            semgrep_result = await self._semgrep_scan(working_directory)
            if semgrep_result:
                issues.extend(semgrep_result.get("issues", []))
                critical_issues += semgrep_result.get("critical_issues", 0)
                high_issues += semgrep_result.get("high_issues", 0)
                medium_issues += semgrep_result.get("medium_issues", 0)
                low_issues += semgrep_result.get("low_issues", 0)
        
        # Basic hardcoded secrets scan
        if self.get_threshold_value(["tools", "code_scan", "hardcoded_secrets"], False):
            secrets_result = await self._hardcoded_secrets_scan(working_directory)
            if secrets_result:
                issues.extend(secrets_result.get("issues", []))
                critical_issues += secrets_result.get("critical_issues", 0)
                high_issues += secrets_result.get("high_issues", 0)
        
        if not issues:
            return None
        
        return {
            "tool": "code_scan",
            "total_issues": len(issues),
            "critical_issues": critical_issues,
            "high_issues": high_issues,
            "medium_issues": medium_issues,
            "low_issues": low_issues,
            "issues": issues
        }
    
    async def _semgrep_scan(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Run Semgrep security scan."""
        
        try:
            # Check if any code files exist
            code_files = await self._find_security_scan_files(working_directory)
            
            if not code_files:
                return {
                    "tool": "semgrep",
                    "total_issues": 0,
                    "critical_issues": 0,
                    "high_issues": 0,
                    "medium_issues": 0,
                    "low_issues": 0,
                    "issues": [],
                    "message": "No code files found for scanning"
                }
            
            # Run semgrep with OWASP rules
            rules = self.get_threshold_value(["tools", "code_scan", "semgrep", "rules"], ["owasp-top-ten"])
            
            cmd_parts = ["semgrep", "--config=auto", "--json", "--no-git-ignore"]
            cmd_parts.extend(code_files)
            
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            issues = []
            critical_issues = high_issues = medium_issues = low_issues = 0
            
            if stdout:
                try:
                    scan_data = json.loads(stdout.decode())
                    results = scan_data.get("results", [])
                    
                    for finding in results:
                        severity = finding.get("severity", "INFO").lower()
                        
                        # Map Semgrep severities to our gate severities
                        if severity == "error":
                            mapped_severity = "high"
                            high_issues += 1
                        elif severity == "warning":
                            mapped_severity = "medium"
                            medium_issues += 1
                        else:
                            mapped_severity = "low"
                            low_issues += 1
                        
                        issue = {
                            "file": finding.get("path", ""),
                            "line": finding.get("start", {}).get("line"),
                            "message": finding.get("message", ""),
                            "rule_id": finding.get("check_id", ""),
                            "severity": mapped_severity
                        }
                        issues.append(issue)
                        
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse Semgrep output: {stderr.decode()}")
            
            return {
                "tool": "semgrep",
                "total_issues": len(issues),
                "critical_issues": 0,  # Semgrep typically doesn't flag critical issues
                "high_issues": high_issues,
                "medium_issues": medium_issues,
                "low_issues": low_issues,
                "issues": issues
            }
            
        except Exception as e:
            self.logger.error(f"Semgrep scan failed: {str(e)}")
            return {
                "tool": "semgrep",
                "total_issues": 0,
                "critical_issues": 0,
                "high_issues": 0,
                "medium_issues": 0,
                "low_issues": 0,
                "error": str(e)
            }
    
    async def _hardcoded_secrets_scan(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Scan for hardcoded secrets in code."""
        
        import glob
        
        issues = []
        critical_issues = high_issues = 0
        
        # Patterns for common secrets
        secret_patterns = [
            r'(?i)(password\s*[:=]\s*["\']([^"\']{6,})["\'])',
            r'(?i)(api[_-]?key\s*[:=]\s*["\']([^"\']{10,})["\'])',
            r'(?i)(secret\s*[:=]\s*["\']([^"\']{8,})["\'])',
            r'(?i)(token\s*[:=]\s*["\']([^"\']{20,})["\'])',
            r'\b(?:sk|pk|sk_live|pk_live)_[a-zA-Z0-9]{16,}\b',  # Stripe keys
            r'\bAKIA[0-9A-Z]{16}\b',  # AWS Access Key ID
        ]
        
        # Scan common file types
        file_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.php", "**/*.java", "**/*.go"]
        
        for pattern in file_patterns:
            files = glob.glob(os.path.join(working_directory, pattern), recursive=True)
            
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        for pattern_idx, regex_pattern in enumerate(secret_patterns):
                            matches = re.finditer(regex_pattern, content, re.MULTILINE)
                            
                            for match in matches:
                                line_num = content[:match.start()].count('\n') + 1
                                
                                # High severity for real secrets, medium for generic matches
                                severity = "high" if "password" in regex_pattern or "token" in regex_pattern else "critical"
                                
                                issue = {
                                    "file": file_path,
                                    "line": line_num,
                                    "message": f"Potential hardcoded secret detected",
                                    "match": match.group(0),
                                    "severity": severity
                                }
                                issues.append(issue)
                                
                                if severity == "critical":
                                    critical_issues += 1
                                else:
                                    high_issues += 1
                                    
                except Exception as e:
                    self.logger.debug(f"Error scanning {file_path}: {e}")
        
        if not issues:
            return {
                "tool": "hardcoded_secrets",
                "total_issues": 0,
                "critical_issues": 0,
                "high_issues": 0,
                "medium_issues": 0,
                "low_issues": 0,
                "issues": []
            }
        
        return {
            "tool": "hardcoded_secrets",
            "total_issues": len(issues),
            "critical_issues": critical_issues,
            "high_issues": high_issues,
            "medium_issues": 0,
            "low_issues": 0,
            "issues": issues
        }
    
    async def _run_license_check(self, working_directory: str) -> Optional[Dict[str, Any]]:
        """Check for license compliance issues."""
        
        try:
            violations = 0
            issues = []
            
            # Check package.json for Node.js licenses
            package_json = os.path.join(working_directory, "package.json")
            if os.path.exists(package_json):
                violations, issues = await self._check_nodejs_licenses(package_json)
            
            # Check requirements.txt for Python licenses  
            requirements_txt = os.path.join(working_directory, "requirements.txt")
            if os.path.exists(requirements_txt):
                python_violations, python_issues = await self._check_python_licenses(requirements_txt)
                violations += python_violations
                issues.extend(python_issues)
            
            if violations == 0:
                return {
                    "tool": "license_check",
                    "violations": 0,
                    "issues": [],
                    "message": "No license violations found"
                }
            
            return {
                "tool": "license_check",
                "violations": violations,
                "issues": issues
            }
            
        except Exception as e:
            self.logger.error(f"License check failed: {str(e)}")
            return {
                "tool": "license_check",
                "violations": 0,
                "error": str(e)
            }
    
    async def _check_nodejs_licenses(self, package_json_path: str) -> Tuple[int, List[Dict[str, Any]]]:
        """Check Node.js package licenses."""
        
        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            allowed_licenses = self.get_threshold_value(["tools", "license_check", "allowed_licenses"], [
                "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"
            ])
            blocked_licenses = self.get_threshold_value(["tools", "license_check", "blocked_licenses"], [
                "GPL-3.0", "AGPL-3.0", "LGPL-3.0"
            ])
            
            violations = 0
            issues = []
            
            # Check dependencies
            dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
            
            for package_name, version in dependencies.items():
                try:
                    # Get package license info
                    result = await asyncio.create_subprocess_exec(
                        "npm", "view", package_name, "license", "--json",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await result.communicate()
                    
                    if stdout:
                        license_info = json.loads(stdout.decode())
                        license_name = license_info.get("license", "")
                        
                        if license_name:
                            # Check against allowed/blocked lists
                            if license_name in blocked_licenses:
                                violations += 1
                                issues.append({
                                    "package": package_name,
                                    "license": license_name,
                                    "severity": "high",
                                    "message": f"Blocked license detected: {license_name}"
                                })
                            elif license_name not in allowed_licenses:
                                issues.append({
                                    "package": package_name,
                                    "license": license_name,
                                    "severity": "medium",
                                    "message": f"Unknown license: {license_name}"
                                })
                                
                except Exception:
                    # If we can't check a package, add a warning
                    issues.append({
                        "package": package_name,
                        "license": "unknown",
                        "severity": "low",
                        "message": "Could not determine package license"
                    })
            
            return violations, issues
            
        except Exception as e:
            self.logger.error(f"Node.js license check failed: {str(e)}")
            return 0, []
    
    async def _check_python_licenses(self, requirements_path: str) -> Tuple[int, List[Dict[str, Any]]]:
        """Check Python package licenses."""
        
        try:
            with open(requirements_path, 'r') as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            violations = 0
            issues = []
            
            allowed_licenses = self.get_threshold_value(["tools", "license_check", "allowed_licenses"], [
                "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"
            ])
            blocked_licenses = self.get_threshold_value(["tools", "license_check", "blocked_licenses"], [
                "GPL-3.0", "AGPL-3.0", "LGPL-3.0"
            ])
            
            for package_line in packages[:10]:  # Limit to first 10 packages for performance
                package_name = package_line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                
                try:
                    # Use pip-license-checker or similar
                    result = await asyncio.create_subprocess_exec(
                        "pip", "show", package_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await result.communicate()
                    
                    if stdout:
                        output = stdout.decode()
                        for line in output.split('\n'):
                            if line.startswith('License:'):
                                license_name = line.split(':', 1)[1].strip()
                                
                                if license_name in blocked_licenses:
                                    violations += 1
                                    issues.append({
                                        "package": package_name,
                                        "license": license_name,
                                        "severity": "high",
                                        "message": f"Blocked license detected: {license_name}"
                                    })
                                elif license_name not in allowed_licenses and license_name != "UNKNOWN":
                                    issues.append({
                                        "package": package_name,
                                        "license": license_name,
                                        "severity": "medium",
                                        "message": f"Unknown license: {license_name}"
                                    })
                                break
                                
                except Exception:
                    # If we can't check a package, skip it
                    continue
            
            return violations, issues
            
        except Exception as e:
            self.logger.error(f"Python license check failed: {str(e)}")
            return 0, []
    
    async def _find_security_scan_files(self, working_directory: str) -> List[str]:
        """Find files suitable for security scanning."""
        import glob
        
        file_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.php", "**/*.java", "**/*.go", "**/*.rb", "**/*.cs"]
        files = []
        
        for pattern in file_patterns:
            matched_files = glob.glob(os.path.join(working_directory, pattern), recursive=True)
            files.extend(matched_files)
        
        # Filter out common excluded directories
        excluded_dirs = {'.git', 'node_modules', '__pycache__', '.venv', '.tox', 'venv', 'build', 'dist'}
        return [f for f in set(files) if not any(excluded_dir in f for excluded_dir in excluded_dirs)]
    
    def _generate_recommendations(
        self,
        total_vulnerabilities: int,
        critical: int,
        high: int,
        medium: int,
        low: int,
        issues: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate security recommendations."""
        
        recommendations = []
        
        if total_vulnerabilities == 0:
            recommendations.append("Excellent! No security vulnerabilities detected.")
            return recommendations
        
        if critical > 0:
            recommendations.append(
                self.create_recommendation(
                    "Critical Security",
                    f"Fix {critical} critical security vulnerabilities immediately",
                    GateSeverity.CRITICAL
                )
            )
        
        if high > 0:
            recommendations.append(
                self.create_recommendation(
                    "High Security",
                    f"Address {high} high-severity security issues",
                    GateSeverity.HIGH
                )
            )
        
        # Dependency security recommendations
        dep_issues = [i for i in issues if i.get("package")]
        if dep_issues:
            recommendations.append("Update vulnerable dependencies to their latest secure versions")
        
        # Code security recommendations  
        code_issues = [i for i in issues if i.get("file") and not i.get("package")]
        if code_issues:
            recommendations.append("Review and fix security issues in your source code")
        
        # License recommendations
        license_issues = [i for i in issues if "license" in i.get("message", "").lower()]
        if license_issues:
            recommendations.append("Review and address any license compliance issues")
        
        # General security practices
        if total_vulnerabilities > 10:
            recommendations.append("Consider implementing automated security scanning in your CI/CD pipeline")
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for security scanning."""
        return ["javascript", "python", "php", "java", "go", "ruby", "csharp"]
    
    def validate_configuration(self) -> List[str]:
        """Validate security gate configuration."""
        errors = super().validate_configuration()
        
        # Check vulnerability thresholds
        tools_config = self.config.threshold_config.get("tools", {})
        
        if "dependency_audit" in tools_config:
            dep_config = tools_config["dependency_audit"]
            for severity in ["critical_vulnerabilities", "high_vulnerabilities", "medium_vulnerabilities", "low_vulnerabilities"]:
                threshold = dep_config.get(severity)
                if threshold is not None and (not isinstance(threshold, int) or threshold < 0):
                    errors.append(f"{severity} must be a non-negative integer")
        
        # Check license configuration
        if "license_check" in tools_config:
            license_config = tools_config["license_check"]
            if license_config.get("enabled", False):
                if not license_config.get("allowed_licenses"):
                    errors.append("allowed_licenses must be provided when license check is enabled")
        
        return errors