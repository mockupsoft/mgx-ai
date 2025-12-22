# GitHub Issues Management Documentation

## Overview

This system provides comprehensive Issue management capabilities including listing, viewing, creating, updating, closing, and commenting on GitHub issues.

## API Endpoints

### List Issues

**GET** `/api/repositories/{link_id}/issues`

List issues for a repository.

**Query Parameters:**
- `state` (optional): Filter by state (`open`, `closed`, `all`) - default: `open`

**Response:**
```json
[
  {
    "number": 1,
    "title": "Bug: Login not working",
    "body": "Issue description",
    "state": "open",
    "html_url": "https://github.com/owner/repo/issues/1",
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "closed_at": null,
    "author": "username",
    "labels": ["bug", "priority-high"],
    "assignees": ["username"],
    "comment_count": 3
  }
]
```

### Get Issue Details

**GET** `/api/repositories/{link_id}/issues/{issue_number}`

Get detailed information about a specific issue.

**Response:**
Same format as list endpoint, but for a single issue.

### Create Issue

**POST** `/api/repositories/{link_id}/issues`

Create a new issue.

**Request Body:**
```json
{
  "title": "Issue title",
  "body": "Issue description",
  "labels": ["bug", "enhancement"],
  "assignees": ["username1", "username2"]
}
```

**Response:**
```json
{
  "number": 2,
  "title": "Issue title",
  "body": "Issue description",
  "state": "open",
  "html_url": "https://github.com/owner/repo/issues/2",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "closed_at": null,
  "author": "username",
  "labels": ["bug", "enhancement"],
  "assignees": ["username1", "username2"],
  "comment_count": 0
}
```

### Update Issue

**PATCH** `/api/repositories/{link_id}/issues/{issue_number}`

Update an existing issue.

**Request Body:**
```json
{
  "title": "Updated title",
  "body": "Updated description",
  "state": "open",
  "labels": ["bug"],
  "assignees": ["username"]
}
```

All fields are optional. Only provided fields will be updated.

**Response:**
Updated issue object.

### Close Issue

**POST** `/api/repositories/{link_id}/issues/{issue_number}/close`

Close an issue.

**Response:**
Closed issue object with `state: "closed"` and `closed_at` timestamp.

### Create Issue Comment

**POST** `/api/repositories/{link_id}/issues/{issue_number}/comments`

Add a comment to an issue.

**Request Body:**
```json
{
  "body": "Comment text"
}
```

**Response:**
```json
{
  "id": 789,
  "body": "Comment text",
  "author": "username",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": null
}
```

### List Issue Comments

**GET** `/api/repositories/{link_id}/issues/{issue_number}/comments`

List all comments on an issue.

**Response:**
```json
[
  {
    "id": 789,
    "body": "Comment text",
    "author": "username",
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": null
  }
]
```

## Authentication

All endpoints require:
- Valid workspace context
- Repository link in the workspace
- GitHub authentication (PAT or GitHub App installation)

## Error Handling

- `404`: Repository link or issue not found
- `403`: Repository link not in workspace
- `500`: GitHub API error or processing failure

## Usage Examples

### List Open Issues

```bash
curl -X GET "https://api.example.com/api/repositories/link-123/issues?state=open" \
  -H "X-Workspace-Id: ws-1"
```

### Create Issue

```bash
curl -X POST "https://api.example.com/api/repositories/link-123/issues" \
  -H "X-Workspace-Id: ws-1" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Bug: Login not working",
    "body": "Users cannot log in with valid credentials",
    "labels": ["bug", "priority-high"],
    "assignees": ["developer"]
  }'
```

### Close Issue

```bash
curl -X POST "https://api.example.com/api/repositories/link-123/issues/1/close" \
  -H "X-Workspace-Id: ws-1"
```

### Add Comment

```bash
curl -X POST "https://api.example.com/api/repositories/link-123/issues/1/comments" \
  -H "X-Workspace-Id: ws-1" \
  -H "Content-Type: application/json" \
  -d '{"body": "Fixed in PR #42"}'
```


