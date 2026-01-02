# MGX-AI Event Contracts & Event-Driven Architecture

## Overview

This document provides comprehensive specifications for the MGX-AI event-driven architecture, including event schemas, versioning strategy, event broadcasting, and consumer guidelines.

## Event Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   API Gateway   ├────▶  Event System  ├────▶   Consumers     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │                        │
                               │                        │
                               ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │                 │    │                 │
                       │  Event Store    │    │ WebSocket       │
                       │  (PostgreSQL)   │    │  Clients        │
                       │                 │    │                 │
                       └─────────────────┘    └─────────────────┘
```

## Event Schema Specification

### Event Envelope Format

All events follow a standardized envelope format:

```json
{
  "event_id": "evt_01HNYZQXQHJ9E1T5VZJQKZGJRM",
  "event_type": "task.created",
  "timestamp": "2024-01-15T10:00:00Z",
  "correlation_id": "corr_01HNYY...",
  "version": "1.0",
  "workspace_id": "ws_123",
  "agent_id": "agent_456",
  "task_id": "task_789",
  "run_id": "run_012",
  "data": {
    // Event-specific payload
  }
}
```

**Field Specifications:**

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `event_id` | string | Yes | Unique event identifier | `evt_01HN...` |
| `event_type` | string | Yes | Event type name | `task.created` |
| `timestamp` | ISO 8601 | Yes | Event creation time | `2024-01-15T10:00:00Z` |
| `correlation_id` | string | No | For distributed tracing | `corr_01HN...` |
| `version` | string | Yes | Schema version | `1.0` |
| `workspace_id` | string | Yes | Workspace identifier | `ws_123` |
| `agent_id` | string | No | Agent identifier | `agent_456` |
| `task_id` | string | No | Task identifier | `task_789` |
| `run_id` | string | No | Run identifier | `run_012` |
| `data` | object | Yes | Event payload | `{...}` |

## Event Types Reference

### 1. Task Lifecycle Events

#### `task.created`

**Description**: Emitted when a new task is created

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "task.created",
  "timestamp": "2024-01-15T10:00:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "data": {
    "task": {
      "id": "task_456",
      "title": "Generate authentication system",
      "description": "Create JWT-based auth module",
      "type": "code_generation",
      "project_id": "proj_789",
      "agent_config": {
        "model": "gpt-4",
        "provider": "openai",
        "max_tokens": 4000
      },
      "estimated_tokens": 3500,
      "estimated_cost": 0.07,
      "priority": "high",
      "due_date": "2024-01-16T10:00:00Z"
    },
    "user": {
      "id": "user_abc",
      "email": "user@example.com",
      "name": "John Doe"
    },
    "metadata": {
      "source": "api",
      "tags": ["auth", "jwt", "backend"]
    }
  }
}
```

**Consumers:**
- Frontend (real-time task list updates)
- Audit Service (compliance logging)
- Notification Service (email/Slack alerts)
- Task Scheduler (priority queue management)

---

#### `task.started`

**Description**: Emitted when task execution begins

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "task.started",
  "timestamp": "2024-01-15T10:00:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "run_id": "run_567",
  "agent_id": "agent_789",
  "data": {
    "task_id": "task_456",
    "agent_id": "agent_789",
    "resources": {
      "model": "gpt-4",
      "provider": "openai",
      "estimated_tokens": 3500,
      "estimated_cost": 0.07,
      "fallback_models": ["claude-3-opus", "gpt-3.5-turbo"]
    },
    "execution_context": {
      "executor_id": "executor_001",
      "memory_limit": "2GB",
      "timeout_seconds": 600
    }
  }
}
```

**Consumers:**
- Frontend (task status updates)
- Cost Tracker (real-time spend monitoring)
- Resource Manager (capacity planning)

---

#### `task.completed`

**Description**: Emitted when task execution completes successfully

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "task.completed",
  "timestamp": "2024-01-15T10:05:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "run_id": "run_567",
  "agent_id": "agent_789",
  "data": {
    "task_id": "task_456",
    "duration_seconds": 300,
    "tokens_used": {
      "prompt": 1500,
      "completion": 1800,
      "total": 3300
    },
    "cost_usd": 0.066,
    "result": {
      "status": "success",
      "artifacts": [
        "artifact_auth_controller.py",
        "artifact_jwt_utils.py",
        "artifact_auth_routes.py"
      ],
      "lines_of_code": 450,
      "files_generated": 3,
      "test_coverage": 85.5
    },
    "performance_metrics": {
      "model_response_time_avg": 2.3,
      "tool_calls_count": 12,
      "retries": 0
    }
  }
}
```

