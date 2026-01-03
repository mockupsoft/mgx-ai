# Multi-Tenant Isolation Test Design

**Version**: 1.0  
**Last Updated**: 2025-01-03  
**Owner**: Security/Backend Team

## Overview

This document defines the comprehensive test design for validating multi-tenant isolation in the MGX-AI platform. The goal is to ensure that workspaces are completely isolated from each other in terms of data access, authentication, resource quotas, and memory usage.

## Isolation Requirements

### Security Principle: Complete Tenant Isolation

**Core Requirements**:
1. **Data Isolation**: Workspace A cannot access Workspace B's data
2. **Authentication Isolation**: Tokens are workspace-scoped
3. **Resource Quota Isolation**: Each workspace has independent quotas
4. **Memory Isolation**: One workspace cannot affect another's memory
5. **Rate Limit Isolation**: Per-workspace rate limits enforced
6. **Audit Log Isolation**: Each workspace has separate audit logs

## Test Categories

### 1. Data Isolation Tests

**Objective**: Verify that data is completely isolated between workspaces

**Test Scenarios**:

#### 1.1 Task Isolation
- ✅ Workspace A creates task → Only Workspace A can read it
- ✅ Workspace B cannot list Workspace A's tasks
- ✅ Workspace B cannot read Workspace A's task by ID
- ✅ Workspace B cannot update Workspace A's task
- ✅ Workspace B cannot delete Workspace A's task
- ✅ SQL queries always filter by workspace_id

#### 1.2 Agent Isolation
- ✅ Workspace A creates agent → Only Workspace A can access it
- ✅ Workspace B cannot list Workspace A's agents
- ✅ Workspace B cannot use Workspace A's agent
- ✅ Agent configurations are workspace-scoped

#### 1.3 Workspace Metadata Isolation
- ✅ Workspace A cannot see Workspace B's metadata
- ✅ Workspace A cannot access Workspace B's settings
- ✅ Workspace A cannot modify Workspace B's configuration

#### 1.4 Repository/Code Isolation
- ✅ Workspace A's code is not accessible to Workspace B
- ✅ Git credentials are workspace-scoped
- ✅ Repository access tokens are isolated

#### 1.5 Secret Isolation
- ✅ Workspace A's secrets not accessible to Workspace B
- ✅ API keys are workspace-scoped
- ✅ LLM provider credentials are isolated

#### 1.6 Artifact Isolation
- ✅ Generated artifacts are workspace-scoped
- ✅ File uploads are isolated
- ✅ Output files cannot be accessed cross-workspace

---

### 2. Authentication & Authorization Isolation Tests

**Objective**: Verify that authentication tokens are properly scoped to workspaces

**Test Scenarios**:

#### 2.1 Token Scope Validation
- ✅ User A's token for Workspace A cannot access Workspace B
- ✅ Token includes workspace_id in claims
- ✅ Token validation enforces workspace matching
- ✅ Expired tokens are rejected
- ✅ Revoked tokens are rejected

#### 2.2 Role-Based Access Control (RBAC)
- ✅ Admin in Workspace A is not admin in Workspace B
- ✅ Member in Workspace A has no access to Workspace B
- ✅ Viewer in Workspace A cannot read Workspace B data
- ✅ Roles are workspace-scoped, not global

#### 2.3 Cross-Workspace Access Attempts
- ✅ Direct API calls with wrong workspace_id fail
- ✅ Modified tokens with wrong workspace_id are rejected
- ✅ JWT tampering is detected and rejected
- ✅ SQL injection attempts fail

#### 2.4 API Key Isolation
- ✅ API key for Workspace A cannot access Workspace B
- ✅ API key validation checks workspace ownership
- ✅ Multiple API keys per workspace work correctly

---

### 3. Resource Quota Isolation Tests

**Objective**: Verify that resource quotas are enforced per workspace

**Test Scenarios**:

#### 3.1 Task Quota Isolation
- ✅ Workspace A hits task quota → only Workspace A is blocked
- ✅ Workspace B can still create tasks
- ✅ Quota counters are workspace-specific
- ✅ Quota reset works per workspace

