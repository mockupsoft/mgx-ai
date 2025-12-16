# API (Workflows)

MGX Agent exposes a **FastAPI** backend under [`backend/`](../backend).

- OpenAPI (local): `http://localhost:8000/docs`
- Related docs:
  - WebSockets: **[WEBSOCKET.md](./WEBSOCKET.md)**
  - Workflow guide: **[WORKFLOWS.md](./WORKFLOWS.md)**
  - Database notes: **[DATABASE.md](./DATABASE.md)**

This document focuses on **Phase 10 – Workflow Engine & Orchestration** endpoints.

---

## Workspace scoping (multi-tenant)

Most endpoints are **workspace-scoped**. Select the active workspace via either:

- Headers:
  - `X-Workspace-Id: <workspace_id>`
  - `X-Workspace-Slug: <workspace_slug>`
- Query:
  - `?workspace_id=<workspace_id>`
  - `?workspace_slug=<workspace_slug>`

If none is provided, the backend may create/use the `default` workspace.

---

## Workflow CRUD endpoints

Base path: `/api/workflows`

| Method | Path | Description |
|---:|---|---|
| GET | `/api/workflows/` | List workflow definitions (pagination + filters) |
| POST | `/api/workflows/` | Create a workflow definition |
| GET | `/api/workflows/{workflow_id}` | Get workflow definition (optionally includes steps/variables) |
| PATCH | `/api/workflows/{workflow_id}` | Update workflow metadata (name/description/config/etc.) |
| DELETE | `/api/workflows/{workflow_id}` | Delete workflow definition (fails if executions are running) |
| POST | `/api/workflows/validate` | Validate a workflow definition without saving |
| GET | `/api/workflows/templates` | Return built-in workflow templates (starter JSON) |

### List workflows

`GET /api/workflows/?skip=0&limit=10&project_id=...&is_active=true`

Response: `WorkflowListResponse`

```json
{
  "items": [
    {
      "id": "...",
      "workspace_id": "...",
      "project_id": "...",
      "name": "My Workflow",
      "version": 1,
      "is_active": true,
      "config": {},
      "timeout_seconds": 3600,
      "max_retries": 3,
      "metadata": {},
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z",
      "steps": [],
      "variables": []
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

### Create workflow

`POST /api/workflows/`

Request: `WorkflowCreate`

Notes:
- `steps[].depends_on_steps` is typically provided as **step names** within the same request (human-friendly). The backend may resolve these internally.
- `metadata` is the preferred request key (it maps to `meta_data` internally).

```json
{
  "name": "Sequential Task",
  "description": "A simple 3-step workflow",
  "project_id": "<optional project id>",
  "timeout_seconds": 3600,
  "max_retries": 3,
  "config": {},
  "variables": [
    {
      "name": "input",
      "data_type": "json",
      "is_required": true,
      "description": "Input payload",
      "metadata": {}
    }
  ],
  "steps": [
    {
      "name": "prepare",
      "step_type": "task",
      "step_order": 1,
      "timeout_seconds": 120,
      "max_retries": 1,
      "depends_on_steps": [],
      "config": {
        "processing_type": "default"
      },
      "metadata": {}
    },
    {
      "name": "process",
      "step_type": "task",
      "step_order": 2,
      "timeout_seconds": 600,
      "max_retries": 2,
      "depends_on_steps": ["prepare"],
      "config": {
        "processing_type": "data_transformation"
      },
      "metadata": {}
    },
    {
      "name": "finalize",
      "step_type": "task",
      "step_order": 3,
      "timeout_seconds": 120,
      "depends_on_steps": ["process"],
      "config": {
        "processing_type": "default"
      },
      "metadata": {}
    }
  ],
  "metadata": {
    "source": "docs/API.md"
  }
}
```

Response: `WorkflowResponse`.

---

## Execution endpoints

| Method | Path | Description |
|---:|---|---|
| POST | `/api/workflows/{workflow_id}/execute` | Start a workflow execution |
| GET | `/api/workflows/{workflow_id}/executions` | List executions for a workflow |
| GET | `/api/workflows/executions/{execution_id}` | Get a single execution (details) |
| GET | `/api/workflows/executions/{execution_id}/status` | Lightweight status snapshot |
| POST | `/api/workflows/executions/{execution_id}/cancel` | Cancel a running execution |
| GET | `/api/workflows/executions/stats` | Workspace-wide execution statistics |

### Start execution

`POST /api/workflows/{workflow_id}/execute`

Request: `WorkflowExecutionCreate`

```json
{
  "input_variables": {
    "input": {"hello": "world"}
  }
}
```

Response (submission):

```json
{
  "status": "submitted",
  "execution_id": "...",
  "message": "Workflow execution started successfully",
  "workflow_id": "..."
}
```

Track progress via:

- REST polling: `GET /api/workflows/executions/{execution_id}/status`
- WebSocket streams: see **[WEBSOCKET.md](./WEBSOCKET.md)**

---

## Telemetry & monitoring endpoints

| Method | Path | Description |
|---:|---|---|
| GET | `/api/workflows/executions/{execution_id}/timeline` | Per-step timeline + metrics |
| GET | `/api/workflows/{workflow_id}/metrics` | Aggregated success rate + duration stats |

---

## Error handling

Errors use FastAPI’s standard format:

```json
{ "detail": "Workflow not found" }
```

Common statuses:

- `400` – validation errors, invalid project/workspace scoping
- `404` – workflow/execution not found
- `409` – conflicting state (e.g., delete while running)
- `503` – workflow engine not available

---

## Rate limiting

Rate limiting is **not enabled by default** in this repository. If you deploy MGX behind an API gateway (NGINX/Traefik/Cloudflare), configure rate limiting at the edge.
