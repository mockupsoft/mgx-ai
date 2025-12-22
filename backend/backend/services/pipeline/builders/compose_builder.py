# -*- coding: utf-8 -*-

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from backend.services.pipeline.utils import command_exists, run_command

logger = logging.getLogger(__name__)


@dataclass
class ComposeBuildResult:
    file_path: str
    content: str
    validated: bool
    validation_output: Optional[str] = None


class ComposeBuilder:
    """Generate a production-ready docker-compose.yml for a project."""

    async def generate(
        self,
        *,
        project_path: str,
        project_name: str,
        image_ref: str,
        app_port: int = 3000,
        include_postgres: bool = True,
        include_redis: bool = True,
        env: Optional[Dict[str, str]] = None,
    ) -> ComposeBuildResult:
        project_dir = Path(project_path)
        target_dir = project_dir / "deploy" / "compose"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / "docker-compose.yml"

        env = env or {}

        services: Dict[str, Any] = {
            "app": {
                "image": image_ref,
                "ports": [f"{app_port}:{app_port}"],
                "environment": {
                    "PORT": str(app_port),
                    **env,
                },
                "healthcheck": {
                    "test": ["CMD", "sh", "-c", f"wget -qO- http://localhost:{app_port}/health || exit 1"],
                    "interval": "10s",
                    "timeout": "3s",
                    "retries": 10,
                },
                "restart": "unless-stopped",
                "logging": {
                    "driver": "json-file",
                    "options": {"max-size": "10m", "max-file": "3"},
                },
                "deploy": {
                    "resources": {
                        "limits": {"cpus": "1.0", "memory": "512M"},
                        "reservations": {"cpus": "0.25", "memory": "128M"},
                    }
                },
            }
        }

        volumes: Dict[str, Any] = {}

        if include_postgres:
            volumes["db_data"] = {}
            services["db"] = {
                "image": "postgres:15",
                "environment": {
                    "POSTGRES_USER": env.get("POSTGRES_USER", "postgres"),
                    "POSTGRES_PASSWORD": env.get("POSTGRES_PASSWORD", "postgres"),
                    "POSTGRES_DB": env.get("POSTGRES_DB", project_name),
                },
                "volumes": ["db_data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 10,
                },
                "restart": "unless-stopped",
            }
            services["app"]["depends_on"] = {"db": {"condition": "service_healthy"}}

        if include_redis:
            volumes["redis_data"] = {}
            services["cache"] = {
                "image": "redis:7",
                "command": ["redis-server", "--appendonly", "yes"],
                "volumes": ["redis_data:/data"],
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "10s",
                    "timeout": "3s",
                    "retries": 10,
                },
                "restart": "unless-stopped",
            }
            services["app"].setdefault("depends_on", {})
            services["app"]["depends_on"]["cache"] = {"condition": "service_healthy"}

        compose: Dict[str, Any] = {
            "name": project_name,
            "services": services,
            "volumes": volumes,
            "networks": {"default": {"name": f"{project_name}_net"}},
        }

        content = yaml.safe_dump(compose, sort_keys=False)
        file_path.write_text(content, encoding="utf-8")

        validated, output = await self._validate(file_path)

        return ComposeBuildResult(
            file_path=str(file_path),
            content=content,
            validated=validated,
            validation_output=output,
        )

    async def _validate(self, compose_file: Path) -> tuple[bool, Optional[str]]:
        if not command_exists("docker"):
            return False, "docker not available; compose validation skipped"

        # docker compose is preferred; fallback to docker-compose.
        if command_exists("docker"):
            result = await run_command(["docker", "compose", "-f", str(compose_file), "config"])
            if result.returncode == 0:
                return True, result.stdout.strip()
            if command_exists("docker-compose"):
                result = await run_command(["docker-compose", "-f", str(compose_file), "config"])
                return result.returncode == 0, (result.stdout + "\n" + result.stderr).strip()
            return False, (result.stdout + "\n" + result.stderr).strip()

        return False, "compose validation not available"