#### 3.2 Storage Quota Isolation
- ✅ Workspace A hits storage quota → only Workspace A is blocked
- ✅ Workspace B's storage is unaffected
- ✅ File uploads respect per-workspace quotas

#### 3.3 Rate Limit Isolation
- ✅ Workspace A hits rate limit → only Workspace A is throttled
- ✅ Workspace B continues at full rate
- ✅ Rate limit buckets are workspace-specific
- ✅ Burst limits are enforced per workspace

#### 3.4 Compute Quota Isolation
- ✅ Workspace A exhausts compute quota → only Workspace A affected
- ✅ Workspace B's compute resources unaffected
- ✅ CPU/memory quotas enforced per workspace

---

### 4. Memory Isolation Tests

**Objective**: Verify that memory usage in one workspace doesn't affect others

**Test Scenarios**:

#### 4.1 Memory Allocation Isolation
- ✅ Workspace A allocates large memory → Workspace B unaffected
- ✅ Memory limits enforced per workspace
- ✅ OOM in Workspace A doesn't crash Workspace B

#### 4.2 Cache Isolation
- ✅ Cache keys include workspace_id
- ✅ Workspace A's cache entries not accessible to Workspace B
- ✅ Cache eviction in Workspace A doesn't affect Workspace B
- ✅ Cache TTL is workspace-scoped

#### 4.3 Session Isolation
- ✅ Sessions are workspace-scoped
- ✅ Workspace A's session data not accessible to Workspace B
- ✅ Session cleanup doesn't affect other workspaces

#### 4.4 Memory Leak Isolation
- ✅ Memory leak in Workspace A doesn't affect Workspace B
- ✅ Workspace-level memory monitoring works
- ✅ Memory cleanup is workspace-scoped

---

## Test Implementation Strategy

### Test Environment Setup

**Test Workspaces**:
```python
# Create multiple test workspaces
WORKSPACE_A = create_test_workspace("workspace-a")
WORKSPACE_B = create_test_workspace("workspace-b")
WORKSPACE_C = create_test_workspace("workspace-c")

# Create users with different roles per workspace
USER_A_ADMIN = create_user(WORKSPACE_A, role="admin")
USER_B_ADMIN = create_user(WORKSPACE_B, role="admin")
USER_AB_MEMBER = create_user([WORKSPACE_A, WORKSPACE_B], role="member")
```

### Test Data Preparation

**Pre-populate Test Data**:
```python
# Workspace A
- 100 tasks
- 10 agents
- 5 repositories
- 20 secrets
- 50 artifacts

# Workspace B
- 150 tasks
- 15 agents
- 8 repositories
- 30 secrets
- 75 artifacts
```

### Test Execution Approach

1. **Unit Tests**: Test individual isolation functions
2. **Integration Tests**: Test end-to-end isolation scenarios
3. **Security Tests**: Attempt to bypass isolation
4. **Load Tests**: Verify isolation under high load
5. **Chaos Tests**: Test isolation during failures

---

## Test Cases

### TC-001: Task Data Isolation

**Priority**: P0 - Critical  
**Type**: Integration Test

**Preconditions**:
- Workspace A and B exist
- Workspace A has 10 tasks
- Workspace B has 5 tasks

**Test Steps**:
1. Authenticate as User A (Workspace A)
2. List all tasks
3. Verify only Workspace A's 10 tasks returned
4. Authenticate as User B (Workspace B)
5. Attempt to access Workspace A's task by ID
6. Verify 404 or 403 error

**Expected Result**:
- ✅ User A sees only Workspace A's tasks
- ✅ User B cannot access Workspace A's tasks
- ✅ Error response is appropriate (404/403)

**Actual Result**: [To be filled during test execution]

**Status**: 🔴 Not Run / 🟡 Failed / 🟢 Passed

---

### TC-002: Authentication Token Isolation

**Priority**: P0 - Critical  
**Type**: Security Test