**Consumers:**
- Frontend (task completion notification)
- Billing Service (cost allocation)
- Analytics (performance tracking)
- Audit Service (compliance)
- Notification Service (completion alerts)

---

#### `task.error`

**Description**: Emitted when task execution fails

**Priority**: Critical
**Retention**: 365 days (for compliance)
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "task.error",
  "timestamp": "2024-01-15T10:05:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "run_id": "run_567",
  "agent_id": "agent_789",
  "data": {
    "task_id": "task_456",
    "error_type": "llm_error",
    "error_code": "RATE_LIMIT_EXCEEDED",
    "error_message": "Rate limit exceeded for gpt-4. Please try again in 60 seconds.",
    "retry_count": 3,
    "max_retries": 3,
    "fatal": true,
    "fallback_triggered": false,
    "context": {
      "model": "gpt-4",
      "provider": "openai",
      "last_successful_step": "generate_jwt_middleware",
      "tool_call_in_progress": "create_database_schema"
    },
    "suggested_actions": [
      "Retry with gpt-3.5-turbo as fallback",
      "Wait 60 seconds and retry",
      "Use claude-3-opus alternative"
    ]
  }
}
```

**Error Types:**
- `timeout`: Operation exceeded time limit
- `llm_error`: Language model API error
- `tool_error`: Code execution or tool failure
- `validation_error`: Input validation failure
- `quota_exceeded`: Usage quota reached
- `authentication_error`: Invalid credentials
- `permission_error`: Insufficient permissions

**Consumers:**
- Alert Service (P1/P2 alerts)
- Frontend (error display to user)
- Retry Service (automatic retry logic)
- Support Dashboard (customer issue tracking)

---

### 2. Agent Execution Events

#### `agent.message`

**Description**: Emitted when agent sends or receives a message

**Priority**: Medium
**Retention**: 30 days
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "agent.message",
  "timestamp": "2024-01-15T10:02:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "run_id": "run_567",
  "agent_id": "agent_789",
  "data": {
    "role": "assistant",
    "message": "I'll generate the authentication system using the JWT pattern. First, I'll create the middleware.",
    "tokens": 450,
    "metadata": {
      "tools_called": ["file_writer", "shell_executor"],
      "tool_results": [
        {"tool": "file_writer", "status": "success"},
        {"tool": "shell_executor", "status": "success"}
      ],
      "reasoning_steps": 3,
      "confidence": 0.92
    },
    "conversation_id": "conv_001",
    "message_index": 5
  }
}
```

**Role Types:**
- `system`: System instructions and context
- `user`: User input to agent
- `assistant`: Agent response/thoughts
- `tool`: Tool execution results

**Consumers:**
- Frontend (real-time conversation display)
- Analytics (agent behavior analysis)
- Audit Service (compliance logging)

---

### 3. Tool Execution Events

#### `tool.call`

**Description**: Emitted when a tool is invoked

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "tool.call",
  "timestamp": "2024-01-15T10:02:30Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "run_id": "run_567",
  "agent_id": "agent_789",
  "data": {
    "tool_id": "tool_001",
    "tool_name": "file_writer",
    "arguments": {
      "path": "/workspace/auth/jwt_middleware.py",
      "content": "<generated code>",
      "overwrite": false
    },
    "task_id": "task_456",
    "execution_context": {
      "sandbox_id": "sandbox_123",
      "timeout_seconds": 30,
      "memory_limit_mb": 512
    }
  }
}
```

**Consumers:**
- Tool Execution Service (actual tool execution)
- Audit Service (compliance tracking)
- Security Monitor (suspicious activity detection)

---

#### `tool.result`

**Description**: Emitted when tool execution completes

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "tool.result",
  "timestamp": "2024-01-15T10:02:35Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "run_id": "run_567",
  "agent_id": "agent_789",
  "data": {
    "tool_id": "tool_001",
    "tool_name": "file_writer",
    "status": "success",
    "result": {
      "file_path": "/workspace/auth/jwt_middleware.py",
      "size_bytes": 4500,
      "lines_written": 85
    },
    "duration_ms": 450,
    "task_id": "task_456"
  }
}
```

