# -*- coding: utf-8 -*-
"""Projects Router

Lightweight endpoints for managing projects within the active workspace.

Projects are always scoped to the active workspace (see :func:`get_workspace_context`).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text

from backend.db.models import Project
from backend.routers.deps import WorkspaceContext, get_workspace_context, slugify
from backend.schemas import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> ProjectListResponse:
    session = ctx.session

    # Count query - this doesn't select columns, so it's safe
    count_query = select(func.count()).select_from(Project).where(Project.workspace_id == ctx.workspace.id)
    total = (await session.execute(count_query)).scalar_one()

    # Use raw SQL to avoid issues with missing columns in database (migration issue)
    # Only select columns that exist in the database
    result = await session.execute(
        text("""
            SELECT id, workspace_id, name, slug, metadata, created_at, updated_at
            FROM projects
            WHERE workspace_id = :workspace_id
            ORDER BY created_at
            OFFSET :skip
            LIMIT :limit
        """),
        {"workspace_id": ctx.workspace.id, "skip": skip, "limit": limit}
    )
    rows = result.all()

    # Convert raw SQL results to ProjectResponse objects
    project_items = []
    for row in rows:
        project_items.append(
            ProjectResponse(
                id=row[0],
                workspace_id=row[1],
                name=row[2],
                slug=row[3],
                meta_data=row[4] if row[4] else {},
                created_at=row[5],
                updated_at=row[6],
                # Optional fields that don't exist in DB yet
                repo_full_name=None,
                default_branch=None,
                primary_repository_link_id=None,
                run_branch_prefix=None,
                commit_template=None,
            )
        )

    return ProjectListResponse(
        items=project_items,
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


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> ProjectResponse:
    session = ctx.session

    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == ctx.workspace.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)

    if "slug" in update_data and update_data["slug"]:
        existing = await session.execute(
            select(Project).where(
                Project.workspace_id == ctx.workspace.id,
                Project.slug == update_data["slug"],
                Project.id != project_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Project slug already exists in workspace")

    for field, value in update_data.items():
        if field == "meta_data" and value is None:
            continue
        setattr(project, field, value)

    await session.flush()
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> dict:
    session = ctx.session

    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == ctx.workspace.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.delete(project)
    return {"status": "deleted", "project_id": project_id}


__all__ = ["router"]
