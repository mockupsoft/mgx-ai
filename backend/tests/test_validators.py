# -*- coding: utf-8 -*-
"""Tests for deployment validator services."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.validators import (
    DeploymentValidator,
    DockerValidator,
    KubernetesValidator,
    HealthCheckValidator,
    SecurityValidator,
    ConfigurationValidator,
    PreDeploymentChecklist,
    DeploymentSimulator,
    RollbackValidator,
)
from backend.services.validators.base import CheckResult, CheckStatus, ValidationResult


@pytest.fixture
def workspace_id():
    """Fixture for workspace ID."""
    return "test-workspace"


@pytest.fixture
def docker_validator(workspace_id):
    """Fixture for Docker validator."""
    return DockerValidator(workspace_id)


@pytest.fixture
def k8s_validator(workspace_id):
    """Fixture for Kubernetes validator."""
    return KubernetesValidator(workspace_id)


@pytest.fixture
def health_validator(workspace_id):
    """Fixture for health check validator."""
    return HealthCheckValidator(workspace_id)


@pytest.fixture
def security_validator(workspace_id):
    """Fixture for security validator."""
    return SecurityValidator(workspace_id)


@pytest.fixture
def config_validator(workspace_id):
    """Fixture for configuration validator."""
    return ConfigurationValidator(workspace_id)


@pytest.fixture
def simulator(workspace_id):
    """Fixture for deployment simulator."""
    return DeploymentSimulator(workspace_id)


@pytest.fixture
def rollback_validator(workspace_id):
    """Fixture for rollback validator."""
    return RollbackValidator(workspace_id)


# Test Docker Validator

@pytest.mark.asyncio
async def test_docker_validate_image_success(docker_validator):
    """Test successful Docker image validation."""
    result = await docker_validator.validate_image(
        validation_id="val-123",
        image_id="myapp:1.0.0",
        image_metadata={
            "size_bytes": 256000000,
            "base_image": "python:3.11-slim",
            "entry_point": ["python", "app.py"],
            "health_check": {
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
            },
            "user": "app",
            "layers": [{"digest": "sha256:abc123"}],
        }
    )
    
    assert result.is_passing()
    assert result.total_checks > 0
    assert result.failed_checks == 0


@pytest.mark.asyncio
async def test_docker_validate_image_missing(docker_validator):
    """Test Docker validation with missing image."""
    result = await docker_validator.validate_image(
        validation_id="val-123",
        image_id="",
        image_metadata={}
    )
    
    assert not result.is_passing()
    assert result.failed_checks > 0


@pytest.mark.asyncio
async def test_docker_validate_large_image_warning(docker_validator):
    """Test Docker validation with large image size."""
    result = await docker_validator.validate_image(
        validation_id="val-123",
        image_id="myapp:1.0.0",
        image_metadata={
            "size_bytes": 600 * 1024 * 1024,  # 600MB (over limit)
            "base_image": "python:3.11-slim",
            "entry_point": ["python", "app.py"],
        }
    )
    
    assert result.has_warnings()


@pytest.mark.asyncio
async def test_docker_validate_hardcoded_secrets(docker_validator):
    """Test Docker validation detects hardcoded secrets."""
    result = await docker_validator.validate_image(
        validation_id="val-123",
        image_id="myapp:1.0.0",
        image_metadata={
            "dockerfile_content": "ENV API_KEY=secret123",
            "base_image": "python:3.11-slim",
            "entry_point": ["python", "app.py"],
        }
    )
    
    assert not result.is_passing()


# Test Kubernetes Validator

@pytest.mark.asyncio
async def test_k8s_validate_valid_manifests(k8s_validator):
    """Test Kubernetes validation with valid manifests."""
    manifests = [
        """
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: myapp
        spec:
          replicas: 3
          template:
            spec:
              containers:
              - name: app
                image: myapp:1.0.0
                resources:
                  requests:
                    cpu: 500m
                    memory: 256Mi
                livenessProbe:
                  httpGet:
                    path: /health
                    port: 8000
                readinessProbe:
                  httpGet:
                    path: /ready
                    port: 8000
        """
    ]
    
    result = await k8s_validator.validate_manifests(
        validation_id="val-123",
        manifests=manifests
    )
    
    assert result.is_passing()


@pytest.mark.asyncio
async def test_k8s_validate_invalid_yaml(k8s_validator):
    """Test Kubernetes validation with invalid YAML."""
    manifests = [
        """
        kind: Deployment
        invalid: yaml: structure
        """
    ]
    
    result = await k8s_validator.validate_manifests(
        validation_id="val-123",
        manifests=manifests
    )
    
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_k8s_validate_missing_resources(k8s_validator):
    """Test Kubernetes validation with missing resource limits."""
    manifests = [
        """
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: myapp
        spec:
          template:
            spec:
              containers:
              - name: app
                image: myapp:1.0.0
        """
    ]
    
    result = await k8s_validator.validate_manifests(
        validation_id="val-123",
        manifests=manifests
    )
    
    assert not result.is_passing() or result.has_warnings()


# Test Health Validator

@pytest.mark.asyncio
async def test_health_validate_success(health_validator):
    """Test successful health check validation."""
    result = await health_validator.validate_health_endpoints(
        validation_id="val-123",
        deployment={
            "health_endpoint": {
                "url": "http://localhost:8000/health",
            },
            "required_env_vars": ["DATABASE_URL"],
            "env_vars": {
                "DATABASE_URL": "postgresql://db:5432/app",
            },
            "dependencies": {
                "database": {
                    "type": "postgresql",
                    "host": "db",
                    "port": 5432,
                }
            },
            "health_check_timeout": 5,
        }
    )
    
    assert result.is_passing()


@pytest.mark.asyncio
async def test_health_validate_missing_env_vars(health_validator):
    """Test health validation with missing environment variables."""
    result = await health_validator.validate_health_endpoints(
        validation_id="val-123",
        deployment={
            "required_env_vars": ["DATABASE_URL"],
            "env_vars": {},  # Missing DATABASE_URL
        }
    )
    
    assert not result.is_passing()


# Test Security Validator

@pytest.mark.asyncio
async def test_security_validate_no_secrets(security_validator):
    """Test security validation with no hardcoded secrets."""
    result = await security_validator.validate_security(
        validation_id="val-123",
        artifacts={
            "application_code": "normal code",
            "configuration": {},
            "env_vars": {},
            "security_headers": {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            },
            "cors_config": {
                "allowed_origins": ["https://app.example.com"]
            }
        }
    )
    
    assert result.is_passing()


@pytest.mark.asyncio
async def test_security_validate_hardcoded_secrets(security_validator):
    """Test security validation detects hardcoded secrets."""
    result = await security_validator.validate_security(
        validation_id="val-123",
        artifacts={
            "application_code": "api_key=sk-123456",
            "configuration": {},
        }
    )
    
    assert not result.is_passing()


@pytest.mark.asyncio
async def test_security_validate_cors_all_origins(security_validator):
    """Test security validation with CORS allowing all origins."""
    result = await security_validator.validate_security(
        validation_id="val-123",
        artifacts={
            "cors_config": {
                "allowed_origins": ["*"]
            }
        }
    )
    
    assert result.has_warnings()


# Test Configuration Validator

@pytest.mark.asyncio
async def test_config_validate_success(config_validator):
    """Test successful configuration validation."""
    result = await config_validator.validate_configuration(
        validation_id="val-123",
        config_files={
            "required_env_vars": ["DATABASE_URL"],
            "env_vars": {
                "DATABASE_URL": "postgresql://prod.example.com:5432/app",
            },
            "database": {
                "type": "postgresql",
                "host": "prod.example.com",
                "port": 5432,
                "database": "app",
            },
            "log_level": "WARNING",
            "replicas": 3,
        },
        environment="production"
    )
    
    assert result.is_passing()


@pytest.mark.asyncio
async def test_config_validate_missing_vars(config_validator):
    """Test configuration validation with missing env vars."""
    result = await config_validator.validate_configuration(
        validation_id="val-123",
        config_files={
            "required_env_vars": ["DATABASE_URL"],
            "env_vars": {},
        }
    )
    
    assert not result.is_passing()


@pytest.mark.asyncio
async def test_config_validate_localhost_in_production(config_validator):
    """Test configuration validation with localhost in production."""
    result = await config_validator.validate_configuration(
        validation_id="val-123",
        config_files={
            "required_env_vars": ["DATABASE_URL"],
            "env_vars": {
                "DATABASE_URL": "postgresql://localhost:5432/app",
            },
        },
        environment="production"
    )
    
    assert not result.is_passing()


# Test Checklist

def test_checklist_creation():
    """Test pre-deployment checklist creation."""
    checklist = PreDeploymentChecklist(workspace_id="ws-123")
    checklist.build_default_checklist()
    
    assert len(checklist.items) > 0
    assert all(item.status == "pending" for item in checklist.items)


def test_checklist_set_status():
    """Test setting checklist item status."""
    checklist = PreDeploymentChecklist(workspace_id="ws-123")
    checklist.add_item("test_item", "Test item", status="pending")
    
    checklist.set_item_status("test_item", "pass")
    
    assert checklist.items[0].status == "pass"


def test_checklist_all_passed():
    """Test checklist all_passed check."""
    checklist = PreDeploymentChecklist(workspace_id="ws-123")
    checklist.add_item("item1", status="pass")
    checklist.add_item("item2", status="not_applicable")
    
    assert checklist.all_passed()


def test_checklist_not_all_passed():
    """Test checklist not all_passed check."""
    checklist = PreDeploymentChecklist(workspace_id="ws-123")
    checklist.add_item("item1", status="pass")
    checklist.add_item("item2", status="pending")
    
    assert not checklist.all_passed()


# Test Simulator

@pytest.mark.asyncio
async def test_simulator_simulate_deployment(simulator):
    """Test deployment simulation."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {
                    "kind": "Deployment",
                    "metadata": {"name": "myapp"}
                }
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    assert len(result["steps"]) > 0


