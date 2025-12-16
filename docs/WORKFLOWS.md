# Workflows (Phase 10) – Guide

This guide explains MGX’s workflow engine concepts, how to build workflow definitions, and how to monitor executions.

Quick links:

- API endpoints: **[API.md](./API.md)**
- WebSocket streams: **[WEBSOCKET.md](./WEBSOCKET.md)**
- Backend implementation: **[BACKEND_README.md](../BACKEND_README.md#workflows-phase-10)**
- Example workflow definitions: **[`examples/workflows/`](../examples/workflows/)**

---

## Concepts & terminology

### Workflow definition

A *workflow definition* (`WorkflowDefinition`) is a versioned blueprint containing:

- `steps[]`: the units of work
- `variables[]`: typed input variables accepted at execution time
- execution defaults like `timeout_seconds` and `max_retries`

### Step

A *step* (`WorkflowStep`) is a node in the workflow graph.

Key fields:

- `name`: unique within a workflow
- `step_type`: one of `task`, `agent`, `condition`, `parallel`, `sequential`
- `depends_on_steps`: dependencies (typically step names when authoring JSON)
- `timeout_seconds` / `max_retries`: per-step overrides
- `config`: free-form JSON for step-specific behavior

### Execution

A *workflow execution* (`WorkflowExecution`) is a single run of a workflow definition. Each step run is tracked by `WorkflowStepExecution`.

---

## Building workflows

### 1) Sequential workflows

The simplest pattern: each step depends on the previous step.

See example:

- `examples/workflows/sequential_task.json`

### 2) Parallel workflows

You can model parallelism by giving multiple steps the same dependency (fan-out), and then optionally joining later.

See example:

- `examples/workflows/parallel_agents.json`

Notes:
- The engine uses a dependency resolver to group steps that can run in parallel.
- Steps with no dependencies are entry points.

### 3) Conditional workflows

Conditional execution is controlled by `condition_expression`.

Current supported syntax is intentionally minimal:

- `${var_name}`: treated as a boolean (truthy/falsy)
- literals: `"true"`, `"1"`, `"yes"`, `"on"`

See example:

- `examples/workflows/conditional_workflow.json`

### 4) Retry & timeout policies

Defaults live on the workflow:

- `timeout_seconds`
- `max_retries`

And can be overridden per step:

- `steps[].timeout_seconds`
- `steps[].max_retries`

See example:

- `examples/workflows/with_retries.json`

---

## Agent assignment strategies

For `agent` steps, the engine uses `MultiAgentController` to pick an agent instance.

Set these in `steps[].config`:

- `assignment_strategy`: `round_robin`, `least_loaded`, `capability_match`, `resource_based`
- `required_capabilities`: list of strings

You can also pin a specific agent/definition:

- `agent_definition_id`
- `agent_instance_id`

See example:

- `examples/workflows/multi_agent_chain.json`

---

## Dependency resolution

MGX validates workflow graphs and prevents common issues:

- duplicate step names
- missing dependencies
- circular dependencies

Implementation:

- `backend/services/workflows/dependency_resolver.py`

Tip: keep step names stable; treat them like human-readable identifiers.

---

## Common patterns & best practices

- **Keep steps small** and focused; use `config` to parameterize behavior.
- **Prefer explicit timeouts** on slow steps.
- **Use retries for transient work** (network calls, external services), not for deterministic failures.
- **Avoid deeply nested conditional logic**; prefer clear branching with well-named boolean variables.
- **Monitor via WebSockets** for real-time UI updates.

---

## Importing example workflows

You can seed the JSON examples into a workspace:

```bash
python -m backend.scripts.seed_workflows --workspace-id <workspace_id> --project-id <project_id> --skip-existing
```

(See `backend/scripts/seed_workflows.py`.)
