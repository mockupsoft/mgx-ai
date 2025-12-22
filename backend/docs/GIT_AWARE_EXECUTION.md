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
