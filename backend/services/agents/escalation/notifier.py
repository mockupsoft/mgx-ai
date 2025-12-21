# -*- coding: utf-8 -*-
"""
Escalation Notifier

Sends notifications for escalation events via WebSocket, Email, and Slack.
"""

import logging
from typing import Any, Dict, Optional

from backend.db.models import (
    EscalationEvent,
    EscalationRule,
)
from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster

logger = logging.getLogger(__name__)


class EscalationNotifier:
    """
    Handles notifications for escalation events.
    
    Supports:
    - WebSocket real-time notifications
    - Email notifications
    - Slack notifications
    """
    
    def __init__(self):
        """Initialize the escalation notifier."""
        self.broadcaster = get_event_broadcaster()
        logger.info("EscalationNotifier initialized")
    
    async def notify_escalation_created(
        self,
        event: EscalationEvent,
        rule: Optional[EscalationRule] = None,
    ) -> None:
        """
        Notify about a new escalation.
        
        Args:
            event: Escalation event
            rule: Escalation rule that triggered (optional)
        """
        notification_data = {
            "escalation_id": event.id,
            "severity": event.severity.value,
            "reason": event.reason.value,
            "status": event.status.value,
            "workspace_id": event.workspace_id,
            "project_id": event.project_id,
            "task_id": event.task_id,
            "source_agent_id": event.source_agent_id,
            "trigger_data": event.trigger_data,
        }
        
        if rule:
            notification_data["rule_name"] = rule.name
            notification_data["rule_id"] = rule.id
        
        # Send WebSocket notification
        await self._send_websocket_notification(
            event.workspace_id,
            "escalation_created",
            notification_data
        )
        
        # Send email notification if configured
        if rule and rule.notify_email:
            await self._send_email_notification(
                event, rule, "escalation_created"
            )
        
        # Send Slack notification if configured
        if rule and rule.notify_slack:
            await self._send_slack_notification(
                event, rule, "escalation_created"
            )
    
    async def notify_escalation_assigned(
        self,
        event: EscalationEvent,
        target_agent_id: str,
    ) -> None:
        """
        Notify about escalation assignment.
        
        Args:
            event: Escalation event
            target_agent_id: ID of assigned agent
        """
        notification_data = {
            "escalation_id": event.id,
            "severity": event.severity.value,
            "reason": event.reason.value,
            "status": event.status.value,
            "target_agent_id": target_agent_id,
            "workspace_id": event.workspace_id,
            "project_id": event.project_id,
        }
        
        # Send WebSocket notification
        await self._send_websocket_notification(
            event.workspace_id,
            "escalation_assigned",
            notification_data
        )
    
    async def notify_escalation_resolved(
        self,
        event: EscalationEvent,
        resolution_data: Dict[str, Any],
    ) -> None:
        """
        Notify about escalation resolution.
        
        Args:
            event: Escalation event
            resolution_data: Resolution details
        """
        notification_data = {
            "escalation_id": event.id,
            "severity": event.severity.value,
            "reason": event.reason.value,
            "status": event.status.value,
            "target_agent_id": event.target_agent_id,
            "resolution_data": resolution_data,
            "time_to_resolve_seconds": event.time_to_resolve_seconds,
            "workspace_id": event.workspace_id,
            "project_id": event.project_id,
        }
        
        # Send WebSocket notification
        await self._send_websocket_notification(
            event.workspace_id,
            "escalation_resolved",
            notification_data
        )
    
    async def notify_escalation_failed(
        self,
        event: EscalationEvent,
        error_message: str,
    ) -> None:
        """
        Notify about escalation failure.
        
        Args:
            event: Escalation event
            error_message: Error message
        """
        notification_data = {
            "escalation_id": event.id,
            "severity": event.severity.value,
            "reason": event.reason.value,
            "status": event.status.value,
            "error_message": error_message,
            "workspace_id": event.workspace_id,
            "project_id": event.project_id,
        }
        
        # Send WebSocket notification
        await self._send_websocket_notification(
            event.workspace_id,
            "escalation_failed",
            notification_data
        )
    
    async def _send_websocket_notification(
        self,
        workspace_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Send WebSocket notification."""
        try:
            # Map event type to EventTypeEnum
            event_type_map = {
                "escalation_created": EventTypeEnum.ESCALATION_CREATED,
                "escalation_assigned": EventTypeEnum.ESCALATION_ASSIGNED,
                "escalation_resolved": EventTypeEnum.ESCALATION_RESOLVED,
                "escalation_failed": EventTypeEnum.ESCALATION_FAILED,
            }
            
            # Get proper event type enum
            enum_type = event_type_map.get(event_type, EventTypeEnum.AGENT_ACTIVITY)
            
            payload = EventPayload(
                event_type=enum_type,
                workspace_id=workspace_id,
                agent_id=data.get("target_agent_id"),
                task_id=data.get("task_id"),
                run_id=data.get("task_run_id"),
                data=data,
            )
            
            await self.broadcaster.publish(payload)
            logger.debug(f"Sent WebSocket notification: {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {str(e)}")
    
    async def _send_email_notification(
        self,
        event: EscalationEvent,
        rule: EscalationRule,
        event_type: str,
    ) -> None:
        """Send email notification."""
        try:
            # Get email configuration from rule
            email_config = rule.notification_config.get("email", {})
            recipients = email_config.get("recipients", [])
            
            if not recipients:
                logger.debug("No email recipients configured")
                return
            
            # Build email content
            subject = self._build_email_subject(event, event_type)
            body = self._build_email_body(event, rule, event_type)
            
            # TODO: Integrate with email service
            # For now, just log
            logger.info(
                f"Email notification: {subject} to {', '.join(recipients)}"
            )
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    async def _send_slack_notification(
        self,
        event: EscalationEvent,
        rule: EscalationRule,
        event_type: str,
    ) -> None:
        """Send Slack notification."""
        try:
            # Get Slack configuration from rule
            slack_config = rule.notification_config.get("slack", {})
            webhook_url = slack_config.get("webhook_url")
            channel = slack_config.get("channel")
            
            if not webhook_url:
                logger.debug("No Slack webhook configured")
                return
            
            # Build Slack message
            message = self._build_slack_message(event, rule, event_type)
            
            # TODO: Integrate with Slack webhook
            # For now, just log
            logger.info(
                f"Slack notification: {event_type} to {channel or 'default'}"
            )
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
    
    def _build_email_subject(
        self,
        event: EscalationEvent,
        event_type: str,
    ) -> str:
        """Build email subject."""
        severity = event.severity.value.upper()
        reason = event.reason.value.replace("_", " ").title()
        
        if event_type == "escalation_created":
            return f"[{severity}] Escalation: {reason}"
        elif event_type == "escalation_assigned":
            return f"[{severity}] Escalation Assigned: {reason}"
        elif event_type == "escalation_resolved":
            return f"[{severity}] Escalation Resolved: {reason}"
        else:
            return f"[{severity}] Escalation Update: {reason}"
    
    def _build_email_body(
        self,
        event: EscalationEvent,
        rule: EscalationRule,
        event_type: str,
    ) -> str:
        """Build email body."""
        lines = [
            f"Escalation Event: {event_type}",
            f"",
            f"Severity: {event.severity.value.upper()}",
            f"Reason: {event.reason.value.replace('_', ' ').title()}",
            f"Status: {event.status.value.replace('_', ' ').title()}",
            f"",
            f"Rule: {rule.name}",
            f"Workspace ID: {event.workspace_id}",
        ]
        
        if event.project_id:
            lines.append(f"Project ID: {event.project_id}")
        
        if event.task_id:
            lines.append(f"Task ID: {event.task_id}")
        
        if event.source_agent_id:
            lines.append(f"Source Agent: {event.source_agent_id}")
        
        if event.target_agent_id:
            lines.append(f"Target Agent: {event.target_agent_id}")
        
        lines.append("")
        lines.append("Trigger Data:")
        for key, value in event.trigger_data.items():
            lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)
    
    def _build_slack_message(
        self,
        event: EscalationEvent,
        rule: EscalationRule,
        event_type: str,
    ) -> Dict[str, Any]:
        """Build Slack message."""
        severity_emoji = {
            "low": ":information_source:",
            "medium": ":warning:",
            "high": ":exclamation:",
            "critical": ":rotating_light:",
        }
        
        emoji = severity_emoji.get(event.severity.value, ":bell:")
        
        return {
            "text": f"{emoji} Escalation: {event.reason.value}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Escalation: {event.reason.value}",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{event.severity.value.upper()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Status:*\n{event.status.value}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Rule:*\n{rule.name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Escalation ID:*\n{event.id}"
                        },
                    ]
                }
            ]
        }


__all__ = ["EscalationNotifier"]
