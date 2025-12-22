# GitHub Webhooks Documentation

## Overview

GitHub webhooks allow real-time event notifications from GitHub repositories. This system receives, validates, processes, and stores webhook events for audit and replay purposes.

## Configuration

### Environment Variables

Set the following environment variable:

```bash
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
```

### GitHub Repository Setup

1. Go to your GitHub repository settings
2. Navigate to **Webhooks** section
3. Click **Add webhook**
4. Set the following:
   - **Payload URL**: `https://your-domain.com/api/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: Your `GITHUB_WEBHOOK_SECRET` value
   - **Events**: Select events you want to receive (push, pull_request, issues, etc.)
5. Click **Add webhook**

## Supported Events

- `push` - Repository push events
- `pull_request` - Pull request events (opened, closed, merged, etc.)
- `issues` - Issue events (opened, closed, etc.)
- `issue_comment` - Issue comment events
- `create` - Branch/tag creation events
- `delete` - Branch/tag deletion events
- `release` - Release events
- `workflow_run` - GitHub Actions workflow run events

## API Endpoints

### POST /api/webhooks/github

Receive GitHub webhook events.

**Headers:**
- `X-Hub-Signature-256`: GitHub webhook signature (format: `sha256=<hex>`)
- `X-GitHub-Event`: Event type (push, pull_request, etc.)
- `X-GitHub-Delivery`: Unique delivery ID
- `Content-Type`: `application/json`

**Response:**
```json
{
  "success": true,
  "event_type": "push",
  "delivery_id": "abc123",
  "processed_at": "2024-01-01T12:00:00Z"
}
```

### GET /api/webhooks/github/events

List webhook events (for debugging and audit).

**Query Parameters:**
- `repo_full_name` (optional): Filter by repository
- `event_type` (optional): Filter by event type
- `limit` (optional): Maximum number of events (default: 50)

**Response:**
```json
{
  "items": [...],
  "total": 100,
  "limit": 50
}
```

## Security

### Signature Verification

All webhook requests are verified using HMAC SHA256 signature validation. Invalid signatures are rejected with a 401 status code.

### Duplicate Detection

Webhook events are deduplicated by delivery ID to prevent duplicate processing.

## Event Processing

1. **Signature Validation**: Verify HMAC SHA256 signature
2. **Event Type Validation**: Check if event type is supported
3. **Duplicate Check**: Verify delivery ID hasn't been processed
4. **Event Parsing**: Extract relevant data from payload
5. **Event Broadcasting**: Broadcast to WebSocket subscribers
6. **Event Storage**: Store in database for audit

## Database Schema

Events are stored in the `github_webhook_events` table with the following fields:

- `id`: Unique event ID
- `delivery_id`: GitHub delivery ID (unique)
- `event_type`: Event type
- `repository_id`: Linked repository link ID (if matched)
- `repo_full_name`: Repository full name
- `payload`: Full webhook payload (JSON)
- `parsed_data`: Parsed event data (JSON)
- `processed`: Whether event was successfully processed
- `processed_at`: Processing timestamp
- `error_message`: Error message if processing failed
- `created_at`: Event creation timestamp
- `updated_at`: Last update timestamp

## WebSocket Events

Processed webhook events are broadcast to WebSocket subscribers on channels:

- `repo:{repo_full_name}` - Repository-specific events
- `github_webhooks` - All webhook events

## Troubleshooting

### Invalid Signature

- Verify `GITHUB_WEBHOOK_SECRET` matches GitHub webhook configuration
- Ensure signature header format is correct (`sha256=<hex>`)

### Events Not Processing

- Check event type is supported
- Verify repository link exists and matches `repo_full_name`
- Check logs for processing errors

### Duplicate Events

- Duplicate delivery IDs are automatically detected and skipped
- Check `processed` field in database to verify event status