---

### 4. Artifact Events

#### `artifact.created`

**Description**: Emitted when a file or artifact is created

**Priority**: Medium
**Retention**: 90 days (or per retention policy)
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "artifact.created",
  "timestamp": "2024-01-15T10:02:35Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "data": {
    "artifact_id": "artifact_001",
    "artifact_type": "file",
    "task_id": "task_456",
    "path": "/workspace/auth/jwt_middleware.py",
    "size_bytes": 4500,
    "mime_type": "text/x-python",
    "checksum": "sha256:abc123...",
    "metadata": {
      "generated_by": "agent_789",
      "generation_tool": "file_writer",
      "lines_of_code": 85,
      "test_coverage": null,
      "quality_score": 0.85
    }
  }
}
```

---

### 5. Workflow Events

#### `workflow.started`

**Description**: Emitted when workflow execution begins

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "workflow.started",
  "timestamp": "2024-01-15T10:00:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "data": {
    "workflow_id": "wf_auth_flow",
    "workflow_execution_id": "exec_001",
    "workflow_name": "Generate Authentication Flow",
    "trigger": "manual",
    "triggered_by": "user_abc",
    "input_variables": {
      "framework": "FastAPI",
      "auth_type": "JWT",
      "database": "PostgreSQL"
    },
    "scheduled_execution_time": null,
    "expected_duration_seconds": 600,
    "priority": "high"
  }
}
```

---

#### `workflow.step.completed`

**Description**: Emitted when workflow step completes

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "workflow.step.completed",
  "timestamp": "2024-01-15T10:02:35Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "data": {
    "workflow_execution_id": "exec_001",
    "step_id": "step_generate_middleware",
    "step_name": "Generate JWT Middleware",
    "step_order": 1,
    "duration_seconds": 120,
    "retry_count": 0,
    "status": "success",
    "output_data": {
      "files_generated": 1,
      "test_coverage": 85.5,
      "quality_score": 0.92
    },
    "next_steps": ["step_generate_routes", "step_create_tests"]
  }
}
```

---

#### `workflow.completed`

**Description**: Emitted when workflow execution completes

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Stable)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "workflow.completed",
  "timestamp": "2024-01-15T10:10:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "data": {
    "workflow_execution_id": "exec_001",
    "workflow_id": "wf_auth_flow",
    "status": "completed",
    "total_duration_seconds": 600,
    "results": {
      "overall_quality_score": 0.88,
      "files_generated": 5,
      "total_lines_of_code": 450,
      "test_coverage": 82.3,
      "artifacts": [
        "file_auth_controller.py",
        "file_jwt_utils.py",
        "file_routes.py",
        "file_tests.py",
        "file_documentation.md"
      ]
    },
    "steps_summary": {
      "total_steps": 5,
      "completed_steps": 5,
      "failed_steps": 0,
      "skipped_steps": 0
    }
  }
}
```

---

### 6. System Events

#### `system.resource.warning`

**Description**: Emitted when resource usage exceeds warning threshold

**Priority**: Medium
**Retention**: 30 days
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "system.resource.warning",
  "timestamp": "2024-01-15T10:10:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "data": {
    "resource_type": "memory",
    "current_value": 85.5,
    "threshold": 80.0,
    "severity": "warning",
    "affected_services": ["agent_executor", "task_runner"],
    "recommendation": "Consider scaling up memory or reducing concurrent task limit",
    "projected_time_to_critical": "15 minutes"
  }
}
```

---

#### `system.resource.critical`

**Description**: Emitted when resource usage exceeds critical threshold

**Priority**: Critical
**Retention**: 90 days
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "system.resource.critical",
  "timestamp": "2024-01-15T10:25:00Z",
  "version": "1.0",
  "data": {
    "resource_type": "memory",
    "current_value": 95.2,
    "threshold": 90.0,
    "severity": "critical",
    "affected_services": ["agent_executor"],
    "immediate_action_required": "Scale up or kill non-critical tasks",
    "escalation_level": "page_oncall_engineer"
  }
}
```

