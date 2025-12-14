# MGX Agent (mgx-ai)

AI-powered multi-agent development system built on **MetaGPT**, with a production-ready **FastAPI backend**, multi-tenant **PostgreSQL** schema, real-time **WebSocket** events, **GitHub** integration, and a global **CLI** (PyPI + npm).

---

## Project status

```
┌──────────────────────────────────────────────────────────────┐
│ Overall Score:        9.8/10                                  │
│ Production Ready:     98% ✅                                   │
│ Test Suite:           130+ tests ✅ (80%+ coverage target met) │
│ Backend API:          FastAPI + DB + WebSockets ✅             │
│ Git-aware Execution:  Branch/commit/PR automation ✅           │
│ Deployment:           Docker Compose (self-hosted) ✅          │
└──────────────────────────────────────────────────────────────┘
```

### Phase completion matrix (1 → 8.3)

| Phase | Name | Status | Highlights |
|------:|------|:------:|------------|
| 1 | Quick Fixes | ✅ | Constants centralization, DRY, input validation |
| 2 | Modularization | ✅ | 2393 lines → modular packages, backward compatible |
| 3 | Test Coverage | ✅ | 130+ tests, CI/CD configured |
| 4 | Performance Optimization | ✅ | Async pipeline tuning, caching, profiling, perf docs |
| 4.5 | API & Events | ✅ | FastAPI + PostgreSQL + WebSockets, event broadcaster |
| 5 | Git Integration | ✅ | GitHub linking, branch/commit/PR creation, git events |
| 6 | Workspace & Project Management | ✅ | Multi-tenant Workspaces/Projects with isolation |
| 7 | Web Stack Support | ✅ | StackSpec, stack-aware prompting + FILE manifest |
| 8.1 | Output Validation Guardrails | ✅ | Stack-specific validation + auto-revision |
| 8.2 | Safe Patch / Diff Writer | ✅ | Unified diff parser + safe apply + recovery |
| 8.3 | Code Formatting & Pre-commit | ✅ | Stack-aware formatters + pre-commit templates |
| 8 | Global Expansion (CLI & Docker) | ✅ | mgx-cli (pip/npm) + Docker Compose self-hosted |

---

## Quick start

### 1) Docker Compose (recommended)

Self-host MGX Agent with PostgreSQL, Redis, MinIO (S3-compatible), and optional Kafka.

```bash
cp .env.example .env
# Edit .env (change secrets for production)

docker compose up -d --build

curl http://localhost:8000/health/
# OpenAPI docs:
# http://localhost:8000/docs
```

Full guide: **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**.

### 2) Local development (Python)

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt

# Run DB migrations (local Postgres required)
alembic -c backend/alembic.ini upgrade head

# Start API
uvicorn backend.app.main:app --reload
```

### 3) Running the agent locally

Python module usage:

```bash
python -m mgx_agent.cli --task "Create a FastAPI health endpoint"
# or
python examples/mgx_style_team.py --task "Implement user login"
```

### 4) Running tests

```bash
pytest
# Optional:
pytest -q
pytest --cov
```

---

## Project architecture

### High-level components

- **mgx_agent/**: core agent runtime (team orchestration, stack specs, guardrails, diff/patch, formatters)
- **backend/**: FastAPI app + async SQLAlchemy + Alembic migrations
- **mgx_cli/**: Python CLI package published as `mgx-cli` (entrypoint: `mgx`)
- **npm-wrapper/**: npm wrapper published as `@mgxai/cli` (also exposes `mgx`)
- **docker-compose.yml**: self-hosted stack (Postgres/Redis/MinIO + optional Kafka)

### Repository structure (key paths)

```text
backend/
  app/main.py              # FastAPI application factory + lifespan
  routers/                 # /api/* routes + /ws/* WebSocket endpoints
  services/                # task executor, event broadcaster, git service
  db/models/entities.py    # Workspace → Project → Task → TaskRun
  migrations/              # Alembic migrations (backend)

docs/
  API_EVENTS_DOCUMENTATION.md
  TESTING.md
  PERFORMANCE.md
  WEB_STACK_SUPPORT.md
  OUTPUT_VALIDATION.md
  PATCH_MODE.md
  DIFF_FORMAT.md
  CODE_FORMATTING.md
  CLI.md
  GIT_AWARE_EXECUTION.md
  GITHUB_REPOSITORY_LINKING.md

