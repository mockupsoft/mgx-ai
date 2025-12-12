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
├── config.py                      # Settings with .env support
├── app/
│   ├── __init__.py
│   └── main.py                   # FastAPI app, lifespan, entry point
├── services/
│   ├── __init__.py
│   ├── team_provider.py          # MGXStyleTeam wrapper
│   └── background.py             # Background task runner
└── routers/
    ├── __init__.py
    ├── health.py                 # Health & status endpoints
    ├── tasks.py                  # Task management (stub)
    └── runs.py                   # Run management (stub)
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

✅ **Services**
- MGXTeamProvider for team management
- BackgroundTaskRunner for async operations
- Singleton pattern for global access

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

- [ ] Implement task execution endpoints
- [ ] Add database models (SQLAlchemy)
- [ ] Create database migrations (Alembic)
- [ ] Implement WebSocket support for real-time updates
- [ ] Add authentication/authorization
- [ ] Create comprehensive API tests
- [ ] Add monitoring and metrics
- [ ] Deploy to production environment

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [MetaGPT](https://github.com/geekan/MetaGPT)
