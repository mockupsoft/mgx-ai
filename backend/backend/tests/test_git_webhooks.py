# -*- coding: utf-8 -*-
"""GitHub Webhook E2E Tests.

Comprehensive testing of GitHub webhook event reception, parsing, processing,
signature verification, and UI event emission.

All webhook interactions are tested with proper signature verification to ensure
security and data integrity.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock

import pytest
import responses
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster


def generate_github_signature(payload: str, secret: str, delivery_id: str = None) -> Dict[str, str]:
    """Generate GitHub webhook signature headers."""
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Hub-Signature-256": f"sha256={signature}",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": delivery_id or "12345-67890",
        "Content-Type": "application/json"
    }
    
    return headers


def generate_pr_signature(payload: str, secret: str, action: str = "opened") -> Dict[str, str]:
    """Generate GitHub PR webhook signature headers."""
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Hub-Signature-256": f"sha256={signature}",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "pr-12345-67890",
        "X-GitHub-Hook-ID": "1",
        "Content-Type": "application/json"
    }
    
    return headers


class TestWebhookReception:
    """Test GitHub webhook reception and parsing."""
    
    def test_push_webhook_received(self, client, db_session):
        """Test push webhook reception and parsing."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        push_event = {
            "ref": "refs/heads/mgx/add-auth/run-1",
            "before": "0000000000000000000000000000000000000000",
            "after": "abc123def456789012345678901234567890abcd",
            "repository": {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "test-user/test-repo",
                "private": False
            },
            "pusher": {
                "name": "mgx-agent",
                "email": "agent@mgx.dev"
            },
            "sender": {
                "login": "mgx-agent",
                "id": 99999
            }
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["event_type"] == "push"
        assert "abc123def456789012345678901234567890abcd" in result["commit_sha"]
    
    def test_pr_webhook_received(self, client, db_session):
        """Test pull request webhook reception."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        pr_event = {
            "action": "opened",
            "number": 42,
            "pull_request": {
                "id": 123456,
                "number": 42,
                "state": "open",
                "title": "feat: Implement authentication",
                "body": "## Changes\\n- Add login endpoint\\n- Add JWT validation",
                "head": {
                    "ref": "mgx/add-auth/run-1",
                    "sha": "abc123def456"
                },
                "base": {
                    "ref": "main",
                    "sha": "def456abc123"
                },
                "html_url": "https://github.com/test-user/test-repo/pull/42",
                "created_at": "2024-01-01T12:00:00Z"
            },
            "repository": {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "test-user/test-repo"
            },
            "sender": {
                "login": "mgx-agent",
                "id": 99999
            }
        }
        
        payload = json.dumps(pr_event)
        headers = generate_pr_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["event_type"] == "pull_request"
        assert result["action"] == "opened"
        assert result["pr_number"] == 42
    
    def test_pull_request_review_webhook(self, client, db_session):
        """Test pull request review webhook."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        review_event = {
            "action": "submitted",
            "review": {
                "id": 987654,
                "state": "approved",
                "commit_id": "abc123def456",
                "body": "Looks good! Approved.",
                "user": {
                    "login": "reviewer",
                    "id": 88888
                }
            },
            "pull_request": {
                "number": 42,
                "title": "feat: Implement authentication",
                "head": {
                    "ref": "mgx/add-auth/run-1",
                    "sha": "abc123def456"
                },
                "base": {
                    "ref": "main",
                    "sha": "def456abc123"
                }
            },
            "repository": {
                "full_name": "test-user/test-repo"
            },
            "sender": {
                "login": "reviewer"
            }
        }
        
        payload = json.dumps(review_event)
        headers = generate_github_signature(payload, webhook_secret)
        headers["X-GitHub-Event"] = "pull_request_review"
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["event_type"] == "pull_request_review"
        assert result["review_state"] == "approved"
        assert result["pr_number"] == 42
    
    def test_commit_comment_webhook(self, client, db_session):
        """Test commit comment webhook."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        comment_event = {
            "action": "created",
            "comment": {
                "id": 555555,
                "body": "This implementation looks good!",
                "commit_id": "abc123def456",
                "user": {
                    "login": "reviewer",
                    "id": 88888
                },
                "created_at": "2024-01-01T13:00:00Z"
            },
            "repository": {
                "full_name": "test-user/test-repo"
            },
            "sender": {
                "login": "reviewer"
            }
        }
        
        payload = json.dumps(comment_event)
        headers = generate_github_signature(payload, webhook_secret)
        headers["X-GitHub-Event"] = "commit_comment"
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["event_type"] == "commit_comment"
        assert result["comment_id"] == 555555


class TestWebhookProcessing:
    """Test webhook processing and data extraction."""
    
    def test_webhook_payload_parsed_correctly(self, client, db_session):
        """Test webhook payload parsing and data extraction."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        push_event = {
            "ref": "refs/heads/mgx/add-auth/run-1",
            "before": "old_sha",
            "after": "new_commit_sha_12345",
            "repository": {
                "full_name": "test-user/test-repo",
                "id": 123456789
            },
            "pusher": {
                "name": "mgx-agent",
                "email": "agent@mgx.dev"
            },
            "commits": [
                {
                    "id": "new_commit_sha_12345",
                    "message": "feat(auth): Add login endpoint",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "author": {
                        "name": "MGX Agent",
                        "email": "agent@mgx.dev"
                    }
                }
            ]
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["branch_name"] == "mgx/add-auth/run-1"
        assert result["commit_sha"] == "new_commit_sha_12345"
        assert result["author"] == "MGX Agent"
        assert result["timestamp"] == "2024-01-01T12:00:00Z"
    
    def test_commit_hash_extraction(self, client, db_session):
        """Test commit hash extraction from webhook."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        push_event = {
            "after": "abc123def456789012345678901234567890abcd",
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["commit_sha"] == "abc123def456789012345678901234567890abcd"
    
    def test_branch_name_extraction(self, client, db_session):
        """Test branch name extraction from webhook."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        push_event = {
            "ref": "refs/heads/mgx/feature-branch/run-5",
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["branch_name"] == "mgx/feature-branch/run-5"
    
    def test_author_information_capture(self, client, db_session):
        """Test author information capture from webhook."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        push_event = {
            "pusher": {
                "name": "mgx-agent",
                "email": "agent@mgx.dev"
            },
            "sender": {
                "login": "developer",
                "id": 88888,
                "avatar_url": "https://avatars.githubusercontent.com/u/88888"
            },
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["author"] == "mgx-agent"
        assert result["author_email"] == "agent@mgx.dev"
        assert result["sender"] == "developer"
    
    def test_pr_metadata_storage(self, client, db_session):
        """Test PR metadata extraction and storage."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        pr_event = {
            "action": "opened",
            "number": 42,
            "pull_request": {
                "id": 123456,
                "number": 42,
                "state": "open",
                "title": "feat: Implement authentication",
                "user": {"login": "mgx-agent"},
                "head": {
                    "ref": "mgx/add-auth/run-1",
                    "sha": "abc123def456"
                },
                "base": {
                    "ref": "main",
                    "sha": "def456abc123"
                },
                "html_url": "https://github.com/test-user/test-repo/pull/42",
                "mergeable": True,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:30:00Z",
                "labels": [{"name": "enhancement"}],
                "assignees": [{"login": "team-lead"}],
                "requested_reviewers": [{"login": "security-team"}]
            },
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(pr_event)
        headers = generate_pr_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["pr_number"] == 42
        assert result["pr_title"] == "feat: Implement authentication"
        assert result["pr_url"] == "https://github.com/test-user/test-repo/pull/42"
        assert result["mergeable"] is True
        assert len(result.get("labels", [])) > 0