**Preconditions**:
- Workspace A and B exist
- User A has valid token for Workspace A

**Test Steps**:
1. Obtain token for User A (Workspace A)
2. Attempt to access Workspace B's endpoints with User A's token
3. Modify token's workspace_id claim to Workspace B
4. Attempt to access Workspace B's endpoints

**Expected Result**:
- ✅ Original token cannot access Workspace B
- ✅ Modified token is rejected (signature invalid)
- ✅ Error logged in security audit log

**Actual Result**: [To be filled during test execution]

**Status**: 🔴 Not Run / 🟡 Failed / 🟢 Passed

---

### TC-003: Quota Isolation

**Priority**: P0 - Critical  
**Type**: Integration Test

**Preconditions**:
- Workspace A has task quota of 100
- Workspace A currently has 95 tasks
- Workspace B has task quota of 100
- Workspace B currently has 10 tasks

**Test Steps**:
1. Authenticate as User A
2. Create 10 tasks (will exceed quota at task 6)
3. Verify quota exceeded error after task 5
4. Authenticate as User B
5. Create task successfully
6. Verify Workspace B unaffected by Workspace A's quota

**Expected Result**:
- ✅ Workspace A blocked at quota limit
- ✅ Workspace B continues normally
- ✅ Quota counters are independent

**Actual Result**: [To be filled during test execution]

**Status**: 🔴 Not Run / 🟡 Failed / 🟢 Passed

---

### TC-004: Cache Key Isolation

**Priority**: P1 - High  
**Type**: Integration Test

**Preconditions**:
- Redis cache is empty
- Workspace A and B exist

**Test Steps**:
1. Authenticate as User A
2. Access cached resource (e.g., agent list)
3. Verify cache key includes workspace_id
4. Authenticate as User B
5. Access same resource type
6. Verify separate cache key created
7. Modify Workspace A's cache directly
8. Verify Workspace B's cache unaffected

**Expected Result**:
- ✅ Cache keys are namespaced by workspace
- ✅ Workspace B's cache is independent
- ✅ No cache key collisions

**Actual Result**: [To be filled during test execution]

**Status**: 🔴 Not Run / 🟡 Failed / 🟢 Passed

---

### TC-005: SQL Injection - Workspace Bypass Attempt

**Priority**: P0 - Critical  
**Type**: Security Test

**Preconditions**:
- Workspace A and B exist
- User A authenticated for Workspace A

**Test Steps**:
1. Authenticate as User A
2. Attempt SQL injection to bypass workspace filter:
   ```
   GET /api/v1/tasks?workspace_id=' OR '1'='1
   GET /api/v1/tasks/1' OR workspace_id='workspace-b
   ```
3. Verify attempts are blocked
4. Check SQL query logs for proper parameterization

**Expected Result**:
- ✅ SQL injection attempts fail
- ✅ Only Workspace A data returned
- ✅ Security event logged

**Actual Result**: [To be filled during test execution]

**Status**: 🔴 Not Run / 🟡 Failed / 🟢 Passed

---

### TC-006: Memory Isolation Under Load

**Priority**: P1 - High  
**Type**: Load Test

**Preconditions**:
- Workspace A and B exist
- System under normal load

**Test Steps**:
1. Authenticate as User A
2. Create 1000 tasks in rapid succession (high memory usage)
3. Monitor Workspace A's memory usage
4. Simultaneously, User B creates tasks
5. Monitor Workspace B's task creation success rate
6. Verify Workspace B's latency remains acceptable

**Expected Result**:
- ✅ Workspace A's high memory usage doesn't affect Workspace B
- ✅ Workspace B's latency < 2x baseline
- ✅ No OOM errors in either workspace

**Actual Result**: [To be filled during test execution]

**Status**: 🔴 Not Run / 🟡 Failed / 🟢 Passed

---

## Automated Test Suite Structure

