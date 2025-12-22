# RBAC & Audit Logging System Documentation

## Overview

The RBAC (Role-Based Access Control) and Audit Logging System provides enterprise-grade security, access control, and compliance tracking for the multi-tenant workspace environment.

## Architecture

### Core Components

1. **RBAC Service** (`backend/services/auth/rbac.py`)
   - Permission checking and validation
   - Role management and assignment
   - FastAPI integration with dependency injection

2. **Audit Logger** (`backend/services/audit/logger.py`)
   - Comprehensive action tracking
   - Flexible filtering and export capabilities
   - Statistics and analytics

3. **Database Models** (`backend/db/models/entities.py`)
   - Role, UserRole, Permission, AuditLog models
   - Multi-tenant workspace isolation
   - Proper relationships and constraints

4. **API Layer** (`backend/routers/rbac.py`, `backend/routers/audit.py`)
   - Complete CRUD operations
   - Advanced filtering and pagination
   - Export and analytics endpoints

## Default Roles

### Admin Role
- **Purpose**: Full administrative access
- **Permissions**: All resources with all actions
- **Use Case**: System administrators, workspace owners
- **Default Permissions**:
  - `tasks:*` (create, read, update, delete, execute)
  - `workflows:*` (create, read, update, delete, execute)
  - `repositories:*` (create, read, update, delete, connect)
  - `agents:*` (create, read, update, delete, manage)
  - `settings:*` (read, update, manage)
  - `users:*` (create, read, update, delete, manage)
  - `audit:*` (read, manage)
  - `metrics:*` (read, manage)
  - `workspaces:*` (create, read, update, delete, manage)
  - `projects:*` (create, read, update, delete, manage)

### Developer Role
- **Purpose**: Development team member access
- **Permissions**: Development workflow operations
- **Use Case**: Software developers, engineers
- **Default Permissions**:
  - `tasks:create`, `tasks:read`, `tasks:update`, `tasks:execute`
  - `workflows:create`, `workflows:read`, `workflows:execute`
  - `repositories:read`, `repos:read`, `agents:read`
  - `metrics:read`, `projects:read`

### Viewer Role
- **Purpose**: Read-only access for stakeholders
- **Permissions**: Read operations only
- **Use Case**: Project stakeholders, observers, management
- **Default Permissions**:
  - `tasks:read`, `workflows:read`
  - `repositories:read`, `repos:read`, `agents:read`
  - `metrics:read`, `audit:read`, `projects:read`

### Auditor Role
- **Purpose**: Compliance and security audit access
- **Permissions**: Audit and compliance operations
- **Use Case**: Security auditors, compliance officers
- **Default Permissions**:
  - `audit:read`, `metrics:read`, `logs:read`
  - Read access to all audit-relevant resources

## Permission System

### Permission String Format
Permissions can be specified as strings in two formats:

1. **Wildcard Format**: `"resource:*"` (e.g., `"tasks:*"`)
2. **Specific Action**: `"resource:action"` (e.g., `"tasks:create"`)

### Available Resources
- `tasks` - Task management
- `workflows` - Workflow operations
- `repositories` - Repository connections
- `repos` - Repository operations
- `agents` - Agent management
- `settings` - System settings
- `users` - User management
- `audit` - Audit log access
- `metrics` - Metrics and analytics
- `workspaces` - Workspace management
- `projects` - Project management

### Available Actions
- `create` - Create new resources
- `read` - Read/view resources
- `update` - Modify existing resources
- `delete` - Remove resources
- `execute` - Execute/run operations
- `approve` - Approve operations
- `manage` - Administrative management
- `connect` - Connect to external services

### Permission Checking

#### Using FastAPI Dependency
```python
from backend.services.auth.rbac import require_permission

@router.get("/tasks")
async def list_tasks(
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("tasks", "read"))
):
    # Endpoint automatically requires tasks:read permission
    tasks = await get_tasks(session, user_context["workspace_id"])
    return tasks
```

#### Manual Permission Checking
```python
from backend.services.auth.rbac import get_rbac_service

rbac_service = await get_rbac_service()
has_permission = await rbac_service.check_permission(
    user_id=user_id,
    workspace_id=workspace_id,
    resource="tasks",
    action="create"
)
```

#### Role Checking
```python
from backend.services.auth.rbac import get_rbac_service

rbac_service = await get_rbac_service()
has_role = await rbac_service.has_role(
    user_id=user_id,
    workspace_id=workspace_id,
    role_name="developer"
)
```

## Audit Logging

### Audit Actions

The system tracks over 50 different action types:

#### User Management
- `USER_LOGIN`, `USER_LOGOUT`
- `USER_CREATED`, `USER_UPDATED`, `USER_DELETED`

