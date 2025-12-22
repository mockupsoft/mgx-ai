# -*- coding: utf-8 -*-
"""Repository linking router.

Endpoints to connect a project to an external Git repository (currently GitHub).

The router is workspace-scoped using :func:`backend.routers.deps.get_workspace_context`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from backend.db.models import Project, RepositoryLink
from backend.db.models.enums import RepositoryLinkStatus, RepositoryProvider
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import (
    RepositoryLinkConnectRequest,
    RepositoryLinkListResponse,
    RepositoryLinkResponse,
    RepositoryLinkTestRequest,
    RepositoryLinkTestResponse,
    RepositoryLinkUpdateRequest,
)
from backend.services.git import GitService, RepositoryAccessError, RepositoryNotFoundError, get_git_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


async def _get_project_in_workspace(ctx: WorkspaceContext, project_id: str) -> Project:
    result = await ctx.session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == ctx.workspace.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_link_in_workspace(ctx: WorkspaceContext, link_id: str) -> RepositoryLink:
    result = await ctx.session.execute(
        select(RepositoryLink)
        .join(Project, RepositoryLink.project_id == Project.id)
        .where(RepositoryLink.id == link_id, Project.workspace_id == ctx.workspace.id)
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Repository link not found")
    return link


@router.get("/", response_model=RepositoryLinkListResponse)
async def list_repository_links(
    project_id: Optional[str] = Query(None, description="Filter by project id"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RepositoryLinkListResponse:
    session = ctx.session

    query = (
        select(RepositoryLink)
        .join(Project, RepositoryLink.project_id == Project.id)
        .where(Project.workspace_id == ctx.workspace.id)
    )

    if project_id:
        await _get_project_in_workspace(ctx, project_id)
        query = query.where(RepositoryLink.project_id == project_id)

    total_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(total_query)).scalar_one()

    result = await session.execute(query.order_by(RepositoryLink.created_at.desc()).offset(skip).limit(limit))
    links = result.scalars().all()

    return RepositoryLinkListResponse(
        items=[RepositoryLinkResponse.model_validate(link) for link in links],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/test", response_model=RepositoryLinkTestResponse)
async def test_repository_access(
    payload: RepositoryLinkTestRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    git_service: GitService = Depends(get_git_service),
) -> RepositoryLinkTestResponse:
    _ = ctx  # workspace context reserved for future auditing

    try:
        info = await git_service.fetch_repo_info(
            payload.repo_full_name,
            installation_id=payload.installation_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RepositoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RepositoryAccessError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    return RepositoryLinkTestResponse(
        ok=True,
        repo_full_name=info.full_name,
        default_branch=info.default_branch,
    )


@router.post("/connect", response_model=RepositoryLinkResponse, status_code=201)
async def connect_repository(
    payload: RepositoryLinkConnectRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    git_service: GitService = Depends(get_git_service),
) -> RepositoryLinkResponse:
    session = ctx.session

    project = await _get_project_in_workspace(ctx, payload.project_id)

    try:
        info = await git_service.fetch_repo_info(
            payload.repo_full_name,
            installation_id=payload.installation_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RepositoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RepositoryAccessError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    existing = await session.execute(
        select(RepositoryLink).where(
            RepositoryLink.project_id == project.id,
            RepositoryLink.provider == RepositoryProvider.GITHUB,
            RepositoryLink.repo_full_name == info.full_name,
            RepositoryLink.status != RepositoryLinkStatus.DISCONNECTED,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Repository is already connected to this project")

    link = RepositoryLink(
        project_id=project.id,
        provider=RepositoryProvider.GITHUB,
        repo_full_name=info.full_name,
        default_branch=info.default_branch,
        status=RepositoryLinkStatus.CONNECTED,
        auth_payload={
            "installation_id": payload.installation_id,
            "auth_type": "app" if payload.installation_id else "pat",
        },
        meta_data={
            "private": info.private,
            "html_url": info.html_url,
        },
        last_validated_at=datetime.now(timezone.utc),
    )

    session.add(link)
    await session.flush()

    should_set_primary = payload.set_as_primary or not project.primary_repository_link_id
    if should_set_primary:
        project.primary_repository_link_id = link.id
        project.repo_full_name = link.repo_full_name
        project.default_branch = payload.reference_branch or link.default_branch

        if payload.reference_branch:
            link.default_branch = payload.reference_branch

    logger.info("Repository connected: project=%s repo=%s", project.id, link.repo_full_name)

    return RepositoryLinkResponse.model_validate(link)


@router.post("/{link_id}/refresh", response_model=RepositoryLinkResponse)
async def refresh_repository_link(
    link_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    git_service: GitService = Depends(get_git_service),
) -> RepositoryLinkResponse:
    session = ctx.session

    link = await _get_link_in_workspace(ctx, link_id)
    project = await _get_project_in_workspace(ctx, link.project_id)

    installation_id = None
    if isinstance(link.auth_payload, dict):
        installation_id = link.auth_payload.get("installation_id")

    try:
        info = await git_service.fetch_repo_info(link.repo_full_name, installation_id=installation_id)
    except RepositoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RepositoryAccessError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    link.repo_full_name = info.full_name
    link.default_branch = info.default_branch
    link.status = RepositoryLinkStatus.CONNECTED
    link.meta_data = {"private": info.private, "html_url": info.html_url}
    link.last_validated_at = datetime.now(timezone.utc)

    if project.primary_repository_link_id == link.id:
        project.repo_full_name = link.repo_full_name
        project.default_branch = link.default_branch

    await session.flush()

    return RepositoryLinkResponse.model_validate(link)


@router.patch("/{link_id}", response_model=RepositoryLinkResponse)
async def update_repository_link(
    link_id: str,
    payload: RepositoryLinkUpdateRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RepositoryLinkResponse:
    session = ctx.session

    link = await _get_link_in_workspace(ctx, link_id)
    project = await _get_project_in_workspace(ctx, link.project_id)

    if payload.reference_branch is not None:
        link.default_branch = payload.reference_branch

    if payload.set_as_primary is True:
        project.primary_repository_link_id = link.id
        project.repo_full_name = link.repo_full_name
        project.default_branch = link.default_branch

    await session.flush()
    return RepositoryLinkResponse.model_validate(link)


@router.delete("/{link_id}", response_model=RepositoryLinkResponse)
async def disconnect_repository(
    link_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> RepositoryLinkResponse:
    session = ctx.session

    link = await _get_link_in_workspace(ctx, link_id)
    project = await _get_project_in_workspace(ctx, link.project_id)

    link.status = RepositoryLinkStatus.DISCONNECTED
    link.auth_payload = {}

    if project.primary_repository_link_id == link.id:
        project.primary_repository_link_id = None
        project.repo_full_name = None
        project.default_branch = None

    await session.flush()

    return RepositoryLinkResponse.model_validate(link)


__all__ = ["router"]
