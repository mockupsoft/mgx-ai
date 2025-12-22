# -*- coding: utf-8 -*-
"""Activity feed router.

Endpoints for GitHub activity feed:
- Get activity feed (combined)
- Get commit history
- Get timeline view
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
from backend.services.github.activity_feed import (
    ActivityFeed,
    ActivityEvent,
    get_activity_feed,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["activity"])


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


@router.get("/{link_id}/activity", response_model=List[dict])
async def get_activity_feed(
    link_id: str,
    limit: int = Query(50, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    activity_feed: ActivityFeed = Depends(get_activity_feed),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    Get combined activity feed (commits, PRs, issues).
    
    Args:
        link_id: Repository link ID
        limit: Maximum number of events
        ctx: Workspace context
        activity_feed: Activity feed instance
        session: Database session
    
    Returns:
        List of activity events
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        events = await activity_feed.get_activity_feed(
            repo_full_name=link.repo_full_name,
            limit=limit,
            installation_id=installation_id,
        )
        
        return [
            {
                "id": event.id,
                "type": event.type,
                "timestamp": event.timestamp,
                "actor": event.actor,
                "title": event.title,
                "body": event.body,
                "url": event.url,
                "metadata": event.metadata or {},
            }
            for event in events
        ]
    except Exception as e:
        logger.error(f"Error getting activity feed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get activity feed: {e}")


@router.get("/{link_id}/commits", response_model=List[dict])
async def get_commit_history(
    link_id: str,
    branch: str = Query("main"),
    limit: int = Query(50, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    activity_feed: ActivityFeed = Depends(get_activity_feed),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    Get commit history.
    
    Args:
        link_id: Repository link ID
        branch: Branch name
        limit: Maximum number of commits
        ctx: Workspace context
        activity_feed: Activity feed instance
        session: Database session
    
    Returns:
        List of commit events
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        events = await activity_feed.get_commit_history(
            repo_full_name=link.repo_full_name,
            branch=branch,
            limit=limit,
            installation_id=installation_id,
        )
        
        return [
            {
                "id": event.id,
                "type": event.type,
                "timestamp": event.timestamp,
                "actor": event.actor,
                "title": event.title,
                "body": event.body,
                "url": event.url,
                "metadata": event.metadata or {},
            }
            for event in events
        ]
    except Exception as e:
        logger.error(f"Error getting commit history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get commit history: {e}")


@router.get("/{link_id}/activity/timeline", response_model=List[dict])
async def get_timeline_view(
    link_id: str,
    limit: int = Query(50, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    activity_feed: ActivityFeed = Depends(get_activity_feed),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """
    Get timeline view of activity (same as activity feed, but with timeline formatting).
    
    Args:
        link_id: Repository link ID
        limit: Maximum number of events
        ctx: Workspace context
        activity_feed: Activity feed instance
        session: Database session
    
    Returns:
        List of activity events with timeline formatting
    """
    link = await _get_repository_link(ctx, link_id, session)
    
    installation_id = link.auth_payload.get("installation_id") if link.auth_payload else None
    
    try:
        events = await activity_feed.get_activity_feed(
            repo_full_name=link.repo_full_name,
            limit=limit,
            installation_id=installation_id,
        )
        
        return [
            {
                "id": event.id,
                "type": event.type,
                "timestamp": event.timestamp,
                "actor": event.actor,
                "title": event.title,
                "body": event.body,
                "url": event.url,
                "metadata": event.metadata or {},
            }
            for event in events
        ]
    except Exception as e:
        logger.error(f"Error getting timeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get timeline: {e}")