#### Role and Permission Management
- `ROLE_CREATED`, `ROLE_UPDATED`, `ROLE_DELETED`
- `ROLE_ASSIGNED`, `ROLE_REVOKED`
- `PERMISSION_GRANTED`, `PERMISSION_REVOKED`

#### Workspace and Project Management
- `WORKSPACE_CREATED`, `WORKSPACE_UPDATED`, `WORKSPACE_DELETED`
- `PROJECT_CREATED`, `PROJECT_UPDATED`, `PROJECT_DELETED`

#### Task Management
- `TASK_CREATED`, `TASK_UPDATED`, `TASK_DELETED`
- `TASK_EXECUTED`, `TASK_RUN_STARTED`, `TASK_RUN_COMPLETED`

#### Workflow Operations
- `WORKFLOW_CREATED`, `WORKFLOW_UPDATED`, `WORKFLOW_DELETED`
- `WORKFLOW_EXECUTED`, `WORKFLOW_STEP_EXECUTED`

#### Security Events
- `UNAUTHORIZED_ACCESS_ATTEMPT`
- `SECURITY_VIOLATION_DETECTED`

### Audit Log Data

Each audit log entry includes:
- **User Context**: User ID, IP address, user agent
- **Action Details**: Action type, resource type, resource ID
- **Changes**: Before/after values for modifications
- **Status**: Success, failure, error, warning
- **Timing**: Execution time in milliseconds
- **Context**: Additional metadata

### Querying Audit Logs

#### Basic Query
```python
from backend.services.audit.logger import get_audit_logger

audit_logger = await get_audit_logger()
logs = await audit_logger.get_audit_trail(
    workspace_id=workspace_id,
    limit=50,
    offset=0
)
```

#### Filtered Query
```python
from backend.schemas import AuditLogFilter

filters = AuditLogFilter(
    user_id=user_id,
    action="TASK_CREATED",
    date_from=datetime(2024, 1, 1),
    date_to=datetime(2024, 12, 31)
)

logs = await audit_logger.get_audit_trail(
    workspace_id=workspace_id,
    filters=filters
)
```

#### Export Logs
```python
from backend.schemas import AuditLogExportRequest

export_request = AuditLogExportRequest(
    format="json",
    limit=1000,
    filters=filters
)

export_response = await audit_logger.export_audit_logs(
    workspace_id=workspace_id,
    export_request=export_request
)
```

## API Reference

### RBAC Endpoints

#### User Management
```http
POST /api/rbac/workspaces/{workspace_id}/users
Content-Type: application/json
X-User-ID: {admin_user_id}
X-Workspace-ID: {workspace_id}

{
  "user_id": "user_uuid",
  "role_id": "role_uuid"
}
```

```http
GET /api/rbac/workspaces/{workspace_id}/users/{user_id}/roles
X-User-ID: {user_id}
X-Workspace-ID: {workspace_id}
```

#### Role Management
```http
POST /api/rbac/workspaces/{workspace_id}/roles
Content-Type: application/json
X-User-ID: {admin_user_id}
X-Workspace-ID: {workspace_id}

{
  "name": "custom_role",
  "permissions": ["tasks:read", "workflows:execute"],
  "description": "Custom role description"
}
```

```http
GET /api/rbac/workspaces/{workspace_id}/roles
X-User-ID: {user_id}
X-Workspace-ID: {workspace_id}
```

#### Permission Checking
```http
POST /api/rbac/permissions/check
Content-Type: application/json
X-User-ID: {user_id}
X-Workspace-ID: {workspace_id}

{
  "user_id": "user_uuid",
  "workspace_id": "workspace_uuid",
  "resource": "tasks",
  "action": "create"
}
```

### Audit Endpoints

#### List Audit Logs
```http
GET /api/audit/workspaces/{workspace_id}/audit-logs?page=1&per_page=50&user_id=user_uuid&action=TASK_CREATED
X-User-ID: {user_id}
X-Workspace-ID: {workspace_id}
```

#### Export Audit Logs
```http
POST /api/audit/workspaces/{workspace_id}/audit-logs/export
Content-Type: application/json
X-User-ID: {user_id}
X-Workspace-ID: {workspace_id}

{
  "format": "json",
  "filters": {
    "action": "TASK_CREATED",
    "date_from": "2024-01-01T00:00:00",
    "date_to": "2024-12-31T23:59:59"
  }
}
```

#### Audit Statistics
```http
GET /api/audit/workspaces/{workspace_id}/audit-logs/statistics?date_range_days=30
X-User-ID: {user_id}
X-Workspace-ID: {workspace_id}
```

## Integration Examples

### Workspace Creation with Default Roles

