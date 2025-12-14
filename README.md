# MGX AI (MGX Agent)

AI-powered, multi-agent software engineering system built on **MetaGPT**.

MGX pairs a production-ready **FastAPI backend** (PostgreSQL + WebSocket events + background execution) with an opinionated **agent runtime** (`mgx_agent/`) that simulates a small AI engineering team: analyze → plan → approve → implement → test → review → validate → format → (optionally) open a PR.

## Executive summary & badges

### Badge board

> Note: Some badges require the repository to be hosted at `mockupsoft/mgx-ai`.

| Category | Badge |
|---|---|
| Status | ![status](https://img.shields.io/badge/status-production--ready-brightgreen) |
| CI (tests) | ![Test Suite](https://github.com/mockupsoft/mgx-ai/actions/workflows/tests.yml/badge.svg) |
| Coverage | ![codecov](https://codecov.io/gh/mockupsoft/mgx-ai/branch/main/graph/badge.svg) |
| License | ![license](https://img.shields.io/github/license/mockupsoft/mgx-ai) |
| Python | ![python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue) |
| Backend | ![fastapi](https://img.shields.io/badge/FastAPI-async-009688) |
| CLI (PyPI) | ![pypi](https://img.shields.io/pypi/v/mgx-cli) |
| CLI (npm) | ![npm](https://img.shields.io/npm/v/@mgxai/cli) |

### Production readiness snapshot

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Overall completion score:   9.8/10                                           │
│ Production readiness:        98%                                             │
│ Test suite:                  130+ automated tests (80%+ coverage gate)       │
│ Backend API:                 FastAPI + async DB + WebSockets + migrations    │
│ Git-aware execution:         branch/commit/PR automation                     │
│ Self-hosted deployment:      Docker Compose (Postgres/Redis/MinIO, Kafka opt)│
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Table of contents

- [What is MGX?](#what-is-mgx)
- [Quick start guide](#quick-start-guide)
  - [Docker Compose (5 minutes)](#docker-compose-5-minutes)
  - [Local development (10 minutes)](#local-development-10-minutes)
  - [First task example (copy-paste)](#first-task-example-copy-paste)
- [Project status & roadmap](#project-status--roadmap)
  - [Phase 1: Code review & quick fixes](#phase-1-code-review--quick-fixes)
  - [Phase 2: Modularization](#phase-2-modularization)
  - [Phase 3: Test coverage & infrastructure](#phase-3-test-coverage--infrastructure)
  - [Phase 4: Performance optimization](#phase-4-performance-optimization)
  - [Phase 45: Backend API & real-time events](#phase-45-backend-api--real-time-events)
  - [Phase 5: Git integration](#phase-5-git-integration)
  - [Phase 6: Multi-tenant workspaces & projects](#phase-6-multi-tenant-workspaces--projects)
  - [Phase 7: Web stack support (8 stacks)](#phase-7-web-stack-support-8-stacks)
  - [Phase 81: Output validation guardrails](#phase-81-output-validation-guardrails)
  - [Phase 82: Safe patchdiff writer](#phase-82-safe-patchdiff-writer)
  - [Phase 83: Code formatting & pre-commit](#phase-83-code-formatting--pre-commit)
  - [Phase 8: Global expansion](#phase-8-global-expansion)
- [Architecture & design](#architecture--design)
  - [Overall architecture diagram](#overall-architecture-diagram)
  - [Module dependencies](#module-dependencies)
  - [Data flow](#data-flow)
- [Installation & setup](#installation--setup)
  - [Requirements](#requirements)
  - [Option 1: Docker Compose (recommended)](#option-1-docker-compose-recommended)
  - [Option 2: Local development](#option-2-local-development)
  - [Environment variables](#environment-variables)
- [Usage examples](#usage-examples)
  - [CLI example: generate a FastAPI feature](#cli-example-generate-a-fastapi-feature)
  - [CLI example: patch an existing repository](#cli-example-patch-an-existing-repository)
  - [REST API example: create and run a task](#rest-api-example-create-and-run-a-task)
  - [WebSocket example: subscribe to task events](#websocket-example-subscribe-to-task-events)
- [API reference](#api-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Performance benchmarks](#performance-benchmarks)
- [Deployment guide](#deployment-guide)
- [Contributing](#contributing)
- [License & credits](#license--credits)
- [Links & resources](#links--resources)
- [Appendices (embedded full docs)](#appendices-embedded-full-docs)

---

## What is MGX?

MGX is a **multi-agent AI engineering runtime** designed to take a task description (via CLI or API) and run a repeatable, production-oriented software workflow: analysis, planning, implementation, testing, review, validation, formatting, and (optionally) Git operations.

Where a single LLM prompt often produces incomplete or inconsistent output, MGX focuses on **systems**: deterministic constraints, validations, safe patch application, and event streaming so humans can monitor progress and intervene when needed.

MGX is built on the **MetaGPT** foundation and extends it with a practical "AI engineering team simulation". The team includes role-like behaviors (planner, implementer, reviewer) and a set of actions (analyze, draft plan, write code, write tests, review) that can be orchestrated end-to-end.

MGX is intentionally stack-aware: it can infer a target web stack (FastAPI, Express-TS, NestJS, Laravel, Next.js, React+Vite, Vue+Vite, and a DevOps-focused stack for Docker/GitHub Actions), apply stack-specific constraints, and format output using that ecosystem’s standard tooling.

### Core capabilities

- **Agent runtime** (Python): team orchestration, stack inference, guardrails, patch/diff writer, formatters, caching, profiling
- **Backend API** (FastAPI): multi-tenant DB schema, task/run persistence, WebSocket events, background execution
- **Git integration**: repository linking and git-aware execution (branch/commit/PR automation)
- **Self-hosting**: Docker Compose with Postgres + Redis + MinIO (S3-compatible), optional Kafka

---

## Quick start guide

### Docker Compose (5 minutes)

This is the recommended path to run MGX locally or self-host it.

```bash
cd mgx-ai
cp .env.example .env

# Edit .env and change secrets for production

docker compose up -d --build

# Optional Kafka profile:
# docker compose --profile kafka up -d --build

# Health check
curl http://localhost:8000/health/

# OpenAPI (Swagger)
# http://localhost:8000/docs
```

Full guide: **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**.

### Local development (10 minutes)

If you prefer running the API directly:

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt

# Run DB migrations (requires a Postgres instance)
alembic -c backend/alembic.ini upgrade head

uvicorn backend.app.main:app --reload --port 8000
```

### First task example (copy-paste)

Run the agent from Python:

```bash
python -m mgx_agent.cli --task "Create a FastAPI /health endpoint and add tests"
```

Or use the `mgx` CLI package (if installed):

```bash
mgx task "Add request ID logging middleware to the FastAPI backend"
```

Expected output (typical):

- A plan is produced and (depending on configuration) may require approval
- Execution proceeds in phases and emits progress events
- Outputs are validated for stack constraints
- Files are formatted (best-effort) and optionally committed / pushed

---

## Project status & roadmap

MGX is organized into explicit implementation phases. Phases 1–8.3 are complete and stable; the roadmap section lists potential Phase 9+ work.

### Phase 1: Code review & quick fixes

Phase 1 established a reliable baseline by hardening inputs, standardizing configuration, and tightening error handling.

Eight targeted improvements:

1. **Constants centralization**: reduced magic strings and duplicated defaults.
2. **DRY principle application**: extracted repeated logic into shared helpers.
3. **Input validation strengthening**: early, explicit checks with actionable errors.
4. **Error message improvements**: clearer failures for users and for automated retries.
5. **Type hints enhancement**: improved static readability and testability.
6. **Documentation updates**: aligned docs with runtime behavior and CLI/API flags.
7. **Performance micro-optimizations**: low-risk improvements for hot paths.
8. **Security audit fixes**: reduced risky defaults and clarified secret handling.

Quality gates introduced/standardized:

- CI test gate: **130+ tests** minimum
- CI coverage gate: **80%+** for `mgx_agent`

### Phase 2: Modularization

Phase 2 moved the agent runtime toward clear module ownership. The repo currently contains multiple focused modules, while preserving backward-compatible entry points.

Reference module layout:

```text
mgx_agent/
├── config.py              # Configuration & constants
├── metrics.py             # Score calculations
├── actions.py             # Action execution
├── adapter.py             # MetaGPT adapter
├── roles.py               # Role definitions
├── team.py                # Team orchestration
└── cli.py                 # CLI interface
```

Patterns used:

- **Factory pattern**: centralized action creation and defaults
- **Strategy pattern**: pluggable scoring/budget behaviors
- **Observer pattern**: callbacks/event hooks for metrics + WebSocket streaming
- **Dependency injection**: easier unit and integration testing

Backward compatibility checklist:

- `python -m mgx_agent.cli ...` remains supported
- public objects are re-exported where needed to reduce breaking imports

### Phase 3: Test coverage & infrastructure

Phase 3 added a structured, multi-level test suite and CI wiring.

- **130+ automated tests** total (unit + integration + e2e)
- pytest + pytest-asyncio
- Coverage reports: terminal + HTML + XML
- CI workflow enforces minimum test count and coverage thresholds

Reference breakdown (targets / reported in CI):

- Unit tests: 60+
- Integration tests: 50+
- E2E tests: 20+

Module coverage targets (typical):

- `config.py`: 99%
- `metrics.py`: 99%
- `adapter.py`: 85%+
- `actions.py`: 85%+
- `roles.py`: 85%+
- `team.py`: 85%+
- `cli.py`: 75%+

See: **[docs/TESTING.md](docs/TESTING.md)**.

### Phase 4: Performance optimization

Phase 4 focused on measurable runtime speedups and on making performance regressions visible.

Async pipeline tuning:

- Sequential execution moved toward **concurrent orchestration** where safe
- Parallel phases via `asyncio.gather()`
- Timeout handling via `asyncio.wait_for()`
- Task timing infrastructure (per phase)

Caching layer:

- In-memory LRU cache + TTL
- Optional Redis backend
- Typical cache hit rates: 65–75% on iterative workflows

Example configuration:

```python
from mgx_agent.config import TeamConfig

TeamConfig(
    enable_caching=True,
    cache_backend="memory",  # or "redis"
    cache_max_entries=1024,
    cache_ttl_seconds=3600,
)
```

Profiling + reporting:

- Per-phase timing snapshots
- Optional memory tracking (tracemalloc)
- Reports written to `perf_reports/` (and uploaded as CI artifacts)

See: **[docs/PERFORMANCE.md](docs/PERFORMANCE.md)**.

### Phase 45: Backend API & real-time events

Phase 4.5 delivered a production-oriented backend for running MGX as a service.

- FastAPI REST API
- Async SQLAlchemy models + Alembic migrations
- Workspace/project/task/run persistence
- Real-time WebSocket event streaming
- Background executor + event broadcaster

Endpoint groups (high-level):

- Health: `/health/*`
- Workspaces/projects: `/api/workspaces`, `/api/projects`
- Tasks/runs: `/api/tasks`, `/api/runs`
- Metrics: `/api/metrics/*`
- Repositories (linking): `/api/repositories/*`

Event types include:

- `task:*` lifecycle events (analysis, plan_ready, execution_started, phase_update, completed, failed)
- `git_*` lifecycle events (branch_created, commit_created, push_success, pull_request_opened, etc.)

See: **[docs/API.md](docs/API.md)** and **[docs/API_EVENTS_DOCUMENTATION.md](docs/API_EVENTS_DOCUMENTATION.md)**.

### Phase 5: Git integration

Phase 5 made executions git-aware and repository-scoped.

- GitHub integration (PAT or OAuth-style credentials depending on deployment)
- Repository discovery and linking per project
- Automated branch creation (example pattern: `mgx/{task_slug}/run-{n}`)
- Commit template support
- Optional push and PR creation

Git metadata tracked per run:

- `branch_name`
- `commit_sha`
- `pr_url`
- `git_status`

See: **[docs/GIT_AWARE_EXECUTION.md](docs/GIT_AWARE_EXECUTION.md)** and **[docs/GITHUB_REPOSITORY_LINKING.md](docs/GITHUB_REPOSITORY_LINKING.md)**.

### Phase 6: Multi-tenant workspaces & projects

Phase 6 introduced explicit tenant boundaries and multi-project organization.

- Workspace model: company/team isolation boundary
- Project model: per-workspace repositories and settings
- Query scoping foundations to avoid cross-tenant leakage
- RBAC-ready shape (auth itself is a Phase 9+ item)

See: **[docs/MULTI_TENANT.md](docs/MULTI_TENANT.md)**.

### Phase 7: Web stack support (8 stacks)

Phase 7 made the agent stack-aware end-to-end.

- StackSpec registry (stack inference + constraints)
- Stack-aware prompting: analysis, planning, codegen, testing
- Framework-appropriate tests/linters/formatters

Stacks supported:

- Backend: Express-TS, NestJS, Laravel, FastAPI
- Frontend: React + Vite, Next.js, Vue + Vite
- DevOps: Docker, GitHub Actions CI

Strict output format:

- A FILE-manifest-style output is enforced so generated changes can be parsed, validated, formatted, and applied safely.

See: **[docs/WEB_STACK_SUPPORT.md](docs/WEB_STACK_SUPPORT.md)**.

### Phase 81: Output validation guardrails

Phase 8.1 introduced deterministic validation of generated outputs.

- Stack-specific required file checks
- Forbidden library detection
- Stack mismatch prevention
- Strict FILE manifest compliance
- Bounded auto-revision loop (max retries)

See: **[docs/OUTPUT_VALIDATION.md](docs/OUTPUT_VALIDATION.md)**.

### Phase 82: Safe patch/diff writer

Phase 8.2 introduced a safe patch application layer.

- Unified diff parser (single or multiple hunks)
- Backup before apply
- Rollback on failure
- Line-drift tolerance
- Multi-file patch transaction semantics

See: **[docs/PATCH_MODE.md](docs/PATCH_MODE.md)** and **[docs/DIFF_FORMAT.md](docs/DIFF_FORMAT.md)**.

### Phase 83: Code formatting & pre-commit

Phase 8.3 introduced post-generation formatting and pre-commit templates.

- Stack-aware formatters:
  - Python: black/ruff/isort
  - Node: prettier/eslint
  - PHP: pint/phpstan
- Best-effort integration (formatting should not fail tasks)
- Template `.pre-commit-config.yaml` samples per stack

See: **[docs/CODE_FORMATTING.md](docs/CODE_FORMATTING.md)**.

### Phase 8: Global expansion

Phase 8 delivered distribution and self-hosting.

CLI distribution:

- PyPI: `pip install mgx-cli`
- npm: `npm install -g @mgxai/cli`

Self-hosting:

- Docker Compose stack (Postgres + Redis + MinIO, optional Kafka)
- Health checks, persistence, and operational guidance

See: **[docs/CLI.md](docs/CLI.md)** and **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**.

#### Roadmap (Phase 9+)

- Authentication and authorization (JWT/RBAC)
- Durable event bus (Kafka-first, replayable)
- Job queue / scheduler (retries, rate limits)
- Observability (OpenTelemetry)
- Horizontal scaling and HA playbook
- Kubernetes deployment option (Helm)

---

## Architecture & design

### Overall architecture diagram

```text
┌─────────────────────────────────────────────────────────────────────┐
│                              MGX AI                                 │
├──────────────────┬───────────────────────┬──────────────────────────┤
│ Frontend UI      │ Backend API           │ Agent runtime             │
│ (external)       │ (FastAPI)             │ (mgx_agent)               │
│                  │                       │                          │
│ - dashboard      │ - REST API (/api/*)   │ - analyze                 │
│ - task monitor   │ - WebSockets (/ws/*)  │ - plan + approval gates   │
│ - approvals      │ - background executor │ - execute + test + review │
│ - git status     │ - events broadcaster  │ - validate + format       │
├──────────────────┴───────────────────────┴──────────────────────────┤
│ Data layer: PostgreSQL (multi-tenant) + optional Redis cache         │
├─────────────────────────────────────────────────────────────────────┤
│ Git integration: clone/branch/commit/push/PR                          │
├─────────────────────────────────────────────────────────────────────┤
│ Deployment: Docker Compose (Postgres + Redis + MinIO, Kafka optional) │
└─────────────────────────────────────────────────────────────────────┘
```

### Module dependencies

```text
config  ─┬─> metrics
         ├─> actions
         ├─> roles
         ├─> team
         └─> cli

adapter ─┬─> roles
         └─> team

actions ─┬─> adapter
         └─> roles

roles   ─┬─> actions
         └─> adapter

team    ─┬─> config, metrics, actions, roles, adapter
         └─> guardrails, diff_writer, formatters, cache

cli     ─┬─> team
         └─> config
```

### Data flow

```text
1. Task input arrives via CLI or REST API
2. Analyze phase determines intent, constraints, and stack
3. Planning phase produces a structured plan
4. Optional approval workflow gates execution
5. Execution phase writes code + tests (or patches existing code)
6. Output validation guardrails run (stack constraints + manifest format)
7. Formatting runs (best-effort, stack-aware)
8. Optional Git operations (branch, commit, push, PR)
9. Results are persisted (task/run/models/artifacts)
10. Metrics are computed and streamed over WebSocket
```

---

## Installation & setup

### Requirements

- Python **3.9+** (tested in CI on 3.9–3.12)
- Docker + Docker Compose (recommended for local/self-hosted)
- PostgreSQL **13+** (Docker Compose uses PostgreSQL 16)
- Redis **6+** (optional; in-memory cache is also supported)
- Git 2.30+ (for git-aware execution)
- Node.js **18+** (optional: npm CLI wrapper and/or external frontend development)

A separate frontend is not bundled in this repository.

### Option 1: Docker Compose (recommended)

```bash
cp .env.example .env
# Update secrets and any overrides

docker compose up -d --build
curl http://localhost:8000/health/
```

### Option 2: Local development

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt

# Migrate DB
alembic -c backend/alembic.ini upgrade head

# (Optional) seed data
python backend/scripts/seed_data.py

# Run API
uvicorn backend.app.main:app --reload --port 8000
```

### Environment variables

MGX reads configuration from environment variables and/or `.env`.

A complete template is provided in **[.env.example](./.env.example)**.

Common groups:

```bash
# Core
MGX_ENV=development
MGX_PORT=8000
MGX_LOG_LEVEL=INFO
MGX_BASE_URL=http://localhost:8000

# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=mgx
DB_USER=mgx
DB_PASSWORD=change-me

# Cache
REDIS_URL=redis://redis:6379/0

# S3 / MinIO
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET=mgx-artifacts
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=change-me

# GitHub (optional)
GITHUB_PAT=ghp_...
```

---

## Usage examples

### CLI example: generate a FastAPI feature

```bash
mgx task "Create a FastAPI CRUD API for a User model with tests"
```

Typical results:

- Plan draft appears (and may require approval, depending on settings)
- Code and tests are generated
- Output constraints are validated
- Formatting runs
- (Optional) a feature branch is created and a PR is opened

### CLI example: patch an existing repository

```bash
mgx task "Add authentication middleware to the Express server" \
  --existing-path ./auth-service \
  --mode patch_existing
```

### REST API example: create and run a task

```bash
# Create a workspace
curl -X POST http://localhost:8000/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name":"MyTeam"}'

# Create a task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add logging middleware",
    "description": "Add request-id logging and propagate it to responses"
  }'
```

### WebSocket example: subscribe to task events

```text
ws://localhost:8000/ws/tasks/{task_id}
ws://localhost:8000/ws/runs/{run_id}
ws://localhost:8000/ws/stream
```

Full contract: **[docs/WEBSOCKET.md](docs/WEBSOCKET.md)** and **[docs/API_EVENTS_DOCUMENTATION.md](docs/API_EVENTS_DOCUMENTATION.md)**.

---

## API reference

The canonical, complete API + event contract (endpoints, schemas, examples) is maintained here:

- **[docs/API_EVENTS_DOCUMENTATION.md](docs/API_EVENTS_DOCUMENTATION.md)**

When running locally:

- Swagger UI: `GET /docs`
- OpenAPI JSON: `GET /openapi.json`

---

## Testing

```bash
pytest

# Unit tests only
pytest tests/unit

# Integration tests only
pytest tests/integration

# End-to-end tests
pytest tests/e2e

# Coverage (HTML)
pytest --cov=mgx_agent --cov-report=html
```

See **[docs/TESTING.md](docs/TESTING.md)**.

---

## Troubleshooting

Common issues:

- API not responding:
  - verify `DATABASE_URL` / DB credentials
  - ensure Alembic migrations ran
  - check container health: `docker compose ps`
- Git operations failing:
  - verify `GITHUB_PAT` or GitHub App credentials
  - ensure repo is linked to a project (repository linking endpoints)
- High memory usage:
  - reduce cache size / TTL
  - enable profiling and inspect reports

Debug settings:

```bash
# Backend (FastAPI) log level
export MGX_LOG_LEVEL=DEBUG

# Agent runtime profiling (CLI)
python -m mgx_agent.cli --profile --task "Run a small task with profiling enabled"
# For memory profiling (tracemalloc):
# python -m mgx_agent.cli --profile-memory --task "..."
```

---

## Performance benchmarks

MGX performance is stack- and model-dependent. Typical task timings for a medium feature request:

- Analysis: 15–20s
- Planning: 10–15s
- Execution: 20–30s
- Total: 45–65s (with concurrency enabled where applicable)

Cache hit rates often fall in the 65–75% range on iterative workflows, yielding significant speedups.

See **[docs/PERFORMANCE.md](docs/PERFORMANCE.md)**.

---

## Deployment guide

For a production-oriented, self-hosted setup (Postgres + Redis + MinIO + optional Kafka), use Docker Compose.

High-level checklist:

- Generate strong secrets (`JWT_SECRET`, `API_KEY`, DB password, S3 keys)
- Put MGX behind TLS (nginx/caddy)
- Restrict exposed ports (firewall)
- Enable backups (Postgres volumes + object store)
- Monitor resource usage and logs

Full guide: **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**.

---

## Contributing

- Follow existing code style and patterns.
- Run `pytest` before opening a PR.
- Use stack-aware formatting guidelines:
  - Python: black / ruff / isort
  - JS/TS: prettier / eslint
  - PHP: pint / phpstan

Pre-commit templates are provided under `docs/.pre-commit-config-*.yaml`.

---

## License & credits

- License: **MIT** (see [LICENSE](./LICENSE))
- Built on top of MetaGPT and the broader open-source ecosystem

---

## Links & resources

- Docker deployment: **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**
- API (entry point): **[docs/API.md](docs/API.md)**
- API + events (canonical): **[docs/API_EVENTS_DOCUMENTATION.md](docs/API_EVENTS_DOCUMENTATION.md)**
- WebSocket: **[docs/WEBSOCKET.md](docs/WEBSOCKET.md)**
- Database: **[docs/DATABASE.md](docs/DATABASE.md)**
- Testing: **[docs/TESTING.md](docs/TESTING.md)**
- Performance: **[docs/PERFORMANCE.md](docs/PERFORMANCE.md)**
- Web stack support: **[docs/WEB_STACK_SUPPORT.md](docs/WEB_STACK_SUPPORT.md)**
- Output validation: **[docs/OUTPUT_VALIDATION.md](docs/OUTPUT_VALIDATION.md)**
- Patch mode: **[docs/PATCH_MODE.md](docs/PATCH_MODE.md)** and **[docs/DIFF_FORMAT.md](docs/DIFF_FORMAT.md)**
- Code formatting: **[docs/CODE_FORMATTING.md](docs/CODE_FORMATTING.md)**
- Git integration: **[docs/GIT_INTEGRATION.md](docs/GIT_INTEGRATION.md)** and **[docs/GIT_AWARE_EXECUTION.md](docs/GIT_AWARE_EXECUTION.md)**
- GitHub repository linking: **[docs/GITHUB_REPOSITORY_LINKING.md](docs/GITHUB_REPOSITORY_LINKING.md)**

---

## Appendices (embedded full docs)

The following appendices embed the canonical documentation files so this README can function as a single, comprehensive guide.

> Tip: Use your editor’s symbol outline or in-page search for navigation.

## Appendix A: Docker Compose self-hosted deployment (complete production guide)

<details>
<summary>Expand Appendix A</summary>

# Docker Deployment Guide - MGX Agent Self-Hosted

Complete guide for deploying MGX Agent with Docker Compose, including PostgreSQL, Redis, MinIO (S3-compatible storage), and optional Kafka.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Architecture Overview](#architecture-overview)
4. [Initial Setup](#initial-setup)
5. [Services Overview](#services-overview)
6. [Data Persistence & Backups](#data-persistence--backups)
7. [Database Migrations](#database-migrations)
8. [Monitoring & Logs](#monitoring--logs)
9. [Troubleshooting](#troubleshooting)
10. [Security Best Practices](#security-best-practices)
11. [Performance Tuning](#performance-tuning)
12. [External Integrations](#external-integrations)
13. [Scaling & High Availability](#scaling--high-availability)

---

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/mgx-agent.git
cd mgx-agent
cp .env.example .env
```

### 2. Generate Secure Secrets (Production)

```bash
# Generate secure secrets
JWT_SECRET=$(openssl rand -hex 32)
API_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)
S3_SECRET=$(openssl rand -base64 32)

# Update .env file with generated secrets
sed -i "s/change-me-in-production-use-openssl-rand-hex-32/$JWT_SECRET/g" .env
sed -i "s/S3_SECRET_ACCESS_KEY=minioadmin/S3_SECRET_ACCESS_KEY=$S3_SECRET/g" .env
# ... manually update DB_PASSWORD and other values
```

Or manually edit `.env`:
```bash
nano .env
```

### 3. Start Services

```bash
# Build and start all services in background
docker compose up -d --build

# Wait for services to become healthy
docker compose ps

# Expected output (all healthy):
# NAME                 IMAGE               STATUS
# mgx-postgres         postgres:16-alpine  Up 2m (healthy)
# mgx-redis            redis:7-alpine      Up 2m (healthy)
# mgx-minio            minio:latest        Up 2m (healthy)
# mgx-minio-init       minio/mc:latest     Exited 0
# mgx-migrate          mgx-agent:latest    Exited 0
# mgx-ai               mgx-agent:latest    Up 1m (healthy)
```

### 4. Verify API Health

```bash
# Check API health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "timestamp": "2024-01-01T12:00:00Z"}

# View API documentation
# Open http://localhost:8000/docs in browser
```

### 5. Access MinIO Console (Optional)

```bash
# MinIO web console
# Open http://localhost:9001 in browser
# Username: minioadmin
# Password: minioadmin (from .env S3_SECRET_ACCESS_KEY)
```

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU Cores | 2 | 4+ |
| RAM | 4 GB | 8+ GB |
| Disk Space | 20 GB | 50+ GB SSD |
| Docker Version | 20.10 | 24.0+ |
| Docker Compose | v2.0 | v2.20+ |
| OS | Linux/Mac | Linux (recommended) |

### Install Docker & Docker Compose

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

**macOS:**
```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Includes Docker and Docker Compose v2
```

**Verify Installation:**
```bash
docker --version      # Docker version 20.10+
docker compose version  # Docker Compose version v2.0+
```

### Required Ports

| Port | Service | Purpose |
|------|---------|---------|
| 8000 | FastAPI | API HTTP |
| 5432 | PostgreSQL | Database |
| 6379 | Redis | Cache |
| 9000 | MinIO | S3 API |
| 9001 | MinIO | Web Console |
| 9092 | Kafka | Event Stream (optional) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network (mgx-net)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │              │    │              │    │              │       │
│  │  mgx-ai      │◄───┤  postgres    │    │  redis       │       │
│  │  (FastAPI)   │    │  (DB)        │    │  (Cache)     │       │
│  │              │    │              │    │              │       │
│  │ Port 8000    │    │ Port 5432    │    │ Port 6379    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│        ▲                                                          │
│        │                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │              │    │              │    │              │       │
│  │  minio       │    │ minio-init   │    │  mgx-migrate │       │
│  │  (S3 Compat) │◄───┤  (Bucket     │    │  (Alembic)   │       │
│  │              │    │   Init)      │    │              │       │
│  │ Port 9000/01 │    │              │    │              │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │              │    │              │ (Optional Profile)         │
│  │  kafka       │    │  zookeeper   │                           │
│  │  (Events)    │◄───┤ (Kafka Coord)│                           │
│  │              │    │              │                           │
│  │ Port 9092    │    │ Port 2181    │                           │
│  └──────────────┘    └──────────────┘                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
1. Client requests → mgx-ai (FastAPI)
2. mgx-ai queries → postgres (database)
3. mgx-ai caches → redis (cache)
4. mgx-ai stores → minio (S3 artifacts)
5. mgx-ai emits → kafka (optional events)
```

### Service Dependencies

```
minio ──┐
        ├─► minio-init (bucket creation)
postgres ──┐
           ├─► mgx-migrate (run migrations)
           │   │
           │   ├─► mgx-ai (API)
           │
redis ─────┘
```

---

## Initial Setup

### 1. Prepare Configuration

```bash
# Copy example environment
cp .env.example .env

# Edit for your deployment
# Critical settings to change:
# - JWT_SECRET (use: openssl rand -hex 32)
# - API_KEY (use: openssl rand -hex 32)
# - DB_PASSWORD (use: openssl rand -hex 16)
# - S3_ACCESS_KEY_ID & S3_SECRET_ACCESS_KEY
# - MGX_BASE_URL (change from localhost if needed)
```

### 2. Build Docker Image

```bash
# Build the MGX Agent image
docker compose build

# Force rebuild if needed
docker compose build --no-cache
```

### 3. Create .env for your environment

```bash
# Development (auto-applied if docker-compose.override.yml exists)
# Sets: MGX_ENV=development, MGX_LOG_LEVEL=DEBUG

# Production (specify explicitly)
docker compose -f docker-compose.yml up -d

# Or unset override:
MGX_ENV=production docker compose --no-project-directory up -d
```

### 4. Start Services

```bash
# Start all services in background
docker compose up -d --build

# Follow startup logs
docker compose logs -f mgx-ai

# Wait for healthy status
docker compose ps
```

---

## Services Overview

### PostgreSQL 16 (postgres)

**Purpose:** Primary relational database for all application data

**Configuration:**
- Image: `postgres:16-alpine` (lightweight)
- Port: 5432 (internal only)
- Volume: `pg_data` (persistent)
- Health Check: `pg_isready`

**Initialization:**
- Executes `init-db.sql` on first run
- Creates tables: workspaces, projects, repositories, tasks, runs, metrics, artifacts
- Idempotent (safe to re-run)

**Performance Settings:**
- `shared_buffers=256MB` (1/4 of RAM)
- `effective_cache_size=1GB`
- `max_connections=200`

**Connect directly (development):**
```bash
docker compose exec postgres psql -U mgx -d mgx
```

### Redis 7 (redis)

**Purpose:** In-memory cache and distributed session store

**Configuration:**
- Image: `redis:7-alpine` (lightweight)
- Port: 6379 (internal only)
- Volume: `redis_data` (persistent AOF)
- Health Check: `redis-cli ping`
- Persistence: AOF enabled (`--appendonly yes`)

**Features:**
- LRU eviction for automatic cache cleanup
- AOF durability for data recovery
- Performance optimized: `appendfsync everysec` (balance)

**Monitoring:**
```bash
# Check Redis stats
docker compose exec redis redis-cli info stats

# Monitor commands
docker compose exec redis redis-cli monitor

# Check memory usage
docker compose exec redis redis-cli info memory
```

### MinIO (minio)

**Purpose:** S3-compatible object storage for artifacts

**Configuration:**
- Image: `minio/latest` (latest stable)
- Ports: 9000 (API), 9001 (console)
- Volume: `minio_data` (persistent)
- Health Check: `curl minio/health/live`

**Console Access:**
- URL: http://localhost:9001
- Username: minioadmin
- Password: From `S3_SECRET_ACCESS_KEY` in `.env`

**Bucket Initialization:**
- Service: `minio-init` (runs once after minio is healthy)
- Creates bucket: `mgx-artifacts` (configurable)
- Enables versioning for data recovery
- Idempotent: Safe to re-run

### MinIO Init (minio-init)

**Purpose:** One-time bucket creation and versioning

**Execution:**
- Depends: minio service healthy
- Runs: `minio/mc` (MinIO client)
- Commands:
  1. Connect to MinIO
  2. Create bucket (ignore if exists)
  3. Enable versioning
  4. Exit (doesn't keep running)

**Inspect Results:**
```bash
# View service status (exits after completion)
docker compose ps | grep minio-init

# View logs if creation failed
docker compose logs minio-init
```

### Database Migrations (mgx-migrate)

**Purpose:** Run Alembic migrations before API starts

**Execution:**
- Depends: postgres service healthy
- Runs: `alembic upgrade head`
- Command: `bash -c "alembic upgrade head && echo 'Migrations completed'"`
- Exit: After migrations complete (doesn't keep running)

**Check Status:**
```bash
# View migration logs
docker compose logs mgx-migrate

# Expected success message:
# INFO [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO [alembic.runtime.migration] Will assume transactional DDL.
# INFO [alembic.runtime.migration] Running upgrade (initial) -> (version), (version) -> ...
```

**Manually Run Migrations:**
```bash
# If you need to re-run migrations
docker compose run --rm mgx-migrate alembic upgrade head

# Or in running container
docker compose exec mgx-ai alembic upgrade head
```

### FastAPI Application (mgx-ai)

**Purpose:** Main application server

**Configuration:**
- Image: `mgx-agent:latest` (built from ./Dockerfile)
- Port: 8000
- Workers: `MGX_WORKERS` (default: 4)
- Health Check: GET `/health` endpoint

**Startup Process:**
1. Waits for: postgres, redis, minio healthy
2. Waits for: mgx-migrate completed
3. Runs: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
4. WebSocket support via uvicorn

**API Endpoints:**
- Docs: http://localhost:8000/docs (Swagger UI)
- ReDoc: http://localhost:8000/redoc
- OpenAPI: http://localhost:8000/openapi.json
- Health: http://localhost:8000/health

**View Logs:**
```bash
# Recent logs
docker compose logs mgx-ai

# Follow logs in real-time
docker compose logs -f mgx-ai

# Last 100 lines with timestamps
docker compose logs --tail 100 --timestamps mgx-ai
```

### Apache Kafka (kafka) - Optional

**Purpose:** Distributed event streaming (optional, enable with profile)

**Start with Kafka:**
```bash
docker compose --profile kafka up -d
```

**Configuration:**
- Image: `confluentinc/cp-kafka:7.5.0`
- Port: 9092 (external), 29092 (internal)
- Volume: `kafka_data` (persistent)
- Broker ID: 1 (single broker for dev/small deployments)

**Features:**
- Auto-create topics
- 24-hour retention
- 1GB size-based retention

**Monitor Kafka:**
```bash
# Check broker status
docker compose exec kafka kafka-broker-api-versions.sh --bootstrap-server kafka:9092

# List topics
docker compose exec kafka kafka-topics.sh --bootstrap-server kafka:9092 --list

# Create topic
docker compose exec kafka kafka-topics.sh --bootstrap-server kafka:9092 \
  --create --topic mgx-events --partitions 1 --replication-factor 1
```

### Zookeeper (zookeeper) - Optional

**Purpose:** Kafka cluster coordination (required for Kafka)

**Configuration:**
- Image: `confluentinc/cp-zookeeper:7.5.0`
- Port: 2181
- Volumes: `zookeeper_data`, `zookeeper_logs`

---

## Data Persistence & Backups

### Volume Structure

| Volume | Service | Path | Purpose |
|--------|---------|------|---------|
| `pg_data` | postgres | `/var/lib/postgresql/data` | Database files |
| `redis_data` | redis | `/data` | Redis AOF persistence |
| `minio_data` | minio | `/data` | Object storage |
| `kafka_data` | kafka | `/var/lib/kafka/data` | Event streams (optional) |
| `zookeeper_data` | zookeeper | `/var/lib/zookeeper/data` | Zookeeper state (optional) |

### List Volumes

```bash
# Show all MGX volumes
docker volume ls | grep mgx

# Inspect specific volume
docker volume inspect project_pg_data

# Volume location on host
docker volume inspect --format '{{.Mountpoint}}' project_pg_data
```

### PostgreSQL Backups

#### Full Database Dump

```bash
# Backup to SQL file
docker compose exec -T postgres pg_dump -U mgx -d mgx > backup-$(date +%Y%m%d-%H%M%S).sql

# Backup to compressed archive (recommended)
docker compose exec -T postgres pg_dump -U mgx -d mgx | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Size estimate
docker compose exec postgres du -sh /var/lib/postgresql/data
```

#### Restore from Backup

```bash
# From uncompressed dump
docker compose exec -T postgres psql -U mgx -d mgx < backup-20240101-120000.sql

# From compressed backup
gunzip < backup-20240101-120000.sql.gz | \
  docker compose exec -T postgres psql -U mgx -d mgx

# Verify restoration
docker compose exec postgres psql -U mgx -d mgx -c "SELECT COUNT(*) FROM workspaces;"
```

#### Scheduled Backups (Cron)

```bash
#!/bin/bash
# /usr/local/bin/mgx-backup.sh

BACKUP_DIR="/backups/mgx"
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

# Create backup
BACKUP_FILE="$BACKUP_DIR/mgx-db-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose -f /opt/mgx/docker-compose.yml exec -T postgres \
  pg_dump -U mgx -d mgx | gzip > $BACKUP_FILE

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup created: $BACKUP_FILE"
```

Add to crontab (daily at 2 AM):
```bash
0 2 * * * /usr/local/bin/mgx-backup.sh >> /var/log/mgx-backup.log 2>&1
```

### MinIO Backups

#### Using mc (MinIO Client)

```bash
# Mirror entire bucket to local directory
docker run --rm -v /backups/minio:/export minio/mc:latest \
  sh -c "mc alias set myminio http://minio:9000 minioadmin minioadmin && \
         mc mirror myminio/mgx-artifacts /export"

# Restore from backup
docker run --rm -v /backups/minio:/export minio/mc:latest \
  sh -c "mc alias set myminio http://minio:9000 minioadmin minioadmin && \
         mc mirror /export myminio/mgx-artifacts"
```

#### Using S3 CLI

```bash
# If using AWS S3 as backup target
aws s3 sync s3://minio-local/mgx-artifacts s3://backup-bucket/mgx-artifacts/

# Or use AWS DataSync for automated backups
```

### Disk Space Management

```bash
# Check volume sizes
docker system df

# Prune unused data
docker system prune -a

# Check container logs size
docker exec mgx-ai du -sh /app/logs

# Rotate logs (in docker-compose.yml)
# logging:
#   driver: "json-file"
#   options:
#     max-size: "100m"
#     max-file: "10"
```

---

## Database Migrations

### Understanding Alembic

Alembic is the SQL Alchemy migration tool used for schema changes.

**Migration Files:**
```
backend/migrations/
├── env.py           # Alembic environment configuration
├── script.py.mako   # Migration template
└── versions/        # Migration files
    ├── 001_initial.py
    ├── 002_add_git_metadata.py
    └── ...
```

### Running Migrations

#### Automatic (default)

Migrations run automatically when services start:
1. `mgx-migrate` service checks for pending migrations
2. Runs `alembic upgrade head`
3. Exits after completion
4. `mgx-ai` waits for `mgx-migrate` to complete

#### Manual (if needed)

```bash
# Apply all pending migrations
docker compose exec mgx-ai alembic upgrade head

# Apply specific migration
docker compose exec mgx-ai alembic upgrade 002_add_git_metadata

# Downgrade to previous version
docker compose exec mgx-ai alembic downgrade -1

# View migration history
docker compose exec mgx-ai alembic current
docker compose exec mgx-ai alembic history
```

### Creating New Migrations

```bash
# Generate new migration (detects schema changes)
docker compose exec mgx-ai alembic revision --autogenerate -m "description of changes"

# Edit generated migration file: backend/migrations/versions/XXX_description.py

# Apply new migration
docker compose exec mgx-ai alembic upgrade head

# Test with rollback
docker compose exec mgx-ai alembic downgrade -1
docker compose exec mgx-ai alembic upgrade head
```

### Troubleshooting Migrations

#### Migration fails to apply

```bash
# Check error logs
docker compose logs mgx-migrate

# Check database state
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT * FROM alembic_version;"

# Mark migration as complete (use with caution!)
docker compose exec postgres psql -U mgx -d mgx -c \
  "INSERT INTO alembic_version (version_num) VALUES ('migration_id');"
```

#### Database schema out of sync

```bash
# Check current version
docker compose exec mgx-ai alembic current

# View pending migrations
docker compose exec mgx-ai alembic upgrade head --sql

# Downgrade all (dangerous!)
docker compose exec mgx-ai alembic downgrade base

# Re-apply all
docker compose exec mgx-ai alembic upgrade head
```

---

## Monitoring & Logs

### Service Status

```bash
# View all services and health status
docker compose ps

# Expected healthy output:
# NAME               STATUS
# mgx-postgres       Up 5 minutes (healthy)
# mgx-redis          Up 5 minutes (healthy)
# mgx-minio          Up 5 minutes (healthy)
# mgx-ai             Up 3 minutes (healthy)

# Watch status updates
watch docker compose ps

# Get detailed stats
docker compose stats
```

### View Logs

```bash
# View logs for specific service
docker compose logs mgx-ai
docker compose logs postgres
docker compose logs redis

# Follow logs in real-time
docker compose logs -f mgx-ai

# View last N lines
docker compose logs --tail 50 mgx-ai

# With timestamps
docker compose logs --timestamps mgx-ai

# All services
docker compose logs

# Filter by time
docker compose logs --since 2024-01-01T12:00:00 mgx-ai
docker compose logs --until 2024-01-01T13:00:00 mgx-ai
```

### API Health Check

```bash
# Health endpoint
curl http://localhost:8000/health

# Response (healthy):
# {
#   "status": "healthy",
#   "timestamp": "2024-01-01T12:00:00Z",
#   "version": "0.1.0"
# }

# Root endpoint
curl http://localhost:8000/

# API documentation
curl http://localhost:8000/openapi.json
```

### Database Health

```bash
# Check connection
docker compose exec postgres psql -U mgx -d mgx -c "SELECT 1"

# View database size
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT pg_size_pretty(pg_database_size('mgx'))"

# Check table sizes
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) \
   FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"

# View active connections
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname"
```

### Resource Monitoring

```bash
# Memory, CPU, network usage
docker compose stats

# Disk usage per volume
docker volume ls | awk '{print $2}' | xargs -I {} docker volume inspect {} \
  --format '{{.Name}}: {{.Mountpoint}}'

# Container resource limits (if set)
docker inspect mgx-ai | grep -A 20 "HostConfig"
```

### Application Metrics

```bash
# View recent API requests (from logs)
docker compose logs mgx-ai | grep "GET\|POST\|PUT\|DELETE"

# Track error rates
docker compose logs mgx-ai | grep ERROR | wc -l

# Monitor task execution
docker compose logs mgx-ai | grep "task_run\|status"
```

---

## Troubleshooting

### Common Issues and Solutions

#### ❌ "API not healthy" / Port 8000 not responding

**Symptoms:**
```bash
curl http://localhost:8000/health
# curl: (7) Failed to connect
# OR
# HTTP 503 Service Unavailable
```

**Diagnosis:**
```bash
# Check service status
docker compose ps mgx-ai

# View logs
docker compose logs mgx-ai

# Check port is exposed
docker compose port mgx-ai 8000
```

**Solutions:**

1. **Service not started:**
   ```bash
   # Restart service
   docker compose restart mgx-ai
   
   # Check dependencies
   docker compose ps
   ```

2. **Database not healthy:**
   ```bash
   # Check PostgreSQL
   docker compose logs postgres
   docker compose ps postgres
   
   # Reconnect if needed
   docker compose restart postgres
   ```

3. **Check dependencies:**
   ```bash
   # Verify all required services are healthy
   docker compose ps
   
   # All should show "Up X minutes (healthy)"
   # If not, troubleshoot that service
   ```

---

#### ❌ Database connection errors

**Symptoms:**
```
FATAL: database "mgx" does not exist
FATAL: role "mgx" does not exist
```

**Diagnosis:**
```bash
# Check PostgreSQL logs
docker compose logs postgres

# Check if initialization ran
docker compose exec postgres psql -U postgres -c "\\l"
```

**Solutions:**

1. **Database not initialized:**
   ```bash
   # Remove volume and restart
   docker compose down -v postgres
   docker compose up -d postgres
   
   # Wait for initialization
   docker compose ps postgres  # Watch for (healthy)
   ```

2. **Check init-db.sql exists:**
   ```bash
   ls -la init-db.sql
   
   # Should be readable
   head -20 init-db.sql
   ```

3. **Manual database creation:**
   ```bash
   docker compose exec postgres psql -U postgres -c \
     "CREATE USER mgx WITH PASSWORD 'mgx' CREATEDB;"
   
   docker compose exec postgres psql -U postgres -c \
     "CREATE DATABASE mgx OWNER mgx;"
   
   # Re-run migrations
   docker compose restart mgx-migrate
   ```

---

#### ❌ Migration failures

**Symptoms:**
```bash
docker compose logs mgx-migrate
# ERROR: Tables already exist
# ERROR: Invalid migration
# ERROR: Rollback failed
```

**Diagnosis:**
```bash
# Check migration status
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT * FROM alembic_version;"

# View pending migrations
docker compose exec mgx-ai alembic current
docker compose exec mgx-ai alembic heads
```

**Solutions:**

1. **Tables already exist from init-db.sql:**
   ```bash
   # Check if alembic_version exists
   docker compose exec postgres psql -U mgx -d mgx -c \
     "SELECT * FROM alembic_version;"
   
   # If empty, mark initial as applied
   docker compose exec postgres psql -U mgx -d mgx -c \
     "INSERT INTO alembic_version (version_num) VALUES ('initial');"
   ```

2. **Invalid SQL in migration:**
   ```bash
   # Check migration file syntax
   cat backend/migrations/versions/XXX_description.py
   
   # Check for errors
   docker compose exec mgx-ai python -m py_compile \
     backend/migrations/versions/XXX_description.py
   ```

3. **Downgrade and retry:**
   ```bash
   docker compose exec mgx-ai alembic downgrade -1
   docker compose exec mgx-ai alembic upgrade head
   ```

---

#### ❌ MinIO bucket not created

**Symptoms:**
```bash
docker compose ps minio-init
# Exited with error code 1

# S3 operations fail in application
```

**Diagnosis:**
```bash
# Check minio-init logs
docker compose logs minio-init

# Check MinIO is healthy
docker compose ps minio

# Manually check bucket
docker compose exec minio mc ls myminio/
```

**Solutions:**

1. **MinIO endpoint not accessible:**
   ```bash
   # Test connectivity from init container
   docker compose exec minio-init curl http://minio:9000/minio/health/live
   
   # If fails, restart MinIO
   docker compose restart minio
   docker compose up -d minio-init
   ```

2. **Credentials incorrect:**
   ```bash
   # Verify in .env
   grep "S3_" .env
   
   # Restart minio-init with correct creds
   docker compose restart minio-init
   ```

3. **Bucket already exists:**
   ```bash
   # Check existing buckets
   docker compose exec minio mc ls myminio/
   
   # If exists, mark init as complete
   # minio-init uses --ignore-existing flag, should be OK
   ```

4. **Manual bucket creation:**
   ```bash
   docker compose exec minio mc mb myminio/mgx-artifacts
   docker compose exec minio mc version enable myminio/mgx-artifacts
   ```

---

#### ❌ Permission/Disk errors

**Symptoms:**
```
permission denied: /var/lib/postgresql/data
disk quota exceeded
no space left on device
```

**Diagnosis:**
```bash
# Check volume permissions
docker volume inspect project_pg_data | grep Mountpoint
ls -la /var/lib/docker/volumes/project_pg_data/_data/

# Check disk usage
docker system df
df -h

# Check container permissions
docker compose exec postgres id
docker compose exec postgres ls -la /var/lib/postgresql/data
```

**Solutions:**

1. **Fix volume permissions:**
   ```bash
   # Find volume path
   VOLUME_PATH=$(docker volume inspect --format '{{.Mountpoint}}' project_pg_data)
   
   # Fix permissions
   sudo chown 999:999 $VOLUME_PATH
   sudo chmod 700 $VOLUME_PATH
   
   # Restart service
   docker compose restart postgres
   ```

2. **Free disk space:**
   ```bash
   # Remove old images
   docker image prune -a
   
   # Remove stopped containers
   docker container prune
   
   # Remove unused volumes
   docker volume prune
   
   # Check what's using space
   du -sh /var/lib/docker
   ```

3. **Increase disk allocation:**
   ```bash
   # Docker Desktop: Settings > Resources > Disk image size
   # Linux: Extend LVM or add more storage
   ```

---

#### ❌ High CPU/Memory usage

**Symptoms:**
```bash
docker compose stats
# mgx-ai: CPU 80%, MEM 3.5GB / 4GB
```

**Diagnosis:**
```bash
# View resource limits
docker inspect mgx-ai | grep -A 20 "HostConfig"

# Monitor in real-time
docker stats --no-stream mgx-ai

# Check for memory leaks
docker compose logs mgx-ai | grep -i "memory\|gc"
```

**Solutions:**

1. **Reduce worker count:**
   ```bash
   # Edit .env
   MGX_WORKERS=2

   # Restart
   docker compose restart mgx-ai
   ```

2. **Reduce cache size:**
   ```bash
   # Edit .env
   MGX_CACHE_MAX_ENTRIES=1000
   MGX_CACHE_TTL_SECONDS=1800

   # Restart
   docker compose restart mgx-ai
   ```

3. **Set resource limits:**
   ```yaml
   # In docker-compose.yml
   mgx-ai:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
         reservations:
           cpus: '1'
           memory: 1G
   ```

---

#### ❌ Redis connection refused

**Symptoms:**
```
redis.exceptions.ConnectionError: Error 111 connecting to redis:6379
REDIS_URL not set or invalid
```

**Diagnosis:**
```bash
# Check Redis status
docker compose ps redis

# Test connectivity
docker compose exec mgx-ai redis-cli -h redis ping

# Check configuration
grep REDIS .env
```

**Solutions:**

1. **Start Redis:**
   ```bash
   docker compose up -d redis
   docker compose ps redis  # Wait for (healthy)
   ```

2. **Verify REDIS_URL:**
   ```bash
   # Should be redis://redis:6379/0 (or your custom port)
   grep REDIS_URL .env
   
   # Restart services
   docker compose restart mgx-ai
   ```

3. **Clear Redis and restart:**
   ```bash
   docker compose down -v redis
   docker compose up -d redis
   ```

---

### Debugging Checklist

Use this checklist when troubleshooting:

- [ ] All services healthy: `docker compose ps`
- [ ] No error logs: `docker compose logs | grep -i error`
- [ ] Ports accessible: `docker compose port` for each service
- [ ] Network reachable: `docker network inspect project_mgx-net`
- [ ] Volumes mounted: `docker volume ls | grep project`
- [ ] .env file loaded: `docker compose config | head -50`
- [ ] Dependencies met: Check `depends_on` for each service
- [ ] No port conflicts: `netstat -tlnp | grep 8000`
- [ ] Sufficient resources: `docker system df`
- [ ] Logs reviewed: `docker compose logs -f <service>`

---

## Security Best Practices

### 1. Change Default Secrets

**❌ Never leave default values in production:**

```bash
# INSECURE - DO NOT USE IN PRODUCTION
JWT_SECRET=change-me-in-production
S3_SECRET_ACCESS_KEY=minioadmin
DB_PASSWORD=mgx
```

**✅ Generate strong, random secrets:**

```bash
# Generate 32-character hex string
JWT_SECRET=$(openssl rand -hex 32)

# Generate base64 string
S3_SECRET=$(openssl rand -base64 32)

# Generate 16-character hex string
DB_PASSWORD=$(openssl rand -hex 16)

# Update .env file
sed -i "s/change-me-in-production-use-openssl-rand-hex-32/$JWT_SECRET/" .env
sed -i "s/S3_SECRET_ACCESS_KEY=minioadmin/S3_SECRET_ACCESS_KEY=$S3_SECRET/" .env
```

### 2. Use Environment Secrets

**Development:**
```bash
# Plain .env file is OK for local development
cp .env.example .env
```

**Production:**
```bash
# Use Docker secrets (Swarm mode)
echo "my-jwt-secret-value" | docker secret create jwt_secret -

# Or use Docker compose secrets syntax
docker compose -f docker-compose.prod.yml up

# In docker-compose.prod.yml:
# services:
#   mgx-ai:
#     secrets:
#       - jwt_secret
# secrets:
#   jwt_secret:
#     external: true
```

### 3. Implement Reverse Proxy (TLS)

**Nginx with Let's Encrypt:**

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

### 4. Restrict Port Access

```bash
# Close unnecessary ports from public internet
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP (nginx)
sudo ufw allow 443/tcp # HTTPS (nginx)

# Database access only from internal network
# MinIO console only from trusted IPs
# Redis only from containers
```

### 5. Regular Updates

```bash
# Update base images monthly
docker compose pull
docker compose up -d

# Update dependencies
# Rebuild with latest Python packages in next build
docker compose build --no-cache

# Monitor security advisories
# Set up Dependabot notifications on GitHub
```

### 6. Audit Access

```bash
# Enable PostgreSQL logging
# Add to docker-compose.yml environment:
# POSTGRES_INITDB_ARGS: "-c log_statement=all"

# Monitor authentication
docker compose logs postgres | grep "authentication"

# Review API access logs
docker compose logs mgx-ai | grep "GET\|POST\|DELETE"
```

### 7. Backup Security

```bash
# Encrypt backups
docker compose exec -T postgres pg_dump -U mgx -d mgx | \
  openssl enc -aes-256-cbc -salt -in backup.sql.enc

# Store off-site
# Consider: AWS S3 with encryption, Azure Blob, Google Cloud Storage

# Test restore procedure monthly
```

---

## Performance Tuning

### 1. FastAPI Workers

```bash
# .env
# CPU cores - 1 = optimal workers
# 4 cores → 3 workers
# 8 cores → 7 workers
MGX_WORKERS=4
```

### 2. Database Connection Pool

```bash
# .env
# Pool size per worker
# workers × 2 = adequate for most uses
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

### 3. PostgreSQL Performance

```sql
-- Adjust in docker-compose.yml POSTGRES_INITDB_ARGS:
-c shared_buffers=512MB         # For 8GB RAM
-c effective_cache_size=2GB     # 1/4 of total RAM
-c work_mem=32MB                # Memory per operation
-c maintenance_work_mem=256MB   # For backups/index

-- Check current settings
docker compose exec postgres psql -U mgx -d mgx -c "SHOW shared_buffers;"
```

### 4. Redis Performance

```bash
# Monitor hit rate
docker compose exec redis redis-cli info stats | grep hits_ratio

# Clear old entries if needed
docker compose exec redis redis-cli FLUSHDB

# Increase maxmemory policy
# In docker-compose.yml command:
# redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### 5. Caching Strategy

```bash
# .env
MGX_ENABLE_CACHING=true
MGX_CACHE_BACKEND=redis          # Use redis for multi-worker
MGX_CACHE_TTL_SECONDS=3600       # 1 hour
MGX_CACHE_MAX_ENTRIES=50000      # Increase for more data

# Monitor cache effectiveness
curl http://localhost:8000/metrics | grep cache_hits
```

### 6. Load Balancing

```nginx
# Nginx upstream for multiple workers
upstream mgx_api {
    server localhost:8000;
    server localhost:8001;  # Scale to multiple containers
    server localhost:8002;
    keepalive 32;
}

server {
    listen 80;
    location / {
        proxy_pass http://mgx_api;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 7. Disk I/O Optimization

```bash
# Use SSD for data volumes
# Check mount options
df -T | grep mgx

# Increase journal size for MinIO
# In docker-compose.yml MinIO volumes:
# - minio_data:/data:rw,sync=false

# Enable write-back caching for Redis
# In docker-compose.yml Redis command:
# redis-server --appendonly yes --appendfsync no
```

### 8. Memory Optimization

```bash
# Monitor memory usage
docker compose stats mgx-ai

# Reduce cache size if memory is limited
MGX_CACHE_MAX_ENTRIES=1000

# Limit container memory
# In docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 2G
```

---

## External Integrations

### AWS S3 (Instead of MinIO)

```bash
# .env
S3_ENDPOINT_URL=https://s3.us-west-2.amazonaws.com
S3_REGION=us-west-2
S3_BUCKET=my-mgx-artifacts
S3_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
S3_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_SECURE=true

# Create IAM user with S3 access
# Create bucket
# Update environment variables
# Restart services
docker compose restart mgx-ai
```

### Managed PostgreSQL (AWS RDS)

```bash
# .env
DB_HOST=mydb.c9akciq32.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=mgx
DB_USER=admin
DB_PASSWORD=strong-password

# Run migrations against RDS
docker compose exec mgx-ai alembic upgrade head

# Test connection
docker compose exec mgx-ai python -c \
  "from backend.config import settings; print(settings.async_database_url)"
```

### Enable Kafka for Event Streaming

```bash
# Start with Kafka profile
docker compose --profile kafka up -d

# Configure in .env
KAFKA_ENABLED=true
KAFKA_BROKERS=kafka:29092
KAFKA_TOPIC_EVENTS=mgx-events

# Verify Kafka is running
docker compose ps kafka
docker compose ps zookeeper

# Test topic creation
docker compose exec kafka kafka-topics.sh \
  --bootstrap-server kafka:29092 \
  --create --topic mgx-events --if-not-exists

# Consume events (development only)
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server kafka:29092 \
  --topic mgx-events \
  --from-beginning
```

### OpenTelemetry Observability

```bash
# Add Jaeger for distributed tracing
# Add Prometheus for metrics
# Add Grafana for visualization

# In .env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Extend docker-compose.yml with:
# jaeger:
#   image: jaegertracing/all-in-one:latest
#   ports: ["6831:6831/udp", "16686:16686"]
```

### GitHub Integration

See [Ticket #5: Git-Aware Execution](docs/GIT_AWARE_EXECUTION.md) for complete GitHub App setup.

```bash
# GitHub App authentication (recommended)
GITHUB_APP_ID=123456
GITHUB_CLIENT_ID=Iv1.abcdef123456
GITHUB_PRIVATE_KEY_PATH=/run/secrets/github_app_private_key.pem

# Or Personal Access Token (fallback)
GITHUB_PAT=ghp_xxxxxxxxxxxx
```

---

## Scaling & High Availability

### Horizontal Scaling (Multiple API Servers)

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  mgx-ai-1:
    build: .
    ports: ["8001:8000"]
    depends_on: [postgres, redis, minio]

  mgx-ai-2:
    build: .
    ports: ["8002:8000"]
    depends_on: [postgres, redis, minio]

  mgx-ai-3:
    build: .
    ports: ["8003:8000"]
    depends_on: [postgres, redis, minio]

  # Nginx load balancer
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on: [mgx-ai-1, mgx-ai-2, mgx-ai-3]
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mgx-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mgx-api
  template:
    metadata:
      labels:
        app: mgx-api
    spec:
      containers:
      - name: mgx-api
        image: mgx-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mgx-secrets
              key: database-url
        - name: REDIS_URL
          value: redis://redis:6379/0
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
```

### Database Replication

```bash
# PostgreSQL streaming replication
# Set up primary-replica configuration
# Consider managed services: AWS RDS, Google Cloud SQL, Azure Database

# For high availability:
# - Use PostgreSQL with replicas
# - Enable automatic failover with Patroni
# - Monitor with Prometheus + Grafana
```

### Backup Strategy

```bash
# Automated daily backups
# Off-site replication (S3, Azure Blob, GCS)
# Weekly full backups to separate storage
# Monthly archival retention

# 3-2-1 rule:
# - 3 copies of data
# - 2 different storage media
# - 1 off-site copy
```

---

## Summary

This Docker Compose setup provides:

✅ **Production-Ready:**
- All critical services with health checks
- Proper startup ordering and dependencies
- Data persistence with volumes
- Comprehensive logging and monitoring

✅ **Secure:**
- Environment variable management
- Secret rotation guidance
- TLS/HTTPS support via reverse proxy
- Network isolation

✅ **Scalable:**
- Redis for distributed caching
- PostgreSQL connection pooling
- Kafka for event streaming (optional)
- Horizontal scaling with load balancing

✅ **Recoverable:**
- Automated backups procedures
- Volume management and recovery
- Migration tracking and rollback

✅ **Observable:**
- Health endpoints for all services
- Comprehensive logging
- Resource monitoring
- Performance metrics

For questions or issues, refer to:
- [GitHub Issues](https://github.com/your-org/mgx-agent/issues)
- [Community Slack](#)
- [Email Support](mailto:support@example.com)

</details>

---

## Appendix B: API reference + real-time events (canonical contract)

<details>
<summary>Expand Appendix B</summary>

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

---

### WebSocket quick notes (entry point)

# WebSocket / Event Streaming

MGX Agent supports **real-time event streaming** over WebSockets.

## Endpoints

- `ws://localhost:8000/ws/tasks/{task_id}`
- `ws://localhost:8000/ws/runs/{run_id}`
- `ws://localhost:8000/ws/stream` (global stream)

## Event contract

The canonical event schema, event types, and message examples are documented in:

- **[API_EVENTS_DOCUMENTATION.md](./API_EVENTS_DOCUMENTATION.md)**

Implementation reference:

- Router: [`backend/routers/ws.py`](../backend/routers/ws.py)
- Broadcaster: `backend/services/events.py` (see `backend/services/`)

</details>

---

## Appendix C: Testing guide (unit/integration/e2e/performance)

<details>
<summary>Expand Appendix C</summary>

# 🧪 Testing Guide - TEM Agent

Comprehensive guide to the TEM Agent test infrastructure, fixtures, and best practices.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Setup](#setup)
3. [Running Tests](#running-tests)
4. [Test Structure](#test-structure)
5. [Fixtures](#fixtures)
6. [Test Helpers & Stubs](#test-helpers--stubs)
7. [Writing Tests](#writing-tests)
8. [Coverage](#coverage)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The TEM Agent project uses **pytest** as its testing framework with comprehensive support for:

- **Unit tests**: Fast, isolated tests for individual functions
- **Integration tests**: Tests verifying component interactions
- **End-to-end tests**: Complete workflow tests
- **Async testing**: Built-in asyncio support via pytest-asyncio
- **Coverage tracking**: Automated coverage reports (HTML, XML, terminal)
- **MetaGPT stubs**: Lightweight mocks for MetaGPT components (no network calls)

### Current Status

```
Phase 3: Testing Infrastructure ✅
├─ pytest.ini configuration      ✅ Complete
├─ requirements-dev.txt          ✅ Complete  
├─ Test directory structure      ✅ Complete
├─ MetaGPT stubs & factories     ✅ Complete
├─ Test fixtures                 ✅ Complete
└─ Smoke tests                   ✅ Passing
```

**Coverage Target**: 80%+ (current: ~71%; see PROJECT_STATUS.md)

---

## Setup

### Installation

```bash
# 1. Install test dependencies
pip install -r requirements-dev.txt

# 2. Verify pytest is installed
pytest --version

# 3. Check pytest can collect tests
pytest --collect-only
```

### Verify Setup

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_helpers.py

# Run specific test class
pytest tests/unit/test_helpers.py::TestMockLogger

# Run specific test function
pytest tests/unit/test_helpers.py::TestMockLogger::test_logger_creation
```

---

## Running Tests

### Common Commands

```bash
# Run all tests with coverage report
pytest

# Run specific test level
pytest tests/unit              # Unit tests only
pytest tests/integration       # Integration tests only
pytest tests/e2e              # End-to-end tests only

# Run with output options
pytest -v                      # Verbose output
pytest -s                      # Show print statements
pytest -x                      # Stop on first failure
pytest -k "keyword"            # Run tests matching keyword

# Run with markers
pytest -m asyncio              # Async tests only
pytest -m "not slow"           # Skip slow tests

# Performance/load tests (excluded by default via pytest.ini addopts)
pytest -o addopts='' -m performance tests/performance -v

# Parallel execution (faster)
pytest -n auto                 # Use all CPU cores

# Run with specific log level
pytest --log-cli-level=DEBUG   # Show debug logs
```

Performance suite notes:

- Generates artifacts in `perf_reports/` (`latest.json`, `before_after.md`)
- Compares against the committed baseline `perf_reports/baseline.json`

See [docs/PERFORMANCE.md](PERFORMANCE.md) for configuration flags, profiling usage, and the CI workflow.

### Coverage Reports

```bash
# Terminal report (default)
pytest
# Shows missing lines and coverage percentage

# Generate HTML report
pytest --cov=mgx_agent --cov-report=html
# Open: htmlcov/index.html

# Generate XML report (for CI/CD)
pytest --cov=mgx_agent --cov-report=xml
# Use in: GitHub Actions, GitLab CI, etc.

# Combined reports
pytest --cov=mgx_agent --cov-report=term-missing --cov-report=html --cov-report=xml

# Coverage by specific module
pytest --cov=mgx_agent.roles tests/unit
```

---

## Test Structure

### Directory Layout

```
tests/
├── __init__.py                  # Package init
├── conftest.py                  # Global fixtures & configuration
├── pytest.ini                   # Pytest config (in project root)
│
├── unit/                        # Fast, isolated tests
│   ├── __init__.py
│   ├── test_helpers.py         # Tests for test infrastructure
│   ├── test_config.py          # Tests for config module
│   ├── test_metrics.py         # Tests for metrics module
│   ├── test_actions.py         # Tests for actions module
│   ├── test_adapter.py         # Tests for adapter module
│   ├── test_roles.py           # Tests for roles module
│   └── test_team.py            # Tests for team module
│
├── integration/                 # Component interaction tests
│   ├── __init__.py
│   ├── test_team_roles.py      # Team + Roles integration
│   ├── test_adapter_roles.py   # Adapter + Roles integration
│   └── test_workflow.py        # Complete workflow tests
│
├── e2e/                        # Complete workflow tests
│   ├── __init__.py
│   ├── test_full_pipeline.py  # Complete pipeline
│   └── test_user_scenarios.py # Real-world use cases
│
├── helpers/                    # Test utilities & stubs
│   ├── __init__.py
│   ├── metagpt_stubs.py       # MetaGPT component stubs
│   └── factories.py           # Factory functions
│
└── logs/                       # Test logs directory
    └── pytest.log             # Pytest log file
```

### Test File Structure

```python
# tests/unit/test_module.py

import pytest
from mgx_agent.module import MyClass

class TestMyClass:
    """Tests for MyClass."""
    
    def test_basic_functionality(self):
        """Test basic feature."""
        obj = MyClass()
        assert obj is not None
    
    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async feature."""
        obj = MyClass()
        result = await obj.async_method()
        assert result is not None
    
    def test_with_fixtures(self, fake_team, fake_role):
        """Test using fixtures."""
        team = fake_team
        team.hire(fake_role)
        assert len(team.roles) == 1
```

---

## Fixtures

### Global Fixtures (from conftest.py)

#### Event Loop Fixture

```python
def test_async_operation(event_loop):
    """Async tests automatically get a fresh event loop."""
    # Fixture is automatically used for @pytest.mark.asyncio tests
    pass
```

#### Team Fixtures

```python
def test_with_team(fake_team):
    """Get a team with 4 default roles."""
    assert len(fake_team.roles) == 4

def test_custom_team(fake_team_with_custom_roles):
    """Factory fixture for custom teams."""
    team = fake_team_with_custom_roles(
        role_names=["Engineer", "Tester", "Reviewer"]
    )
    assert len(team.roles) == 3
```

#### Role Fixtures

```python
def test_with_role(fake_role):
    """Get a role with 2 default actions."""
    assert len(fake_role.actions) == 2
```

#### Memory Fixtures

```python
def test_with_memory(fake_memory):
    """Get an empty memory store."""
    fake_memory.add("key", "value")
    assert fake_memory.get("key") == "value"

def test_with_memory_data(fake_memory_with_data):
    """Get memory with initial data."""
    assert fake_memory_with_data.get("task") == "Test Task"
    assert len(fake_memory_with_data.get_messages()) > 0
```

#### Message Fixtures

```python
def test_with_message(fake_message):
    """Factory fixture for creating messages."""
    msg = fake_message(role="user", content="Hello")
    assert msg.content == "Hello"
```

#### LLM Response Fixtures

```python
def test_with_llm_response(fake_llm_response):
    """Factory fixture for LLM responses."""
    response = fake_llm_response(content="Generated code")
    assert "Generated code" in response.content

def test_with_mock_llm(async_mock_llm):
    """Factory fixture for async mock LLMs."""
    mock = async_mock_llm(responses=["Response 1", "Response 2"])
    result = await mock("prompt")
    assert "Response 1" in result
```

#### Directory Fixtures

```python
def test_with_output_dir(tmp_output_dir):
    """Get a temporary output directory."""
    output_file = tmp_output_dir / "output.txt"
    output_file.write_text("test")
    assert output_file.exists()

def test_with_logs_dir(tmp_logs_dir):
    """Get a temporary logs directory."""
    log_file = tmp_logs_dir / "test.log"
    log_file.write_text("log content")
    assert log_file.exists()
```

#### Logging Fixtures

```python
def test_with_caplog(caplog_setup):
    """Capture and verify logs."""
    logger = logging.getLogger(__name__)
    logger.info("Test message")
    
    assert "Test message" in caplog_setup.text
```

---

## Test Helpers & Stubs

### MetaGPT Stubs

Since tests should run without the real MetaGPT package or network calls, we provide lightweight stubs:

#### Available Stubs

```python
from tests.helpers import (
    MockAction,      # Stub for metagpt.Action
    MockRole,        # Stub for metagpt.Role
    MockTeam,        # Stub for metagpt.Team
    MockMessage,     # Stub for metagpt.types.Message
    mock_logger,     # Stub for metagpt.logs.logger
)
```

#### Automatic Registration

The stubs are automatically registered in `sys.modules` in `tests/conftest.py`:

```python
sys.modules['metagpt'] = MetaGPTStub()
sys.modules['metagpt.logs'] = MetaGPTLogsStub()
sys.modules['metagpt.types'] = MetaGPTTypesStub()
```

This allows tests to import and use MetaGPT components without errors.

### Factory Functions

#### Team Factory

```python
from tests.helpers import create_fake_team

# Basic usage
team = create_fake_team()  # 4 default roles

# Custom
team = create_fake_team(
    name="CustomTeam",
    role_names=["Mike", "Alex", "Bob", "Charlie"]
)
```

#### Role Factory

```python
from tests.helpers import create_fake_role

role = create_fake_role(
    name="Engineer",
    goal="Write code",
    num_actions=3
)
```

#### Action Factory

```python
from tests.helpers import create_fake_action

action = create_fake_action(
    name="WriteCode",
    run_result="Generated code"
)

result = await action.run()
```

#### Memory Factory

```python
from tests.helpers import create_fake_memory_store

memory = create_fake_memory_store(
    initial_data={"key": "value"},
    initial_messages=[msg1, msg2]
)
```

#### LLM Response Factory

```python
from tests.helpers import (
    create_fake_llm_response,
    create_async_mock_llm
)

# Fake response
response = create_fake_llm_response(
    content="Generated code",
    completion_tokens=50
)

# Async mock LLM
mock_llm = create_async_mock_llm(
    responses=["Response 1", "Response 2"]
)
result = await mock_llm("prompt")
```

---

## Writing Tests

### Unit Test Example

```python
# tests/unit/test_myfeature.py

import pytest
from mgx_agent.module import MyClass

class TestMyClass:
    """Test suite for MyClass."""
    
    def test_initialization(self):
        """Test object initialization."""
        obj = MyClass(param="value")
        assert obj.param == "value"
    
    def test_method_returns_expected_value(self):
        """Test method returns correct value."""
        obj = MyClass()
        result = obj.method()
        assert result is not None
        assert isinstance(result, str)
    
    def test_exception_on_invalid_input(self):
        """Test exception handling."""
        obj = MyClass()
        with pytest.raises(ValueError):
            obj.method(invalid_param="test")
```

### Async Test Example

```python
# tests/unit/test_async_feature.py

import pytest
from mgx_agent.module import AsyncClass

class TestAsyncClass:
    """Test suite for async features."""
    
    @pytest.mark.asyncio
    async def test_async_method(self):
        """Test async method."""
        obj = AsyncClass()
        result = await obj.async_method()
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_async_with_mock_team(self, fake_team):
        """Test async with fixtures."""
        obj = AsyncClass(team=fake_team)
        result = await obj.process()
        assert result is not None
```

### Integration Test Example

```python
# tests/integration/test_team_workflow.py

import pytest
from mgx_agent.team import MGXStyleTeam
from mgx_agent.roles import Mike, Alex

@pytest.mark.integration
class TestTeamWorkflow:
    """Test team workflow integration."""
    
    @pytest.mark.asyncio
    async def test_team_execution(self, fake_team):
        """Test complete team execution."""
        # Run team
        result = await fake_team.run(max_iterations=3)
        
        # Verify results
        assert fake_team.is_running is False
        assert fake_team.run_count == 1
```

### Test with Markers

```python
@pytest.mark.asyncio
def test_async_operation():
    """Mark test as async."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Mark test as slow (use: pytest -m "not slow")."""
    pass

@pytest.mark.integration
def test_integration():
    """Mark test as integration."""
    pass
```

---

## Coverage

### Understanding Coverage Reports

The terminal coverage report shows:

```
mgx_agent/config.py    87    4    95%   23-25, 45
mgx_agent/roles.py    189   12    94%   45-50, 100-102
...
```

Columns:
- **Module**: File path
- **Statements**: Total lines of code
- **Missing**: Lines not executed in tests
- **Coverage**: Percentage of code covered
- **Missing lines**: Line numbers not covered

### Achieving 80% Coverage Target

1. **Identify gaps**:
   ```bash
   pytest --cov=mgx_agent --cov-report=term-missing
   ```

2. **Write tests for missing lines**:
   ```python
   def test_untested_branch():
       # Test code path not yet covered
       pass
   ```

3. **Track progress**:
   ```bash
   # Repeat coverage check
   pytest --cov=mgx_agent --cov-report=term-missing
   ```

### HTML Coverage Reports

```bash
# Generate HTML report
pytest --cov=mgx_agent --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov\index.html  # Windows
```

The HTML report provides:
- Color-coded coverage visualization
- Line-by-line coverage details
- Branch coverage analysis
- Clickable file navigation

### Coverage Requirements

This project maintains strict quality standards:

```bash
# Verify 80% coverage requirement
pytest --cov=mgx_agent --cov-report=term-missing

# Check test count requirement (≥130 tests)
pytest --collect-only -q | tail -1
```

**Quality Gates**:
- ✅ **Test Count**: ≥130 tests (current: 310 tests)
- ✅ **Coverage**: ≥80% overall coverage
- ✅ **HTML Reports**: Generated under `htmlcov/`
- ✅ **XML Reports**: Generated as `coverage.xml`

### Comprehensive Coverage Commands

```bash
# Run tests with all coverage reports
pytest --cov=mgx_agent \
       --cov-report=html:htmlcov \
       --cov-report=xml:coverage.xml \
       --cov-report=term-missing

# Expected output files:
# - coverage.xml (XML format for CI/CD tools)
# - htmlcov/ (HTML reports directory)
# - .coverage (binary coverage data)

# View coverage in terminal
coverage report --show-missing

# Generate XML report explicitly
coverage xml -o coverage.xml

# Check coverage percentage
pytest --cov=mgx_agent --cov-report=term-missing | tail -1
```

### CI/CD Integration

#### GitHub Actions Workflow

The project includes a comprehensive GitHub Actions workflow (`.github/workflows/tests.yml`) that automatically:

1. **Installs dependencies** including `pytest-cov` for coverage
2. **Runs unit, integration, and E2E tests** with coverage tracking
3. **Generates HTML and XML coverage reports**
4. **Uploads coverage artifacts** for each Python version
5. **Validates quality gates** (≥130 tests, ≥80% coverage)

```yaml
# Trigger conditions
on:
  push:
    branches: [ main, test-cli-workflows-coverage-ci-docs ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:
```

#### Automated Quality Checks

The workflow performs automated quality validation:

```bash
# Test count validation (≥130 tests)
TEST_COUNT=$(pytest --collect-only -q | grep -o '[0-9]*')
if [ "$TEST_COUNT" -lt 130 ]; then exit 1; fi

# Coverage validation (≥80%)
COVERAGE=$(coverage report | tail -1 | grep -o '[0-9]*%' | sed 's/%//')
if [ "$COVERAGE" -lt 80 ]; then exit 1; fi
```

#### Coverage Report Integration

- **HTML Reports**: Uploaded as artifacts (`coverage-reports-*.tar.gz`)
- **XML Reports**: Generated as `coverage.xml` for CI/CD tools
- **Codecov Integration**: Optional upload if token is configured
- **PR Comments**: Automatic coverage reporting on pull requests

#### Performance (Phase 4) Job

The CI workflow also includes a dedicated `performance` job that runs the performance-marked suite (excluded from default runs).

- **Command:** `pytest -o addopts='' -m performance tests/performance -v`
- **Artifacts:** uploads `perf_reports/` (including `latest.json` and `before_after.md`)
- **Job summary:** publishes the before/after table so regressions are visible without downloading artifacts
- **Triggering:** can be configured to run on a schedule, workflow dispatch, or via a PR label (see `.github/workflows/tests.yml`)

#### Manual Coverage Commands

For local development and CI verification:

```bash
# Full coverage report
pytest --cov=mgx_agent --cov-report=html:htmlcov --cov-report=xml:coverage.xml

# Check test and coverage requirements
pytest --collect-only -q
coverage report --show-missing
coverage xml -o coverage.xml

# View HTML reports
open htmlcov/index.html  # or your browser
```

The workflow ensures all quality gates are met before merging to maintain code quality standards.

---

## Troubleshooting

### Common Issues

#### 1. Event Loop Errors

**Problem**: `RuntimeError: no running event loop`

**Solution**: Use `@pytest.mark.asyncio` decorator:
```python
@pytest.mark.asyncio
async def test_async_function():
    pass
```

#### 2. Import Errors for MetaGPT

**Problem**: `ModuleNotFoundError: No module named 'metagpt'`

**Solution**: Stubs are registered in `conftest.py`. Ensure:
- `conftest.py` exists in `tests/` directory
- Tests are run via pytest (not directly)

#### 3. Fixture Not Found

**Problem**: `fixture 'fake_team' not found`

**Solution**: Ensure `conftest.py` is in the same directory:
```
tests/
├── conftest.py          # Must be here
├── unit/
│   └── test_*.py        # Uses fixtures
```

#### 4. Tests Not Discovered

**Problem**: `no tests collected`

**Solution**:
```bash
# Check pytest can find tests
pytest --collect-only

# Verify file/function names:
# - Files: test_*.py or *_test.py
# - Classes: Test*
# - Functions: test_*
```

#### 5. Async Test Timeout

**Problem**: `test timed out after 300 seconds`

**Solution**:
```python
@pytest.mark.timeout(10)  # 10 second timeout
async def test_slow_async():
    pass
```

Or adjust in `pytest.ini`:
```ini
timeout = 600  # Change to 600 seconds
```

---

## Best Practices

### ✅ Do

- ✅ Use fixtures to reduce boilerplate
- ✅ Write descriptive test names
- ✅ Test one thing per test function
- ✅ Use parametrize for similar tests
- ✅ Mock external dependencies
- ✅ Keep tests fast (< 1 second each)
- ✅ Test edge cases and errors

### ❌ Don't

- ❌ Depend on test execution order
- ❌ Make network calls in tests
- ❌ Use real file I/O (use tmp_path)
- ❌ Print to stdout (use logging)
- ❌ Have side effects between tests
- ❌ Use sleep() in tests
- ❌ Ignore test failures

---

## Next Steps

### Phase 3 Roadmap

1. **✅ Pytest Infrastructure** (Week 1)
   - Setup pytest, fixtures, stubs
   - Create test directory structure
   - Write smoke tests

2. **Unit Tests** (Week 2-3)
   - Test each module in isolation
   - Achieve 80% coverage
   - 80+ unit tests

3. **Integration Tests** (Week 4)
   - Test component interactions
   - Workflow integration tests
   - 30+ integration tests

4. **E2E Tests** (Week 5)
   - Complete pipeline tests
   - User scenario tests
   - 10+ e2e tests

### Coverage Target

```
Current:  2%  (Baseline)
Phase 3:  80% (Target)  ← You are here

Unit:     80%
Integration: 70%
E2E:      60%
```

---

## Documentation

- [Pytest Official Docs](https://docs.pytest.org/)
- [Pytest Asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py Docs](https://coverage.readthedocs.io/)
- [Mock/Stub Patterns](https://en.wikipedia.org/wiki/Mock_object)

---

**Last Updated**: December 2024  
**Status**: 🟢 Testing Infrastructure Complete

</details>

---

## Appendix D: Performance guide (profiling, caching, async tuning)

<details>
<summary>Expand Appendix D</summary>

# Performance & Profiling Guide (Phase 4)

This document describes the Phase 4 performance features: async execution patterns, response caching configuration, profiling/reporting, and the load-test workflow used in CI.

## Contents

- [Quick start](#quick-start)
- [Configuration flags](#configuration-flags)
- [Async patterns](#async-patterns)
- [Caching](#caching)
- [Profiling](#profiling)
- [Load testing & CI workflow](#load-testing--ci-workflow)
- [Best practices](#best-practices)

## Quick start

### Run the default test suite (performance tests excluded)

Performance tests are excluded by default via `pytest.ini` (`-m "not performance"`).

```bash
pytest
```

### Run the performance suite locally

Because `pytest.ini` defines `addopts` that excludes performance tests, override it:

```bash
pytest -o addopts='' -m performance tests/performance -v
```

Artifacts written by the performance suite:

- `perf_reports/latest.json` (generated)
- `perf_reports/before_after.md` (generated)

### Run the standalone load-test harness

```bash
python scripts/load_test.py --runs 20 --concurrency 10 --llm-latency 0.01
```

To update the committed baseline (do this only during a performance-baseline update / release process):

```bash
python scripts/load_test.py --runs 20 --concurrency 10 --llm-latency 0.01 --update-baseline
# commit perf_reports/baseline.json
```

## Configuration flags

All performance-related configuration is in `mgx_agent.config.TeamConfig`.

### Caching flags

| Flag | Type | Default | Notes |
|---|---|---:|---|
| `enable_caching` | bool | `True` | Master switch for caching |
| `cache_backend` | str | `"memory"` | `none` \| `memory` \| `redis` |
| `cache_max_entries` | int | `1024` | In-memory LRU capacity |
| `cache_ttl_seconds` | int | `3600` | TTL in seconds (0 disables TTL in-memory) |
| `redis_url` | str\|None | `None` | Required when `cache_backend="redis"` |
| `cache_log_hits` | bool | `False` | Log cache hits (noisy) |
| `cache_log_misses` | bool | `False` | Log cache misses (noisy) |

Example:

```python
from mgx_agent import MGXStyleTeam, TeamConfig

config = TeamConfig(
    enable_caching=True,
    cache_backend="memory",
    cache_max_entries=4096,
    cache_ttl_seconds=3600,
)
team = MGXStyleTeam(config=config)
```

Redis example:

```python
config = TeamConfig(
    enable_caching=True,
    cache_backend="redis",
    redis_url="redis://localhost:6379/0",
    cache_ttl_seconds=3600,
)
```

### Profiling flags

| Flag | Type | Default | Notes |
|---|---|---:|---|
| `enable_profiling` | bool | `False` | Enables the team profiler integration |
| `enable_profiling_tracemalloc` | bool | `False` | Enables tracemalloc-based memory sampling |

CLI flags:

```bash
python -m mgx_agent.cli --profile
python -m mgx_agent.cli --profile --profile-memory
```

### Environment variables

| Variable | Meaning |
|---|---|
| `MGX_GLOBAL_CACHE=1` | Use a shared in-memory cache instance across teams (used by the load test harness for stable hit-rate under concurrency) |

## Async patterns

Phase 4 introduces async utilities in `mgx_agent.performance.async_tools`:

- `AsyncTimer(name)`: async context manager that records span timings (and forwards to an active profiler if present)
- `bounded_gather(*awaitables, max_concurrent=N)`: `asyncio.gather` with concurrency limits
- `with_timeout(seconds)`: decorator around `asyncio.wait_for`
- `run_in_thread(func, *args, **kwargs)`: offload blocking work to the default threadpool

Example:

```python
from mgx_agent.performance import AsyncTimer, bounded_gather

async def fetch_all(urls: list[str]):
    async with AsyncTimer("fetch_all"):
        return await bounded_gather(*(fetch(u) for u in urls), max_concurrent=10)
```

## Caching

### What is cached?

The hottest path is plan generation (`AnalyzeTask + DraftPlan`) in `MGXStyleTeam.analyze_and_plan()`. The team also exposes a generic helper:

- `MGXStyleTeam.cached_llm_call(...)`

### Cache backends

- **none**: `NullCache` (no caching)
- **memory**: `InMemoryLRUTTLCache` (thread-safe, LRU + TTL)
- **redis**: `RedisCache` (optional dependency: `redis`)

### Operational helpers

`MGXStyleTeam` provides runtime cache utilities:

- `cache_inspect()` / `inspect_cache()`
- `cache_clear()` / `clear_cache()`
- `cache_warm()` / `warm_cache()`

## Profiling

### Using the profiler directly

For accurate async span tracking, use `PerformanceProfiler` as an async context manager:

```python
from mgx_agent.performance.profiler import PerformanceProfiler
from mgx_agent.performance.async_tools import AsyncTimer

async with PerformanceProfiler(
    "my_run",
    enable_tracemalloc=True,
    enable_file_output=True,
) as prof:
    async with AsyncTimer("phase_a"):
        await do_work()

# prof.to_run_metrics() -> dict
```

### Team-integrated profiling

When `TeamConfig(enable_profiling=True)` is enabled, `MGXStyleTeam._start_profiler()` / `_end_profiler()` can be used to produce report files.

Generated artifacts:

- `logs/performance/<timestamp>.json` (detailed)
- `perf_reports/latest.json` (summary)

## Load testing & CI workflow

### Baseline and regression gating

- `perf_reports/baseline.json` is committed and acts as the regression baseline.
- The performance test generates `perf_reports/latest.json` and `perf_reports/before_after.md`.
- CI uploads `perf_reports/` as artifacts.

### CI job

The GitHub Actions workflow includes a dedicated `performance` job that:

1. Runs `pytest -o addopts='' -m performance tests/performance`
2. Uploads `perf_reports` artifacts
3. Publishes the before/after table into the job summary

## Best practices

- Keep performance tests deterministic: mock latency, avoid real network/LLM calls.
- Use generous budgets in CI and rely on the baseline regression checks to detect slowdowns.
- Only update `perf_reports/baseline.json` intentionally (release cadence) and accompany it with an updated [PERFORMANCE_REPORT.md](../PERFORMANCE_REPORT.md).
- Prefer `bounded_gather` over unbounded `asyncio.gather` to avoid resource spikes.
- Offload blocking file/system operations via `run_in_thread()`.

</details>

---

## Appendix E: Web stack support (StackSpec, manifests, constraints)

<details>
<summary>Expand Appendix E</summary>

# Web Stack Desteği - TEM Agent

MGX AI artık **production-ready web development** için tam stack desteği sunuyor! 🚀

## 📋 İçindekiler

- [Desteklenen Stack'ler](#desteklenen-stackler)
- [Özellikler](#özellikler)
- [Kullanım](#kullanım)
- [JSON Task Format](#json-task-format)
- [Örnekler](#örnekler)
- [Stack-Aware Actions](#stack-aware-actions)
- [Output Validation](#output-validation)
- [Sınırlamalar](#sınırlamalar)

---

## 🎯 Desteklenen Stack'ler

### Backend (5 stack)

| Stack ID | İsim | Test Framework | Package Manager | Dil |
|----------|------|----------------|-----------------|-----|
| `express-ts` | Node.js + Express (TypeScript) | Jest | npm/pnpm | TS |
| `nestjs` | Node.js + NestJS (TypeScript) | Jest | npm/pnpm | TS |
| `laravel` | PHP + Laravel | PHPUnit | Composer | PHP |
| `fastapi` | Python + FastAPI | Pytest | pip | Python |
| `dotnet-api` | .NET Web API (C#) | xUnit | dotnet | C# |

### Frontend (3 stack)

| Stack ID | İsim | Test Framework | Package Manager | Dil |
|----------|------|----------------|-----------------|-----|
| `react-vite` | React + Vite (TypeScript) | Vitest | npm/pnpm | TS |
| `nextjs` | Next.js (TypeScript) | Jest | npm/pnpm | TS |
| `vue-vite` | Vue + Vite (TypeScript) | Vitest | npm/pnpm | TS |

### DevOps (2 stack)

| Stack ID | İsim | Test Framework | Package Manager | Dil |
|----------|------|----------------|-----------------|-----|
| `devops-docker` | Docker + Docker Compose | - | - | YAML |
| `ci-github-actions` | GitHub Actions CI/CD | - | - | YAML |

---

## ✨ Özellikler

### Phase A: Stack Specifications
- ✅ **StackSpec**: Her stack için teknik spesifikasyonlar
- ✅ **ProjectType**: `api`, `webapp`, `fullstack`, `devops`
- ✅ **OutputMode**: `generate_new`, `patch_existing`
- ✅ **Automatic Stack Inference**: Görev açıklamasından stack tahmin etme

### Phase B: JSON Input Contract
- ✅ **Structured Input**: JSON dosyasından görev yükleme
- ✅ **Constraints**: Ek kısıtlamalar tanımlama
- ✅ **Plain Text Fallback**: Normal metin görev desteği devam ediyor

### Phase C: Stack-Aware Actions
- ✅ **AnalyzeTask**: Karmaşıklık + önerilen stack + dosya manifest + test stratejisi
- ✅ **DraftPlan**: Stack bilgisini içeren plan
- ✅ **WriteCode**: Multi-language + FILE manifest format
- ✅ **WriteTest**: Stack'e özgü test framework (Jest/Vitest/PHPUnit/Pytest)
- ✅ **ReviewCode**: Stack-specific best practices kontrolü

### Phase D: Guardrails
- ✅ **Output Validation**: Stack yapısına uygunluk kontrolü
- ✅ **FILE Manifest Parser**: Çoklu dosya desteği
- ✅ **Safe File Writer**: Otomatik `.bak` yedekleme
- ✅ **Patch Mode**: Mevcut projelere güvenli değişiklik

### Phase E: Tests
- ✅ **28+ Integration Tests**: Stack specs, file utils, validation testleri

---

## 🚀 Kullanım

### 1. JSON Dosyasından Görev Yükleme

```bash
python -m mgx_agent.cli --json examples/express_api_task.json
```

### 2. Normal Metin Görev (Otomatik Stack Inference)

```bash
python -m mgx_agent.cli --task "Create a Next.js dashboard with user management"
```

### 3. Python API Kullanımı

```python
from mgx_agent.team import MGXStyleTeam
from mgx_agent.config import TeamConfig

# Stack-aware config
config = TeamConfig(
    target_stack="fastapi",
    project_type="api",
    output_mode="generate_new",
    strict_requirements=True,
    constraints=["Use Pydantic", "Add authentication"]
)

team = MGXStyleTeam(config=config)

# Görev çalıştır
await team.analyze_and_plan("Create user management API")
team.approve_plan()
await team.execute()
```

---

## 📄 JSON Task Format

### Minimal Format

```json
{
  "task": "Create a REST API for user management"
}
```

### Full Format

```json
{
  "task": "Create a REST API for user management",
  "target_stack": "fastapi",
  "project_type": "api",
  "output_mode": "generate_new",
  "strict_requirements": true,
  "constraints": [
    "Use Pydantic models",
    "Add JWT authentication",
    "Include .env configuration"
  ],
  "existing_project_path": "./my-project"
}
```

### Alan Açıklamaları

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `task` | string | ✅ | Görev açıklaması |
| `target_stack` | string | ❌ | Stack ID (otomatik tahmin edilir) |
| `project_type` | string | ❌ | `api`, `webapp`, `fullstack`, `devops` |
| `output_mode` | string | ❌ | `generate_new` (default) veya `patch_existing` |
| `strict_requirements` | boolean | ❌ | FILE manifest formatı zorunlu (default: false) |
| `constraints` | array | ❌ | Ek kısıtlamalar listesi |
| `existing_project_path` | string | ❌ | Patch mode için proje yolu |

---

## 📚 Örnekler

### Örnek 1: Express TypeScript API

**Dosya:** `examples/express_api_task.json`

```json
{
  "task": "Create a simple Express TypeScript REST API with user CRUD endpoints",
  "target_stack": "express-ts",
  "project_type": "api",
  "constraints": [
    "Use TypeScript",
    "Include error handling middleware",
    "Add input validation"
  ]
}
```

**Çalıştırma:**

```bash
python -m mgx_agent.cli --json examples/express_api_task.json
```

**Beklenen Çıktı:**

```
FILE: package.json
{
  "name": "express-api",
  "scripts": {
    "dev": "ts-node-dev src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "express": "^4.18.0",
    "dotenv": "^16.0.0"
  }
}

FILE: src/server.ts
import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(express.json());

// User routes
app.get('/users', (req, res) => {
  res.json({ users: [] });
});

export default app;

FILE: tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist"
  }
}
```

---

### Örnek 2: FastAPI Backend

**Dosya:** `examples/fastapi_task.json`

```json
{
  "task": "Build a FastAPI application for user management",
  "target_stack": "fastapi",
  "project_type": "api",
  "strict_requirements": true,
  "constraints": [
    "Use Pydantic models",
    "Implement JWT authentication"
  ]
}
```

**Çalıştırma:**

```bash
python -m mgx_agent.cli --json examples/fastapi_task.json
```

**Beklenen Çıktı:**

```
FILE: app/main.py
from fastapi import FastAPI
from app.routers import users

app = FastAPI(title="User Management API")
app.include_router(users.router)

FILE: app/models.py
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    id: int
    email: EmailStr
    username: str

FILE: app/routers/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def get_users():
    return {"users": []}

FILE: requirements.txt
fastapi
uvicorn[standard]
pydantic[email]
python-jose[cryptography]
```

---

### Örnek 3: Next.js Dashboard

**Dosya:** `examples/nextjs_task.json`

```json
{
  "task": "Create a Next.js admin dashboard with user list page",
  "target_stack": "nextjs",
  "project_type": "webapp",
  "constraints": [
    "Use App Router (Next.js 13+)",
    "Server-side rendering"
  ]
}
```

**Beklenen Dosya Yapısı:**

```
app/
  page.tsx          # Ana sayfa
  users/
    page.tsx        # Kullanıcı listesi
  api/
    users/
      route.ts      # API endpoint
components/
  UserTable.tsx
package.json
next.config.js
tsconfig.json
```

---

### Örnek 4: Docker Setup

**Dosya:** `examples/docker_task.json`

```json
{
  "task": "Create Docker setup for Node.js API with PostgreSQL",
  "target_stack": "devops-docker",
  "project_type": "devops",
  "constraints": [
    "Multi-stage build",
    "Health checks"
  ]
}
```

**Beklenen Çıktı:**

```
FILE: Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY package*.json ./
RUN npm ci --only=production
CMD ["node", "dist/server.js"]

FILE: docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "3000:3000"
    depends_on:
      - postgres
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

### Örnek 5: Laravel Module (Patch Mode)

**Dosya:** `examples/laravel_task.json`

```json
{
  "task": "Add blog module to Laravel project",
  "target_stack": "laravel",
  "project_type": "api",
  "output_mode": "patch_existing",
  "existing_project_path": "./my-laravel-project",
  "constraints": [
    "Use Eloquent ORM",
    "Create migration files"
  ]
}
```

**Beklenen Değişiklikler:**

```
FILE: app/Models/Post.php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Post extends Model
{
    protected $fillable = ['title', 'content', 'author_id'];
}

FILE: app/Http/Controllers/PostController.php
<?php

namespace App\Http\Controllers;

class PostController extends Controller
{
    public function index()
    {
        return Post::all();
    }
}

FILE: database/migrations/2024_01_01_000000_create_posts_table.php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;

class CreatePostsTable extends Migration
{
    public function up()
    {
        Schema::create('posts', function (Blueprint $table) {
            $table->id();
            $table->string('title');
            $table->text('content');
            $table->timestamps();
        });
    }
}
```

---

## 🧠 Stack-Aware Actions

### AnalyzeTask Çıktısı

```
KARMAŞIKLIK: M
ÖNERİLEN_STACK: fastapi - Python REST API için optimal, async desteği
DOSYA_MANİFESTO:
- app/main.py: FastAPI app instance
- app/routers/users.py: User endpoints
- app/models.py: Pydantic models
- requirements.txt: Dependencies
- .env.example: Configuration template
TEST_STRATEJİSİ: pytest ile 5 adet test (CRUD operations + auth)
```

### WriteCode FILE Manifest Format

**Strict Mode (strict_requirements=true):**

```
FILE: src/server.ts
import express from 'express';
const app = express();

FILE: src/routes/users.ts
export const userRoutes = router();
```

**Normal Mode:**

```typescript
// Tek dosya için
import express from 'express';
const app = express();
```

### WriteTest Stack-Aware

**FastAPI (Pytest):**

```python
import pytest
from fastapi.testclient import TestClient

def test_create_user():
    client = TestClient(app)
    response = client.post("/users")
    assert response.status_code == 201
```

**Express-TS (Jest):**

```typescript
import { describe, it, expect } from '@jest/globals';
import request from 'supertest';

describe('User API', () => {
  it('should create user', async () => {
    const response = await request(app).post('/users');
    expect(response.status).toBe(201);
  });
});
```

---

## ✅ Output Validation

### Stack Structure Validation

```python
from mgx_agent.file_utils import validate_stack_structure

is_valid, warnings = validate_stack_structure("./my-project", "fastapi")

if not is_valid:
    print("⚠️ Uyarılar:", warnings)
```

### Constraint Validation

```python
from mgx_agent.file_utils import validate_output_constraints

files = {
    "package.json": '{"scripts": {"dev": "pnpm dev"}}',
    ".env.example": "DATABASE_URL=",
}

is_valid, errors = validate_output_constraints(
    files,
    stack_id="express-ts",
    constraints=["Use pnpm", "Include env vars"]
)
```

**Constraint Kuralları:**

| Constraint | Kontrol |
|------------|---------|
| "Use pnpm" | package.json'da `pnpm` aranır |
| "No extra libraries" | Bağımlılık sayısı kontrolü |
| "Must include env vars" | `.env.example` dosyası varlığı |
| "Use minimal dependencies" | Toplam dependency sayısı < 20 |

---

## 🛡️ Safe File Operations

### Otomatik Backup

```python
from mgx_agent.file_utils import safe_write_file

# Mevcut dosyayı yedekler ve yazar
safe_write_file("src/main.py", "# New code", create_backup_flag=True)

# Yedek: src/main.py.20240101_120000.bak
```

### FILE Manifest Parser

```python
from mgx_agent.file_utils import parse_file_manifest

manifest = """
FILE: package.json
{"name": "test"}

FILE: src/index.ts
console.log("hello");
"""

files = parse_file_manifest(manifest)
# {'package.json': '{"name": "test"}', 'src/index.ts': 'console.log("hello");'}
```

---

## 🔧 TeamConfig Stack Ayarları

```python
from mgx_agent.config import TeamConfig

config = TeamConfig(
    # Stack ayarları
    target_stack="nextjs",           # Stack seçimi
    project_type="webapp",           # Proje tipi
    output_mode="generate_new",      # Mod
    strict_requirements=True,        # FILE manifest zorunlu
    constraints=["Use App Router"],  # Kısıtlamalar
    existing_project_path="./app",   # Patch mode için
    
    # Mevcut ayarlar (hala destekleniyor)
    max_rounds=5,
    human_reviewer=False,
    enable_caching=True,
)
```

---

## ⚠️ Sınırlamalar

### Şu An Desteklenmeyen
- ❌ Multi-tenant SaaS özellikleri
- ❌ Kubernetes configuration (istenirse eklenebilir)
- ❌ Her dil/framework (sadece liste alındaki stack'ler)
- ❌ Otomatik patch conflict resolution

### Bilinen Sorunlar
- **Patch Mode**: Unified diff desteği için `patch_ng` kütüphanesi gerekli
  - Yoksa `.mgx_new` dosyası oluşturulur (manuel merge gerekir)
- **Large Projects**: Çok büyük projelerde dosya sayısı sınırı olabilir
- **LLM Output**: Bazen FILE manifest formatına uyulmayabilir
  - Validation ve retry mekanizması devreye girer

---

## 🧪 Test Çalıştırma

### Tüm Web Stack Testleri

```bash
pytest tests/test_web_stack_support.py -v
```

### Spesifik Test Grubu

```bash
# Stack specs testleri
pytest tests/test_web_stack_support.py::TestStackSpecs -v

# File manifest testleri
pytest tests/test_web_stack_support.py::TestFileManifestParser -v

# Validation testleri
pytest tests/test_web_stack_support.py::TestOutputValidation -v
```

---

## 📊 Başarı Metrikleri

### Hedefler ✅

- ✅ 10 stack desteği (5 backend, 3 frontend, 2 devops)
- ✅ JSON input contract
- ✅ Stack-aware actions (5 action güncellendi)
- ✅ Output validation + guardrails
- ✅ 28+ integration test
- ✅ FILE manifest parser
- ✅ Safe file writer with backup
- ✅ Backward compatibility

### Test Coverage

```
tests/test_web_stack_support.py::TestStackSpecs                 PASSED [ 10%]
tests/test_web_stack_support.py::TestFileManifestParser         PASSED [ 20%]
tests/test_web_stack_support.py::TestOutputValidation           PASSED [ 40%]
tests/test_web_stack_support.py::TestSafeFileWriter             PASSED [ 60%]
tests/test_web_stack_support.py::TestStackStructureValidation   PASSED [ 70%]
tests/test_web_stack_support.py::TestTeamConfigStackSupport     PASSED [ 80%]
tests/test_web_stack_support.py::TestJSONInputParsing           PASSED [ 90%]
tests/test_web_stack_support.py::TestBackwardCompatibility      PASSED [100%]
```

---

## 🚀 Gelecek Geliştirmeler

### v2.0 (Planlanıyor)
- [ ] Vue 2 backward compatibility
- [ ] Ruby on Rails stack
- [ ] Go (Gin/Echo) stack
- [ ] Rust (Actix/Rocket) stack
- [ ] Automatic conflict resolution (patch mode)
- [ ] Multi-file diff preview
- [ ] Stack migration tools (örn: Express → NestJS)

### v2.1 (Planlanıyor)
- [ ] Kubernetes manifests (Helm charts)
- [ ] Terraform templates
- [ ] AWS CDK templates
- [ ] CI/CD: GitLab CI, CircleCI, Jenkins

---

## 📞 Destek

Sorunlar için GitHub Issues açabilir veya [IMPROVEMENT_GUIDE.md](../IMPROVEMENT_GUIDE.md) dökümanına bakabilirsiniz.

---

**Web Stack Support - Production Ready! 🎉**

</details>

---

## Appendix F: Output validation guardrails (stack-specific rules)

<details>
<summary>Expand Appendix F</summary>

# Output Validation Guardrails (Phase 8.1)

**Production-stable validation for generated code output**

## Overview

The Output Validation Guardrails system ensures that code generated by the MGX Agent meets quality standards, follows stack conventions, and complies with user constraints. This validation layer acts as a safety net to catch common mistakes before they reach production.

### Key Features

✅ **Stack-Specific Validation**: Enforces file layout requirements for each supported stack (Express TS, FastAPI, Laravel, Next.js, Vue+Vite, etc.)

✅ **Forbidden Library Detection**: Prevents mixing incompatible technologies (e.g., Django imports in FastAPI code)

✅ **FILE Manifest Compliance**: Validates strict format requirements for file-based output

✅ **Path Security**: Blocks path traversal attacks and dangerous file system access

✅ **Constraint Enforcement**: Validates user-provided constraints like "no extra libraries"

✅ **Auto-Revision**: Automatically retries generation with error feedback when validation fails

## Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  WriteCode Action                                            │
│                                                              │
│  1. Generate code output                                    │
│  2. Run validate_output_constraints()                       │
│  3. Validation passed? ✅ → Return output                   │
│     Validation failed? ❌ → Build revision prompt           │
│  4. Retry with validation errors (max 2 retries)           │
│  5. Still fails? → Mark as NEEDS_INFO                       │
└─────────────────────────────────────────────────────────────┘
```

## Validation Rules by Stack

### Express TypeScript (`express-ts`)

**Required Files:**
- `package.json` - Node.js dependencies
- `tsconfig.json` - TypeScript configuration
- `src/` directory - Source code

**Required Commands:**
- `npm run dev`
- `npm run build`
- `npm test`

**Forbidden Files:**
- `requirements.txt` (Python)
- `composer.json` (PHP)
- `pyproject.toml` (Python)
- `Gemfile` (Ruby)

**Forbidden Imports:**
- `from django` (Python framework)
- `from flask` (Python framework)
- `import laravel` (PHP framework)
- `require('laravel')` (PHP framework)

**Example Valid Output:**
```
FILE: package.json
{
  "name": "my-api",
  "dependencies": {
    "express": "^4.18.0",
    "dotenv": "^16.0.0"
  },
  "scripts": {
    "dev": "ts-node src/index.ts",
    "build": "tsc",
    "test": "jest"
  }
}

FILE: tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist"
  }
}

FILE: src/index.ts
import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(express.json());

app.get('/', (req, res) => {
  res.json({ message: 'Hello World' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

---

### FastAPI (`fastapi`)

**Required Files:**
- `main.py` - Main application entry
- `requirements.txt` OR `pyproject.toml` - Python dependencies
- `app/` directory - Application code

**Required Commands:**
- `uvicorn` (for running)
- `pytest` (for testing)

**Forbidden Files:**
- `composer.json` (PHP)
- `Gemfile` (Ruby)

**Forbidden Imports:**
- `import express` (Node.js)
- `require(` (Node.js)
- `use Illuminate` (Laravel/PHP)
- `from django` (Different Python framework)

**Example Valid Output:**
```
FILE: main.py
from fastapi import FastAPI
from app.routers import users

app = FastAPI(title="My API")

app.include_router(users.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to My API"}

FILE: requirements.txt
fastapi==0.104.0
uvicorn[standard]==0.24.0
pydantic==2.4.0
python-dotenv==1.0.0

FILE: app/__init__.py

FILE: app/routers/users.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])

class User(BaseModel):
    id: int
    name: str
    email: str

@router.get("/{user_id}")
def get_user(user_id: int):
    return User(id=user_id, name="John Doe", email="john@example.com")
```

---

### Laravel (`laravel`)

**Required Files:**
- `composer.json` - PHP dependencies
- `.env.example` - Environment variables template
- `app/` directory - Application logic
- `routes/` directory - Route definitions

**Required Commands:**
- `php artisan serve`
- `php artisan test`
- `composer test`

**Forbidden Files:**
- `requirements.txt` (Python)
- `pyproject.toml` (Python)
- `Gemfile` (Ruby)

**Forbidden Imports:**
- `import express` (Node.js)
- `from fastapi` (Python)
- `from django` (Python)
- `import React` (Frontend)

**Example Valid Output:**
```
FILE: composer.json
{
    "name": "my-app",
    "require": {
        "php": "^8.1",
        "laravel/framework": "^10.0"
    }
}

FILE: .env.example
APP_NAME=MyApp
APP_ENV=local
APP_KEY=
DB_CONNECTION=mysql

FILE: routes/web.php
<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\UserController;

Route::get('/', function () {
    return view('welcome');
});

Route::resource('users', UserController::class);

FILE: app/Http/Controllers/UserController.php
<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class UserController extends Controller
{
    public function index()
    {
        return response()->json(['message' => 'Users list']);
    }
}
```

---

### Next.js (`nextjs`)

**Required Files:**
- `package.json` - Node.js dependencies
- `next.config.js` - Next.js configuration
- `tsconfig.json` - TypeScript configuration
- `app/` OR `pages/` directory - Routes

**Required Commands:**
- `npm run dev`
- `npm run build`

**Forbidden Files:**
- `vite.config` (Different bundler)
- `requirements.txt` (Python)
- `composer.json` (PHP)

**Forbidden Imports:**
- `from 'react-router'` (Next.js has built-in routing)
- `createBrowserRouter` (Use Next.js routing)
- `from 'vite'` (Different bundler)

---

### Vue + Vite (`vue-vite`)

**Required Files:**
- `package.json` - Node.js dependencies
- `vite.config.ts` - Vite configuration
- `src/` directory - Source code

**Required Commands:**
- `npm run dev`
- `npm run build`

**Forbidden Files:**
- `next.config` (Next.js specific)
- `nuxt.config` (Nuxt.js specific)
- `requirements.txt` (Python)

**Forbidden Imports:**
- `from 'next'` (Different framework)
- `import React` (Different framework)
- `from 'react'` (Different framework)

---

## Forbidden Libraries Scanner

### How It Works

The scanner detects forbidden import/require statements using regex patterns. It's **context-aware** and ignores:

- Comments (lines starting with `#`, `//`, `/*`)
- String literals (inside quotes)

### Examples

**❌ FAIL - Express import in FastAPI:**
```python
from fastapi import FastAPI
import express  # ❌ Forbidden in Python

app = FastAPI()
```
**Error:** `Forbidden import/usage in stack 'fastapi': 'import express'`

---

**✅ PASS - Comment is OK:**
```python
from fastapi import FastAPI
# We could use express but we're using FastAPI
# import express would be wrong

app = FastAPI()
```

---

**❌ FAIL - Django in FastAPI:**
```python
from fastapi import FastAPI
from django.http import HttpResponse  # ❌ Wrong framework

app = FastAPI()
```
**Error:** `Forbidden import/usage in stack 'fastapi': 'from django'`

---

## Constraint Enforcement

### User Constraint: "No Extra Libraries"

When a user specifies the constraint `"no extra libraries"`, the validator checks that only **common dependencies** and **built-in modules** are used.

**FastAPI Common Dependencies:**
- `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`

**Python Built-ins (Always Allowed):**
- `os`, `sys`, `json`, `re`, `typing`, `dataclasses`, `datetime`, `pathlib`

**Example - FAIL:**
```python
from fastapi import FastAPI
import requests  # ❌ Not in common deps
import numpy as np  # ❌ Not in common deps

app = FastAPI()
```
**Error:** `Constraint 'no extra libraries': Found import 'requests' which is not in common dependencies`

**Example - PASS:**
```python
from fastapi import FastAPI
from pydantic import BaseModel
import os
import json

app = FastAPI()
```

---

## FILE Manifest Compliance

### Strict Mode vs Normal Mode

#### Strict Mode (`strict_mode=True`)

**Requirements:**
- Every line must be inside a FILE block or empty
- No prose/explanations outside FILE blocks
- FILE: prefix must be exact
- No duplicate file definitions

**Example - FAIL:**
```
Here's my solution:  ❌ Prose outside FILE block

FILE: main.py
def hello():
    pass

This is great!  ❌ Prose outside FILE block
```

**Example - PASS:**
```
FILE: main.py
def hello():
    pass

FILE: tests/test_main.py
def test_hello():
    assert hello() is not None
```

#### Normal Mode (`strict_mode=False`)

**Allows:**
- Explanations before/after FILE blocks
- Traditional code blocks (```python)
- More lenient parsing

**Example - PASS:**
```
Here's my FastAPI implementation:

FILE: main.py
from fastapi import FastAPI
app = FastAPI()

Or you can use:

```python
def alternative():
    pass
```

This implements the requested feature.
```

---

## Path Security Validation

### Path Traversal Prevention

**❌ FAIL - Path Traversal:**
```
FILE: ../../../etc/passwd
FILE: ../../config/secrets.yml
```
**Error:** `Path traversal detected: ../../../etc/passwd`

**❌ FAIL - Dangerous Absolute Paths:**
```
FILE: /etc/shadow
FILE: /var/log/auth.log
```
**Error:** `Dangerous absolute path: /etc/shadow`

**✅ PASS - Safe Relative Paths:**
```
FILE: src/main.py
FILE: tests/test_main.py
FILE: config/settings.json
```

---

## Duplicate File Detection

**❌ FAIL:**
```
FILE: main.py
def hello():
    pass

FILE: routes.py
def route():
    pass

FILE: main.py  ❌ Duplicate!
def goodbye():
    pass
```
**Error:** `Duplicate file definition: main.py (defined 2 times)`

---

## Mixed Stack Detection

The validator warns when multiple stack indicators are present (e.g., both `package.json` and `requirements.txt`).

**⚠️ WARNING:**
```
FILE: package.json
{
  "name": "mixed"
}

FILE: requirements.txt
fastapi==0.104.0

FILE: src/index.ts
import express from 'express';

FILE: main.py
from fastapi import FastAPI
```
**Warning:** `Mixed stack detected: Expected 'nodejs' (based on express-ts) but also found indicators for: python. This might be intentional (monorepo) or a mistake.`

---

## Auto-Revision on Validation Failure

When validation fails, WriteCode automatically:

1. Logs detailed validation errors
2. Builds a revision prompt with all errors
3. Retries generation (max 2 retries)
4. Returns output with NEEDS_INFO status if still fails

### Example Revision Prompt

```
⚠️ OUTPUT VALIDATION FAILED

The previous output did not pass validation checks. Please fix the following issues:

ERRORS (MUST FIX):
- Stack 'express-ts' requires file: package.json
- Stack 'express-ts' requires file: tsconfig.json
- Forbidden import/usage in stack 'express-ts': 'from django'

WARNINGS (RECOMMENDED TO FIX):
- Stack 'express-ts' typically uses command: npm run dev (not found in output)

Original Task: Create an Express TypeScript REST API with user authentication

Please regenerate the output addressing ALL validation errors above.
Ensure:
1. All required files for the stack are present
2. No forbidden libraries or files are used
3. FILE manifest format is correct (if required)
4. All file paths are valid and secure
5. No duplicate file definitions

Generate the complete, corrected output now.
```

---

## How to Extend Validation for New Stacks

### 1. Add Stack Specification

In `mgx_agent/stack_specs.py`:
```python
STACK_SPECS["my-new-stack"] = StackSpec(
    stack_id="my-new-stack",
    name="My New Framework",
    category=StackCategory.BACKEND,
    language="go",
    test_framework="go test",
    package_manager="go mod",
    # ... other fields
)
```

### 2. Add Validation Rules

In `mgx_agent/guardrails.py`:
```python
STACK_VALIDATION_RULES["my-new-stack"] = {
    "required_files": ["go.mod", "main.go"],
    "required_dirs": ["cmd/", "pkg/"],
    "forbidden_files": ["package.json", "requirements.txt"],
    "required_commands": ["go run", "go test", "go build"],
    "forbidden_imports": [
        r"import\s+express",
        r"from\s+fastapi",
    ],
}
```

### 3. Add Tests

In `tests/unit/test_output_validation.py`:
```python
def test_my_new_stack_required_files():
    files = ["README.md"]
    errors = StackValidator.validate_required_files(files, "my-new-stack")
    assert len(errors) >= 1
    assert any("go.mod" in e for e in errors)
```

---

## Troubleshooting

### "Why did my code fail validation?"

#### Error: "No FILE: blocks found in strict mode"

**Cause:** Strict mode requires FILE manifest format.

**Fix:** Use FILE: prefix for each file:
```
FILE: main.py
<content>

FILE: tests/test_main.py
<content>
```

---

#### Error: "Stack 'express-ts' requires file: package.json"

**Cause:** Required file is missing for the selected stack.

**Fix:** Add the required file:
```
FILE: package.json
{
  "name": "my-app",
  "dependencies": {
    "express": "^4.18.0"
  }
}
```

---

#### Error: "Forbidden import/usage in stack 'fastapi': 'import express'"

**Cause:** Mixing incompatible technologies.

**Fix:** Remove the forbidden import and use the correct stack's libraries:
```python
# ❌ Wrong
from fastapi import FastAPI
import express

# ✅ Correct
from fastapi import FastAPI
```

---

#### Error: "Path traversal detected: ../../../etc/passwd"

**Cause:** Dangerous file path.

**Fix:** Use safe relative paths within project:
```
# ❌ Wrong
FILE: ../../../etc/passwd

# ✅ Correct
FILE: config/settings.json
```

---

#### Error: "Duplicate file definition: main.py"

**Cause:** Same file defined multiple times.

**Fix:** Merge duplicate files or remove duplicates.

---

#### Warning: "Mixed stack detected"

**Cause:** Multiple stack indicators found (e.g., both package.json and requirements.txt).

**Context:** This might be intentional (monorepo) or a mistake.

**Action:** If intentional, ignore warning. If mistake, remove files from the wrong stack.

---

## Configuration

### Disable Validation (Not Recommended)

```python
from mgx_agent.actions import WriteCode

action = WriteCode()
output = await action.run(
    instruction="Create an API",
    enable_validation=False  # Disable validation
)
```

### Adjust Max Retries

```python
output = await action.run(
    instruction="Create an API",
    max_validation_retries=3  # Default is 2
)
```

### Use Strict Mode

```python
output = await action.run(
    instruction="Create an API",
    strict_mode=True  # Enforce FILE-only format
)
```

---

## Best Practices

1. **Always Enable Validation in Production**: Catches mistakes early
2. **Use Strict Mode for Multi-File Projects**: Ensures clean FILE manifest format
3. **Provide Clear Constraints**: Be specific about requirements (e.g., "no extra libraries")
4. **Review Warnings**: Even if validation passes, warnings may indicate issues
5. **Test New Stacks Thoroughly**: Add comprehensive validation rules when adding new stacks

---

## API Reference

### `validate_output_constraints()`

```python
def validate_output_constraints(
    generated_output: str,
    stack_spec: Optional[StackSpec] = None,
    constraints: Optional[List[str]] = None,
    strict_mode: bool = False,
) -> ValidationResult:
    """
    Validate generated output against stack specifications and constraints.
    
    Args:
        generated_output: Complete FILE manifest or code output
        stack_spec: Stack specification (from Phase 7)
        constraints: User-provided constraints (e.g., ["no extra libraries"])
        strict_mode: If True, enforce FILE-only format, no prose allowed
    
    Returns:
        ValidationResult with is_valid, errors, and warnings
    """
```

### `ValidationResult`

```python
class ValidationResult(BaseModel):
    is_valid: bool  # Whether output passed all validations
    errors: List[str]  # Critical errors (must fix)
    warnings: List[str]  # Non-critical warnings
    
    def add_error(self, error: str)
    def add_warning(self, warning: str)
    def summary(self) -> str  # Human-readable summary
```

### `build_revision_prompt()`

```python
def build_revision_prompt(
    validation_result: ValidationResult,
    original_task: str
) -> str:
    """
    Build a revision prompt based on validation errors.
    
    Returns:
        Revision prompt string for LLM
    """
```

---

## Summary

The Output Validation Guardrails system provides:

- ✅ **Quality Assurance**: Catches common mistakes automatically
- ✅ **Stack Compliance**: Ensures generated code follows conventions
- ✅ **Security**: Prevents dangerous file system operations
- ✅ **Auto-Correction**: Retries with feedback when validation fails
- ✅ **Extensibility**: Easy to add validation for new stacks
- ✅ **Clear Feedback**: Detailed error messages help users understand issues

**Result:** Production-stable code generation with confidence! 🚀

</details>

---

## Appendix G: Patch mode + diff format (safe patch/diff writer)

<details>
<summary>Expand Appendix G</summary>

# Patch Mode - Safe Diff Application

## Overview

Patch Mode allows MGX Agent to safely apply unified diffs to existing projects with guaranteed backups and fallback mechanisms. This mode is essential for modifying existing codebases without risking data loss.

## Features

- ✅ **Automatic Backups**: Every file modification creates a timestamped backup
- ✅ **Line Drift Detection**: Warns when diff line numbers don't match file
- ✅ **Fallback Mechanism**: Creates `.mgx_new` files on failure for manual review
- ✅ **Transaction Support**: All-or-nothing or best-effort patch application
- ✅ **Dry-Run Mode**: Test patches without modifying files
- ✅ **Comprehensive Logging**: Detailed logs of what succeeded and failed

## Patch Mode vs. Generate New Mode

| Feature | Patch Mode | Generate New Mode |
|---------|------------|-------------------|
| Use Case | Modify existing files | Create new project |
| Safety | Backups + rollback | N/A |
| Line Numbers | Critical | Not needed |
| Conflict Handling | Fallback to .mgx_new | N/A |
| Best For | Bug fixes, features | Greenfield projects |

## Usage

### Basic Patch Application

```python
from mgx_agent.diff_writer import apply_diff

# Apply a single diff
diff_str = """--- a/src/app.py
+++ b/src/app.py
@@ -10,5 +10,7 @@
 def hello():
-    print("Hello")
+    print("Hello World")
+    return True
"""

result = apply_diff(
    file_path="src/app.py",
    diff=diff_str,
    backup=True  # Create backup (default)
)

if result.success:
    print(f"✅ Patch applied successfully")
    print(f"Backup: {result.backup_file}")
else:
    print(f"❌ Patch failed: {result.message}")
    print(f"Review: {result.new_file_created}")
    print(f"Log: {result.log_file}")
```

### Multi-File Patch Set

```python
from mgx_agent.diff_writer import apply_patch_set

diffs = [
    ("src/app.py", diff1),
    ("src/utils.py", diff2),
    ("tests/test_app.py", diff3)
]

# All-or-nothing mode (rollback on any failure)
result = apply_patch_set(
    diffs=diffs,
    project_path="/path/to/project",
    mode="all_or_nothing"
)

# Best-effort mode (apply what you can)
result = apply_patch_set(
    diffs=diffs,
    project_path="/path/to/project",
    mode="best_effort"
)

print(f"Applied: {result.applied_count}/{len(diffs)}")
print(f"Failed: {result.failed_count}")
```

### Dry-Run Mode

```python
# Test without modifying files
result = apply_diff(
    file_path="src/app.py",
    diff=diff_str,
    dry_run=True
)

print(f"Would apply: {result.message}")
for warning in result.line_drift_warnings:
    print(f"⚠️ {warning}")
```

## Backup Management

### List Backups

```python
from mgx_agent.file_recovery import list_backups

backups = list_backups("/path/to/project")

for backup in backups:
    print(f"Original: {backup.original_file}")
    print(f"Backup: {backup.backup_file}")
    print(f"Timestamp: {backup.timestamp}")
    print(f"Size: {backup.size_bytes} bytes")
```

### Restore from Backup

```python
from mgx_agent.file_recovery import restore_from_backup

# Restore from latest backup
success = restore_from_backup("src/app.py")

# Restore from specific timestamp
success = restore_from_backup(
    "src/app.py",
    backup_timestamp="20250114_153022"
)
```

### Cleanup Old Backups

```python
from mgx_agent.file_recovery import cleanup_old_backups

# Keep only 5 latest backups per file
removed = cleanup_old_backups(
    project_path="/path/to/project",
    keep_latest=5
)

print(f"Removed {removed} old backups")
```

## Handling .mgx_new Files

When a patch fails to apply, MGX Agent creates several files for manual review:

- **`file.mgx_new`**: Attempted changes that couldn't be applied
- **`file.mgx_apply_log.txt`**: Detailed log of what went wrong
- **`file.mgx_failed_diff.txt`**: The diff that failed

### Manual Review Workflow

1. **Review the Log**:
   ```bash
   cat src/app.py.mgx_apply_log.txt
   ```

2. **Compare Files**:
   ```bash
   diff src/app.py src/app.py.mgx_new
   ```

3. **Decide**:
   - **Accept Changes**: `mv src/app.py.mgx_new src/app.py`
   - **Reject Changes**: `rm src/app.py.mgx_new`
   - **Manual Merge**: Use editor to selectively apply changes

4. **Cleanup**:
   ```bash
   rm src/app.py.mgx_apply_log.txt
   rm src/app.py.mgx_failed_diff.txt
   ```

## Line Drift Detection

Patch Mode detects when diff line numbers don't match the current file state:

```python
result = apply_diff(file_path, diff)

for warning in result.line_drift_warnings:
    print(f"⚠️ {warning}")
```

**Tolerance**: Drift > 2 lines triggers a warning but doesn't block application.

**What to do**:
- Check if file was modified since diff was generated
- Regenerate diff against current file state
- Manually review `.mgx_new` file

## Integration with TaskExecutor

Patch mode is automatically used when `output_mode == 'patch_existing'`:

```python
# In TaskExecutor.execute_task()
if output_mode == 'patch_existing':
    # Extract diffs from generated output
    diffs = extract_diffs_from_output(result)
    
    # Apply patch set
    patch_result = apply_patch_set(
        diffs=diffs,
        project_path=project_path,
        mode="best_effort"
    )
    
    if not patch_result.success:
        # Emit event with .mgx_new file references
        await broadcaster.publish(PatchApplyFailedEvent(
            task_id=task_id,
            run_id=run_id,
            data={
                "failed_count": patch_result.failed_count,
                "results": patch_result.results
            }
        ))
```

## Safety Guarantees

1. **Non-Destructive**: Original files are never lost
2. **Atomic Operations**: File modification is atomic (write to temp, then rename)
3. **Rollback on Failure**: All-or-nothing mode rolls back all changes
4. **Manual Fallback**: Failed changes written to `.mgx_new` for review

## Troubleshooting

### "Patch apply failed: No hunks found"

**Cause**: Invalid diff format

**Solution**: Check diff syntax, ensure it follows unified diff format

### "Line drift: hunk starts at line 100, but file has only 50 lines"

**Cause**: File was modified since diff was generated

**Solution**: Regenerate diff against current file state

### "File does not exist for modification"

**Cause**: Diff tries to modify non-existent file

**Solution**: Change operation to CREATE or ensure file exists

### ".mgx_new files accumulating"

**Cause**: Failed patches not cleaned up

**Solution**: Use `cleanup_mgx_artifacts()` to remove all MGX files

```python
from mgx_agent.file_recovery import cleanup_mgx_artifacts

removed = cleanup_mgx_artifacts("/path/to/project")
```

## Best Practices

1. **Always Enable Backups**: Never disable backup creation in production
2. **Use Dry-Run First**: Test patches before applying to critical files
3. **Monitor Line Drift**: Regenerate diffs if drift warnings appear
4. **Regular Cleanup**: Remove old backups periodically (keep 5-10 latest)
5. **Review .mgx_new Files**: Don't ignore failed patches, review manually
6. **Transaction Mode for Critical**: Use "all_or_nothing" for production deployments

## Example: Complete Workflow

```python
from mgx_agent.diff_writer import apply_patch_set
from mgx_agent.file_recovery import list_backups, cleanup_old_backups

# 1. Apply patches
diffs = [
    ("src/app.py", diff1),
    ("src/utils.py", diff2)
]

result = apply_patch_set(
    diffs=diffs,
    project_path="/path/to/project",
    mode="all_or_nothing"
)

# 2. Handle results
if result.success:
    print("✅ All patches applied successfully")
    
    # List backups
    backups = list_backups("/path/to/project")
    print(f"Created {len(backups)} backups")
else:
    print(f"❌ {result.failed_count} patches failed")
    
    # Review failures
    for r in result.results:
        if not r.success:
            print(f"Failed: {r.file_path}")
            print(f"Review: {r.new_file_created}")
            print(f"Log: {r.log_file}")

# 3. Cleanup old backups
removed = cleanup_old_backups("/path/to/project", keep_latest=5)
print(f"Cleaned up {removed} old backups")
```

## Related Documentation

- [DIFF_FORMAT.md](./DIFF_FORMAT.md) - Unified diff format specification
- [OUTPUT_VALIDATION.md](./OUTPUT_VALIDATION.md) - Output validation guardrails
- [GIT_AWARE_EXECUTION.md](./GIT_AWARE_EXECUTION.md) - Git integration

---

### Unified diff format (accepted input contract)

# Unified Diff Format Specification

## Overview

This document describes the unified diff format supported by MGX Agent's patch system. Understanding this format is essential for generating diffs that can be safely applied to existing projects.

## Basic Format

A unified diff consists of:
1. **File headers** (`---` and `+++` lines)
2. **Hunk headers** (`@@` lines)
3. **Hunk content** (context, additions, deletions)

## Format Components

### File Headers

```diff
--- a/path/to/original/file.ext
+++ b/path/to/modified/file.ext
```

- `--- a/`: Original file path (prefix `a/` is conventional but optional)
- `+++ b/`: Modified file path (prefix `b/` is conventional but optional)

### Hunk Header

```diff
@@ -10,5 +10,7 @@
```

Format: `@@ -<start>,<count> +<start>,<count> @@`

- `-10,5`: Original file starts at line 10, shows 5 lines
- `+10,7`: Modified file starts at line 10, shows 7 lines
- Difference (7-5=2): Net 2 lines added

### Hunk Content

```diff
 context line (unchanged)
-removed line
+added line
 another context line
```

- Lines starting with ` ` (space): Context (unchanged)
- Lines starting with `-`: Removed from original
- Lines starting with `+`: Added in modified

## Operations

### 1. File Modification

Modify an existing file by adding/removing/changing lines.

**Example: Add logging to a function**

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -10,5 +10,8 @@
 def process_data(data):
+    import logging
+    logging.info(f"Processing {len(data)} items")
     result = []
     for item in data:
         result.append(item * 2)
     return result
```

**Result**: Adds 2 lines (import and logging) to the function.

### 2. File Creation

Create a new file from scratch.

**Format**:
```diff
--- /dev/null
+++ b/path/to/new/file.ext
@@ -0,0 +1,N @@
+line 1 of new file
+line 2 of new file
+...
+line N of new file
```

**Example: Create a new utility module**

```diff
--- /dev/null
+++ b/src/utils/helper.py
@@ -0,0 +1,5 @@
+def format_name(name):
+    """Format a name to title case."""
+    return name.strip().title()
+
+# End of file
```

### 3. File Deletion

Delete an existing file.

**Format**:
```diff
--- a/path/to/file.ext
+++ /dev/null
```

**Example: Remove deprecated module**

```diff
--- a/src/deprecated/old_utils.py
+++ /dev/null
```

**Note**: No hunk content needed for deletion.

## Multiple Hunks

Multiple hunks in the same file are separated by new `@@` headers.

**Example: Modify two separate sections**

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -5,3 +5,4 @@
 import os
 import sys
+import logging

@@ -15,2 +16,3 @@
 def main():
+    logging.basicConfig(level=logging.INFO)
     run_app()
```

## Context Lines

Context lines help identify where changes should be applied:

- **Minimum**: 3 lines of context before and after changes
- **Purpose**: Uniquely identify location in file
- **Line Drift**: More context = better drift detection

**Example with context**

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -10,7 +10,8 @@
 # Context before
 def calculate(x, y):
     result = x + y
-    return result
+    # Added validation
+    return result if result > 0 else 0
 # Context after
```

## Advanced Patterns

### Replace Multiple Lines

```diff
--- a/config.py
+++ b/config.py
@@ -5,4 +5,3 @@
 CONFIG = {
-    'host': 'localhost',
-    'port': 8080,
+    'server': 'localhost:8080',
 }
```

**Result**: Replaces 2 lines with 1 line (net -1 line).

### Insert Block of Code

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -20,0 +21,5 @@
+def new_function():
+    """New utility function."""
+    pass
+
+
```

**Note**: `@@ -20,0 +21,5 @@` means insert at line 21 (after line 20).

### Modify Multiple Files

Separate diffs for different files with blank line:

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -10,1 +10,2 @@
 import sys
+import logging

--- a/src/utils.py
+++ b/src/utils.py
@@ -5,1 +5,2 @@
 def helper():
+    logging.info("Called helper")
     pass
```

## How TEM Agent Should Format Diffs

When generating diffs, TEM Agent should:

1. **Use Standard Format**: Follow unified diff format exactly
2. **Include Context**: Minimum 3 lines before/after changes
3. **Use Relative Paths**: Paths relative to project root
4. **One Operation Per Diff**: Don't mix create/modify/delete in same diff
5. **Clear Intent**: Make it obvious what changed and why

### Good Diff Example

```diff
--- a/src/middleware/auth.py
+++ b/src/middleware/auth.py
@@ -15,6 +15,8 @@
 def authenticate_user(token):
     """Authenticate user by token."""
+    if not token:
+        raise ValueError("Token is required")
+    
     user = decode_token(token)
     if not user:
         raise AuthenticationError("Invalid token")
```

**Why Good**:
- Clear context (function definition)
- Obvious change (added validation)
- Proper formatting (spaces, indentation)

### Bad Diff Example

```diff
--- a/src/middleware/auth.py
+++ b/src/middleware/auth.py
@@ -15,1 +15,2 @@
+    if not token:
+        raise ValueError("Token is required")
```

**Why Bad**:
- No context (can't determine where to insert)
- Missing surrounding code
- Ambiguous location

## Line Number Handling

### Absolute Line Numbers

Line numbers in hunk headers are **absolute** (1-based):

```diff
@@ -10,5 +10,7 @@
```

- Original file: lines 10-14 (5 lines)
- Modified file: lines 10-16 (7 lines)

### Sequential Application

When applying multiple hunks, line numbers adjust after each hunk:

```diff
# Hunk 1: Insert at line 10
@@ -10,0 +10,2 @@
+new line 1
+new line 2

# Hunk 2: Line numbers shifted by +2
@@ -20,1 +22,1 @@
-old line
+new line
```

**Note**: Second hunk line numbers account for first hunk's changes.

## Special Cases

### Empty File Creation

```diff
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,1 @@
+# Empty file with comment
```

### Complete File Replacement

```diff
--- a/old_file.py
+++ b/new_file.py
@@ -1,5 +0,0 @@
-old line 1
-old line 2
-old line 3
-old line 4
-old line 5
@@ -0,0 +1,3 @@
+new line 1
+new line 2
+new line 3
```

**Note**: Remove all old content, then add new content.

### Binary Files

Binary files are detected but not supported:

```diff
--- a/image.png
+++ b/image.png
Binary files differ
```

**MGX Behavior**: Skip with warning, don't corrupt binary files.

## Diff Generation Tips

### Use Git

```bash
# Single file
git diff src/app.py > app.patch

# Multiple files
git diff src/ > changes.patch

# Staged changes
git diff --staged > staged.patch
```

### Use Diff Command

```bash
# Single file
diff -u original.py modified.py > file.patch

# Directory
diff -ur original_dir/ modified_dir/ > dir.patch
```

### Python Generation

```python
import difflib

with open('original.py') as f:
    original = f.readlines()

with open('modified.py') as f:
    modified = f.readlines()

diff = difflib.unified_diff(
    original,
    modified,
    fromfile='a/original.py',
    tofile='b/modified.py',
    lineterm=''
)

print('\n'.join(diff))
```

## Validation

MGX Agent validates diffs before applying:

1. **Syntax Check**: Valid unified diff format
2. **Path Security**: No path traversal (`../`, `/etc/`)
3. **File Existence**: Modification target exists
4. **Line Bounds**: Line numbers within file range
5. **Context Match**: Context lines match file content

## Common Errors

### Missing File Headers

```diff
@@ -10,1 +10,2 @@
 line 1
+line 2
```

**Fix**: Add `---` and `+++` headers.

### Wrong Line Numbers

```diff
@@ -1000,2 +1000,3 @@
 line at position 1000
```

**Fix**: Ensure line numbers match actual file.

### Missing Context

```diff
@@ -10,0 +10,1 @@
+new line
```

**Fix**: Add at least 3 lines of context before/after.

### Mixed Operations

```diff
--- /dev/null
+++ b/new_file.py
@@ -10,1 +10,2 @@
```

**Fix**: Don't mix create with modify hunks.

## Testing Diffs

Before applying to production:

```python
from mgx_agent.diff_writer import apply_diff

# Dry-run test
result = apply_diff(
    file_path="src/app.py",
    diff=diff_string,
    dry_run=True
)

if result.success:
    print("✅ Diff is valid")
else:
    print(f"❌ Error: {result.message}")
```

## Related Documentation

- [PATCH_MODE.md](./PATCH_MODE.md) - Safe patch application
- [OUTPUT_VALIDATION.md](./OUTPUT_VALIDATION.md) - Output validation

</details>

---

## Appendix H: Code formatting + pre-commit templates

<details>
<summary>Expand Appendix H</summary>

# Code Formatting & Pre-commit Hooks Guide

## Overview

This guide covers code formatting, style standardization, and pre-commit hook configuration for MGX Agent projects across all supported stacks.

**Key Goals:**
- Ensure consistent code style across projects
- Prevent unformatted code from being committed
- Reduce manual code review friction
- Support multiple programming languages and frameworks

---

## Formatter Configuration per Stack

### Python (FastAPI, Backend)

**Formatters:**
- **black** - Code formatter (line-length=100, target-version=py310)
- **ruff** - Fast linter (includes E, F, W rules)
- **isort** - Import sorter (profile=black)

**Configuration:**
```python
from mgx_agent.config import FORMATTER_CONFIGS

config = FORMATTER_CONFIGS['fastapi']
# {
#   'language': 'python',
#   'formatters': ['isort', 'black', 'ruff'],
#   'formatter_commands': {
#       'isort': 'isort --profile=black',
#       'black': 'black --line-length=100 --target-version=py310',
#       'ruff': 'ruff check --fix',
#   }
# }
```

**Line Length:** 100 characters
**Target Version:** Python 3.10+
**Import Style:** Black-compatible

**Local Setup:**
```bash
pip install black ruff isort
```

**Run Formatters:**
```bash
isort .                  # Sort imports
black .                  # Format code
ruff check --fix .       # Lint and fix
```

---

### JavaScript/TypeScript (Express, NestJS, Next.js, React+Vite, Vue+Vite)

**Formatters:**
- **prettier** - Code formatter (printWidth=100, semi=true, singleQuote=true)
- **eslint** - Linter (extends recommended + framework-specific)

**Configuration:**
```python
config = FORMATTER_CONFIGS['express-ts']
# {
#   'language': 'typescript',
#   'formatters': ['prettier', 'eslint'],
#   'formatter_commands': {
#       'prettier': 'prettier --write --print-width=100 --semi=true --single-quote=true',
#       'eslint': 'eslint --fix',
#   }
# }
```

**Print Width:** 100 characters
**Semicolons:** True (required)
**Quotes:** Single quotes (')

**Local Setup:**
```bash
npm install --save-dev prettier eslint @typescript-eslint/eslint-plugin
```

**Run Formatters:**
```bash
npx prettier --write .
npx eslint --fix .
```

**With Next.js:**
```bash
npm install --save-dev eslint-config-next
# Add to .eslintrc.json:
# "extends": ["next", "plugin:@typescript-eslint/recommended"]
```

---

### PHP (Laravel)

**Formatters:**
- **pint** - PHP code formatter (preset=laravel)
- **phpstan** - Static analysis (level=8, optional)

**Configuration:**
```python
config = FORMATTER_CONFIGS['laravel']
# {
#   'language': 'php',
#   'formatters': ['pint', 'phpstan'],
#   'formatter_commands': {
#       'pint': 'pint --preset=laravel',
#       'phpstan': 'phpstan analyse --level=8',
#   }
# }
```

**Preset:** Laravel (PSR-12 compatible)
**Type Level:** 8 (strict)

**Local Setup:**
```bash
composer require --dev laravel/pint
composer require --dev phpstan/phpstan
```

**Run Formatters:**
```bash
./vendor/bin/pint
./vendor/bin/phpstan analyse app routes tests
```

---

### .NET / C# (Optional)

**Formatters:**
- **dotnet format** - C# code formatter

**Configuration:**
```python
config = FORMATTER_CONFIGS['dotnet-api']
# {
#   'language': 'csharp',
#   'formatters': ['dotnet format'],
#   'formatter_commands': {
#       'dotnet format': 'dotnet format --include',
#   }
# }
```

**Local Setup:**
```bash
dotnet tool install -g dotnet-format
```

**Run Formatter:**
```bash
dotnet format
```

---

## Pre-commit Hook Configuration

Pre-commit hooks automatically run formatters before each commit, preventing unformatted code from entering the repository.

### Installation

**1. Install pre-commit:**
```bash
pip install pre-commit
# or
brew install pre-commit
```

**2. Choose configuration template:**

Choose based on your project type:

**Python Projects:**
```bash
cp docs/.pre-commit-config-python.yaml .pre-commit-config.yaml
```

**Node.js/TypeScript Projects:**
```bash
cp docs/.pre-commit-config-node.yaml .pre-commit-config.yaml
```

**PHP Projects:**
```bash
cp docs/.pre-commit-config-php.yaml .pre-commit-config.yaml
```

**3. Install hooks:**
```bash
pre-commit install
pre-commit install --hook-type commit-msg  # Optional: for commit message linting
```

**4. Run on all files (first time):**
```bash
pre-commit run --all-files
```

### Running Pre-commit

**Automatic (on commit):**
```bash
git add .
git commit -m "Add feature"  # Hooks run automatically
```

**Manual (on specific files):**
```bash
pre-commit run --files src/*.py
pre-commit run --files app.ts
```

**Run all hooks on all files:**
```bash
pre-commit run --all-files
```

### Skipping Hooks (Not Recommended)

If you need to bypass hooks temporarily:
```bash
git commit --no-verify
```

**Note:** Using `--no-verify` bypasses all safety checks. Use with caution!

### Customizing Configuration

Edit `.pre-commit-config.yaml` to:

**Exclude files:**
```yaml
exclude: |
  (?x)^(
    migrations/|
    build/|
    vendor/
  )
```

**Modify arguments:**
```yaml
- id: black
  args: ['--line-length=88']  # Change line length
```

**Disable specific hooks:**
Comment out or remove the hook entry.

---

## WriteCode Auto-formatting

When `WriteCode` action generates files in FILE manifest mode, it automatically formats each file based on the target stack.

### How It Works

1. Parse FILE manifest output from LLM
2. Detect language from file extension
3. Apply stack-appropriate formatters
4. Log format changes (non-fatal on errors)
5. Return formatted manifest

### Example Flow

```python
from mgx_agent.actions import WriteCode

action = WriteCode()
result = await action.run(
    instruction="Create API endpoint",
    target_stack="fastapi"
)
# Automatically formats Python files with black, isort, ruff
```

### Format Detection

Files are formatted based on:

1. **Target Stack** → language (e.g., fastapi → python)
2. **File Extension** → language (e.g., .ts → typescript)
3. **Formatter Config** → tools to apply

### Minified File Detection

`WriteCode` warns about potentially minified files:

- Lines > 250 characters → suspicious
- > 10 levels of nesting → suspicious
- > 70% lines are long → likely minified

Example log:
```
⚠️ File app.js may be minified: Possible minified code: 8/10 lines exceed 250 chars
```

### Best-Effort Formatting

Formatting is **non-fatal**:
- If formatter fails: log warning, continue
- Original content returned on error
- Task never fails due to formatting

---

## Test File Formatting

After `WriteTest` generates test files, they are automatically formatted for readability:

```python
from mgx_agent.actions import WriteTest

action = WriteTest()
result = await action.run(code=source_code)
# Test output is automatically formatted and cleaned
```

### Cleanup Applied

- Trailing whitespace removed
- Proper line endings ensured
- Consistent indentation
- Imports sorted (Python)
- Code aligned (JavaScript/PHP)

---

## Minified/Malformed File Detection

Utility to detect and warn about problematic code patterns:

```python
from mgx_agent.formatters import detect_minified_file

code = open('app.js').read()
is_minified, issues = detect_minified_file(code)

if is_minified:
    print("⚠️ Issues:", issues)
    # [
    #   "Possible minified code: 15/20 lines exceed 250 chars",
    #   "Excessive nesting detected (depth: 12, max: 10)"
    # ]
```

### Thresholds

| Issue | Threshold |
|-------|-----------|
| Long line | > 250 characters |
| Nesting depth | > 10 levels |
| Minified indicator | > 70% long lines |

---

## Troubleshooting

### Formatter Not Found

**Error:** `Command not found: black`

**Solution:**
```bash
# Python
pip install black isort ruff

# Node.js
npm install --save-dev prettier eslint

# PHP
composer require --dev laravel/pint
```

### Pre-commit Hook Not Running

**Error:** Hooks not executing on commit

**Solution:**
```bash
# Reinstall hooks
pre-commit install

# Verify installation
cat .git/hooks/pre-commit
```

### Pre-commit Takes Too Long

**Solution - Run on staged files only:**
```bash
# Edit .pre-commit-config.yaml
stages: [commit]
```

**Or skip expensive hooks:**
```bash
# Comment out mypy, phpstan
```

### Line Length Conflicts

Different formatters have different defaults:

| Formatter | Default | Recommended |
|-----------|---------|-------------|
| Black | 88 | 100 (configured) |
| Prettier | 80 | 100 (configured) |
| Pint | 120 | 100 (via config file) |

**Solution:** Use configuration files in project root:

**pyproject.toml (Python):**
```toml
[tool.black]
line-length = 100

[tool.isort]
profile = "black"
line_length = 100
```

**.prettierrc.json (JavaScript):**
```json
{
  "printWidth": 100,
  "semi": true,
  "singleQuote": true
}
```

**pint.json (PHP):**
```json
{
  "preset": "laravel"
}
```

### Commit Message Too Long

Pre-commit may check commit message length:

**Solution:** Edit message or increase limit in config:
```yaml
- id: commit-msg
  args: ['--max-length=100']
```

---

## Integration with TaskExecutor

When `TaskExecutor` runs a task:

1. **After WriteCode:**
   - Receives FILE manifest
   - Auto-formats output
   - Emits `code_formatted` event (optional)

2. **Before Creating PR:**
   - Runs formatters on changes
   - Ensures clean git diff
   - Commits with formatted code

3. **WebSocket Events:**
   ```javascript
   // Monitor formatting
   ws.onmessage = (event) => {
     if (event.data.type === 'code_formatted') {
       console.log(`Formatted ${event.data.files_count} files`);
     }
   };
   ```

---

## Local Development Setup

### Python Project

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install formatters
pip install black ruff isort mypy

# Install pre-commit
pip install pre-commit

# Setup hooks
cp docs/.pre-commit-config-python.yaml .pre-commit-config.yaml
pre-commit install
pre-commit run --all-files
```

### Node.js Project

```bash
# Install formatters
npm install --save-dev prettier eslint @typescript-eslint/eslint-plugin

# Install pre-commit
npm install -g pre-commit

# Setup hooks
cp docs/.pre-commit-config-node.yaml .pre-commit-config.yaml
pre-commit install
pre-commit run --all-files
```

### PHP Project

```bash
# Install formatters
composer require --dev laravel/pint phpstan/phpstan

# Install pre-commit
# Use system pre-commit or composer script

# Setup hooks
cp docs/.pre-commit-config-php.yaml .pre-commit-config.yaml
pre-commit install
```

---

## Common Formatting Issues

### Issue: Black and Prettier Differ

**Problem:** Black (Python) and Prettier (JS) have different line-length preferences.

**Solution:** Configure both to use 100 chars (as in MGX defaults).

### Issue: Import Order Conflicts

**Problem:** isort and ruff have different import ordering.

**Solution:** Use `isort --profile=black` (configured by default).

### Issue: Trailing Commas

**Problem:** Prettier adds trailing commas, some linters don't like them.

**Solution:** Configure both to allow trailing commas:
```json
{
  "trailingComma": "es5"
}
```

### Issue: Semicolons in JavaScript

**Problem:** Some projects omit semicolons.

**Solution:** Prettier and ESLint configured to require them (MGX default).

---

## API Reference

### CodeFormatter.format_code()

```python
from mgx_agent.formatters import CodeFormatter, Language

result = CodeFormatter.format_code(
    content="def foo(): pass",
    file_path="test.py",  # Optional, for language detection
    language=Language.PYTHON  # Optional, explicit language
)

# Returns FormatterResult with:
# - success: bool
# - formatters_applied: List[str]
# - formatted_content: str
# - errors: List[str]
# - warnings: List[str]
```

### MinifyDetector.detect_minified_file()

```python
from mgx_agent.formatters import MinifyDetector

is_minified, issues = MinifyDetector.detect_minified_file(code)

# Returns:
# - is_minified: bool
# - issues: List[str] (descriptions of problems)
```

### get_formatter_config()

```python
from mgx_agent.config import get_formatter_config

config = get_formatter_config('fastapi')
# config = {
#   'language': 'python',
#   'formatters': [...],
#   'formatter_commands': {...}
# }
```

---

## FAQ

**Q: Do I have to use pre-commit hooks?**
A: No, they're optional. But highly recommended for team projects.

**Q: What if a formatter breaks my code?**
A: Formatters are designed to preserve semantics. If code breaks, report the issue.

**Q: Can I skip specific files?**
A: Yes, use `exclude` in `.pre-commit-config.yaml`.

**Q: How often should I run formatters?**
A: On every commit (via pre-commit) or manually before pushing.

**Q: What about code review formatting feedback?**
A: Most formatting should be automated. Code review should focus on logic, not style.

---

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [Prettier Documentation](https://prettier.io/docs/)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [Laravel Pint](https://laravel.com/docs/pint)
- [Pre-commit Documentation](https://pre-commit.com/)
- [ESLint Rules](https://eslint.org/docs/rules/)

---

**Phase 8.3 - Code Formatting & Pre-commit Complete** ✅

</details>

---

## Appendix I: Git integration (execution + repository linking)

<details>
<summary>Expand Appendix I</summary>

# Git-Aware Task Execution

## Overview

The Git-aware execution feature automatically manages Git repositories during task execution, creating branches, committing changes, and opening pull requests for each task run.

## Features

- **Automatic Branch Creation**: Creates a unique feature branch for each task run
- **Commit Management**: Stages and commits changes with customizable commit messages
- **Pull Request Creation**: Automatically opens draft PRs with task context
- **Git Metadata Tracking**: Stores branch names, commit SHAs, and PR URLs in the database
- **Event Broadcasting**: Emits real-time events for all Git operations
- **Error Handling**: Robust error handling with automatic cleanup on failure

## Configuration

### Project-Level Settings

Projects can define default Git preferences:

```json
{
  "run_branch_prefix": "mgx",
  "commit_template": "MGX Task: {task_name} - Run #{run_number}"
}
```

**Fields:**
- `run_branch_prefix` (string, default: "mgx"): Prefix for branch names
- `commit_template` (string, optional): Template for commit messages
  - Placeholders: `{task_name}`, `{run_number}`

### Task-Level Overrides

Tasks can override project settings:

```json
{
  "name": "My Task",
  "run_branch_prefix": "feature",
  "commit_template": "Custom: {task_name} (Run {run_number})"
}
```

## Execution Flow

### 1. Plan Generation Phase

After generating the execution plan, the system:

1. Clones or updates the repository
2. Creates a feature branch: `{prefix}/{task-slug}/run-{number}`
3. Records branch name in the database
4. Emits `git_branch_created` event

**Example Branch Name**: `mgx/analyze-sales-data/run-1`

### 2. Approval Phase

The user reviews the plan while the Git branch is ready. The branch name is visible in the run metadata.

### 3. Execution Phase

After approval, the task executes and artifacts are generated.

### 4. Commit and Push Phase

After successful execution:

1. Stages all changes in the repository
2. Creates a commit with the configured template
3. Pushes the branch to the remote repository
4. Records commit SHA in the database
5. Emits `git_commit_created` and `git_push_success` events

### 5. Pull Request Phase

After successful push:

1. Opens a draft pull request
2. Sets PR title: `MGX: {task_name} - Run #{run_number}`
3. Includes task context in PR body
4. Records PR URL in the database
5. Emits `pull_request_opened` event

### 6. Cleanup Phase

After completion (success or failure):

1. Cleans up local branch
2. Leaves remote branch for review
3. Logs cleanup status

## API Integration

### Task Creation with Git Settings

```bash
POST /api/tasks/
{
  "name": "Analyze Sales Data",
  "description": "Q4 2024 analysis",
  "project_id": "project_123",
  "run_branch_prefix": "analysis",
  "commit_template": "Analysis: {task_name} - Run #{run_number}"
}
```

### Run Response with Git Metadata

```json
{
  "id": "run_456",
  "task_id": "task_123",
  "run_number": 1,
  "status": "completed",
  "branch_name": "mgx/analyze-sales-data/run-1",
  "commit_sha": "abc123def456789",
  "pr_url": "https://github.com/owner/repo/pull/42",
  "git_status": "pr_opened"
}
```

### Git Status Values

- `pending`: Git operations not started
- `branch_created`: Branch created, awaiting execution
- `committed`: Changes committed locally
- `pushed`: Changes pushed to remote
- `pr_opened`: Pull request successfully created
- `failed`: Git operation failed

## Event Types

### git_branch_created

Emitted when a Git branch is created.

```json
{
  "event_type": "git_branch_created",
  "task_id": "task_123",
  "run_id": "run_456",
  "data": {
    "branch_name": "mgx/analyze-sales-data/run-1",
    "base_branch": "main",
    "repo_full_name": "owner/repo"
  },
  "message": "Git branch created: mgx/analyze-sales-data/run-1"
}
```

### git_commit_created

Emitted when changes are committed.

```json
{
  "event_type": "git_commit_created",
  "task_id": "task_123",
  "run_id": "run_456",
  "data": {
    "commit_sha": "abc123def456",
    "branch_name": "mgx/analyze-sales-data/run-1",
    "commit_message": "MGX Task: Analyze Sales Data - Run #1"
  },
  "message": "Git commit created: abc123de"
}
```

### git_push_success

Emitted when branch is successfully pushed.

```json
{
  "event_type": "git_push_success",
  "task_id": "task_123",
  "run_id": "run_456",
  "data": {
    "branch_name": "mgx/analyze-sales-data/run-1",
    "commit_sha": "abc123def456"
  },
  "message": "Git push successful: mgx/analyze-sales-data/run-1"
}
```

### git_push_failed

Emitted when push fails.

```json
{
  "event_type": "git_push_failed",
  "task_id": "task_123",
  "run_id": "run_456",
  "data": {
    "error": "Authentication failed",
    "branch": "mgx/analyze-sales-data/run-1"
  },
  "message": "Git push failed: Authentication failed"
}
```

### pull_request_opened

Emitted when PR is created.

```json
{
  "event_type": "pull_request_opened",
  "task_id": "task_123",
  "run_id": "run_456",
  "data": {
    "pr_url": "https://github.com/owner/repo/pull/42",
    "branch_name": "mgx/analyze-sales-data/run-1",
    "commit_sha": "abc123def456"
  },
  "message": "Pull request opened: https://github.com/owner/repo/pull/42"
}
```

### git_operation_failed

Emitted when any Git operation fails.

```json
{
  "event_type": "git_operation_failed",
  "task_id": "task_123",
  "run_id": "run_456",
  "data": {
    "error": "Repository not found",
    "operation": "branch_creation"
  },
  "message": "Git setup failed: Repository not found"
}
```

## WebSocket Monitoring

Connect to WebSocket endpoints to receive real-time Git events:

```javascript
// Monitor specific run
const ws = new WebSocket('ws://localhost:8000/ws/runs/run_456');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event_type) {
    case 'git_branch_created':
      console.log('Branch created:', data.data.branch_name);
      break;
    case 'pull_request_opened':
      console.log('PR opened:', data.data.pr_url);
      break;
  }
};
```

## Error Handling

### Branch Creation Failure

If branch creation fails, execution continues without Git integration. The error is logged and a `git_operation_failed` event is emitted.

### Push Failure

If push fails, the task completes but PR creation is skipped. The commit remains local and cleanup removes the branch.

### PR Creation Failure

If PR creation fails (e.g., duplicate PR), the task still completes successfully. The branch and commit remain available.

### Cleanup Guarantee

The executor guarantees cleanup of local branches in a `finally` block, even if the task fails.

## Database Schema

### Projects Table

```sql
ALTER TABLE projects 
ADD COLUMN run_branch_prefix VARCHAR(255) DEFAULT 'mgx',
ADD COLUMN commit_template TEXT;
```

### Tasks Table

```sql
ALTER TABLE tasks
ADD COLUMN run_branch_prefix VARCHAR(255),
ADD COLUMN commit_template TEXT;
```

### Task Runs Table

```sql
ALTER TABLE task_runs
ADD COLUMN branch_name VARCHAR(255),
ADD COLUMN commit_sha VARCHAR(64),
ADD COLUMN pr_url VARCHAR(512),
ADD COLUMN git_status VARCHAR(50);

CREATE INDEX ix_task_runs_branch_name ON task_runs(branch_name);
```

## Testing

### Unit Tests

Test individual Git operations:

```python
async def test_git_branch_creation(executor, mock_git_service):
    result = await executor.execute_task(
        task_id="task_123",
        run_id="run_456",
        task_description="Test",
        project_config={"repo_full_name": "owner/repo"}
    )
    
    mock_git_service.create_branch.assert_called_once()
```

### Integration Tests

Test full execution flow:

```python
async def test_full_git_workflow(executor):
    # Execute task with approval
    result = await executor.execute_task(...)
    
    # Verify git metadata
    assert result["git_metadata"]["branch_name"]
    assert result["git_metadata"]["commit_sha"]
    assert result["git_metadata"]["pr_url"]
```

## Best Practices

### Branch Naming

- Use descriptive prefixes (`feature`, `fix`, `analysis`)
- Keep task names concise (50 characters max after sanitization)
- Run numbers provide uniqueness

### Commit Messages

- Include task context
- Use consistent templates
- Add run number for traceability

### Repository Setup

- Ensure CI/CD is configured for MGX branches
- Set up branch protection for base branch
- Configure required reviewers for PRs

### Error Recovery

- Monitor `git_operation_failed` events
- Check task run metadata for Git status
- Manually create PRs if automated creation fails

## Limitations

- **Single Repository**: Each task run works with one repository
- **No Merge**: PRs are created as drafts; merging is manual
- **No Conflict Resolution**: If conflicts exist, push may fail
- **Rate Limits**: GitHub API rate limits apply to PR creation

## Future Enhancements

- Support for multiple repositories per task
- Automatic conflict resolution
- PR merge automation with approval
- Support for GitLab, Bitbucket
- Branch cleanup policies
- Artifact-to-file mapping for selective commits

## Troubleshooting

### "Git push failed: Authentication failed"

**Cause**: GitHub credentials are missing or invalid.

**Solution**: Configure `GITHUB_PAT` or GitHub App credentials in `.env`.

### "Branch already exists"

**Cause**: Previous run created a branch that wasn't cleaned up.

**Solution**: Manually delete the remote branch or increment the run number.

### "PR creation failed: Validation Failed"

**Cause**: A PR already exists for the branch.

**Solution**: Check existing PRs and update or close duplicates.

### "Repository not found"

**Cause**: Repository name is incorrect or access is denied.

**Solution**: Verify `repo_full_name` and GitHub credentials.

## See Also

- [API Documentation](./API_EVENTS_DOCUMENTATION.md)
- [Git Service](../backend/services/git.py)
- [Task Executor](../backend/services/executor.py)
- [Database Schema](./DATABASE_SCHEMA_COMPLETE.md)

---

### Repository linking (GitHub / PAT / OAuth)

# GitHub Repository Linking

This backend supports linking a **Project** to one or more GitHub repositories via `RepositoryLink` records.

## Environment variables

The repository linking feature uses the following environment variables (see `.env.example`):

- `GITHUB_APP_ID` (optional): GitHub App ID
- `GITHUB_CLIENT_ID` (optional): GitHub OAuth client ID (not currently used by the backend router; reserved for future OAuth flow)
- `GITHUB_PRIVATE_KEY_PATH` (optional): Path to the GitHub App private key PEM file
- `GITHUB_PAT` (optional): Personal Access Token fallback (used when app auth is not configured)
- `GITHUB_CLONE_CACHE_DIR` (optional): Directory where the backend caches git clones (default: `/tmp/mgx-agent-repos`)

Auth resolution order:

1. If `installation_id` is provided in the API request and GitHub App settings are configured (`GITHUB_APP_ID` + `GITHUB_PRIVATE_KEY_PATH`), the backend uses an installation access token.
2. Otherwise, `GITHUB_PAT` is used.

## Required GitHub permissions/scopes

### GitHub App

The GitHub App must have access to the target repository and sufficient permissions for the operations you want:

- Read repository metadata
- Read contents (for cloning)
- Write contents (for pushing branches)
- Pull requests: write (for PR creation)

### PAT fallback

For a classic PAT, the simplest scope set is:

- `repo` (private repos) or `public_repo` (public repos only)

For a fine-grained token, grant:

- Repository permissions: `Contents` (Read/Write)
- Repository permissions: `Pull requests` (Read/Write)
- Repository permissions: `Metadata` (Read)

## API

Base path: `/api/repositories`

### Test access

`POST /api/repositories/test`

```json
{
  "repo_full_name": "octocat/Hello-World",
  "installation_id": 123456
}
```

Response:

```json
{
  "ok": true,
  "repo_full_name": "octocat/Hello-World",
  "default_branch": "main"
}
```

### Connect a repository to a project

`POST /api/repositories/connect`

```json
{
  "project_id": "<project-id>",
  "repo_full_name": "octocat/Hello-World",
  "installation_id": 123456,
  "reference_branch": "main",
  "set_as_primary": true
}
```

Notes:

- The backend validates access to the repository before persisting the link.
- If `set_as_primary` is true, the Project fields `repo_full_name`, `default_branch`, and `primary_repository_link_id` are updated.

### List repository links

`GET /api/repositories?project_id=<project-id>`

### Refresh repository metadata

`POST /api/repositories/{link_id}/refresh`

Refreshes `repo_full_name` and `default_branch` from GitHub.

### Update branch preferences / primary link

`PATCH /api/repositories/{link_id}`

```json
{
  "reference_branch": "develop",
  "set_as_primary": true
}
```

### Disconnect

`DELETE /api/repositories/{link_id}`

Marks the link as `disconnected` and clears stored auth metadata.

</details>

---

## Appendix J: Multi-tenant model + database entry points

<details>
<summary>Expand Appendix J</summary>

# Multi-tenant model (Workspaces & Projects)

MGX Agent is designed as a multi-tenant system.

## Hierarchy

- **Workspace**: top-level tenant container (team/company)
- **Project**: scoped under a workspace; represents a target repository/config
- **Task**: scoped to a workspace + project
- **TaskRun**: a single execution of a task; stores run status, results, and git metadata

## API

- Workspaces: `/api/workspaces/*`
- Projects: `/api/projects/*`

Workspace context is propagated through backend dependencies (see `backend/routers/deps.py`).

## Database

See:

- [DATABASE.md](./DATABASE.md)
- Models: `backend/db/models/entities.py`

---

### Database overview (entry point)

# Database

MGX Agent uses **PostgreSQL** with **async SQLAlchemy** and **Alembic** migrations.

## Model hierarchy (multi-tenant)

**Workspace → Project → Task → TaskRun**

Key tables include:

- `workspaces`
- `projects`
- `tasks`
- `task_runs`
- `repository_links`
- `metric_snapshots`
- `artifacts`

## Migrations

- Alembic config: `backend/alembic.ini`
- Migration scripts: `backend/migrations/`

## Detailed schema docs

- **[DATABASE_SCHEMA_GUIDE.md](../DATABASE_SCHEMA_GUIDE.md)**
- **[DATABASE_SCHEMA_COMPLETE.md](../DATABASE_SCHEMA_COMPLETE.md)**

Implementation reference:

- SQLAlchemy models: [`backend/db/models/entities.py`](../backend/db/models/entities.py)

</details>

---

## Appendix K: Environment template (.env.example)

<details>
<summary>Expand Appendix K</summary>

```dotenv
# =============================================================================
# MGX Agent - Docker Compose Environment Variables
# =============================================================================
# Copy this file to .env and customize for your deployment
#
# SECURITY WARNING:
# - Change all JWT_SECRET and API_KEY values for production
# - Change MinIO credentials (S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY)
# - Change database passwords (DB_PASSWORD)
# - Use strong, randomly-generated values (see below for generation)
#
# Generate secure secrets:
#   JWT_SECRET: openssl rand -hex 32
#   API_KEY: openssl rand -hex 32
#   DB_PASSWORD: openssl rand -hex 16
#   S3_SECRET_ACCESS_KEY: openssl rand -base64 32
#
# =============================================================================

# =============================================================================
# Core Application Settings
# =============================================================================

# Deployment environment: development, staging, production
MGX_ENV=production

# API server host and port (host should be 0.0.0.0 for Docker)
MGX_PORT=8000
MGX_BASE_URL=http://localhost:8000

# Number of uvicorn workers (1-4 for small deployments, 4-8 for larger)
MGX_WORKERS=4

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
MGX_LOG_LEVEL=INFO

# =============================================================================
# Security - CHANGE THESE FOR PRODUCTION
# =============================================================================

# JWT secret for authentication (generate with: openssl rand -hex 32)
# CHANGE THIS: openssl rand -hex 32
JWT_SECRET=change-me-in-production-use-openssl-rand-hex-32

# API key for service-to-service authentication
# CHANGE THIS: openssl rand -hex 32
API_KEY=change-me-in-production-use-openssl-rand-hex-32

# =============================================================================
# MGX Agent Configuration
# =============================================================================

# Maximum number of rounds for task execution (1-20)
MGX_MAX_ROUNDS=5

# Maximum number of revision rounds for output validation (0-5)
MGX_MAX_REVISION_ROUNDS=2

# Maximum memory size for agent context (10-500 MB)
MGX_MAX_MEMORY_SIZE=50

# Enable response caching (true/false)
MGX_ENABLE_CACHING=true

# Cache backend: none, memory, or redis
# - memory: In-process LRU cache (single worker)
# - redis: Distributed cache (multi-worker, requires Redis)
# - none: No caching
MGX_CACHE_BACKEND=redis

# Maximum number of cache entries for memory backend
MGX_CACHE_MAX_ENTRIES=10000

# Cache entry time-to-live in seconds (60-86400)
MGX_CACHE_TTL_SECONDS=3600

# =============================================================================
# PostgreSQL Database Configuration
# =============================================================================

# Database host (use 'postgres' for Docker Compose internal networking)
DB_HOST=postgres

# Database port
DB_PORT=5432

# Database name
DB_NAME=mgx

# Database user (create this user in PostgreSQL)
DB_USER=mgx

# Database password (CHANGE THIS FOR PRODUCTION)
# CHANGE THIS: openssl rand -hex 16
DB_PASSWORD=mgx

# Connection pool settings
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Async connection URL (auto-generated from above settings)
# Format: postgresql+asyncpg://user:password@host:port/database
# Leave empty to auto-generate from DB_* variables above
# DATABASE_URL=postgresql+asyncpg://mgx:mgx@postgres:5432/mgx

# =============================================================================
# Redis Cache Configuration
# =============================================================================

# Redis host (use 'redis' for Docker Compose internal networking)
REDIS_HOST=redis

# Redis port
REDIS_PORT=6379

# Redis cache TTL in seconds (should match MGX_CACHE_TTL_SECONDS)
REDIS_CACHE_TTL=3600

# Full Redis URL (auto-generated if empty)
# Leave empty to auto-generate from REDIS_HOST and REDIS_PORT
# REDIS_URL=redis://redis:6379/0

# =============================================================================
# S3/MinIO Object Storage Configuration
# =============================================================================

# S3 endpoint URL (use 'http://minio:9000' for Docker Compose internal)
# For external S3 (AWS), use: https://s3.amazonaws.com or s3.region.amazonaws.com
S3_ENDPOINT_URL=http://minio:9000

# AWS region (any valid AWS region, default: us-east-1)
S3_REGION=us-east-1

# S3 bucket name for artifacts
S3_BUCKET=mgx-artifacts

# S3 access key (MinIO root user or AWS access key)
# CHANGE THIS FOR PRODUCTION
S3_ACCESS_KEY_ID=minioadmin

# S3 secret key (MinIO root password or AWS secret key)
# CHANGE THIS FOR PRODUCTION: openssl rand -base64 32
S3_SECRET_ACCESS_KEY=minioadmin

# Use TLS for S3 connection (true for AWS, false for local MinIO)
S3_SECURE=false

# =============================================================================
# Application Defaults
# =============================================================================

# Default workspace name created on startup
DEFAULT_WORKSPACE_NAME=default

# Default project name created in the default workspace
DEFAULT_PROJECT_NAME=default

# =============================================================================
# Optional Integrations
# =============================================================================

# Enable Kafka event streaming (requires --profile kafka)
KAFKA_ENABLED=false

# Kafka broker addresses (if KAFKA_ENABLED=true)
# For Docker Compose: kafka:29092 (internal), localhost:9092 (external)
# KAFKA_BROKERS=kafka:29092

# Kafka topic for event streaming
# KAFKA_TOPIC_EVENTS=mgx-events

# Enable OpenTelemetry observability
OTEL_ENABLED=false

# OpenTelemetry exporter endpoint (if OTEL_ENABLED=true)
# OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Sentry error tracking (optional)
# SENTRY_DSN=https://key@sentry.io/project-id

# =============================================================================
# GitHub Integration (Optional)
# =============================================================================

# GitHub App authentication (recommended for production)
# Follow: https://docs.github.com/en/apps/creating-github-apps/creating-github-apps/creating-a-github-app

# GitHub App ID
# GITHUB_APP_ID=123456

# GitHub App Client ID
# GITHUB_CLIENT_ID=Iv1.abcdef123456

# Path to GitHub App private key PEM file (relative to /app)
# GITHUB_PRIVATE_KEY_PATH=/run/secrets/github_app_private_key.pem

# Fallback: GitHub Personal Access Token (if App auth not configured)
# Required scopes: repo, workflow, gist, read:user, write:repo_hook
# GITHUB_PAT=ghp_...

# Local directory for cached git clones (must be writable)
GITHUB_CLONE_CACHE_DIR=/tmp/mgx-agent-repos

# =============================================================================
# Debug & Monitoring
# =============================================================================

# Enable debug mode (affects logging verbosity)
DEBUG=false

# Application log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# =============================================================================
# Advanced Database Settings (Usually not needed)
# =============================================================================

# PostgreSQL shared_buffers (for tuning database performance)
# Default 256MB, increase for larger deployments
# PG_SHARED_BUFFERS=256MB

# PostgreSQL effective_cache_size (for query planner tuning)
# Default 1GB, should be about 1/4 of available RAM
# PG_EFFECTIVE_CACHE_SIZE=1GB

# PostgreSQL work_mem (memory per sort/hash operation)
# Default 16MB, increase if you have memory and run complex queries
# PG_WORK_MEM=16MB

# PostgreSQL max connections
# Default 200, adjust based on connection pool size
# PG_MAX_CONNECTIONS=200

# =============================================================================
# Advanced Redis Settings (Usually not needed)
# =============================================================================

# Redis persistence: appendonly yes/no
# Default: yes (AOF persistence enabled)
# REDIS_APPENDONLY=yes

# Redis appendfsync: always, everysec, no
# Default: everysec (balance between durability and performance)
# REDIS_APPENDFSYNC=everysec

# =============================================================================
# Notes for Production Deployment
# =============================================================================

# 1. SECURITY:
#    - Run: openssl rand -hex 32 | xargs -I {} sed -i 's/change-me-in-production/{}/g' .env
#    - Rotate secrets regularly
#    - Use Docker secrets or encrypted vaults for sensitive data
#    - Enable TLS for all external connections

# 2. PERFORMANCE:
#    - Monitor resources: docker compose stats
#    - Increase MGX_WORKERS based on CPU cores (CPU count - 1)
#    - Increase DB_POOL_SIZE for high concurrency (20-50)
#    - Enable Redis for distributed caching

# 3. BACKUPS:
#    - Regular PostgreSQL backups: docker exec mgx-postgres pg_dump -U mgx mgx > backup.sql
#    - MinIO backups: sync volumes to external storage
#    - Test restore procedures regularly

# 4. MONITORING:
#    - Use: docker compose logs -f mgx-ai
#    - Monitor health: docker compose ps
#    - Set up alerts on unhealthy services
#    - Enable OpenTelemetry for detailed observability

# 5. SCALING:
#    - Use docker compose --profile kafka for event streaming
#    - Enable Redis for distributed caching
#    - Consider S3-compatible external storage for MinIO
#    - Use managed PostgreSQL for databases
#    - Implement reverse proxy (nginx/caddy) in front of port 8000

# =============================================================================
```

</details>

