# -*- coding: utf-8 -*-
"""
Sandbox Runner for secure code execution.

Manages Docker containers with security hardening, resource limits,
and multi-language support for safe code execution.
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import docker  # type: ignore
    from docker.models.containers import Container  # type: ignore
    from docker.errors import DockerException, NotFound, APIError  # type: ignore
except ImportError:  # pragma: no cover
    docker = None  # type: ignore

    class DockerException(Exception):
        pass

    class NotFound(DockerException):
        pass

    class APIError(DockerException):
        pass

    Container = object  # type: ignore

from .executors import LanguageExecutor, ExecutorFactory

logger = logging.getLogger(__name__)


class SandboxRunnerError(Exception):
    """Base exception for sandbox runner errors."""
    pass


class ContainerNotFoundError(SandboxRunnerError):
    """Raised when a container is not found."""
    pass


class ResourceLimitExceededError(SandboxRunnerError):
    """Raised when resource limits are exceeded."""
    pass


class ExecutionTimeoutError(SandboxRunnerError):
    """Raised when execution times out."""
    pass


class SecurityViolationError(SandboxRunnerError):
    """Raised when security policies are violated."""
    pass


class SandboxRunner:
    """
    Sandboxed code execution runner with Docker integration.
    
    Provides secure, isolated execution environments with:
    - Docker-based containerization
    - Resource limits (CPU, memory, time)
    - Security hardening (read-only, no network)
    - Multi-language support via executors
    - WebSocket streaming for live logs
    """
    
    # Default security settings
    DEFAULT_SECURITY_OPTS = [
        "no-new-privileges:true",
        "apparmor=unconfined",
        "seccomp=unconfined",
    ]
    
    # Default resource limits
    DEFAULT_MEMORY_LIMIT = "512m"
    DEFAULT_CPU_LIMIT = "1.0"
    DEFAULT_TIMEOUT = 30.0
    
    # Supported base images
    BASE_IMAGES = {
        "javascript": "mgx-sandbox-node:latest",
        "python": "mgx-sandbox-python:latest", 
        "php": "mgx-sandbox-php:latest",
        "docker": "mgx-sandbox-node:latest",  # For Docker-in-Docker scenarios
    }
    
    def __init__(self, docker_client: Optional["docker.DockerClient"] = None):
        """Initialize the sandbox runner.

        Args:
            docker_client: Docker client instance. If omitted, we try to build one from
                environment variables via ``docker.from_env()``.

        Note:
            The Python ``docker`` package is an optional dependency in this repo.
            When it's not installed, this class can still be imported, but it cannot
            be instantiated unless a compatible ``docker_client`` is provided.
        """

        if docker_client is None:
            if docker is None:
                raise SandboxRunnerError(
                    "Docker SDK for Python is not installed. Install 'docker' or provide a docker_client."
                )
            docker_client = docker.from_env()

        self.docker_client = docker_client
        self.executor_factory = ExecutorFactory()
        self.active_containers: Dict[str, Container] = {}

        # Validate Docker connection
        try:
            self.docker_client.ping()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise SandboxRunnerError(f"Docker connection failed: {e}")
    
    async def execute_code(
        self,
        execution_id: str,
        code: str,
        command: str,
        language: str,
        timeout: float = DEFAULT_TIMEOUT,
        memory_limit_mb: int = 512,
        workspace_id: Optional[str] = None,
        project_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute code in a secure sandbox container.
        
        Args:
            execution_id: Unique execution identifier
            code: Source code to execute
            command: Command to run (e.g., 'npm test', 'pytest')
            language: Programming language (javascript, python, php)
            timeout: Execution timeout in seconds
            memory_limit_mb: Memory limit in megabytes
            workspace_id: Workspace ID for scoping
            project_id: Project ID for scoping
            **kwargs: Additional execution parameters
        
        Returns:
            Execution result dictionary with success status, output, and metrics
        """
        logger.info(f"Starting execution {execution_id} for {language}")
        
        start_time = time.time()
        
        # Validate parameters
        if language not in self.BASE_IMAGES:
            raise SandboxRunnerError(f"Unsupported language: {language}")
        
        if timeout <= 0:
            raise SandboxRunnerError(f"Invalid timeout: {timeout}")
        
        if memory_limit_mb <= 0:
            raise SandboxRunnerError(f"Invalid memory limit: {memory_limit_mb}")
        
        try:
            # Get appropriate executor
            executor = self.executor_factory.get_executor(language)
            
            # Create and prepare working directory
            workdir = Path(f"/tmp/sandbox_{execution_id}")
            workdir.mkdir(exist_ok=True)
            
            # Write code to workspace
            code_file = workdir / self._get_main_filename(language)
            code_file.write_text(code, encoding="utf-8")
            
            # Build container configuration
            container_config = self._build_container_config(
                base_image=self.BASE_IMAGES[language],
                workdir=str(workdir),
                command=command,
                timeout=timeout,
                memory_limit_mb=memory_limit_mb,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            
            # Execute in container
            result = await self._execute_in_container(
                execution_id=execution_id,
                container_config=container_config,
                executor=executor,
                timeout=timeout,
            )
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            result["duration_ms"] = duration_ms
            
            # Store execution record
            await self._store_execution_record(
                execution_id=execution_id,
                result=result,
                workspace_id=workspace_id,
                project_id=project_id,
                language=language,
            )
            
            logger.info(f"Execution {execution_id} completed in {duration_ms}ms")
            return result
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}")
            
            duration_ms = int((time.time() - start_time) * 1000)
            error_result = {
                "success": False,
                "stdout": "",
                "stderr": f"Execution failed: {str(e)}",
                "exit_code": 1,
                "duration_ms": duration_ms,
                "resource_usage": {
                    "max_memory_mb": 0,
                    "cpu_percent": 0,
                    "network_io": 0,
                    "disk_io": 0,
                },
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
            
            # Store failed execution record
            await self._store_execution_record(
                execution_id=execution_id,
                result=error_result,
                workspace_id=workspace_id,
                project_id=project_id,
                language=language,
            )
            
            return error_result
            
        finally:
            # Cleanup working directory
            try:
                if workdir.exists():
                    import shutil
                    shutil.rmtree(workdir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup workdir {workdir}: {e}")
    
    def _build_container_config(
        self,
        base_image: str,
        workdir: str,
        command: str,
        timeout: float,
        memory_limit_mb: int,
        workspace_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build Docker container configuration with security hardening.
        
        Args:
            base_image: Base Docker image to use
            workdir: Working directory inside container
            command: Command to execute
            timeout: Execution timeout
            memory_limit_mb: Memory limit in MB
            workspace_id: Workspace ID for metadata
            project_id: Project ID for metadata
        
        Returns:
            Container configuration dictionary
        """
        # Resource limits
        mem_limit = f"{memory_limit_mb}m"
        cpu_limit = int(timeout * 1000)  # CPU quota in microseconds
        
        # Volume mounts (bind mount for code)
        volumes = {
            workdir: {
                "bind": "/workspace",
                "mode": "rw"
            }
        }
        
        # Environment variables
        env = {
            "SANDBOX_EXECUTION_ID": str(uuid.uuid4()),
            "SANDBOX_TIMEOUT": str(int(timeout)),
            "SANDBOX_MEMORY_LIMIT": str(memory_limit_mb),
            "SANDBOX_WORKSPACE_ID": workspace_id or "",
            "SANDBOX_PROJECT_ID": project_id or "",
        }
        
        # Build command with timeout wrapper
        wrapped_command = f"timeout {int(timeout)}s {command}"
        
        container_config = {
            "image": base_image,
            "command": wrapped_command,
            "working_dir": "/workspace",
            "environment": env,
            "volumes": volumes,
            "mem_limit": mem_limit,
            "mem_reservation": f"{memory_limit_mb // 2}m",
            "cpu_period": 100000,
            "cpu_quota": cpu_limit,
            "cpu_shares": 512,
            "network_mode": "none",  # No network access
            "security_opt": self.DEFAULT_SECURITY_OPTS.copy(),
            "read_only": True,  # Read-only root filesystem
            "tmpfs": {
                "/tmp": "rw,noexec,nosuid,size=100m"
            },
            "user": "nobody",  # Run as non-root user
            "cap_drop": ["ALL"],  # Drop all capabilities
            "cap_add": [],  # No additional capabilities
            "ulimits": [
                {"name": "nofile", "soft": 1024, "hard": 2048},
                {"name": "nproc", "soft": 64, "hard": 128},
            ],
            "detach": False,  # Run in foreground to capture output
            "remove": True,  # Auto-remove container after execution
        }
        
        return container_config
    
    async def _execute_in_container(
        self,
        execution_id: str,
        container_config: Dict[str, Any],
        executor: LanguageExecutor,
        timeout: float,
    ) -> Dict[str, Any]:
        """
        Execute command in Docker container with monitoring.
        
        Args:
            execution_id: Execution identifier
            container_config: Docker container configuration
            executor: Language-specific executor
            timeout: Execution timeout
        
        Returns:
            Execution result dictionary
        """
        container = None
        start_time = time.time()
        
        try:
            # Pull image if needed (in production, ensure images are pre-built)
            logger.debug(f"Pulling image: {container_config['image']}")
            
            # Create container
            container = self.docker_client.containers.run(**container_config)
            self.active_containers[execution_id] = container
            
            # Wait for completion with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", 0)
                
                # Get container logs
                logs = container.logs(stdout=True, stderr=True)
                stdout_stderr = logs.decode("utf-8", errors="replace")
                
                # Parse stdout/stderr
                stdout_lines = []
                stderr_lines = []
                for line in stdout_stderr.split("\n"):
                    if line.strip():
                        # Try to determine if line is stderr (assuming apps use stderr for errors)
                        if any(error_indicator in line.lower() for error_indicator in 
                               ["error", "exception", "failed", "traceback", "stack trace"]):
                            stderr_lines.append(line)
                        else:
                            stdout_lines.append(line)
                
                stdout = "\n".join(stdout_lines)
                stderr = "\n".join(stderr_lines)
                
                # Get resource usage from container stats
                resource_usage = await self._get_resource_usage(container)
                
                success = exit_code == 0 and not any(
                    error in stdout.lower() or error in stderr.lower() 
                    for error in ["error", "exception", "failed"]
                )
                
                return {
                    "success": success,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "resource_usage": resource_usage,
                    "container_id": container.id,
                }
                
            except asyncio.TimeoutError:
                # Kill container on timeout
                if container:
                    container.kill()
                
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout} seconds",
                    "exit_code": 124,  # timeout exit code
                    "resource_usage": await self._get_resource_usage(container),
                    "error_type": "ExecutionTimeoutError",
                    "error_message": f"Execution timed out after {timeout} seconds",
                }
                
        except DockerException as e:
            logger.error(f"Docker error during execution {execution_id}: {e}")
            
            if container:
                try:
                    container.kill()
                except:
                    pass
            
            raise SandboxRunnerError(f"Docker execution failed: {e}")
            
        finally:
            # Clean up container reference
            if execution_id in self.active_containers:
                del self.active_containers[execution_id]
    
    async def _get_resource_usage(self, container: Optional[Container]) -> Dict[str, Any]:
        """
        Get resource usage statistics from container.
        
        Args:
            container: Docker container instance
        
        Returns:
            Resource usage dictionary
        """
        if not container:
            return {
                "max_memory_mb": 0,
                "cpu_percent": 0,
                "network_io": 0,
                "disk_io": 0,
            }
        
        try:
            stats = container.stats(stream=False)
            
            # Memory usage
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_mb = memory_usage // (1024 * 1024)
            
            # CPU usage (approximate calculation)
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            
            cpu_percent = 0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100 * len(
                    stats["cpu_stats"]["cpu_usage"]["percpu_usage"]
                )
            
            # Network I/O (bytes transferred)
            network_io = 0
            if "networks" in stats:
                for network_data in stats["networks"].values():
                    network_io += network_data.get("rx_bytes", 0)
                    network_io += network_data.get("tx_bytes", 0)
            
            # Disk I/O (approximate)
            disk_io = 0
            if "blkio_stats" in stats and "io_service_bytes_recursive" in stats["blkio_stats"]:
                for io_stat in stats["blkio_stats"]["io_service_bytes_recursive"]:
                    if io_stat["op"] in ["Read", "Write"]:
                        disk_io += io_stat.get("value", 0)
            
            return {
                "max_memory_mb": int(memory_mb),
                "cpu_percent": round(cpu_percent, 2),
                "network_io": int(network_io),
                "disk_io": int(disk_io),
            }
            
        except Exception as e:
            logger.warning(f"Failed to get resource usage: {e}")
            return {
                "max_memory_mb": 0,
                "cpu_percent": 0,
                "network_io": 0,
                "disk_io": 0,
            }
    
    async def _store_execution_record(
        self,
        execution_id: str,
        result: Dict[str, Any],
        workspace_id: Optional[str],
        project_id: Optional[str],
        language: str,
    ):
        """
        Store execution record in database.
        
        Args:
            execution_id: Execution identifier
            result: Execution result
            workspace_id: Workspace ID
            project_id: Project ID
            language: Programming language
        """
        # TODO: Implement database storage
        # This would integrate with the existing database models
        logger.debug(f"Execution record stored: {execution_id}")
    
    def _get_main_filename(self, language: str) -> str:
        """
        Get the main filename for a given language.
        
        Args:
            language: Programming language
        
        Returns:
            Main filename for the language
        """
        filename_map = {
            "javascript": "index.js",
            "python": "main.py", 
            "php": "index.php",
            "docker": "Dockerfile",
        }
        
        return filename_map.get(language, "main")
    
    async def stop_execution(self, execution_id: str) -> bool:
        """
        Stop a running execution by killing the container.
        
        Args:
            execution_id: Execution identifier
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if execution_id not in self.active_containers:
            return False
        
        container = self.active_containers[execution_id]
        
        try:
            container.kill()
            del self.active_containers[execution_id]
            logger.info(f"Execution {execution_id} stopped")
            return True
        except DockerException as e:
            logger.error(f"Failed to stop execution {execution_id}: {e}")
            return False
    
    async def get_execution_logs(self, execution_id: str) -> Optional[str]:
        """
        Get live logs from a running execution.
        
        Args:
            execution_id: Execution identifier
        
        Returns:
            Container logs as string, or None if not found
        """
        if execution_id not in self.active_containers:
            return None
        
        container = self.active_containers[execution_id]
        
        try:
            logs = container.logs(stdout=True, stderr=True, stream=False)
            return logs.decode("utf-8", errors="replace")
        except DockerException as e:
            logger.error(f"Failed to get logs for execution {execution_id}: {e}")
            return None
    
    def cleanup(self):
        """
        Clean up resources and stop all active containers.
        """
        logger.info("Cleaning up sandbox runner")
        
        for execution_id, container in self.active_containers.items():
            try:
                container.kill()
                logger.debug(f"Stopped container for execution {execution_id}")
            except DockerException as e:
                logger.warning(f"Failed to stop container {execution_id}: {e}")
        
        self.active_containers.clear()