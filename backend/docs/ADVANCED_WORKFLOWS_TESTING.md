# Advanced Workflows Testing Guide

## Overview

This document describes the testing strategy and implementation for advanced workflow features in the MGX Agent platform.

## Test Coverage

We have implemented comprehensive tests covering the following areas:

### 1. Human-in-the-Loop Approval (`backend/tests/test_human_approval.py`)
- **Workflow Pausing**: Verifies that workflows pause when `auto_approve_plan` is False.
- **Approval Process**: Tests the manual approval flow (`approve_plan()`).
- **Auto-Approval**: Tests the `auto_approve_plan` configuration.
- **Change Requests**: Tests the revision loop when a reviewer requests changes.

### 2. Incremental Development (`backend/tests/test_incremental_development.py`)
- **Feature Addition**: Tests adding new features to an existing project structure.
- **Bug Fixes**: Tests identifying and fixing bugs in existing code.
- **Refactoring**: Tests code refactoring workflows.
- **Knowledge Reuse**: Verifies that agents respect existing project conventions.

### 3. Retry Mechanisms (`backend/tests/test_retry_mechanisms.py`)
- **Transient Errors**: Tests automatic retries for transient failures (network, etc.).
- **Exponential Backoff**: Verifies that retry delays increase exponentially.
- **Max Retries**: Checks that the system stops retrying after the configured limit.

### 4. Concurrent Execution (`backend/tests/test_concurrent_execution.py`)
- **Parallel Tasks**: Tests running multiple independent tasks simultaneously.
- **Isolation**: Verifies that data does not leak between concurrent workflows.

### 5. Agent Memory (`backend/tests/test_agent_memory.py`)
- **Retention**: Tests that agents remember previous actions and context.
- **Pruning**: Verifies that memory is cleaned up when limits are reached (LRU).
- **Context Persistence**: Checks that context survives across execution rounds.

### 6. Workflow States (`backend/tests/test_workflow_states.py`)
- **State Transitions**: Tests transitions between Planning, Execution, and Completed states.
- **Progress Tracking**: Verifies that progress is accurately recorded.
- **Metrics**: Checks that task metrics (success, duration, etc.) are collected.

### 7. Complex Scenarios (`backend/tests/test_complex_scenarios.py`)
- **Full Lifecycle**: End-to-end test of a complex workflow with feedback loops.
- **Parallel Complex Workflows**: Stress test with multiple complex scenarios.

## Running Tests

To run the advanced workflow tests:

```bash
pytest backend/tests/test_human_approval.py \
       backend/tests/test_incremental_development.py \
       backend/tests/test_retry_mechanisms.py \
       backend/tests/test_concurrent_execution.py \
       backend/tests/test_agent_memory.py \
       backend/tests/test_workflow_states.py \
       backend/tests/test_complex_scenarios.py
```

## Implementation Details

- **Mocking**: Tests use `unittest.mock` to simulate LLM responses and avoid external API calls.
- **Async Testing**: Tests are asynchronous and verify the async nature of the agent workflows.
- **Isolation**: Each test runs with a fresh `MGXStyleTeam` instance to ensure isolation.

## Known Issues & Fixes

- **Missing `_format_output`**: A bug was identified where `WriteCode` action called a missing `_format_output` method. This has been fixed by adding a placeholder implementation in `mgx_agent/actions.py`.
- **Environment Dependencies**: The test environment lacked some dependencies (`fastapi`, `aiosqlite`). `backend/tests/conftest.py` was updated to robustly handle missing dependencies.
