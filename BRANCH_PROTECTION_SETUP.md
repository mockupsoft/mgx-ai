# Branch Protection Setup Guide

This document provides instructions for setting up GitHub branch protection rules to enforce Phase 1 quality gates.

---

## Overview

Branch protection rules ensure that:
- PRs pass all quality gates before merging
- Security scans run on every PR
- Code coverage is maintained
- Linting and type checking pass

---

## Required Branch Protection Rules

### Branch: `main`

#### Required Checks

All of the following checks must pass before merging:

1. **Quality Gates**
   - `Linting / Code Quality Checks` ✅
   - `Security-scan / Security Vulnerability Scan` ✅
   - `Pre-commit / Pre-commit Hooks` ✅
   - `Code-style / Code Style Enforcement` ✅
   - `Dependency-check / Dependency Validation` ✅

2. **Test Suite**
   - `Test / test (3.9)` ✅
   - `Test / test (3.10)` ✅
   - `Test / test (3.11)` ✅
   - `Test / test (3.12)` ✅

3. **Coverage** (optional, recommended)
   - `coverage-report / Generate coverage report` ✅

#### Settings

```yaml
require_pull_request_reviews: true
required_approving_review_count: 1
require_code_owner_reviews: true
dismiss_stale_reviews_on_push: true
require_last_push_approval: true

require_status_checks: true
required_status_checks:
  - "Linting / Code Quality Checks"
  - "Security-scan / Security Vulnerability Scan"
  - "Pre-commit / Pre-commit Hooks"
  - "Code-style / Code Style Enforcement"
  - "Dependency-check / Dependency Validation"
  - "Test / test (3.11)"  # Minimum Python version

strict: true  # Require status checks from PR target branch

enforce_admins: false  # Admins must follow rules

allow_force_pushes: false
allow_deletions: false

require_linear_history: true  # Use merge commits or rebase only
```

---

### Branch: `develop`

#### Required Checks

```yaml
require_status_checks: true
required_status_checks:
  - "Linting / Code Quality Checks"
  - "Test / test (3.11)"

strict: false  # Don't require checks from main branch

require_pull_request_reviews: true
required_approving_review_count: 1
require_code_owner_reviews: false
```

---

## Setup Instructions

### Option 1: GitHub UI (Manual)

1. Go to repository **Settings** → **Branches**
2. Click **Add branch protection rule**
3. Enter branch name pattern: `main`
4. Configure settings as shown above
5. Click **Create**

### Option 2: GitHub CLI (Automated)

```bash
# Install GitHub CLI if not already installed
# https://cli.github.com/

# Authenticate
gh auth login

# Set up main branch protection
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  repos/:owner/:repo/branches/main/protection \
  -f required_status_checks='{"strict":true,"checks":[{"context":"Linting / Code Quality Checks"},{"context":"Security-scan / Security Vulnerability Scan"},{"context":"Pre-commit / Pre-commit Hooks"},{"context":"Code-style / Code Style Enforcement"},{"context":"Dependency-check / Dependency Validation"},{"context":"Test / test (3.11)"}]}' \
  -f enforce_admins='false' \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"require_code_owner_reviews":true,"dismiss_stale_reviews":true,"require_last_push_approval":true}' \
  -f restrictions='null' \
  -f allow_force_pushes='false' \
  -f allow_deletions='false' \
  -f required_linear_history='true'
```

### Option 3: Terraform (Infrastructure as Code)

Create `terraform/github_branch_protection.tf`:

```hcl
resource "github_branch_protection" "main" {
  repository_id          = github_repository.mgx.id
  branch                 = "main"

  required_status_checks {
    strict = true
    contexts = [
      "Linting / Code Quality Checks",
      "Security-scan / Security Vulnerability Scan",
      "Pre-commit / Pre-commit Hooks",
      "Code-style / Code Style Enforcement",
      "Dependency-check / Dependency Validation",
      "Test / test (3.11)"
    ]
  }

  required_pull_request_reviews {
    required_approving_review_count = 1
    require_code_owner_reviews      = true
    dismiss_stale_reviews           = true
    require_last_push_approval      = true
  }

  enforce_admins = false

  allow_force_pushes = false
  allow_deletions   = false

  require_linear_history = true
}
```

---

## Status Check Explanation

### Quality Gates Checks

