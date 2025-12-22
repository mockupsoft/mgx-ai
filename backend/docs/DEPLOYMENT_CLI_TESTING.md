# CLI & Deployment Integration Testing

This document details the comprehensive testing suite implemented for MGX CLI, Docker Compose deployment, Kubernetes manifests, configuration validation, and multi-environment setup.

## Test Suite Overview

The testing suite is designed to verify the reliability and correctness of deployment workflows and CLI operations. It uses `pytest` framework with `pytest-asyncio` for asynchronous testing.

### 1. CLI Command Testing (`backend/tests/test_cli_commands.py`)

Tests the `mgx` command-line interface functionality.

**Coverage:**
- `mgx --version`: Verifies version output.
- `mgx task`: Tests task creation with and without arguments.
- `mgx task --json`: Tests task creation from JSON input.
- `mgx task` (interactive): Mocks user confirmation input.
- `mgx list`: Verifies listing tasks.
- `mgx status`: Verifies checking task status.

### 2. Docker Compose Deployment (`backend/tests/test_docker_compose.py`)

Tests the Docker Compose configuration and deployment process.

**Coverage:**
- `.env` file validation: Checks for existence of configuration files.
- `docker compose build`: Verifies build command execution.
- `docker compose up`: Verifies service startup.
- Service Health: Mocks health checks for services (Postgres, Redis, MinIO).
- `docker-compose.yml`: Validates that all required services are defined.

### 3. Kubernetes Manifests (`backend/tests/test_kubernetes.py`)

Tests the Kubernetes YAML manifests for validity and best practices.

**Coverage:**
- YAML Validation: Ensures all manifests are valid YAML.
- Deployment Resources: Checks that deployments have CPU/Memory requests and limits defined.
- Service Definitions: Verifies service ports and selectors.

*(Note: These tests skip if `kubernetes/` directory is not present)*

### 4. Configuration Validation (`backend/tests/test_configuration.py`)

Tests the application configuration loading and validation logic.

**Coverage:**
- Default Settings: Verifies default values are loaded correctly.
- Environment Overrides: Tests that environment variables override defaults.
- Database URL: Verifies correct generation of database connection strings.
- Validation: Checks that invalid configurations are rejected (implicit via Pydantic).

### 5. Deployment Scenarios (`backend/tests/test_deployment_scenarios.py`)

Tests end-to-end deployment workflows.

**Coverage:**
- Full Deployment Flow: Simulates the sequence of Build -> Deploy -> Verify.
- Rollback Scenario: Simulates a failed deployment and subsequent rollback.

## Running Tests

To run the full deployment test suite:

```bash
pytest backend/tests/test_cli_commands.py \
       backend/tests/test_docker_compose.py \
       backend/tests/test_kubernetes.py \
       backend/tests/test_configuration.py \
       backend/tests/test_deployment_scenarios.py
```

## Environment Requirements

- Python 3.11+
- pytest
- docker (mocked in tests)
- kubectl (mocked in tests)

## Fixes Implemented

During the implementation of these tests, several issues in the codebase were identified and fixed:
- **Circular Imports**: Resolved circular dependencies in `backend.services.knowledge`.
- **Import Errors**: Fixed relative imports in `backend.routers` and `backend.services`.
- **Syntax Errors**: Fixed invalid syntax in `__init__.py` files and f-strings.
- **Dependency Issues**: Fixed `require_permission` dependency usage in `backend.services.auth.rbac`.
- **Missing Models**: Added missing `User` model to `backend.db.models.entities`.

The codebase is now more robust and testable.
