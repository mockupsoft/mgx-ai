# Cost Tracking & Resource Monitoring

**Phase 17 Implementation**

## Overview

The Cost Tracking & Resource Monitoring system provides comprehensive tracking of LLM API costs, token usage, compute resources, and budget management for workspaces and projects.

## Features

### 1. LLM Cost Tracking
- Track every LLM API call with provider, model, and token counts
- Automatic cost calculation based on current pricing
- Support for multiple providers: OpenAI, Anthropic/Claude, Mistral, Google, etc.
- Token usage statistics and analysis
- Latency tracking for performance monitoring

### 2. Compute Resource Tracking
- Track CPU, memory, GPU, storage, and bandwidth usage
- Sandbox execution time monitoring
- Cost calculation for all resource types
- Duration-based pricing for time-based resources

### 3. Budget Management
- Set monthly budgets for workspaces and projects
- Configurable alert thresholds (50%, 80%, 90%, 100%)
- Email notifications for budget alerts
- Hard limits to prevent overspending
- Automatic spending updates

### 4. Cost Optimization
- AI-powered cost optimization recommendations
- Model downgrade suggestions for simple tasks
- Token usage optimization tips
- Execution pattern analysis
- Cost forecasting and predictions

### 5. Reporting & Analytics
- Real-time cost dashboards
- Historical cost trends
- Breakdown by model, provider, and resource type
- Daily, weekly, and monthly summaries
- Cost per execution tracking

## Database Schema

### LLMCall
Tracks individual LLM API calls:
- `workspace_id`: Associated workspace
- `execution_id`: Task run or workflow execution
- `provider`: LLM provider (openai, claude, etc.)
- `model`: Model name (gpt-4, claude-3-opus, etc.)
- `tokens_prompt`: Prompt tokens used
- `tokens_completion`: Completion tokens generated
- `tokens_total`: Total tokens used
- `cost_usd`: Cost in USD
- `latency_ms`: API call latency
- `timestamp`: Call timestamp

### ResourceUsage
Tracks compute resource usage:
- `workspace_id`: Associated workspace
- `execution_id`: Task run or workflow execution
- `resource_type`: Type (cpu, memory, gpu, storage, etc.)
- `usage_value`: Amount used
- `unit`: Unit of measurement
- `cost_usd`: Cost in USD
- `duration_seconds`: Usage duration
- `timestamp`: Usage timestamp

### ExecutionCost
Aggregated cost summary per execution:
- `execution_id`: Task run or workflow ID (unique)
- `workspace_id`: Associated workspace
- `total_llm_cost`: Total LLM costs
- `total_compute_cost`: Total compute costs
- `total_cost`: Grand total
- `breakdown`: Detailed cost breakdown (JSON)
- `llm_call_count`: Number of LLM calls
- `total_tokens`: Total tokens used

### WorkspaceBudget
Budget configuration for workspaces:
- `workspace_id`: Associated workspace (unique)
- `monthly_budget_usd`: Monthly budget limit
- `current_month_spent`: Current spending
- `alert_threshold_percent`: Alert threshold (default: 80%)
- `alert_emails`: Email addresses for alerts
- `hard_limit`: Whether to enforce hard limit
- `alerts_sent`: History of alerts sent

### ProjectBudget
Budget configuration for projects:
- `project_id`: Associated project (unique)
- `workspace_id`: Parent workspace
- `monthly_budget_usd`: Monthly budget limit
- `current_month_spent`: Current spending

## API Endpoints

### Cost Tracking

#### Get Workspace Costs
```http
GET /api/workspaces/{workspace_id}/costs?period=month
```

Returns:
```json
{
  "period": "month",
  "total_cost": 1234.56,
  "llm_cost": 1000.00,
  "compute_cost": 234.56,
  "breakdown": {
    "llm": {
      "total": 1000.00,
      "tokens": 2500000,
      "calls": 150
    },
    "compute": {
      "total": 234.56,
      "records": 75
    }
  },
  "by_model": [
    {
      "provider": "openai",
      "model": "gpt-4",
      "cost": 800.00,
      "tokens": 2000000,
      "calls": 100
    }
  ],
  "by_resource": [
    {
      "resource_type": "cpu",
      "cost": 150.00,
      "usage": 3000.0,
      "count": 50
    }
  ],
  "trends": {
    "daily": [...],
    "forecast_eom": 2500.00,
    "forecast_confidence": "high"
  }
}
```

#### Get Execution Costs
```http
GET /api/executions/{execution_id}/costs
```

Returns:
```json
{
  "execution_id": "uuid",
  "total_cost": 45.67,
  "llm_cost": 40.00,
  "compute_cost": 5.67,
  "breakdown": {
    "llm": {
      "cost": 40.00,
      "tokens": 100000,
      "calls": 5
    },
    "compute": {
      "cost": 5.67,
      "by_type": {
        "cpu": {"cost": 3.00, "usage": 60.0},
        "memory": {"cost": 2.00, "usage": 200.0},
        "sandbox": {"cost": 0.67, "usage": 1}
      }
    }
  }
}
```

