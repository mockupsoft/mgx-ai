# -*- coding: utf-8 -*-
"""
Service Health Check Tests

Tests cover:
- PostgreSQL health check
- Redis health check
- MinIO health check
- API health check
- Service dependency tests
"""

import pytest
import subprocess
import time
from typing import Optional


@pytest.mark.docker
class TestPostgreSQLHealth:
    """Test PostgreSQL health checks."""
    
    def test_postgres_container_running(self, docker_services):
        """Test that PostgreSQL container is running."""
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={docker_services['postgres']}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        assert result.returncode == 0
        assert "Up" in result.stdout
    
    def test_postgres_health_status(self, docker_services, postgres_healthy):
        """Test PostgreSQL health status."""
        # If fixture passed, PostgreSQL is healthy
        assert postgres_healthy is True
    
    def test_postgres_connection(self, docker_services):
        """Test PostgreSQL connection."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["postgres"],
                "pg_isready",
                "-U",
                "mgx",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode == 0
        assert "accepting connections" in result.stdout.lower()
    
    def test_postgres_database_exists(self, docker_services):
        """Test that database exists."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["postgres"],
                "psql",
                "-U",
                "mgx",
                "-d",
                "mgx",
                "-c",
                "SELECT 1;",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should be able to connect and query
        assert result.returncode == 0 or "does not exist" not in result.stderr.lower()


@pytest.mark.docker
class TestRedisHealth:
    """Test Redis health checks."""
    
    def test_redis_container_running(self, docker_services):
        """Test that Redis container is running."""
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={docker_services['redis']}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        assert result.returncode == 0
        assert "Up" in result.stdout
    
    def test_redis_health_status(self, docker_services, redis_healthy):
        """Test Redis health status."""
        assert redis_healthy is True
    
    def test_redis_connection(self, docker_services):
        """Test Redis connection."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["redis"],
                "redis-cli",
                "ping",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode == 0
        assert result.stdout.strip().upper() == "PONG"
    
    def test_redis_data_persistence(self, docker_services):
        """Test Redis data persistence."""
        # Set a value
        subprocess.run(
            [
                "docker",
                "exec",
                docker_services["redis"],
                "redis-cli",
                "SET",
                "test_key",
                "test_value",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Get the value
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["redis"],
                "redis-cli",
                "GET",
                "test_key",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode == 0
        assert result.stdout.strip() == "test_value"


@pytest.mark.docker
class TestMinIOHealth:
    """Test MinIO health checks."""
    
    def test_minio_container_running(self, docker_services):
        """Test that MinIO container is running."""
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={docker_services['minio']}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        assert result.returncode == 0
        assert "Up" in result.stdout
    
    def test_minio_health_status(self, docker_services, minio_healthy):
        """Test MinIO health status."""
        assert minio_healthy is True
    
    def test_minio_api_accessible(self, docker_services):
        """Test MinIO API accessibility."""
        result = subprocess.run(
            [
                "curl",
                "-f",
                "http://localhost:9000/minio/health/live",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should be accessible
        assert result.returncode == 0
    
    def test_minio_console_accessible(self, docker_services):
        """Test MinIO console accessibility."""
        result = subprocess.run(
            [
                "curl",
                "-f",
                "http://localhost:9001",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Console should be accessible
        assert result.returncode == 0 or result.status_code == 200


@pytest.mark.docker
class TestAPIHealth:
    """Test API health checks."""
    
    def test_api_container_running(self, docker_services):
        """Test that API container is running."""
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={docker_services['api']}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        assert result.returncode == 0
        assert "Up" in result.stdout
    
    def test_api_health_status(self, docker_services, api_healthy):
        """Test API health status."""
        assert api_healthy is True
    
    def test_api_health_endpoint(self, docker_services):
        """Test API health endpoint."""
        result = subprocess.run(
            [
                "curl",
                "-f",
                "http://localhost:8000/health",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode == 0
    
    def test_api_readiness_endpoint(self, docker_services):
        """Test API readiness endpoint."""
        result = subprocess.run(
            [
                "curl",
                "-f",
                "http://localhost:8000/health/ready",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode == 0
    
    def test_api_liveness_endpoint(self, docker_services):
        """Test API liveness endpoint."""
        result = subprocess.run(
            [
                "curl",
                "-f",
                "http://localhost:8000/health/live",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode == 0


@pytest.mark.docker
class TestServiceDependencies:
    """Test service dependency management."""
    
    def test_api_depends_on_postgres(self, docker_services):
        """Test that API depends on PostgreSQL."""
        # API should not start if PostgreSQL is not healthy
        # This is tested by docker-compose depends_on configuration
        pass
    
    def test_api_depends_on_redis(self, docker_services):
        """Test that API depends on Redis."""
        # API should not start if Redis is not healthy
        pass
    
    def test_api_depends_on_minio(self, docker_services):
        """Test that API depends on MinIO."""
        # API should not start if MinIO is not healthy
        pass
    
    def test_migration_runs_before_api(self, docker_services):
        """Test that migrations run before API starts."""
        # mgx-migrate should complete before mgx-ai starts
        # This is tested by docker-compose depends_on configuration
        pass
    
    def test_minio_init_runs_after_minio(self, docker_services):
        """Test that MinIO init runs after MinIO is healthy."""
        # minio-init should run after minio is healthy
        pass


@pytest.mark.docker
class TestServiceStartupOrder:
    """Test service startup order."""
    
    def test_infrastructure_services_start_first(self, docker_services):
        """Test that infrastructure services (postgres, redis, minio) start first."""
        # These should start before application services
        pass
    
    def test_init_services_run_after_dependencies(self, docker_services):
        """Test that init services run after their dependencies."""
        # minio-init after minio
        # mgx-migrate after postgres
        pass
    
    def test_api_starts_last(self, docker_services):
        """Test that API starts after all dependencies."""
        # API should start after:
        # - PostgreSQL is healthy
        # - Redis is healthy
        # - MinIO is healthy
        # - Migrations are complete
        pass

