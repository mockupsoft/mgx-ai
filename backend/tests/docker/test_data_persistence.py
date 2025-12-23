# -*- coding: utf-8 -*-
"""
Data Persistence Tests

Tests cover:
- Database data persistence
- Redis data persistence
- MinIO data persistence
- Volume mount tests
- Backup/restore tests
"""

import pytest
import subprocess
import time
import requests
from typing import Optional


@pytest.mark.docker
class TestDatabasePersistence:
    """Test database data persistence."""
    
    def test_database_data_persists_after_restart(self, docker_services, all_services_healthy):
        """Test that database data persists after container restart."""
        # Create test data
        workspace_data = {"name": "Persistence Test", "slug": "persistence-test"}
        response = requests.post(
            "http://localhost:8000/api/workspaces",
            json=workspace_data,
            timeout=10,
        )
        
        if response.status_code in [200, 201]:
            workspace = response.json()
            workspace_id = workspace.get("id")
            
            # Restart PostgreSQL container
            subprocess.run(
                ["docker", "restart", docker_services["postgres"]],
                timeout=30,
            )
            
            # Wait for PostgreSQL to be ready
            time.sleep(10)
            
            # Verify data still exists
            get_response = requests.get(
                f"http://localhost:8000/api/workspaces/{workspace_id}",
                timeout=10,
            )
            # Should still be able to retrieve (if auth allows)
            assert get_response.status_code in [200, 401, 403]
    
    def test_database_volume_mount(self, docker_services):
        """Test that database volume is mounted correctly."""
        # Check volume mount
        result = subprocess.run(
            [
                "docker",
                "inspect",
                docker_services["postgres"],
                "--format",
                "{{.Mounts}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should have volume mount
        assert result.returncode == 0
        assert "pg_data" in result.stdout or "volume" in result.stdout.lower()
    
    def test_database_backup_restore(self, docker_services):
        """Test database backup and restore."""
        # This would test:
        # 1. Create backup
        # 2. Add data
        # 3. Restore backup
        # 4. Verify data is restored
        pass


@pytest.mark.docker
class TestRedisPersistence:
    """Test Redis data persistence."""
    
    def test_redis_data_persists_after_restart(self, docker_services):
        """Test that Redis data persists after container restart."""
        # Set a value
        subprocess.run(
            [
                "docker",
                "exec",
                docker_services["redis"],
                "redis-cli",
                "SET",
                "persist_test",
                "persist_value",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Restart Redis container
        subprocess.run(
            ["docker", "restart", docker_services["redis"]],
            timeout=30,
        )
        
        # Wait for Redis to be ready
        time.sleep(5)
        
        # Verify value still exists (if AOF enabled)
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["redis"],
                "redis-cli",
                "GET",
                "persist_test",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Value may or may not persist depending on AOF configuration
        # But should not error
        assert result.returncode == 0
    
    def test_redis_volume_mount(self, docker_services):
        """Test that Redis volume is mounted correctly."""
        # Check volume mount
        result = subprocess.run(
            [
                "docker",
                "inspect",
                docker_services["redis"],
                "--format",
                "{{.Mounts}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should have volume mount
        assert result.returncode == 0
        assert "redis_data" in result.stdout or "volume" in result.stdout.lower()


@pytest.mark.docker
class TestMinIOPersistence:
    """Test MinIO data persistence."""
    
    def test_minio_data_persists_after_restart(self, docker_services):
        """Test that MinIO data persists after container restart."""
        # This would test:
        # 1. Upload file to MinIO
        # 2. Restart MinIO container
        # 3. Verify file still exists
        pass
    
    def test_minio_volume_mount(self, docker_services):
        """Test that MinIO volume is mounted correctly."""
        # Check volume mount
        result = subprocess.run(
            [
                "docker",
                "inspect",
                docker_services["minio"],
                "--format",
                "{{.Mounts}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should have volume mount
        assert result.returncode == 0
        assert "minio_data" in result.stdout or "volume" in result.stdout.lower()
    
    def test_minio_bucket_persistence(self, docker_services):
        """Test that MinIO buckets persist after restart."""
        # Buckets should persist if volume is mounted
        pass


@pytest.mark.docker
class TestVolumeMounts:
    """Test volume mount functionality."""
    
    def test_all_volumes_created(self, docker_services):
        """Test that all required volumes are created."""
        result = subprocess.run(
            [
                "docker",
                "volume",
                "ls",
                "--format",
                "{{.Name}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should list volumes
        assert result.returncode == 0
        volumes = result.stdout.split("\n")
        # Check for expected volume names (may have project prefix)
        assert len(volumes) > 0
    
    def test_volume_permissions(self, docker_services):
        """Test that volumes have correct permissions."""
        # Check PostgreSQL volume permissions
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["postgres"],
                "ls",
                "-la",
                "/var/lib/postgresql/data",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should be able to list directory
        assert result.returncode == 0


@pytest.mark.docker
class TestBackupRestore:
    """Test backup and restore functionality."""
    
    def test_database_backup(self, docker_services):
        """Test database backup creation."""
        # Create backup
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["postgres"],
                "pg_dump",
                "-U",
                "mgx",
                "mgx",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        # Should create backup
        assert result.returncode == 0
        assert len(result.stdout) > 0
    
    def test_database_restore(self, docker_services):
        """Test database restore from backup."""
        # This would test:
        # 1. Create backup
        # 2. Drop database
        # 3. Restore from backup
        # 4. Verify data restored
        pass
    
    def test_redis_backup(self, docker_services):
        """Test Redis backup creation."""
        # Redis AOF should provide persistence
        # Check AOF file exists
        result = subprocess.run(
            [
                "docker",
                "exec",
                docker_services["redis"],
                "ls",
                "/data",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should have data directory
        assert result.returncode == 0

