# WebSocket / Event Streaming

MGX Agent supports **real-time event streaming** over WebSockets.

## Endpoints

- `ws://localhost:8000/ws/tasks/{task_id}`
- `ws://localhost:8000/ws/runs/{run_id}`
- `ws://localhost:8000/ws/stream` (global stream)

## Event contract

The canonical event schema, event types, and message examples are documented in:

- **[API_EVENTS_DOCUMENTATION.md](./API_EVENTS_DOCUMENTATION.md)**

Implementation reference:

- Router: [`backend/routers/ws.py`](../backend/routers/ws.py)
- Broadcaster: `backend/services/events.py` (see `backend/services/`)