---

### 7. Security Events

#### `security.suspicious_activity`

**Description**: Emitted when suspicious security activity is detected

**Priority**: High
**Retention**: 365 days (compliance)
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "security.suspicious_activity",
  "timestamp": "2024-01-15T10:25:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "data": {
    "event_type": "suspicious_activity",
    "severity": "high",
    "user_id": "user_789",
    "ip_address": "192.168.1.100",
    "user_agent": "Python-http-client/2.1",
    "suspicious_activity": "Rate limit exceeded 10 times in 1 minute",
    "blocked": true,
    "block_duration_seconds": 3600,
    "risk_factors": [
      "abnormal_request_pattern",
      "known_vulnerable_user_agent"
    ],
    "recommended_action": "Investigate user behavior and consider account suspension"
  }
}
```

---

### 8. Billing Events

#### `billing.threshold.reached`

**Description**: Emitted when usage threshold is reached

**Priority**: High
**Retention**: 7 years (compliance)
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "billing.threshold.reached",
  "timestamp": "2024-01-15T10:25:00Z",
  "version": "1.0",
  "workspace_id": "ws_123",
  "data": {
    "workspace_id": "ws_123",
    "threshold_type": "monthly",
    "current_usage": 500.0,
    "threshold": 500.0,
    "percentage": 100,
    "alert_level": "critical",
    "cost_breakdown": {
      "openai": 420.0,
      "anthropic": 80.0
    },
    "projected_month_end": 650.0,
    "recommended_actions": [
      "Upgrade to higher tier",
      "Set stricter rate limits",
      "Review usage patterns"
    ]
  }
}
```

---

### 9. LLM Provider Events

#### `llm.provider.error`

**Description**: Emitted when LLM provider encounters an error

**Priority**: High
**Retention**: 90 days
**Version**: 1.0 (Beta)

```json
{
  "event_id": "evt_01HN...",
  "event_type": "llm.provider.error",
  "timestamp": "2024-01-15T10:25:00Z",
  "version": "1.0",
  "data": {
    "provider": "openai",
    "model": "gpt-4",
    "error_type": "rate_limit",
    "error_code": "429",
    "error_message": "Rate limit exceeded: 100 requests per minute",
    "retry_count": 3,
    "fallback_triggered": true,
    "fallback_to": {
      "provider": "anthropic",
      "model": "claude-3-opus"
    },
    "affected_workspaces": ["ws_123", "ws_456"]
  }
}
```

---

## Event Versioning Strategy

### Semantic Versioning

Events use semantic versioning to manage breaking changes:

```
Version Format: {major}.{minor}.{patch}

- Major (X.0.0): Breaking changes
  - Field removal
  - Field type change
  - Required field added
  - Event type renamed

- Minor (0.X.0): Backward compatible  
  - New optional field added
  - New event type added
  - New enum value (with fallback)

- Patch (0.0.X): Non-breaking
  - Documentation updates
  - Bug fixes in validation
  - Examples updated
```

### Backward Compatibility Policy

**Support Window**: 90 days for major versions
**Deprecation Notice**: 30 days before removal
**Migration Path**: Automated migration scripts provided

```python
# Example migration: v1.0 → v2.0
class EventMigration_v1_to_v2:
    """Migrate task.created from v1.0 to v2.0"""
    
    def migrate(self, event_data):
        v2_event = event_data.copy()
        
        # Add new optional field with default
        if "estimated_cost" not in v2_event.get("data", {}).get("task", {}):
            v2_event["data"]["task"]["estimated_cost"] = 0.0
            
        # Add priority field if missing
        if "priority" not in v2_event.get("data", {}).get("task", {}):
            v2_event["data"]["task"]["priority"] = "medium"
            
        v2_event["version"] = "2.0"
        return v2_event
```

