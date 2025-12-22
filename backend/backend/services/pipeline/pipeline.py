# -*- coding: utf-8 -*-

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.db.models import ArtifactBuild, ArtifactBuildStatus, GeneratedProject
from backend.services.pipeline.builders import (
    ComposeBuilder,
    DockerBuilder,
    HelmBuilder,
    MigrationPlanner,
    ReleaseNotesBuilder,
)
from backend.services.pipeline.publishers import DockerRegistryPublisher

logger = logging.getLogger(__name__)


class ArtifactPipelineError(RuntimeError):
    pass


PublishTargets = Literal["docker_registry", "github_releases", "artifact_repo"]


@dataclass
class ArtifactBuildConfig:
    docker_enabled: bool = True
    docker_registry: Optional[str] = None
    docker_tag: str = "latest"
    docker_scan_enabled: bool = True
    docker_sign_enabled: bool = True

    compose_enabled: bool = True

    helm_enabled: bool = False
    helm_version: str = "0.1.0"

    release_notes_enabled: bool = True
    migration_plan_enabled: bool = True

    @classmethod
    def from_request(cls, payload: Dict[str, Any]) -> "ArtifactBuildConfig":
        docker = payload.get("docker", {}) or {}
        compose = payload.get("compose", {}) or {}
        helm = payload.get("helm", {}) or {}
        release_notes = payload.get("release_notes", {}) or {}
        migration_plan = payload.get("migration_plan", {}) or {}

        return cls(
            docker_enabled=bool(docker.get("enabled", True)),
            docker_registry=docker.get("registry"),
            docker_tag=docker.get("tag", "latest"),
            docker_scan_enabled=bool(docker.get("scan", True)),
            docker_sign_enabled=bool(docker.get("sign", True)),
            compose_enabled=bool(compose.get("enabled", True)),
            helm_enabled=bool(helm.get("enabled", False)),
            helm_version=helm.get("version", "0.1.0"),
            release_notes_enabled=bool(release_notes.get("enabled", True)),
            migration_plan_enabled=bool(migration_plan.get("enabled", True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "docker": {
                "enabled": self.docker_enabled,
                "registry": self.docker_registry,
                "tag": self.docker_tag,
                "scan": self.docker_scan_enabled,
                "sign": self.docker_sign_enabled,
            },
            "compose": {"enabled": self.compose_enabled},
            "helm": {"enabled": self.helm_enabled, "version": self.helm_version},
            "release_notes": {"enabled": self.release_notes_enabled},
            "migration_plan": {"enabled": self.migration_plan_enabled},
        }


@dataclass
class ArtifactBuildResult:
    build_id: str
    status: str
    results: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class ArtifactPipeline:
    """Orchestrates artifact build + validation + publishing."""

    def __init__(self, db: Session):
        self.db = db
        self.docker_builder = DockerBuilder()
        self.compose_builder = ComposeBuilder()
        self.helm_builder = HelmBuilder()
        self.release_notes_builder = ReleaseNotesBuilder()
        self.migration_planner = MigrationPlanner()

    def create_build(
        self,
        *,
        execution_id: UUID,
        project_id: str,
        build_config: ArtifactBuildConfig,
    ) -> ArtifactBuild:
        build = ArtifactBuild(
            id=str(uuid4()),
            execution_id=str(execution_id),
            project_id=project_id,
            status=ArtifactBuildStatus.BUILDING,
            build_config=build_config.to_dict(),
            results={},
        )
        self.db.add(build)
        self.db.commit()
        self.db.refresh(build)
        return build

    def get_build(self, build_id: str) -> Optional[ArtifactBuild]:
        return self.db.query(ArtifactBuild).filter(ArtifactBuild.id == build_id).first()

    async def run_build(
        self,
        *,
        build_id: str,
        project_path: Optional[str] = None,
        project_name: Optional[str] = None,
        version: str = "0.1.0",
        changes: Optional[List[str]] = None,
        breaking_changes: Optional[List[str]] = None,
        migration_changes: Optional[Dict[str, Any]] = None,
    ) -> ArtifactBuild:
        build = self.get_build(build_id)
        if not build:
            raise ArtifactPipelineError(f"Build not found: {build_id}")

        try:
            build.status = ArtifactBuildStatus.BUILDING
            if not build.started_at:
                build.started_at = datetime.utcnow()
            self.db.commit()

            config = ArtifactBuildConfig.from_request(build.build_config or {})

            # Resolve project path
            if not project_path:
                gen = self.db.query(GeneratedProject).filter(GeneratedProject.id == build.project_id).first()
                if gen and gen.project_path:
                    project_path = gen.project_path
                if gen and not project_name:
                    project_name = gen.name

            if not project_path:
                raise ArtifactPipelineError("project_path is required (or project_id must reference a GeneratedProject with project_path)")

            project_dir = Path(project_path)
            if not project_name:
                project_name = project_dir.name

            results: Dict[str, Any] = {}

            image_ref: Optional[str] = None

            if config.docker_enabled:
                dockerfile = project_dir / "Dockerfile"
                docker_res = await self.docker_builder.build_image(
                    execution_id=UUID(build.execution_id),
                    project_path=str(project_dir),
                    dockerfile_path=str(dockerfile),
                    tag=config.docker_tag,
                    image_name=project_name,
                )
                results["docker_image"] = {
                    "image_ref": docker_res.image_ref,
                    "image_id": docker_res.image_id,
                    "digest": docker_res.digest,
                    "success": docker_res.success,
                }
                results["docker_build_logs"] = docker_res.logs[-20000:]

                if docker_res.success:
                    image_ref = docker_res.image_ref

                if docker_res.success and config.docker_scan_enabled:
                    scan = await self.docker_builder.scan_image(docker_res.image_ref, output_dir=project_dir / "deploy" / "security")
                    results["docker_scan"] = {
                        "tool": scan.tool,
                        "vulnerabilities": scan.vulnerabilities,
                        "score": scan.score,
                        "report_path": scan.report_path,
                        "skipped": scan.skipped,
                    }

                if docker_res.success and config.docker_sign_enabled:
                    sign = await self.docker_builder.sign_image(docker_res.image_ref)
                    results["docker_sign"] = {
                        "success": sign.returncode == 0,
                        "stdout": sign.stdout[-5000:],
                        "stderr": sign.stderr[-5000:],
                    }

                if docker_res.success and config.docker_registry:
                    push = await self.docker_builder.push_image(docker_res.image_ref, config.docker_registry)
                    results["docker_push"] = {
                        "registry": push.registry,
                        "image_ref": push.image_ref,
                        "digest": push.digest,
                        "success": push.success,
                    }
                    results["docker_push_logs"] = push.logs[-20000:]
                    if push.success:
                        image_ref = push.image_ref

            if config.compose_enabled:
                comp = await self.compose_builder.generate(
                    project_path=str(project_dir),
                    project_name=project_name,
                    image_ref=image_ref or f"{project_name}:{config.docker_tag}",
                    app_port=3000,
                    env={},
                )
                results["compose_file"] = comp.file_path
                results["compose_validated"] = comp.validated
                results["compose_validation_output"] = (comp.validation_output or "")[-5000:]

            if config.helm_enabled:
                helm_values = {
                    "replicaCount": 2,
                    "image": {
                        "repository": (image_ref or f"{project_name}").split(":")[0],
                        "tag": (image_ref or f"{project_name}:{version}").split(":")[-1],
                        "pullPolicy": "IfNotPresent",
                    },
                    "service": {"type": "ClusterIP", "port": 3000},
                    "env": {},
                    "resources": {
                        "limits": {"cpu": "1", "memory": "512Mi"},
                        "requests": {"cpu": "250m", "memory": "128Mi"},
                    },
                    "ingress": {"enabled": False, "host": ""},
                    "autoscaling": {
                        "enabled": True,
                        "minReplicas": 2,
                        "maxReplicas": 10,
                        "targetCPUUtilizationPercentage": 80,
                    },
                }

                helm_dir = project_dir / "deploy" / "helm"
                helm = await self.helm_builder.generate_chart(
                    project_name=project_name,
                    version=config.helm_version,
                    values=helm_values,
                    output_dir=str(helm_dir),
                )
                results["helm_chart"] = helm.chart_path
                results["helm_validated"] = helm.validated
                results["helm_validation_output"] = (helm.validation_output or "")[-5000:]

            if config.release_notes_enabled:
                rn = await self.release_notes_builder.generate_notes(
                    project_name=project_name,
                    version=version,
                    changes=changes or [],
                    breaking_changes=breaking_changes or [],
                    migration_steps=[],
                    security_alerts=["None"],
                    performance_improvements=[],
                    image_ref=image_ref,
                    output_dir=str(project_dir / "deploy" / "release-notes"),
                )
                results["release_notes"] = rn.file_path

            if config.migration_plan_enabled:
                mp = await self.migration_planner.generate_plan(
                    from_version="previous",
                    to_version=version,
                    changes=migration_changes or {},
                    output_dir=str(project_dir / "deploy" / "migrations"),
                )
                results["migration_plan"] = mp.file_path

            build.results = results
            build.status = ArtifactBuildStatus.COMPLETED
            build.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(build)
            return build

        except Exception as e:
            build.status = ArtifactBuildStatus.FAILED
            build.error_message = str(e)
            build.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(build)
            raise

    async def publish(self, *, build_id: str, targets: List[PublishTargets]) -> Dict[str, Any]:
        build = self.get_build(build_id)
        if not build:
            raise ArtifactPipelineError(f"Build not found: {build_id}")

        results: Dict[str, Any] = {}

        if "docker_registry" in targets:
            docker = (build.results or {}).get("docker_image") or {}
            image_ref = docker.get("image_ref")
            registry = (build.build_config or {}).get("docker", {}).get("registry")
            if image_ref and registry:
                publisher = DockerRegistryPublisher()
                res = await publisher.push(image_ref=image_ref, registry=registry)
                results["docker_registry"] = {
                    "success": res.success,
                    "registry": res.registry,
                    "image_ref": res.image_ref,
                    "logs": res.logs[-20000:],
                }

        # github_releases / artifact_repo are intentionally not auto-configured here.

        build_results = dict(build.results or {})
        build_results["publish"] = results
        build.results = build_results
        self.db.commit()

        return results
