# Workflow Telemetry and Monitoring (Phase 10)

## Overview

Phase 10 introduces comprehensive telemetry and monitoring capabilities for workflow execution. This document describes the APIs, data structures, and usage patterns for tracking workflow performance and history.

## Features

- **Execution Timeline**: Detailed per-step execution history with timestamps and metrics
- **Step Metrics**: Duration, retry count, input/output summaries for each step
- **Aggregated Metrics**: Workflow-level success rates, duration statistics
- **Historical Tracking**: Complete execution history with status transitions
- **WebSocket Events**: Real-time execution status updates

## REST API Endpoints

### Telemetry Endpoints

#### Get Workflow Execution Timeline

```
GET /api/workflows/executions/{execution_id}/timeline
```

Returns a detailed timeline of workflow execution with per-step metrics.

**Parameters:**
- `execution_id` (path): ID of the workflow execution

**Headers:**
- `X-Workspace-Id` or `X-Workspace-Slug`: Workspace context

**Response (200 OK):**
```json
{
  "execution_id": "exec-123",
  "workflow_id": "workflow-456",
  "status": "completed",
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:02:30Z",
  "total_duration_seconds": 150.5,
  "step_count": 3,
  "completed_step_count": 3,
  "failed_step_count": 0,
  "skipped_step_count": 0,
  "step_timeline": [
    {
      "step_id": "step-001",
      "step_name": "initialize",
      "step_order": 1,
      "status": "completed",
      "started_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:00:30Z",
      "duration_seconds": 30.0,
      "retry_count": 0,
      "error_message": null,
      "input_summary": {
        "data_size": 1024
      },
      "output_summary": {
        "processed_records": 100
      }
    },
    {
      "step_id": "step-002",
      "step_name": "process",
      "step_order": 2,
      "status": "completed",
      "started_at": "2024-01-15T10:00:30Z",
      "completed_at": "2024-01-15T10:02:00Z",
      "duration_seconds": 90.0,
      "retry_count": 1,
      "error_message": null,
      "input_summary": {
        "batch_size": 100
      },
      "output_summary": {
        "results": "success"
      }
    },
    {
      "step_id": "step-003",
      "step_name": "finalize",
      "step_order": 3,
      "status": "completed",
      "started_at": "2024-01-15T10:02:00Z",
      "completed_at": "2024-01-15T10:02:30Z",
      "duration_seconds": 30.5,
      "retry_count": 0,
      "error_message": null
    }
  ],
  "error_message": null
}
```

**Error Responses:**
- `404 Not Found`: Execution not found or not in active workspace
- `403 Forbidden`: Insufficient permissions

**Usage:**
```python
import requests

response = requests.get(
    f"http://localhost:8000/api/workflows/executions/{execution_id}/timeline",
    headers={"X-Workspace-Id": workspace_id}
)
timeline = response.json()

# Process timeline
for step in timeline["step_timeline"]:
    print(f"{step['step_name']}: {step['duration_seconds']}s")
```

#### Get Workflow Metrics

```
GET /api/workflows/{workflow_id}/metrics
```

Returns aggregated metrics for a workflow across all executions.

**Parameters:**
- `workflow_id` (path): ID of the workflow

**Headers:**
- `X-Workspace-Id` or `X-Workspace-Slug`: Workspace context

**Response (200 OK):**
```json
{
  "total_duration_seconds": 450.75,
  "success_rate": 85.5,
  "total_executions": 10,
  "successful_executions": 8,
  "failed_executions": 2,
  "average_duration_seconds": 45.075,
  "min_duration_seconds": 25.3,
  "max_duration_seconds": 120.5
}
```

**Metrics Explained:**
- `success_rate`: Percentage of successful executions (0-100)
- `average_duration_seconds`: Mean execution time
- `min_duration_seconds`: Fastest execution
- `max_duration_seconds`: Slowest execution

**Usage:**
```python
response = requests.get(
    f"http://localhost:8000/api/workflows/{workflow_id}/metrics",
    headers={"X-Workspace-Id": workspace_id}
)
metrics = response.json()

print(f"Success Rate: {metrics['success_rate']:.1f}%")
print(f"Avg Duration: {metrics['average_duration_seconds']:.1f}s")
```

#### List Workflow Executions

```
GET /api/workflows/{workflow_id}/executions
```

List all executions for a workflow with optional filtering.