```
tests/isolation/
├── __init__.py
├── conftest.py                      # Shared fixtures
├── test_data_isolation.py           # TC-001 and related
├── test_auth_isolation.py           # TC-002 and related
├── test_quota_isolation.py          # TC-003 and related
├── test_memory_isolation.py         # TC-004, TC-006
├── test_security_bypass.py          # TC-005 and related
├── test_rate_limit_isolation.py     # Rate limiting tests
├── test_cache_isolation.py          # Cache isolation tests
└── test_production_validation.py    # Production smoke tests
```

---

## Test Metrics and Reporting

### Test Coverage Metrics

| Category | Test Cases | Coverage |
|----------|------------|----------|
| Data Isolation | 15 | 100% |
| Auth Isolation | 12 | 100% |
| Quota Isolation | 8 | 100% |
| Memory Isolation | 6 | 100% |
| **Total** | **41** | **100%** |

### Pass/Fail Criteria

**Critical (P0)**: All tests must pass - blocking issue if any fail  
**High (P1)**: 95%+ pass rate required  
**Medium (P2)**: 90%+ pass rate required

### Regression Testing

- Run full isolation test suite on every PR
- Run security tests nightly
- Run load-based isolation tests weekly

---

## Security Audit Checklist

### Code Review Checklist

- [ ] All database queries filter by workspace_id
- [ ] All API endpoints validate workspace ownership
- [ ] Cache keys include workspace_id namespace
- [ ] Authentication tokens include workspace claims
- [ ] Rate limits are workspace-scoped
- [ ] Audit logs include workspace_id
- [ ] Error messages don't leak workspace info
- [ ] Foreign keys enforce workspace relationships

### Database Schema Audit

- [ ] All tables have workspace_id column (where applicable)
- [ ] Foreign keys include workspace_id
- [ ] Indexes include workspace_id as first column
- [ ] Row-level security policies defined (if using PostgreSQL RLS)
- [ ] Materialized views filtered by workspace_id

### API Endpoint Audit

- [ ] All endpoints require authentication
- [ ] All endpoints validate workspace_id from token
- [ ] No endpoints accept workspace_id from request body
- [ ] workspace_id extracted from validated token only
- [ ] Cross-workspace queries explicitly blocked

---

## Production Validation Plan

### Smoke Tests in Production

Run these tests against production (with test workspaces):

1. **Data Isolation Smoke Test** (5 min)
   - Create task in Workspace A
   - Verify Workspace B cannot access
   - Delete test data

2. **Auth Isolation Smoke Test** (5 min)
   - Obtain token for Workspace A
   - Attempt to access Workspace B
   - Verify rejection

3. **Quota Smoke Test** (5 min)
   - Create task near quota limit
   - Verify quota enforcement
   - Verify other workspace unaffected

**Frequency**: Daily at 2 AM UTC  
**Alert Channel**: #security-alerts  
**Escalation**: Page on-call if any test fails

---

## Compliance and Audit

### Regulatory Requirements

**SOC 2 Type II**:
- ✅ Multi-tenant isolation documented
- ✅ Isolation tested and verified
- ✅ Test results archived for audit

**GDPR**:
- ✅ Data isolation ensures data controller separation
- ✅ Right to erasure scoped to workspace
- ✅ Data export scoped to workspace

**HIPAA** (if applicable):
- ✅ PHI isolated by workspace (tenant)
- ✅ Access logs separated by workspace
- ✅ Encryption keys scoped to workspace

### Audit Evidence

- Automated test results (daily)
- Manual penetration test reports (quarterly)
- Code review records (per PR)
- Production monitoring dashboards
- Security incident reports (if any)

---

## References

- [Multi-Tenant Architecture](/docs/architecture/multi-tenant-architecture.md)
- [Security Review](/docs/isolation/isolation-security-review.md)
- [RBAC Documentation](/docs/RBAC.md)
- [Database Schema](/docs/DATABASE.md)

---

**Next Steps**:

1. Implement automated test suite
2. Run tests in staging environment
3. Fix any identified issues
4. Run security penetration tests
5. Validate in production with test workspaces
6. Document results for compliance audit
