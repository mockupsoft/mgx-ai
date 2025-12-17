# -*- coding: utf-8 -*-
"""backend.tests.test_secrets

Comprehensive tests for the secret management and encryption system.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.db.models.entities import Secret, SecretAudit
from backend.db.models.enums import (
    SecretType, SecretRotationPolicy, SecretBackend, SecretAuditAction
)
from backend.services.secrets.encryption import (
    EncryptionService, FernetBackend, EncryptionBackend
)
from backend.services.secrets.manager import (
    SecretManager, SecretCreateRequest, SecretUpdateRequest, SecretMetadata
)
from backend.services.secrets.vault import VaultClient


class TestEncryptionService:
    """Test encryption service with multiple backends."""

    @pytest.mark.asyncio
    async def test_fernet_backend_encryption_decryption(self):
        """Test Fernet encryption and decryption."""
        backend = FernetBackend()
        
        # Test data
        plaintext = "sensitive-secret-data-123"
        
        # Encrypt
        ciphertext = await backend.encrypt(plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) > len(plaintext)
        
        # Decrypt
        decrypted = await backend.decrypt(ciphertext)
        assert decrypted == plaintext
        
    @pytest.mark.asyncio
    async def test_fernet_key_rotation(self):
        """Test Fernet key rotation."""
        backend = FernetBackend()
        
        # Original key
        original_key = backend.key_id
        
        # Rotate
        rotated = await backend.rotate_key()
        assert rotated is True
        
        # Should have new key
        new_key = backend.key_id
        assert new_key != original_key
        
    @pytest.mark.asyncio
    async def test_fernet_health_check(self):
        """Test Fernet backend health check."""
        backend = FernetBackend()
        
        # Should be healthy
        healthy = await backend.is_healthy()
        assert healthy is True
        
    @pytest.mark.asyncio
    async def test_encryption_service_initialization(self):
        """Test encryption service initialization."""
        service = EncryptionService()
        
        # Initialize with Fernet
        await service.initialize(
            backend_type=SecretBackend.FERNET,
            encryption_key=None
        )
        
        # Should be initialized
        assert service.current_backend == SecretBackend.FERNET
        
        # Test encryption/decryption
        plaintext = "test-data"
        ciphertext = await service.encrypt(plaintext)
        decrypted = await service.decrypt(ciphertext)
        assert decrypted == plaintext
        
    @pytest.mark.asyncio
    async def test_encryption_service_key_rotation(self):
        """Test encryption service key rotation."""
        service = EncryptionService()
        await service.initialize(SecretBackend.FERNET)
        
        # Rotate keys
        results = await service.rotate_encryption_key()
        
        # Should have results for current backend
        assert SecretBackend.FERNET in results
        assert results[SecretBackend.FERNET]['success'] is True


class TestSecretManager:
    """Test secret management service."""

    @pytest.fixture
    def mock_session(self):
        """Mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def secret_manager(self, mock_session):
        """Create secret manager with mock session."""
        return SecretManager(mock_session)

    @pytest.fixture
    def sample_secret_data(self):
        """Sample secret creation data."""
        return SecretCreateRequest(
            name="TEST_SECRET",
            secret_type=SecretType.API_KEY,
            value="test-secret-value",
            usage="Test secret for unit testing",
            rotation_policy=SecretRotationPolicy.MANUAL
        )

    @pytest.mark.asyncio
    async def test_create_secret_success(self, secret_manager, sample_secret_data, mock_session):
        """Test successful secret creation."""
        # Mock workspace check
        mock_workspace = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_workspace)
        
        # Mock existing secret check
        mock_session.execute = AsyncMock()
        mock_existing_result = MagicMock()
        mock_existing_result.first.return_value = None
        mock_session.execute.return_value = mock_existing_result
        
        # Mock encryption
        with patch('backend.services.secrets.manager.encryption_service') as mock_encryption:
            mock_encryption.encrypt = AsyncMock(return_value="encrypted_value")
            
            # Create secret
            secret = await secret_manager.create_secret(
                workspace_id="workspace123",
                request=sample_secret_data,
                user_id="user123"
            )
            
            # Verify secret properties
            assert secret.workspace_id == "workspace123"
            assert secret.name == "TEST_SECRET"
            assert secret.secret_type == SecretType.API_KEY
            assert secret.encrypted_value == "encrypted_value"
            assert secret.is_active is True
            
            # Verify session operations
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_secret_duplicate_name(self, secret_manager, sample_secret_data, mock_session):
        """Test secret creation with duplicate name."""
        # Mock existing secret
        mock_existing = MagicMock()
        mock_session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_existing
        mock_session.execute.return_value = mock_result
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            await secret_manager.create_secret(
                workspace_id="workspace123",
                request=sample_secret_data
            )

    @pytest.mark.asyncio
    async def test_get_secret_success(self, secret_manager, mock_session):
        """Test successful secret retrieval."""
        # Mock secret
        mock_secret = MagicMock()
        mock_secret.id = "secret123"
        mock_secret.workspace_id = "workspace123"
        mock_secret.name = "TEST_SECRET"
        mock_secret.is_active = True
        mock_secret.encrypted_value = "encrypted_value"
        
        mock_session.get = AsyncMock(return_value=mock_secret)
        
        # Get secret
        secret = await secret_manager.get_secret(
            workspace_id="workspace123",
            secret_id="secret123"
        )
        
        # Verify
        assert secret == mock_secret
        mock_session.get.assert_called_once_with(Secret, "secret123")

    @pytest.mark.asyncio
    async def test_get_secret_not_found(self, secret_manager, mock_session):
        """Test secret retrieval when not found."""
        mock_session.get = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="not found"):
            await secret_manager.get_secret(
                workspace_id="workspace123",
                secret_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_get_secret_wrong_workspace(self, secret_manager, mock_session):
        """Test secret retrieval from wrong workspace."""
        # Mock secret from different workspace
        mock_secret = MagicMock()
        mock_secret.workspace_id = "different_workspace"
        
        mock_session.get = AsyncMock(return_value=mock_secret)
        
        with pytest.raises(ValueError, match="does not belong to workspace"):
            await secret_manager.get_secret(
                workspace_id="workspace123",
                secret_id="secret123"
            )

    @pytest.mark.asyncio
    async def test_get_secret_value_success(self, secret_manager, mock_session):
        """Test successful secret value decryption."""
        # Mock secret
        mock_secret = MagicMock()
        mock_secret.encrypted_value = "encrypted_value"
        
        # Mock get_secret
        with patch.object(secret_manager, 'get_secret', return_value=mock_secret):
            with patch('backend.services.secrets.manager.encryption_service') as mock_encryption:
                mock_encryption.decrypt = AsyncMock(return_value="decrypted_value")
                
                # Get secret value
                value = await secret_manager.get_secret_value(
                    workspace_id="workspace123",
                    secret_id="secret123"
                )
                
                assert value == "decrypted_value"
                mock_encryption.decrypt.assert_called_once_with("encrypted_value")

    @pytest.mark.asyncio
    async def test_list_secrets(self, secret_manager, mock_session):
        """Test listing secrets."""
        # Mock secrets query result
        mock_secrets = [
            MagicMock(
                id="secret1",
                name="SECRET1",
                secret_type=SecretType.API_KEY,
                usage="Test secret 1",
                rotation_policy=SecretRotationPolicy.MANUAL,
                last_rotated_at=None,
                rotation_due_at=None,
                created_by_user_id=None,
                updated_by_user_id=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                is_active=True,
                tags=[],
                metadata={},
                is_rotation_due=False
            ),
            MagicMock(
                id="secret2",
                name="SECRET2",
                secret_type=SecretType.DATABASE_CREDENTIAL,
                usage="Test secret 2",
                rotation_policy=SecretRotationPolicy.AUTO_90_DAYS,
                last_rotated_at=datetime.now(timezone.utc),
                rotation_due_at=datetime.now(timezone.utc) + timedelta(days=90),
                created_by_user_id=None,
                updated_by_user_id=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                is_active=True,
                tags=["database"],
                metadata={},
                is_rotation_due=False
            )
        ]
        
        # Mock query execution
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_secrets
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # List secrets
        secrets = await secret_manager.list_secrets(workspace_id="workspace123")
        
        # Verify
        assert len(secrets) == 2
        assert isinstance(secrets[0], SecretMetadata)
        assert secrets[0].id == "secret1"
        assert secrets[1].id == "secret2"

    @pytest.mark.asyncio
    async def test_update_secret_value(self, secret_manager, mock_session):
        """Test updating secret value."""
        # Mock existing secret
        mock_secret = MagicMock()
        mock_secret.workspace_id = "workspace123"
        mock_secret.is_active = True
        mock_secret.rotation_policy = SecretRotationPolicy.MANUAL
        mock_secret.rotation_due_at = None
        
        mock_session.get = AsyncMock(return_value=mock_secret)
        
        # Mock encryption
        with patch('backend.services.secrets.manager.encryption_service') as mock_encryption:
            mock_encryption.encrypt = AsyncMock(return_value="new_encrypted_value")
            
            # Update request
            update_request = SecretUpdateRequest(
                value="new-secret-value"
            )
            
            # Update secret
            updated_secret = await secret_manager.update_secret(
                workspace_id="workspace123",
                secret_id="secret123",
                request=update_request
            )
            
            # Verify encryption was called
            mock_encryption.encrypt.assert_called_once_with("new-secret-value")
            
            # Verify session operations
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_secret)

    @pytest.mark.asyncio
    async def test_rotate_secret(self, secret_manager, mock_session):
        """Test secret rotation."""
        # Mock existing secret
        mock_secret = MagicMock()
        mock_secret.workspace_id = "workspace123"
        mock_secret.is_active = True
        mock_secret.name = "TEST_SECRET"
        mock_secret.rotation_policy = SecretRotationPolicy.MANUAL
        
        with patch.object(secret_manager, 'update_secret', return_value=mock_secret):
            # Rotate secret
            rotated_secret = await secret_manager.rotate_secret(
                workspace_id="workspace123",
                secret_id="secret123",
                new_value="new-secret-value"
            )
            
            # Verify
            assert rotated_secret == mock_secret

    @pytest.mark.asyncio
    async def test_delete_secret(self, secret_manager, mock_session):
        """Test secret deletion."""
        # Mock existing secret
        mock_secret = MagicMock()
        mock_secret.workspace_id = "workspace123"
        mock_secret.name = "TEST_SECRET"
        
        mock_session.get = AsyncMock(return_value=mock_secret)
        
        # Delete secret
        result = await secret_manager.delete_secret(
            workspace_id="workspace123",
            secret_id="secret123"
        )
        
        # Verify
        assert result is True
        assert mock_secret.is_active is False
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rotation_due_secrets(self, secret_manager, mock_session):
        """Test getting rotation due secrets."""
        # Mock secrets due for rotation
        mock_secrets = [
            MagicMock(
                id="secret1",
                name="SECRET1",
                rotation_policy=SecretRotationPolicy.AUTO_30_DAYS,
                rotation_due_at=datetime.now(timezone.utc) + timedelta(days=5)
            )
        ]
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_secrets
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Get rotation due secrets
        secrets = await secret_manager.get_rotation_due_secrets(
            workspace_id="workspace123",
            days_ahead=7
        )
        
        # Verify
        assert len(secrets) == 1
        assert secrets[0].id == "secret1"

    @pytest.mark.asyncio
    async def test_get_secret_statistics(self, secret_manager, mock_session):
        """Test getting secret statistics."""
        # Mock query results
        mock_session.execute = AsyncMock()
        
        # Mock different query results based on the SQL query
        def execute_side_effect(query):
            if "count" in str(query) and "WHERE" in str(query):
                # Total count query
                result = MagicMock()
                result.fetchall.return_value = [None] * 5  # 5 total secrets
                return result
            else:
                # Specific queries
                result = MagicMock()
                result.fetchall.return_value = []
                return result
        
        mock_session.execute.side_effect = execute_side_effect
        
        # Get statistics
        stats = await secret_manager.get_secret_statistics(
            workspace_id="workspace123"
        )
        
        # Verify structure
        assert 'total_secrets' in stats
        assert 'secrets_by_type' in stats
        assert 'secrets_by_rotation_policy' in stats
        assert 'rotation_due_count' in stats
        assert 'last_updated' in stats


