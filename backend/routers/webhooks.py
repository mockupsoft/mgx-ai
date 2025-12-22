# -*- coding: utf-8 -*-
"""GitHub webhook router.

Handles incoming GitHub webhook events with signature verification,
event processing, and real-time broadcasting.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select

from backend.config import settings
from backend.db.models import RepositoryLink, GitHubWebhookEvent
from backend.db.models.enums import RepositoryProvider
from backend.db.session import get_session
from backend.services.github.webhook_validator import WebhookValidator, WebhookValidationError
from backend.services.github.webhook_processor import WebhookProcessor
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


async def get_webhook_validator() -> WebhookValidator:
    """Get webhook validator instance."""
    secret = settings.github_webhook_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub webhook secret is not configured",
        )
    return WebhookValidator(secret)


@router.post("/github")
async def receive_github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    validator: WebhookValidator = Depends(get_webhook_validator),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Receive and process GitHub webhook events.
    
    Validates signature, parses event, stores in database, and broadcasts
    to WebSocket subscribers.
    
    Args:
        request: FastAPI request object
        x_github_event: GitHub event type header
        x_github_delivery: GitHub delivery ID header
        x_hub_signature_256: GitHub signature header
        validator: Webhook validator instance
        session: Database session
    
    Returns:
        Processing result
    """
    # Read raw body for signature verification
    body_bytes = await request.body()
    
    # Validate signature
    try:
        is_valid = validator.validate_signature(body_bytes, x_hub_signature_256)
        if not is_valid:
            logger.warning(f"Invalid webhook signature for delivery {x_github_delivery}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
    except WebhookValidationError as e:
        logger.error(f"Webhook validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signature validation error: {e}",
        ) from e
    
    # Validate event type
    if not validator.validate_event_type(x_github_event):
        logger.warning(f"Unsupported event type: {x_github_event}")
        # Still return 200 to acknowledge receipt, but don't process
        return {
            "success": True,
            "event_type": x_github_event,
            "delivery_id": x_github_delivery,
            "message": "Event received but not processed (unsupported type)",
        }
    
    # Parse payload
    try:
        payload = json.loads(body_bytes.decode('utf-8'))
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from e
    
    # Check for duplicate delivery ID
    if x_github_delivery:
        existing = await session.execute(
            select(GitHubWebhookEvent).where(
                GitHubWebhookEvent.delivery_id == x_github_delivery
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(f"Duplicate webhook delivery ID: {x_github_delivery}")
            return {
                "success": True,
                "event_type": x_github_event,
                "delivery_id": x_github_delivery,
                "message": "Event already processed",
            }
    
    # Extract repository info
    repo_full_name = payload.get("repository", {}).get("full_name")
    
    # Try to match with repository link
    repository_link_id = None
    if repo_full_name:
        result = await session.execute(
            select(RepositoryLink).where(
                RepositoryLink.provider == RepositoryProvider.GITHUB,
                RepositoryLink.repo_full_name == repo_full_name,
            )
        )
        repository_link = result.scalar_one_or_none()
        if repository_link:
            repository_link_id = repository_link.id
    
    # Process event
    processor = WebhookProcessor()
    try:
        parsed_data = processor.parse_event(payload, x_github_event or "unknown")
        process_result = await processor.process_event(
            parsed_data,
            x_github_delivery or "unknown",
            x_github_event or "unknown",
        )
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}", exc_info=True)
        process_result = {
            "success": False,
            "error": str(e),
        }
    
    # Store event in database
    webhook_event = GitHubWebhookEvent(
        delivery_id=x_github_delivery or "unknown",
        event_type=x_github_event or "unknown",
        repository_id=repository_link_id,
        repo_full_name=repo_full_name,
        payload=payload,
        parsed_data=parsed_data if 'parsed_data' in locals() else None,
        processed=process_result.get("success", False),
        processed_at=datetime.now(timezone.utc) if process_result.get("success") else None,
        error_message=process_result.get("error"),
    )
    
    session.add(webhook_event)
    await session.commit()
    
    # Return result
    if process_result.get("success"):
        return {
            "success": True,
            "event_type": x_github_event,
            "delivery_id": x_github_delivery,
            "processed_at": process_result.get("processed_at"),
        }
    else:
        return {
            "success": False,
            "event_type": x_github_event,
            "delivery_id": x_github_delivery,
            "error": process_result.get("error"),
        }


@router.get("/github/events")
async def list_webhook_events(
    repo_full_name: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    List webhook events (for debugging and audit).
    
    Args:
        repo_full_name: Filter by repository
        event_type: Filter by event type
        limit: Maximum number of events to return
        session: Database session
    
    Returns:
        List of webhook events
    """
    from sqlalchemy import func
    
    query = select(GitHubWebhookEvent)
    
    if repo_full_name:
        query = query.where(GitHubWebhookEvent.repo_full_name == repo_full_name)
    
    if event_type:
        query = query.where(GitHubWebhookEvent.event_type == event_type)
    
    total_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(total_query)).scalar_one()
    
    result = await session.execute(
        query.order_by(GitHubWebhookEvent.created_at.desc()).limit(limit)
    )
    events = result.scalars().all()
    
    return {
        "items": [event.to_dict() for event in events],
        "total": total,
        "limit": limit,
    }

