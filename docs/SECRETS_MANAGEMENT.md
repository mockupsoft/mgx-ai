# Secret Management & Encryption System

## Overview

The Secret Management & Encryption System provides secure storage, encryption, and rotation of sensitive data such as API keys, database credentials, and OAuth tokens. This system replaces the previous practice of storing secrets as plaintext in environment files with a comprehensive encrypted storage solution.

## Features

- **Multi-Backend Encryption**: Support for Fernet, AWS KMS, and HashiCorp Vault
- **Automatic Secret Rotation**: Configurable rotation policies (30, 60, 90, 180, 365 days)
- **Comprehensive Audit Trail**: All secret access and operations are logged
- **Workspace Isolation**: Secrets are isolated by workspace for multi-tenancy
- **Fine-Grained Access Control**: Integration with RBAC system
- **API Integration**: RESTful API for all secret operations
- **Environment Variable Injection**: Inject secrets into application environment

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────┤
│                Secret Management Service                     │
├─────────────────────────────────────────────────────────────┤
│              Encryption Service (Multi-Backend)             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Fernet    │  │  AWS KMS    │  │ HashiCorp   │        │
│  │  (Default)  │  │             │  │   Vault     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│                  Database Layer                             │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │   Secrets   │  │ Secret      │                          │
│  │   Table     │  │ Audits      │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### Secrets Table
- `id`: Unique identifier (UUID)
- `workspace_id`: Workspace association
- `name`: Secret name (e.g., "GITHUB_TOKEN")
- `secret_type`: Type of secret (api_key, database_cred, oauth_token, etc.)
- `encrypted_value`: Encrypted secret value
- `rotation_policy`: Rotation policy (manual, auto_30_days, etc.)
- `last_rotated_at`: Last rotation timestamp
- `rotation_due_at`: Next rotation due date
- `usage`: Description of secret usage
- `tags`: JSON array of tags for organization
- `is_active`: Whether secret is active
- `created_by_user_id`: User who created the secret
- `updated_by_user_id`: User who last updated the secret

### Secret Audits Table
- `id`: Unique identifier (UUID)
- `secret_id`: Associated secret
- `action`: Action performed (created, accessed, rotated, deleted, etc.)
- `user_id`: User who performed the action
- `ip_address`: IP address of the request
- `user_agent`: User agent of the request
- `details`: JSON details of the operation
- `success`: Whether the operation was successful

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# Secret Management Configuration
SECRET_ENCRYPTION_BACKEND=fernet  # fernet | vault | aws_kms
SECRET_ENCRYPTION_KEY=            # Base64-encoded encryption key (for Fernet)
VAULT_URL=                        # Vault URL (for Vault backend)
VAULT_TOKEN=                      # Vault token (for Vault backend)
VAULT_MOUNT_POINT=secret          # Vault mount point
AWS_KMS_KEY_ID=                   # AWS KMS key ID (for AWS KMS backend)
AWS_REGION=us-east-1              # AWS region
SECRET_ROTATION_DAYS=90           # Default rotation period
ENABLE_SECRET_AUDIT_LOGGING=true  # Enable audit logging
SECRET_AUDIT_RETENTION_DAYS=365   # Audit log retention
```

### Fernet Backend Configuration

The Fernet backend is the default and requires no additional setup:

```python
# For development - automatic key generation
SECRET_ENCRYPTION_BACKEND=fernet
SECRET_ENCRYPTION_KEY=  # Will be auto-generated

# For production - manual key generation
SECRET_ENCRYPTION_BACKEND=fernet
SECRET_ENCRYPTION_KEY=<your-base64-encoded-key>
```

To generate a Fernet key:
```bash
curl -X POST /api/secrets/admin/encryption/generate-key
```

### AWS KMS Backend Configuration

For production use with AWS KMS:

```bash
SECRET_ENCRYPTION_BACKEND=aws_kms
AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/your-key-id
AWS_REGION=us-east-1
```

### HashiCorp Vault Backend Configuration

For advanced use with HashiCorp Vault:

```bash
SECRET_ENCRYPTION_BACKEND=vault
VAULT_URL=https://your-vault-instance.com
VAULT_TOKEN=your-vault-token
VAULT_MOUNT_POINT=secret
VAULT_NAMESPACE=  # Optional namespace for multi-tenancy
```

## API Endpoints

### Secret Management

#### Create Secret
```http
POST /api/secrets/workspaces/{workspace_id}/secrets
Content-Type: application/json

{
  "name": "GITHUB_TOKEN",
  "secret_type": "oauth_token",
  "value": "ghp_...",
  "usage": "GitHub API access for repository operations",
  "rotation_policy": "auto_90_days",
  "tags": ["github", "api", "development"],
  "metadata": {
    "scopes": ["repo", "user"]
  }
}
```

#### List Secrets
```http
GET /api/secrets/workspaces/{workspace_id}/secrets?limit=10&offset=0
```

#### Get Secret Value
```http
GET /api/secrets/workspaces/{workspace_id}/secrets/{secret_id}/value
```

#### Update Secret
```http
PATCH /api/secrets/workspaces/{workspace_id}/secrets/{secret_id}
Content-Type: application/json

