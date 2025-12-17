# -*- coding: utf-8 -*-
"""backend.routers.secrets

Secret management API endpoints for secure storage, retrieval, rotation, and audit.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.deps import get_session, require_permission
from backend.db.models.enums import SecretType, SecretRotationPolicy, PermissionResource, PermissionAction
from backend.schemas import (
    SecretCreateRequest, SecretUpdateRequest, SecretResponse, SecretMetadataResponse,
    SecretRotationRequest, SecretListResponse, SecretAuditLogResponse, SecretStatisticsResponse
)
from backend.services.secrets.manager import get_secret_manager, SecretManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/secrets", tags=["secrets"])


@router.post(
    "/workspaces/{workspace_id}/secrets",
    response_model=SecretResponse,
    dependencies=[Depends(require_permission("secrets", "create"))]
)
async def create_secret(
    workspace_id: str,
    request: SecretCreateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.CREATE))
):
    """Create a new secret in the workspace."""
    try:
        secret_manager = await get_secret_manager(session)
        
        # Extract user context
        user_id = user_context.get("user_id")
        
        secret = await secret_manager.create_secret(
            workspace_id=workspace_id,
            request=request,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        logger.info(f"Created secret '{secret.name}' in workspace {workspace_id}")
        return secret
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create secret: {e}")
        raise HTTPException(status_code=500, detail="Failed to create secret")


@router.get(
    "/workspaces/{workspace_id}/secrets",
    response_model=SecretListResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def list_secrets(
    workspace_id: str,
    secret_type: Optional[SecretType] = Query(None, description="Filter by secret type"),
    is_rotation_due: Optional[bool] = Query(None, description="Filter by rotation due status"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """List secrets in a workspace (metadata only, no values)."""
    try:
        secret_manager = await get_secret_manager(session)
        
        secrets = await secret_manager.list_secrets(
            workspace_id=workspace_id,
            secret_type=secret_type,
            is_rotation_due=is_rotation_due,
            is_active=is_active,
            tags=tags,
            limit=limit,
            offset=offset
        )
        
        return {
            "secrets": [SecretMetadataResponse.from_secret_metadata(secret) for secret in secrets],
            "total": len(secrets),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to list secrets: {e}")
        raise HTTPException(status_code=500, detail="Failed to list secrets")


@router.get(
    "/workspaces/{workspace_id}/secrets/{secret_id}",
    response_model=SecretResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def get_secret(
    workspace_id: str,
    secret_id: str,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """Get a secret by ID (includes encrypted value)."""
    try:
        secret_manager = await get_secret_manager(session)
        
        user_id = user_context.get("user_id")
        
        secret = await secret_manager.get_secret(
            workspace_id=workspace_id,
            secret_id=secret_id,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        return secret
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get secret {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get secret")


@router.get(
    "/workspaces/{workspace_id}/secrets/{secret_id}/value",
    response_model=dict,  # Returns {"value": "decrypted_secret_value"}
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def get_secret_value(
    workspace_id: str,
    secret_id: str,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """Get the decrypted value of a secret."""
    try:
        secret_manager = await get_secret_manager(session)
        
        user_id = user_context.get("user_id")
        
        value = await secret_manager.get_secret_value(
            workspace_id=workspace_id,
            secret_id=secret_id,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        return {"value": value}
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get secret value {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get secret value")


@router.get(
    "/workspaces/{workspace_id}/secrets/by-name/{name}",
    response_model=SecretResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def get_secret_by_name(
    workspace_id: str,
    name: str,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """Get a secret by name."""
    try:
        secret_manager = await get_secret_manager(session)
        
        user_id = user_context.get("user_id")
        
        secret = await secret_manager.get_secret_by_name(
            workspace_id=workspace_id,
            name=name,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        if not secret:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        
        return secret
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get secret by name '{name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to get secret by name")


@router.patch(
    "/workspaces/{workspace_id}/secrets/{secret_id}",
    response_model=SecretResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.UPDATE))]
)
async def update_secret(
    workspace_id: str,
    secret_id: str,
    request: SecretUpdateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.UPDATE))
):
    """Update a secret (metadata or value)."""
    try:
        secret_manager = await get_secret_manager(session)
        
        user_id = user_context.get("user_id")
        
        secret = await secret_manager.update_secret(
            workspace_id=workspace_id,
            secret_id=secret_id,
            request=request,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        logger.info(f"Updated secret '{secret.name}' in workspace {workspace_id}")
        return secret
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update secret {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update secret")


@router.post(
    "/workspaces/{workspace_id}/secrets/{secret_id}/rotate",
    response_model=SecretResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.UPDATE))]
)
async def rotate_secret(
    workspace_id: str,
    secret_id: str,
    request: SecretRotationRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.UPDATE))
):
    """Rotate a secret with a new value."""
    try:
        secret_manager = await get_secret_manager(session)
        
        user_id = user_context.get("user_id")
        
        secret = await secret_manager.rotate_secret(
            workspace_id=workspace_id,
            secret_id=secret_id,
            new_value=request.new_value,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        logger.info(f"Rotated secret '{secret.name}' in workspace {workspace_id}")
        return secret
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rotate secret {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to rotate secret")


@router.delete(
    "/workspaces/{workspace_id}/secrets/{secret_id}",
    dependencies=[Depends(require_permission("secrets", PermissionAction.DELETE))]
)
async def delete_secret(
    workspace_id: str,
    secret_id: str,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.DELETE))
):
    """Delete a secret (soft delete - marks as inactive)."""
    try:
        secret_manager = await get_secret_manager(session)
        
        user_id = user_context.get("user_id")
        
        success = await secret_manager.delete_secret(
            workspace_id=workspace_id,
            secret_id=secret_id,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        if success:
            logger.info(f"Deleted secret {secret_id} in workspace {workspace_id}")
            return {"message": "Secret deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete secret")
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete secret {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete secret")


@router.get(
    "/workspaces/{workspace_id}/secrets/rotation-due",
    response_model=List[SecretMetadataResponse],
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def get_rotation_due_secrets(
    workspace_id: str,
    days_ahead: int = Query(7, ge=1, le=365, description="Days ahead to check for rotation due"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """Get secrets that are due for rotation."""
    try:
        secret_manager = await get_secret_manager(session)
        
        secrets = await secret_manager.get_rotation_due_secrets(
            workspace_id=workspace_id,
            days_ahead=days_ahead
        )
        
        return [SecretMetadataResponse.from_secret_metadata(secret) for secret in secrets]
        
    except Exception as e:
        logger.error(f"Failed to get rotation due secrets: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rotation due secrets")


@router.get(
    "/workspaces/{workspace_id}/secrets/{secret_id}/audit",
    response_model=SecretAuditLogResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def get_secret_audit_logs(
    workspace_id: str,
    secret_id: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of audit logs"),
    offset: int = Query(0, ge=0, description="Number of audit logs to skip"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """Get audit logs for a specific secret."""
    try:
        secret_manager = await get_secret_manager(session)
        
        audit_logs = await secret_manager.get_secret_audit_logs(
            secret_id=secret_id,
            limit=limit,
            offset=offset
        )
        
        return {
            "audit_logs": [log for log in audit_logs],
            "total": len(audit_logs),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get audit logs for secret {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get audit logs")


@router.get(
    "/workspaces/{workspace_id}/secrets/statistics",
    response_model=SecretStatisticsResponse,
    dependencies=[Depends(require_permission("secrets", PermissionAction.READ))]
)
async def get_secret_statistics(
    workspace_id: str,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("secrets", PermissionAction.READ))
):
    """Get statistics about secrets in a workspace."""
    try:
        secret_manager = await get_secret_manager(session)
        
        stats = await secret_manager.get_secret_statistics(workspace_id=workspace_id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get secret statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get secret statistics")


# Admin endpoints for encryption management
@router.post(
    "/admin/encryption/rotate-key",
    dependencies=[Depends(require_permission("settings", PermissionAction.MANAGE))]
)
async def rotate_encryption_key(
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("settings", PermissionAction.MANAGE))
):
    """Rotate encryption keys across all backends (admin only)."""
    try:
        from backend.services.secrets.encryption import encryption_service
        
        results = await encryption_service.rotate_encryption_key()
        
        return {
            "message": "Encryption key rotation completed",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to rotate encryption key: {e}")
        raise HTTPException(status_code=500, detail="Failed to rotate encryption key")


@router.get(
    "/admin/encryption/health",
    dependencies=[Depends(require_permission("settings", PermissionAction.READ))]
)
async def get_encryption_health(
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("settings", PermissionAction.READ))
):
    """Get health status of encryption backends (admin only)."""
    try:
        from backend.services.secrets.encryption import encryption_service
        
        health_status = await encryption_service.get_backend_health()
        
        return {
            "current_backend": encryption_service.current_backend,
            "health_status": health_status
        }
        
    except Exception as e:
        logger.error(f"Failed to get encryption health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get encryption health")


@router.post(
    "/admin/encryption/generate-key",
    dependencies=[Depends(require_permission("settings", PermissionAction.MANAGE))]
)
async def generate_fernet_key():
    """Generate a new Fernet encryption key (admin only)."""
    try:
        from backend.services.secrets.encryption import encryption_service
        
        key = await encryption_service.generate_fernet_key()
        
        return {
            "encryption_key": key,
            "backend": "fernet",
            "note": "Keep this key secure and use it to initialize the encryption service"
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Fernet key: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate encryption key")