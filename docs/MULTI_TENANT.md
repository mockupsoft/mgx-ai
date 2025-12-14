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