### Budget Management

#### Get Workspace Budget
```http
GET /api/workspaces/{workspace_id}/budget
```

#### Create/Update Workspace Budget
```http
POST /api/workspaces/{workspace_id}/budget
Content-Type: application/json

{
  "monthly_budget_usd": 5000.0,
  "alert_threshold_percent": 80,
  "alert_emails": ["admin@example.com"],
  "hard_limit": false
}
```

#### Check Budget Status
```http
GET /api/workspaces/{workspace_id}/budget/status
```

Returns:
```json
{
  "has_budget": true,
  "budget": 5000.0,
  "spent": 3500.0,
  "remaining": 1500.0,
  "usage_percent": 70.0,
  "alert_needed": false,
  "is_over_budget": false,
  "hard_limit": false
}
```

#### Create Project Budget
```http
POST /api/projects/{project_id}/budget?workspace_id=ws_id
Content-Type: application/json

{
  "monthly_budget_usd": 1000.0
}
```

### Cost Optimization

#### Get Recommendations
```http
GET /api/workspaces/{workspace_id}/cost-optimization?period=month
```

Returns:
```json
[
  {
    "type": "model_downgrade",
    "priority": "high",
    "title": "Use GPT-4 Turbo for simple tasks",
    "description": "You're using gpt-4 with average 300 tokens. Consider using gpt-4-turbo for 67% cost savings.",
    "current_model": "gpt-4",
    "recommended_model": "gpt-4-turbo",
    "estimated_savings": 670.0,
    "impact": "$670.00/month"
  }
]
```

#### Get Cost Forecast
```http
GET /api/workspaces/{workspace_id}/cost-forecast
```

Returns:
```json
{
  "current_month_spent": 1200.0,
  "llm_cost": 1000.0,
  "compute_cost": 200.0,
  "days_elapsed": 15,
  "total_days": 30,
  "daily_average": 80.0,
  "forecast_end_of_month": 2400.0,
  "forecast_confidence": 0.75,
  "projection_accuracy": "high"
}
```

#### Get Cost Statistics
```http
GET /api/workspaces/{workspace_id}/cost-stats
```

## Usage Examples

### Python Client

```python
import httpx

# Get workspace costs
async def get_costs(workspace_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/workspaces/{workspace_id}/costs",
            params={"period": "month"}
        )
        return response.json()

# Set up budget
async def setup_budget(workspace_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/workspaces/{workspace_id}/budget",
            json={
                "monthly_budget_usd": 5000.0,
                "alert_threshold_percent": 80,
                "alert_emails": ["admin@example.com"],
                "hard_limit": False
            }
        )
        return response.json()

# Get optimization recommendations
async def get_recommendations(workspace_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/workspaces/{workspace_id}/cost-optimization",
            params={"period": "month"}
        )
        return response.json()
```

### Service Layer Usage

```python
from backend.services.cost import (
    get_llm_tracker,
    get_compute_tracker,
    get_budget_manager,
)
from backend.db.session import get_db

async def track_llm_call():
    async for db in get_db():
        tracker = get_llm_tracker(db)
        
        await tracker.log_llm_call(
            workspace_id="ws_123",
            execution_id="exec_456",
            provider="openai",
            model="gpt-4",
            tokens_prompt=1000,
            tokens_completion=500,
            latency_ms=1500,
            metadata={"temperature": 0.7}
        )

async def track_sandbox():
    async for db in get_db():
        tracker = get_compute_tracker(db)
        
        await tracker.track_sandbox_execution(
            workspace_id="ws_123",
            execution_id="exec_456",
            cpu_cores=2.0,
            memory_mb=1024,
            duration_seconds=120
        )

async def check_budget():
    async for db in get_db():
        manager = get_budget_manager(db)
        
        # Check if execution can proceed
        result = await manager.can_execute(
            workspace_id="ws_123",
            estimated_cost=10.0
        )
        
        if not result["can_execute"]:
            print(f"Cannot execute: {result['reason']}")
```

## Pricing Configuration

Model pricing is configured in `backend/services/cost/llm_tracker.py`:

```python
PRICING_CONFIG = {
    "openai": {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    },
    "anthropic": {
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    },
    # ... more providers
}
```

Resource pricing in `backend/services/cost/compute_tracker.py`:

```python
RESOURCE_PRICING = {
    "cpu": {"unit": "core-hour", "cost_per_unit": 0.05},
    "memory": {"unit": "gb-hour", "cost_per_unit": 0.01},
    "gpu": {"unit": "gpu-hour", "cost_per_unit": 1.50},
    "storage": {"unit": "gb-month", "cost_per_unit": 0.10},
    "bandwidth": {"unit": "gb", "cost_per_unit": 0.12},
    "sandbox": {"unit": "execution-minute", "cost_per_unit": 0.002},
}
```

