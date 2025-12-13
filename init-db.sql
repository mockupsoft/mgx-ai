-- Initialize MGX Agent Database (PostgreSQL)
--
-- This file is executed when the PostgreSQL container starts for the first time.
-- It creates the core tables used by the FastAPI backend and inserts a small
-- set of demo multi-tenant data (workspaces/projects).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ==============================
-- Enum Types (idempotent)
-- ==============================
DO $$ BEGIN
    CREATE TYPE taskstatus AS ENUM ('pending','running','completed','failed','cancelled','timeout');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE runstatus AS ENUM ('pending','running','completed','failed','cancelled','timeout');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE metrictype AS ENUM (
        'counter','gauge','histogram','timer','status','error_rate','throughput','latency','custom'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE artifacttype AS ENUM (
        'document','image','video','audio','code','data','log','config','model','report','summary','chart'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ==============================
-- Multi-tenant tables
-- ==============================

CREATE TABLE IF NOT EXISTS workspaces (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_workspaces_id ON workspaces(id);
CREATE INDEX IF NOT EXISTS ix_workspaces_slug ON workspaces(slug);

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    workspace_id VARCHAR(36) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    run_branch_prefix VARCHAR(255) DEFAULT 'mgx',
    commit_template TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_projects_workspace_slug UNIQUE (workspace_id, slug),
    CONSTRAINT uq_projects_workspace_id_id UNIQUE (workspace_id, id)
);

CREATE INDEX IF NOT EXISTS ix_projects_id ON projects(id);
CREATE INDEX IF NOT EXISTS ix_projects_workspace_id ON projects(workspace_id);

-- ==============================
-- Core tables
-- ==============================

CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    workspace_id VARCHAR(36) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id VARCHAR(36) NOT NULL,
    CONSTRAINT fk_tasks_project_in_workspace FOREIGN KEY (workspace_id, project_id)
        REFERENCES projects(workspace_id, id) ON DELETE RESTRICT,

    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    status taskstatus NOT NULL DEFAULT 'pending',

    max_rounds INTEGER DEFAULT 5,
    max_revision_rounds INTEGER DEFAULT 2,
    memory_size INTEGER DEFAULT 50,

    run_branch_prefix VARCHAR(255),
    commit_template TEXT,

    total_runs INTEGER DEFAULT 0,
    successful_runs INTEGER DEFAULT 0,
    failed_runs INTEGER DEFAULT 0,

    last_run_at TIMESTAMPTZ,
    last_run_duration DOUBLE PRECISION,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS ix_tasks_id ON tasks(id);
CREATE INDEX IF NOT EXISTS ix_tasks_name ON tasks(name);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS ix_tasks_workspace_id ON tasks(workspace_id);
CREATE INDEX IF NOT EXISTS ix_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace_project ON tasks(workspace_id, project_id);

CREATE TABLE IF NOT EXISTS task_runs (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    task_id VARCHAR(36) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,

    workspace_id VARCHAR(36) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id VARCHAR(36) NOT NULL,
    CONSTRAINT fk_task_runs_project_in_workspace FOREIGN KEY (workspace_id, project_id)
        REFERENCES projects(workspace_id, id) ON DELETE RESTRICT,

    run_number INTEGER NOT NULL,
    status runstatus NOT NULL DEFAULT 'pending',

    plan JSONB,
    results JSONB,

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration DOUBLE PRECISION,

    error_message TEXT,
    error_details JSONB,

    memory_used INTEGER,
    round_count INTEGER,

    branch_name VARCHAR(255),
    commit_sha VARCHAR(64),
    pr_url VARCHAR(512),
    git_status VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS ix_task_runs_id ON task_runs(id);
CREATE INDEX IF NOT EXISTS ix_task_runs_status ON task_runs(status);
CREATE INDEX IF NOT EXISTS ix_task_runs_task_id_status ON task_runs(task_id, status);
CREATE INDEX IF NOT EXISTS ix_task_runs_started_at ON task_runs(started_at);
CREATE INDEX IF NOT EXISTS ix_task_runs_workspace_id ON task_runs(workspace_id);
CREATE INDEX IF NOT EXISTS ix_task_runs_project_id ON task_runs(project_id);
CREATE INDEX IF NOT EXISTS ix_task_runs_workspace_status ON task_runs(workspace_id, status);
CREATE INDEX IF NOT EXISTS ix_task_runs_branch_name ON task_runs(branch_name);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    workspace_id VARCHAR(36) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id VARCHAR(36) NOT NULL,
    CONSTRAINT fk_metric_snapshots_project_in_workspace FOREIGN KEY (workspace_id, project_id)
        REFERENCES projects(workspace_id, id) ON DELETE RESTRICT,

    task_id VARCHAR(36) REFERENCES tasks(id) ON DELETE SET NULL,
    task_run_id VARCHAR(36) REFERENCES task_runs(id) ON DELETE SET NULL,

    name VARCHAR(255) NOT NULL,
    metric_type metrictype NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50),
    labels JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_metric_snapshots_id ON metric_snapshots(id);
CREATE INDEX IF NOT EXISTS ix_metric_snapshots_task_id ON metric_snapshots(task_id);
CREATE INDEX IF NOT EXISTS ix_metric_snapshots_task_run_timestamp ON metric_snapshots(task_run_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_metric_snapshots_name_timestamp ON metric_snapshots(name, timestamp);
CREATE INDEX IF NOT EXISTS ix_metric_snapshots_workspace_id ON metric_snapshots(workspace_id);
CREATE INDEX IF NOT EXISTS ix_metric_snapshots_project_id ON metric_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_metric_snapshots_workspace_name_timestamp ON metric_snapshots(workspace_id, name, timestamp);

CREATE TABLE IF NOT EXISTS artifacts (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    task_id VARCHAR(36) REFERENCES tasks(id) ON DELETE SET NULL,
    task_run_id VARCHAR(36) REFERENCES task_runs(id) ON DELETE SET NULL,

    name VARCHAR(255) NOT NULL,
    artifact_type artifacttype NOT NULL,

    file_path TEXT,
    file_size BIGINT,
    file_hash VARCHAR(64),
    content_type VARCHAR(100),
    content TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS ix_artifacts_id ON artifacts(id);
CREATE INDEX IF NOT EXISTS ix_artifacts_task_id ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS ix_artifacts_task_run_type ON artifacts(task_run_id, artifact_type);
CREATE INDEX IF NOT EXISTS ix_artifacts_file_hash ON artifacts(file_hash);

-- ==============================
-- Seed demo tenants (idempotent)
-- ==============================

-- Default workspace/project
WITH ws AS (
    INSERT INTO workspaces (id, name, slug)
    VALUES (gen_random_uuid()::text, 'Default Workspace', 'default')
    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
)
INSERT INTO projects (id, workspace_id, name, slug)
SELECT gen_random_uuid()::text, ws.id, 'Default Project', 'default'
FROM ws
ON CONFLICT (workspace_id, slug) DO UPDATE SET name = EXCLUDED.name;

-- Demo workspace/project for local testing
WITH ws AS (
    INSERT INTO workspaces (id, name, slug, metadata)
    VALUES (gen_random_uuid()::text, 'Demo Workspace', 'demo', '{"env": "local"}'::jsonb)
    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
)
INSERT INTO projects (id, workspace_id, name, slug, metadata)
SELECT gen_random_uuid()::text, ws.id, 'Demo Project', 'demo', '{"purpose": "examples"}'::jsonb
FROM ws
ON CONFLICT (workspace_id, slug) DO UPDATE SET name = EXCLUDED.name;

SELECT 'MGX Agent database initialized (multi-tenant)' AS status;
