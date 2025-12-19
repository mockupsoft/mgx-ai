# Workflow / Multi-Agent / Knowledge Base Testing

This repo contains a set of focused tests that validate the core orchestration layers:

- **Task execution lifecycle** (analysis → plan → approval → execution → completion)
- **Knowledge base semantic search + RAG prompt enhancement**
- **LLM provider routing + fallback behaviour**
- **Lightweight integration scenarios** showing how these building blocks compose

The tests are designed to run **without external services** (no hosted LLMs, no vector DB, no Docker daemon), using mocks and in-memory stubs.

## Test files

### `backend/tests/test_multi_agent_workflow.py`
Validates the `TaskExecutor` lifecycle:

- events emitted in the expected order (`analysis_start`, `plan_ready`, `approval_required`, `approved`, `completion`)
- rejection short-circuits execution (`failure` without calling the team)
- concurrent runs don’t mix events across `run:{id}` channels

### `backend/tests/test_rag_knowledge.py`
Validates knowledge base behaviour using a deterministic in-memory vector DB:

- knowledge items stored in DB and searched via semantic search
- filters work (category + language)
- vector DB failures gracefully fall back to text search
- RAG prompt enhancement includes retrieved examples
- usage tracking increments `usage_count` and `relevance_score`

### `backend/tests/test_llm_routing.py`
Validates routing and fallback behaviour:

- routing strategy respects provider availability
- fallback chain is executed when the primary provider errors
- cost tracking is only recorded for the *successful* call (no double-charge)

### `backend/tests/test_integration_scenarios.py`
A small set of integration-style checks:

- cost-optimized vs quality-optimized routing selections
- RAG-enhanced prompt can be composed as the input for an LLM generation call

## Running tests

From the repo root:

```bash
pytest
```

To run only the workflow/KB/LLM tests:

```bash
pytest -q \
  backend/tests/test_multi_agent_workflow.py \
  backend/tests/test_rag_knowledge.py \
  backend/tests/test_llm_routing.py \
  backend/tests/test_integration_scenarios.py
```
