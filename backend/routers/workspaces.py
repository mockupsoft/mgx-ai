# -*- coding: utf-8 -*-
"""Workspaces Router

Lightweight CRUD endpoints for managing workspaces.

These endpoints are not scoped (they operate across all workspaces).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Project, Workspace
from backend.db.session import get_session
from backend.routers.deps import DEFAULT_PROJECT_NAME, DEFAULT_PROJECT_SLUG, slugify
from backend.schemas import WorkspaceCreate, WorkspaceListResponse, WorkspaceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("/", response_model=WorkspaceListResponse)
async def list_workspaces(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceListResponse:
    count_query = select(func.count()).select_from(Workspace)
    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(select(Workspace).order_by(Workspace.created_at).offset(skip).limit(limit))
    workspaces = result.scalars().all()

    return WorkspaceListResponse(
        items=[WorkspaceResponse.model_validate(ws) for ws in workspaces],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    payload: WorkspaceCreate,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceResponse:
    slug = payload.slug or slugify(payload.name)

    existing = await session.execute(select(Workspace).where(Workspace.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Workspace slug already exists")

    workspace = Workspace(name=payload.name, slug=slug, meta_data=payload.meta_data)
    session.add(workspace)
    await session.flush()

    default_project = Project(
        workspace_id=workspace.id,
        name=DEFAULT_PROJECT_NAME,
        slug=DEFAULT_PROJECT_SLUG,
        meta_data={},
    )
    session.add(default_project)
    await session.flush()

    logger.info("Workspace created: %s", workspace.id)
    return WorkspaceResponse.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceResponse:
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return WorkspaceResponse.model_validate(workspace)


__all__ = ["router"]
