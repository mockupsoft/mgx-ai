# -*- coding: utf-8 -*-
"""Shared router dependencies.

This module provides workspace scoping for multi-tenant APIs.

Clients can select the active workspace via:
- Header: X-Workspace-Id / X-Workspace-Slug
- Query:  workspace_id / workspace_slug

If none is provided, the "default" workspace is used (and created on-demand).
"""

from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, DisconnectionError

from backend.db.models import Project, Workspace
from backend.db.session import get_session

logger = logging.getLogger(__name__)


# Alias for backward compatibility
get_db_session = get_session


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
    """Get or create default project for workspace."""
    try:
        # Use raw SQL to avoid issues with missing columns in database (migration issue)
        # This is a workaround until migrations are properly applied
        from sqlalchemy import text
        
        logger.debug("[_get_or_create_default_project] Looking up project for workspace_id=%s", workspace.id)
        
        # First, try to get existing project using raw SQL (only select columns that exist)
        result = await session.execute(
            text("""
                SELECT id, workspace_id, name, slug, metadata, created_at, updated_at
                FROM projects
                WHERE workspace_id = :workspace_id AND slug = :slug
                LIMIT 1
            """),
            {"workspace_id": workspace.id, "slug": DEFAULT_PROJECT_SLUG}
        )
        row = result.first()
        
        if row is not None:
            # Project exists - create a Project object manually from row data
            # We can't use session.get() because it will try to select all columns including repo_full_name
            logger.debug("[_get_or_create_default_project] Found existing project: %s", row[0])
            project = Project(
                id=row[0],
                workspace_id=row[1],
                name=row[2],
                slug=row[3],
                meta_data=row[4] if row[4] else {},
            )
            # Make it an expunged object (not attached to session) to avoid loading from DB
            # We'll return it as-is since we have all the data we need
            return project

        # Project doesn't exist - create it using raw SQL to avoid missing columns
        logger.info("[_get_or_create_default_project] Creating new default project for workspace_id=%s", workspace.id)
        import uuid
        project_id = str(uuid.uuid4())
        
        # Use raw SQL INSERT to avoid SQLAlchemy trying to insert non-existent columns
        await session.execute(
            text("""
                INSERT INTO projects (id, workspace_id, name, slug, metadata, created_at, updated_at)
                VALUES (:id, :workspace_id, :name, :slug, :metadata, NOW(), NOW())
            """),
            {
                "id": project_id,
                "workspace_id": workspace.id,
                "name": DEFAULT_PROJECT_NAME,
                "slug": DEFAULT_PROJECT_SLUG,
                "metadata": "{}",
            }
        )
        await session.flush()
        
        # Create Project object manually from the inserted data
        project = Project(
            id=project_id,
            workspace_id=workspace.id,
            name=DEFAULT_PROJECT_NAME,
            slug=DEFAULT_PROJECT_SLUG,
            meta_data={},
        )
        logger.debug("[_get_or_create_default_project] Created project: %s", project.id)
        return project
    except Exception as e:
        logger.error("[_get_or_create_default_project] Error: %s", e, exc_info=True)
        raise


async def get_workspace_context(
    session: AsyncSession = Depends(get_session),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_workspace_slug: Optional[str] = Header(None, alias="X-Workspace-Slug"),
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
) -> WorkspaceContext:
    """Resolve the active workspace and ensure a default project exists."""
    try:
        logger.debug(
            "[get_workspace_context] Starting - workspace_id=%s, workspace_slug=%s",
            x_workspace_id or workspace_id,
            x_workspace_slug or workspace_slug,
        )

        resolved_id = x_workspace_id or workspace_id
        resolved_slug = x_workspace_slug or workspace_slug

        workspace: Optional[Workspace] = None

        if resolved_id:
            logger.debug("[get_workspace_context] Looking up workspace by ID: %s", resolved_id)
            result = await session.execute(select(Workspace).where(Workspace.id == resolved_id))
            workspace = result.scalar_one_or_none()
            if workspace is None:
                logger.warning("[get_workspace_context] Workspace not found: %s", resolved_id)
                raise HTTPException(status_code=404, detail="Workspace not found")
        else:
            slug = resolved_slug or DEFAULT_WORKSPACE_SLUG
            logger.debug("[get_workspace_context] Looking up workspace by slug: %s", slug)
            result = await session.execute(select(Workspace).where(Workspace.slug == slug))
            workspace = result.scalar_one_or_none()

            if workspace is None:
                if slug != DEFAULT_WORKSPACE_SLUG:
                    logger.warning("[get_workspace_context] Workspace not found: %s", slug)
                    raise HTTPException(status_code=404, detail="Workspace not found")

                logger.info("[get_workspace_context] Creating default workspace")
                workspace = Workspace(
                    name=DEFAULT_WORKSPACE_NAME,
                    slug=DEFAULT_WORKSPACE_SLUG,
                    workspace_metadata={},
                )
                session.add(workspace)
                await session.flush()

        logger.debug("[get_workspace_context] Getting or creating default project")
        default_project = await _get_or_create_default_project(session, workspace)

        logger.debug("[get_workspace_context] Success - workspace_id=%s", workspace.id)
        return WorkspaceContext(session=session, workspace=workspace, default_project=default_project)
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except (OperationalError, DisconnectionError) as e:
        # Database connection errors
        logger.error("[get_workspace_context] Database connection error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {str(e)}. Please check database configuration and connectivity."
        )
    except socket.gaierror as e:
        # DNS resolution errors
        logger.error("[get_workspace_context] DNS resolution error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Database hostname resolution failed: {str(e)}. Please check DB_HOST configuration."
        )
    except Exception as e:
        # Other unexpected errors
        logger.error("[get_workspace_context] Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while resolving workspace context: {str(e)}"
        )