### Consumer Version Detection

```python
# Consumer logic for handling multiple versions
def consume_event(event_data):
    version = event_data.get("version", "1.0")
    event_type = event_data["event_type"]
    
    # Route to appropriate handler
    if version == "1.0":
        return handle_v1(event_data)
    elif version == "2.0":
        # Migrate on-the-fly if needed
        if should_migrate():
            event_data = migrate_v1_to_v2(event_data)
        return handle_v2(event_data)
    else:
        raise UnsupportedVersionError(f"Unsupported version: {version}")
```

## Event Delivery Guarantees

### Delivery Semantics

**At-Least-Once Delivery**: For critical events (task.*, billing.*)
**At-Most-Once Delivery**: For non-critical events (metrics, analytics)

### Ordering Guarantees

- **Per-Task Ordering**: Events for same task_id delivered in order
- **Per-Workspace Ordering**: Guaranteed for critical events
- **Cross-Task Ordering**: Best effort, eventual consistency

### Idempotency

Event consumers must be idempotent. Use `event_id` for deduplication:

```python
# Example: Idempotent event processing
def process_event(event_data, db_connection):
    event_id = event_data["event_id"]
    
    # Check if already processed
    if is_duplicate(event_id, db_connection):
        logger.info(f"Event {event_id} already processed, skipping")
        return
    
    # Process event
    try:
        result = handle_event(event_data)
        
        # Mark as processed
        mark_processed(event_id, db_connection)
        
        return result
    except Exception as e:
        # Log but don't mark as processed (will retry)
        logger.error(f"Event processing failed for {event_id}: {e}")
        raise
```

## Event Broadcasting

### Using Event System

```python
from backend.services import get_event_broadcaster
from backend.schemas import EventPayload

# Get broadcaster instance
broadcaster = get_event_broadcaster()

# Create event payload
event = EventPayload(
    event_type="task.created",
    workspace_id="ws_123",
    task_id="task_456",
    data={
        "task": {
            "id": "task_456",
            "title": "Generate authentication system",
            # ...
        }
    }
)

# Publish event
await broadcaster.publish(event)
```

### Subscribing to Events

```python
# Subscribe to specific task events
queue = await broadcaster.subscribe(
    subscriber_id="frontend_client_123",
    channels=["task:task_456", "workspace:ws_123"]
)

# Receive events
while True:
    event = await queue.get()
    
    if event["event_type"] == "task.completed":
        # Handle completion
        update_task_ui(event["data"])
    
    elif event["event_type"] == "task.error":
        # Handle error
        display_error(event["data"])
```

### Wildcard Subscriptions

```python
# Subscribe to all events
queue = await broadcaster.subscribe(
    subscriber_id="audit_service",
    channels=["all"]
)

# Subscribe to all workspace events
queue = await broadcaster.subscribe(
    subscriber_id="workspace_admin",
    channels=["workspace:ws_123"]
)

# Subscribe to all task events
queue = await broadcaster.subscribe(
    subscriber_id="task_monitor",
    channels=["task:*", "task:task_456"]
)
```

## Event Schema Validation

### JSON Schema Validation

```python
from jsonschema import validate, ValidationError

TASK_CREATED_SCHEMA = {
    "type": "object",
    "required": ["event_type", "timestamp", "workspace_id", "data"],
    "properties": {
        "event_type": {"type": "string", "enum": ["task.created"]},
        "timestamp": {"type": "string", "format": "date-time"},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "workspace_id": {"type": "string"},
        "task_id": {"type": "string"},
        "data": {
            "type": "object",
            "required": ["task", "user"],
            "properties": {
                "task": {
                    "type": "object",
                    "required": ["id", "title", "type"],
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string", "minLength": 1},
                        "type": {"enum": ["code_generation", "refactoring", "testing", "documentation"]}
                    }
                }
            }
        }
    }
}

def validate_event(event_data):
    try:
        schema = get_schema_for_event(event_data["event_type"])
        validate(instance=event_data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)
```

## Best Practices

### 1. Event Design

**✅ DO:**
- Keep events small and focused
- Include only necessary data in payload
- Use consistent naming conventions (snake_case)
- Include timestamps in UTC
- Version events from day one
- Document event schemas