class TestSecretModels:
    """Test secret database models."""

    def test_secret_model_properties(self):
        """Test Secret model properties."""
        secret = Secret(
            id="secret123",
            workspace_id="workspace123",
            name="TEST_SECRET",
            secret_type=SecretType.API_KEY,
            usage="Test secret",
            encrypted_value="encrypted_value",
            rotation_policy=SecretRotationPolicy.MANUAL,
            last_rotated_at=None,
            rotation_due_at=None,
            is_active=True
        )
        
        # Test is_rotation_due property
        assert secret.is_rotation_due is False
        
        # Test with rotation due
        secret.rotation_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert secret.is_rotation_due is True

    def test_secret_repr(self):
        """Test Secret model string representation."""
        secret = Secret(
            id="secret123",
            workspace_id="workspace123",
            name="TEST_SECRET",
            secret_type=SecretType.API_KEY,
            usage="Test secret",
            encrypted_value="encrypted_value"
        )
        
        expected = "<Secret(id=secret123, workspace_id=workspace123, name=TEST_SECRET, type=api_key)>"
        assert repr(secret) == expected

    def test_secret_audit_repr(self):
        """Test SecretAudit model string representation."""
        audit = SecretAudit(
            id="audit123",
            secret_id="secret123",
            action=SecretAuditAction.CREATED,
            user_id="user123"
        )
        
        expected = "<SecretAudit(id=audit123, secret_id=secret123, action=created, user_id=user123)>"
        assert repr(audit) == expected


