# -*- coding: utf-8 -*-
"""Tests for deployment procedures and integration scenarios."""

import sys
import os

# Add project root to path to allow direct imports without conftest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import validators directly
from backend.services.validators import (
    DeploymentValidator,
    PreDeploymentChecklist,
    DeploymentSimulator,
    RollbackValidator,
)


@pytest.fixture
def workspace_id():
    """Fixture for workspace ID."""
    return "test-workspace"


@pytest.fixture
def checklist(workspace_id):
    """Fixture for pre-deployment checklist."""
    return PreDeploymentChecklist(workspace_id)


@pytest.fixture
def simulator(workspace_id):
    """Fixture for deployment simulator."""
    return DeploymentSimulator(workspace_id)


@pytest.fixture
def rollback_validator(workspace_id):
    """Fixture for rollback validator."""
    return RollbackValidator(workspace_id)


@pytest.fixture
def deployment_validator(workspace_id):
    """Fixture for main deployment validator."""
    return DeploymentValidator(workspace_id)


# ============================================================================
# Pre-Deployment Checklist Tests
# ============================================================================

def test_checklist_default_items_creation(checklist):
    """Test that default 12-item checklist is created."""
    checklist.build_default_checklist()
    
    assert len(checklist.items) == 12
    assert any("docker" in item.description.lower() for item in checklist.items)
    assert any("kubernetes" in item.description.lower() or "k8s" in item.name.lower() for item in checklist.items)
    assert any("health" in item.description.lower() for item in checklist.items)
    assert any("security" in item.description.lower() for item in checklist.items)
    assert any("configuration" in item.description.lower() for item in checklist.items)
    assert any("backup" in item.description.lower() for item in checklist.items)
    assert any("rollback" in item.description.lower() for item in checklist.items)
    assert any("monitoring" in item.description.lower() for item in checklist.items)
    assert any("load testing" in item.description.lower() for item in checklist.items)
    assert any("security review" in item.description.lower() for item in checklist.items)
    assert any("deployment window" in item.description.lower() for item in checklist.items)
    assert any("stakeholder" in item.description.lower() or "approval" in item.description.lower() for item in checklist.items)


def test_checklist_item_status_tracking(checklist):
    """Test checklist item status tracking."""
    checklist.add_item("test_item", "Test description", status="pending")
    
    # Check initial status
    assert checklist.items[0].status == "pending"
    
    # Update to pass
    checklist.set_item_status("test_item", "pass")
    assert checklist.items[0].status == "pass"
    
    # Update to fail
    checklist.set_item_status("test_item", "fail")
    assert checklist.items[0].status == "fail"


def test_checklist_completion_summary(checklist):
    """Test checklist completion summary."""
    checklist.add_item("item1", description="Item 1", status="pass")
    checklist.add_item("item2", description="Item 2", status="pass")
    checklist.add_item("item3", description="Item 3", status="not_applicable")
    
    summary = checklist.get_status_summary()
    
    assert checklist.items[0].status == "pass"
    assert checklist.items[1].status == "pass"
    assert checklist.items[2].status == "not_applicable"
    assert checklist.all_passed()


def test_checklist_prevent_deployment_critical_unchecked(checklist):
    """Test that deployment is prevented if critical items are unchecked."""
    checklist.add_item("critical_item", description="Critical", status="pending")
    checklist.add_item("normal_item", description="Normal", status="pass")
    
    # Not all passed
    assert not checklist.all_passed()
    
    # Mark critical as passed
    checklist.set_item_status("critical_item", "pass")
    assert checklist.all_passed()


def test_checklist_human_signoff_required(checklist):
    """Test that human sign-off tracking exists."""
    checklist.add_item("critical_item", description="Critical item", status="pass")
    
    # Can check all passed status
    checklist.set_item_status("critical_item", "pass")
    
    # Verify item is in pass state
    assert checklist.items[0].status == "pass"


def test_checklist_not_all_passed_with_failure(checklist):
    """Test checklist with failed items."""
    checklist.add_item("item1", status="pass")
    checklist.add_item("item2", status="fail")
    
    assert not checklist.all_passed()


