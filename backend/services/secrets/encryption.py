# -*- coding: utf-8 -*-
"""backend.services.secrets.encryption

Encryption service supporting multiple backends:
- Fernet (built-in, for development)
- AWS KMS
- HashiCorp Vault
"""

import base64
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    Fernet = None

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

try:
    import hvac
    from hvac.exceptions import VaultError
except ImportError:
    hvac = None

from backend.config import settings
from backend.db.models.enums import SecretBackend

logger = logging.getLogger(__name__)


class EncryptionBackend(ABC):
    """Abstract base class for encryption backends."""

    @abstractmethod
    async def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return ciphertext."""
        pass

    @abstractmethod
    async def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext and return plaintext."""
        pass

    @abstractmethod
    async def rotate_key(self) -> bool:
        """Rotate encryption key. Return True if successful."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the backend is healthy and accessible."""
        pass


class FernetBackend(EncryptionBackend):
    """Fernet encryption backend for development and testing."""

    def __init__(self, encryption_key: Optional[str] = None):
        if Fernet is None:
            raise ImportError("cryptography package not installed")
        
        self.backend_type = SecretBackend.FERNET
        
        if encryption_key:
            # Use provided key
            key_bytes = base64.urlsafe_b64decode(encryption_key.encode())
        else:
            # Generate new key
            key_bytes = Fernet.generate_key()
            encryption_key = base64.urlsafe_b64encode(key_bytes).decode()
        
        self._fernet = Fernet(key_bytes)
        self._key = encryption_key
        self._created_at = datetime.now(timezone.utc)

    async def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using Fernet."""
        try:
            ciphertext = self._fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(ciphertext).decode()
        except Exception as e:
            logger.error(f"Fernet encryption failed: {e}")
            raise

    async def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext using Fernet."""
        try:
            ciphertext_bytes = base64.urlsafe_b64decode(ciphertext.encode())
            plaintext_bytes = self._fernet.decrypt(ciphertext_bytes)
            return plaintext_bytes.decode()
        except Exception as e:
            logger.error(f"Fernet decryption failed: {e}")
            raise

    async def rotate_key(self) -> bool:
        """Rotate Fernet key by generating a new one."""
        try:
            new_key = Fernet.generate_key()
            self._fernet = Fernet(new_key)
            self._key = base64.urlsafe_b64encode(new_key).decode()
            self._created_at = datetime.now(timezone.utc)
            logger.info("Fernet key rotated successfully")
            return True
        except Exception as e:
            logger.error(f"Fernet key rotation failed: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check Fernet backend health."""
        try:
            # Test encryption/decryption
            test_data = "health_check"
            encrypted = await self.encrypt(test_data)
            decrypted = await self.decrypt(encrypted)
            return decrypted == test_data
        except Exception:
            return False

    @property
    def key_id(self) -> str:
        """Return key identifier for tracking."""
        return f"fernet_{self._created_at.strftime('%Y%m%d_%H%M%S')}"


class AWSKMSBackend(EncryptionBackend):
    """AWS KMS encryption backend for production."""

    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        if boto3 is None:
            raise ImportError("boto3 package not installed")
        
        self.backend_type = SecretBackend.AWS_KMS
        self.kms_key_id = kms_key_id
        self.region = region
        
        try:
            self._kms_client = boto3.client('kms', region_name=region)
        except Exception as e:
            logger.error(f"Failed to initialize AWS KMS client: {e}")
            raise

    async def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using AWS KMS."""
        try:
            response = self._kms_client.encrypt(
                KeyId=self.kms_key_id,
                Plaintext=plaintext.encode('utf-8')
            )
            ciphertext_blob = response['CiphertextBlob']
            return base64.b64encode(ciphertext_blob).decode('utf-8')
        except ClientError as e:
            logger.error(f"AWS KMS encryption failed: {e}")
            raise

    async def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext using AWS KMS."""
        try:
            ciphertext_blob = base64.b64decode(ciphertext.encode('utf-8'))
            response = self._kms_client.decrypt(
                CiphertextBlob=ciphertext_blob
            )
            plaintext = response['Plaintext'].decode('utf-8')
            return plaintext
        except ClientError as e:
            logger.error(f"AWS KMS decryption failed: {e}")
            raise

    async def rotate_key(self) -> bool:
        """AWS KMS key rotation is handled by AWS automatically."""
        try:
            # Check if key rotation is enabled
            response = self._kms_client.get_key_rotation_status(KeyId=self.kms_key_id)
            logger.info(f"AWS KMS key rotation status: {response['KeyRotationEnabled']}")
            return response['KeyRotationEnabled']
        except ClientError as e:
            logger.error(f"AWS KMS rotation check failed: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check AWS KMS backend health."""
        try:
            # Test encrypt/decrypt
            test_data = "health_check"
            encrypted = await self.encrypt(test_data)
            decrypted = await self.decrypt(encrypted)
            return decrypted == test_data
        except Exception:
            return False

    @property
    def key_id(self) -> str:
        """Return key identifier."""
        return self.kms_key_id


class VaultBackend(EncryptionBackend):
    """HashiCorp Vault encryption backend."""

    def __init__(self, vault_url: str, vault_token: str, mount_point: str = "secret"):
        if hvac is None:
            raise ImportError("hvac package not installed")
        
        self.backend_type = SecretBackend.VAULT
        self.vault_url = vault_url
        self.vault_token = vault_token
        self.mount_point = mount_point
        
        try:
            self._client = hvac.Client(url=vault_url, token=vault_token)
            if not self._client.is_authenticated():
                raise Exception("Failed to authenticate with Vault")
        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            raise

    async def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using Vault transit engine."""
        try:
            response = self._client.secrets.transit.encrypt_data(
                name='encryption-key',
                plaintext=base64.b64encode(plaintext.encode()).decode()
            )
            return response['data']['ciphertext']
        except VaultError as e:
            logger.error(f"Vault encryption failed: {e}")
            raise

    async def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext using Vault transit engine."""
        try:
            response = self._client.secrets.transit.decrypt_data(
                name='encryption-key',
                ciphertext=ciphertext
            )
            plaintext_bytes = base64.b64decode(response['data']['plaintext'])
            return plaintext_bytes.decode()
        except VaultError as e:
            logger.error(f"Vault decryption failed: {e}")
            raise

    async def rotate_key(self) -> bool:
        """Rotate Vault transit key."""
        try:
            self._client.secrets.transit.rotate_key(name='encryption-key')
            logger.info("Vault encryption key rotated successfully")
            return True
        except VaultError as e:
            logger.error(f"Vault key rotation failed: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check Vault backend health."""
        try:
            # Check authentication status
            if not self._client.is_authenticated():
                return False
            
            # Test encrypt/decrypt
            test_data = "health_check"
            encrypted = await self.encrypt(test_data)
            decrypted = await self.decrypt(encrypted)
            return decrypted == test_data
        except Exception:
            return False

    @property
    def key_id(self) -> str:
        """Return key identifier."""
        return f"vault_{self.mount_point}"


class EncryptionService:
    """Main encryption service supporting multiple backends."""

    def __init__(self):
        self._backends: Dict[SecretBackend, EncryptionBackend] = {}
        self._current_backend: Optional[EncryptionBackend] = None
        self._key_rotation_history: list = []

    async def initialize(self, backend_type: SecretBackend, **kwargs) -> None:
        """Initialize encryption service with specified backend."""
        try:
            if backend_type == SecretBackend.FERNET:
                backend = FernetBackend(**kwargs)
            elif backend_type == SecretBackend.AWS_KMS:
                backend = AWSKMSBackend(**kwargs)
            elif backend_type == SecretBackend.VAULT:
                backend = VaultBackend(**kwargs)
            else:
                raise ValueError(f"Unsupported encryption backend: {backend_type}")

            # Test backend health
            if not await backend.is_healthy():
                raise Exception(f"Encryption backend {backend_type} is not healthy")

            self._backends[backend_type] = backend
            self._current_backend = backend
            logger.info(f"Encryption service initialized with {backend_type} backend")

        except Exception as e:
            logger.error(f"Failed to initialize encryption service: {e}")
            raise

    async def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using current backend."""
        if not self._current_backend:
            raise Exception("Encryption service not initialized")
        
        try:
            ciphertext = await self._current_backend.encrypt(plaintext)
            logger.debug("Data encrypted successfully")
            return ciphertext
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    async def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext using current backend."""
        if not self._current_backend:
            raise Exception("Encryption service not initialized")
        
        try:
            plaintext = await self._current_backend.decrypt(ciphertext)
            logger.debug("Data decrypted successfully")
            return plaintext
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    async def rotate_encryption_key(self) -> Dict[str, Any]:
        """Rotate encryption key across all backends."""
        rotation_results = {}

        for backend_type, backend in self._backends.items():
            try:
                success = await backend.rotate_key()
                rotation_results[backend_type] = {
                    'success': success,
                    'key_id': backend.key_id,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                if success:
                    logger.info(f"Successfully rotated key for {backend_type}")
                else:
                    logger.warning(f"Failed to rotate key for {backend_type}")

            except Exception as e:
                logger.error(f"Key rotation failed for {backend_type}: {e}")
                rotation_results[backend_type] = {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

        # Record rotation history
        self._key_rotation_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'results': rotation_results
        })

        return rotation_results

    async def get_backend_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all encryption backends."""
        health_status = {}

        for backend_type, backend in self._backends.items():
            try:
                is_healthy = await backend.is_healthy()
                health_status[backend_type] = {
                    'healthy': is_healthy,
                    'key_id': backend.key_id,
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                health_status[backend_type] = {
                    'healthy': False,
                    'error': str(e),
                    'last_check': datetime.now(timezone.utc).isoformat()
                }

        return health_status

    @property
    def current_backend(self) -> Optional[SecretBackend]:
        """Get current encryption backend type."""
        return self._current_backend.backend_type if self._current_backend else None

    @property
    def key_rotation_history(self) -> list:
        """Get key rotation history."""
        return self._key_rotation_history.copy()

    async def generate_fernet_key(self) -> str:
        """Generate a new Fernet key for manual configuration."""
        if Fernet is None:
            raise ImportError("cryptography package not installed")
        
        key = Fernet.generate_key()
        return base64.urlsafe_b64encode(key).decode()


# Global encryption service instance
encryption_service = EncryptionService()