{
  "value": "new-secret-value",
  "usage": "Updated description",
  "tags": ["github", "api", "production"]
}
```

#### Rotate Secret
```http
POST /api/secrets/workspaces/{workspace_id}/secrets/{secret_id}/rotate
Content-Type: application/json

{
  "new_value": "new-rotated-secret-value"
}
```

#### Delete Secret
```http
DELETE /api/secrets/workspaces/{workspace_id}/secrets/{secret_id}
```

### Secret Rotation Management

#### Get Rotation Due Secrets
```http
GET /api/secrets/workspaces/{workspace_id}/secrets/rotation-due?days_ahead=7
```

### Audit Trail

#### Get Secret Audit Logs
```http
GET /api/secrets/workspaces/{workspace_id}/secrets/{secret_id}/audit?limit=50
```

#### Get Secret Statistics
```http
GET /api/secrets/workspaces/{workspace_id}/secrets/statistics
```

### Admin Operations

#### Rotate Encryption Keys
```http
POST /api/secrets/admin/encryption/rotate-key
```

#### Get Encryption Health
```http
GET /api/secrets/admin/encryption/health
```

#### Generate Fernet Key
```http
POST /api/secrets/admin/encryption/generate-key
```

## Usage Examples

### Python Integration

```python
from backend.services.secrets.manager import SecretManager, SecretCreateRequest
from backend.services.secrets.encryption import encryption_service
from backend.db.models.enums import SecretType, SecretRotationPolicy

# Initialize encryption service
await encryption_service.initialize(
    backend_type=SecretBackend.FERNET
)

# Create a secret
secret_request = SecretCreateRequest(
    name="DATABASE_PASSWORD",
    secret_type=SecretType.DATABASE_CREDENTIAL,
    value="super-secure-password",
    usage="Main database password for production",
    rotation_policy=SecretRotationPolicy.AUTO_90_DAYS,
    tags=["database", "production", "critical"]
)

secret_manager = SecretManager(session)
secret = await secret_manager.create_secret(
    workspace_id="workspace-123",
    request=secret_request,
    user_id="user-456"
)

# Retrieve secret value
secret_value = await secret_manager.get_secret_value(
    workspace_id="workspace-123",
    secret_id=secret.id,
    user_id="user-456"
)

# Rotate secret
await secret_manager.rotate_secret(
    workspace_id="workspace-123",
    secret_id=secret.id,
    new_value="new-rotated-password",
    user_id="user-456"
)
```

### Environment Variable Injection

```python
# Load secrets into environment variables
async def inject_secrets_to_environment(workspace_id: str):
    secret_manager = SecretManager(session)
    
    # Get all active secrets
    secrets = await secret_manager.list_secrets(workspace_id)
    
    for secret_metadata in secrets:
        # Get secret value
        secret_value = await secret_manager.get_secret_value(
            workspace_id, secret_metadata.id
        )
        
        # Set as environment variable
        os.environ[f"SECRET_{secret_metadata.name}"] = secret_value

# Use in application startup
async def startup_event():
    await inject_secrets_to_environment(workspace_id)
```

### FastAPI Integration

```python
from fastapi import APIRouter, Depends
from backend.services.secrets.manager import get_secret_manager
from backend.app.deps import require_permission

router = APIRouter()

@router.post("/deploy")
async def deploy_service(
    config: DeployConfig,
    secret_manager = Depends(get_secret_manager),
    user_context = Depends(require_permission("secrets", "read"))
):
    # Get required secrets
    api_key = await secret_manager.get_secret_value(
        workspace_id=config.workspace_id,
        secret_id=config.api_key_secret_id,
        user_id=user_context["user_id"]
    )
    
    # Use secret in deployment
    deploy_config = {
        "api_key": api_key,
        "endpoint": config.endpoint
    }
    
    return await deploy_service(deploy_config)
```

## Migration from .env Files

### Automatic Migration

For existing applications with `.env` files:

```bash
# Run migration script
python scripts/migrate_secrets_from_env.py
```

### Manual Migration

```python
# Example migration script
import os
from backend.services.secrets.manager import SecretManager
from backend.db.models.enums import SecretType

async def migrate_env_secrets():
    # Read existing environment variables
    env_vars = os.environ
    
    # Identify potential secrets
    potential_secrets = {}
    for key, value in env_vars.items():
        if any(pattern in key.lower() for pattern in [
            'key', 'password', 'secret', 'token', 'credential'
        ]) and value:
            potential_secrets[key] = value
    
    # Create secrets in the system
    secret_manager = SecretManager(session)
    
    for env_name, secret_value in potential_secrets.items():
        # Determine secret type based on name
        secret_type = SecretType.API_KEY
        if 'password' in env_name.lower():
            secret_type = SecretType.DATABASE_CREDENTIAL
        elif 'token' in env_name.lower():
            secret_type = SecretType.OAUTH_TOKEN
        
        await secret_manager.create_secret(
            workspace_id="default",
            name=env_name,
            secret_type=secret_type,
            value=secret_value,
            usage=f"Migrated from environment variable {env_name}",
            rotation_policy=SecretRotationPolicy.MANUAL
        )
