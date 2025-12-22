# -*- coding: utf-8 -*-
"""Pull Request management router.

Endpoints for managing GitHub Pull Requests:
- List PRs
- Get PR details
- Merge PR
- Create review
- Create comment
"""

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select

from backend.db.models import RepositoryLink
from backend.db.models.enums import RepositoryProvider
from backend.db.session import get_session
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.services.github.pr_manager import (
    PRManager,
    PullRequestInfo,
    PRReview,
    PRComment,
    get_pr_manager,
)
from backend.services.git import get_git_service
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["pull-requests"])


async def _get_repository_link(
    ctx: WorkspaceContext,
    link_id: str,
    session: AsyncSession,
) -> RepositoryLink:
    """Get repository link in workspace."""
    from backend.db.models import Project
    
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


@router.get("/{link_id}/pull-requests", response_model=List[dict])
async def list_pull_requests(
    link_id: str,
    state: str = Query("open", regex="^(open|closed|all)$"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    List pull requests for a repository.
    
    Args:
        link_id: Repository link ID
        state: PR state filter (open, closed, all)
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        List of pull requests
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        prs = await pr_manager.list_pull_requests(
            repo_full_name=link.repo_full_name,
            state=state,
            installation_id=installation_id,
        )
        
        return [
            {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "head_branch": pr.head_branch,
                "base_branch": pr.base_branch,
                "head_sha": pr.head_sha,
                "base_sha": pr.base_sha,
                "html_url": pr.html_url,
                "created_at": pr.created_at,
                "updated_at": pr.updated_at,
                "merged_at": pr.merged_at,
                "mergeable": pr.mergeable,
                "mergeable_state": pr.mergeable_state,
                "author": pr.author,
                "labels": pr.labels or [],
                "review_count": pr.review_count,
                "comment_count": pr.comment_count,
            }
            for pr in prs
        ]
    except Exception as e:
        logger.error(f"Error listing PRs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list pull requests: {e}")


@router.get("/{link_id}/pull-requests/{pr_number}", response_model=dict)
async def get_pull_request(
    link_id: str,
    pr_number: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get pull request details.
    
    Args:
        link_id: Repository link ID
        pr_number: Pull request number
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        Pull request details
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        pr = await pr_manager.get_pull_request(
            repo_full_name=link.repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
        
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "head_branch": pr.head_branch,
            "base_branch": pr.base_branch,
            "head_sha": pr.head_sha,
            "base_sha": pr.base_sha,
            "html_url": pr.html_url,
            "created_at": pr.created_at,
            "updated_at": pr.updated_at,
            "merged_at": pr.merged_at,
            "mergeable": pr.mergeable,
            "mergeable_state": pr.mergeable_state,
            "author": pr.author,
            "labels": pr.labels or [],
            "review_count": pr.review_count,
            "comment_count": pr.comment_count,
        }
    except Exception as e:
        logger.error(f"Error getting PR {pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pull request: {e}")


@router.post("/{link_id}/pull-requests/{pr_number}/merge", response_model=dict)
async def merge_pull_request(
    link_id: str,
    pr_number: int,
    merge_method: str = Query("merge", regex="^(merge|squash|rebase)$"),
    commit_title: Optional[str] = None,
    commit_message: Optional[str] = None,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Merge a pull request.
    
    Args:
        link_id: Repository link ID
        pr_number: Pull request number
        merge_method: Merge method (merge, squash, rebase)
        commit_title: Custom commit title
        commit_message: Custom commit message
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        Merge result
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        result = await pr_manager.merge_pull_request(
            repo_full_name=link.repo_full_name,
            pr_number=pr_number,
            merge_method=merge_method,
            commit_title=commit_title,
            commit_message=commit_message,
            installation_id=installation_id,
        )
        
        return result
    except Exception as e:
        logger.error(f"Error merging PR {pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to merge pull request: {e}")


@router.post("/{link_id}/pull-requests/{pr_number}/review", response_model=dict)
async def create_pull_request_review(
    link_id: str,
    pr_number: int,
    state: str = Query(..., regex="^(APPROVE|REQUEST_CHANGES|COMMENT)$"),
    body: Optional[str] = Body(None),
    event: Optional[str] = Query(None, regex="^(APPROVE|REQUEST_CHANGES|COMMENT)$"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Create a pull request review.
    
    Args:
        link_id: Repository link ID
        pr_number: Pull request number
        state: Review state (APPROVE, REQUEST_CHANGES, COMMENT)
        body: Review body/comment
        event: Review event (overrides state if provided)
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        Created review
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    # Get body from request body if not provided
    review_body = body or ""
    
    try:
        review = await pr_manager.create_review(
            repo_full_name=link.repo_full_name,
            pr_number=pr_number,
            state=state,
            body=review_body,
            event=event,
            installation_id=installation_id,
        )
        
        return {
            "id": review.id,
            "state": review.state,
            "body": review.body,
            "author": review.author,
            "submitted_at": review.submitted_at,
        }
    except Exception as e:
        logger.error(f"Error creating review for PR {pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create review: {e}")


@router.post("/{link_id}/pull-requests/{pr_number}/comments", response_model=dict)
async def create_pull_request_comment(
    link_id: str,
    pr_number: int,
    body: str = Body(...),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Create a pull request comment.
    
    Args:
        link_id: Repository link ID
        pr_number: Pull request number
        body: Comment body
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        Created comment
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        comment = await pr_manager.create_comment(
            repo_full_name=link.repo_full_name,
            pr_number=pr_number,
            body=body,
            installation_id=installation_id,
        )
        
        return {
            "id": comment.id,
            "body": comment.body,
            "author": comment.author,
            "created_at": comment.created_at,
            "path": comment.path,
            "line": comment.line,
        }
    except Exception as e:
        logger.error(f"Error creating comment for PR {pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create comment: {e}")


@router.get("/{link_id}/pull-requests/{pr_number}/reviews", response_model=List[dict])
async def list_pull_request_reviews(
    link_id: str,
    pr_number: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    List pull request reviews.
    
    Args:
        link_id: Repository link ID
        pr_number: Pull request number
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        List of reviews
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        reviews = await pr_manager.list_reviews(
            repo_full_name=link.repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
        
        return [
            {
                "id": review.id,
                "state": review.state,
                "body": review.body,
                "author": review.author,
                "submitted_at": review.submitted_at,
            }
            for review in reviews
        ]
    except Exception as e:
        logger.error(f"Error listing reviews for PR {pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list reviews: {e}")


@router.get("/{link_id}/pull-requests/{pr_number}/comments", response_model=List[dict])
async def list_pull_request_comments(
    link_id: str,
    pr_number: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    pr_manager: PRManager = Depends(get_pr_manager),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    List pull request comments.
    
    Args:
        link_id: Repository link ID
        pr_number: Pull request number
        ctx: Workspace context
        pr_manager: PR manager instance
        session: Database session
    
    Returns:
        List of comments
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        comments = await pr_manager.list_comments(
            repo_full_name=link.repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
        
        return [
            {
                "id": comment.id,
                "body": comment.body,
                "author": comment.author,
                "created_at": comment.created_at,
                "path": comment.path,
                "line": comment.line,
            }
            for comment in comments
        ]
    except Exception as e:
        logger.error(f"Error listing comments for PR {pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list comments: {e}")

