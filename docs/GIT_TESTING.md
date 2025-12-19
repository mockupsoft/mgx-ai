# Git Integration E2E Testing Guide

This document provides comprehensive documentation for the GitHub Integration E2E test suite, covering setup, execution, and best practices for testing Git operations without requiring actual GitHub API access.

## Overview

The Git Integration E2E test suite provides comprehensive testing of:
- GitHub OAuth flow and token management
- Repository linking and management
- Branch operations and automated creation
- Commit automation with proper formatting
- Push operations and conflict handling
- Pull request creation and metadata
- Webhook event reception and processing
- Git metadata display in UI
- Error handling and recovery
- Complete end-to-end workflows

## Test Structure

### Test Files

1. **`test_git_integration.py`** - Core Git integration tests
   - OAuth flow and authentication
   - Repository discovery and management
   - Branch management operations
   - Commit automation
   - Push operations
   - Pull request creation

2. **`test_git_webhooks.py`** - Webhook event testing
   - Webhook reception and parsing
   - Signature verification
   - Event processing and data storage
   - UI event emission via WebSocket
   - Duplicate webhook prevention

3. **`test_git_scenarios.py`** - End-to-end workflow scenarios
   - Complete workflow validation
   - Error recovery scenarios
   - Concurrent operations
   - Performance testing

4. **`fixtures/github_mocks.py`** - Mock GitHub API fixtures
   - Mock data generation utilities
   - Signature generation helpers
   - API response mocks

## Test Architecture

### Mock-Based Testing

All tests use comprehensive mocking to avoid external GitHub API dependencies:

```python
@responses.activate
def test_oauth_flow(client, db_session, mock_github_token):
    setup_github_mocks(responses, {'mock_github_token': mock_github_token})
    
    response = client.post("/api/repositories/oauth/callback", json={
        "code": "test_code"
    })
    
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Test Isolation

Tests are designed to be:
- **Fast**: No network calls, all operations in-memory
- **Isolated**: Each test runs in its own transaction
- **Repeatable**: Deterministic mock data
- **Comprehensive**: Edge cases included

## Setup and Configuration

### Environment Variables

```bash
# GitHub API credentials (for real integration tests only)
GITHUB_PAT=your_github_personal_access_token
GITHUB_CLIENT_ID=your_oauth_client_id
GITHUB_CLIENT_SECRET=your_oauth_client_secret

# Webhook secret (for webhook tests)
WEBHOOK_SECRET=test_webhook_secret_12345

# Test database (SQLite by default for speed)
DATABASE_URL=sqlite:///./test.db
```

### Installing Test Dependencies

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Or install directly
pip install pytest pytest-asyncio responses httpx
```

## Running Tests

### Run All Git Tests

```bash
# Run all Git integration tests
pytest backend/tests/test_git_integration.py -v

# Run webhook tests
pytest backend/tests/test_git_webhooks.py -v

# Run E2E scenario tests
pytest backend/tests/test_git_scenarios.py -v
```

### Run Specific Test Categories

```bash
# Test OAuth flow
pytest backend/tests/test_git_integration.py::TestGitHubOAuth -v

# Test webhook signature verification
pytest backend/tests/test_git_webhooks.py::TestWebhookSignatureVerification -v

# Test complete workflow
pytest backend/tests/test_git_scenarios.py::TestCompleteGitWorkflow -v
```

### Run with Coverage

```bash
# Run with coverage report
pytest backend/tests/test_git_*.py --cov=backend.services.git --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## Test Examples

### Testing OAuth Flow

```python
@responses.activate
def test_oauth_flow(client, db_session, mock_github_token):
    # Setup mocks
    setup_github_mocks(responses, {'mock_github_token': mock_github_token})
    
    # Test OAuth callback
    response = client.post("/api/repositories/oauth/callback", json={
        "code": "test_code",
        "state": "test_state"
    })
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
```

### Testing Webhook Processing

```python
def test_push_webhook_received(client, db_session):
    # Generate webhook with valid signature
    webhook_secret = "test_webhook_secret_12345"
    push_event = {
        "ref": "refs/heads/mgx/add-auth/run-1",
        "after": "abc123def456"
    }
    
    payload = json.dumps(push_event)
    headers = generate_github_signature(payload, webhook_secret)
    
    # Send webhook
    response = client.post("/api/webhooks/github", data=payload, headers=headers)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] is True
```

### Testing Complete Workflow

```python
@responses.activate 
def test_complete_workflow(client, db_session):
    # Setup all necessary mocks
    setup_github_mocks(responses, mock_data)
    
    # 1. OAuth
    # 2. Connect repository
    # 3. Create task
    # 4. Create branch
    # 5. Commit and push
    # 6. Create PR
    # 7. Process webhook
    
    # Verify all steps completed
    assert link_response.status_code == 201
    assert branch_response.status_code == 201
    assert pr_response.status_code == 201
```

## Mock Utilities

### MockGitHubAPI

```python
api = MockGitHubAPI(token="test_token")
repo_info = api.get_repo_info("test-user/test-repo")
pr_url = api.create_pull_request("test-user/test-repo", "PR Title", "PR Body", "feature", "main")
```

### MockGitRepoManager

```python
manager = MockGitRepoManager()
repo_dir = manager.clone_or_update("https://github.com/test/repo.git", Path("/tmp/repo"), "main")
manager.create_branch(repo_dir, "feature-branch", "main")
commit_sha = manager.stage_and_commit(repo_dir, "Add feature", ["file.py"])
```

### Signature Generation

```python
from backend.tests.fixtures.github_mocks import generate_github_signature