**❌ DON'T:**
- Include PII in events (hash/anonymize)
- Create events larger than 1MB
- Use ambiguous event types
- Break backward compatibility without migration plan
- Forget to handle duplicate events

### 2. Event Consumption

**✅ DO:**
- Implement idempotent consumers
- Use correlation IDs for tracing
- Validate event schemas
- Handle unknown event versions gracefully
- Implement retry logic with exponential backoff
- Monitor consumer lag

**❌ DON'T:**
- Block event processing on slow operations
- Make assumptions about event ordering (except where guaranteed)
- Ignore event versions
- Fail silently on validation errors

### 3. Event Production

**✅ DO:**
- Use strongly-typed event models
- Validate before publishing
- Include workspace_id for isolation
- Set appropriate retention policies
- Monitor publication success rates
- Implement circuit breakers

**❌ DON'T:**
- Publish events in database transactions (risk of inconsistency)
- Swallow publication errors
- Publish before state changes are persisted
- Create events without version field

## Testing Events

### Integration Tests

```python
import pytest
from backend.services import get_event_broadcaster
from backend.schemas import EventPayload

@pytest.mark.asyncio
async def test_task_created_event():
    """Test task.created event publishing and consumption."""
    
    broadcaster = get_event_broadcaster()
    
    # Subscribe to events
    queue = await broadcaster.subscribe(
        "test_subscriber",
        ["workspace:ws_test", "task:task_123"]
    )
    
    # Create and publish event
    event = EventPayload(
        event_type="task.created",
        workspace_id="ws_test",
        task_id="task_123",
        data={
            "task": {
                "id": "task_123",
                "title": "Test Task",
                "type": "code_generation"
            }
        }
    )
    
    await broadcaster.publish(event)
    
    # Receive event
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    
    assert received["event_type"] == "task.created"
    assert received["workspace_id"] == "ws_test"
    assert received["task_id"] == "task_123"
```

## Migration Guide

### Adding New Event Types

1. **Define Schema:**
   ```python
   # backend/schemas.py
   class MyNewEvent(BaseModel):
       event_type: Literal["my.new.event"] = "my.new.event"
       data: MyNewEventData
       version: str = "1.0"
   ```

2. **Update Consumer Filters:**
   ```python
   # In consumers that need this event
   await broadcaster.subscribe(
       "my_consumer",
       channels=["my", "new", "event_types"]
   )
   ```

3. **Add Validation:**
   ```python
   # Add schema to validation registry
   SCHEMA_REGISTRY["my.new.event"] = MY_NEW_EVENT_SCHEMA
   ```

4. **Update Documentation:**
   - Add to event catalog
   - Document in API docs
   - Update consumer guides

## Support & Troubleshooting

### Common Issues

**1. Events not being received:**
- Check subscription channels match event channels
- Verify WebSocket connection is active
- Check for channel name typos

**2. Duplicate events:**
- Implement idempotency using event_id
- Check for multiple subscriptions
- Verify event replay configuration

**3. Event validation failures:**
- Check version compatibility
- Validate required fields are present
- Check data types match schema

**4. High event latency:**
- Monitor consumer lag
- Scale out consumer instances
- Check event size (should be <1MB)

### Monitoring

Key metrics to monitor:
- Event publication success rate
- Consumer lag (time between publish and consume)
- Event processing duration
- Dead letter queue size
- Event size distribution
- Schema validation failure rate

## References

- [Event System Implementation](../services/events.py)
- [Event Schemas](../schemas.py)
- [Audit Logger Implementation](../services/audit/logger.py)
- [Workflow Telemetry](../WORKFLOW_TELEMETRY.md)
- [OpenAPI Specification](../schemas/openapi.yml)

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2024-01-15 | Initial event contract specification | DevSecOps |
| 1.1 | 2024-01-20 | Added billing events, security events | DevSecOps |

## Contact

For questions or clarifications, contact:
- Technical Lead: tech-lead@mgx-ai.com
- DevSecOps: devsecops@mgx-ai.com
- Event System Issues: create GitHub issue with `event-system` label