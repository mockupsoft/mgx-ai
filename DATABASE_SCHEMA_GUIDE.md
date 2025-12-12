# Database Schema Implementation Guide

This document provides comprehensive documentation for the database schema implementation, including migration commands, model usage, and best practices.

## Overview

The database schema implementation provides a complete persistence layer for the MGX Agent dashboard with the following features:

- **Async SQLAlchemy** engine with PostgreSQL support
- **Alembic migrations** for schema version control
- **Four core models**: Task, TaskRun, MetricSnapshot, Artifact
- **Comprehensive testing** with in-memory SQLite
- **Sample data seeding** for local development

## Database Models

### Task Model
Represents individual task definitions and configuration.

```python
from backend.db.models import Task, TaskStatus

# Create a task
task = Task(
    name="Market Analysis",
    description="Comprehensive market analysis",
    config={
        "model": "gpt-4",
        "temperature": 0.7,
        "tools": ["web_search", "data_analysis"]
    },
    max_rounds=5,
    memory_size=50
)
```

**Key Fields:**
- `id`: UUID primary key
- `name`, `description`: Task identification
- `config`: JSON configuration blob
- `status`: TaskStatus enum (PENDING, RUNNING, COMPLETED, etc.)
- `total_runs`, `successful_runs`, `failed_runs`: Execution statistics
- `success_rate`: Computed property for success percentage

### TaskRun Model
Represents individual executions of tasks.

```python
from backend.db.models import TaskRun, RunStatus

# Create a task run
run = TaskRun(
    task_id=task.id,
    run_number=1,
    status=RunStatus.COMPLETED,
    plan={"steps": [...]},
    results={"summary": "..."},
    duration=120.5
)
```

**Key Fields:**
- `task_id`: Foreign key to parent Task
- `run_number`: Sequential run number within task
- `status`: RunStatus enum
- `plan`, `results`: JSON execution data
- `started_at`, `completed_at`, `duration`: Timing information
- `error_message`, `error_details`: Error tracking

### MetricSnapshot Model
Stores performance and system metrics.

```python
from backend.db.models import MetricSnapshot, MetricType

# Create a metric
metric = MetricSnapshot(
    task_id=task.id,
    task_run_id=run.id,
    name="cpu_usage",
    metric_type=MetricType.GAUGE,
    value=75.5,
    unit="%",
    labels={"host": "server1"}
)
```

**Key Fields:**
- `task_id`, `task_run_id`: Optional foreign keys
- `name`, `metric_type`: Metric identification (MetricType enum)
- `value`, `unit`: Measurement data
- `labels`: JSON tags/labels
- `timestamp`: Measurement time

### Artifact Model
Stores generated files and outputs.

```python
from backend.db.models import Artifact, ArtifactType

# Create an artifact
artifact = Artifact(
    task_id=task.id,
    task_run_id=run.id,
    name="analysis_report.md",
    artifact_type=ArtifactType.REPORT,
    file_path="/reports/report.md",
    file_size=1024,
    content="# Report\n\nGenerated content",
    metadata={"version": "1.0"}
)
```

**Key Fields:**
- `task_id`, `task_run_id`: Optional foreign keys
- `name`, `artifact_type`: Artifact identification (ArtifactType enum)
- `file_path`, `file_size`, `file_hash`: File information
- `content_type`, `content`: File content
- `metadata`: JSON additional data

## Database Configuration

### Environment Variables

Set these environment variables for database connectivity:

```bash
# PostgreSQL connection
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=mgx_agent

# Connection pool settings
export DB_POOL_SIZE=10
export DB_MAX_OVERFLOW=20
```

### Database URLs

The system automatically generates synchronous and asynchronous URLs:

```python
from backend.config import settings

# Synchronous URL (for migrations)
sync_url = settings.database_url
# postgresql://postgres:postgres@localhost:5432/mgx_agent

# Asynchronous URL (for application)
async_url = settings.async_database_url
# postgresql+asyncpg://postgres:postgres@localhost:5432/mgx_agent
```