payload = json.dumps(webhook_data)
headers = generate_github_signature(payload, webhook_secret)
```

## Coverage Areas

### OAuth Tests
- ✅ GitHub OAuth redirect works
- ✅ User authorizes app
- ✅ Token received and stored
- ✅ Token persists in database
- ✅ Token encrypted at rest
- ✅ Token used for API calls
- ✅ Token refresh before expiry
- ✅ Revoked token rejected
- ✅ Rate limit respected

### Repository Tests
- ✅ User repos listed
- ✅ Org repos listed
- ✅ Search returns correct repos
- ✅ Pagination works (limit/offset)
- ✅ Private repos included (if authorized)
- ✅ Archived repos handled
- ✅ Fork handling correct

### Branch Management Tests
- ✅ Default branch identified (main/master)
- ✅ All branches listed
- ✅ Branch protection rules retrieved
- ✅ Protected branch detected
- ✅ Branch existence verified
- ✅ Branch metadata stored

### Commit Automation Tests
- ✅ Files staged correctly
- ✅ Commit created successfully
- ✅ Commit message includes task reference
- ✅ Author set correctly
- ✅ Committer set correctly
- ✅ Multiple commits per task
- ✅ Commit history preserved
- ✅ Commit linked to task run

### Push Operation Tests
- ✅ Branch pushed successfully
- ✅ Remote branch created
- ✅ Push with 1 commit works
- ✅ Push with multiple commits works
- ✅ Push updates remote branch
- ✅ Commit visible on GitHub
- ✅ Push failure handled gracefully
- ✅ Authentication error detected
- ✅ Rate limit error detected

### PR Creation Tests
- ✅ PR created successfully
- ✅ PR title includes task reference
- ✅ PR body includes context/description
- ✅ PR links to task run
- ✅ PR points to correct branches
- ✅ PR draft mode (optional)
- ✅ PR reviews required (if configured)
- ✅ PR auto-merge (if enabled)

### Webhook Tests
- ✅ Push webhook received
- ✅ Webhook payload parsed
- ✅ Commit hash extracted
- ✅ Branch name extracted
- ✅ Author information captured
- ✅ PR webhook received
- ✅ PR action (opened, closed) captured
- ✅ PR metadata stored
- ✅ Webhook verified (signature check)
- ✅ Duplicate webhook prevented

### Merge Conflict Tests
- ✅ Conflict detected on push
- ✅ Conflict message informative
- ✅ Conflicted files identified
- ✅ Conflict markers shown (if needed)
- ✅ Manual merge option provided
- ✅ Retry after resolution
- ✅ Task marked as "needs_review"

### Error Handling Tests
- ✅ 404 error handled gracefully
- ✅ 403 error shows clear message
- ✅ 429 rate limit respected
- ✅ 409 conflict handled
- ✅ Branch protection error shown
- ✅ Auth expired → re-authenticate
- ✅ Network timeout handled
- ✅ Retry mechanism works

## Best Practices

### 1. Use Proper Fixtures

```python
@pytest.fixture
def mock_repo_info():
    return {
        "id": 123456789,
        "full_name": "test-user/test-repo",
        "default_branch": "main",
        "private": False
    }
```

### 2. Clean Up After Tests

```python
def cleanup_test_data(workspace_id: str):
    """Clean up test data after test completion."""
    with db_session() as session:
        # Delete test workspaces, projects, tasks
        pass
```

### 3. Test Edge Cases

```python
def test_push_with_empty_commit_message(self):
    """Test push with empty commit message - should fail gracefully."""
    response = client.post("/git/push", json={"commit_message": ""})
    assert response.status_code == 422
    assert "commit message" in response.json()["detail"].lower()
```

### 4. Verify Proper Error Messages

```python
def test_rate_limit_reached(self):
    # Mock rate limit exceeded
    setup_github_rate_limit_exceeded(responses)
    
    response = client.get("/api/repositories/user/repos")
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()
```

## Continuous Integration

### GitHub Actions Setup

```yaml
name: Git Integration Tests

on:
  pull_request:
    paths:
      - '**/test_git_*.py'
      - '**/git.py'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements-test.txt
      - run: pytest backend/tests/test_git_*.py --cov=backend.services.git
      - uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **"Module not found" errors**
   - Ensure pytest is installed
   - Check Python path includes backend/

2. **Database transaction errors**
   - Use proper transaction isolation
   - Clean up test data between tests

3. **Mock responses not working**
   - Use `@responses.activate` decorator
   - Ensure responses library is installed

4. **Signature verification fails**
   - Use `generate_github_signature` utility
   - Ensure consistent secret across test

## Maintenance

### Updating Tests

When updating GitHub integration code:

1. **Update corresponding tests** - Ensure new features are tested
2. **Add new test cases** - Cover new code paths
3. **Update mocks** - Keep mock data in sync with API
4. **Review coverage** - Ensure no regressions

### Test Data Management

- Use fixtures for test data
- Keep mock data realistic
- Document mock data structures
- Update with API changes

## Conclusion

This test suite provides comprehensive coverage of GitHub integration functionality. Tests are fast, reliable, and maintainable through proper mocking and isolation techniques. Follow the best practices and maintenance guidelines to ensure continued test effectiveness.