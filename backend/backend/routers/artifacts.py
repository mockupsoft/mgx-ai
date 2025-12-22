# -*- coding: utf-8 -*-
"""Artifact & Release Pipeline API Router."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.models import ArtifactBuildStatus
from backend.db.session import get_db
from backend.services.pipeline import ArtifactBuildConfig, ArtifactPipeline


class ArtifactBuildDockerConfig(BaseModel):
    enabled: bool = True
    registry: Optional[str] = None
    tag: str = "latest"
    scan: bool = True
    sign: bool = True


class ArtifactBuildComposeConfig(BaseModel):
    enabled: bool = True


class ArtifactBuildHelmConfig(BaseModel):
    enabled: bool = False
    version: str = "0.1.0"


class ArtifactBuildReleaseNotesConfig(BaseModel):
    enabled: bool = True


class ArtifactBuildMigrationPlanConfig(BaseModel):
    enabled: bool = True


class ArtifactBuildConfigRequest(BaseModel):
    docker: ArtifactBuildDockerConfig = Field(default_factory=ArtifactBuildDockerConfig)
    compose: ArtifactBuildComposeConfig = Field(default_factory=ArtifactBuildComposeConfig)
    helm: ArtifactBuildHelmConfig = Field(default_factory=ArtifactBuildHelmConfig)
    release_notes: ArtifactBuildReleaseNotesConfig = Field(default_factory=ArtifactBuildReleaseNotesConfig)
    migration_plan: ArtifactBuildMigrationPlanConfig = Field(default_factory=ArtifactBuildMigrationPlanConfig)


class ArtifactBuildRequest(BaseModel):
    execution_id: UUID
    project_id: str
    project_path: Optional[str] = None
    project_name: Optional[str] = None

    version: str = "0.1.0"

    changes: List[str] = Field(default_factory=list)
    breaking_changes: List[str] = Field(default_factory=list)
    migration_changes: Dict[str, Any] = Field(default_factory=dict)

    build_config: ArtifactBuildConfigRequest = Field(default_factory=ArtifactBuildConfigRequest)


class ArtifactBuildResponse(BaseModel):
    build_id: str
    status: str
    estimated_duration: int


class ArtifactBuildStatusResponse(BaseModel):
    build_id: str
    status: str
    results: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ArtifactPublishRequest(BaseModel):
    build_id: str
    targets: List[Literal["docker_registry", "github_releases", "artifact_repo"]]


router = APIRouter(prefix="/api/artifacts", tags=["Artifacts"])


@router.post("/build", response_model=ArtifactBuildResponse)
async def build_artifacts(
    request: ArtifactBuildRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    pipeline = ArtifactPipeline(db)
    cfg = ArtifactBuildConfig.from_request(request.build_config.model_dump())

    build = pipeline.create_build(execution_id=request.execution_id, project_id=request.project_id, build_config=cfg)

    background_tasks.add_task(
        pipeline.run_build,
        build_id=build.id,
        project_path=request.project_path,
        project_name=request.project_name,
        version=request.version,
        changes=request.changes,
        breaking_changes=request.breaking_changes,
        migration_changes=request.migration_changes,
    )

    return ArtifactBuildResponse(build_id=build.id, status=build.status.value, estimated_duration=120)


@router.get("/builds/{build_id}", response_model=ArtifactBuildStatusResponse)
async def get_build_status(build_id: str, db: Session = Depends(get_db)):
    pipeline = ArtifactPipeline(db)
    build = pipeline.get_build(build_id)
    if not build:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build not found")

    return ArtifactBuildStatusResponse(
        build_id=build.id,
        status=build.status.value if isinstance(build.status, ArtifactBuildStatus) else str(build.status),
        results=build.results or {},
        error_message=build.error_message,
        created_at=build.created_at,
        updated_at=build.updated_at,
    )


@router.post("/publish")
async def publish_artifacts(
    request: ArtifactPublishRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    pipeline = ArtifactPipeline(db)
    build = pipeline.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build not found")

    background_tasks.add_task(pipeline.publish, build_id=request.build_id, targets=request.targets)

    return {"status": "publishing", "build_id": request.build_id}
