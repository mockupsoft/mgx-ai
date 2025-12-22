# -*- coding: utf-8 -*-
"""Branch management router.

Endpoints for managing GitHub Branches:
- List branches
- Create branch
- Delete branch
- Compare branches
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select

from backend.db.models import RepositoryLink, Project
from backend.db.models.enums import RepositoryProvider
from backend.db.session import get_session
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.services.github.branch_manager import (
    BranchManager,
    BranchInfo,
    BranchCompare,
    get_branch_manager,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["branches"])


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


@router.get("/{link_id}/branches", response_model=List[dict])
async def list_branches(
    link_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    branch_manager: BranchManager = Depends(get_branch_manager),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    List branches for a repository.
    
    Args:
        link_id: Repository link ID
        ctx: Workspace context
        branch_manager: Branch manager instance
        session: Database session
    
    Returns:
        List of branches
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        branches = await branch_manager.list_branches(
            repo_full_name=link.repo_full_name,
            installation_id=installation_id,
        )
        
        return [
            {
                "name": branch.name,
                "sha": branch.sha,
                "protected": branch.protected,
                "default": branch.default,
            }
            for branch in branches
        ]
    except Exception as e:
        logger.error(f"Error listing branches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list branches: {e}")


@router.post("/{link_id}/branches", response_model=dict, status_code=201)
async def create_branch(
    link_id: str,
    branch_name: str = Body(...),
    from_branch: str = Body("main"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    branch_manager: BranchManager = Depends(get_branch_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Create a new branch.
    
    Args:
        link_id: Repository link ID
        branch_name: New branch name
        from_branch: Source branch
        ctx: Workspace context
        branch_manager: Branch manager instance
        session: Database session
    
    Returns:
        Created branch info
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        branch = await branch_manager.create_branch(
            repo_full_name=link.repo_full_name,
            branch_name=branch_name,
            from_branch=from_branch,
            installation_id=installation_id,
        )
        
        return {
            "name": branch.name,
            "sha": branch.sha,
            "protected": branch.protected,
            "default": branch.default,
        }
    except Exception as e:
        logger.error(f"Error creating branch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create branch: {e}")


@router.delete("/{link_id}/branches/{branch_name}", response_model=dict)
async def delete_branch(
    link_id: str,
    branch_name: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    branch_manager: BranchManager = Depends(get_branch_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Delete a branch.
    
    Args:
        link_id: Repository link ID
        branch_name: Branch name to delete
        ctx: Workspace context
        branch_manager: Branch manager instance
        session: Database session
    
    Returns:
        Deletion result
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        deleted = await branch_manager.delete_branch(
            repo_full_name=link.repo_full_name,
            branch_name=branch_name,
            installation_id=installation_id,
        )
        
        return {"deleted": deleted, "branch_name": branch_name}
    except Exception as e:
        logger.error(f"Error deleting branch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete branch: {e}")


@router.get("/{link_id}/branches/compare", response_model=dict)
async def compare_branches(
    link_id: str,
    base: str = Query(..., description="Base branch"),
    head: str = Query(..., description="Head branch"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    branch_manager: BranchManager = Depends(get_branch_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Compare two branches.
    
    Args:
        link_id: Repository link ID
        base: Base branch
        head: Head branch
        ctx: Workspace context
        branch_manager: Branch manager instance
        session: Database session
    
    Returns:
        Branch comparison result
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        comparison = await branch_manager.compare_branches(
            repo_full_name=link.repo_full_name,
            base_branch=base,
            head_branch=head,
            installation_id=installation_id,
        )
        
        return {
            "ahead_by": comparison.ahead_by,
            "behind_by": comparison.behind_by,
            "total_commits": comparison.total_commits,
            "commits": comparison.commits,
        }
    except Exception as e:
        logger.error(f"Error comparing branches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compare branches: {e}")