# Test Rollback Validator

@pytest.mark.asyncio
async def test_rollback_validate_success(rollback_validator):
    """Test successful rollback validation."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {
                "0.9.0": "myapp:0.9.0",
            },
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "steps": ["Stop", "Restore", "Start"],
            }
        }
    )
    
    assert result.validation_passed


@pytest.mark.asyncio
async def test_rollback_validate_no_backup(rollback_validator):
    """Test rollback validation without backup."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {
                "0.9.0": "myapp:0.9.0",
            },
            "database_rollback_plan": {
                "backup_available": False,
            }
        }
    )
    
    assert not result.validation_passed


# Test Main Orchestrator

@pytest.mark.asyncio
async def test_main_validator_validate_artifacts():
    """Test main validator orchestrator."""
    validator = DeploymentValidator(workspace_id="ws-123")
    
    result = await validator.validate_artifacts(
        validation_id="val-123",
        build_id="build-123",
        artifacts={
            "docker_image": {
                "size_bytes": 256000000,
                "base_image": "python:3.11-slim",
                "entry_point": ["python", "app.py"],
                "user": "app",
            },
            "kubernetes_manifests": [
                {
                    "kind": "Deployment",
                    "metadata": {"name": "myapp"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "resources": {
                                            "requests": {"cpu": "500m"},
                                            "limits": {"cpu": "1000m"},
                                        },
                                        "livenessProbe": {},
                                        "readinessProbe": {},
                                    }
                                ]
                            }
                        }
                    }
                }
            ],
            "deployment_config": {},
            "configuration": {
                "required_env_vars": [],
                "env_vars": {},
            }
        },
        environment="staging"
    )
    
    assert result["status"] in ["passed", "warning", "failed"]
    assert "phases" in result
    assert result["summary"]["total_checks"] > 0
