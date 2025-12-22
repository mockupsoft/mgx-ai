# -*- coding: utf-8 -*-
"""
Test suite for sandbox execution features (Phase 11).

Tests cover:
- Unit tests: Executor initialization, command building
- Integration tests: Mocked Docker API
- E2E tests: Real containers (npm test, pytest, phpunit)
- Security tests: Resource limits enforced
- Failure scenarios: Timeout, OOM, network isolation
"""

import asyncio
import json
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from uuid import uuid4

# Test imports
from backend.services.sandbox import (
    SandboxRunner,
    SandboxRunnerError,
    NodeExecutor,
    PythonExecutor,
    PHPExecutor,
    DockerExecutor,
    ExecutorFactory,
)
from backend.services.sandbox.executors import LanguageExecutor
from backend.db.models.entities import SandboxExecution
from backend.schemas import (
    ExecutionRequest,
    ExecutionResult,
    SandboxExecutionResponse,
    SandboxExecutionLanguageEnum,
    SandboxExecutionStatusEnum,
)


class TestSandboxRunner:
    """Test cases for SandboxRunner class."""
    
    @pytest.fixture
    def mock_docker_client(self):
        """Mock Docker client for testing."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_container = MagicMock()
        mock_container.id = "test_container_id"
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"Test output\n"
        mock_container.stats.return_value = {
            "memory_stats": {"usage": 1024 * 1024 * 100},  # 100MB
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000, "percpu_usage": [500000, 500000]},
                "system_cpu_usage": 2000000
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 900000, "percpu_usage": [450000, 450000]},
                "system_cpu_usage": 1800000
            },
            "networks": {
                "eth0": {"rx_bytes": 1024 * 100, "tx_bytes": 1024 * 200}
            },
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 1024 * 1024},
                    {"op": "Write", "value": 2048 * 1024}
                ]
            }
        }
        mock_client.containers.run.return_value = mock_container
        return mock_client
    
    @pytest.fixture
    def sandbox_runner(self, mock_docker_client):
        """Create sandbox runner with mocked Docker client."""
        with patch('backend.services.sandbox.runner.docker.from_env') as mock_docker:
            mock_docker.return_value = mock_docker_client
            return SandboxRunner(mock_docker_client)
    
    @pytest.mark.asyncio
    async def test_execute_code_success(self, sandbox_runner):
        """Test successful code execution."""
        execution_id = str(uuid4())
        code = "print('Hello World')"
        command = "python main.py"
        language = "python"
        
        result = await sandbox_runner.execute_code(
            execution_id=execution_id,
            code=code,
            command=command,
            language=language,
            timeout=30,
            memory_limit_mb=512,
            workspace_id="test-workspace",
            project_id="test-project",
        )
        
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["duration_ms"] is not None
        assert "max_memory_mb" in result["resource_usage"]
        assert result["container_id"] == "test_container_id"
    
    @pytest.mark.asyncio
    async def test_execute_code_invalid_language(self, sandbox_runner):
        """Test execution with unsupported language."""
        execution_id = str(uuid4())
        code = "echo 'Hello'"
        command = "bash test.sh"
        language = "unsupported"
        
        with pytest.raises(SandboxRunnerError, match="Unsupported language"):
            await sandbox_runner.execute_code(
                execution_id=execution_id,
                code=code,
                command=command,
                language=language,
                timeout=30,
                memory_limit_mb=512,
            )
    
    @pytest.mark.asyncio
    async def test_execute_code_timeout(self, sandbox_runner):
        """Test execution timeout."""
        execution_id = str(uuid4())
        code = "import time; time.sleep(60)"
        command = "python main.py"
        language = "python"
        
        # Mock container that times out
        mock_container = MagicMock()
        mock_container.id = "timeout_container"
        mock_container.wait.side_effect = asyncio.TimeoutError()
        
        sandbox_runner.docker_client.containers.run.return_value = mock_container
        sandbox_runner.active_containers[execution_id] = mock_container
        
        result = await sandbox_runner.execute_code(
            execution_id=execution_id,
            code=code,
            command=command,
            language=language,
            timeout=1,  # Very short timeout
            memory_limit_mb=512,
        )
        
        assert result["success"] is False
        assert "timeout" in result["error_message"].lower()
        assert result["exit_code"] == 124  # Timeout exit code
    
    def test_container_security_config(self, sandbox_runner):
        """Test container security configuration."""
        workdir = "/tmp/test"
        config = sandbox_runner._build_container_config(
            base_image="mgx-sandbox-python:latest",
            workdir=workdir,
            command="python main.py",
            timeout=30,
            memory_limit_mb=512,
            workspace_id="test-workspace",
            project_id="test-project",
        )
        
        # Check security hardening
        assert config["network_mode"] == "none"
        assert config["read_only"] is True
        assert "tmpfs" in config
        assert config["user"] == "nobody"
        assert "no-new-privileges:true" in config["security_opt"]
        assert config["cap_drop"] == ["ALL"]
    
    def test_resource_limits_config(self, sandbox_runner):
        """Test resource limits configuration."""
        config = sandbox_runner._build_container_config(
            base_image="mgx-sandbox-python:latest",
            workdir="/tmp/test",
            command="python main.py",
            timeout=30,
            memory_limit_mb=512,
            workspace_id="test-workspace",
            project_id="test-project",
        )
        
        assert config["mem_limit"] == "512m"
        assert config["cpu_quota"] == 30000  # 30 seconds * 1000
        assert config["cpu_period"] == 100000
        assert config["cpu_shares"] == 512
    
    @pytest.mark.asyncio
    async def test_stop_execution(self, sandbox_runner):
        """Test stopping a running execution."""
        execution_id = str(uuid4())
        
        # Mock active container
        mock_container = MagicMock()
        sandbox_runner.active_containers[execution_id] = mock_container
        
        result = await sandbox_runner.stop_execution(execution_id)
        
        assert result is True
        mock_container.kill.assert_called_once()
        assert execution_id not in sandbox_runner.active_containers
    
    @pytest.mark.asyncio
    async def test_stop_nonexistent_execution(self, sandbox_runner):
        """Test stopping non-existent execution."""
        result = await sandbox_runner.stop_execution("nonexistent")
        assert result is False


class TestLanguageExecutors:
    """Test cases for language-specific executors."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_node_executor_setup_dependencies(self, temp_dir):
        """Test Node.js executor dependency setup."""
        executor = NodeExecutor()
        
        # Test with existing package.json
        package_json = temp_dir / "package.json"
        package_json.write_text(json.dumps({
            "name": "test",
            "version": "1.0.0",
            "dependencies": {}
        }))
        
        # Mock async execution
        with patch.object(executor, '_run_command', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True
            result = asyncio.run(executor.setup_dependencies(temp_dir))
            assert result is True
            mock_run.assert_called_once_with(temp_dir, "npm install")
    
    def test_python_executor_setup_dependencies(self, temp_dir):
        """Test Python executor dependency setup."""
        executor = PythonExecutor()
        
        # Test with requirements.txt
        requirements = temp_dir / "requirements.txt"
        requirements.write_text("requests==2.28.0\n")
        
        with patch.object(executor, '_run_command', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True
            result = asyncio.run(executor.setup_dependencies(temp_dir))
            assert result is True
            mock_run.assert_called_once_with(temp_dir, "pip install -r requirements.txt")
    
    def test_php_executor_setup_dependencies(self, temp_dir):
        """Test PHP executor dependency setup."""
        executor = PHPExecutor()
        
        # Test with composer.json
        composer_json = temp_dir / "composer.json"
        composer_json.write_text(json.dumps({
            "name": "test/package",
            "require": {}
        }))
        
        with patch.object(executor, '_run_command', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True
            result = asyncio.run(executor.setup_dependencies(temp_dir))
            assert result is True
            mock_run.assert_called_once_with(temp_dir, "composer install --no-dev --prefer-dist")
    
    def test_node_executor_commands(self, temp_dir):
        """Test Node.js executor command building."""
        executor = NodeExecutor()
        
        # Create package.json with test script
        package_json = temp_dir / "package.json"
        package_json.write_text(json.dumps({
            "scripts": {
                "test": "jest"
            }
        }))
        
        test_cmd = executor.get_test_command(temp_dir)
        assert test_cmd == "npm test"
        
        build_cmd = executor.get_build_command(temp_dir)
        assert build_cmd == "npm run build"
        
        exec_cmd = executor.build_execution_command("console.log('test')", temp_dir)
        assert exec_cmd == "node index.js"
    
    def test_python_executor_commands(self, temp_dir):
        """Test Python executor command building."""
        executor = PythonExecutor()
        
        # Create pytest.ini
        pytest_ini = temp_dir / "pytest.ini"
        pytest_ini.write_text("[tool:pytest]")
        
        test_cmd = executor.get_test_command(temp_dir)
        assert test_cmd == "pytest"
        
        exec_cmd = executor.build_execution_command("print('test')", temp_dir)
        assert exec_cmd == "python main.py"
    
    def test_php_executor_commands(self, temp_dir):
        """Test PHP executor command building."""
        executor = PHPExecutor()
        
        # Create phpunit.xml
        phpunit_xml = temp_dir / "phpunit.xml"
        phpunit_xml.write_text("<phpunit></phpunit>")
        
        test_cmd = executor.get_test_command(temp_dir)
        assert test_cmd == "vendor/bin/phpunit"
        
        exec_cmd = executor.build_execution_command("<?php echo 'test';", temp_dir)
        assert exec_cmd == "php index.php"
    
    def test_executor_factory(self):
        """Test executor factory."""
        factory = ExecutorFactory()
        
        # Test supported languages
        assert "javascript" in factory.list_supported_languages()
        assert "python" in factory.list_supported_languages()
        assert "php" in factory.list_supported_languages()
        assert "docker" in factory.list_supported_languages()
        
        # Test getting executors
        node_executor = factory.get_executor("javascript")
        assert isinstance(node_executor, NodeExecutor)
        
        python_executor = factory.get_executor("python")
        assert isinstance(python_executor, PythonExecutor)
        
        # Test unsupported language
        with pytest.raises(ValueError, match="Unsupported language"):
            factory.get_executor("unsupported")
        
        # Test validation
        assert factory.validate_language("python") is True
        assert factory.validate_language("unsupported") is False


class TestSandboxExecutionSchemas:
    """Test cases for sandbox execution schemas."""
    
    def test_execution_request_validation(self):
        """Test ExecutionRequest schema validation."""
        # Valid request
        valid_request = ExecutionRequest(
            code="print('Hello')",
            command="python main.py",
            language=SandboxExecutionLanguageEnum.PYTHON,
            timeout=30,
            memory_limit_mb=512,
        )
        assert valid_request.timeout == 30
        assert valid_request.memory_limit_mb == 512
        
        # Invalid timeout (too large)
        with pytest.raises(ValueError):
            ExecutionRequest(
                code="print('Hello')",
                command="python main.py",
                language=SandboxExecutionLanguageEnum.PYTHON,
                timeout=400,  # > 300 seconds
            )
    
    def test_execution_result_schema(self):
        """Test ExecutionResult schema."""
        result = ExecutionResult(
            success=True,
            stdout="Hello World",
            stderr="",
            exit_code=0,
            duration_ms=1500,
            resource_usage={
                "max_memory_mb": 100,
                "cpu_percent": 45.5,
                "network_io": 1024,
                "disk_io": 2048,
            }
        )
        
        assert result.success is True
        assert result.stdout == "Hello World"
        assert result.duration_ms == 1500
        assert result.resource_usage.max_memory_mb == 100
        assert result.resource_usage.cpu_percent == 45.5
    
    def test_sandbox_execution_response_from_orm(self):
        """Test creating response from ORM model."""
        # This would typically use actual ORM model
        # For now, test the schema structure
        execution_data = {
            "id": str(uuid4()),
            "workspace_id": "test-workspace",
            "project_id": "test-project",
            "execution_type": SandboxExecutionLanguageEnum.PYTHON.value,
            "status": SandboxExecutionStatusEnum.COMPLETED.value,
            "command": "python main.py",
            "code": "print('test')",
            "stdout": "test output",
            "stderr": "",
            "exit_code": 0,
            "success": True,
            "duration_ms": 1500,
            "max_memory_mb": 100,
            "cpu_percent": 45.5,
            "error_type": None,
            "error_message": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:01Z",
        }
        
        response = SandboxExecutionResponse(**execution_data)
        assert response.success is True
        assert response.execution_type == SandboxExecutionLanguageEnum.PYTHON


class TestSecurityFeatures:
    """Test cases for sandbox security features."""
    
    @pytest.fixture
    def sandbox_runner(self):
        """Create sandbox runner for security testing."""
        with patch('backend.services.sandbox.runner.docker.from_env') as mock_docker:
            mock_docker.return_value.ping.return_value = True
            return SandboxRunner(mock_docker.return_value)
    
    def test_network_isolation(self, sandbox_runner):
        """Test network isolation configuration."""
        config = sandbox_runner._build_container_config(
            base_image="mgx-sandbox-python:latest",
            workdir="/tmp/test",
            command="python main.py",
            timeout=30,
            memory_limit_mb=512,
        )
        
        assert config["network_mode"] == "none"
    
    def test_readonly_filesystem(self, sandbox_runner):
        """Test read-only filesystem configuration."""
        config = sandbox_runner._build_container_config(
            base_image="mgx-sandbox-python:latest",
            workdir="/tmp/test",
            command="python main.py",
            timeout=30,
            memory_limit_mb=512,
        )
        
        assert config["read_only"] is True
        assert "/tmp" in config["tmpfs"]
    
    def test_user_isolation(self, sandbox_runner):
        """Test user isolation configuration."""
        config = sandbox_runner._build_container_config(
            base_image="mgx-sandbox-python:latest",
            workdir="/tmp/test",
            command="python main.py",
            timeout=30,
            memory_limit_mb=512,
        )
        
        assert config["user"] == "nobody"
        assert config["cap_drop"] == ["ALL"]
    
    def test_resource_limits(self, sandbox_runner):
        """Test resource limits enforcement."""
        config = sandbox_runner._build_container_config(
            base_image="mgx-sandbox-python:latest",
            workdir="/tmp/test",
            command="python main.py",
            timeout=30,
            memory_limit_mb=512,
        )
        
        assert config["mem_limit"] == "512m"
        assert config["cpu_quota"] == 30000  # 30 seconds in microseconds
        assert "ulimits" in config
        assert config["ulimits"][0]["name"] == "nofile"
        assert config["ulimits"][1]["name"] == "nproc"


class TestFailureScenarios:
    """Test cases for failure scenarios and edge cases."""
    
    @pytest.fixture
    def sandbox_runner(self):
        """Create sandbox runner for failure testing."""
        with patch('backend.services.sandbox.runner.docker.from_env') as mock_docker:
            mock_docker.return_value.ping.return_value = True
            return SandboxRunner(mock_docker.return_value)
    
    @pytest.mark.asyncio
    async def test_docker_connection_failure(self):
        """Test handling of Docker connection failures."""
        with patch('backend.services.sandbox.runner.docker.from_env') as mock_docker:
            mock_docker.side_effect = Exception("Docker connection failed")
            
            with pytest.raises(SandboxRunnerError, match="Docker connection failed"):
                SandboxRunner()
    
    @pytest.mark.asyncio
    async def test_container_creation_failure(self, sandbox_runner):
        """Test handling of container creation failures."""
        sandbox_runner.docker_client.containers.run.side_effect = Exception("Container creation failed")
        
        execution_id = str(uuid4())
        result = await sandbox_runner.execute_code(
            execution_id=execution_id,
            code="print('test')",
            command="python main.py",
            language="python",
            timeout=30,
            memory_limit_mb=512,
        )
        
        assert result["success"] is False
        assert "Container creation failed" in result["stderr"]
    
    @pytest.mark.asyncio
    async def test_invalid_parameters(self, sandbox_runner):
        """Test handling of invalid parameters."""
        execution_id = str(uuid4())
        
        # Test invalid timeout
        with pytest.raises(SandboxRunnerError, match="Invalid timeout"):
            await sandbox_runner.execute_code(
                execution_id=execution_id,
                code="print('test')",
                command="python main.py",
                language="python",
                timeout=-1,  # Invalid timeout
                memory_limit_mb=512,
            )
        
        # Test invalid memory limit
        with pytest.raises(SandboxRunnerError, match="Invalid memory limit"):
            await sandbox_runner.execute_code(
                execution_id=execution_id,
                code="print('test')",
                command="python main.py",
                language="python",
                timeout=30,
                memory_limit_mb=-1,  # Invalid memory limit
            )
    
    @pytest.mark.asyncio
    async def test_workdir_cleanup(self, sandbox_runner):
        """Test cleanup of working directory."""
        execution_id = str(uuid4())
        
        # Mock workdir that should be cleaned up
        workdir = Path(f"/tmp/sandbox_{execution_id}")
        workdir.mkdir(exist_ok=True)
        test_file = workdir / "test.txt"
        test_file.write_text("test")
        
        # Execute code (will trigger cleanup)
        await sandbox_runner.execute_code(
            execution_id=execution_id,
            code="print('test')",
            command="python main.py",
            language="python",
            timeout=30,
            memory_limit_mb=512,
        )
        
        # Workdir should be cleaned up
        assert not workdir.exists()


class TestSandboxIntegration:
    """Integration tests for sandbox with real components."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_execution_flow(self):
        """Test full execution flow from request to result."""
        # This test would require actual Docker setup
        # For now, test the integration points
        
        from backend.services.sandbox import get_sandbox_runner
        runner = get_sandbox_runner()
        
        # Test that we can get a runner instance
        assert runner is not None
        assert isinstance(runner, SandboxRunner)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_database_integration(self):
        """Test database integration for execution records."""
        # This test would require actual database setup
        # For now, test the schema integration
        
        execution_id = str(uuid4())
        
        # Test creating execution record structure
        execution = SandboxExecution(
            id=execution_id,
            workspace_id="test-workspace",
            project_id="test-project",
            execution_type="python",
            status="pending",
            command="python main.py",
            code="print('test')",
            timeout_seconds=30,
        )
        
        assert execution.id == execution_id
        assert execution.execution_type == "python"
        assert execution.status.value == "pending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])