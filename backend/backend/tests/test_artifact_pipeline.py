# -*- coding: utf-8 -*-

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, ArtifactBuildStatus, ArtifactBuild
from backend.services.pipeline.builders import (
    ComposeBuilder,
    DockerBuildResult,
    HelmBuilder,
    MigrationPlanner,
    ReleaseNotesBuilder,
    SecurityScanResult,
)
from backend.services.pipeline.pipeline import ArtifactBuildConfig, ArtifactPipeline


class TestArtifactBuilders:
    @pytest.mark.asyncio
    async def test_release_notes_builder_generates_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = ReleaseNotesBuilder()
            res = await builder.generate_notes(
                project_name="my-app",
                version="v1.0.0",
                changes=["Feature: add login", "Fix: handle null"],
                breaking_changes=["Breaking: remove legacy endpoint"],
                migration_steps=["Run migrations"],
                image_ref="org/my-app:v1.0.0",
                output_dir=tmp,
            )

            content = Path(res.file_path).read_text(encoding="utf-8")
            assert "# Release v1.0.0" in content
            assert "## Features" in content
            assert "## Bug Fixes" in content
            assert "## Breaking Changes" in content
            assert "org/my-app:v1.0.0" in content

    @pytest.mark.asyncio
    async def test_compose_builder_includes_healthchecks(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = ComposeBuilder()
            res = await builder.generate(
                project_path=tmp,
                project_name="my-app",
                image_ref="my-app:latest",
                app_port=3000,
            )

            assert Path(res.file_path).exists()
            assert "healthcheck" in res.content
            assert "depends_on" in res.content

    @pytest.mark.asyncio
    async def test_helm_builder_creates_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = HelmBuilder()
            res = await builder.generate_chart(
                project_name="my-app",
                version="1.0.0",
                values={
                    "replicaCount": 1,
                    "image": {"repository": "my-app", "tag": "1.0.0", "pullPolicy": "IfNotPresent"},
                    "service": {"type": "ClusterIP", "port": 3000},
                    "env": {},
                    "resources": {"limits": {"cpu": "1", "memory": "256Mi"}, "requests": {"cpu": "100m", "memory": "64Mi"}},
                    "ingress": {"enabled": False, "host": ""},
                    "autoscaling": {"enabled": False, "minReplicas": 1, "maxReplicas": 1, "targetCPUUtilizationPercentage": 80},
                },
                output_dir=tmp,
            )

            chart_dir = Path(res.chart_path)
            assert (chart_dir / "Chart.yaml").exists()
            assert (chart_dir / "values.yaml").exists()
            assert (chart_dir / "templates" / "deployment.yaml").exists()


class TestArtifactPipeline:
    @pytest.fixture
    def db(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.mark.asyncio
    async def test_pipeline_build_persists_results(self, db):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "my-app"
            project_dir.mkdir(parents=True)
            (project_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

            pipeline = ArtifactPipeline(db)

            # Patch Docker steps to avoid needing docker/trivy/cosign in test environment.
            async def fake_build_image(**kwargs):
                return DockerBuildResult(
                    image_ref="my-app:latest",
                    image_id="sha256:dummy",
                    digest="my-app@sha256:dummy",
                    logs="ok",
                    success=True,
                )

            async def fake_scan_image(image_ref, **kwargs):
                return SecurityScanResult(
                    tool="trivy",
                    image_ref=image_ref,
                    vulnerabilities=0,
                    score="A",
                    report_path=None,
                    skipped=False,
                    raw={},
                )

            async def fake_sign_image(image_ref):
                class R:
                    returncode = 0
                    stdout = "signed"
                    stderr = ""

                return R()

            pipeline.docker_builder.build_image = fake_build_image  # type: ignore[method-assign]
            pipeline.docker_builder.scan_image = fake_scan_image  # type: ignore[method-assign]
            pipeline.docker_builder.sign_image = fake_sign_image  # type: ignore[method-assign]

            cfg = ArtifactBuildConfig(docker_enabled=True, compose_enabled=True, helm_enabled=False)

            build = pipeline.create_build(execution_id=uuid4(), project_id="external", build_config=cfg)

            await pipeline.run_build(build_id=build.id, project_path=str(project_dir), version="0.1.0")

            saved = db.query(ArtifactBuild).filter(ArtifactBuild.id == build.id).first()
            assert saved is not None
            assert saved.status == ArtifactBuildStatus.COMPLETED
            assert "docker_image" in (saved.results or {})
            assert "compose_file" in (saved.results or {})

    @pytest.mark.asyncio
    async def test_migration_planner_generates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            planner = MigrationPlanner()
            res = await planner.generate_plan(
                from_version="1.0.0",
                to_version="1.1.0",
                changes={"db_migrations_sql": "ALTER TABLE x ADD COLUMN y INT;"},
                output_dir=tmp,
            )

            assert Path(res.file_path).exists()
            content = Path(res.file_path).read_text(encoding="utf-8")
            assert "ALTER TABLE" in content