mgx_agent/
  team.py                  # orchestration (async optimized)
  stack_specs.py           # StackSpec registry + inference
  guardrails.py            # validate_output_constraints()
  diff_writer.py           # unified diff parser + safe apply
  file_recovery.py         # backups + restore helpers
  formatters.py            # stack-aware formatting (Phase 8.3)

mgx_cli/
  main.py                  # `mgx` entrypoint
```

---

## Installed features (phases 1–8.3)

- **Core TEM Agent (Phases 1–2)**: modular MGX-style team orchestration with safe defaults and input validation
- **Test infrastructure (Phase 3)**: unit + integration tests (130+) and CI wiring
- **Performance (Phase 4)**: async tuning, caching layer, profiling hooks, load/perf testing documentation
- **Backend API + Events (Phase 4.5)**: FastAPI backend, async SQLAlchemy models, Alembic, REST + WebSocket streaming
- **Git integration (Phase 5)**: repository linking, git-aware execution, branch/commit/PR automation, git metadata tracking
- **Multi-tenant system (Phase 6)**: workspaces/projects, workspace isolation boundaries, project-scoped tasks
- **Web stack support (Phase 7)**:
  - Backend: Express-TS, NestJS, Laravel, FastAPI
  - Frontend: React + Vite, Next.js, Vue + Vite
  - DevOps: Docker, GitHub Actions
  - (Also supported: .NET Web API / C#)
- **Output validation & formatting (Phases 8.1–8.3)**: stack-specific constraints validation, safe patch apply, stack-aware formatting + pre-commit templates
- **Global CLI & Docker deployment (Phase 8)**: `mgx-cli` + `@mgxai/cli`, plus production-oriented Docker Compose

---

## Technology stack

### Backend (this repo)

- **API**: FastAPI (async)
- **DB**: PostgreSQL (SQLAlchemy async) + Alembic migrations
- **Cache**: Redis (optional; also supports in-memory caching)
- **Artifacts**: MinIO (S3-compatible) for object storage
- **Events**: WebSocket streaming; Kafka optional in Docker profile

### Frontend (optional)

A frontend ("ai-front") is expected to consume the API/WebSocket streams (Next.js 16 + React 19). It is not bundled in this repository.

### Tooling

- **Tests**: pytest
- **Formatting/Linting** (Phase 8.3): black/ruff/isort (Python), prettier/eslint (JS/TS), pint/phpstan (PHP)
- **CI/CD**: GitHub Actions (see `.github/workflows/`)

---

## Database

The backend is **multi-tenant by design**:

**Workspace → Project → Task → TaskRun**

Key tables:

- `workspaces`
- `projects`
- `tasks`
- `task_runs` (includes git metadata: branch, commit SHA, PR URL)
- `repository_links`
- `metric_snapshots`
- `artifacts`

Migrations:

- Alembic configuration: `backend/alembic.ini`
- Migrations folder: `backend/migrations/`

More details:

- **[docs/DATABASE.md](docs/DATABASE.md)** (entry point)
- **[DATABASE_SCHEMA_GUIDE.md](./DATABASE_SCHEMA_GUIDE.md)**
- **[DATABASE_SCHEMA_COMPLETE.md](./DATABASE_SCHEMA_COMPLETE.md)**

---

## API endpoints

The FastAPI server publishes OpenAPI at:

- Swagger UI: `GET /docs`
- OpenAPI JSON: `GET /openapi.json`

High-level endpoint groups:

- **Health**: `GET /health/`, `/health/ready`, `/health/live`, `/health/status`
- **Workspaces**: `GET/POST /api/workspaces`, `GET /api/workspaces/{workspace_id}`
- **Projects**: `GET/POST /api/projects`, `GET /api/projects/{project_id}`
- **Repositories (GitHub linking)**:
  - `GET /api/repositories`
  - `POST /api/repositories/test`
  - `POST /api/repositories/connect`
  - `POST /api/repositories/{link_id}/refresh`
  - `PATCH /api/repositories/{link_id}`
  - `DELETE /api/repositories/{link_id}`
- **Tasks (CRUD)**: `GET/POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/{task_id}`
- **Runs**:
  - `GET/POST /api/runs`
  - `GET/PATCH/DELETE /api/runs/{run_id}`
  - `POST /api/runs/{run_id}/approve` (plan approval)
  - `GET /api/runs/{run_id}/logs`
- **Metrics**:
  - `GET /api/metrics`, `GET /api/metrics/{metric_id}`
  - `GET /api/metrics/task/{task_id}/summary`
  - `GET /api/metrics/run/{run_id}/summary`

Full details: **[docs/API.md](docs/API.md)**.

---

## WebSocket events

WebSocket endpoints:

- `ws://localhost:8000/ws/tasks/{task_id}`
- `ws://localhost:8000/ws/runs/{run_id}`
- `ws://localhost:8000/ws/stream` (global)

