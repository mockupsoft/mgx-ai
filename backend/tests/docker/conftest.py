# -*- coding: utf-8 -*-
"""
Docker Compose Test Infrastructure

Provides:
- Docker compose fixtures
- Service health check utilities
- Container lifecycle management
- Test database setup/teardown
"""

import pytest
import subprocess
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any


# Path to docker-compose files
DOCKER_COMPOSE_FILE = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"
DOCKER_COMPOSE_TEST_FILE = Path(__file__).parent.parent.parent.parent / "docker-compose.test.yml"


def check_docker_available() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_docker_compose_available() -> bool:
    """Check if docker compose is available."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for tests."""
    if not check_docker_available():
        pytest.skip("Docker is not available")
    if not check_docker_compose_available():
        pytest.skip("Docker Compose is not available")
    return True


@pytest.fixture(scope="session")
def docker_compose_file():
    """Get docker-compose file path."""
    # Use test compose file if exists, otherwise use main
    if DOCKER_COMPOSE_TEST_FILE.exists():
        return DOCKER_COMPOSE_TEST_FILE
    return DOCKER_COMPOSE_FILE


@pytest.fixture(scope="session")
def docker_compose_project_name():
    """Get docker compose project name for test isolation."""
    return f"mgx-test-{int(time.time())}"


def wait_for_service_health(
    service_name: str,
    healthcheck_cmd: list,
    timeout: int = 60,
    interval: int = 2,
) -> bool:
    """Wait for a service to become healthy."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            result = subprocess.run(
                healthcheck_cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        time.sleep(interval)
    
    return False


def get_service_health(service_name: str, project_name: str) -> Optional[str]:
    """Get service health status."""
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                f"{project_name}-{service_name}-1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


@pytest.fixture(scope="session")
def docker_compose_up(docker_available, docker_compose_file, docker_compose_project_name):
    """Start docker compose services."""
    if not docker_available:
        pytest.skip("Docker not available")
    
    # Start services
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(docker_compose_file),
            "-p",
            docker_compose_project_name,
            "up",
            "-d",
            "--build",
        ],
        check=False,
        timeout=300,
    )
    
    yield
    
    # Teardown: stop and remove containers
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(docker_compose_file),
            "-p",
            docker_compose_project_name,
            "down",
            "-v",
        ],
        check=False,
        timeout=60,
    )


@pytest.fixture
def docker_services(docker_compose_up, docker_compose_project_name):
    """Get docker services fixture."""
    return {
        "project_name": docker_compose_project_name,
        "postgres": f"{docker_compose_project_name}-postgres-1",
        "redis": f"{docker_compose_project_name}-redis-1",
        "minio": f"{docker_compose_project_name}-minio-1",
        "api": f"{docker_compose_project_name}-mgx-ai-1",
    }


def check_service_health(service_name: str, project_name: str) -> bool:
    """Check if a service is healthy."""
    health_status = get_service_health(service_name, project_name)
    return health_status == "healthy"


@pytest.fixture
def postgres_healthy(docker_services):
    """Wait for PostgreSQL to be healthy."""
    project_name = docker_services["project_name"]
    
    # Wait for PostgreSQL
    if wait_for_service_health(
        "postgres",
        ["docker", "exec", docker_services["postgres"], "pg_isready", "-U", "mgx"],
        timeout=60,
    ):
        return True
    
    pytest.fail("PostgreSQL did not become healthy")


@pytest.fixture
def redis_healthy(docker_services):
    """Wait for Redis to be healthy."""
    project_name = docker_services["project_name"]
    
    # Wait for Redis
    if wait_for_service_health(
        "redis",
        ["docker", "exec", docker_services["redis"], "redis-cli", "ping"],
        timeout=30,
    ):
        return True
    
    pytest.fail("Redis did not become healthy")


@pytest.fixture
def minio_healthy(docker_services):
    """Wait for MinIO to be healthy."""
    project_name = docker_services["project_name"]
    
    # Wait for MinIO
    if wait_for_service_health(
        "minio",
        ["curl", "-f", f"http://localhost:9000/minio/health/live"],
        timeout=60,
    ):
        return True
    
    pytest.fail("MinIO did not become healthy")


@pytest.fixture
def api_healthy(docker_services):
    """Wait for API to be healthy."""
    project_name = docker_services["project_name"]
    
    # Wait for API
    if wait_for_service_health(
        "mgx-ai",
        ["curl", "-f", "http://localhost:8000/health"],
        timeout=120,
    ):
        return True
    
    pytest.fail("API did not become healthy")


@pytest.fixture
def all_services_healthy(postgres_healthy, redis_healthy, minio_healthy, api_healthy):
    """Wait for all services to be healthy."""
    return {
        "postgres": postgres_healthy,
        "redis": redis_healthy,
        "minio": minio_healthy,
        "api": api_healthy,
    }




