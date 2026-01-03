# MGX Agent Event Contracts

This document defines all event types emitted by the MGX Agent system, including their schemas, validation rules, and versioning strategy.

## Table of Contents

- [Event System Overview](#event-system-overview)
- [Event Types](#event-types)
  - [Task Events](#task-events)
  - [Agent Events](#agent-events)
  - [Execution Events](#execution-events)
  - [Error Events](#error-events)
  - [Workflow Events](#workflow-events)
  - [Knowledge Events](#knowledge-events)
- [Event Schema](#event-schema)
- [Event Validation](#event-validation)
- [Versioning Strategy](#versioning-strategy)
- [OpenAPI Specification](#openapi-specification)

---

## Event System Overview

The MGX Agent uses an event-driven architecture for tracking and coordinating multi-agent workflows. Events are:

- **Published** when actions occur (task creation, agent messages, errors, etc.)
- **Validated** against JSON schemas before publishing
- **Versioned** to maintain backward compatibility
- **Correlated** using `task_id`, `agent_id`, and `workspace_id`

### Event Flow

```
[Client] → [FastAPI Router] → [Event Publisher] → [WebSocket/Kafka] → [Subscribers]
```

### Correlation IDs

All events include correlation IDs for tracing:

- `event_id`: Unique event identifier (UUID)
- `task_id`: Associated task ID
- `agent_id`: Associated agent ID (if applicable)
- `workspace_id`: Workspace context
- `project_id`: Project context (if applicable)
- `run_id`: Execution run ID (if applicable)

---

## Event Types

### Task Events

#### task.created

Emitted when a new task is created.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/task.created.json",
  "event_type": "task.created",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "project_id": "project_xyz",
  "data": {
    "title": "Task title",
    "description": "Task description",
    "status": "pending",
    "priority": "medium",
    "created_by": "user_123",
    "metadata": {}
  }
}
```

#### task.started

Emitted when a task execution begins.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/task.started.json",
  "event_type": "task.started",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "agent": "product_manager",
    "context": {},
    "start_time": "2024-01-01T00:00:00Z"
  }
}
```

#### task.completed

Emitted when a task execution completes successfully.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/task.completed.json",
  "event_type": "task.completed",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:01:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "status": "completed",
    "result": {
      "output": "Task output",
      "artifacts": [],
      "metrics": {
        "duration_ms": 60000,
        "tokens_used": 1000,
        "rounds": 3
      }
    },
    "end_time": "2024-01-01T00:01:00Z"
  }
}
```

#### task.failed

Emitted when a task execution fails.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/task.failed.json",
  "event_type": "task.failed",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:30Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "error": {
      "type": "LLMError",
      "message": "Failed to generate response",
      "code": "LLM_TIMEOUT",
      "details": {}
    },
    "stacktrace": "Full stack trace...",
    "end_time": "2024-01-01T00:00:30Z"
  }
}
```

#### task.cancelled

Emitted when a task is cancelled.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/task.cancelled.json",
  "event_type": "task.cancelled",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:20Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "cancelled_by": "user_123",
    "reason": "User requested cancellation",
    "cancel_time": "2024-01-01T00:00:20Z"
  }
}
```

---

### Agent Events

#### agent.message

Emitted when an agent sends a message.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/agent.message.json",
  "event_type": "agent.message",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:10Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "agent_id": "agent_789",
  "data": {
    "agent_role": "product_manager",
    "message": "Agent message content",
    "message_type": "info",
    "round": 1,
    "context": {
      "thought": "Agent's internal reasoning",
      "action": "Action taken"
    }
  }
}
```

#### agent.thinking

Emitted when an agent is processing (intermediate state).

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/agent.thinking.json",
  "event_type": "agent.thinking",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:05Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "agent_id": "agent_789",
  "data": {
    "agent_role": "product_manager",
    "thinking": "Agent's current thought process",
    "round": 1,
    "progress": 0.5
  }
}
```

#### agent.action

Emitted when an agent performs an action (file write, API call, etc.).

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/agent.action.json",
  "event_type": "agent.action",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:15Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "agent_id": "agent_789",
  "data": {
    "agent_role": "engineer",
    "action_type": "write_file",
    "action_details": {
      "path": "/path/to/file.py",
      "content": "file content",
      "mode": "overwrite"
    },
    "status": "success",
    "round": 2
  }
}
```

---

### Execution Events

#### execution.started

Emitted when a new execution run begins.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/execution.started.json",
  "event_type": "execution.started",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "agents": ["product_manager", "engineer", "architect"],
    "max_rounds": 5,
    "execution_mode": "sequential",
    "start_time": "2024-01-01T00:00:00Z"
  }
}
```

#### execution.completed

Emitted when an execution run finishes.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/execution.completed.json",
  "event_type": "execution.completed",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:01:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "status": "completed",
    "final_state": {
      "rounds_completed": 3,
      "total_messages": 15,
      "total_actions": 5,
      "duration_ms": 60000
    },
    "end_time": "2024-01-01T00:01:00Z"
  }
}
```

---

### Error Events

#### error.occurred

Emitted when an error occurs during execution.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/error.occurred.json",
  "event_type": "error.occurred",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:30Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "run_id": "run_456",
  "data": {
    "error_type": "LLMError",
    "error_code": "LLM_TIMEOUT",
    "error_message": "Failed to generate response from LLM provider",
    "severity": "error",
    "context": {
      "agent_role": "product_manager",
      "provider": "openai",
      "model": "gpt-4",
      "retry_count": 3
    },
    "stacktrace": "Full stack trace..."
  }
}
```

---

### Workflow Events

#### workflow.started

Emitted when a workflow execution begins.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/workflow.started.json",
  "event_type": "workflow.started",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_id": "workspace_abc",
  "data": {
    "workflow_id": "workflow_123",
    "workflow_name": "PR Review Workflow",
    "triggered_by": "user_123",
    "trigger_type": "manual",
    "input_parameters": {}
  }
}
```

#### workflow.completed

Emitted when a workflow execution completes.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/workflow.completed.json",
  "event_type": "workflow.completed",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:05:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_id": "workspace_abc",
  "data": {
    "workflow_id": "workflow_123",
    "status": "completed",
    "result": {
      "tasks_completed": 5,
      "duration_ms": 300000,
      "output": {}
    },
    "end_time": "2024-01-01T00:05:00Z"
  }
}
```

---

### Knowledge Events

#### knowledge.indexed

Emitted when a knowledge item is indexed.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/knowledge.indexed.json",
  "event_type": "knowledge.indexed",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_id": "workspace_abc",
  "data": {
    "knowledge_id": "knowledge_123",
    "knowledge_type": "document",
    "title": "Document title",
    "vector_db": "chroma",
    "embedding_model": "openai-text-embedding-3-small",
    "metadata": {}
  }
}
```

#### knowledge.retrieved

Emitted when knowledge is retrieved for a query.

```json
{
  "$schema": "https://mgx.ai/events/v1/schemas/knowledge.retrieved.json",
  "event_type": "knowledge.retrieved",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:05Z",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_id": "workspace_abc",
  "task_id": "task_123",
  "data": {
    "query": "Query text",
    "results_count": 5,
    "min_relevance_score": 0.3,
    "vector_db": "chroma",
    "execution_time_ms": 100
  }
}
```

---

## Event Schema

### Base Event Structure

All events follow this base structure:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

class BaseEvent(BaseModel):
    """Base event model."""

    event_type: str = Field(..., description="Type of event")
    version: str = Field(default="1.0.0", description="Event version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_id: UUID = Field(default_factory=uuid4)
    task_id: Optional[str] = Field(None, description="Associated task ID")
    workspace_id: str = Field(..., description="Workspace context")
    project_id: Optional[str] = Field(None, description="Project context")
    run_id: Optional[str] = Field(None, description="Execution run ID")
    agent_id: Optional[str] = Field(None, description="Agent ID (if applicable)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "task.created",
                "version": "1.0.0",
                "timestamp": "2024-01-01T00:00:00Z",
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "task_id": "task_123",
                "workspace_id": "workspace_abc",
                "data": {}
            }
        }
```

---

## Event Validation

### Validation Rules

1. **Required Fields**: All base fields must be present
2. **Event Types**: Must match predefined event types
3. **Version Format**: Must follow semantic versioning (X.Y.Z)
4. **Timestamp**: Must be valid ISO 8601 datetime
5. **UUIDs**: Must be valid UUID v4 format
6. **Data Schema**: Must match event-specific schema

### Validation Example

```python
from pydantic import validator

class TaskCreatedEvent(BaseEvent):
    """Task created event."""

    @validator('event_type')
    def validate_event_type(cls, v):
        if v != 'task.created':
            raise ValueError(f"Invalid event_type: {v}")
        return v

    @validator('data')
    def validate_data(cls, v):
        required_fields = ['title', 'description', 'status']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field: {field}")
        return v
```

---

## Versioning Strategy

### Semantic Versioning

Events follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (e.g., removing required fields)
- **MINOR**: Non-breaking additions (e.g., adding optional fields)
- **PATCH**: Bug fixes (e.g., fixing validation logic)

### Version Compatibility

- **Consumers** should be tolerant of unknown fields
- **Producers** must not remove required fields without MAJOR version bump
- **Backward compatibility** should be maintained for at least 2 major versions

### Versioning Examples

| Old Version | New Version | Change Type | Example |
|-------------|-------------|-------------|---------|
| 1.0.0 | 1.1.0 | MINOR | Added optional `metadata` field |
| 1.0.0 | 1.0.1 | PATCH | Fixed validation regex |
| 1.0.0 | 2.0.0 | MAJOR | Removed `created_by` field |

---

## OpenAPI Specification

The FastAPI application automatically generates OpenAPI specifications at `/openapi.json`.

### Accessing OpenAPI Spec

```bash
# Get OpenAPI JSON specification
curl http://localhost:8000/openapi.json > openapi.json

# View interactive documentation
open http://localhost:8000/docs

# View ReDoc documentation
open http://localhost:8000/redoc
```

### Event Endpoints

#### POST /events/publish

Publish a new event.

```json
{
  "event_type": "task.created",
  "task_id": "task_123",
  "workspace_id": "workspace_abc",
  "data": {
    "title": "New task",
    "description": "Task description"
  }
}
```

#### GET /events/stream

Subscribe to real-time event stream (WebSocket).

```python
import websockets

async def subscribe_events():
    uri = "ws://localhost:8000/events/stream?workspace_id=workspace_abc"
    async with websockets.connect(uri) as websocket:
        while True:
            event = await websocket.recv()
            print(event)
```

#### GET /events/{event_id}

Get a specific event by ID.

#### GET /events

Query events with filters.

```
GET /events?task_id=task_123&event_type=agent.message&limit=50
```

---

## Appendix

### Event Type Registry

| Event Type | Category | Version | Status |
|------------|----------|---------|--------|
| task.created | Task | 1.0.0 | Stable |
| task.started | Task | 1.0.0 | Stable |
| task.completed | Task | 1.0.0 | Stable |
| task.failed | Task | 1.0.0 | Stable |
| task.cancelled | Task | 1.0.0 | Stable |
| agent.message | Agent | 1.0.0 | Stable |
| agent.thinking | Agent | 1.0.0 | Stable |
| agent.action | Agent | 1.0.0 | Stable |
| execution.started | Execution | 1.0.0 | Stable |
| execution.completed | Execution | 1.0.0 | Stable |
| error.occurred | Error | 1.0.0 | Stable |
| workflow.started | Workflow | 1.0.0 | Stable |
| workflow.completed | Workflow | 1.0.0 | Stable |
| knowledge.indexed | Knowledge | 1.0.0 | Stable |
| knowledge.retrieved | Knowledge | 1.0.0 | Stable |

### Event Schema Files

JSON schemas for each event type are stored in:
```
backend/schemas/events/v1/{event_type}.json
```

### Contact & Support

For questions about event contracts:
- **Documentation**: See `/docs` endpoint
- **Issues**: GitHub Issues
- **Email**: support@mgx.ai