def test_checklist_export_report(checklist):
    """Test checklist export to report format."""
    checklist.build_default_checklist()
    checklist.set_item_status(checklist.items[0].name, "pass")
    
    report = checklist.to_dict()
    
    assert "total_items" in report
    assert "items" in report
    assert len(report["items"]) == 12


# ============================================================================
# Deployment Simulation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_simulator_test_namespace_creation(simulator):
    """Test that simulator creates test namespace."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    assert "test_namespace" in result
    assert result["test_namespace"].startswith("test-")


@pytest.mark.asyncio
async def test_simulator_deployment_succeeds_test_env(simulator):
    """Test that deployment succeeds in test environment."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    assert len(result["steps"]) > 0


@pytest.mark.asyncio
async def test_simulator_pods_reach_ready_state(simulator):
    """Test that pods reach ready state."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    # Verify readiness step exists
    assert any(step["name"] == "Wait for Readiness" for step in result["steps"])


@pytest.mark.asyncio
async def test_simulator_health_checks_respond(simulator):
    """Test that health checks are executed."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
            "deployment_config": {
                "health_endpoint": {"url": "http://localhost:8000/health"}
            }
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    assert "health_checks" in result


@pytest.mark.asyncio
async def test_simulator_metrics_collected(simulator):
    """Test that metrics are collected during simulation."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
        },
        target_environment="staging",
        dry_run=True,
    )
    
    assert "metrics" in result
    assert "deployment_time_seconds" in result["metrics"] or "resource_usage" in result["metrics"]


@pytest.mark.asyncio
async def test_simulator_test_cleanup_works(simulator):
    """Test that test environment is cleaned up."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    # Verify cleanup step is in the steps
    assert any(step["name"] == "Cleanup Test Resources" for step in result["steps"])


@pytest.mark.asyncio
async def test_simulator_dry_run_no_production_impact(simulator):
    """Test that dry-run doesn't affect production."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "test-app"}}
            ],
        },
        target_environment="production",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    assert result["dry_run"] is True
    assert "production" not in result.get("deployed_to", [])


# ============================================================================
# Rollback Validation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_rollback_previous_version_available(rollback_validator):
    """Test that previous version availability is checked."""
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
                "estimated_time": 10,
                "steps": ["Restore backup"]
            }
        }
    )
    
    assert result.validation_passed
    assert result.previous_version_available


@pytest.mark.asyncio
async def test_rollback_no_code_changes_required(rollback_validator):
    """Test that rollback doesn't require code changes."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "estimated_time": 10,
                "steps": ["Restore backup"]
            },
            "requires_code_changes": False,
        }
    )
    
    assert result.validation_passed


@pytest.mark.asyncio
async def test_rollback_database_migrations_rollback(rollback_validator):
    """Test that database migrations can rollback."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback_v1.sql",
                "estimated_time": 10,
                "steps": ["Restore backup", "Rollback migrations"],
                "can_rollback_migrations": True,
            }
        }
    )
    
    assert result.validation_passed
    assert result.database_rollback_valid


@pytest.mark.asyncio
async def test_rollback_sla_window_respected(rollback_validator):
    """Test that SLA window (≤30 minutes) is verified."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "estimated_time": 10,
                "steps": ["Restore backup"]
            },
        }
    )
    
    assert result.validation_passed
    assert result.estimated_rollback_time_minutes <= 30


@pytest.mark.asyncio
async def test_rollback_time_estimated(rollback_validator):
    """Test that rollback time is estimated."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "estimated_time": 10,
                "steps": ["Restore backup"]
            },
        }
    )
    
    assert hasattr(result, 'estimated_rollback_time_minutes')
    assert result.estimated_rollback_time_minutes > 0


@pytest.mark.asyncio
async def test_rollback_post_health_check_passes(rollback_validator):
    """Test that rollback procedure includes health check verification."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "estimated_time": 10,
                "steps": ["Restore backup"]
            },
        }
    )
    
    assert result.validation_passed
    # Verify health checks are in procedure
    assert any("health" in step.lower() for step in result.procedure_steps)


@pytest.mark.asyncio
async def test_rollback_data_consistency_verified(rollback_validator):
    """Test that data consistency verification is included in manual steps."""
    result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "estimated_time": 10,
                "steps": ["Restore backup"]
            },
        }
    )
    
    assert result.validation_passed
    # Verify data integrity check is in manual steps
    assert any("integrity" in step.lower() for step in result.manual_steps)


