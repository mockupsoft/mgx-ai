# -*- coding: utf-8 -*-
"""GitHub webhook event processing."""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from backend.services.events import get_event_broadcaster
from backend.services.github.webhook_validator import WebhookValidationError
from backend.schemas import EventPayload, EventTypeEnum

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """Processes GitHub webhook events."""
    
    def __init__(self):
        """Initialize the webhook processor."""
        self._event_broadcaster = get_event_broadcaster()
    
    def parse_event(self, payload: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """
        Parse GitHub webhook event payload.
        
        Args:
            payload: GitHub webhook payload (parsed JSON)
            event_type: GitHub event type (push, pull_request, etc.)
        
        Returns:
            Parsed event data
        """
        try:
            if event_type == "push":
                return self._parse_push_event(payload)
            elif event_type == "pull_request":
                return self._parse_pull_request_event(payload)
            elif event_type == "issues":
                return self._parse_issues_event(payload)
            elif event_type == "issue_comment":
                return self._parse_issue_comment_event(payload)
            elif event_type == "create":
                return self._parse_create_event(payload)
            elif event_type == "delete":
                return self._parse_delete_event(payload)
            elif event_type == "release":
                return self._parse_release_event(payload)
            elif event_type == "workflow_run":
                return self._parse_workflow_run_event(payload)
            else:
                logger.warning(f"Unsupported event type: {event_type}")
                return {
                    "event_type": event_type,
                    "raw_payload": payload,
                }
        except Exception as e:
            logger.error(f"Error parsing {event_type} event: {e}")
            raise
    
    def _parse_push_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse push event."""
        repo = payload.get("repository", {})
        return {
            "event_type": "push",
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "ref": payload.get("ref"),
            "before": payload.get("before"),
            "after": payload.get("after"),
            "commits": payload.get("commits", []),
            "pusher": payload.get("pusher", {}),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_pull_request_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse pull request event."""
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        return {
            "event_type": "pull_request",
            "action": payload.get("action"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "pr_number": pr.get("number"),
            "pr_id": pr.get("id"),
            "pr_state": pr.get("state"),
            "pr_title": pr.get("title"),
            "pr_body": pr.get("body"),
            "pr_head": pr.get("head", {}),
            "pr_base": pr.get("base", {}),
            "pr_html_url": pr.get("html_url"),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_issues_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse issues event."""
        issue = payload.get("issue", {})
        repo = payload.get("repository", {})
        return {
            "event_type": "issues",
            "action": payload.get("action"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "issue_number": issue.get("number"),
            "issue_id": issue.get("id"),
            "issue_state": issue.get("state"),
            "issue_title": issue.get("title"),
            "issue_body": issue.get("body"),
            "issue_html_url": issue.get("html_url"),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_issue_comment_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse issue comment event."""
        issue = payload.get("issue", {})
        comment = payload.get("comment", {})
        repo = payload.get("repository", {})
        return {
            "event_type": "issue_comment",
            "action": payload.get("action"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "issue_number": issue.get("number"),
            "comment_id": comment.get("id"),
            "comment_body": comment.get("body"),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_create_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse create event (branch/tag creation)."""
        repo = payload.get("repository", {})
        return {
            "event_type": "create",
            "ref_type": payload.get("ref_type"),  # branch or tag
            "ref": payload.get("ref"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_delete_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse delete event (branch/tag deletion)."""
        repo = payload.get("repository", {})
        return {
            "event_type": "delete",
            "ref_type": payload.get("ref_type"),  # branch or tag
            "ref": payload.get("ref"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_release_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse release event."""
        release = payload.get("release", {})
        repo = payload.get("repository", {})
        return {
            "event_type": "release",
            "action": payload.get("action"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "release_tag": release.get("tag_name"),
            "release_name": release.get("name"),
            "release_body": release.get("body"),
            "release_html_url": release.get("html_url"),
            "sender": payload.get("sender", {}),
        }
    
    def _parse_workflow_run_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse workflow run event."""
        workflow_run = payload.get("workflow_run", {})
        repo = payload.get("repository", {})
        return {
            "event_type": "workflow_run",
            "action": payload.get("action"),
            "repo_full_name": repo.get("full_name"),
            "repo_id": repo.get("id"),
            "workflow_run_id": workflow_run.get("id"),
            "workflow_run_status": workflow_run.get("status"),
            "workflow_run_conclusion": workflow_run.get("conclusion"),
            "workflow_name": workflow_run.get("name"),
            "sender": payload.get("sender", {}),
        }
    
    async def process_event(
        self,
        event_data: Dict[str, Any],
        delivery_id: str,
        event_type: str,
    ) -> Dict[str, Any]:
        """
        Process webhook event and broadcast to subscribers.
        
        Args:
            event_data: Parsed event data
            delivery_id: GitHub delivery ID
            event_type: GitHub event type
        
        Returns:
            Processing result
        """
        try:
            # Map GitHub event types to internal event types
            event_type_map = {
                "push": EventTypeEnum.GIT_PUSH_SUCCESS,
                "pull_request": EventTypeEnum.PULL_REQUEST_OPENED,
                "issues": "github_issue_event",
                "issue_comment": "github_issue_comment",
                "create": "github_create_event",
                "delete": "github_delete_event",
                "release": "github_release_event",
                "workflow_run": "github_workflow_run",
            }
            
            # Use EventTypeEnum if available, otherwise use string
            mapped_type = event_type_map.get(event_type, "github_webhook_event")
            if isinstance(mapped_type, EventTypeEnum):
                internal_event_type = mapped_type.value
            else:
                internal_event_type = mapped_type
            
            # Create event payload
            event_payload = EventPayload(
                event_type=internal_event_type,
                task_id=None,
                run_id=None,
                data={
                    **event_data,
                    "delivery_id": delivery_id,
                    "github_event_type": event_type,
                },
                message=f"GitHub {event_type} event: {delivery_id}",
            )
            
            # Broadcast event
            repo_full_name = event_data.get("repo_full_name")
            if repo_full_name:
                channel = f"repo:{repo_full_name}"
            else:
                channel = "github_webhooks"
            
            await self._event_broadcaster.publish(event_payload, channel=channel)
            
            logger.info(f"Processed {event_type} event: {delivery_id}")
            
            return {
                "success": True,
                "event_type": event_type,
                "delivery_id": delivery_id,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {e}")
            return {
                "success": False,
                "error": str(e),
                "event_type": event_type,
                "delivery_id": delivery_id,
            }

