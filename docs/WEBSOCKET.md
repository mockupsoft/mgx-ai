# WebSocket / Event Streaming

MGX Agent supports real-time event streaming via WebSockets.

All messages are JSON payloads matching the `EventPayload` schema in `backend/schemas.py`.

Related:
- API: **[API.md](./API.md)**
- Workflow guide: **[WORKFLOWS.md](./WORKFLOWS.md)**

---

## WebSocket endpoints

Base: `ws://{host}/ws/*`

### Tasks / runs (Phase 4.5)

- `ws://{host}/ws/tasks/{task_id}`
- `ws://{host}/ws/runs/{run_id}`
- `ws://{host}/ws/stream` (global stream: tasks/runs/workflows/agents)

### Agents

- `ws://{host}/ws/agents/{agent_id}`
- `ws://{host}/ws/agents/stream?workspace_id=...&agent_id=a1,a2` (filtered)

### Workflows (Phase 10)

- `ws://{host}/ws/workflows/{workflow_id}` (definition-scoped)
- `ws://{host}/ws/workflows/executions/{execution_id}` (execution-scoped)
- `ws://{host}/ws/workflows/steps/{step_id}` (step-scoped)
- `ws://{host}/ws/workflows/stream` (all workflow events)

---

## Event message shape

Most streamed messages look like:

```json
{
  "event_type": "workflow_started",
  "timestamp": "2025-01-01T00:00:00Z",
  "workspace_id": "...",

  "task_id": null,
  "run_id": null,

  "workflow_id": "...",
  "workflow_execution_id": "...",
  "workflow_step_id": null,

  "agent_id": null,

  "data": {
    "step_count": 3
  },
  "message": "Workflow 'My Workflow' started execution"
}
```

Heartbeats are periodically sent if no events are emitted:

```json
{ "type": "heartbeat", "timestamp": 1234567.89 }
```

---

## Workflow event types

Workflow execution is observable via the following `event_type` values:

### Workflow lifecycle

- `workflow_started`
- `workflow_completed`
- `workflow_failed`
- `workflow_cancelled`

### Step lifecycle

- `step_started`
- `step_completed`
- `step_failed`
- `step_skipped`

### Agent signals (related)

Workflows can also produce agent-related events (agent registry / controller):

- `agent_status_changed`
- `agent_activity`
- `agent_message`

Frontend-friendly semantic mapping (optional):

- `agent:assigned` → `agent_status_changed` where `data.status == "busy"`
- `agent:failed` → `agent_status_changed` where `data.status == "error"`

---

## Subscription examples

### Browser / JavaScript

```js
const workflowId = "...";
const ws = new WebSocket(`ws://localhost:8000/ws/workflows/${workflowId}`);

ws.onmessage = (evt) => {
  const msg = JSON.parse(evt.data);
  console.log("event", msg.event_type, msg);
};
```

### wscat

```bash
wscat -c ws://localhost:8000/ws/workflows/stream
```

---

## Channels & routing (server-side)

Internally, the backend uses an in-memory pub/sub broadcaster (`backend/services/events.py`).

Events are published to channel names such as:

- `workflow:{workflow_id}`
- `workflow-run:{execution_id}`
- `workflow-step:{step_id}`
- `workflows` (workflow global stream)
- `all` (global)

The WebSocket routes subscribe to the appropriate channel(s) and forward matching events.

Implementation reference:

- Router: [`backend/routers/ws.py`](../backend/routers/ws.py)
- Broadcaster: [`backend/services/events.py`](../backend/services/events.py)
