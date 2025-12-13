# -*- coding: utf-8 -*-
"""Projects Router

Lightweight endpoints for managing projects within the active workspace.

Projects are always scoped to the active workspace (see :func:`get_workspace_context`).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from backend.db.models import Project
from backend.routers.deps import WorkspaceContext, get_workspace_context, slugify
from backend.schemas import ProjectCreate, ProjectListResponse, ProjectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> ProjectListResponse:
    session = ctx.session

    count_query = select(func.count()).select_from(Project).where(Project.workspace_id == ctx.workspace.id)
    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(
        select(Project)
        .where(Project.workspace_id == ctx.workspace.id)
        .order_by(Project.created_at)
        .offset(skip)
        .limit(limit)
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> ProjectResponse:
    session = ctx.session

    slug = payload.slug or slugify(payload.name)

    existing = await session.execute(
        select(Project).where(Project.workspace_id == ctx.workspace.id, Project.slug == slug)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Project slug already exists in workspace")

    project = Project(
        workspace_id=ctx.workspace.id,
        name=payload.name,
        slug=slug,
        meta_data=payload.meta_data,
    )

    session.add(project)
    await session.flush()

    logger.info("Project created: %s", project.id)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> ProjectResponse:
    session = ctx.session

    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == ctx.workspace.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse.model_validate(project)


__all__ = ["router"]
