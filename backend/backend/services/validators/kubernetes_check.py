# -*- coding: utf-8 -*-
"""Kubernetes manifest validation."""

import re
from typing import Any, Dict, List, Optional

import yaml

from .base import BaseValidator, ValidationResult


class KubernetesValidator(BaseValidator):
    """Validates Kubernetes manifests for deployment readiness."""
    
    async def validate_manifests(
        self,
        validation_id: str,
        manifests: List[str],
    ) -> ValidationResult:
        """Validate Kubernetes manifests."""
        result = self._create_result(validation_id, "running")
        
        try:
            # Parse manifests
            parsed_manifests = self._parse_manifests(manifests)
            
            for i, manifest in enumerate(parsed_manifests):
                await self._validate_single_manifest(result, manifest, i)
            
            result.status = "passed" if result.is_passing() else ("warning" if result.has_warnings() else "failed")
            
        except Exception as e:
            result.error_message = str(e)
            result.status = "failed"
            self.logger.error(f"Kubernetes validation failed: {e}")
        
        return result
    
    def _parse_manifests(self, manifests: List[str]) -> List[Dict[str, Any]]:
        """Parse YAML manifests."""
        parsed = []
        
        for manifest_content in manifests:
            try:
                docs = list(yaml.safe_load_all(manifest_content))
                parsed.extend([doc for doc in docs if doc])
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML: {e}")
        
        return parsed
    
    async def _validate_single_manifest(
        self,
        result: ValidationResult,
        manifest: Dict[str, Any],
        index: int,
    ) -> None:
        """Validate a single manifest."""
        if not manifest:
            return
        
        kind = manifest.get("kind", "Unknown")
        name = manifest.get("metadata", {}).get("name", f"resource-{index}")
        
        # YAML syntax valid (already validated during parsing)
        self._add_passed_check(
            result,
            f"YAML Syntax Valid ({kind})",
            f"Manifest {name} is valid YAML",
            details={"kind": kind, "name": name}
        )
        
        # Validate spec if present
        if "spec" in manifest:
            await self._validate_spec(result, manifest, name)
    
    async def _validate_spec(
        self,
        result: ValidationResult,
        manifest: Dict[str, Any],
        name: str,
    ) -> None:
        """Validate spec section."""
        spec = manifest.get("spec", {})
        kind = manifest.get("kind", "")
        
        if kind == "Deployment" or kind == "Pod":
            await self._validate_pod_spec(result, manifest, spec, name)
        elif kind == "Service":
            await self._validate_service(result, manifest, spec, name)
        elif kind == "Ingress":
            await self._validate_ingress(result, manifest, spec, name)
    
    async def _validate_pod_spec(
        self,
        result: ValidationResult,
        manifest: Dict[str, Any],
        spec: Dict[str, Any],
        name: str,
    ) -> None:
        """Validate pod specification."""
        template = spec.get("template", {})
        pod_spec = template.get("spec", spec)
        containers = pod_spec.get("containers", [])
        
        if not containers:
            self._add_failed_check(
                result,
                f"Containers Defined ({name})",
                "No containers defined in pod spec",
                remediation="Add containers section to pod spec"
            )
            return
        
        for i, container in enumerate(containers):
            container_name = container.get("name", f"container-{i}")
            
            # Check resources
            self._validate_container_resources(result, container, name, container_name)
            
            # Check probes
            self._validate_probes(result, container, name, container_name)
            
            # Check security context
            self._validate_security_context(result, container, name, container_name)
            
            # Check image pull policy
            self._validate_image_pull_policy(result, container, name, container_name)
    
    def _validate_container_resources(
        self,
        result: ValidationResult,
        container: Dict[str, Any],
        pod_name: str,
        container_name: str,
    ) -> None:
        """Validate container resources."""
        resources = container.get("resources", {})
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})
        
        label = f"Resources ({pod_name}/{container_name})"
        
        if not requests:
            self._add_failed_check(
                result,
                f"Resource Requests ({pod_name}/{container_name})",
                "No resource requests defined",
                description="Define CPU and memory requests",
                remediation="Add resources.requests for cpu and memory"
            )
        else:
            self._add_passed_check(
                result,
                f"Resource Requests ({pod_name}/{container_name})",
                f"Requests: {requests}",
                details=requests
            )
        
        if not limits:
            self._add_warning_check(
                result,
                f"Resource Limits ({pod_name}/{container_name})",
                "No resource limits defined",
                description="Define CPU and memory limits",
            )
        else:
            self._add_passed_check(
                result,
                f"Resource Limits ({pod_name}/{container_name})",
                f"Limits: {limits}",
                details=limits
            )
    
    def _validate_probes(
        self,
        result: ValidationResult,
        container: Dict[str, Any],
        pod_name: str,
        container_name: str,
    ) -> None:
        """Validate liveness and readiness probes."""
        liveness_probe = container.get("livenessProbe")
        readiness_probe = container.get("readinessProbe")
        
        if not liveness_probe:
            self._add_warning_check(
                result,
                f"Liveness Probe ({pod_name}/{container_name})",
                "No liveness probe defined",
                description="Define liveness probe for automatic restart",
            )
        else:
            self._add_passed_check(
                result,
                f"Liveness Probe ({pod_name}/{container_name})",
                "Liveness probe is defined",
                details=liveness_probe
            )
        
        if not readiness_probe:
            self._add_warning_check(
                result,
                f"Readiness Probe ({pod_name}/{container_name})",
                "No readiness probe defined",
                description="Define readiness probe for load balancer",
            )
        else:
            self._add_passed_check(
                result,
                f"Readiness Probe ({pod_name}/{container_name})",
                "Readiness probe is defined",
                details=readiness_probe
            )
    
    def _validate_security_context(
        self,
        result: ValidationResult,
        container: Dict[str, Any],
        pod_name: str,
        container_name: str,
    ) -> None:
        """Validate security context."""
        security_context = container.get("securityContext", {})
        
        if not security_context:
            self._add_warning_check(
                result,
                f"Security Context ({pod_name}/{container_name})",
                "No security context defined",
                description="Define security context for container",
            )
        else:
            self._add_passed_check(
                result,
                f"Security Context ({pod_name}/{container_name})",
                "Security context is defined",
                details=security_context
            )
    
    def _validate_image_pull_policy(
        self,
        result: ValidationResult,
        container: Dict[str, Any],
        pod_name: str,
        container_name: str,
    ) -> None:
        """Validate image pull policy."""
        pull_policy = container.get("imagePullPolicy", "IfNotPresent")
        
        if pull_policy == "Always" or pull_policy == "IfNotPresent":
            self._add_passed_check(
                result,
                f"Image Pull Policy ({pod_name}/{container_name})",
                f"Image pull policy set to {pull_policy}",
                details={"imagePullPolicy": pull_policy}
            )
        else:
            self._add_warning_check(
                result,
                f"Image Pull Policy ({pod_name}/{container_name})",
                f"Uncommon image pull policy: {pull_policy}",
            )
    
    async def _validate_service(
        self,
        result: ValidationResult,
        manifest: Dict[str, Any],
        spec: Dict[str, Any],
        name: str,
    ) -> None:
        """Validate Service manifest."""
        selector = spec.get("selector")
        
        if not selector:
            self._add_warning_check(
                result,
                f"Service Selector ({name})",
                "No selector defined in service",
                description="Define selector to match pods",
            )
        else:
            self._add_passed_check(
                result,
                f"Service Selector ({name})",
                "Service selector is defined",
                details={"selector": selector}
            )
    
    async def _validate_ingress(
        self,
        result: ValidationResult,
        manifest: Dict[str, Any],
        spec: Dict[str, Any],
        name: str,
    ) -> None:
        """Validate Ingress manifest."""
        rules = spec.get("rules", [])
        
        if not rules:
            self._add_warning_check(
                result,
                f"Ingress Rules ({name})",
                "No ingress rules defined",
                description="Define ingress rules for routing",
            )
        else:
            self._add_passed_check(
                result,
                f"Ingress Rules ({name})",
                f"Ingress has {len(rules)} rules",
                details={"rule_count": len(rules)}
            )