| Check | Description | Required on Main | Required on Develop |
|-------|-------------|------------------|---------------------|
| Linting / Code Quality Checks | Ruff, Black, MyPy, Bandit | ✅ Yes | ✅ Yes |
| Security-scan / Security Vulnerability Scan | pip-audit, safety, gitleaks | ✅ Yes | ✅ Yes |
| Pre-commit / Pre-commit Hooks | Pre-commit validation | ✅ Yes | ✅ Yes |
| Code-style / Code Style Enforcement | isort, TODO checks | ✅ Yes | ✅ Yes |
| Dependency-check / Dependency Validation | Requirements validation | ✅ Yes | ✅ Yes |

### Test Suite Checks

| Check | Description | Required on Main |
|-------|-------------|-----------------|
| Test / test (3.9) | Unit & integration tests on Python 3.9 | ✅ Yes |
| Test / test (3.10) | Unit & integration tests on Python 3.10 | ✅ Yes |
| Test / test (3.11) | Unit & integration tests on Python 3.11 | ✅ Yes |
| Test / test (3.12) | Unit & integration tests on Python 3.12 | ✅ Yes |

---

## Coverage Enforcement

### Enforcing 80% Coverage

The `.github/workflows/tests.yml` workflow already checks for >= 80% coverage. To enforce it in branch protection:

```yaml
required_status_checks:
  checks:
    - context: "Test / test (3.11)"
    - context: "coverage-report / Generate coverage report"
```

### Coverage Exceptions

If coverage must be temporarily lowered:

1. Update `PHASE1_IMPLEMENTATION_STATUS.md`
2. Document the reason and target restoration date
3. Add a comment in the PR explaining the exception

---

## Bypassing Branch Protection (Emergency Only)

### Admin Override

In emergencies, admins can bypass branch protection:

```bash
# Force push (requires admin access)
git push --force-with-lease origin main

# Or merge directly in GitHub UI (requires admin access)
```

### Emergency Bypass Process

1. Document the emergency reason in a GitHub issue
2. Get approval from at least 2 other maintainers
3. Make the bypass
4. Create a follow-up PR to restore protection
5. Update the emergency issue with resolution

---

## Best Practices

### 1. Review Requirements

- Require at least 1 approval for `main` branch
- Require code owner reviews for modified directories
- Dismiss stale reviews when new commits are pushed

### 2. Status Checks

- Require all quality gates to pass
- Require tests on multiple Python versions
- Require minimum coverage (80%)

### 3. History

- Require linear history (no merge commits)
- This prevents messy git graphs
- Use rebase and squash merge

### 4. Security

- Enforce rules for all users (including admins)
- Prevent force pushes and deletions
- Require recent approval (disable last push approval for security-sensitive repos)

---

## Troubleshooting

### Check Status Not Passing

**Problem**: PR shows checks as "pending" or "failed"

**Solutions**:
1. Check the specific workflow run logs in the "Checks" tab
2. Ensure workflow files are committed (`.github/workflows/`)
3. Verify branch matches protected branch pattern
4. Check for workflow errors in the Actions tab

### Coverage Check Failing

**Problem**: Coverage check fails even though tests pass

**Solutions**:
1. Run tests locally: `pytest --cov=backend --cov-report=term-missing`
2. Check if coverage is below 80%
3. Add tests for uncovered code
4. Update `.coveragerc` if needed (to exclude generated code)

### Pre-commit Hook Failing

**Problem**: Pre-commit hooks pass locally but fail in CI

**Solutions**:
1. Ensure pre-commit is installed: `pre-commit install`
2. Update hooks: `pre-commit autoupdate`
3. Run locally: `pre-commit run --all-files`
4. Check for environment differences

---

## Monitoring

### Watch List

Monitor these metrics in GitHub Insights:

1. **Merge Frequency**: How often PRs are merged
2. **Review Time**: Average time from PR to merge
3. **Failed Checks**: How often checks fail
4. **Coverage Trend**: Test coverage over time

### Alerts

Set up alerts for:
- Branch protection rules disabled
- Check failures on main branch
- Coverage drops below 80%
- Security vulnerabilities found

---

## Summary

Branch protection rules are critical for maintaining code quality and security. With these rules in place:

✅ All code passes linting and formatting
✅ Security scans run on every PR
✅ Test coverage is maintained at 80%+
✅ Code is reviewed before merging
✅ Linear history is maintained

This ensures that Phase 1 quality gates are enforced and the codebase remains production-ready.
