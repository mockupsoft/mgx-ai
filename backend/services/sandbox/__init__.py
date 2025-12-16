# -*- coding: utf-8 -*-
"""
Sandboxed Code Runner for secure code execution.

Provides safe, isolated execution environments for multiple programming languages
with Docker-based containerization and resource limits.
"""

from .runner import SandboxRunner, SandboxRunnerError
from .executors import NodeExecutor, PythonExecutor, PHPExecutor, DockerExecutor

# Global sandbox runner instance
_sandbox_runner_instance = None


def get_sandbox_runner() -> SandboxRunner:
    """Get global sandbox runner instance."""
    global _sandbox_runner_instance
    if _sandbox_runner_instance is None:
        _sandbox_runner_instance = SandboxRunner()
    return _sandbox_runner_instance


__all__ = [
    "SandboxRunner",
    "SandboxRunnerError", 
    "NodeExecutor",
    "PythonExecutor", 
    "PHPExecutor",
    "DockerExecutor",
    "get_sandbox_runner",
]