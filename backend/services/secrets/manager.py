# -*- coding: utf-8 -*-
"""backend.services.secrets.manager

Secret management service for secure storage, retrieval, rotation, and audit logging.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from sqlalchemy import and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models.entities import Secret, SecretAudit, Workspace
from backend.db.models.enums import (
    SecretType, SecretRotationPolicy, SecretAuditAction, SecretBackend
)
from backend.services.audit.logger import AuditLogger
from .encryption import encryption_service

logger = logging.getLogger(__name__)


class SecretCreateRequest:
    """Request model for creating secrets."""
    
    def __init__(
        self,
        name: str,
        secret_type: SecretType,
        value: str,
        usage: str = "",
        rotation_policy: SecretRotationPolicy = SecretRotationPolicy.MANUAL,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by_user_id: Optional[str] = None
    ):
        self.name = name
        self.secret_type = secret_type
        self.value = value
        self.usage = usage
        self.rotation_policy = rotation_policy
        self.tags = tags or []
        self.metadata = metadata or {}
        self.created_by_user_id = created_by_user_id


class SecretUpdateRequest:
    """Request model for updating secrets."""
    
    def __init__(
        self,
        value: Optional[str] = None,
        usage: Optional[str] = None,
        rotation_policy: Optional[SecretRotationPolicy] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        updated_by_user_id: Optional[str] = None
    ):
        self.value = value
        self.usage = usage
        self.rotation_policy = rotation_policy
        self.tags = tags or []
        self.metadata = metadata or {}
        self.updated_by_user_id = updated_by_user_id


class SecretMetadata:
    """Metadata representation of a secret (without encrypted value)."""
    
    def __init__(self, secret: Secret):
        self.id = secret.id
        self.name = secret.name
        self.secret_type = secret.secret_type
        self.usage = secret.usage
        self.rotation_policy = secret.rotation_policy
        self.last_rotated_at = secret.last_rotated_at
        self.rotation_due_at = secret.rotation_due_at
        self.created_by_user_id = secret.created_by_user_id
        self.updated_by_user_id = secret.updated_by_user_id
        self.created_at = secret.created_at
        self.updated_at = secret.updated_at
        self.is_active = secret.is_active
        self.tags = secret.tags or []
        self.metadata = secret.meta_data or {}
        self.is_rotation_due = secret.is_rotation_due


class SecretManager:
    """Service for managing encrypted secrets with rotation and audit logging."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_audit_logger(self) -> AuditLogger:
        """Get audit logger instance."""
        from ...db.engine import get_session_factory
        session_factory = await get_session_factory()
        return AuditLogger(session_factory)

    async def create_secret(
        self,
        workspace_id: str,
        request: SecretCreateRequest,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Secret:
        """Create a new encrypted secret."""
        try:
            # Validate workspace exists
            workspace = await self.session.get(Workspace, workspace_id)
            if not workspace:
                raise ValueError(f"Workspace {workspace_id} not found")

            # Check if secret name already exists in workspace
            existing = await self.session.execute(
                Secret.__table__.select().where(
                    and_(
                        Secret.workspace_id == workspace_id,
                        Secret.name == request.name,
                        Secret.is_active == True
                    )
                )
            )
            if existing.first():
                raise ValueError(f"Secret '{request.name}' already exists in workspace")

            # Encrypt the secret value
            encrypted_value = await encryption_service.encrypt(request.value)

            # Calculate rotation date if needed
            rotation_due_at = None
            last_rotated_at = datetime.now(timezone.utc)
            
            if request.rotation_policy != SecretRotationPolicy.MANUAL:
                days_map = {
                    SecretRotationPolicy.AUTO_30_DAYS: 30,
                    SecretRotationPolicy.AUTO_60_DAYS: 60,
                    SecretRotationPolicy.AUTO_90_DAYS: 90,
                    SecretRotationPolicy.AUTO_180_DAYS: 180,
                    SecretRotationPolicy.AUTO_365_DAYS: 365,
                }
                days = days_map.get(request.rotation_policy)
                if days:
                    rotation_due_at = last_rotated_at + timedelta(days=days)

            # Create secret record
            secret = Secret(
                workspace_id=workspace_id,
                name=request.name,
                secret_type=request.secret_type,
                usage=request.usage,
                encrypted_value=encrypted_value,
                rotation_policy=request.rotation_policy,
                last_rotated_at=last_rotated_at,
                rotation_due_at=rotation_due_at,
                created_by_user_id=user_id,
                updated_by_user_id=user_id,
                meta_data=request.metadata,
                tags=request.tags,
                is_active=True
            )

            self.session.add(secret)
            await self.session.commit()
            await self.session.refresh(secret)

            # Log audit event
            audit_logger = await self._get_audit_logger()
            await audit_logger.log_secret_action(
                secret_id=secret.id,
                action=SecretAuditAction.CREATED,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    'name': request.name,
                    'type': request.secret_type,
                    'rotation_policy': request.rotation_policy
                }
            )

            logger.info(f"Created secret '{request.name}' in workspace {workspace_id}")
            return secret

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create secret: {e}")
            raise

    async def get_secret(
        self,
        workspace_id: str,
        secret_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Secret:
        """Get a secret by ID and decrypt its value."""
        try:
            secret = await self.session.get(Secret, secret_id)
            if not secret:
                raise ValueError(f"Secret {secret_id} not found")

            if secret.workspace_id != workspace_id:
                raise ValueError(f"Secret {secret_id} does not belong to workspace {workspace_id}")

            if not secret.is_active:
                raise ValueError(f"Secret {secret_id} is not active")

            # Log audit event for secret access
            audit_logger = await self._get_audit_logger()
            await audit_logger.log_secret_action(
                secret_id=secret.id,
                action=SecretAuditAction.ACCESSED,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={'access_method': 'direct'}
            )

            logger.debug(f"Retrieved secret '{secret.name}' from workspace {workspace_id}")
            return secret

        except Exception as e:
            logger.error(f"Failed to get secret {secret_id}: {e}")
            raise

    async def get_secret_value(
        self,
        workspace_id: str,
        secret_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Get decrypted value of a secret."""
        secret = await self.get_secret(
            workspace_id, secret_id, user_id, ip_address, user_agent
        )
        
        try:
            decrypted_value = await encryption_service.decrypt(secret.encrypted_value)
            
            # Update access statistics (you might want to track this)
            logger.debug(f"Decrypted secret '{secret.name}' value for user {user_id}")
            return decrypted_value

        except Exception as e:
            logger.error(f"Failed to decrypt secret {secret_id}: {e}")
            raise

    async def get_secret_by_name(
        self,
        workspace_id: str,
        name: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Secret]:
        """Get a secret by name."""
        try:
            result = await self.session.execute(
                Secret.__table__.select().where(
                    and_(
                        Secret.workspace_id == workspace_id,
                        Secret.name == name,
                        Secret.is_active == True
                    )
                )
            )
            secret = result.first()
            
            if secret and user_id:
                # Log audit event for secret access by name
                audit_logger = await self._get_audit_logger()
                await audit_logger.log_secret_action(
                    secret_id=secret.id,
                    action=SecretAuditAction.ACCESSED,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={'access_method': 'by_name'}
                )

            return secret

        except Exception as e:
            logger.error(f"Failed to get secret by name '{name}': {e}")
            raise

    async def list_secrets(
        self,
        workspace_id: str,
        secret_type: Optional[SecretType] = None,
        is_rotation_due: Optional[bool] = None,
        is_active: Optional[bool] = True,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecretMetadata]:
        """List secrets metadata in a workspace."""
        try:
            query = Secret.__table__.select().where(
                and_(
                    Secret.workspace_id == workspace_id,
                    Secret.is_active == is_active if is_active is not None else True
                )
            )

            if secret_type:
                query = query.where(Secret.secret_type == secret_type)

            if tags:
                # Filter by tags (this is a simplified implementation)
                for tag in tags:
                    query = query.where(Secret.tags.contains([tag]))

            # Add ordering
            query = query.order_by(desc(Secret.created_at)).limit(limit).offset(offset)

            result = await self.session.execute(query)
            secrets = result.fetchall()

            # Filter by rotation due if requested
            if is_rotation_due is not None:
                secrets = [s for s in secrets if s.is_rotation_due == is_rotation_due]

            return [SecretMetadata(secret) for secret in secrets]

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            raise

    async def update_secret(
        self,
        workspace_id: str,
        secret_id: str,
        request: SecretUpdateRequest,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Secret:
        """Update an existing secret."""
        try:
            secret = await self.session.get(Secret, secret_id)
            if not secret:
                raise ValueError(f"Secret {secret_id} not found")

            if secret.workspace_id != workspace_id:
                raise ValueError(f"Secret {secret_id} does not belong to workspace {workspace_id}")

            if not secret.is_active:
                raise ValueError(f"Secret {secret_id} is not active")

            updated_fields = []
            
            # Update encrypted value if provided
            if request.value is not None:
                secret.encrypted_value = await encryption_service.encrypt(request.value)
                secret.last_rotated_at = datetime.now(timezone.utc)
                
                # Update rotation due date
                if secret.rotation_policy != SecretRotationPolicy.MANUAL:
                    days_map = {
                        SecretRotationPolicy.AUTO_30_DAYS: 30,
                        SecretRotationPolicy.AUTO_60_DAYS: 60,
                        SecretRotationPolicy.AUTO_90_DAYS: 90,
                        SecretRotationPolicy.AUTO_180_DAYS: 180,
                        SecretRotationPolicy.AUTO_365_DAYS: 365,
                    }
                    days = days_map.get(secret.rotation_policy)
                    if days:
                        secret.rotation_due_at = secret.last_rotated_at + timedelta(days=days)
                
                updated_fields.append('value')

            # Update other fields
            if request.usage is not None:
                secret.usage = request.usage
                updated_fields.append('usage')

            if request.rotation_policy is not None:
                secret.rotation_policy = request.rotation_policy
                updated_fields.append('rotation_policy')
                
                # Recalculate rotation due date if policy changed
                if request.rotation_policy == SecretRotationPolicy.MANUAL:
                    secret.rotation_due_at = None
                else:
                    days_map = {
                        SecretRotationPolicy.AUTO_30_DAYS: 30,
                        SecretRotationPolicy.AUTO_60_DAYS: 60,
                        SecretRotationPolicy.AUTO_90_DAYS: 90,
                        SecretRotationPolicy.AUTO_180_DAYS: 180,
                        SecretRotationPolicy.AUTO_365_DAYS: 365,
                    }
                    days = days_map.get(request.rotation_policy)
                    if days:
                        secret.rotation_due_at = secret.last_rotated_at + timedelta(days=days)
                
                updated_fields.append('rotation_policy')

            if request.tags is not None:
                secret.tags = request.tags
                updated_fields.append('tags')

            if request.metadata is not None:
                secret.meta_data = request.metadata
                updated_fields.append('metadata')

            secret.updated_by_user_id = user_id
            secret.updated_at = datetime.now(timezone.utc)

            await self.session.commit()
            await self.session.refresh(secret)

            # Log audit event
            audit_logger = await self._get_audit_logger()
            await audit_logger.log_secret_action(
                secret_id=secret.id,
                action=SecretAuditAction.UPDATED,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={'updated_fields': updated_fields}
            )

            logger.info(f"Updated secret '{secret.name}' in workspace {workspace_id}")
            return secret

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update secret {secret_id}: {e}")
            raise

    async def rotate_secret(
        self,
        workspace_id: str,
        secret_id: str,
        new_value: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Secret:
        """Rotate a secret with a new value."""
        try:
            update_request = SecretUpdateRequest(
                value=new_value,
                updated_by_user_id=user_id
            )
            
            secret = await self.update_secret(
                workspace_id, secret_id, update_request, user_id, ip_address, user_agent
            )

            # Log rotation-specific audit event
            audit_logger = await self._get_audit_logger()
            await audit_logger.log_secret_action(
                secret_id=secret.id,
                action=SecretAuditAction.ROTATED,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    'rotation_type': 'manual',
                    'previous_rotation': secret.last_rotated_at.isoformat()
                }
            )

            logger.info(f"Rotated secret '{secret.name}' in workspace {workspace_id}")
            return secret

        except Exception as e:
            logger.error(f"Failed to rotate secret {secret_id}: {e}")
            raise

    async def delete_secret(
        self,
        workspace_id: str,
        secret_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Soft delete a secret (mark as inactive)."""
        try:
            secret = await self.session.get(Secret, secret_id)
            if not secret:
                raise ValueError(f"Secret {secret_id} not found")

            if secret.workspace_id != workspace_id:
                raise ValueError(f"Secret {secret_id} does not belong to workspace {workspace_id}")

            secret.is_active = False
            secret.updated_by_user_id = user_id
            secret.updated_at = datetime.now(timezone.utc)

            await self.session.commit()

            # Log audit event
            audit_logger = await self._get_audit_logger()
            await audit_logger.log_secret_action(
                secret_id=secret.id,
                action=SecretAuditAction.DELETED,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={'deletion_type': 'soft_delete'}
            )

            logger.info(f"Deleted secret '{secret.name}' in workspace {workspace_id}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete secret {secret_id}: {e}")
            raise

    async def get_rotation_due_secrets(
        self,
        workspace_id: str,
        days_ahead: int = 7
    ) -> List[Secret]:
        """Get secrets due for rotation within the specified days."""
        try:
            cutoff_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
            
            result = await self.session.execute(
                Secret.__table__.select().where(
                    and_(
                        Secret.workspace_id == workspace_id,
                        Secret.is_active == True,
                        Secret.rotation_policy != SecretRotationPolicy.MANUAL,
                        Secret.rotation_due_at <= cutoff_date
                    )
                ).order_by(Secret.rotation_due_at)
            )
            
            return result.fetchall()

        except Exception as e:
            logger.error(f"Failed to get rotation due secrets: {e}")
            raise

    async def get_secret_audit_logs(
        self,
        secret_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[SecretAudit]:
        """Get audit logs for a specific secret."""
        try:
            result = await self.session.execute(
                SecretAudit.__table__.select()
                .where(SecretAudit.secret_id == secret_id)
                .order_by(desc(SecretAudit.created_at))
                .limit(limit)
                .offset(offset)
            )
            
            return result.fetchall()

        except Exception as e:
            logger.error(f"Failed to get audit logs for secret {secret_id}: {e}")
            raise

    async def get_secret_statistics(
        self,
        workspace_id: str
    ) -> Dict[str, Any]:
        """Get statistics about secrets in a workspace."""
        try:
            # Get total counts
            total_result = await self.session.execute(
                Secret.__table__.select()
                .where(and_(Secret.workspace_id == workspace_id, Secret.is_active == True))
            )
            total_secrets = len(total_result.fetchall())

            # Count by type
            type_counts = {}
            for secret_type in SecretType:
                result = await self.session.execute(
                    Secret.__table__.select().where(
                        and_(
                            Secret.workspace_id == workspace_id,
                            Secret.secret_type == secret_type,
                            Secret.is_active == True
                        )
                    )
                )
                type_counts[secret_type.value] = len(result.fetchall())

            # Count rotation due
            rotation_due = await self.get_rotation_due_secrets(workspace_id, days_ahead=0)
            
            # Count by rotation policy
            policy_counts = {}
            for policy in SecretRotationPolicy:
                result = await self.session.execute(
                    Secret.__table__.select().where(
                        and_(
                            Secret.workspace_id == workspace_id,
                            Secret.rotation_policy == policy,
                            Secret.is_active == True
                        )
                    )
                )
                policy_counts[policy.value] = len(result.fetchall())

            return {
                'total_secrets': total_secrets,
                'secrets_by_type': type_counts,
                'secrets_by_rotation_policy': policy_counts,
                'rotation_due_count': len(rotation_due),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get secret statistics: {e}")
            raise


# Dependency function to get SecretManager instance
async def get_secret_manager(session: AsyncSession) -> SecretManager:
    """Dependency function to get SecretManager instance."""
    return SecretManager(session)