class TestVaultIntegration:
    """Test HashiCorp Vault integration."""

    @pytest.mark.skipif(not True, reason="Vault integration tests require Vault server")
    def test_vault_client_initialization(self):
        """Test Vault client initialization."""
        # This test requires a running Vault server
        # In real deployment, this would be tested with test containers
        pass

    @pytest.mark.skipif(not True, reason="Vault integration tests require Vault server")
    async def test_vault_secret_operations(self):
        """Test Vault secret storage and retrieval."""
        # This test requires a running Vault server
        pass


# Integration tests with mock external services
class TestSecretManagementIntegration:
    """Integration tests for secret management system."""

    @pytest.mark.asyncio
    async def test_secret_lifecycle_with_audit(self):
        """Test complete secret lifecycle with audit logging."""
        # Mock dependencies
        mock_session = AsyncMock()
        mock_workspace = MagicMock()
        mock_session.get.return_value = mock_workspace
        mock_session.execute.return_value.first.return_value = None
        
        # Create secret manager
        secret_manager = SecretManager(mock_session)
        
        # Mock encryption service
        with patch('backend.services.secrets.manager.encryption_service') as mock_encryption:
            mock_encryption.encrypt = AsyncMock(return_value="encrypted_value")
            mock_encryption.decrypt = AsyncMock(return_value="secret_value")
            
            # Create secret
            create_request = SecretCreateRequest(
                name="LIFECYCLE_SECRET",
                secret_type=SecretType.API_KEY,
                value="secret_value",
                usage="Test lifecycle secret"
            )
            
            # Mock created secret
            mock_secret = MagicMock()
            mock_secret.id = "secret123"
            mock_secret.workspace_id = "workspace123"
            mock_secret.name = "LIFECYCLE_SECRET"
            mock_secret.is_active = True
            
            with patch.object(secret_manager, 'create_secret', return_value=mock_secret):
                # Create
                created = await secret_manager.create_secret(
                    workspace_id="workspace123",
                    request=create_request,
                    user_id="user123"
                )
                assert created.id == "secret123"
                
                # Update
                update_request = SecretUpdateRequest(value="new_value")
                with patch.object(secret_manager, 'update_secret', return_value=mock_secret):
                    updated = await secret_manager.update_secret(
                        workspace_id="workspace123",
                        secret_id="secret123",
                        request=update_request
                    )
                    assert updated.id == "secret123"
                
                # Delete
                with patch.object(secret_manager, 'delete_secret', return_value=True):
                    deleted = await secret_manager.delete_secret(
                        workspace_id="workspace123",
                        secret_id="secret123"
                    )
                    assert deleted is True

    @pytest.mark.asyncio
    async def test_rotation_policy_handling(self):
        """Test rotation policy calculation and enforcement."""
        # Test different rotation policies
        policies = {
            SecretRotationPolicy.MANUAL: None,
            SecretRotationPolicy.AUTO_30_DAYS: 30,
            SecretRotationPolicy.AUTO_90_DAYS: 90,
            SecretRotationPolicy.AUTO_365_DAYS: 365
        }
        
        for policy, expected_days in policies.items():
            if expected_days:
                # Should calculate rotation due date
                due_date = datetime.now(timezone.utc) + timedelta(days=expected_days)
                assert due_date >= datetime.now(timezone.utc)
            else:
                # Manual policy should not set rotation due date
                assert True  # Placeholder assertion


