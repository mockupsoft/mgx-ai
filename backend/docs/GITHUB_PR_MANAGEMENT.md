# GitHub Pull Request Management Documentation

## Overview

This system provides comprehensive Pull Request (PR) management capabilities including listing, viewing, merging, reviewing, and commenting on GitHub pull requests.

## API Endpoints

### List Pull Requests

**GET** `/api/repositories/{link_id}/pull-requests`

List pull requests for a repository.

**Query Parameters:**
- `state` (optional): Filter by state (`open`, `closed`, `all`) - default: `open`

**Response:**
```json
[
  {
    "number": 1,
    "title": "feat: Add authentication",
    "body": "PR description",
    "state": "open",
    "head_branch": "feature/auth",
    "base_branch": "main",
    "head_sha": "abc123",
    "base_sha": "def456",
    "html_url": "https://github.com/owner/repo/pull/1",
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "merged_at": null,
    "mergeable": true,
    "mergeable_state": "clean",
    "author": "username",
    "labels": ["bug", "enhancement"],
    "review_count": 2,
    "comment_count": 5
  }
]
```

### Get Pull Request Details

**GET** `/api/repositories/{link_id}/pull-requests/{pr_number}`

Get detailed information about a specific pull request.

**Response:**
Same format as list endpoint, but for a single PR.

### Merge Pull Request

**POST** `/api/repositories/{link_id}/pull-requests/{pr_number}/merge`

Merge a pull request.

**Query Parameters:**
- `merge_method` (optional): Merge method (`merge`, `squash`, `rebase`) - default: `merge`
- `commit_title` (optional): Custom commit title
- `commit_message` (optional): Custom commit message

**Response:**
```json
{
  "merged": true,
  "message": "Merged successfully",
  "sha": "merged_commit_sha"
}
```

### Create Pull Request Review

**POST** `/api/repositories/{link_id}/pull-requests/{pr_number}/review`

Create a review for a pull request.

**Query Parameters:**
- `state` (required): Review state (`APPROVE`, `REQUEST_CHANGES`, `COMMENT`)
- `event` (optional): Review event (overrides state if provided)
- `body` (optional): Review body/comment

**Request Body:**
```json
{
  "body": "Review comment text"
}
```

**Response:**
```json
{
  "id": 123,
  "state": "APPROVED",
  "body": "Review comment text",
  "author": "username",
  "submitted_at": "2024-01-01T12:00:00Z"
}
```

### Create Pull Request Comment

**POST** `/api/repositories/{link_id}/pull-requests/{pr_number}/comments`

Add a comment to a pull request.

**Request Body:**
```json
{
  "body": "Comment text"
}
```

**Response:**
```json
{
  "id": 456,
  "body": "Comment text",
  "author": "username",
  "created_at": "2024-01-01T12:00:00Z",
  "path": null,
  "line": null
}
```

### List Pull Request Reviews

**GET** `/api/repositories/{link_id}/pull-requests/{pr_number}/reviews`

List all reviews for a pull request.

**Response:**
```json
[
  {
    "id": 123,
    "state": "APPROVED",
    "body": "Looks good!",
    "author": "username",
    "submitted_at": "2024-01-01T12:00:00Z"
  }
]
```

### List Pull Request Comments

**GET** `/api/repositories/{link_id}/pull-requests/{pr_number}/comments`

List all comments on a pull request.

**Response:**
```json
[
  {
    "id": 456,
    "body": "Comment text",
    "author": "username",
    "created_at": "2024-01-01T12:00:00Z",
    "path": null,
    "line": null
  }
]
```

## Authentication

All endpoints require:
- Valid workspace context
- Repository link in the workspace
- GitHub authentication (PAT or GitHub App installation)

## Error Handling

- `404`: Repository link not found
- `403`: Repository link not in workspace
- `500`: GitHub API error or processing failure

## Usage Examples

### List Open Pull Requests

```bash
curl -X GET "https://api.example.com/api/repositories/link-123/pull-requests?state=open" \
  -H "X-Workspace-Id: ws-1"
```

### Merge Pull Request

```bash
curl -X POST "https://api.example.com/api/repositories/link-123/pull-requests/1/merge?merge_method=squash" \
  -H "X-Workspace-Id: ws-1"
```

### Approve Pull Request

```bash
curl -X POST "https://api.example.com/api/repositories/link-123/pull-requests/1/review?state=APPROVE" \
  -H "X-Workspace-Id: ws-1" \
  -H "Content-Type: application/json" \
  -d '{"body": "Looks good to me!"}'
```


