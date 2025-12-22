-- Migration: Add Git metadata fields
-- Description: Adds git preferences to projects/tasks and git metadata to task_runs

-- Add git preferences to projects table
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS run_branch_prefix VARCHAR(255) DEFAULT 'mgx',
ADD COLUMN IF NOT EXISTS commit_template TEXT;

COMMENT ON COLUMN projects.run_branch_prefix IS 'Branch prefix for task runs (e.g., ''mgx'' -> mgx/task-name/run-1)';
COMMENT ON COLUMN projects.commit_template IS 'Template for commit messages (supports {task_name}, {run_number} placeholders)';

-- Add git preferences to tasks table (can override project defaults)
ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS run_branch_prefix VARCHAR(255),
ADD COLUMN IF NOT EXISTS commit_template TEXT;

COMMENT ON COLUMN tasks.run_branch_prefix IS 'Branch prefix for this task''s runs (overrides project setting)';
COMMENT ON COLUMN tasks.commit_template IS 'Commit message template for this task (overrides project setting)';

-- Add git metadata to task_runs table
ALTER TABLE task_runs
ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS commit_sha VARCHAR(64),
ADD COLUMN IF NOT EXISTS pr_url VARCHAR(512),
ADD COLUMN IF NOT EXISTS git_status VARCHAR(50);

COMMENT ON COLUMN task_runs.branch_name IS 'Git branch created for this run';
COMMENT ON COLUMN task_runs.commit_sha IS 'Latest commit SHA from this run';
COMMENT ON COLUMN task_runs.pr_url IS 'Pull request URL if created';
COMMENT ON COLUMN task_runs.git_status IS 'Git operation status (pending, branch_created, committed, pushed, pr_opened, failed)';

-- Add index for branch_name lookups
CREATE INDEX IF NOT EXISTS ix_task_runs_branch_name ON task_runs(branch_name);

SELECT 'Git metadata migration completed' AS status;
