# -*- coding: utf-8 -*-
"""GitHub Issues management router.

Endpoints for managing GitHub Issues:
- List issues
- Get issue details
- Create issue
- Update issue
- Close issue
- Create comment
- List comments
"""

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select

from backend.db.models import RepositoryLink, Project
from backend.db.models.enums import RepositoryProvider
from backend.db.session import get_session
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.services.github.issues_manager import (
    IssuesManager,
    IssueInfo,
    IssueComment,
    get_issues_manager,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["issues"])


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


@router.get("/{link_id}/issues", response_model=List[dict])
async def list_issues(
    link_id: str,
    state: str = Query("open", regex="^(open|closed|all)$"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    List issues for a repository.
    
    Args:
        link_id: Repository link ID
        state: Issue state filter (open, closed, all)
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        List of issues
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        issues = await issues_manager.list_issues(
            repo_full_name=link.repo_full_name,
            state=state,
            installation_id=installation_id,
        )
        
        return [
            {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "html_url": issue.html_url,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at,
                "closed_at": issue.closed_at,
                "author": issue.author,
                "labels": issue.labels or [],
                "assignees": issue.assignees or [],
                "comment_count": issue.comment_count,
            }
            for issue in issues
        ]
    except Exception as e:
        logger.error(f"Error listing issues: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list issues: {e}")


@router.get("/{link_id}/issues/{issue_number}", response_model=dict)
async def get_issue(
    link_id: str,
    issue_number: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get issue details.
    
    Args:
        link_id: Repository link ID
        issue_number: Issue number
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        Issue details
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        issue = await issues_manager.get_issue(
            repo_full_name=link.repo_full_name,
            issue_number=issue_number,
            installation_id=installation_id,
        )
        
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "html_url": issue.html_url,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "closed_at": issue.closed_at,
            "author": issue.author,
            "labels": issue.labels or [],
            "assignees": issue.assignees or [],
            "comment_count": issue.comment_count,
        }
    except Exception as e:
        logger.error(f"Error getting issue {issue_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get issue: {e}")


@router.post("/{link_id}/issues", response_model=dict, status_code=201)
async def create_issue(
    link_id: str,
    title: str = Body(...),
    body: Optional[str] = Body(None),
    labels: Optional[List[str]] = Body(None),
    assignees: Optional[List[str]] = Body(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Create an issue.
    
    Args:
        link_id: Repository link ID
        title: Issue title
        body: Issue body
        labels: Issue labels
        assignees: Issue assignees
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        Created issue
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        issue = await issues_manager.create_issue(
            repo_full_name=link.repo_full_name,
            title=title,
            body=body,
            labels=labels,
            assignees=assignees,
            installation_id=installation_id,
        )
        
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "html_url": issue.html_url,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "closed_at": issue.closed_at,
            "author": issue.author,
            "labels": issue.labels or [],
            "assignees": issue.assignees or [],
            "comment_count": issue.comment_count,
        }
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create issue: {e}")


@router.patch("/{link_id}/issues/{issue_number}", response_model=dict)
async def update_issue(
    link_id: str,
    issue_number: int,
    title: Optional[str] = Body(None),
    body: Optional[str] = Body(None),
    state: Optional[str] = Body(None, regex="^(open|closed)$"),
    labels: Optional[List[str]] = Body(None),
    assignees: Optional[List[str]] = Body(None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Update an issue.
    
    Args:
        link_id: Repository link ID
        issue_number: Issue number
        title: New title
        body: New body
        state: New state (open, closed)
        labels: New labels
        assignees: New assignees
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        Updated issue
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        issue = await issues_manager.update_issue(
            repo_full_name=link.repo_full_name,
            issue_number=issue_number,
            title=title,
            body=body,
            state=state,
            labels=labels,
            assignees=assignees,
            installation_id=installation_id,
        )
        
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "html_url": issue.html_url,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "closed_at": issue.closed_at,
            "author": issue.author,
            "labels": issue.labels or [],
            "assignees": issue.assignees or [],
            "comment_count": issue.comment_count,
        }
    except Exception as e:
        logger.error(f"Error updating issue {issue_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update issue: {e}")


@router.post("/{link_id}/issues/{issue_number}/close", response_model=dict)
async def close_issue(
    link_id: str,
    issue_number: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Close an issue.
    
    Args:
        link_id: Repository link ID
        issue_number: Issue number
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        Closed issue
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        issue = await issues_manager.close_issue(
            repo_full_name=link.repo_full_name,
            issue_number=issue_number,
            installation_id=installation_id,
        )
        
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "html_url": issue.html_url,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "closed_at": issue.closed_at,
            "author": issue.author,
            "labels": issue.labels or [],
            "assignees": issue.assignees or [],
            "comment_count": issue.comment_count,
        }
    except Exception as e:
        logger.error(f"Error closing issue {issue_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close issue: {e}")


@router.post("/{link_id}/issues/{issue_number}/comments", response_model=dict)
async def create_issue_comment(
    link_id: str,
    issue_number: int,
    body: str = Body(...),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Create an issue comment.
    
    Args:
        link_id: Repository link ID
        issue_number: Issue number
        body: Comment body
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        Created comment
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        comment = await issues_manager.create_comment(
            repo_full_name=link.repo_full_name,
            issue_number=issue_number,
            body=body,
            installation_id=installation_id,
        )
        
        return {
            "id": comment.id,
            "body": comment.body,
            "author": comment.author,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
        }
    except Exception as e:
        logger.error(f"Error creating comment for issue {issue_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create comment: {e}")


@router.get("/{link_id}/issues/{issue_number}/comments", response_model=List[dict])
async def list_issue_comments(
    link_id: str,
    issue_number: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    issues_manager: IssuesManager = Depends(get_issues_manager),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    List issue comments.
    
    Args:
        link_id: Repository link ID
        issue_number: Issue number
        ctx: Workspace context
        issues_manager: Issues manager instance
        session: Database session
    
    Returns:
        List of comments
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        comments = await issues_manager.list_comments(
            repo_full_name=link.repo_full_name,
            issue_number=issue_number,
            installation_id=installation_id,
        )
        
        return [
            {
                "id": comment.id,
                "body": comment.body,
                "author": comment.author,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
            }
            for comment in comments
        ]
    except Exception as e:
        logger.error(f"Error listing comments for issue {issue_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list comments: {e}")

