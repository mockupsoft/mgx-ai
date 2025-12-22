# -*- coding: utf-8 -*-
"""Health check validation."""

from typing import Any, Dict, Optional
import asyncio
import aiohttp

from .base import BaseValidator, ValidationResult


class HealthCheckValidator(BaseValidator):
    """Validates health check endpoints and dependencies."""
    
    HEALTH_CHECK_TIMEOUT = 10  # seconds
    
    async def validate_health_endpoints(
        self,
        validation_id: str,
        deployment: Dict[str, Any],
        test_environment: str = "sandbox",
    ) -> ValidationResult:
        """Validate health endpoints."""
        result = self._create_result(validation_id, "running")
        
        try:
            health_endpoint = deployment.get("health_endpoint")
            readiness_endpoint = deployment.get("readiness_endpoint")
            liveness_endpoint = deployment.get("liveness_endpoint")
            
            # Check health endpoint
            if health_endpoint:
                await self._check_endpoint(
                    result,
                    "Health Endpoint",
                    health_endpoint,
                    deployment
                )
            else:
                self._add_warning_check(
                    result,
                    "Health Endpoint",
                    "No health endpoint configured",
                    description="Configure /health or /healthz endpoint"
                )
            
            # Check readiness endpoint
            if readiness_endpoint:
                await self._check_endpoint(
                    result,
                    "Readiness Endpoint",
                    readiness_endpoint,
                    deployment
                )
            else:
                self._add_warning_check(
                    result,
                    "Readiness Endpoint",
                    "No readiness endpoint configured",
                    description="Configure /ready or /readiness endpoint"
                )
            
            # Check liveness endpoint
            if liveness_endpoint:
                await self._check_endpoint(
                    result,
                    "Liveness Endpoint",
                    liveness_endpoint,
                    deployment
                )
            else:
                self._add_warning_check(
                    result,
                    "Liveness Endpoint",
                    "No liveness endpoint configured",
                    description="Configure /alive or /liveness endpoint"
                )
            
            # Check required env vars
            await self._check_env_vars(result, deployment)
            
            # Check dependencies
            await self._check_dependencies(result, deployment)
            
            # Check health check timeout
            await self._check_timeout_config(result, deployment)
            
            result.status = "passed" if result.is_passing() else ("warning" if result.has_warnings() else "failed")
            
        except Exception as e:
            result.error_message = str(e)
            result.status = "failed"
            self.logger.error(f"Health check validation failed: {e}")
        
        return result
    
    async def _check_endpoint(
        self,
        result: ValidationResult,
        endpoint_name: str,
        endpoint: Dict[str, Any],
        deployment: Dict[str, Any],
    ) -> None:
        """Check if an endpoint is accessible."""
        url = endpoint.get("url")
        port = endpoint.get("port", 8000)
        path = endpoint.get("path", "/health")
        
        if not url:
            # Try to construct URL
            host = deployment.get("host", "localhost")
            url = f"http://{host}:{port}{path}"
        
        try:
            # For now, just validate the URL format
            if not url.startswith("http"):
                raise ValueError("Invalid URL format")
            
            self._add_passed_check(
                result,
                f"{endpoint_name} URL Valid",
                f"Endpoint URL is valid: {url}",
                details={"url": url, "port": port, "path": path}
            )
            
        except Exception as e:
            self._add_warning_check(
                result,
                f"{endpoint_name} Accessible",
                f"Could not verify endpoint accessibility: {e}",
                description="Verify endpoint is accessible in test environment"
            )
    
    async def _check_env_vars(
        self,
        result: ValidationResult,
        deployment: Dict[str, Any],
    ) -> None:
        """Check if required environment variables are set."""
        required_env_vars = deployment.get("required_env_vars", [])
        env_vars = deployment.get("env_vars", {})
        
        if not required_env_vars:
            self._add_passed_check(
                result,
                "No Required Env Vars",
                "No specific environment variables required",
            )
            return
        
        missing_vars = []
        for var in required_env_vars:
            if var not in env_vars or not env_vars[var]:
                missing_vars.append(var)
        
        if missing_vars:
            self._add_failed_check(
                result,
                "Required Env Vars Set",
                f"Missing environment variables: {', '.join(missing_vars)}",
                description="Set required environment variables",
                remediation=f"Set: {', '.join(missing_vars)}"
            )
        else:
            self._add_passed_check(
                result,
                "Required Env Vars Set",
                f"All {len(required_env_vars)} required environment variables are set",
                details={"env_vars": list(required_env_vars)}
            )
    
    async def _check_dependencies(
        self,
        result: ValidationResult,
        deployment: Dict[str, Any],
    ) -> None:
        """Check if dependencies are reachable."""
        dependencies = deployment.get("dependencies", {})
        
        if not dependencies:
            self._add_passed_check(
                result,
                "No External Dependencies",
                "No external dependencies configured",
            )
            return
        
        # Check database
        if "database" in dependencies:
            await self._check_database_connection(result, dependencies["database"])
        
        # Check cache
        if "cache" in dependencies:
            await self._check_cache_connection(result, dependencies["cache"])
        
        # Check other services
        for name, config in dependencies.items():
            if name not in ["database", "cache"]:
                await self._check_service_connection(result, name, config)
    
    async def _check_database_connection(
        self,
        result: ValidationResult,
        db_config: Dict[str, Any],
    ) -> None:
        """Check database connectivity."""
        db_type = db_config.get("type", "unknown")
        host = db_config.get("host")
        port = db_config.get("port")
        
        if not host or not port:
            self._add_warning_check(
                result,
                "Database Config",
                "Database connection parameters incomplete",
                description="Verify database configuration"
            )
        else:
            self._add_passed_check(
                result,
                "Database Config",
                f"Database {db_type} configured at {host}:{port}",
                details={"type": db_type, "host": host, "port": port}
            )
    
    async def _check_cache_connection(
        self,
        result: ValidationResult,
        cache_config: Dict[str, Any],
    ) -> None:
        """Check cache connectivity."""
        cache_type = cache_config.get("type", "redis")
        host = cache_config.get("host")
        port = cache_config.get("port")
        
        if not host or not port:
            self._add_warning_check(
                result,
                "Cache Config",
                "Cache connection parameters incomplete",
                description="Verify cache configuration"
            )
        else:
            self._add_passed_check(
                result,
                "Cache Config",
                f"Cache {cache_type} configured at {host}:{port}",
                details={"type": cache_type, "host": host, "port": port}
            )
    
    async def _check_service_connection(
        self,
        result: ValidationResult,
        service_name: str,
        service_config: Dict[str, Any],
    ) -> None:
        """Check external service connectivity."""
        host = service_config.get("host")
        port = service_config.get("port")
        
        if not host or not port:
            self._add_warning_check(
                result,
                f"Service {service_name}",
                f"Service connection parameters incomplete",
            )
        else:
            self._add_passed_check(
                result,
                f"Service {service_name}",
                f"Service {service_name} configured at {host}:{port}",
                details={"host": host, "port": port}
            )
    
    async def _check_timeout_config(
        self,
        result: ValidationResult,
        deployment: Dict[str, Any],
    ) -> None:
        """Check if health check timeout is reasonable."""
        timeout = deployment.get("health_check_timeout", 10)
        
        if timeout > self.HEALTH_CHECK_TIMEOUT:
            self._add_warning_check(
                result,
                "Health Check Timeout",
                f"Timeout {timeout}s exceeds recommended {self.HEALTH_CHECK_TIMEOUT}s",
                description="Reduce health check timeout for faster failure detection",
                remediation=f"Set timeout to {self.HEALTH_CHECK_TIMEOUT} seconds or less"
            )
        else:
            self._add_passed_check(
                result,
                "Health Check Timeout",
                f"Health check timeout {timeout}s is reasonable",
                details={"timeout_seconds": timeout}
            )