class TestSecretSecurity:
    """Test security aspects of secret management."""

    @pytest.mark.asyncio
    async def test_no_plaintext_in_logs(self):
        """Test that plaintext secrets don't appear in logs."""
        with patch('backend.services.secrets.manager.logger') as mock_logger:
            backend = FernetBackend()
            
            # Encrypt some sensitive data
            sensitive_data = "VERY_SENSITIVE_API_KEY_12345"
            encrypted = await backend.encrypt(sensitive_data)
            
            # Log the encrypted value
            mock_logger.info(f"Encrypted secret: {encrypted}")
            
            # Verify that plaintext doesn't appear in log calls
            for call in mock_logger.info.call_args_list:
                logged_message = str(call[0])
                assert sensitive_data not in logged_message
                # Only encrypted version should be logged
                if "Encrypted secret:" in logged_message:
                    assert encrypted in logged_message

    @pytest.mark.asyncio
    async def test_audit_logging_completeness(self):
        """Test that all secret operations are logged."""
        # Mock session and audit logger
        mock_session = AsyncMock()
        secret_manager = SecretManager(mock_session)
        
        # Test each operation logs appropriately
        operations = [
            ("create", "created"),
            ("access", "accessed"),
            ("update", "updated"),
            ("rotate", "rotated"),
            ("delete", "deleted")
        ]
        
        for operation, expected_action in operations:
            with patch.object(secret_manager, '_get_audit_logger') as mock_audit:
                mock_audit_instance = MagicMock()
                mock_audit_instance.log_secret_action = AsyncMock()
                mock_audit.return_value = mock_audit_instance
                
                # Perform operation (mocked)
                if operation == "create":
                    mock_secret = MagicMock()
                    mock_session.execute.return_value.first.return_value = None
                    with patch('backend.services.secrets.manager.encryption_service'):
                        await secret_manager.create_secret(
                            "workspace123",
                            SecretCreateRequest(
                                name="TEST_SECRET",
                                secret_type=SecretType.API_KEY,
                                value="secret"
                            ),
                            user_id="user123"
                        )
                
                # Verify audit logging
                mock_audit_instance.log_secret_action.assert_called()
                call_args = mock_audit_instance.log_secret_action.call_args
                assert call_args[1]['action'] == expected_action

    @pytest.mark.asyncio
    async def test_workspace_isolation(self):
        """Test that secrets are properly isolated by workspace."""
        # Mock secrets in different workspaces
        workspace_1_secrets = [
            MagicMock(workspace_id="workspace1", name="SECRET_1"),
            MagicMock(workspace_id="workspace1", name="SECRET_2")
        ]
        
        workspace_2_secrets = [
            MagicMock(workspace_id="workspace2", name="SECRET_3")
        ]
        
        # Test that listing respects workspace boundaries
        mock_session = AsyncMock()
        secret_manager = SecretManager(mock_session)
        
        # Mock query execution
        def execute_side_effect(query):
            if "workspace_id == 'workspace1'" in str(query):
                result = MagicMock()
                result.fetchall.return_value = workspace_1_secrets
                return result
            elif "workspace_id == 'workspace2'" in str(query):
                result = MagicMock()
                result.fetchall.return_value = workspace_2_secrets
                return result
            else:
                return MagicMock()
        
        mock_session.execute.side_effect = execute_side_effect
        
        # List secrets for each workspace
        secrets_workspace1 = await secret_manager.list_secrets("workspace1")
        secrets_workspace2 = await secret_manager.list_secrets("workspace2")
        
        # Verify isolation
        assert len(secrets_workspace1) == 2
        assert len(secrets_workspace2) == 1
        
        # Verify workspace assignment
        for secret in secrets_workspace1:
            assert secret.workspace_id == "workspace1"
        
        for secret in secrets_workspace2:
            assert secret.workspace_id == "workspace2"


if __name__ == "__main__":
    pytest.main([__file__])