# -*- coding: utf-8 -*-
"""Deployment validator orchestrator."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import ValidationResult
from .docker_check import DockerValidator
from .kubernetes_check import KubernetesValidator
from .health_check import HealthCheckValidator
from .security_check import SecurityValidator
from .configuration_check import ConfigurationValidator
from .checklist import PreDeploymentChecklist
from .simulator import DeploymentSimulator
from .rollback import RollbackValidator


logger = logging.getLogger(__name__)


class DeploymentValidator:
    """Main deployment validator orchestrator."""
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.docker_validator = DockerValidator(workspace_id)
        self.k8s_validator = KubernetesValidator(workspace_id)
        self.health_validator = HealthCheckValidator(workspace_id)
        self.security_validator = SecurityValidator(workspace_id)
        self.config_validator = ConfigurationValidator(workspace_id)
        self.simulator = DeploymentSimulator(workspace_id)
        self.rollback_validator = RollbackValidator(workspace_id)
        self.logger = logging.getLogger(__name__)
    
    async def validate_artifacts(
        self,
        validation_id: str,
        build_id: str,
        artifacts: Dict[str, Any],
        environment: str = "staging",
    ) -> Dict[str, Any]:
        """Validate all artifacts for deployment."""
        validation_result = {
            "validation_id": validation_id,
            "build_id": build_id,
            "environment": environment,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "phases": {},
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 0,
                "warning_checks": 0,
            },
            "is_deployable": False,
        }
        
        try:
            # Phase 1: Docker Validation
            self.logger.info("Starting Docker image validation...")
            docker_result = await self._validate_docker(validation_id, artifacts)
            validation_result["phases"]["docker"] = docker_result.to_dict()
            
            # Phase 2: Kubernetes Validation
            self.logger.info("Starting Kubernetes manifest validation...")
            k8s_result = await self._validate_kubernetes(validation_id, artifacts)
            validation_result["phases"]["kubernetes"] = k8s_result.to_dict()
            
            # Phase 3: Health Check Validation
            self.logger.info("Starting health check validation...")
            health_result = await self._validate_health(validation_id, artifacts)
            validation_result["phases"]["health_check"] = health_result.to_dict()
            
            # Phase 4: Security Validation
            self.logger.info("Starting security validation...")
            security_result = await self._validate_security(validation_id, artifacts)
            validation_result["phases"]["security"] = security_result.to_dict()
            
            # Phase 5: Configuration Validation
            self.logger.info("Starting configuration validation...")
            config_result = await self._validate_configuration(validation_id, artifacts, environment)
            validation_result["phases"]["configuration"] = config_result.to_dict()
            
            # Aggregate results
            self._aggregate_results(validation_result)
            
            # Phase 6: Dry-Run Simulation
            if validation_result["is_deployable"]:
                self.logger.info("Starting dry-run simulation...")
                sim_result = await self.simulator.simulate_deployment(
                    validation_id,
                    artifacts,
                    environment,
                    dry_run=True,
                )
                validation_result["phases"]["simulation"] = sim_result
            
            # Phase 7: Rollback Validation
            if validation_result["is_deployable"]:
                self.logger.info("Validating rollback procedure...")
                from_version = artifacts.get("current_version", "unknown")
                to_version = artifacts.get("new_version", "unknown")
                rollback_result = await self.rollback_validator.validate_rollback_plan(
                    validation_id,
                    from_version,
                    to_version,
                    artifacts,
                )
                validation_result["phases"]["rollback"] = rollback_result.to_dict()
            
            validation_result["status"] = "passed" if validation_result["is_deployable"] else ("warning" if validation_result["summary"]["failed_checks"] == 0 else "failed")
            
        except Exception as e:
            validation_result["status"] = "failed"
            validation_result["error"] = str(e)
            self.logger.error(f"Validation failed: {e}")
        
        validation_result["completed_at"] = datetime.utcnow().isoformat()
        return validation_result
    
    async def _validate_docker(
        self,
        validation_id: str,
        artifacts: Dict[str, Any],
    ) -> ValidationResult:
        """Validate Docker image."""
        image_metadata = artifacts.get("docker_image", {})
        image_id = artifacts.get("image_id", "")
        
        result = await self.docker_validator.validate_image(
            validation_id,
            image_id,
            image_metadata,
        )
        
        return result
    
    async def _validate_kubernetes(
        self,
        validation_id: str,
        artifacts: Dict[str, Any],
    ) -> ValidationResult:
        """Validate Kubernetes manifests."""
        manifests = artifacts.get("kubernetes_manifests", [])
        
        result = await self.k8s_validator.validate_manifests(
            validation_id,
            manifests,
        )
        
        return result
    
    async def _validate_health(
        self,
        validation_id: str,
        artifacts: Dict[str, Any],
    ) -> ValidationResult:
        """Validate health checks."""
        deployment = artifacts.get("deployment_config", {})
        environment = artifacts.get("environment", "sandbox")
        
        result = await self.health_validator.validate_health_endpoints(
            validation_id,
            deployment,
            environment,
        )
        
        return result
    
    async def _validate_security(
        self,
        validation_id: str,
        artifacts: Dict[str, Any],
    ) -> ValidationResult:
        """Validate security."""
        result = await self.security_validator.validate_security(
            validation_id,
            artifacts,
        )
        
        return result
    
    async def _validate_configuration(
        self,
        validation_id: str,
        artifacts: Dict[str, Any],
        environment: str,
    ) -> ValidationResult:
        """Validate configuration."""
        config_files = artifacts.get("configuration", {})
        
        result = await self.config_validator.validate_configuration(
            validation_id,
            config_files,
            environment,
        )
        
        return result
    
    def _aggregate_results(self, validation_result: Dict[str, Any]) -> None:
        """Aggregate validation results."""
        summary = validation_result["summary"]
        failed_checks = 0
        
        for phase_name, phase_result in validation_result["phases"].items():
            if isinstance(phase_result, dict) and "checks" in phase_result:
                summary["total_checks"] += phase_result.get("total_checks", 0)
                summary["passed_checks"] += phase_result.get("passed_checks", 0)
                summary["failed_checks"] += phase_result.get("failed_checks", 0)
                summary["warning_checks"] += phase_result.get("warning_checks", 0)
                
                if phase_result.get("failed_checks", 0) > 0:
                    failed_checks += 1
        
        # Determine if deployable
        validation_result["is_deployable"] = failed_checks == 0
    
    async def run_pre_deployment_checklist(
        self,
        validation_id: str,
        validation_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run pre-deployment checklist."""
        checklist = PreDeploymentChecklist(self.workspace_id)
        checklist.build_default_checklist()
        
        # Update checklist based on validation results
        docker_valid = validation_results["phases"]["docker"]["failed_checks"] == 0
        checklist.set_item_status(
            "docker_image_valid",
            "pass" if docker_valid else "fail"
        )
        
        k8s_valid = validation_results["phases"]["kubernetes"]["failed_checks"] == 0
        checklist.set_item_status(
            "k8s_manifests_valid",
            "pass" if k8s_valid else "fail"
        )
        
        health_valid = validation_results["phases"]["health_check"]["failed_checks"] == 0
        checklist.set_item_status(
            "health_checks_pass",
            "pass" if health_valid else "fail"
        )
        
        security_valid = validation_results["phases"]["security"]["failed_checks"] == 0
        checklist.set_item_status(
            "security_validation_passed",
            "pass" if security_valid else "fail"
        )
        
        config_valid = validation_results["phases"]["configuration"]["failed_checks"] == 0
        checklist.set_item_status(
            "configuration_complete",
            "pass" if config_valid else "fail"
        )
        
        return {
            "validation_id": validation_id,
            "checklist": checklist.to_dict(),
            "all_passed": checklist.all_passed(),
            "status_summary": checklist.get_status_summary(),
        }