```python
from backend.services.auth.default_roles import setup_workspace_default_roles
from backend.services.audit.logger import get_audit_logger

async def create_workspace_with_defaults(workspace_data, user_id):
    # Create workspace
    workspace = await create_workspace_in_db(workspace_data)
    
    # Setup default roles
    setup = DefaultRolesSetup()
    roles = await setup.setup_default_roles(workspace.id, session)
    
    # Log workspace creation
    audit_logger = await get_audit_logger()
    await audit_logger.log_action(
        user_id=user_id,
        workspace_id=workspace.id,
        action=AuditAction.WORKSPACE_CREATED,
        resource_type="workspace",
        resource_id=workspace.id,
        changes={"name": workspace.name, "slug": workspace.slug}
    )
    
    return workspace, roles
```

### Task Creation with Permission Check and Audit

```python
from backend.services.auth.rbac import require_permission
from backend.services.audit.logger import get_audit_logger

@router.post("/tasks")
async def create_task(
    task_data: TaskCreate,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("tasks", "create"))
):
    user_id = user_context["user_id"]
    workspace_id = user_context["workspace_id"]
    
    # Create task
    task = await create_task_in_db(session, task_data, workspace_id)
    
    # Log the action
    audit_logger = await get_audit_logger()
    await audit_logger.log_action(
        user_id=user_id,
        workspace_id=workspace_id,
        action=AuditAction.TASK_CREATED,
        resource_type="task",
        resource_id=task.id,
        changes={
            "name": task.name,
            "project_id": task.project_id,
            "status": task.status
        }
    )
    
    return task
```

### Permission-Based Resource Filtering

```python
from backend.services.auth.rbac import get_rbac_service

async def get_accessible_tasks(user_id, workspace_id):
    rbac_service = await get_rbac_service()
    
    # Check if user has broad task access
    if await rbac_service.check_permission(user_id, workspace_id, "tasks", "*"):
        return await get_all_tasks(workspace_id)
    
    # Otherwise, apply user-specific filtering
    user_roles = await rbac_service.get_user_roles(user_id, workspace_id)
    return await get_tasks_by_user_roles(workspace_id, user_roles)
```

## Security Best Practices

### 1. Principle of Least Privilege
- Grant only the minimum permissions required
- Use specific permissions instead of wildcards when possible
- Regularly review and audit user permissions

### 2. Regular Access Reviews
- Conduct quarterly permission reviews
- Monitor audit logs for unusual activity patterns
- Implement automated alerts for security events

### 3. Separation of Duties
- Use Auditor role for compliance oversight
- Separate Admin and Developer roles
- Implement approval workflows for sensitive operations

### 4. Audit Log Integrity
- Enable audit log immutability in production
- Regular backup of audit logs
- Monitor for audit log tampering attempts

### 5. Performance Considerations
- Use permission caching appropriately
- Index audit log queries by common filters
- Implement log rotation and cleanup policies

## Troubleshooting

### Common Issues

#### Permission Denied Errors
```json
{
  "detail": "Permission denied: tasks:create"
}
```
**Solution**: Check user roles and ensure they have the required permission.

#### Missing Audit Logs
**Check**: 
1. Audit logger service is running
2. Database connections are healthy
3. Log retention policies aren't too aggressive

#### Slow Permission Checks
**Solutions**:
1. Check cache configuration
2. Verify database indexes
3. Monitor query performance

### Performance Tuning

#### Cache Configuration
```python
# Adjust cache TTL for your use case
rbac_service._cache_ttl = 300  # 5 minutes (default)
```

#### Database Optimization
```sql
-- Ensure these indexes exist
CREATE INDEX idx_user_roles_user_workspace ON user_roles(user_id, workspace_id);
CREATE INDEX idx_audit_logs_workspace_timestamp ON audit_logs(workspace_id, created_at);
```

## Deployment

### Environment Variables
```bash
# RBAC Configuration
RBAC_CACHE_TTL=300
RBAC_ENABLE_CACHE=true

# Audit Logging
AUDIT_LOG_RETENTION_DAYS=365
AUDIT_ENABLE_EXPORT=true

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
```

### Database Migration
```bash
# Run RBAC migration
alembic upgrade rbac_audit_logging_001

# Verify tables created
psql -d database -c "\dt roles user_roles permissions audit_logs"
```

### Health Checks
```python
# Check RBAC service health
GET /health/rbac

# Check audit logging health
GET /health/audit

# Verify database connections
GET /health/database
```

## Monitoring and Alerting

### Key Metrics
- Permission check latency
- Audit log write rate
- Database query performance
- Cache hit/miss ratios

### Security Alerts
- Failed permission checks
- Unauthorized access attempts
- Unusual audit log patterns
- Role escalation attempts

### Compliance Reporting
```python
# Generate compliance report
report = await audit_logger.get_audit_statistics(
    workspace_id=workspace_id,
    date_range_days=90
)
```

This RBAC & Audit Logging system provides enterprise-grade security and compliance capabilities while maintaining performance and usability for multi-tenant workspace environments.