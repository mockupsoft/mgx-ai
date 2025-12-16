# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.contract_gate

Quality gate for API endpoint contract testing.
"""

import json
import subprocess
import os
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import logging
import jsonschema
from urllib.parse import urlparse
import aiohttp

from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@register_gate(QualityGateType.CONTRACT)


class ContractGate(BaseQualityGate):
    """Quality gate for API endpoint contract testing."""
    
    def __init__(self, config: GateConfiguration):
        super().__init__(QualityGateType.CONTRACT, config)
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
        openapi_spec: Optional[str] = None,
        **kwargs
    ) -> GateResult:
        """Evaluate contract quality gate."""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Set execution context
            self.set_execution_context({
                "workspace_id": workspace_id,
                "project_id": project_id,
                "working_directory": working_directory or os.getcwd(),
                "application_url": application_url,
                "openapi_spec": openapi_spec
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
            endpoint_results = []
            total_endpoints = 0
            passed_endpoints = 0
            failed_endpoints = 0
            error_endpoints = 0
            
            # Get endpoints configuration
            endpoints_config = self.get_threshold_value("endpoints", [])
            validation_config = self.get_threshold_value("validation", {})
            
            # If no explicit endpoints, try to discover from OpenAPI spec
            if not endpoints_config and openapi_spec:
                endpoints_config = await self._discover_endpoints_from_openapi(openapi_spec)
            
            # If still no endpoints, try to discover from application URL
            if not endpoints_config and application_url:
                endpoints_config = await self._discover_endpoints_from_app(application_url)
            
            # Test each endpoint
            for endpoint_config in endpoints_config:
                total_endpoints += 1
                
                try:
                    endpoint_result = await self._test_endpoint(
                        endpoint_config, application_url, validation_config
                    )
                    endpoint_results.append(endpoint_result)
                    
                    if endpoint_result.get("passed", False):
                        passed_endpoints += 1
                    elif endpoint_result.get("error"):
                        error_endpoints += 1
                    else:
                        failed_endpoints += 1
                        
                except Exception as e:
                    self.logger.error(f"Error testing endpoint {endpoint_config}: {str(e)}")
                    endpoint_results.append({
                        "endpoint": f"{endpoint_config.get('method', 'GET')} {endpoint_config.get('path', '/')}",
                        "passed": False,
                        "error": str(e),
                        "severity": "high"
                    })
                    error_endpoints += 1
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Determine gate result
            passed = failed_endpoints == 0 and error_endpoints == 0
            passed_with_warnings = error_endpoints == 0  # Allow failures but not errors
            status = QualityGateStatus.PASSED
            
            if not passed:
                if error_endpoints > 0:
                    status = QualityGateStatus.FAILED
                else:
                    passed_with_warnings = True
                    status = QualityGateStatus.WARNING
            
            # Generate recommendations
            recommendations = self._generate_recommendations(endpoint_results, passed_endpoints, total_endpoints)
            
            # Update context with results
            context = self.get_execution_context()
            context.update({
                "endpoint_results": endpoint_results,
                "total_endpoints": total_endpoints,
                "passed_endpoints": passed_endpoints,
                "failed_endpoints": failed_endpoints,
                "error_endpoints": error_endpoints
            })
            
            result = GateResult(
                gate_type=self.gate_type,
                status=status,
                passed=passed,
                passed_with_warnings=passed_with_warnings,
                execution_time_ms=execution_time_ms,
                details={
                    "total_endpoints": total_endpoints,
                    "passed_endpoints": passed_endpoints,
                    "failed_endpoints": failed_endpoints,
                    "error_endpoints": error_endpoints,
                    "pass_rate": round((passed_endpoints / total_endpoints) * 100, 2) if total_endpoints > 0 else 0,
                    "endpoint_results": endpoint_results
                },
                metrics={
                    "endpoints_tested": total_endpoints,
                    "endpoints_passed": passed_endpoints,
                    "endpoints_failed": failed_endpoints,
                    "endpoints_with_errors": error_endpoints
                },
                recommendations=recommendations,
                total_issues=failed_endpoints + error_endpoints,
                critical_issues=error_endpoints,
                high_issues=failed_endpoints
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Contract gate evaluation failed: {str(e)}", exc_info=True)
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}",
                execution_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        finally:
            await self.cleanup()
    
    async def _test_endpoint(
        self,
        endpoint_config: Dict[str, Any],
        base_url: Optional[str],
        validation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test a single endpoint."""
        
        path = endpoint_config.get("path", "/")
        method = endpoint_config.get("method", "GET").upper()
        expected_status = endpoint_config.get("expected_status", 200)
        timeout_ms = endpoint_config.get("timeout_ms", 5000)
        headers = endpoint_config.get("headers", {})
        request_body = endpoint_config.get("request_body")
        response_schema = endpoint_config.get("response_schema")
        
        # Construct full URL
        if base_url:
            # Parse base URL and path to construct full URL
            base_parsed = urlparse(base_url)
            if path.startswith("http"):
                full_url = path
            else:
                base_path = base_parsed.path.rstrip("/")
                full_path = f"{base_path}/{path.lstrip('/')}"
                full_url = f"{base_parsed.scheme}://{base_parsed.netloc}{full_path}"
        else:
            full_url = path
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Make HTTP request
            timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                request_kwargs = {
                    "url": full_url,
                    "method": method,
                    "headers": headers
                }
                
                if request_body:
                    request_kwargs["json"] = request_body
                
                async with session.request(**request_kwargs) as response:
                    response_body = await response.text()
                    response_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    
                    # Test status code
                    status_passed = response.status == expected_status
                    
                    # Test response time
                    response_time_passed = response_time_ms <= timeout_ms
                    
                    # Test response schema if provided
                    schema_passed = True
                    schema_errors = []
                    
                    if response_schema:
                        try:
                            if response.headers.get('content-type', '').startswith('application/json'):
                                response_json = json.loads(response_body)
                                jsonschema.validate(response_json, response_schema)
                            else:
                                # For non-JSON responses, just check if response_schema expects string
                                if response_schema.get("type") == "string":
                                    schema_passed = True
                                else:
                                    schema_passed = False
                                    schema_errors.append("Response is not JSON but schema expects structured data")
                        except jsonschema.ValidationError as e:
                            schema_passed = False
                            schema_errors.append(f"Schema validation failed: {str(e)}")
                        except json.JSONDecodeError:
                            if response_schema.get("type") == "string":
                                schema_passed = True
                            else:
                                schema_passed = False
                                schema_errors.append("Response is not valid JSON")
                    
                    # Determine overall result
                    passed = status_passed and response_time_passed and schema_passed
                    
                    # Count issues by severity
                    critical_issues = 0
                    high_issues = 0
                    medium_issues = 0
                    
                    issues = []
                    
                    if not status_passed:
                        critical_issues += 1
                        issues.append({
                            "type": "status_code",
                            "message": f"Expected status {expected_status}, got {response.status}",
                            "severity": "critical",
                            "actual": response.status,
                            "expected": expected_status
                        })
                    
                    if not response_time_passed:
                        high_issues += 1
                        issues.append({
                            "type": "response_time",
                            "message": f"Response time {response_time_ms}ms exceeded timeout {timeout_ms}ms",
                            "severity": "high",
                            "actual": response_time_ms,
                            "expected": timeout_ms
                        })
                    
                    if not schema_passed:
                        medium_issues += 1
                        for error in schema_errors:
                            issues.append({
                                "type": "schema_validation",
                                "message": error,
                                "severity": "medium"
                            })
                    
                    return {
                        "endpoint": f"{method} {path}",
                        "full_url": full_url,
                        "passed": passed,
                        "response_time_ms": response_time_ms,
                        "status_code": response.status,
                        "expected_status": expected_status,
                        "status_passed": status_passed,
                        "response_time_passed": response_time_passed,
                        "schema_passed": schema_passed,
                        "issues": issues,
                        "critical_issues": critical_issues,
                        "high_issues": high_issues,
                        "medium_issues": medium_issues,
                        "response_size": len(response_body),
                        "response_headers": dict(response.headers)
                    }
                    
        except asyncio.TimeoutError:
            return {
                "endpoint": f"{method} {path}",
                "full_url": full_url,
                "passed": False,
                "error": f"Request timed out after {timeout_ms}ms",
                "severity": "high",
                "critical_issues": 1
            }
        except Exception as e:
            return {
                "endpoint": f"{method} {path}",
                "full_url": full_url,
                "passed": False,
                "error": str(e),
                "severity": "critical"
            }
    
    async def _discover_endpoints_from_openapi(self, openapi_spec: str) -> List[Dict[str, Any]]:
        """Discover endpoints from OpenAPI specification."""
        
        try:
            if os.path.exists(openapi_spec):
                with open(openapi_spec, 'r') as f:
                    spec_data = json.load(f)
            else:
                # Assume it's JSON content
                spec_data = json.loads(openapi_spec)
            
            endpoints = []
            paths = spec_data.get("paths", {})
            
            for path, methods in paths.items():
                for method, method_spec in methods.items():
                    if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                        # Extract response schema for success responses
                        responses = method_spec.get("responses", {})
                        response_schema = None
                        expected_status = 200
                        
                        # Look for 200 or 201 response
                        for status_code in ["200", "201", "202"]:
                            if status_code in responses:
                                content = responses[status_code].get("content", {})
                                if "application/json" in content:
                                    schema = content["application/json"].get("schema")
                                    if schema:
                                        response_schema = schema
                                        expected_status = int(status_code)
                                break
                        
                        endpoint_config = {
                            "path": path,
                            "method": method.upper(),
                            "expected_status": expected_status,
                            "timeout_ms": 5000,
                            "response_schema": response_schema
                        }
                        
                        # Add parameters as headers if query params
                        parameters = method_spec.get("parameters", [])
                        headers = {}
                        for param in parameters:
                            if param.get("in") == "header":
                                headers[param.get("name", "")] = param.get("default", "")
                        
                        if headers:
                            endpoint_config["headers"] = headers
                        
                        endpoints.append(endpoint_config)
            
            return endpoints
            
        except Exception as e:
            self.logger.warning(f"Failed to discover endpoints from OpenAPI spec: {e}")
            return []
    
    async def _discover_endpoints_from_app(self, base_url: str) -> List[Dict[str, Any]]:
        """Discover endpoints from application (basic discovery)."""
        
        # Basic endpoint discovery - this is a simplified approach
        # In a real implementation, you might use tools like swagger-ui, 
        # graph introspection, or other discovery methods
        
        common_endpoints = [
            {"path": "/health", "method": "GET", "expected_status": 200, "timeout_ms": 3000},
            {"path": "/status", "method": "GET", "expected_status": 200, "timeout_ms": 3000},
            {"path": "/api/v1/status", "method": "GET", "expected_status": 200, "timeout_ms": 3000},
            {"path": "/api/health", "method": "GET", "expected_status": 200, "timeout_ms": 3000}
        ]
        
        # Test which endpoints exist
        discovered_endpoints = []
        
        async with aiohttp.ClientSession() as session:
            for endpoint in common_endpoints:
                try:
                    if endpoint["path"].startswith("http"):
                        test_url = endpoint["path"]
                    else:
                        base_parsed = urlparse(base_url)
                        base_path = base_parsed.path.rstrip("/")
                        full_path = f"{base_path}/{endpoint['path'].lstrip('/')}"
                        test_url = f"{base_parsed.scheme}://{base_parsed.netloc}{full_path}"
                    
                    async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                        if response.status < 500:  # If not a server error, endpoint exists
                            discovered_endpoints.append(endpoint)
                            
                except Exception:
                    # Endpoint doesn't exist or is unreachable
                    continue
        
        return discovered_endpoints
    
    def _generate_recommendations(
        self,
        endpoint_results: List[Dict[str, Any]],
        passed_endpoints: int,
        total_endpoints: int
    ) -> List[str]:
        """Generate recommendations based on contract test results."""
        
        recommendations = []
        
        if total_endpoints == 0:
            recommendations.append("No endpoints configured for contract testing")
            recommendations.append("Consider defining API endpoints in configuration or OpenAPI specification")
            return recommendations
        
        pass_rate = (passed_endpoints / total_endpoints) * 100 if total_endpoints > 0 else 0
        
        # Overall recommendations
        if pass_rate < 50:
            recommendations.append(
                self.create_recommendation(
                    "API Contract",
                    f"Only {pass_rate:.1f}% of endpoints pass contract tests",
                    GateSeverity.CRITICAL
                )
            )
        elif pass_rate < 80:
            recommendations.append(
                self.create_recommendation(
                    "API Contract",
                    f"{pass_rate:.1f}% of endpoints pass - investigate failing endpoints",
                    GateSeverity.HIGH
                )
            )
        
        # Specific endpoint recommendations
        failed_endpoints = [r for r in endpoint_results if not r.get("passed", False)]
        
        if failed_endpoints:
            recommendations.append("Fix the following failing endpoints:")
            
            for endpoint_result in failed_endpoints[:5]:  # Limit to first 5
                endpoint = endpoint_result.get("endpoint", "Unknown endpoint")
                error = endpoint_result.get("error", "")
                
                if error:
                    recommendations.append(f"  - {endpoint}: {error}")
                else:
                    issues = endpoint_result.get("issues", [])
                    for issue in issues:
                        recommendations.append(f"  - {endpoint}: {issue.get('message', 'Unknown issue')}")
            
            if len(failed_endpoints) > 5:
                recommendations.append(f"  ... and {len(failed_endpoints) - 5} more failing endpoints")
        
        # Performance recommendations
        slow_endpoints = [r for r in endpoint_results if r.get("response_time_ms", 0) > 2000]
        if slow_endpoints:
            recommendations.append("Several endpoints have slow response times (>2s):")
            for endpoint_result in slow_endpoints[:3]:
                endpoint = endpoint_result.get("endpoint", "Unknown endpoint")
                response_time = endpoint_result.get("response_time_ms", 0)
                recommendations.append(f"  - {endpoint}: {response_time}ms")
        
        # Schema recommendations
        schema_failures = [r for r in endpoint_results if not r.get("schema_passed", True)]
        if schema_failures:
            recommendations.append("Some endpoints have schema validation issues:")
            for endpoint_result in schema_failures[:3]:
                endpoint = endpoint_result.get("endpoint", "Unknown endpoint")
                recommendations.append(f"  - {endpoint}: Check response format")
        
        if pass_rate == 100:
            recommendations.append("Excellent! All API endpoints pass contract tests.")
        elif pass_rate >= 80:
            recommendations.append("Good API contract compliance. Review any remaining issues.")
        
        return recommendations
    
    def get_supported_languages(self) -> List[str]:
        """Get supported programming languages for contract testing."""
        return ["javascript", "python", "php", "java", "go", "ruby", "csharp"]
    
    def validate_configuration(self) -> List[str]:
        """Validate contract gate configuration."""
        errors = super().validate_configuration()
        
        # Check endpoints configuration
        endpoints = self.get_threshold_value("endpoints", [])
        if not endpoints:
            errors.append("At least one endpoint must be configured for contract testing")
            return errors
        
        for i, endpoint in enumerate(endpoints):
            if not isinstance(endpoint, dict):
                errors.append(f"Endpoint {i} must be a dictionary")
                continue
            
            path = endpoint.get("path", "")
            method = endpoint.get("method", "GET").upper()
            
            if not path:
                errors.append(f"Endpoint {i} must have a path")
            
            if method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                errors.append(f"Endpoint {i} has invalid method: {method}")
            
            expected_status = endpoint.get("expected_status")
            if expected_status and not isinstance(expected_status, int):
                errors.append(f"Endpoint {i} expected_status must be an integer")
            
            timeout_ms = endpoint.get("timeout_ms")
            if timeout_ms and (not isinstance(timeout_ms, int) or timeout_ms <= 0):
                errors.append(f"Endpoint {i} timeout_ms must be a positive integer")
        
        return errors