## Integration Points

### Automatic LLM Tracking
Integrate cost tracking into your agent/LLM wrapper:

```python
from backend.services.cost import get_llm_tracker
from backend.db.session import get_db

async def call_llm_with_tracking(
    workspace_id: str,
    execution_id: str,
    prompt: str,
    model: str = "gpt-4"
):
    # Make LLM call
    start_time = time.time()
    response = await openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Track cost
    async for db in get_db():
        tracker = get_llm_tracker(db)
        await tracker.log_llm_call(
            workspace_id=workspace_id,
            execution_id=execution_id,
            provider="openai",
            model=model,
            tokens_prompt=response.usage.prompt_tokens,
            tokens_completion=response.usage.completion_tokens,
            latency_ms=latency_ms
        )
    
    return response
```

### Automatic Resource Tracking
Integrate into sandbox execution:

```python
from backend.services.cost import get_compute_tracker
from backend.db.session import get_db

async def execute_with_tracking(
    workspace_id: str,
    execution_id: str,
    code: str
):
    start_time = time.time()
    
    # Execute in sandbox
    result = await sandbox.execute(code)
    
    duration = time.time() - start_time
    
    # Track resources
    async for db in get_db():
        tracker = get_compute_tracker(db)
        await tracker.track_sandbox_execution(
            workspace_id=workspace_id,
            execution_id=execution_id,
            cpu_cores=result.cpu_usage,
            memory_mb=result.memory_usage_mb,
            duration_seconds=duration
        )
    
    return result
```

### Budget Checks
Add budget checks before expensive operations:

```python
from backend.services.cost import get_budget_manager
from backend.db.session import get_db

async def execute_task_with_budget_check(
    workspace_id: str,
    task_id: str
):
    async for db in get_db():
        manager = get_budget_manager(db)
        
        # Check if can execute
        result = await manager.can_execute(
            workspace_id=workspace_id,
            estimated_cost=5.0  # Estimated task cost
        )
        
        if not result["can_execute"]:
            raise BudgetExceededError(result["reason"])
        
        # Proceed with execution
        await execute_task(task_id)
        
        # Check for alerts
        await manager.check_and_alert(workspace_id)
```

## Best Practices

### 1. Set Realistic Budgets
- Start with monitoring (no hard limits)
- Analyze spending patterns for 1-2 months
- Set budgets based on historical data
- Add 20-30% buffer for growth

### 2. Configure Alerts
- Set multiple threshold levels (50%, 80%, 90%)
- Use team email lists for alerts
- Monitor alerts regularly
- Adjust thresholds based on patterns

### 3. Regular Reviews
- Review cost dashboards weekly
- Check optimization recommendations monthly
- Update pricing configuration quarterly
- Audit anomalies immediately

### 4. Cost Optimization
- Use cheaper models for simple tasks
- Implement prompt caching
- Batch similar requests
- Monitor token usage patterns
- Set max_tokens limits

### 5. Resource Management
- Set reasonable sandbox timeouts
- Monitor memory usage
- Clean up unused resources
- Use resource pooling

## Troubleshooting

### High Costs
1. Check cost dashboard for anomalies
2. Review model usage distribution
3. Look for token usage spikes
4. Check execution frequency
5. Review optimization recommendations

### Budget Alerts Not Working
1. Verify budget is enabled
2. Check alert_emails configuration
3. Confirm spending is being tracked
4. Review alerts_sent history
5. Check email delivery logs

### Inaccurate Cost Calculations
1. Verify pricing configuration
2. Check for model name changes
3. Review token counts
4. Validate duration calculations
5. Check for missing provider configs

### Missing Cost Data
1. Verify tracking is integrated
2. Check database connectivity
3. Review error logs
4. Confirm workspace_id is correct
5. Check timestamp filters

## Performance Considerations

- Cost tracking adds minimal overhead (~10-50ms per call)
- Database queries are optimized with indexes
- Aggregations use efficient SQL functions
- Historical data can be archived after 12 months
- Use caching for frequently accessed summaries

## Security

- Budget data is workspace-scoped
- Only workspace members can view costs
- Budget limits prevent runaway spending
- Audit logs track all budget changes
- API endpoints require authentication

## Future Enhancements

- Real-time cost streaming
- Slack/Teams integrations
- Custom cost allocation tags
- Multi-currency support
- Advanced anomaly detection
- ML-based cost predictions
- Cost comparison across workspaces
- Detailed cost attribution

## Support

For issues or questions:
- Check logs in `backend/logs/`
- Review error messages in responses
- Consult API documentation at `/docs`
- Contact development team