**Parameters:**
- `workflow_id` (path): ID of the workflow
- `skip` (query): Number of results to skip (default 0)
- `limit` (query): Number of results to return (default 10, max 100)
- `status` (query): Filter by status (pending, running, completed, failed, cancelled, timeout)

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "exec-001",
      "workflow_id": "workflow-456",
      "execution_number": 1,
      "status": "completed",
      "started_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:02:30Z",
      "duration": 150.0,
      "input_variables": {
        "mode": "standard"
      },
      "results": {
        "output": "success"
      },
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:02:30Z"
    }
  ],
  "total": 10,
  "skip": 0,
  "limit": 10
}
```

#### Get Workflow Execution Details

```
GET /api/workflows/executions/{execution_id}
```

Get detailed information about a specific execution.

**Parameters:**
- `execution_id` (path): ID of the execution

**Response (200 OK):**
```json
{
  "id": "exec-001",
  "workflow_id": "workflow-456",
  "execution_number": 1,
  "status": "completed",
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:02:30Z",
  "duration": 150.0,
  "input_variables": {
    "mode": "standard"
  },
  "results": {
    "output": "success"
  },
  "error_message": null,
  "step_executions": [
    {
      "id": "step-exec-001",
      "execution_id": "exec-001",
      "step_id": "step-001",
      "status": "completed",
      "started_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:00:30Z",
      "duration": 30.0,
      "retry_count": 0,
      "output_data": {
        "records": 100
      }
    }
  ],
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:02:30Z"
}
```

### Workflow Management Endpoints

See [BACKEND_README.md](./BACKEND_README.md#workflows-phase-10) for complete workflow management API reference.

## WebSocket Events

### Workflow Execution Events

```
ws://{host}/ws/workflows/{workflow_id}
```

Subscribe to real-time execution events for a workflow.

**Events:**

#### `workflow_started`
```json
{
  "event": "workflow_started",
  "data": {
    "execution_id": "exec-001",
    "workflow_id": "workflow-456",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

#### `workflow_completed`
```json
{
  "event": "workflow_completed",
  "data": {
    "execution_id": "exec-001",
    "workflow_id": "workflow-456",
    "status": "completed",
    "duration_seconds": 150.5,
    "timestamp": "2024-01-15T10:02:30Z"
  }
}
```

#### `workflow_failed`
```json
{
  "event": "workflow_failed",
  "data": {
    "execution_id": "exec-001",
    "workflow_id": "workflow-456",
    "error": "Step 'process' failed",
    "timestamp": "2024-01-15T10:01:45Z"
  }
}
```

### Step Execution Events

```
ws://{host}/ws/workflows/{workflow_id}/step/{step_id}
```

Subscribe to real-time events for a specific step.

**Events:**

#### `step_started`
```json
{
  "event": "step_started",
  "data": {
    "execution_id": "exec-001",
    "step_id": "step-001",
    "step_name": "initialize",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

#### `step_completed`
```json
{
  "event": "step_completed",
  "data": {
    "execution_id": "exec-001",
    "step_id": "step-001",
    "step_name": "initialize",
    "duration_seconds": 30.0,
    "output": {
      "records": 100
    },
    "timestamp": "2024-01-15T10:00:30Z"
  }
}
```

#### `step_failed`
```json
{
  "event": "step_failed",
  "data": {
    "execution_id": "exec-001",
    "step_id": "step-002",
    "step_name": "process",
    "error": "Timeout exceeded",
    "retry_count": 1,
    "timestamp": "2024-01-15T10:01:00Z"
  }
}
```

## Data Structures

### WorkflowExecutionTimeline

```python
class WorkflowExecutionTimeline(BaseModel):
    execution_id: str
    workflow_id: str
    status: str  # completed, failed, running, etc.
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_duration_seconds: Optional[float]
    
    # Aggregated step counts
    step_count: int
    completed_step_count: int
    failed_step_count: int
    skipped_step_count: int
    
    step_timeline: List[WorkflowStepTimelineEntry]
    error_message: Optional[str]
```

### WorkflowStepTimelineEntry

```python
class WorkflowStepTimelineEntry(BaseModel):
    step_id: str
    step_name: str
    step_order: int
    status: str  # completed, failed, skipped, pending, running
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    retry_count: int
    error_message: Optional[str]
    input_summary: Optional[Dict]  # Truncated for large inputs
    output_summary: Optional[Dict]  # Truncated for large outputs
```

### WorkflowMetricsSummary

```python
class WorkflowMetricsSummary(BaseModel):
    total_duration_seconds: float
    success_rate: float  # 0-100
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_seconds: float
    min_duration_seconds: Optional[float]
    max_duration_seconds: Optional[float]
```

## Example Workflows

Four example workflows are provided in `examples/workflows/`:

### basic_sequence.json
A simple 3-step workflow that executes sequentially:
1. Initialize
2. Process (depends on Initialize)
3. Finalize (depends on Process)

**Use case:** Simple data processing pipelines

### parallel_processing.json
Splits work across 3 parallel branches then merges:
1. Data Preparation
2. Branch A (parallel, depends on Data Preparation)
3. Branch B (parallel, depends on Data Preparation)
4. Branch C (parallel, depends on Data Preparation)
5. Merge Results (depends on all branches)

**Use case:** Processing large datasets in parallel

### conditional_workflow.json
Branches execution based on input mode:
1. Evaluate Condition
2. Fast Process (mode == 'fast')
3. Standard Process (mode == 'standard')
4. Thorough Process (mode == 'thorough')
5. Aggregate Results

**Use case:** Adaptive workflows based on configuration

### data_pipeline.json
Full 7-step ETL pipeline:
1. Validate Source
2. Extract Data
3. Transform Data
4. Validate Transformation
5. Load Data
6. Post-Load Validation
7. Cleanup

**Use case:** Production data pipelines with validation

## Seeding Example Workflows

To load example workflows into your workspace:

```bash
# Basic usage (uses first project in workspace)
python -m backend.scripts.seed_workflows \
  --workspace-id <workspace_id>

# Specify project
python -m backend.scripts.seed_workflows \
  --workspace-id <workspace_id> \
  --project-id <project_id>

# Skip existing workflows
python -m backend.scripts.seed_workflows \
  --workspace-id <workspace_id> \
  --skip-existing
```

## UI Integration Guide

### Rendering Execution Timeline

```javascript
// Fetch timeline data
const response = await fetch(
  `/api/workflows/executions/${executionId}/timeline`,
  { headers: { 'X-Workspace-Id': workspaceId } }
);
const timeline = await response.json();

// Render timeline visualization
timeline.step_timeline.forEach(step => {
  const duration = step.duration_seconds || 0;
  const startTime = new Date(step.started_at);
  const endTime = new Date(step.completed_at);
  
  console.log(`${step.step_name}: ${duration}s`);
});

// Show aggregated stats
console.log(`Total: ${timeline.total_duration_seconds}s`);
console.log(`Success: ${timeline.completed_step_count}/${timeline.step_count}`);
```

### Displaying Metrics Dashboard

```javascript
// Fetch metrics
const response = await fetch(
  `/api/workflows/${workflowId}/metrics`,
  { headers: { 'X-Workspace-Id': workspaceId } }
);
const metrics = await response.json();

// Display metrics
const dashboard = {
  successRate: `${metrics.success_rate.toFixed(1)}%`,
  totalExecutions: metrics.total_executions,
  avgDuration: `${metrics.average_duration_seconds.toFixed(1)}s`,
  minDuration: `${metrics.min_duration_seconds?.toFixed(1)}s`,
  maxDuration: `${metrics.max_duration_seconds?.toFixed(1)}s`,
};
```

### Real-time Updates with WebSocket

```javascript
// Subscribe to workflow execution events
const ws = new WebSocket(
  `ws://localhost:8000/ws/workflows/${workflowId}`
);

ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  
  if (message.event === 'workflow_started') {
    console.log('Workflow started');
    startTimer();
  } else if (message.event === 'workflow_completed') {
    console.log(`Workflow completed in ${message.data.duration_seconds}s`);
    stopTimer();
  } else if (message.event === 'step_completed') {
    console.log(`${message.data.step_name} completed`);
    updateUI();
  }
});
```

## Performance Considerations

### Large Execution Histories

For workflows with thousands of executions:
- Use pagination (`skip`/`limit`) on the executions list
- Query metrics endpoint for aggregated statistics instead of processing all executions
- Implement caching for metrics endpoints

### Large Step Outputs

Input/output summaries in timeline entries are truncated:
- For full data, query the step execution details endpoint
- Consider streaming large outputs outside the workflow system

### Database Indexing

The following indexes are created to optimize telemetry queries:
- `idx_workflow_executions_workspace_status`: For filtering by workspace/status
- `idx_workflow_step_executions_execution`: For timeline queries
- `idx_workflow_executions_started_at`: For time-range queries

## Troubleshooting

### Timeline endpoint returns 404

- Verify the execution_id exists and belongs to your workspace
- Check workspace context headers/query params

### Metrics show 0% success rate

- Verify executions exist for the workflow
- Check that execution statuses are properly set to `completed` or `failed`

### WebSocket events not arriving

- Verify WebSocket connection is established (check browser DevTools)
- Ensure correct workflow_id in URL
- Check that events are actually occurring (monitor execution status)

## Database Schema

### workflow_executions

Stores execution records with timing data:
- `id`: Unique execution ID
- `workflow_id`: Reference to workflow
- `workspace_id`, `project_id`: Tenancy
- `execution_number`: Sequential counter
- `status`: Current status
- `started_at`, `completed_at`: Timestamps
- `duration`: Calculated duration in seconds
- `input_variables`, `results`: JSON payload
- `error_message`, `error_details`: Failure info

### workflow_step_executions

Stores per-step execution records:
- `id`: Unique step execution ID
- `execution_id`: Reference to parent execution
- `step_id`: Reference to workflow step
- `status`: Step status
- `started_at`, `completed_at`: Timestamps
- `duration`: Step duration
- `input_data`, `output_data`: JSON payload
- `retry_count`: Number of retries
- `error_message`: Failure reason

## See Also

- [BACKEND_README.md](./BACKEND_README.md#workflows-phase-10) - Workflow API reference
- `backend/schemas.py` - Pydantic schemas
- `backend/routers/workflows.py` - Implementation
- `examples/workflows/` - Example workflow definitions
- `backend/scripts/seed_workflows.py` - Workflow seeding script
