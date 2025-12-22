# -*- coding: utf-8 -*-
"""Configuration validation."""

import re
from typing import Any, Dict, List, Optional

from .base import BaseValidator, ValidationResult


class ConfigurationValidator(BaseValidator):
    """Validates configuration files for deployment."""
    
    LOCALHOST_PATTERNS = [
        r'localhost',
        r'127\.0\.0\.1',
        r'0\.0\.0\.0',
    ]
    
    async def validate_configuration(
        self,
        validation_id: str,
        config_files: Dict[str, Any],
        environment: str = "production",
    ) -> ValidationResult:
        """Validate configuration files."""
        result = self._create_result(validation_id, "running")
        
        try:
            # Check required env vars
            await self._check_required_env_vars(result, config_files)
            
            # Check env var values
            await self._check_env_var_values(result, config_files, environment)
            
            # Check service endpoints
            await self._check_service_endpoints(result, config_files)
            
            # Check database connection
            await self._check_database_connection(result, config_files)
            
            # Check Redis connection
            await self._check_redis_connection(result, config_files)
            
            # Check storage configuration
            await self._check_storage_config(result, config_files)
            
            # Check log level
            await self._check_log_level(result, config_files, environment)
            
            # Check timeouts
            await self._check_timeouts(result, config_files)
            
            # Check resource limits
            await self._check_resource_limits(result, config_files)
            
            # Check replica count
            await self._check_replica_count(result, config_files)
            
            result.status = "passed" if result.is_passing() else ("warning" if result.has_warnings() else "failed")
            
        except Exception as e:
            result.error_message = str(e)
            result.status = "failed"
            self.logger.error(f"Configuration validation failed: {e}")
        
        return result
    
    async def _check_required_env_vars(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check if all required environment variables are defined."""
        required_vars = config_files.get("required_env_vars", [])
        env_vars = config_files.get("env_vars", {})
        
        if not required_vars:
            self._add_passed_check(
                result,
                "Required Env Vars Defined",
                "No specific required variables",
            )
            return
        
        missing_vars = []
        for var in required_vars:
            if var not in env_vars:
                missing_vars.append(var)
        
        if missing_vars:
            self._add_failed_check(
                result,
                "Required Env Vars Defined",
                f"Missing environment variables: {', '.join(missing_vars)}",
                description="Define all required environment variables",
                remediation=f"Set: {', '.join(missing_vars)}"
            )
        else:
            self._add_passed_check(
                result,
                "Required Env Vars Defined",
                f"All {len(required_vars)} required environment variables defined",
                details={"count": len(required_vars)}
            )
    
    async def _check_env_var_values(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
        environment: str,
    ) -> None:
        """Check if environment variable values are reasonable."""
        env_vars = config_files.get("env_vars", {})
        
        localhost_vars = []
        empty_vars = []
        
        for key, value in env_vars.items():
            if not value:
                empty_vars.append(key)
                continue
            
            if environment == "production":
                # In production, check for localhost
                value_str = str(value).lower()
                for pattern in self.LOCALHOST_PATTERNS:
                    if re.search(pattern, value_str):
                        localhost_vars.append(f"{key}={value}")
                        break
        
        if localhost_vars and environment == "production":
            self._add_failed_check(
                result,
                "Env Var Values Valid",
                f"Localhost addresses detected in production config: {', '.join(localhost_vars[:3])}",
                description="Use production service endpoints",
                remediation="Replace localhost with production service endpoints"
            )
        elif empty_vars:
            self._add_warning_check(
                result,
                "Env Var Values Valid",
                f"Empty environment variables: {', '.join(empty_vars)}",
                description="Verify empty variables are intentional"
            )
        else:
            self._add_passed_check(
                result,
                "Env Var Values Valid",
                f"All {len(env_vars)} environment variable values are valid",
                details={"count": len(env_vars)}
            )
    
    async def _check_service_endpoints(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check if service endpoints are properly configured."""
        services = config_files.get("services", {})
        
        if not services:
            self._add_passed_check(
                result,
                "Service Endpoints",
                "No external services configured",
            )
            return
        
        invalid_endpoints = []
        for service_name, endpoint in services.items():
            if not self._is_valid_endpoint(endpoint):
                invalid_endpoints.append(f"{service_name}: {endpoint}")
        
        if invalid_endpoints:
            self._add_warning_check(
                result,
                "Service Endpoints",
                f"Invalid service endpoints: {', '.join(invalid_endpoints[:3])}",
                description="Verify service endpoints are correct"
            )
        else:
            self._add_passed_check(
                result,
                "Service Endpoints",
                f"{len(services)} service endpoints configured",
                details={"service_count": len(services)}
            )
    
    def _is_valid_endpoint(self, endpoint: Any) -> bool:
        """Check if endpoint is valid."""
        if isinstance(endpoint, str):
            return endpoint.startswith("http") or endpoint.startswith("$")
        elif isinstance(endpoint, dict):
            host = endpoint.get("host")
            port = endpoint.get("port")
            return bool(host and port)
        return False
    
    async def _check_database_connection(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check database connection configuration."""
        db_config = config_files.get("database", {})
        
        if not db_config:
            self._add_warning_check(
                result,
                "Database Configuration",
                "No database configuration found",
                description="Configure database connection"
            )
            return
        
        required_db_fields = ["host", "port", "database"]
        missing_fields = [f for f in required_db_fields if not db_config.get(f)]
        
        if missing_fields:
            self._add_failed_check(
                result,
                "Database Configuration",
                f"Missing database fields: {', '.join(missing_fields)}",
                remediation=f"Configure: {', '.join(missing_fields)}"
            )
        else:
            db_type = db_config.get("type", "unknown")
            host = db_config.get("host")
            self._add_passed_check(
                result,
                "Database Configuration",
                f"Database {db_type} configured at {host}",
                details={"type": db_type, "host": host}
            )
    
    async def _check_redis_connection(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check Redis cache configuration."""
        redis_config = config_files.get("redis", {})
        
        if not redis_config:
            self._add_passed_check(
                result,
                "Redis Configuration",
                "Redis not configured (optional)",
            )
            return
        
        host = redis_config.get("host")
        port = redis_config.get("port")
        
        if not host or not port:
            self._add_warning_check(
                result,
                "Redis Configuration",
                "Incomplete Redis configuration",
                description="Configure Redis connection"
            )
        else:
            self._add_passed_check(
                result,
                "Redis Configuration",
                f"Redis configured at {host}:{port}",
                details={"host": host, "port": port}
            )
    
    async def _check_storage_config(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check storage configuration."""
        storage = config_files.get("storage", {})
        
        if not storage:
            self._add_passed_check(
                result,
                "Storage Configuration",
                "Storage not configured (optional)",
            )
            return
        
        storage_type = storage.get("type", "unknown")
        required_fields = ["bucket", "region"] if storage_type == "s3" else ["path"]
        missing_fields = [f for f in required_fields if not storage.get(f)]
        
        if missing_fields:
            self._add_warning_check(
                result,
                "Storage Configuration",
                f"Incomplete storage configuration",
                description="Configure storage properly"
            )
        else:
            self._add_passed_check(
                result,
                "Storage Configuration",
                f"Storage {storage_type} configured",
                details={"type": storage_type}
            )
    
    async def _check_log_level(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
        environment: str,
    ) -> None:
        """Check log level is appropriate."""
        log_level = config_files.get("log_level", "INFO")
        
        appropriate_levels = {
            "production": ["WARNING", "ERROR", "CRITICAL"],
            "staging": ["INFO", "WARNING", "ERROR"],
            "development": ["DEBUG", "INFO", "WARNING"],
        }
        
        allowed = appropriate_levels.get(environment, ["INFO"])
        
        if log_level not in allowed:
            self._add_warning_check(
                result,
                "Log Level",
                f"Log level {log_level} may not be appropriate for {environment}",
                description="Use appropriate log level for environment",
                remediation=f"Set to one of: {', '.join(allowed)}"
            )
        else:
            self._add_passed_check(
                result,
                "Log Level",
                f"Log level {log_level} is appropriate for {environment}",
                details={"log_level": log_level, "environment": environment}
            )
    
    async def _check_timeouts(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check if timeout values are reasonable."""
        timeouts = config_files.get("timeouts", {})
        
        if not timeouts:
            self._add_passed_check(
                result,
                "Timeout Configuration",
                "No timeout configuration (using defaults)",
            )
            return
        
        reasonable = True
        for timeout_name, timeout_value in timeouts.items():
            if isinstance(timeout_value, (int, float)):
                if timeout_value <= 0 or timeout_value > 3600:
                    reasonable = False
                    break
        
        if reasonable:
            self._add_passed_check(
                result,
                "Timeout Configuration",
                f"{len(timeouts)} timeout values are reasonable",
                details={"timeout_count": len(timeouts)}
            )
        else:
            self._add_warning_check(
                result,
                "Timeout Configuration",
                "Some timeout values are unreasonable",
                description="Review timeout configuration"
            )
    
    async def _check_resource_limits(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check resource limits are configured."""
        resources = config_files.get("resources", {})
        
        if not resources:
            self._add_warning_check(
                result,
                "Resource Limits",
                "No resource limits configured",
                description="Configure resource limits"
            )
            return
        
        self._add_passed_check(
            result,
            "Resource Limits",
            "Resource limits configured",
            details={"limits": len(resources)}
        )
    
    async def _check_replica_count(
        self,
        result: ValidationResult,
        config_files: Dict[str, Any],
    ) -> None:
        """Check replica count is sensible."""
        replicas = config_files.get("replicas", 1)
        
        if replicas < 1:
            self._add_failed_check(
                result,
                "Replica Count",
                f"Replica count {replicas} is invalid",
                remediation="Set replicas to at least 1"
            )
        elif replicas == 1:
            self._add_warning_check(
                result,
                "Replica Count",
                "Only 1 replica configured - no high availability",
                description="Consider multiple replicas for production"
            )
        else:
            self._add_passed_check(
                result,
                "Replica Count",
                f"Replica count {replicas} provides high availability",
                details={"replicas": replicas}
            )
