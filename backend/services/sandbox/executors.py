# -*- coding: utf-8 -*-
"""
Language-specific executors for sandboxed code execution.

Provides executors for different programming languages with specialized
command building, dependency management, and execution strategies.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LanguageExecutor(ABC):
    """Abstract base class for language-specific executors."""
    
    @abstractmethod
    async def setup_dependencies(self, workdir: Path) -> bool:
        """
        Setup dependencies for the execution environment.
        
        Args:
            workdir: Working directory path
        
        Returns:
            True if setup successful, False otherwise
        """
        pass
    
    @abstractmethod
    def build_execution_command(self, code: str, workdir: Path) -> str:
        """
        Build the execution command for the given code.
        
        Args:
            code: Source code to execute
            workdir: Working directory path
        
        Returns:
            Execution command string
        """
        pass
    
    @abstractmethod
    def get_test_command(self, workdir: Path) -> Optional[str]:
        """
        Get the appropriate test command for the language.
        
        Args:
            workdir: Working directory path
        
        Returns:
            Test command string, or None if no standard test command
        """
        pass
    
    @abstractmethod
    def get_build_command(self, workdir: Path) -> Optional[str]:
        """
        Get the appropriate build command for the language.
        
        Args:
            workdir: Working directory path
        
        Returns:
            Build command string, or None if no standard build command
        """
        pass
    
    @abstractmethod
    def validate_environment(self) -> bool:
        """
        Validate that the execution environment is properly configured.
        
        Returns:
            True if environment is valid, False otherwise
        """
        pass


class NodeExecutor(LanguageExecutor):
    """Executor for Node.js/JavaScript code."""
    
    SUPPORTED_PACKAGE_MANAGERS = ["npm", "yarn", "pnpm"]
    DEFAULT_TEST_COMMANDS = ["npm test", "yarn test", "pnpm test"]
    DEFAULT_BUILD_COMMANDS = ["npm run build", "yarn build", "pnpm build"]
    
    async def setup_dependencies(self, workdir: Path) -> bool:
        """Setup Node.js dependencies."""
        try:
            # Check for package.json
            package_json = workdir / "package.json"
            
            if package_json.exists():
                # Install dependencies based on package manager availability
                if self._command_exists("pnpm"):
                    await self._run_command(workdir, "pnpm install")
                elif self._command_exists("yarn"):
                    await self._run_command(workdir, "yarn install")
                else:
                    await self._run_command(workdir, "npm install")
                
                return True
            else:
                # Create minimal package.json if not exists
                package_data = {
                    "name": "sandbox-node-project",
                    "version": "1.0.0",
                    "description": "Sandbox execution",
                    "main": "index.js",
                    "scripts": {
                        "test": "node test.js"
                    }
                }
                
                import json
                with open(package_json, 'w') as f:
                    json.dump(package_data, f, indent=2)
                
                logger.info("Created minimal package.json")
                return True
                
        except Exception as e:
            logger.error(f"Failed to setup Node.js dependencies: {e}")
            return False
    
    def build_execution_command(self, code: str, workdir: Path) -> str:
        """Build Node.js execution command."""
        return "node index.js"
    
    def get_test_command(self, workdir: Path) -> Optional[str]:
        """Get Node.js test command."""
        package_json = workdir / "package.json"
        
        if package_json.exists():
            try:
                import json
                with open(package_json) as f:
                    data = json.load(f)
                    
                scripts = data.get("scripts", {})
                
                # Check for specific test scripts
                if "test" in scripts:
                    test_script = scripts["test"]
                    if "jest" in test_script:
                        return "npm test -- --coverage"
                    else:
                        return "npm test"
                
                # Check for test framework in devDependencies
                dev_deps = data.get("devDependencies", {})
                if "jest" in dev_deps:
                    return "npm test"
                elif "mocha" in dev_deps:
                    return "npx mocha"
                elif "jest" in dev_deps:
                    return "npx jest"
                    
            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")
        
        return None
    
    def get_build_command(self, workdir: Path) -> Optional[str]:
        """Get Node.js build command."""
        package_json = workdir / "package.json"
        
        if package_json.exists():
            try:
                import json
                with open(package_json) as f:
                    data = json.load(f)
                    
                scripts = data.get("scripts", {})
                
                # Check for build script
                if "build" in scripts:
                    return scripts["build"]
                    
            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")
        
        return None
    
    def validate_environment(self) -> bool:
        """Validate Node.js environment."""
        return self._command_exists("node")
    
    def _command_exists(self, command: str) -> bool:
        """Check if command exists in PATH."""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    async def _run_command(self, workdir: Path, command: str) -> bool:
        """Run shell command in workdir."""
        try:
            import asyncio
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"Command '{command}' failed: {stderr.decode()}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to run command '{command}': {e}")
            return False


class PythonExecutor(LanguageExecutor):
    """Executor for Python code."""
    
    SUPPORTED_PACKAGE_MANAGERS = ["pip", "poetry", "pipenv"]
    
    async def setup_dependencies(self, workdir: Path) -> bool:
        """Setup Python dependencies."""
        try:
            # Check for dependency files
            dependency_files = [
                "requirements.txt",
                "pyproject.toml", 
                "Pipfile",
                "poetry.lock"
            ]
            
            found_files = [f for f in dependency_files if (workdir / f).exists()]
            
            if found_files:
                # Install based on available package manager
                if (workdir / "pyproject.toml").exists():
                    await self._run_command(workdir, "poetry install")
                elif (workdir / "Pipfile").exists():
                    await self._run_command(workdir, "pipenv install")
                else:
                    await self._run_command(workdir, "pip install -r requirements.txt")
                
                return True
            else:
                # Create minimal requirements.txt
                requirements = workdir / "requirements.txt"
                requirements.write_text("# Sandbox execution requirements\n")
                await self._run_command(workdir, "pip install -r requirements.txt")
                
                logger.info("Created minimal requirements.txt")
                return True
                
        except Exception as e:
            logger.error(f"Failed to setup Python dependencies: {e}")
            return False
    
    def build_execution_command(self, code: str, workdir: Path) -> str:
        """Build Python execution command."""
        return "python main.py"
    
    def get_test_command(self, workdir: Path) -> Optional[str]:
        """Get Python test command."""
        # Check for common test files
        test_files = ["test_*.py", "*_test.py", "tests/", "test/"]
        
        # Check for pytest configuration
        if (workdir / "pytest.ini").exists() or (workdir / "pyproject.toml").exists():
            return "pytest"
        
        # Check for unittest discovery
        if any((workdir / f.replace("*", "test")).exists() or 
               (workdir / f.replace("*", "_test")).exists() 
               for f in test_files[:2]):
            return "python -m unittest discover"
        
        return None
    
    def get_build_command(self, workdir: Path) -> Optional[str]:
        """Get Python build command."""
        # Python typically doesn't need explicit build commands
        # but we can check for setup.py or pyproject.toml build scripts
        
        if (workdir / "pyproject.toml").exists():
            try:
                import toml
                with open(workdir / "pyproject.toml") as f:
                    data = toml.load(f)
                
                # Check for build scripts in pyproject.toml
                if "tool" in data and "poetry" in data["tool"]:
                    return "poetry build"
                    
            except Exception as e:
                logger.warning(f"Failed to parse pyproject.toml: {e}")
        
        return None
    
    def validate_environment(self) -> bool:
        """Validate Python environment."""
        try:
            subprocess.run(["python", "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _command_exists(self, command: str) -> bool:
        """Check if command exists in PATH."""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    async def _run_command(self, workdir: Path, command: str) -> bool:
        """Run shell command in workdir."""
        try:
            import asyncio
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"Command '{command}' failed: {stderr.decode()}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to run command '{command}': {e}")
            return False


class PHPExecutor(LanguageExecutor):
    """Executor for PHP code."""
    
    async def setup_dependencies(self, workdir: Path) -> bool:
        """Setup PHP dependencies."""
        try:
            # Check for composer.json
            composer_json = workdir / "composer.json"
            
            if composer_json.exists():
                # Install dependencies via composer
                await self._run_command(workdir, "composer install --no-dev --prefer-dist")
                return True
            else:
                # Create minimal composer.json
                composer_data = {
                    "name": "sandbox/php-project",
                    "description": "Sandbox execution",
                    "type": "project",
                    "require": {},
                    "require-dev": {},
                    "autoload": {
                        "psr-4": {
                            "App\\": "src/"
                        }
                    }
                }
                
                import json
                with open(composer_json, 'w') as f:
                    json.dump(composer_data, f, indent=2)
                
                await self._run_command(workdir, "composer install")
                logger.info("Created minimal composer.json")
                return True
                
        except Exception as e:
            logger.error(f"Failed to setup PHP dependencies: {e}")
            return False
    
    def build_execution_command(self, code: str, workdir: Path) -> str:
        """Build PHP execution command."""
        return "php index.php"
    
    def get_test_command(self, workdir: Path) -> Optional[str]:
        """Get PHP test command."""
        # Check for phpunit configuration
        if (workdir / "phpunit.xml").exists() or (workdir / "phpunit.xml.dist").exists():
            return "vendor/bin/phpunit"
        
        # Check for composer test script
        composer_json = workdir / "composer.json"
        if composer_json.exists():
            try:
                import json
                with open(composer_json) as f:
                    data = json.load(f)
                    
                scripts = data.get("scripts", {})
                if "test" in scripts:
                    return f"composer run test"
                    
            except Exception as e:
                logger.warning(f"Failed to parse composer.json: {e}")
        
        return None
    
    def get_build_command(self, workdir: Path) -> Optional[str]:
        """Get PHP build command."""
        # Check for composer build script
        composer_json = workdir / "composer.json"
        if composer_json.exists():
            try:
                import json
                with open(composer_json) as f:
                    data = json.load(f)
                    
                scripts = data.get("scripts", {})
                if "build" in scripts:
                    return f"composer run build"
                    
            except Exception as e:
                logger.warning(f"Failed to parse composer.json: {e}")
        
        return None
    
    def validate_environment(self) -> bool:
        """Validate PHP environment."""
        try:
            subprocess.run(["php", "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _command_exists(self, command: str) -> bool:
        """Check if command exists in PATH."""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    async def _run_command(self, workdir: Path, command: str) -> bool:
        """Run shell command in workdir."""
        try:
            import asyncio
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"Command '{command}' failed: {stderr.decode()}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to run command '{command}': {e}")
            return False


class DockerExecutor(LanguageExecutor):
    """Executor for Docker-related operations."""
    
    async def setup_dependencies(self, workdir: Path) -> bool:
        """Setup Docker execution environment."""
        # Docker execution doesn't require additional setup
        # Docker daemon is accessed via Docker API
        return True
    
    def build_execution_command(self, code: str, workdir: Path) -> str:
        """Build Docker execution command."""
        # For Docker, we expect a Dockerfile to be present
        return "docker build -t sandbox-app . && docker run --rm sandbox-app"
    
    def get_test_command(self, workdir: Path) -> Optional[str]:
        """Get Docker test command."""
        # Docker testing would depend on the specific Docker setup
        dockerfile = workdir / "Dockerfile"
        if dockerfile.exists():
            return "docker build -t sandbox-app . && docker run --rm sandbox-app npm test"
        
        return None
    
    def get_build_command(self, workdir: Path) -> Optional[str]:
        """Get Docker build command."""
        return "docker build -t sandbox-app ."
    
    def validate_environment(self) -> bool:
        """Validate Docker environment."""
        try:
            subprocess.run(["docker", "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


class ExecutorFactory:
    """Factory for creating language-specific executors."""
    
    _executors = {
        "javascript": NodeExecutor,
        "node": NodeExecutor,
        "js": NodeExecutor,
        "python": PythonExecutor,
        "py": PythonExecutor,
        "php": PHPExecutor,
        "docker": DockerExecutor,
    }
    
    def get_executor(self, language: str) -> LanguageExecutor:
        """
        Get executor for the specified language.
        
        Args:
            language: Programming language identifier
        
        Returns:
            Language-specific executor instance
        
        Raises:
            ValueError: If language is not supported
        """
        language = language.lower()
        
        if language not in self._executors:
            raise ValueError(f"Unsupported language: {language}")
        
        executor_class = self._executors[language]
        return executor_class()
    
    def list_supported_languages(self) -> List[str]:
        """Get list of supported programming languages."""
        return list(self._executors.keys())
    
    def validate_language(self, language: str) -> bool:
        """Validate if language is supported."""
        return language.lower() in self._executors