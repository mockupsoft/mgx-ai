# Backend FastAPI Application

RESTful API for MGX Style Multi-Agent Team, built with FastAPI and integrated with the `mgx_agent` package.

## Quick Start

### Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

2. **Create `.env` file from example:**
```bash
cp .env.example .env
```

3. **Run the development server:**
```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Or use Python directly:
```bash
python -m backend.app.main
```

The API will be available at `http://127.0.0.1:8000`

### OpenAPI Documentation

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc
- **OpenAPI JSON:** http://127.0.0.1:8000/openapi.json

## Configuration

### Environment Variables

All settings can be overridden via environment variables. See `.env.example` for all options.

**Key settings:**

```bash
# API Server
API_HOST=127.0.0.1
API_PORT=8000
API_RELOAD=true          # Auto-reload on code changes
API_WORKERS=1            # Number of Uvicorn workers

# MGX Agent
MGX_MAX_ROUNDS=5
MGX_CACHE_BACKEND=memory  # Options: none, memory, redis

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=mgx_agent

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Configuration Priority

1. Environment variables (highest priority)
2. `.env` file
3. Hardcoded defaults (lowest priority)

## API Endpoints

### Health & Status
- `GET /` - Root endpoint with API information
- `GET /health/` - Health check (returns 200 OK)
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe
- `GET /health/status` - Detailed status

### Tasks (Stub)
- `GET /tasks/` - List all tasks
- `POST /tasks/` - Create a new task
- `GET /tasks/{task_id}` - Get specific task
- `PATCH /tasks/{task_id}` - Update task
- `DELETE /tasks/{task_id}` - Delete task

### Runs (Stub)
- `GET /runs/` - List task runs
- `POST /runs/` - Create a run for a task
- `GET /runs/{run_id}` - Get specific run
- `PATCH /runs/{run_id}` - Update run
- `DELETE /runs/{run_id}` - Delete run
- `GET /runs/{run_id}/logs` - Get run logs

### Agents

All agent endpoints are workspace-scoped via the standard workspace selector:

- Headers: `X-Workspace-Id` or `X-Workspace-Slug`
- Query: `workspace_id` or `workspace_slug`

**REST**

- `GET /api/agents/definitions`
  - Lists globally enabled agent definitions.
- `GET /api/agents`
  - Lists agent instances in the active workspace.
- `POST /api/agents`
  - Creates an agent instance from a definition (optionally activates it).
- `PATCH /api/agents/{agent_id}`
  - Updates instance name/config and supports status transitions.
- `POST /api/agents/{agent_id}/activate|deactivate|shutdown`
  - Performs lifecycle transitions.
- `GET /api/agents/{agent_id}/context`
  - Reads (and lazily creates) a named context (`?context_name=default`).
- `POST /api/agents/{agent_id}/context`
  - Writes a new context version.
- `POST /api/agents/{agent_id}/context/rollback`
  - Rolls context back to a previous version.
- `GET /api/agents/{agent_id}/messages`
  - Retrieves message history (pagination via `skip`/`limit`).
- `POST /api/agents/{agent_id}/messages`
  - Persists a message and broadcasts an `agent_message` event.

**WebSocket**

- `GET ws://{host}/ws/agents/{agent_id}`
  - Subscribes to events for a specific agent.
- `GET ws://{host}/ws/agents/stream?workspace_id=...&agent_id=a1,a2`
  - Subscribes to the agent event stream (optionally filtered).

**Event names** (sent via WebSocket)

- `agent_status_changed`
- `agent_activity`
- `agent_message`
- `agent_context_updated`

**Event routing channels**

Events are published to:

- `agent:{agent_id}` (agent-scoped)
- `agents` (wildcard for all agent events)
- `workspace:{workspace_id}` (workspace-scoped; best-effort)
- `all` (global wildcard)

## Services

### MGXTeamProvider

Wraps `MGXStyleTeam` for FastAPI dependency injection:

```python
from backend.services import get_team_provider

@app.post("/execute-task")
async def execute_task(task: str):
    provider = get_team_provider()
    result = await provider.run_task(task)
    return result
```

### BackgroundTaskRunner

Handles async task execution without blocking HTTP responses:

