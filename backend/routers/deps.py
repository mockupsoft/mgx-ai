# -*- coding: utf-8 -*-
"""Shared router dependencies.

This module provides workspace scoping for multi-tenant APIs.

Clients can select the active workspace via:
- Header: X-Workspace-Id / X-Workspace-Slug
- Query:  workspace_id / workspace_slug

If none is provided, the "default" workspace is used (and created on-demand).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Project, Workspace
from backend.db.session import get_session


DEFAULT_WORKSPACE_SLUG = "default"
DEFAULT_WORKSPACE_NAME = "Default Workspace"
DEFAULT_PROJECT_SLUG = "default"
DEFAULT_PROJECT_NAME = "Default Project"


_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = _slug_re.sub("-", value)
    return value.strip("-") or "default"


@dataclass
class WorkspaceContext:
    session: AsyncSession
    workspace: Workspace
    default_project: Project


async def _get_or_create_default_project(session: AsyncSession, workspace: Workspace) -> Project:
    result = await session.execute(
        select(Project).where(
            Project.workspace_id == workspace.id,
            Project.slug == DEFAULT_PROJECT_SLUG,
        )
    )
    project = result.scalar_one_or_none()
    if project is not None:
        return project

    project = Project(
        workspace_id=workspace.id,
        name=DEFAULT_PROJECT_NAME,
        slug=DEFAULT_PROJECT_SLUG,
        meta_data={},
    )
    session.add(project)
    await session.flush()
    return project


async def get_workspace_context(
    session: AsyncSession = Depends(get_session),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_workspace_slug: Optional[str] = Header(None, alias="X-Workspace-Slug"),
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
) -> WorkspaceContext:
    """Resolve the active workspace and ensure a default project exists."""

    resolved_id = x_workspace_id or workspace_id
    resolved_slug = x_workspace_slug or workspace_slug

    workspace: Optional[Workspace] = None

    if resolved_id:
        result = await session.execute(select(Workspace).where(Workspace.id == resolved_id))
        workspace = result.scalar_one_or_none()
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
    else:
        slug = resolved_slug or DEFAULT_WORKSPACE_SLUG
        result = await session.execute(select(Workspace).where(Workspace.slug == slug))
        workspace = result.scalar_one_or_none()

        if workspace is None:
            if slug != DEFAULT_WORKSPACE_SLUG:
                raise HTTPException(status_code=404, detail="Workspace not found")

            workspace = Workspace(
                name=DEFAULT_WORKSPACE_NAME,
                slug=DEFAULT_WORKSPACE_SLUG,
                meta_data={},
            )
            session.add(workspace)
            await session.flush()

    default_project = await _get_or_create_default_project(session, workspace)

    return WorkspaceContext(session=session, workspace=workspace, default_project=default_project)
