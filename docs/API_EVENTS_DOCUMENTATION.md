# API & Events Documentation

## Overview

This document describes the REST API and WebSocket event streaming interface for the MGX Agent system.

**API Version:** 0.1.0  
**Base URL:** `http://localhost:8000`  
**WebSocket URL:** `ws://localhost:8000`

## Table of Contents

1. [Authentication](#authentication)
2. [REST API Endpoints](#rest-api-endpoints)
3. [WebSocket Events](#websocket-events)
4. [Plan Approval Flow](#plan-approval-flow)
5. [Sample Requests](#sample-requests)
6. [Error Handling](#error-handling)

---

## Authentication

**Current Status:** No authentication required (development mode)

In production, the system would use:
- JWT tokens passed in `Authorization: Bearer {token}` header
- WebSocket authentication via token in query parameter
- CORS restrictions based on origin

---

## REST API Endpoints

### Health & Status

#### `GET /health/`
Check API health status.

**Response:**
```json
{
    "status": "ok",
    "timestamp": "2024-01-01T12:00:00Z",
    "version": "0.1.0"
}
```

---

### Tasks Management

#### `GET /api/tasks/`
List all tasks with pagination and filtering.

**Query Parameters:**
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum records to return (default: 10, max: 100)
- `status` (string): Filter by status (pending, running, completed, failed, cancelled, timeout)

**Response:**
```json
{
    "items": [
        {
            "id": "task_123",
            "name": "Analyze sales data",
            "description": "Analyze Q4 2024 sales performance",
            "config": {},
            "status": "pending",
            "max_rounds": 5,
            "max_revision_rounds": 2,
            "memory_size": 50,
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "success_rate": 0.0,
            "last_run_at": null,
            "last_run_duration": null,
            "last_error": null,
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z"
        }
    ],
    "total": 1,
    "skip": 0,
    "limit": 10
}
```

#### `POST /api/tasks/`
Create a new task.

**Request Body:**
```json
{
    "name": "Analyze sales data",
    "description": "Analyze Q4 2024 sales performance",
    "config": {},
    "max_rounds": 5,
    "max_revision_rounds": 2,
    "memory_size": 50
}
```

**Response:** (Same as GET /api/tasks/{task_id})

#### `GET /api/tasks/{task_id}`
Get a specific task.

**Response:**
```json
{
    "id": "task_123",
    "name": "Analyze sales data",
    ...
}
```

#### `PATCH /api/tasks/{task_id}`
Update a task.

**Request Body:** (All fields optional)
```json
{
    "name": "Updated name",
    "description": "Updated description",
    "max_rounds": 10
}
```

#### `DELETE /api/tasks/{task_id}`
Delete a task.

**Response:**
```json
{
    "status": "deleted",
    "task_id": "task_123"
}
```

---

### Runs Management

#### `GET /api/runs/`
List task runs with pagination and filtering.

**Query Parameters:**
- `task_id` (string): Filter by task ID
- `status` (string): Filter by status
- `skip` (int): Offset (default: 0)
- `limit` (int): Max results (default: 10)

**Response:**
```json
{
    "items": [
        {
            "id": "run_456",
            "task_id": "task_123",
            "run_number": 1,
            "status": "running",
            "plan": null,
            "results": null,
            "started_at": "2024-01-01T12:01:00Z",
            "completed_at": null,
            "duration": null,
            "error_message": null,
            "error_details": null,
            "memory_used": null,
            "round_count": null,
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T12:01:00Z"
        }
    ],
    "total": 1,
    "skip": 0,
    "limit": 10
}
```

#### `POST /api/runs/`
Create and execute a new run for a task.

**Request Body:**
```json
{
    "task_id": "task_123"
}
```

**Response:**
```json
{
    "id": "run_456",
    "task_id": "task_123",
    "run_number": 1,
    "status": "pending",
    ...
}
```

**Note:** Creating a run automatically triggers background execution, which will emit events.

#### `GET /api/runs/{run_id}`
Get a specific run.

#### `PATCH /api/runs/{run_id}`
Update a run's status.

**Query Parameters:**
- `status` (string): New status

#### `DELETE /api/runs/{run_id}`
Delete a run.

#### `POST /api/runs/{run_id}/approve`
Approve or reject a plan (critical for the approval flow).

**Request Body:**
```json
{
    "approved": true,
    "feedback": "Plan looks good, proceed with execution"
}
```

**Response:** Updated run object

#### `GET /api/runs/{run_id}/logs`
Get logs for a run.

---

### Metrics

#### `GET /api/metrics/`
List metrics with filtering.

**Query Parameters:**
- `task_id` (string): Filter by task
- `task_run_id` (string): Filter by run
- `name` (string): Filter by metric name (partial match)
- `skip` (int): Offset
- `limit` (int): Max results

**Response:**
```json
{
    "items": [
        {
            "id": "metric_789",
            "task_id": "task_123",
            "task_run_id": "run_456",
            "name": "execution_time",
            "metric_type": "timer",
            "value": 45.32,
            "unit": "seconds",
            "labels": {"stage": "analysis"},
            "timestamp": "2024-01-01T12:05:00Z",
            "created_at": "2024-01-01T12:05:00Z"
        }
    ],
    "total": 1,
    "skip": 0,
    "limit": 10
}
```

#### `GET /api/metrics/{metric_id}`
Get a specific metric.

#### `GET /api/metrics/task/{task_id}/summary`
Get aggregated metrics for a task across all runs.

**Response:**
```json
{
    "task_id": "task_123",
    "metric_count": 10,
    "metrics": {
        "execution_time": {
            "count": 5,
            "min": 30.5,
            "max": 60.2,
            "avg": 45.1,
            "last": 48.3
        },
        "token_usage": {
            "count": 5,
            "min": 1000,
            "max": 5000,
            "avg": 3000,
            "last": 4500
        }
    }
}
```

#### `GET /api/metrics/run/{run_id}/summary`
Get metrics for a specific run.

---

## WebSocket Events

### Connection Endpoints

#### `ws://localhost:8000/ws/tasks/{task_id}`
Subscribe to events for a specific task.

#### `ws://localhost:8000/ws/runs/{run_id}`
Subscribe to events for a specific run.

#### `ws://localhost:8000/ws/stream`
Subscribe to all events (global stream).

### Event Schema

All WebSocket messages follow this schema:

```json
{
    "event_type": "plan_ready",
    "timestamp": "2024-01-01T12:00:00Z",
    "task_id": "task_123",
    "run_id": "run_456",
    "data": {
        "plan": {
            "steps": ["step1", "step2"],
            "estimated_time": "5 minutes"
        }
    },
    "message": "Plan ready for approval"
}
```

### Event Types

#### `analysis_start`
Task analysis has started.

```json
{
    "event_type": "analysis_start",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Starting task analysis",
    "data": {}
}
```

#### `plan_ready`
Execution plan is ready for review. **User must approve before execution continues.**

```json
{
    "event_type": "plan_ready",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Plan ready for review",
    "data": {
        "plan": {
            "steps": ["analyze data", "generate report", "summarize"],
            "estimated_time": "5 minutes",
            "resources": ["agent1", "agent2"]
        }
    }
}
```

#### `approval_required`
Plan is awaiting user approval. Same as `plan_ready`.

#### `approved`
Plan was approved by user.

```json
{
    "event_type": "approved",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Plan approved, execution started",
    "data": {}
}
```

#### `rejected`
Plan was rejected by user.

```json
{
    "event_type": "rejected",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Plan rejected by user",
    "data": {}
}
```

#### `progress`
Execution progress update.

```json
{
    "event_type": "progress",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Step 1/3 completed: Analyzing data",
    "data": {
        "step": 1,
        "total_steps": 3,
        "current_phase": "analyzing",
        "progress_percent": 33
    }
}
```

#### `completion`
Task completed successfully.

```json
{
    "event_type": "completion",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Task completed successfully",
    "data": {
        "results": {
            "summary": "Analysis complete",
            "findings": [...]
        }
    }
}
```

#### `failure`
Task failed with error.

```json
{
    "event_type": "failure",
    "task_id": "task_123",
    "run_id": "run_456",
    "message": "Task failed: Connection timeout",
    "data": {
        "error": "Connection timeout",
        "stack_trace": "..."
    }
}
```

#### `cancelled`
Task was cancelled.

---

## Plan Approval Flow

The plan approval flow is a critical part of the system that requires user confirmation before execution:

### Step-by-Step Flow

1. **Client creates a run:**
   ```bash
   POST /api/runs/ {"task_id": "task_123"}
   ```
   Returns `run_456` with status `pending`

2. **Background executor starts:**
   - Emits `analysis_start` event
   - Analyzes the task
   - Generates an execution plan

3. **Plan ready event sent:**
   ```json
   {
       "event_type": "plan_ready",
       "task_id": "task_123",
       "run_id": "run_456",
       "data": {"plan": {...}},
       "message": "Plan ready for approval"
   }
   ```

4. **Client receives event and displays plan to user:**
   - WebSocket client receives the event
   - Frontend displays plan for review
   - User can approve or reject

5. **User approves/rejects:**
   ```bash
   POST /api/runs/run_456/approve
   {
       "approved": true,
       "feedback": "Plan looks good"
   }
   ```

6. **Executor receives approval:**
   - If approved: `approved` event sent, execution continues
   - If rejected: `rejected` event sent, task stops

7. **Execution continues (if approved):**
   - `progress` events sent during execution
   - `completion` or `failure` event at the end

### Timing Considerations

- **Approval timeout:** 5 minutes (300 seconds) by default
- If timeout expires, the task is marked as failed
- Client should implement reconnection logic to handle network issues

---

## Sample Requests

### Create a Task
```bash
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Analyze Q4 Sales",
    "description": "Analyze Q4 2024 sales data",
    "max_rounds": 5,
    "max_revision_rounds": 2,
    "memory_size": 50
  }'
```

### Create a Run (Triggers Execution)
```bash
curl -X POST http://localhost:8000/api/runs/ \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task_123"}'
```

### Approve a Plan
```bash
curl -X POST http://localhost:8000/api/runs/run_456/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "feedback": "Plan looks good, proceed"
  }'
```

### WebSocket Connection (Using wscat)
```bash
# Install wscat: npm install -g wscat

# Connect to task stream
wscat -c ws://localhost:8000/ws/tasks/task_123

# Connect to run stream
wscat -c ws://localhost:8000/ws/runs/run_456

# Connect to global stream
wscat -c ws://localhost:8000/ws/stream
```

### WebSocket Connection (JavaScript)
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/task_123');

ws.onopen = () => {
    console.log('Connected');
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log('Event:', message.event_type);
    
    // Handle plan approval
    if (message.event_type === 'plan_ready') {
        console.log('Plan:', message.data.plan);
        
        // User reviews plan and approves
        fetch(`/api/runs/${message.run_id}/approve`, {
            method: 'POST',
            body: JSON.stringify({
                approved: true,
                feedback: 'Looks good'
            })
        });
    }
    
    // Handle completion
    if (message.event_type === 'completion') {
        console.log('Results:', message.data.results);
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Disconnected');
    // Implement reconnection logic here
};
```

---

## Error Handling

### HTTP Error Responses

All error responses follow this format:

```json
{
    "detail": "Task not found"
}
```

### Common Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### WebSocket Error Handling

WebSocket connections can fail due to:
- Network issues
- Server restart
- Client going offline

**Client should implement:**

1. **Automatic reconnection:**
   ```javascript
   let ws;
   let reconnectAttempts = 0;
   const maxReconnectAttempts = 10;
   
   function connect() {
       ws = new WebSocket(`ws://localhost:8000/ws/tasks/${taskId}`);
       
       ws.onopen = () => {
           reconnectAttempts = 0;
       };
       
       ws.onclose = () => {
           if (reconnectAttempts < maxReconnectAttempts) {
               const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
               setTimeout(connect, delay);
               reconnectAttempts++;
           }
       };
   }
   ```

2. **Backpressure handling:**
   - Process events sequentially
   - Buffer events if processing is slow
   - Discard old events if buffer is full

3. **Heartbeat detection:**
   - Server sends `type: "heartbeat"` messages
   - Use as keep-alive signal
   - Detect dead connections

---

## Integration Notes

### Frontend (ai-front)

The frontend should:

1. **Create tasks** via `POST /api/tasks/`
2. **Create runs** via `POST /api/runs/`
3. **Connect WebSocket** to `ws/tasks/{task_id}` or `ws/runs/{run_id}`
4. **Listen for `plan_ready` events** and display plan to user
5. **Call `POST /api/runs/{run_id}/approve`** when user approves/rejects
6. **Handle all event types** for UI updates (progress, completion, failure)
7. **Implement reconnection logic** for WebSocket resilience

### Backend (This API)

The backend provides:

1. **REST CRUD** for tasks, runs, metrics
2. **Event broadcast** via WebSocket
3. **Plan approval flow** with user interaction
4. **Background execution** of tasks
5. **Metrics collection** and aggregation

---

## Future Enhancements

- [ ] Authentication & Authorization (JWT)
- [ ] Request rate limiting
- [ ] Event replay for late subscribers
- [ ] Metrics history and trending
- [ ] Task scheduling (cron, recurring)
- [ ] Multi-tenant support
- [ ] Audit logging
- [ ] Performance monitoring
- [ ] Cost tracking (token usage, compute)

---

## Support & Questions

For API issues or questions, refer to:
- OpenAPI docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- GitHub Issues: [project-url]/issues