class TestWebhookSignatureVerification:
    """Test webhook signature verification."""
    
    def test_valid_signature_accepted(self, client, db_session):
        """Test valid webhook signature is accepted."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        payload = json.dumps({"test": "data"})
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json()["signature_valid"] is True
    
    def test_invalid_signature_rejected(self, client, db_session):
        """Test invalid webhook signature is rejected."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        payload = json.dumps({"test": "data"})
        
        # Generate signature with wrong secret
        wrong_signature = hmac.new(
            "wrong_secret".encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-Hub-Signature-256": f"sha256={wrong_signature}",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "12345",
            "Content-Type": "application/json"
        }
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 401
        assert "invalid signature" in response.json()["detail"].lower()
    
    def test_missing_signature_rejected(self, client, db_session):
        """Test missing webhook signature is rejected."""
        # Arrange
        payload = json.dumps({"test": "data"})
        headers = {
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "12345",
            "Content-Type": "application/json"
            # Missing X-Hub-Signature-256
        }
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 401
        assert "signature" in response.json()["detail"].lower()
    
    def test_signature_with_different_payload(self, client, db_session):
        """Test signature verification fails with tampered payload."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        original_payload = json.dumps({"original": "data"})
        headers = generate_github_signature(original_payload, webhook_secret)
        
        # Send different payload with original signature
        tampered_payload = json.dumps({"tampered": "data"})
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=tampered_payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 401
        assert "signature mismatch" in response.json()["detail"].lower()


class TestEmergencyWebhookHandling:
    """Test webhook handling for edge cases and errors."""
    
    def test_webhook_with_malformed_json(self, client, db_session):
        """Test webhook with malformed JSON payload."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        malformed_json = '{"incomplete":}'
        headers = generate_github_signature(malformed_json, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=malformed_json,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 400
        assert "json" in response.json()["detail"].lower()
    
    def test_webhook_with_empty_payload(self, client, db_session):
        """Test webhook with empty payload."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        empty_payload = ""
        
        # Generate signature for empty payload
        signature = hmac.new(
            webhook_secret.encode('utf-8'),
            empty_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "12345",
            "Content-Type": "application/json"
        }
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=empty_payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 400
    
    def test_webhook_with_unknown_event_type(self, client, db_session):
        """Test webhook with unknown event type."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        unknown_event = {
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(unknown_event)
        headers = generate_github_signature(payload, webhook_secret)
        headers["X-GitHub-Event"] = "unknown_event_type"
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 400
        assert result["event_type"] == "unknown"
        assert result["processed"] is False
    
    def test_webhook_with_large_payload(self, client, db_session):
        """Test webhook with large payload handling."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        large_event = {
            "ref": "refs/heads/large-test",
            "repository": {"full_name": "test-user/test-repo"},
            "commits": [
                {
                    "id": f"commit_{i}",
                    "message": f"Commit {i}",
                    "author": {"name": f"Author {i}"}
                }
                for i in range(100)  # Large number of commits
            ]
        }
        
        payload = json.dumps(large_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["commit_count"] == 100
        assert result["success"] is True
    
    @pytest.mark.asyncio
    @patch('backend.services.events.EventBroadcaster')
    async def test_concurrent_webhooks_handled(self, mock_broadcaster, client, db_session):
        """Test concurrent webhook handling without race conditions."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        mock_broadcaster_instance = AsyncMock()
        mock_broadcaster.return_value = mock_broadcaster_instance
        
        payload1 = json.dumps({"ref": "refs/heads/branch1", "repository": {"full_name": "test-repo"}})
        payload2 = json.dumps({"ref": "refs/heads/branch2", "repository": {"full_name": "test-repo"}})
        
        headers1 = generate_github_signature(payload1, webhook_secret)
        headers2 = generate_github_signature(payload2, webhook_secret)
        
        # Act - send concurrent webhooks
        import asyncio
        
        async def send_webhook(payload, headers):
            return client.post("/api/webhooks/github", data=payload, headers=headers)
        
        # Send multiple webhooks concurrently
        tasks = []
        for i in range(10):
            payload = json.dumps({"ref": f"refs/heads/branch{i}", "repository": {"full_name": "test-repo"}})
            headers = generate_github_signature(payload, webhook_secret)
            tasks.append(send_webhook(payload, headers))
        
        responses = await asyncio.gather(*tasks)
        
        # Assert
        for response in responses:
            assert response.status_code == 200


class TestWebhookUIEventEmission:
    """Test webhook-triggered UI event emission."""
    
    @pytest.mark.asyncio
    @patch('backend.services.events.EventBroadcaster')
    async def test_ui_event_emitted_via_websocket(self, mock_broadcaster, client, db_session):
        """Test UI event emission via WebSocket from webhook."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        mock_broadcaster_instance = AsyncMock()
        mock_broadcaster.return_value = mock_broadcaster_instance
        
        push_event = {
            "ref": "refs/heads/mgx/update/run-1",
            "after": "new_commit_sha",
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        # Verify UI event was published
        mock_broadcaster_instance.publish.assert_called_once()
        
        # Verify the event type
        call_args = mock_broadcaster_instance.publish.call_args[0][0]
        assert call_args.event_type == EventTypeEnum.GIT_PUSH_SUCCESS
    
    @patch('backend.routers.webhooks.get_event_broadcaster')
    def test_task_metadata_updated_from_webhook(self, mock_get_broadcaster, client, db_session):
        """Test task metadata update from webhook data."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        mock_broadcaster = Mock()
        mock_get_broadcaster.return_value = mock_broadcaster
        
        push_event = {
            "ref": "refs/heads/mgx/task-123/run-1",
            "after": "abc123def456",
            "repository": {"full_name": "test-user/test-repo"},
            "pusher": {
                "name": "mgx-agent",
                "email": "agent@mgx.dev"
            }
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        
        # Verify task metadata was extracted
        result = response.json()
        assert result["task_id"] == "123"
        assert result["run_number"] == "1"
        assert result["commit_sha"] == "abc123def456"
    
    @patch('backend.routers.webhooks.get_event_broadcaster')
    def test_duplicate_webhook_prevention(self, mock_get_broadcaster, client, db_session):
        """Test duplicate webhook prevention."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        mock_broadcaster = Mock()
        mock_get_broadcaster.return_value = mock_broadcaster
        
        push_event = {
            "ref": "refs/heads/mgx/task-456/run-2",
            "after": "duplicate_sha",
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act - send same webhook twice
        response1 = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        response2 = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Verify only one UI event was emitted (duplicate detection)
        assert mock_broadcaster.publish.call_count == 1
    
    def test_webhook_multiple_events_in_sequence(self, client, db_session):
        """Test multiple webhooks in sequence handled correctly."""
        webhook_secret = "test_webhook_secret_12345"
        
        # Different webhook types in sequence
        webhooks = [
            {
                "event": "push",
                "payload": {"ref": "refs/heads/branch1", "repository": {"full_name": "test-repo"}}
            },
            {
                "event": "pull_request",
                "payload": {
                    "action": "opened",
                    "number": 1,
                    "pull_request": {"id": 111}
                }
            },
            {
                "event": "push",
                "payload": {"ref": "refs/heads/branch2", "repository": {"full_name": "test-repo"}}
            }
        ]
        
        # Send webhooks in sequence
        for webhook_data in webhooks:
            payload = json.dumps(webhook_data["payload"])
            headers = generate_github_signature(payload, webhook_secret)
            headers["X-GitHub-Event"] = webhook_data["event"]
            
            response = client.post(
                "/api/webhooks/github",
                data=payload,
            headers=headers
        )
        
        assert response.status_code == 200
    
    def test_webhook_event_types_processed(self, client, db_session):
        """Test all webhook event types are processed correctly."""
        webhook_secret = "test_webhook_secret_12345"
        
        test_cases = [
            ("push", {"ref": "refs/heads/main"}),
            ("pull_request", {"action": "opened", "pull_request": {"id": 1}}),
            ("pull_request_review", {"action": "submitted", "review": {"id": 1}}),
            ("commit_comment", {"action": "created", "comment": {"id": 1}}),
        ]
        
        for event_type, payload_data in test_cases:
            # Add required fields for signature
            payload_data["repository"] = {"full_name": "test-repo"}
            
                payload = json.dumps(payload_data)
                headers = generate_github_signature(payload, webhook_secret)
                headers["X-GitHub-Event"] = event_type
                
                response = client.post(
                    "/api/webhooks/github",
                    data=payload,
                    headers=headers
                )
                
                assert response.status_code == 200
                result = response.json()
                assert result["success"] is True
                assert result["event_type"] == event_type


class TestWebhookDataStorage:
    """Test webhook data storage in database."""
    
    @patch('backend.routers.webhooks.WebhookStorage')
    def test_webhook_payload_stored(self, mock_storage, client, db_session):
        """Test webhook payload storage."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        
        push_event = {
            "ref": "refs/heads/mgx/test/run-1",
            "after": "new_sha",
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        headers["X-GitHub-Delivery"] = "delivery-12345"
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        # Verify storage was called
        mock_storage_instance.store.assert_called_once()
        
        # Verify stored data
        stored_data = mock_storage_instance.store.call_args[0][0]
        assert stored_data["delivery_id"] == "delivery-12345"
        assert stored_data["event_type"] == "push"
    
    @patch('backend.routers.webhooks.update_task_from_webhook')
    def test_task_updated_from_webhook(self, mock_update, client, db_session):
        """Test task update from webhook processing."""
        # Arrange
        webhook_secret = "test_webhook_secret_12345"
        mock_update.return_value = {"updated": True}
        
        push_event = {
            "ref": "refs/heads/mgx/task-789/run-5",
            "after": "abc123def456",
            "repository": {"full_name": "test-user/test-repo"}
        }
        
        payload = json.dumps(push_event)
        headers = generate_github_signature(payload, webhook_secret)
        
        # Act
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        mock_update.assert_called_once()
        
        # Verify task update was called with correct data
        update_data = mock_update.call_args[0][0]
        assert update_data["task_id"] == "789"
        assert update_data["commit_sha"] == "abc123def456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])