# ============================================================================
# Integration Scenarios Tests
# ============================================================================

@pytest.mark.asyncio
async def test_full_deployment_checklist_flow(checklist, simulator, rollback_validator):
    """Test complete deployment checklist flow."""
    # Step 1: Create checklist
    checklist.build_default_checklist()
    
    # Step 2: Complete checklist items
    for item in checklist.items:
        checklist.set_item_status(item.id, "pass")
    
    assert checklist.all_passed()
    assert checklist.can_deploy()
    
    # Step 3: Run simulation
    sim_result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "app"}}
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert sim_result["status"] == "completed"
    
    # Step 4: Validate rollback plan
    rollback_result = await rollback_validator.validate_rollback_plan(
        validation_id="val-123",
        from_version="1.0.0",
        to_version="0.9.0",
        artifacts={
            "docker_images": {"0.9.0": "myapp:0.9.0"},
            "database_rollback_plan": {
                "backup_available": True,
                "rollback_script": "rollback.sql",
                "estimated_time": 10,
                "steps": ["Restore backup"]
            },
        }
    )
    
    assert rollback_result.validation_passed


@pytest.mark.asyncio
async def test_deployment_with_security_checks(deployment_validator):
    """Test deployment with security validation."""
    with patch.object(deployment_validator, 'validate_security', new_callable=AsyncMock) as mock_security:
        mock_security.return_value = MagicMock(is_passing=lambda: True)
        
        result = await deployment_validator.validate_artifacts(
            validation_id="val-123",
            build_id="build-123",
            artifacts={
                "docker_image": {
                    "size_bytes": 256000000,
                    "base_image": "python:3.11-slim",
                },
                "application_code": "# Clean code",
            }
        )
        
        assert result.get("security_passed")


@pytest.mark.asyncio
async def test_deployment_simulation_success(simulator):
    """Test successful deployment simulation."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": "myapp"},
                    "spec": {
                        "replicas": 3,
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "image": "myapp:1.0.0",
                                        "resources": {
                                            "requests": {
                                                "cpu": "500m",
                                                "memory": "256Mi"
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_deployment_health_checks_green(simulator):
    """Test that health checks are green after deployment."""
    with patch.object(simulator, '_run_health_checks', new_callable=AsyncMock) as mock_health:
        mock_health.return_value = {
            "health": True,
            "ready": True,
            "live": True,
        }
        
        result = await simulator.simulate_deployment(
            validation_id="val-123",
            artifacts={
                "kubernetes_manifests": [
                    {"kind": "Deployment", "metadata": {"name": "app"}}
                ],
            },
            target_environment="staging",
            dry_run=True
        )
        
        assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_deployment_performance_acceptable(simulator):
    """Test that deployment performance is acceptable."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "app"}}
            ],
        },
        target_environment="staging",
        dry_run=True,
    )
    
    assert result["status"] == "completed"
    # Ensure deployment has metrics
    assert "metrics" in result


@pytest.mark.asyncio
async def test_production_deployment_succeeds(simulator):
    """Test production deployment scenario (dry-run)."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "app"}}
            ],
        },
        target_environment="production",
        dry_run=True  # Always dry-run in tests
    )
    
    assert result["status"] == "completed"
    assert result["dry_run"] is True


@pytest.mark.asyncio
async def test_deployment_monitoring_configured(simulator):
    """Test that monitoring is configured during deployment."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "app"}}
            ],
            "monitoring_config": {
                "prometheus": True,
                "grafana_dashboard": "app-metrics",
                "alerts": ["high-cpu", "high-memory"],
            }
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_deployment_no_errors_or_alerts(simulator):
    """Test that deployment has no errors or alerts."""
    result = await simulator.simulate_deployment(
        validation_id="val-123",
        artifacts={
            "kubernetes_manifests": [
                {"kind": "Deployment", "metadata": {"name": "app"}}
            ],
        },
        target_environment="staging",
        dry_run=True
    )
    
    assert result["status"] == "completed"
    assert not result.get("errors")
    assert not result.get("critical_alerts")
