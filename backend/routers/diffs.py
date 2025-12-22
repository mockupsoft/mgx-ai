# -*- coding: utf-8 -*-
"""Diff viewing router.

Endpoints for viewing GitHub diffs:
- Get commit diff
- Get compare diff
- List diffs
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from backend.db.models import RepositoryLink, Project
from backend.db.models.enums import RepositoryProvider
from backend.db.session import get_session
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.services.github.diff_viewer import (
    DiffViewer,
    DiffResponse,
    get_diff_viewer,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["diffs"])


async def _get_repository_link(
    ctx: WorkspaceContext,
    link_id: str,
    session: AsyncSession,
) -> RepositoryLink:
    """Get repository link in workspace."""
    result = await session.execute(
        select(RepositoryLink)
        .join(Project, RepositoryLink.project_id == Project.id)
        .where(
            RepositoryLink.id == link_id,
            RepositoryLink.provider == RepositoryProvider.GITHUB,
            Project.workspace_id == ctx.workspace.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Repository link not found")
    
    return link


@router.get("/{link_id}/diffs/{commit_sha}", response_model=dict)
async def get_commit_diff(
    link_id: str,
    commit_sha: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    diff_viewer: DiffViewer = Depends(get_diff_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get diff for a specific commit.
    
    Args:
        link_id: Repository link ID
        commit_sha: Commit SHA
        ctx: Workspace context
        diff_viewer: Diff viewer instance
        session: Database session
    
    Returns:
        Diff response
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        diff = await diff_viewer.get_commit_diff(
            repo_full_name=link.repo_full_name,
            commit_sha=commit_sha,
            installation_id=installation_id,
        )
        
        return {
            "base_sha": diff.base_sha,
            "head_sha": diff.head_sha,
            "files": [
                {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch,
                    "previous_filename": file.previous_filename,
                }
                for file in diff.files
            ],
            "statistics": {
                "files_changed": diff.statistics.files_changed,
                "additions": diff.statistics.additions,
                "deletions": diff.statistics.deletions,
                "total_changes": diff.statistics.total_changes,
            },
        }
    except Exception as e:
        logger.error(f"Error getting commit diff: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get commit diff: {e}")


@router.get("/{link_id}/diffs/compare", response_model=dict)
async def get_compare_diff(
    link_id: str,
    base: str = Query(..., description="Base branch/commit"),
    head: str = Query(..., description="Head branch/commit"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    diff_viewer: DiffViewer = Depends(get_diff_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get diff between two branches/commits.
    
    Args:
        link_id: Repository link ID
        base: Base branch/commit
        head: Head branch/commit
        ctx: Workspace context
        diff_viewer: Diff viewer instance
        session: Database session
    
    Returns:
        Diff response
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        diff = await diff_viewer.get_compare_diff(
            repo_full_name=link.repo_full_name,
            base=base,
            head=head,
            installation_id=installation_id,
        )
        
        return {
            "base_sha": diff.base_sha,
            "head_sha": diff.head_sha,
            "files": [
                {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch,
                    "previous_filename": file.previous_filename,
                }
                for file in diff.files
            ],
            "statistics": {
                "files_changed": diff.statistics.files_changed,
                "additions": diff.statistics.additions,
                "deletions": diff.statistics.deletions,
                "total_changes": diff.statistics.total_changes,
            },
        }
    except Exception as e:
        logger.error(f"Error getting compare diff: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get compare diff: {e}")