## Migration Commands

### Initial Setup

1. **Initialize Alembic** (already done):
   ```bash
   cd backend
   alembic init migrations
   ```

2. **Configure Alembic**:
   - Edit `alembic.ini` with your database URL
   - Update `migrations/env.py` to import your models

### Migration Operations

#### Create Initial Migration
```bash
cd backend
alembic revision --autogenerate -m "Initial database schema"
```

#### Apply Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Apply specific migration
alembic upgrade <revision_id>

# Check current version
alembic current

# Show migration history
alembic history --verbose
```

#### Rollback Operations
```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Rollback all migrations (WARNING: destructive)
alembic downgrade base
```

#### Migration Script Template
Create migrations in `backend/migrations/versions/` following this pattern:

```python
"""Description of changes

Revision ID: abc123
Revises: 
Create Date: 2024-12-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add tables, columns, indexes
    op.create_table('tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        # ... other columns
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    # Reverse operations
    op.drop_table('tasks')
```

## Database Operations

### Async Session Usage

```python
from backend.db import get_session
from fastapi import Depends

async def create_task(db: AsyncSession = Depends(get_session)):
    task = Task(name="New Task", description="Description", config={})
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task
```

### Model Methods

All models include helper methods:

```python
# Serialization
task_dict = task.to_dict()
task.update_from_dict({"description": "New description"})

# CRUD operations
await task.save(session)
await task.delete(session)
retrieved_task = await Task.get_by_id(session, task_id)
```

### Querying Examples

```python
from sqlalchemy import select
from backend.db.models import Task, TaskStatus

# Get all tasks
result = await session.execute(select(Task))
tasks = result.scalars().all()

# Get tasks by status
result = await session.execute(
    select(Task).where(Task.status == TaskStatus.COMPLETED)
)
completed_tasks = result.scalars().all()

# Get tasks with runs
result = await session.execute(
    select(Task).where(Task.runs.any())
)
tasks_with_runs = result.scalars().all()
```

## Seeding Demo Data

### Run Seeding Script

```bash
cd backend
python scripts/seed_data.py
```

The seeding script creates:
- **8 sample tasks** with realistic configurations
- **3-8 task runs** per task with various statuses
- **Multiple metrics** per task and run (CPU, memory, performance)
- **Artifacts** including reports, data files, logs, and configs

### Expected Output
```
🌱 Starting database seeding...
Creating 8 sample tasks...
  ✅ Created task: Market Analysis
  ✅ Created task: Code Review
  ...
Creating sample runs for each task...
  ✅ Created 5 runs for task: Market Analysis
  ...
Creating sample metrics...
  ✅ Created 45 metrics
Creating sample artifacts...
  ✅ Created 32 artifacts

📊 Seeding Summary:
  • Tasks created: 8
  • Task runs created: 42
  • Metrics created: 45
  • Artifacts created: 32
  • Total executions: 156
  • Successful executions: 123
  • Overall success rate: 78.8%
```

## Testing

### Run Database Tests

```bash
# Run all database tests
pytest tests/unit/test_database_models.py -v

# Run specific test class
pytest tests/unit/test_database_models.py::TestDatabaseModels -v

# Run with coverage
pytest tests/unit/test_database_models.py --cov=backend.db --cov-report=html
```

### Test Database Configuration

Tests automatically use:
- **In-memory SQLite** for isolation
- **Automatic table creation** before tests
- **Rollback after each test** for cleanup
- **Async session management** with proper cleanup

### Test Categories

1. **Model Tests** (`TestDatabaseModels`)
   - Model creation and validation
   - Serialization helpers
   - Relationship integrity
   - CRUD operations

2. **Migration Tests** (`TestMigrationIntegrity`)
   - Schema creation verification
   - Constraint validation
   - Foreign key integrity

3. **Performance Tests** (`TestDatabasePerformance`)
   - Index effectiveness
   - JSON column operations
   - Batch operations

4. **Data Integrity Tests** (`TestDataIntegrity`)
   - Timestamp consistency
   - Run numbering logic
   - Enum validation

## Production Deployment

### Database Setup

1. **Create PostgreSQL Database**:
   ```sql
   CREATE DATABASE mgx_agent;
   CREATE USER mgx_user WITH ENCRYPTED PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE mgx_agent TO mgx_user;
   ```

2. **Run Migrations**:
   ```bash
   # Set production environment
   export DB_HOST=prod-db.example.com
   export DB_USER=mgx_user
   export DB_PASSWORD=secure_password
   
   # Apply migrations
   cd backend
   alembic upgrade head
   ```

3. **Seed Initial Data** (optional):
   ```bash
   python scripts/seed_data.py
   ```

### Docker Deployment

Use the provided `docker-compose.yml`:

```bash
# Start all services (API + Database)
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f db

# Scale API services
docker-compose up --scale api=3
```

### Monitoring and Maintenance

1. **Connection Pool Monitoring**:
   ```python
   from backend.db.engine import get_engine
   engine = get_engine()
   # Monitor pool status via engine.pool.status()
   ```

2. **Migration Health Checks**:
   ```bash
   alembic current
   alembic check  # Verify migration state
   ```

3. **Database Backup**:
   ```bash
   pg_dump -h localhost -U postgres mgx_agent > backup.sql
   ```

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   ```bash
   # Check PostgreSQL is running
   pg_isready -h localhost -p 5432
   
   # Test connection
   psql -h localhost -U postgres -d mgx_agent
   ```

2. **Migration Failures**:
   ```bash
   # Check current state
   alembic current
   alembic history
   
   # Reset to clean state (development only!)
   alembic downgrade base
   alembic upgrade head
   ```

3. **Import Errors**:
   ```bash
   # Verify Python path
   python -c "from backend.db.models import Task; print('Import successful')"
   ```

4. **Test Failures**:
   ```bash
   # Run with verbose output
   pytest tests/unit/test_database_models.py -v -s
   
   # Check test database
   pytest tests/unit/test_database_models.py::TestDatabaseModels::test_model_imports -v
   ```

### Performance Optimization

1. **Index Usage**:
   - Verify indexes are used in query plans
   - Add indexes for frequently queried columns
   - Monitor slow queries

2. **Connection Pooling**:
   - Adjust pool sizes based on load
   - Monitor pool overflow conditions
   - Set appropriate pool recycle times

3. **JSON Operations**:
   - Use GIN indexes for JSONB columns if needed
   - Optimize JSON query patterns
   - Consider JSON schema validation

## API Integration

### FastAPI Integration

```python
from fastapi import APIRouter, Depends
from backend.db import get_session
from backend.db.models import Task

router = APIRouter()

@router.get("/tasks")
async def get_tasks(db = Depends(get_session)):
    result = await db.execute(select(Task))
    return result.scalars().all()

@router.post("/tasks")
async def create_task(task_data: dict, db = Depends(get_session)):
    task = Task(**task_data)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task
```

### Health Checks

```python
@router.get("/health/db")
async def db_health_check(db = Depends(get_session)):
    try:
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Summary

The database schema implementation provides:

✅ **Complete persistence layer** with async SQLAlchemy  
✅ **Four comprehensive models** (Task, TaskRun, MetricSnapshot, Artifact)  
✅ **Alembic migration system** with version control  
✅ **Comprehensive test suite** with in-memory testing  
✅ **Demo data seeding** for development  
✅ **Production-ready configuration** with connection pooling  
✅ **Detailed documentation** and troubleshooting guides  

**Acceptance Criteria Met:**
- ✅ `alembic upgrade head` works on blank database
- ✅ Models import without circular references  
- ✅ Seed script populates demo data
- ✅ Comprehensive test coverage
- ✅ Integration with existing FastAPI backend