```

## Security Best Practices

### 1. Encryption Backend Selection

- **Development**: Use Fernet backend with auto-generated keys
- **Production**: Use AWS KMS or HashiCorp Vault for enterprise security
- **Hybrid**: Use Fernet for less critical secrets, KMS/Vault for critical ones

### 2. Secret Rotation

```python
# Set appropriate rotation policies
rotation_policies = {
    "database_password": SecretRotationPolicy.AUTO_90_DAYS,
    "api_keys": SecretRotationPolicy.AUTO_30_DAYS,
    "oauth_tokens": SecretRotationPolicy.AUTO_60_DAYS,
    "ssh_keys": SecretRotationPolicy.AUTO_180_DAYS,
    "jwt_secrets": SecretRotationPolicy.AUTO_90_DAYS
}
```

### 3. Access Control

- Use RBAC to restrict who can access secrets
- Implement least privilege principle
- Monitor secret access through audit logs
- Use service accounts for application access

### 4. Secret Naming Conventions

```python
# Recommended naming patterns
secret_names = [
    "DATABASE_PASSWORD",          # Database credentials
    "REDIS_PASSWORD",            # Cache credentials
    "GITHUB_TOKEN",              # API tokens
    "STRIPE_SECRET_KEY",         # Payment processor keys
    "JWT_SECRET_KEY",            # JWT signing secrets
    "ENCRYPTION_KEY_MASTER",     # Encryption keys
    "SMTP_PASSWORD",             # Email service credentials
    "AWS_ACCESS_KEY_ID",         # Cloud service credentials
    "OAUTH_CLIENT_SECRET"        # OAuth secrets
]
```

### 5. Monitoring and Alerting

```python
# Monitor for suspicious patterns
async def monitor_secret_access():
    audit_logs = await secret_manager.get_secret_audit_logs(
        secret_id=secret_id,
        limit=1000
    )
    
    # Check for unusual access patterns
    failed_attempts = sum(1 for log in audit_logs if not log.success)
    if failed_attempts > 5:
        # Alert security team
        await alert_security_team(
            f"High number of failed secret access attempts: {failed_attempts}"
        )
```

## Deployment

### Database Migration

```bash
# Run database migration
alembic upgrade head
```

### Application Configuration

1. Set secret management environment variables
2. Initialize encryption backend
3. Configure RBAC permissions for secret management
4. Test secret operations

### Monitoring Setup

```yaml
# Prometheus metrics (if applicable)
- secret_rotation_due_count
- secret_access_failure_rate
- encryption_backend_health
- secret_audit_log_volume
```

## Troubleshooting

### Common Issues

#### 1. Encryption Backend Not Initialized
```
Error: Encryption service not initialized
```
**Solution**: Ensure encryption backend is properly configured and initialized in application startup.

#### 2. Fernet Key Issues
```
Error: Invalid token - token is invalid
```
**Solution**: Check that the Fernet key is properly base64-encoded and consistent across all instances.

#### 3. Vault Connection Issues
```
Error: Vault authentication failed
```
**Solution**: Verify Vault URL, token, and network connectivity.

#### 4. Permission Denied
```
Error: User does not have permission to access secret
```
**Solution**: Check RBAC permissions and user role assignments.

#### 5. Database Connection Issues
```
Error: Unable to connect to database
```
**Solution**: Verify database connection string and credentials.

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging

logging.getLogger('backend.services.secrets').setLevel(logging.DEBUG)
logging.getLogger('backend.services.secrets.encryption').setLevel(logging.DEBUG)
logging.getLogger('backend.services.secrets.manager').setLevel(logging.DEBUG)
```

### Health Checks

```bash
# Check encryption backend health
curl -X GET /api/secrets/admin/encryption/health

# Expected response:
{
  "current_backend": "fernet",
  "health_status": {
    "fernet": {
      "healthy": true,
      "key_id": "fernet_20241217_143000",
      "last_check": "2024-12-17T14:30:00Z"
    }
  }
}
```

### Performance Tuning

1. **Indexing**: Ensure proper database indexes on frequently queried columns
2. **Caching**: Implement caching for frequently accessed secrets
3. **Connection Pooling**: Configure database connection pooling
4. **Audit Logging**: Batch audit log writes to reduce overhead

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review audit logs for operation details
3. Enable debug logging for detailed information
4. Contact the development team with specific error messages and context

## Security Contact

For security-related issues or concerns, contact the security team immediately through the designated channels.