Event types include:

- Task lifecycle: `analysis_start`, `plan_ready`, `approval_required`, `approved`, `rejected`, `progress`, `completion`, `failure`, `cancelled`
- Git lifecycle: `branch_created`, `commit_created`, `pr_opened` (and related `git_*` status events)

Full contract and examples: **[docs/WEBSOCKET.md](docs/WEBSOCKET.md)**.

---

## Running & deployment

### Local API

```bash
uvicorn backend.app.main:app --reload
```

### Docker Compose deployment

```bash
docker compose up -d --build
```

### Environment variables

- Docker Compose reads configuration from `.env`.
- Start by copying **`.env.example` → `.env`** and update secrets.

Common groups:

- **Core**: `MGX_ENV`, `MGX_PORT`, `MGX_LOG_LEVEL`, `MGX_BASE_URL`
- **Database**: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- **Redis**: `REDIS_HOST`, `REDIS_PORT` (or `REDIS_URL`)
- **S3/MinIO**: `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`
- **GitHub** (optional): `GITHUB_PAT` / GitHub App settings

Production checklist (high level):

- Change secrets in `.env` (use `.env.example` as a template)
- Put the API behind TLS (nginx/caddy)
- Restrict exposed ports (firewall)
- Enable backups for Postgres volumes and MinIO bucket
- Consider the Kafka profile if you need an external event bus

Full guide: **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**.

---

## Testing

- Test suite: **130+** tests
- Coverage target: **80%+**
- Run locally with:

```bash
pytest
```

See **[docs/TESTING.md](docs/TESTING.md)**.

---

## Documentation

Primary docs:

- **API**: [docs/API.md](docs/API.md)
- **WebSocket / Events**: [docs/WEBSOCKET.md](docs/WEBSOCKET.md)
- **Database**: [docs/DATABASE.md](docs/DATABASE.md)
- **Testing**: [docs/TESTING.md](docs/TESTING.md)
- **Performance**: [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
- **Web stack support**: [docs/WEB_STACK_SUPPORT.md](docs/WEB_STACK_SUPPORT.md)
- **Output validation**: [docs/OUTPUT_VALIDATION.md](docs/OUTPUT_VALIDATION.md)
- **Patch mode**: [docs/PATCH_MODE.md](docs/PATCH_MODE.md) + [docs/DIFF_FORMAT.md](docs/DIFF_FORMAT.md)
- **Code formatting**: [docs/CODE_FORMATTING.md](docs/CODE_FORMATTING.md)
- **Git integration**: [docs/GIT_INTEGRATION.md](docs/GIT_INTEGRATION.md)
- **Multi-tenant model**: [docs/MULTI_TENANT.md](docs/MULTI_TENANT.md)
- **Docker deployment**: [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)

Additional implementation reports (phase writeups / summaries):

- [CHANGES_SUMMARY.md](./CHANGES_SUMMARY.md)
- [FINAL_REPORT.md](./FINAL_REPORT.md)
- [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md)

---

## CLI distribution

Install:

```bash
pip install mgx-cli
npm install -g @mgxai/cli
```

Common commands:

```bash
mgx init .
mgx task "Create a Snake game in Python"
mgx list
mgx status <task-id>
mgx logs <task-id>
```

See **[docs/CLI.md](docs/CLI.md)**.

---

## Roadmap (Phase 9+)

Potential next steps (post 8.3):

- Authentication + authorization (JWT, RBAC, workspace-scoped tokens)
- Durable event bus integration (Kafka-first, replayable event history)
- Job queue / scheduler (long-running tasks, retries, rate limits)
- Observability (OpenTelemetry traces + metrics + structured logs)
- Horizontal scaling + HA guidance (multi-worker API, DB pooling, S3 externalization)
- Kubernetes deployment option (Helm chart)

---

## Contributing

- Use `requirements-dev.txt` for development dependencies
- Run `pytest` before opening PRs
- Follow stack-aware formatting guidelines:
  - Python: black/ruff/isort
  - JS/TS: prettier/eslint
  - PHP: pint/phpstan

Pre-commit templates are provided in `docs/.pre-commit-config-*.yaml`.

---

## License & credits

- **License**: MIT (see [LICENSE](./LICENSE))
- Built on top of **MetaGPT** and the broader OSS ecosystem