```python
from backend.services import get_task_runner

@app.post("/background-task")
async def submit_background_task(task: str):
    runner = get_task_runner()
    task_id = await runner.submit(some_async_func(), name=task)
    return {"task_id": task_id}

@app.get("/background-task/{task_id}/status")
async def get_task_status(task_id: str):
    runner = get_task_runner()
    status = await runner.get_status(task_id)
    return status
```

### Agent Registry & Services (Optional)

Multi-agent system for managing distributed agent instances with persistent context.

**Enable in `.env`:**
```bash
AGENTS_ENABLED=true
AGENT_MAX_CONCURRENCY=10
AGENT_CONTEXT_HISTORY_LIMIT=100
AGENT_MESSAGE_RETENTION_LIMIT=1000
AGENT_MESSAGE_ACK_WINDOW_SECONDS=3600
AGENT_REGISTRY_MODULES=myapp.agents  # Auto-load agent definitions
```

**Define Custom Agents:**

```python
from backend.services import BaseAgent

class MyCustomAgent(BaseAgent):
    async def initialize(self):
        await super().initialize()
        # Setup resources
    
    async def activate(self):
        await super().activate()
        # Start processing
    
    async def deactivate(self):
        await super().deactivate()
        # Pause processing
    
    async def shutdown(self):
        await super().shutdown()
        # Cleanup

# Register in your module (loaded via AGENT_REGISTRY_MODULES)
def load_agents(registry: AgentRegistry):
    registry.register(MyCustomAgent, "my_agent", "My custom agent")
```

**Use in Routers:**

```python
from fastapi import Request

@app.post("/agents/{instance_id}/context")
async def write_context(instance_id: str, data: dict, request: Request):
    service = request.app.state.context_service
    context = await service.get_or_create_context(
        session, instance_id, "shared", workspace_id, project_id
    )
    version = await service.write_context(
        session, context.id, data, "Updated by API"
    )
    return {"version": version}
```

**Agent Lifecycle:**
- `AgentDefinition`: Global metadata and capabilities
- `AgentInstance`: Workspace/project-scoped instantiation
- `AgentContext`: Persistent shared state with version history
- `AgentContextVersion`: Immutable snapshots for rollback support

## Docker Deployment

### Build Image

```bash
docker build -t mgx-agent-api:latest -f Dockerfile .
```

### Run Container

```bash
docker run -p 8000:8000 \
  -e API_HOST=0.0.0.0 \
  -e API_PORT=8000 \
  -e DB_HOST=postgres \
  -e LOG_LEVEL=INFO \
  mgx-agent-api:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      API_HOST: 0.0.0.0
      API_PORT: 8000
      DB_HOST: postgres
      LOG_LEVEL: INFO
    depends_on:
      - postgres
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: mgx_agent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Run with: `docker-compose up`

## Running Tests

### Unit Tests

```bash
# All backend tests
pytest tests/unit/test_backend_bootstrap.py -v

# Specific test class
pytest tests/unit/test_backend_bootstrap.py::TestHealthEndpoint -v

