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
