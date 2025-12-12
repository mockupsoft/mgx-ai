-- Initialize MGX Agent Database
-- This file is executed when PostgreSQL container starts

-- Create database if not exists (handled by POSTGRES_DB env var)

-- Create schemas
CREATE SCHEMA IF NOT EXISTS mgx_agent;
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA mgx_agent TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA monitoring TO postgres;

-- Create basic tables for future use

-- Tasks table
CREATE TABLE IF NOT EXISTS mgx_agent.tasks (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    complexity VARCHAR(10) DEFAULT 'M',
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    metadata JSONB DEFAULT '{}'
);

-- Task runs table
CREATE TABLE IF NOT EXISTS mgx_agent.runs (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE,
    task_id INTEGER NOT NULL REFERENCES mgx_agent.tasks(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON mgx_agent.tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_complexity ON mgx_agent.tasks(complexity);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON mgx_agent.tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_runs_task_id ON mgx_agent.runs(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON mgx_agent.runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON mgx_agent.runs(created_at);

-- Log initialization
SELECT 'MGX Agent database initialized' AS status;
