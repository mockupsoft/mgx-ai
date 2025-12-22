# -*- coding: utf-8 -*-
"""Integration tests for GitHub webhook endpoints."""

import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


def generate_github_signature(payload: str, secret: str) -> str:
    """Generate GitHub webhook signature."""
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def webhook_secret():
    """Webhook secret for testing."""
    return "test_webhook_secret_12345"


class TestWebhookReception:
    """Test GitHub webhook reception and parsing."""
    
    def test_push_webhook_received(self, client, webhook_secret, monkeypatch):
        """Test push webhook reception and parsing."""
        # Set webhook secret
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", webhook_secret)
        
        push_event = {
            "ref": "refs/heads/main",
            "before": "0000000000000000000000000000000000000000",
            "after": "abc123def456789012345678901234567890abcd",
            "repository": {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "test-user/test-repo",
                "private": False
            },
            "pusher": {
                "name": "test-user",
                "email": "test@example.com"
            },
            "sender": {
                "login": "test-user",
                "id": 99999
            }
        }
        
        payload = json.dumps(push_event)
        signature = generate_github_signature(payload, webhook_secret)
        
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-123",
                "Content-Type": "application/json",
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["event_type"] == "push"
        assert result["delivery_id"] == "test-delivery-123"
    
    def test_pr_webhook_received(self, client, webhook_secret, monkeypatch):
        """Test pull request webhook reception."""
        # Set webhook secret
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", webhook_secret)
        
        pr_event = {
            "action": "opened",
            "number": 42,
            "pull_request": {
                "id": 123456,
                "number": 42,
                "state": "open",
                "title": "feat: Implement authentication",
                "body": "## Changes\n- Add login endpoint\n- Add JWT validation",
                "head": {
                    "ref": "feature/auth",
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
                "login": "test-user",
                "id": 99999
            }
        }
        
        payload = json.dumps(pr_event)
        signature = generate_github_signature(payload, webhook_secret)
        
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "test-delivery-456",
                "Content-Type": "application/json",
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["event_type"] == "pull_request"
        assert result["delivery_id"] == "test-delivery-456"
    
    def test_invalid_signature(self, client, webhook_secret, monkeypatch):
        """Test webhook with invalid signature."""
        # Set webhook secret
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", webhook_secret)
        
        payload = json.dumps({"test": "data"})
        invalid_signature = "sha256=invalid_signature"
        
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-Hub-Signature-256": invalid_signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-789",
                "Content-Type": "application/json",
            }
        )
        
        assert response.status_code == 401
    
    def test_missing_signature(self, client, webhook_secret, monkeypatch):
        """Test webhook with missing signature."""
        # Set webhook secret
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", webhook_secret)
        
        payload = json.dumps({"test": "data"})
        
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-999",
                "Content-Type": "application/json",
            }
        )
        
        assert response.status_code == 401
    
    def test_unsupported_event_type(self, client, webhook_secret, monkeypatch):
        """Test webhook with unsupported event type."""
        # Set webhook secret
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", webhook_secret)
        
        payload = json.dumps({"test": "data"})
        signature = generate_github_signature(payload, webhook_secret)
        
        response = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "unsupported_event",
                "X-GitHub-Delivery": "test-delivery-unsupported",
                "Content-Type": "application/json",
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "not processed" in result.get("message", "").lower()
    
    def test_duplicate_delivery_id(self, client, webhook_secret, monkeypatch):
        """Test webhook with duplicate delivery ID."""
        # Set webhook secret
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", webhook_secret)
        
        payload = json.dumps({"test": "data"})
        signature = generate_github_signature(payload, webhook_secret)
        delivery_id = "test-delivery-duplicate"
        
        # First request
        response1 = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": delivery_id,
                "Content-Type": "application/json",
            }
        )
        assert response1.status_code == 200
        
        # Duplicate request
        response2 = client.post(
            "/api/webhooks/github",
            data=payload,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": delivery_id,
                "Content-Type": "application/json",
            }
        )
        assert response2.status_code == 200
        result = response2.json()
        assert result["success"] is True
        assert "already processed" in result.get("message", "").lower()


