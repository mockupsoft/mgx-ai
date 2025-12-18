# -*- coding: utf-8 -*-
"""Security validation."""

import re
from typing import Any, Dict, List, Optional

from .base import BaseValidator, ValidationResult


class SecurityValidator(BaseValidator):
    """Validates security aspects of deployment artifacts."""
    
    DANGEROUS_PATTERNS = [
        r'password\s*[=:]\s*[\'"]?[\w]+',
        r'secret\s*[=:]\s*[\'"]?[\w]+',
        r'api[_-]?key\s*[=:]\s*[\'"]?[\w]+',
        r'aws[_-]?secret\s*[=:]\s*[\'"]?[\w]+',
        r'private[_-]?key\s*[=:]\s*[\'"]?[\w]+',
        r'token\s*[=:]\s*[\'"]?[\w]{20,}',
        r'authorization\s*[=:]\s*[\'"]?Bearer\s+[\w-]+',
    ]
    
    DANGEROUS_HEADERS = [
        "X-Powered-By",
        "Server",
    ]
    
    INSECURE_PROTOCOLS = [
        "http://",
        "ftp://",
        "telnet://",
    ]
    
    async def validate_security(
        self,
        validation_id: str,
        artifacts: Dict[str, Any],
    ) -> ValidationResult:
        """Validate security of artifacts."""
        result = self._create_result(validation_id, "running")
        
        try:
            # Check for hardcoded secrets
            await self._check_hardcoded_secrets(result, artifacts)
            
            # Check for default credentials
            await self._check_default_credentials(result, artifacts)
            
            # Check dependencies audit
            await self._check_dependency_audit(result, artifacts)
            
            # Check license compliance
            await self._check_license_compliance(result, artifacts)
            
            # Check security headers
            await self._check_security_headers(result, artifacts)
            
            # Check TLS/HTTPS
            await self._check_tls_enforcement(result, artifacts)
            
            # Check CORS configuration
            await self._check_cors_config(result, artifacts)
            
            # Check OWASP top 10
            await self._check_owasp_compliance(result, artifacts)
            
            result.status = "passed" if result.is_passing() else ("warning" if result.has_warnings() else "failed")
            
        except Exception as e:
            result.error_message = str(e)
            result.status = "failed"
            self.logger.error(f"Security validation failed: {e}")
        
        return result
    
    async def _check_hardcoded_secrets(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check for hardcoded secrets in code and configs."""
        found_secrets = []
        
        # Check application code
        app_code = artifacts.get("application_code", "")
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, app_code, re.IGNORECASE | re.MULTILINE):
                found_secrets.append("application code")
                break
        
        # Check configuration files
        config = artifacts.get("configuration", {})
        config_str = str(config)
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, config_str, re.IGNORECASE):
                found_secrets.append("configuration")
                break
        
        # Check environment variables
        env_vars = artifacts.get("env_vars", {})
        for key, value in env_vars.items():
            if any(secret in key.lower() for secret in ["password", "secret", "key", "token"]):
                if value and not value.startswith("${"):
                    found_secrets.append(f"env var: {key}")
        
        if found_secrets:
            self._add_failed_check(
                result,
                "Hardcoded Secrets",
                f"Potential hardcoded secrets detected in: {', '.join(set(found_secrets))}",
                description="Ensure no secrets are hardcoded in source",
                remediation="Use environment variables or secret management for all sensitive data"
            )
        else:
            self._add_passed_check(
                result,
                "Hardcoded Secrets",
                "No hardcoded secrets detected",
            )
    
    async def _check_default_credentials(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check for default credentials."""
        default_creds = ["admin/admin", "root/root", "user/password"]
        found_defaults = []
        
        config_str = str(artifacts.get("configuration", {}))
        env_vars = artifacts.get("env_vars", {})
        
        for cred in default_creds:
            if cred in config_str:
                found_defaults.append(cred)
        
        if found_defaults:
            self._add_failed_check(
                result,
                "Default Credentials",
                f"Default credentials detected: {', '.join(found_defaults)}",
                description="Remove all default credentials",
                remediation="Replace with strong, unique credentials"
            )
        else:
            self._add_passed_check(
                result,
                "Default Credentials",
                "No default credentials detected",
            )
    
    async def _check_dependency_audit(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check if dependencies have been audited."""
        npm_packages = artifacts.get("npm_packages", [])
        pip_packages = artifacts.get("pip_packages", [])
        
        has_vulnerabilities = artifacts.get("has_vulnerabilities", False)
        
        if has_vulnerabilities:
            self._add_failed_check(
                result,
                "Dependency Audit",
                "Known vulnerabilities detected in dependencies",
                description="Update vulnerable dependencies",
                remediation="Run 'npm audit' or 'pip audit' and fix vulnerabilities"
            )
        else:
            if npm_packages:
                self._add_passed_check(
                    result,
                    "NPM Dependency Audit",
                    f"{len(npm_packages)} npm packages are secure",
                    details={"package_count": len(npm_packages)}
                )
            
            if pip_packages:
                self._add_passed_check(
                    result,
                    "Python Dependency Audit",
                    f"{len(pip_packages)} python packages are secure",
                    details={"package_count": len(pip_packages)}
                )
    
    async def _check_license_compliance(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check license compliance of dependencies."""
        licenses = artifacts.get("licenses", {})
        dangerous_licenses = ["GPL", "AGPL"]
        found_dangerous = []
        
        for pkg, license_type in licenses.items():
            if any(lic in license_type for lic in dangerous_licenses):
                found_dangerous.append(f"{pkg} ({license_type})")
        
        if found_dangerous:
            self._add_warning_check(
                result,
                "License Compliance",
                f"Restrictive licenses detected: {', '.join(found_dangerous)}",
                description="Review license compatibility with project"
            )
        else:
            self._add_passed_check(
                result,
                "License Compliance",
                "All licenses are compatible",
                details={"license_count": len(licenses)}
            )
    
    async def _check_security_headers(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check for security headers configuration."""
        security_headers = artifacts.get("security_headers", {})
        
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
        ]
        
        missing_headers = [h for h in required_headers if h not in security_headers]
        
        if missing_headers:
            self._add_warning_check(
                result,
                "Security Headers",
                f"Missing security headers: {', '.join(missing_headers)}",
                description="Configure security headers for HTTP responses",
            )
        else:
            self._add_passed_check(
                result,
                "Security Headers",
                "All required security headers configured",
                details={"headers": required_headers}
            )
    
    async def _check_tls_enforcement(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check if TLS/HTTPS is enforced."""
        config = artifacts.get("configuration", {})
        config_str = str(config).lower()
        
        # Check for insecure protocols
        found_insecure = []
        for protocol in self.INSECURE_PROTOCOLS:
            if protocol in config_str:
                found_insecure.append(protocol)
        
        if found_insecure:
            self._add_failed_check(
                result,
                "TLS/HTTPS Enforcement",
                f"Insecure protocols detected: {', '.join(found_insecure)}",
                description="Enforce TLS/HTTPS for all communications",
                remediation="Remove insecure protocol configurations"
            )
        else:
            self._add_passed_check(
                result,
                "TLS/HTTPS Enforcement",
                "HTTPS/TLS is enforced",
            )
    
    async def _check_cors_config(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check CORS configuration."""
        cors_config = artifacts.get("cors_config", {})
        
        if not cors_config:
            self._add_warning_check(
                result,
                "CORS Configuration",
                "CORS configuration not found",
                description="Configure CORS appropriately",
            )
        else:
            allowed_origins = cors_config.get("allowed_origins", [])
            
            if allowed_origins == ["*"]:
                self._add_warning_check(
                    result,
                    "CORS Configuration",
                    "CORS allows all origins (*)",
                    description="Restrict CORS to specific origins",
                    remediation="Replace * with specific allowed origins"
                )
            else:
                self._add_passed_check(
                    result,
                    "CORS Configuration",
                    f"CORS configured for {len(allowed_origins)} origins",
                    details={"origin_count": len(allowed_origins)}
                )
    
    async def _check_owasp_compliance(
        self,
        result: ValidationResult,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check OWASP Top 10 compliance."""
        owasp_checks = {
            "injection": artifacts.get("owasp_injection_check", True),
            "broken_auth": artifacts.get("owasp_broken_auth_check", True),
            "sensitive_data": artifacts.get("owasp_sensitive_data_check", True),
            "xml_external": artifacts.get("owasp_xml_external_check", True),
            "access_control": artifacts.get("owasp_access_control_check", True),
        }
        
        all_passed = all(owasp_checks.values())
        
        if all_passed:
            self._add_passed_check(
                result,
                "OWASP Top 10 Compliance",
                "OWASP Top 10 checks passed",
                details={"checks_passed": len(owasp_checks)}
            )
        else:
            failed = [k for k, v in owasp_checks.items() if not v]
            self._add_warning_check(
                result,
                "OWASP Top 10 Compliance",
                f"Some OWASP checks need review: {', '.join(failed)}",
                description="Address OWASP Top 10 vulnerabilities",
            )
