# MGX AI (MGX Agent)

**AI-powered, multi-agent software engineering system with production-ready backend, workflow orchestration, and Git-aware code execution.**

Built on **MetaGPT** with a **FastAPI** backend, **PostgreSQL** persistence, **Redis** caching, and **MinIO** artifact storage. Supports multiple web and mobile-oriented stacks (including extended generator targets such as React Native, Flutter, and Go Fiber), deterministic constraints, automated testing, optional **Docker-in-Docker** sandbox runs for reviewer feedback, and enterprise-grade observability.

| Badge | Status |
|-------|--------|
| Status | ![status](https://img.shields.io/badge/status-production--ready-brightgreen) |
| CI Tests | ![Test Suite](https://github.com/mockupsoft/mgx-ai/actions/workflows/tests.yml/badge.svg) |
| Coverage | ![codecov](https://codecov.io/gh/mockupsoft/mgx-ai/branch/main/graph/badge.svg) |
| License | ![license](https://img.shields.io/github/license/mockupsoft/mgx-ai) |
| Python | ![python](https://img.shields.io/badge/python-3.11%2B-blue) |
| Backend | ![fastapi](https://img.shields.io/badge/FastAPI-async-009688) |
| CLI (PyPI) | ![pypi](https://img.shields.io/pypi/v/mgx-cli) |
| CLI (npm) | ![npm](https://img.shields.io/npm/v/@mgxai/cli) |

---

## Quick Links

- [Features](#features) | [Quick Start](#quick-start) | [Architecture](#architecture) | [Testing](#testing--quality)
- [API Docs](./docs/API.md) | [Deployment Guide](./DOCKER_DEPLOYMENT.md) | [CLI Guide](./docs/CLI.md)
- [Workflow Guide](./docs/WORKFLOWS.md) | [Git Integration](./docs/GIT_AWARE_EXECUTION.md) | [Web Stack Support](./docs/WEB_STACK_SUPPORT.md)

---

## Features

### ✅ Multi-Agent Orchestration & Coordination
Sophisticated multi-agent runtime simulating an AI engineering team (planner, implementer, reviewer roles) with task assignment, progress tracking, and stack-aware execution across 8 web frameworks.

### ✅ Intelligent Chat Interface
Smart question detection system that distinguishes between simple chat questions and complex code generation tasks. Simple questions receive direct LLM responses without plan generation, while complex tasks trigger the full multi-agent workflow. Features natural, conversational responses with temperature control and post-processing to filter generic LLM disclaimers.

### ✅ Workflow Engine with Dependency Resolution  
Production-grade DAG-based workflow orchestration with conditional steps, retries/timeouts, multi-agent parallel execution, and real-time telemetry. Supports complex CI/CD pipelines and automated code generation workflows.

### ✅ Git-Aware Code Execution (GitHub Integration)
Deep GitHub integration with repository linking, automated branch creation (`mgx/{task_slug}/run-{n}`), commit templating, and optional PR creation. Full git metadata tracking per execution.

### ✅ Artifact Management Pipeline
Complete artifact lifecycle management with MinIO/S3 storage, versioning, metadata tracking, and secure access controls. Integrated with workflow execution and code generation outputs.

### ✅ Template Library & Prompt Management
Extensible template system with stack-specific prompts, versioned templates, and dynamic parameter injection. Supports custom templates for different code generation scenarios.

### ✅ LLM Caching Layer
Intelligent response caching with in-memory LRU + TTL and optional Redis backend. Achieves 65-75% cache hit rates on iterative workflows with deterministic cache keys and comprehensive stats tracking.

### ✅ Multi-LLM Provider Support
Comprehensive LLM provider integration supporting OpenRouter, Google Gemini, Ollama, OpenAI, Anthropic, Mistral, and Together AI. Dynamic provider switching with automatic fallback and unified API interface. Supports provider-specific features like temperature control, streaming, and custom model selection.

### ✅ Observability (OTEL, Structured Logging)
Enterprise observability with OpenTelemetry tracing, structured logging, metrics collection, and performance profiling. Full integration with workflow execution and multi-agent coordination.

### ✅ Production Validation & Testing
130+ automated tests (80%+ coverage gate) including unit, integration, and e2e tests. CI/CD pipeline with GitHub Actions, automated validation, and comprehensive test reporting.

### ✅ CLI Integration (Python + NPM)
Dual CLI distribution via PyPI (`pip install mgx-cli`) and npm (`npm install -g @mgxai/cli`). Unified interface for task execution, workflow management, and system administration.

### ✅ Docker Self-Hosted Deployment
Production-ready Docker Compose stack with PostgreSQL, Redis, MinIO (S3-compatible), optional Kafka, and a **`docker:dind`** sidecar for isolated sandbox execution when the API container uses `DOCKER_HOST` (see development `docker-compose.override.yml`). Health checks, persistence, backups, and security hardening included.

### ✅ MGX Task History & Pipeline API
PostgreSQL-backed **`mgx_runs`** table for persisting multi-agent task outcomes; REST endpoints under **`/api/mgx/history`** (list, get, delete). **Sequential multi-task pipeline** via **`/api/mgx/pipeline`** using the in-process `BackgroundTaskRunner` and `mgx_pipeline` service (pipeline state is in-memory across restarts).

### ✅ Parallel Microservice Orchestration
Decompose a high-level task into independent microservices using LLM reasoning, develop each service in **parallel** with separate `MGXStyleTeam` instances (bounded concurrency via `bounded_gather`), then let Mike integrate the results. Output includes `docker-compose.yml`, `nginx/nginx.conf`, `service-contracts.md`, and `README.md`. Trigger via `POST /api/mgx/parallel`; poll status at `GET /api/mgx/parallel/{task_id}`.

```http
POST /api/mgx/parallel
{
  "task": "Build a SaaS platform with auth, billing, and dashboard",
  "max_concurrent": 3
}

# Response:
{ "task_id": "abc123", "status": "pending", "message": "Task submitted." }

GET /api/mgx/parallel/abc123
# Returns services[], integration_files{}, stats{total, succeeded, failed}
```

### ✅ Semantic Response Cache
Lightweight proxy embedding (MD5 token-frequency + cosine similarity) for deduplicating near-identical LLM prompts without external model dependencies. Enabled by default (`MGX_ENABLE_SEMANTIC_CACHE=0` to disable). Configurable similarity threshold via `TeamConfig.semantic_cache_similarity_threshold` (default 0.85).

### ✅ Extended Project Generator Stacks
Beyond classic web templates, the backend generator supports **`react_native`**, **`flutter`**, and **`go_fiber`** (`StackType`, manifests under `backend/services/generator/templates/`, aligned with `mgx_agent/stack_specs.py` for the agent layer).

### ✅ DeepSite Frontend & Jest
Next.js App Router UI under **`/deepsite`** with component tests (`frontend/jest.config.ts`, `jest.setup.ts`, `frontend/__tests__/components/deepsite-v2/`).

### ✅ Charlie Sandbox (Real Container Tests)
Before LLM code review, **`RunSandboxTests`** can execute the generated file manifest inside **`SandboxRunner.execute_project`** (multi-file project, public base images, optional image pull). Wired in **`mgx_agent/roles.py`** (Charlie) and integrated into **`ReviewCode`** prompts. Disable with **`DISABLE_SANDBOX_TESTING=true`**.

### ✅ Alex Sandbox Self-Heal (WriteCode)
When **`SANDBOX_SELF_HEAL_MAX_ATTEMPTS`** is greater than zero (default **2**), **`WriteCode`** runs the same **`execute_project`** path plus quality gates via **`run_sandbox_project_result` / `RunSandboxTests.run_detailed`**. On failure, stderr/stdout are fed back into the generation prompt for a limited number of retries. Set **`SANDBOX_SELF_HEAL_MAX_ATTEMPTS=0`** to keep only the legacy single-pass **`_execute_sandbox_testing`** behavior.

---

## Quick Start

### Docker Compose (5 minutes)

Recommended for production and local development.

```bash
git clone https://github.com/mockupsoft/mgx-ai.git
cd mgx-ai
cp .env.example .env

# Edit .env and update secrets for production
# See DOCKER_DEPLOYMENT.md for secure secret generation

docker compose up -d --build

# Health check
curl http://localhost:8000/health/

# View API documentation
# Open http://localhost:8000/docs in browser
```

**Optional:** Add Kafka profile for advanced event streaming:
```bash
docker compose --profile kafka up -d --build
```

Full deployment guide: **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**

### Local Development (10 minutes)

For direct Python execution and development:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt

# Run database migrations (requires PostgreSQL)
alembic -c backend/alembic.ini upgrade head

# Start the API server
uvicorn backend.app.main:app --reload --port 8000
```

### First Task Example

Run the agent using Python:
```bash
python -m mgx_agent.cli --task "Create a FastAPI /health endpoint and add tests"
```

Or use the installed CLI:
```bash
mgx task "Add request ID logging middleware to the FastAPI backend"
```

Expected output:
- Plan generation with optional approval step
- Phased execution with progress events
- Stack-specific validation and formatting
- Optional git commit/PR creation

---

## Architecture

### Core Services

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Interface                         │
│              (CLI, REST API, WebSocket)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  FastAPI Backend Layer                      │
│  (Middleware, Validation, Event Broadcasting, API Routers)  │
└──────────┬────────────────────┬──────────────┬──────────────┘
           │                    │              │
┌──────────▼──────┐  ┌──────────▼──────┐  ┌───▼────────┐
│ Agent Engine    │  │ Workflow        │  │ Git        │
│ (Multi-Agent    │  │ Orchestrator    │  │ Manager    │
│  Coordination)  │  │ (DAG Resolver)  │  │            │
└──────────┬──────┘  └──────────┬──────┘  └────┬───────┘
           │                    │              │
┌──────────▼────────────────────▼──────────────▼──────────────┐
│                   Storage Layer                             │
│  PostgreSQL (Metadata)  Redis (Cache/Queue)  MinIO (Files) │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Task Submission**: CLI/API receives task description and stack context
2. **Agent Orchestration**: Multi-agent team analyzes, plans, and executes
3. **Workflow Execution**: DAG resolver coordinates parallel/sequential steps
4. **Code Generation**: Stack-aware code generation with guardrails
5. **Validation**: Output validation, formatting, and safety checks
6. **Git Operations**: Optional branch/commit/PR automation
7. **Artifact Storage**: Generated files stored in MinIO with metadata
8. **Event Streaming**: Real-time WebSocket events for monitoring

### Technology Stack

- **Runtime**: Python 3.11+, MetaGPT framework (see also project rules / Docker images)
- **Backend**: FastAPI, Async SQLAlchemy, Alembic migrations
- **Database**: PostgreSQL 16+ (metadata, workflows, tasks)
- **Cache/Queue**: Redis 7+ (LLM caching, background jobs)
- **Storage**: MinIO/S3-compatible (artifacts, generated files)
- **Message Queue**: Apache Kafka (optional, for events)
- **Observability**: OpenTelemetry, structured logging
- **Testing**: pytest, pytest-asyncio, coverage.py
- **Deployment**: Docker Compose, GitHub Actions CI/CD

Full architecture details: **[BACKEND_README.md](./BACKEND_README.md)**

---

## Project Structure

```
mgx-ai/
├── mgx_agent/                 # Core agent runtime
│   ├── actions.py            # Code generation, ReviewCode, RunSandboxTests, …
│   ├── roles.py              # Agent role definitions (Charlie runs sandbox before review)
│   ├── team.py               # Multi-agent orchestration
│   ├── stack_specs.py        # STACK_SPECS + infer_stack_from_task
│   ├── config.py             # Configuration management
│   ├── cache.py              # LLM caching layer (InMemoryLRU, Redis, SemanticCache)
│   ├── guardrails.py         # Output validation
│   ├── diff_writer.py        # Safe patch application
│   ├── formatters.py         # Stack-aware formatting
│   ├── cli.py                # CLI interface
│   └── microservice/         # Parallel microservice orchestration
│       ├── models.py         # ServiceSpec, ServiceResult, ParallelRunResult
│       ├── decomposer.py     # DecomposeTask (LLM → List[ServiceSpec])
│       ├── integrator.py     # IntegrateServices (LLM → docker-compose + nginx + README)
│       └── orchestrator.py   # ParallelOrchestrator (bounded_gather coordination)
├── backend/                   # FastAPI backend service
│   ├── app/                  # FastAPI application
│   ├── routers/              # API route handlers (mgx: history, pipeline; parallel: /api/mgx/parallel)
│   ├── services/             # Business logic (mgx_history, mgx_pipeline, parallel_pipeline, sandbox, generator, …)
│   ├── db/                   # Database models & migrations (e.g. mgx_runs)
│   ├── schemas.py            # Pydantic schemas
│   └── config.py             # Backend configuration
├── frontend/                  # Next.js (MGX dashboard, DeepSite)
├── tests/                     # Comprehensive test suite
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   ├── e2e/                  # End-to-end tests
│   └── cli/                  # CLI-specific tests
├── docs/                      # Documentation
├── deployment/                # Deployment configurations
├── examples/                  # Usage examples
├── .github/workflows/         # CI/CD pipelines
└── docker-compose.yml        # Docker Compose stack
```

---

## Key Features Details

### Multi-Agent Controller
The agent orchestration engine coordinates a team of specialized AI agents (planner, implementer, reviewer) with stack-aware task assignment. Features task complexity assessment (XS/S/M/L/XL), dynamic role allocation, progress tracking, and real-time WebSocket event streaming. Integrates with the workflow engine for complex multi-step pipelines.

**Key capabilities:**
- Team orchestration with MetaGPT foundation
- Stack inference and constraint application
- Task complexity assessment and assignment
- Progress tracking with phase-based execution
- Real-time event streaming via WebSocket
- Integration with caching layer for performance

### Workflow Engine
Production-grade DAG-based workflow orchestration supporting sequential, parallel, and conditional execution. Features dependency resolution, retry logic, timeouts, multi-agent step assignment, and comprehensive telemetry. Ideal for CI/CD pipelines, code generation workflows, and complex automation tasks.

**Core features:**
- Workflow CRUD with JSON-based definitions
- Dependency resolver for parallel execution groups
- Conditional steps with boolean expressions
- Retry policies and timeout handling
- Multi-agent orchestration per step
- Execution timeline and metrics tracking
- WebSocket streaming for real-time monitoring

### Git Integration
Deep GitHub integration for repository-scoped execution. Automates branch creation, commit generation, and PR creation with proper linking to MGX tasks. Tracks all git metadata (branch, commit SHA, PR URL) per execution and provides webhooks for repository events.

**Integration features:**
- GitHub PAT and OAuth authentication
- Repository discovery and linking
- Automated branch naming: `mgx/{task_slug}/run-{n}`
- Commit templating and message generation
- Optional push and PR creation
- Git metadata tracking per task run
- Webhook support for repository events

### Artifact Pipeline
Complete artifact management system with MinIO/S3-compatible storage, versioning, metadata tracking, and secure access controls. Handles generated code files, test reports, logs, and workflow outputs with lifecycle management and retention policies.

**Pipeline features:**
- Multi-backend storage (MinIO/S3/GCS)
- Versioned artifacts with metadata
- Secure access controls and presigned URLs
- Lifecycle management and retention
- Integration with workflow execution
- Search and discovery capabilities
- Compression and deduplication

### Template Library
Extensible template system for stack-specific code generation with versioned templates, dynamic parameter injection, and inheritance support. Includes built-in templates for all 8 supported web stacks and allows custom template creation.

**Template features:**
- Stack-specific prompt templates
- Version control and inheritance
- Dynamic parameter injection
- Multi-language support (Python/JS/PHP)
- Template validation and testing
- Integration with workflow engine
- Community template sharing

### Observability & Monitoring
Enterprise-grade observability with OpenTelemetry tracing, structured JSON logging, metrics collection, and performance profiling. Provides complete visibility into multi-agent execution, workflow performance, and system health.

**Observability features:**
- OpenTelemetry tracing with span hierarchy
- Structured JSON logging with correlation IDs
- Performance metrics and profiling
- WebSocket event streaming for real-time monitoring
- Health checks and readiness probes
- Error tracking and alerting
- Cost analysis and optimization insights

---

## Testing & Quality

### Test Structure

```
tests/
├── unit/              # 60+ unit tests (module-level)
├── integration/       # 50+ integration tests (service-level)
├── e2e/              # 20+ end-to-end tests (full system)
├── cli/              # CLI-specific tests
└── conftest.py       # pytest configuration
```

### Coverage Requirements

- **Minimum test count:** 130+ automated tests
- **Coverage gate:** 80%+ for `mgx_agent/` modules
- **Current status:** 310 tests, 89% passing, 71% coverage
- **CI enforcement:** Fail on threshold violations

### Running Tests

```bash
# All tests
pytest

# Specific test categories
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# With coverage report
pytest --cov=mgx_agent --cov-report=html --cov-report=term

# Performance tests
pytest tests/performance

# Verbose mode with timing
pytest -v --durations=10
```

### Frontend (DeepSite) — Jest

From `frontend/`:

```bash
npm test
# or scoped:
npx jest __tests__/components/deepsite-v2/editor/
```

Uses `jest-environment-jsdom` and polyfills in `jest.setup.ts` for stream/fetch-related tests.

### CI/CD Pipeline

GitHub Actions workflow with multiple jobs:
- **Unit Tests:** Fast feedback on core functionality
- **Integration Tests:** Service-level validation
- **E2E Tests:** Full system scenario testing
- **Coverage Report:** Enforces 80%+ coverage gate
- **Security Scan:** Dependency vulnerability scanning
- **Performance Benchmark:** Runtime regression detection

Full testing guide: **[docs/TESTING.md](./docs/TESTING.md)**

---

## Deployment

### Quick Reference

See **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)** for complete deployment guide.

### Environment Variables

Key configuration variables (see `.env.example` for full list):
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/mgx

# Redis
REDIS_URL=redis://localhost:6379

# MinIO/S3
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx

# LLM Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

### Production Checklist

- [ ] Generate secure secrets using OpenSSL
- [ ] Configure PostgreSQL with persistent volume
- [ ] Set up Redis persistence and backups
- [ ] Configure MinIO credentials and bucket policies
- [ ] Enable HTTPS/TLS termination
- [ ] Set up log aggregation and monitoring
- [ ] Configure resource limits and autoscaling
- [ ] Implement backup and disaster recovery
- [ ] Set up alerting and incident response
- [ ] Configure cost monitoring and optimization

Full production guide: **[docs/PRODUCTION_DEPLOYMENT.md](./docs/PRODUCTION_DEPLOYMENT.md)**

---

## Contributing & Development

### Setup for Contributors

```bash
# Clone repository
git clone https://github.com/mockupsoft/mgx-ai.git
cd mgx-ai

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Setup database (requires PostgreSQL)
alembic -c backend/alembic.ini upgrade head

# Run tests to verify setup
pytest tests/unit -v
```

### Branch Naming

```
feature/description       # New features
fix/description         # Bug fixes
docs/description        # Documentation updates
refactor/description    # Code refactoring
test/description       # Test additions
hotfix/description     # Critical production fixes
```

### PR Process

1. **Create feature branch** from `main`
2. **Implement changes** with tests
3. **Run test suite** locally: `pytest`
4. **Check coverage**: `pytest --cov=mgx_agent`
5. **Update docs** if needed
6. **Create PR** with description:
   - What changed and why
   - Test coverage impact
   - Breaking changes (if any)
   - Related issues/PRs
7. **CI validation** must pass
8. **Code review** by maintainers
9. **Merge to main** after approval

### Development Guidelines

- Follow existing code style and patterns
- Add tests for new functionality
- Maintain 80%+ coverage threshold
- Update documentation for user-facing changes
- Use type hints consistently
- Follow async/await patterns for I/O operations
- Use structured logging with correlation IDs

Full contributing guide: **[CONTRIBUTING.md](./CONTRIBUTING.md)**

---

## Recent Updates

### 2026 — Platform additions (this repository)

- **MGX persistence**: `mgx_runs` table + **`/api/mgx/history`** (list/detail/delete).
- **Multi-task pipeline**: **`/api/mgx/pipeline`** — sequential tasks via `mgx_pipeline` + `BackgroundTaskRunner` (in-memory pipeline registry).
- **Generator stacks**: **`react_native`**, **`flutter`**, **`go_fiber`** templates and `StackType` / `stack_specs` alignment.
- **DeepSite Jest**: Editor/Ask-AI component test skeletons under `frontend/__tests__/components/deepsite-v2/`.
- **Alembic**: New migrations require a one-time `alembic upgrade head` per environment when schema changes (not on every app restart).
- **Charlie + DinD**: `RunSandboxTests` + `SandboxRunner.execute_project`; Compose **`dind`** service and dev **`DOCKER_HOST=tcp://dind:2375`** for isolated Docker runs inside the stack.
- **Alex sandbox self-heal**: `WriteCode` + **`SANDBOX_SELF_HEAL_MAX_ATTEMPTS`** — retries generation with sandbox/quality-gate feedback (`run_sandbox_project_result`).
- **Semantic cache**: `SemanticCache` in `mgx_agent/cache.py` — proxy embedding (hash-based) + cosine similarity, enabled by default; `MGX_ENABLE_SEMANTIC_CACHE=0` to disable.
- **Parallel microservice orchestration**: `mgx_agent/microservice/` — LLM-driven task decomposition → concurrent `MGXStyleTeam` instances per service → integration output (docker-compose, nginx, README). API: `POST /api/mgx/parallel`.

Cursor rule files under **`.cursor/rules/`** summarize APIs and Docker/sandbox behavior (e.g. `mgx-api.mdc`, `docker-run.mdc`, `project-overview.mdc`).

### Completed Phases: 1-11+

**Production-Ready Milestones:**
- ✅ Agent Foundation & Multi-Agent Orchestration
- ✅ FastAPI Backend with Real-time Events
- ✅ Git Integration & Repository Linking
- ✅ Multi-Tenant Workspaces & Projects
- ✅ Web Stack Support (8 frameworks)
- ✅ Output Validation & Safe Patch Writer
- ✅ Code Formatting & Pre-commit Hooks
- ✅ CLI Distribution (PyPI + npm)
- ✅ Workflow Engine & Orchestration
- ✅ Sandboxed Code Runner (Phase 11)
- ✅ **Intelligent Chat Interface** - Simple question detection & direct LLM responses
- ✅ **Plan Approval System** - Human-in-the-loop approval with auto-approval for simple tasks
- ✅ **Multi-LLM Provider Support** - OpenRouter, Gemini, Ollama, OpenAI, Anthropic, Mistral, Together
- ✅ **Real-time WebSocket Updates** - Live chat messages, plan updates, execution progress
- ✅ **Enhanced Response Quality** - Natural, conversational AI responses with temperature control

### Recent Merged PRs

- **Feature/LLM-cache-layer** - Intelligent response caching with Redis support
- **Phase-4-test-report-validation** - Enhanced test validation and reporting
- **Feature-expose-api-events** - REST API for event streaming and management  
- **Feat/workspaces-projects-multi-tenancy** - Production multi-tenant isolation
- **Feat/github-repo-links** - GitHub repository linking automation
- **Feat/mgx-cli-py-npm** - Dual CLI distribution (Python + NPM)
- **Phase-9-multi-agent-production-validation** - Production validation framework
- **Feat/workflow-engine-multi-agent** - Multi-agent workflow orchestration
- **Docs-phase-10-workflow-update** - Comprehensive workflow documentation
- **Feat/project-generator-scaffold** - Project scaffolding and templates
- **Feat/phase-16-artifact-release-pipeline** - Artifact management and release
- **Feat/phase-19-template-prompt-library** - Template library system
- **Phase-25-observability-otel-logging** - OpenTelemetry integration

### System Metrics

```
┌─────────────────────────────────────────────────────────────┐
│ Overall completion score:        9.8/10 → Production-Ready  │
│ Production readiness:            Production-Ready           │
│ Test suite:                      130+ automated tests       │
│                                  80%+ coverage gate enforced│
│ Backend API:                     FastAPI + async DB + WS    │
│ Git-aware execution:             Branch/commit/PR automation│
│ Self-hosted deployment:          Docker Compose ready       │
└─────────────────────────────────────────────────────────────┘
```

---

## License & Credits

Copyright (c) 2024 MGX AI Contributors.

Licensed under the MIT License - see [LICENSE](./LICENSE) file for details.

Built on [MetaGPT](https://github.com/geekan/MetaGPT) - Multi-Agent Meta Programming Framework.

---

## Additional Resources

### Documentation

- **[docs/API.md](./docs/API.md)** - Complete REST API reference
- **[docs/WORKFLOWS.md](./docs/WORKFLOWS.md)** - Workflow engine guide
- **[docs/WEB_STACK_SUPPORT.md](./docs/WEB_STACK_SUPPORT.md)** - Stack-specific features
- **[docs/GIT_AWARE_EXECUTION.md](./docs/GIT_AWARE_EXECUTION.md)** - Git integration
- **[docs/CLI.md](./docs/CLI.md)** - Command-line interface
- **[docs/TESTING.md](./docs/TESTING.md)** - Testing framework

### Examples

- **[examples/workflows/](./examples/workflows/)** - Workflow examples
- **[examples/tasks/](./examples/tasks/)** - Task examples by stack
- **[examples/cli/](./examples/cli/)** - CLI usage examples

### API Reference

- **Health:** `GET /health/`
- **MGX history:** `GET /api/mgx/history`, `GET /api/mgx/history/{run_id}`, `DELETE /api/mgx/history/{run_id}`
- **MGX pipeline:** `POST /api/mgx/pipeline`, `GET /api/mgx/pipeline`, `GET /api/mgx/pipeline/{pipeline_id}`
- **MGX parallel:** `POST /api/mgx/parallel` (decompose → parallel teams → integrate), `GET /api/mgx/parallel/{task_id}`
- **Workspaces:** `GET/POST /api/workspaces/`
- **Projects:** `GET/POST /api/projects/`
- **Tasks:** `GET/POST /api/tasks/`
- **Runs:** `GET/POST /api/runs/`
- **Workflows:** `GET/POST /api/workflows/`
- **Repositories:** `GET/POST /api/repositories/`

Complete API documentation available at: `http://localhost:8000/docs`

---

**Status:** Production-Ready 🚀 | **Latest Release:** v1.0.0 | **Last Updated:** April 2026