# -*- coding: utf-8 -*-

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from backend.services.pipeline.utils import CommandResult, command_exists, run_command

logger = logging.getLogger(__name__)


class DockerBuilderError(RuntimeError):
    pass


@dataclass
class DockerBuildResult:
    image_ref: str
    image_id: Optional[str]
    digest: Optional[str]
    logs: str
    success: bool


@dataclass
class SecurityScanResult:
    tool: str
    image_ref: str
    vulnerabilities: int
    score: str
    report_path: Optional[str]
    skipped: bool
    raw: Optional[Dict[str, Any]] = None


@dataclass
class PushResult:
    registry: str
    image_ref: str
    digest: Optional[str]
    success: bool
    logs: str


class DockerBuilder:
    """Build/scan/push Docker images for a generated project."""

    def __init__(self, *, cache_root: Path = Path("/tmp/mgx-docker-cache")):
        self.cache_root = cache_root

    async def build_image(
        self,
        execution_id: UUID,
        project_path: str,
        dockerfile_path: str,
        tag: str = "latest",
        image_name: Optional[str] = None,
        build_args: Optional[Dict[str, str]] = None,
    ) -> DockerBuildResult:
        if not command_exists("docker"):
            return DockerBuildResult(
                image_ref="",
                image_id=None,
                digest=None,
                logs="docker CLI not found in PATH",
                success=False,
            )

        project_dir = Path(project_path)
        dockerfile = Path(dockerfile_path)
        if not dockerfile.is_absolute():
            dockerfile = project_dir / dockerfile

        if image_name is None:
            image_name = project_dir.name

        image_ref = f"{image_name}:{tag}"

        cache_dir = self.cache_root / str(execution_id)
        cache_dir.mkdir(parents=True, exist_ok=True)

        args = [
            "docker",
            "buildx",
            "build",
            "--load",
            "--progress=plain",
            "--file",
            str(dockerfile),
            "--tag",
            image_ref,
            "--cache-from",
            f"type=local,src={cache_dir}",
            "--cache-to",
            f"type=local,dest={cache_dir},mode=max",
            str(project_dir),
        ]

        build_args = build_args or {}
        for k, v in build_args.items():
            args.insert(-1, "--build-arg")
            args.insert(-1, f"{k}={v}")

        env = os.environ.copy()
        env.setdefault("DOCKER_BUILDKIT", "1")

        result = await run_command(args, cwd=project_dir, env=env)
        logs = (result.stdout + "\n" + result.stderr).strip()

        if result.returncode != 0:
            return DockerBuildResult(
                image_ref=image_ref,
                image_id=None,
                digest=None,
                logs=logs,
                success=False,
            )

        image_id = await self._resolve_image_id(image_ref)
        digest = await self._resolve_digest(image_ref)

        return DockerBuildResult(
            image_ref=image_ref,
            image_id=image_id,
            digest=digest,
            logs=logs,
            success=True,
        )

    async def scan_image(
        self,
        image_ref: str,
        *,
        output_dir: Optional[Path] = None,
    ) -> SecurityScanResult:
        if not command_exists("trivy"):
            return SecurityScanResult(
                tool="trivy",
                image_ref=image_ref,
                vulnerabilities=0,
                score="unknown",
                report_path=None,
                skipped=True,
                raw=None,
            )

        output_dir = output_dir or Path("/tmp")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"trivy_{image_ref.replace('/', '_').replace(':', '_')}.json"

        args = [
            "trivy",
            "image",
            "--quiet",
            "--format",
            "json",
            "--output",
            str(report_path),
            image_ref,
        ]

        result = await run_command(args)
        if result.returncode != 0:
            return SecurityScanResult(
                tool="trivy",
                image_ref=image_ref,
                vulnerabilities=0,
                score="unknown",
                report_path=str(report_path),
                skipped=False,
                raw={"error": result.stderr.strip() or result.stdout.strip()},
            )

        try:
            raw = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to parse trivy output: %s", e)
            raw = None

        vulns = 0
        if isinstance(raw, dict):
            for res in raw.get("Results", []) or []:
                vulns += len(res.get("Vulnerabilities", []) or [])

        score = "A" if vulns == 0 else ("B" if vulns < 10 else "C")

        return SecurityScanResult(
            tool="trivy",
            image_ref=image_ref,
            vulnerabilities=vulns,
            score=score,
            report_path=str(report_path),
            skipped=False,
            raw=raw,
        )

    async def push_image(self, image_ref: str, registry: str) -> PushResult:
        if not command_exists("docker"):
            return PushResult(
                registry=registry,
                image_ref=image_ref,
                digest=None,
                success=False,
                logs="docker CLI not found in PATH",
            )

        full_ref = self._with_registry(image_ref, registry)

        tag_result = await run_command(["docker", "tag", image_ref, full_ref])
        if tag_result.returncode != 0:
            logs = (tag_result.stdout + "\n" + tag_result.stderr).strip()
            return PushResult(
                registry=registry,
                image_ref=full_ref,
                digest=None,
                success=False,
                logs=logs,
            )

        push_result = await run_command(["docker", "push", full_ref])
        logs = (push_result.stdout + "\n" + push_result.stderr).strip()

        digest = await self._resolve_digest(full_ref)

        return PushResult(
            registry=registry,
            image_ref=full_ref,
            digest=digest,
            success=push_result.returncode == 0,
            logs=logs,
        )

    async def sign_image(self, image_ref: str) -> CommandResult:
        if not command_exists("cosign"):
            return CommandResult(returncode=127, stdout="", stderr="cosign not found")

        return await run_command(["cosign", "sign", "--yes", image_ref])

    async def _resolve_image_id(self, image_ref: str) -> Optional[str]:
        result = await run_command(["docker", "images", "--quiet", image_ref])
        if result.returncode != 0:
            return None
        image_id = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
        return image_id

    async def _resolve_digest(self, image_ref: str) -> Optional[str]:
        if not command_exists("docker"):
            return None
        result = await run_command([
            "docker",
            "inspect",
            "--format",
            "{{index .RepoDigests 0}}",
            image_ref,
        ])
        if result.returncode != 0:
            return None
        digest = result.stdout.strip() or None
        return digest

    def _with_registry(self, image_ref: str, registry: str) -> str:
        if not registry:
            return image_ref
        if "/" in image_ref and image_ref.split("/")[0].count(".") > 0:
            return image_ref
        return f"{registry.rstrip('/')}/{image_ref}"
