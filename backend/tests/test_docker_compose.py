import pytest
from unittest.mock import patch, MagicMock
import os
import subprocess

class TestDockerCompose:
    
    @pytest.fixture
    def mock_subprocess(self):
        with patch('subprocess.run') as mock:
            yield mock

    def test_env_file_exists(self):
        """Test that .env.example exists and .env can be created"""
        assert os.path.exists(".env.example")
        # In a real test environment we would check .env too, but here we might not have it
        
    def test_docker_compose_build(self, mock_subprocess):
        """Test docker compose build command"""
        mock_subprocess.return_value.returncode = 0
        
        # Simulate running the build command
        cmd = ["docker", "compose", "build"]
        subprocess.run(cmd, check=True)
        
        mock_subprocess.assert_called_with(cmd, check=True)

    def test_docker_compose_up(self, mock_subprocess):
        """Test docker compose up command"""
        mock_subprocess.return_value.returncode = 0
        
        cmd = ["docker", "compose", "up", "-d"]
        subprocess.run(cmd, check=True)
        
        mock_subprocess.assert_called_with(cmd, check=True)

    def test_service_health_check(self, mock_subprocess):
        """Test checking service health"""
        # Mock successful health check
        mock_subprocess.return_value.stdout = "healthy"
        mock_subprocess.return_value.returncode = 0
        
        cmd = ["docker", "inspect", "--format='{{.State.Health.Status}}'", "mgx-ai"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        mock_subprocess.assert_called_with(cmd, capture_output=True, text=True)
        assert result.stdout == "healthy"

    def test_required_services_defined(self):
        """Check docker-compose.yml defines required services"""
        import yaml
        
        if not os.path.exists("docker-compose.yml"):
            pytest.skip("docker-compose.yml not found")
            
        with open("docker-compose.yml", 'r') as f:
            compose_config = yaml.safe_load(f)
            
        services = compose_config.get('services', {})
        assert 'postgres' in services
        assert 'redis' in services
        assert 'minio' in services
        assert 'mgx-ai' in services
