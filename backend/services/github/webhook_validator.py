# -*- coding: utf-8 -*-
"""GitHub webhook signature validation."""

import hmac
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WebhookValidationError(Exception):
    """Raised when webhook validation fails."""
    pass


class WebhookValidator:
    """Validates GitHub webhook signatures using HMAC SHA256."""
    
    def __init__(self, secret: str):
        """
        Initialize the webhook validator.
        
        Args:
            secret: GitHub webhook secret
        """
        if not secret:
            raise ValueError("Webhook secret is required")
        self.secret = secret
    
    def validate_signature(self, payload: bytes, signature_header: Optional[str]) -> bool:
        """
        Validate GitHub webhook signature.
        
        Args:
            payload: Raw request body
            signature_header: X-Hub-Signature-256 header value (format: "sha256=<hex>")
        
        Returns:
            True if signature is valid, False otherwise
        
        Raises:
            WebhookValidationError: If signature format is invalid
        """
        if not signature_header:
            logger.warning("Missing X-Hub-Signature-256 header")
            return False
        
        try:
            # Extract signature from header (format: "sha256=<hex>")
            if not signature_header.startswith("sha256="):
                raise WebhookValidationError(f"Invalid signature format: {signature_header}")
            
            expected_signature = signature_header[7:]  # Remove "sha256=" prefix
            
            # Compute HMAC SHA256
            computed_signature = hmac.new(
                self.secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(computed_signature, expected_signature)
            
            if not is_valid:
                logger.warning("Webhook signature validation failed")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            raise WebhookValidationError(f"Signature validation error: {e}") from e
    
    def validate_event_type(self, event_type: Optional[str]) -> bool:
        """
        Validate GitHub event type.
        
        Args:
            event_type: X-GitHub-Event header value
        
        Returns:
            True if event type is supported, False otherwise
        """
        if not event_type:
            logger.warning("Missing X-GitHub-Event header")
            return False
        
        supported_events = {
            "push",
            "pull_request",
            "issues",
            "issue_comment",
            "create",
            "delete",
            "release",
            "workflow_run",
        }
        
        is_supported = event_type in supported_events
        
        if not is_supported:
            logger.debug(f"Unsupported event type: {event_type}")
        
        return is_supported