# Specific test
pytest tests/unit/test_backend_bootstrap.py::TestHealthEndpoint::test_health_endpoint_with_test_client -v
```

### With Coverage

```bash
pytest tests/unit/test_backend_bootstrap.py --cov=backend --cov-report=html
```

## Project Structure

```
backend/
├── __init__.py                    # Package initialization
├── config.py                      # Settings with .env support (includes agent config)
├── app/
│   ├── __init__.py
│   └── main.py                   # FastAPI app, lifespan, agent service initialization
├── db/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py               # SQLAlchemy base and mixins
│   │   ├── enums.py              # Status enums (TaskStatus, AgentStatus, etc.)
│   │   └── entities.py           # ORM models (Agent*, Task*, Workspace, etc.)
│   ├── engine.py                 # Database engine setup
│   └── session.py                # AsyncSession factory
├── migrations/
│   ├── versions/
│   │   ├── 001_initial_schema.py
│   │   ├── 002_workspace_project.py
│   │   └── 004_agent_core.py     # Agent tables: definitions, instances, contexts
│   ├── env.py
│   └── script.py.mako
├── services/
│   ├── __init__.py
│   ├── team_provider.py          # MGXStyleTeam wrapper
│   ├── background.py             # Background task runner
│   └── agents/
│       ├── __init__.py
│       ├── base.py               # BaseAgent abstract class
│       ├── registry.py           # AgentRegistry for managing definitions/instances
│       └── context.py            # SharedContextService for versioned context
├── routers/
│   ├── __init__.py
│   ├── health.py                 # Health & status endpoints
│   ├── tasks.py                  # Task management endpoints
│   ├── runs.py                   # Run management endpoints
│   └── ...
├── tests/
│   ├── __init__.py
│   └── test_agent_registry.py    # Unit tests for agents
└── schemas.py                    # Pydantic schemas for API requests/responses
```

## Key Features

✅ **FastAPI Integration**
- Async/await support
- Automatic OpenAPI documentation
- CORS middleware

✅ **Configuration**
- Pydantic BaseSettings
- .env file support
- Environment variable overrides
- Agent system configuration (optional)

✅ **Services**
- MGXTeamProvider for team management
- BackgroundTaskRunner for async operations
- **AgentRegistry** for multi-agent management (new)
- **SharedContextService** for persistent context with versioning (new)
- Singleton pattern for global access

✅ **Multi-Agent System (Optional)**
- `BaseAgent` abstract class with lifecycle hooks
- `AgentRegistry` for defining and instantiating agents
- `AgentDefinition` for global agent metadata
- `AgentInstance` for workspace/project-scoped agents
- `AgentContext` with versioned history and rollback support
- Workspace/project isolation enforcement

✅ **Database**
- SQLAlchemy 1.x async ORM
- Alembic migrations
- Multi-tenancy support (Workspace > Project hierarchy)
- Agent core schema with FK integrity

✅ **Health Checks**
- Multiple health endpoints
- Kubernetes-compatible probes
- Status reporting

✅ **Development**
- Auto-reload support
- Comprehensive logging
- CORS configured for development

## Lifespan Events

The application manages startup and shutdown events:

**Startup:**
- Initialize MGXTeamProvider
- Start BackgroundTaskRunner workers
- Log initialization details

**Shutdown:**
- Stop background task runners
- Clean up team resources
- Log shutdown details

## Dependency Injection

All services use FastAPI's dependency injection pattern:

```python
from fastapi import Depends

async def get_team_provider():
    return get_team_provider()

@app.post("/tasks")
async def create_task(task: str, provider: MGXTeamProvider = Depends(get_team_provider)):
    result = await provider.run_task(task)
    return result
```

## Performance Considerations

- **Async I/O:** All endpoints are async for non-blocking operations
- **Worker Processes:** Use `API_WORKERS` for multi-process deployment
- **Connection Pooling:** Database connections pooled (configurable via `DB_POOL_SIZE`)
- **Background Tasks:** Long operations handled via BackgroundTaskRunner

## Security Considerations

- CORS is configured for development (`localhost:3000`, `localhost:8000`)
- Update CORS origins for production
- Store secrets in `.env` (never in code)
- Use environment variables for sensitive data

Example production CORS configuration:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

## Troubleshooting

### Port Already in Use

```bash
# Change port in .env or command line
uvicorn backend.app.main:app --port 9000
```

### Database Connection Issues

```bash
# Check database is running
psql -h localhost -U postgres -d mgx_agent

# Update connection settings in .env
DB_HOST=your_host
DB_PORT=5432
DB_USER=your_user
DB_PASSWORD=your_password
```

### Module Import Errors

```bash
# Ensure project root is in PYTHONPATH
export PYTHONPATH=/path/to/project:$PYTHONPATH

# Or run from project root
cd /path/to/project
uvicorn backend.app.main:app --reload
```

## Next Steps

- [x] Add database models (SQLAlchemy) - Agent core schemas complete
- [x] Create database migrations (Alembic) - Agent core migration added
- [x] Multi-agent system foundation - BaseAgent, AgentRegistry, SharedContextService
- [ ] Implement agent REST endpoints (CRUD for agents/instances/contexts)
- [ ] Add agent lifecycle management endpoints
- [ ] Implement context versioning API
- [ ] Add context rollback REST endpoints
- [ ] Implement WebSocket support for real-time agent updates
- [ ] Add authentication/authorization for agent operations
- [ ] Create comprehensive API tests for agent endpoints
- [ ] Add monitoring and metrics for agents
- [ ] Implement agent scheduler/orchestrator
- [ ] Add built-in agents (e.g., ReviewerAgent, BuilderAgent)
- [ ] Deploy to production environment

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [MetaGPT](https://github.com/geekan/MetaGPT)
