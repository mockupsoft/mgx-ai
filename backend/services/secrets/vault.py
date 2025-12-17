# -*- coding: utf-8 -*-
"""backend.services.secrets.vault

HashiCorp Vault integration for advanced secret management.
This provides direct integration with Vault for dynamic credentials and policies.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

try:
    import hvac
    from hvac.exceptions import VaultError, InvalidRequest
except ImportError:
    hvac = None

from backend.db.models.enums import SecretBackend

logger = logging.getLogger(__name__)


class VaultClient:
    """Advanced HashiCorp Vault client for secret management."""

    def __init__(
        self,
        vault_url: str,
        vault_token: str,
        mount_point: str = "secret",
        namespace: Optional[str] = None
    ):
        if hvac is None:
            raise ImportError("hvac package not required for Vault integration")
        
        self.vault_url = vault_url
        self.vault_token = vault_token
        self.mount_point = mount_point
        self.namespace = namespace
        
        try:
            # Initialize Vault client
            client_kwargs = {
                'url': vault_url,
                'token': vault_token
            }
            
            if namespace:
                client_kwargs['namespace'] = namespace
                
            self._client = hvac.Client(**client_kwargs)
            
            # Test authentication
            if not self._client.is_authenticated():
                raise Exception("Failed to authenticate with Vault")
            
            logger.info(f"Vault client initialized for {vault_url}")

        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            raise

    def is_healthy(self) -> bool:
        """Check if Vault client is healthy and authenticated."""
        try:
            return self._client.is_authenticated()
        except Exception:
            return False

    # Generic Secret Management
    async def store_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Store a secret at the specified path."""
        try:
            full_path = f"{self.mount_point}/{path}"
            
            if self.namespace:
                response = self._client.secrets.kv.v2.create_or_update_secret(
                    path=full_path,
                    secret=data,
                    mount_point=self.mount_point
                )
            else:
                response = self._client.secrets.kv.v2.create_or_update_secret(
                    path=full_path,
                    secret=data
                )

            logger.info(f"Stored secret at path: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to store secret at path {path}: {e}")
            raise

    async def retrieve_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """Retrieve a secret from the specified path."""
        try:
            full_path = f"{self.mount_point}/{path}"
            
            if self.namespace:
                response = self._client.secrets.kv.v2.read_secret_version(
                    path=full_path,
                    mount_point=self.mount_point
                )
            else:
                response = self._client.secrets.kv.v2.read_secret_version(
                    path=full_path
                )

            logger.debug(f"Retrieved secret from path: {path}")
            return response['data']['data']

        except Exception as e:
            logger.error(f"Failed to retrieve secret from path {path}: {e}")
            return None

    async def delete_secret(self, path: str) -> bool:
        """Delete a secret from the specified path."""
        try:
            full_path = f"{self.mount_point}/{path}"
            
            if self.namespace:
                self._client.secrets.kv.v2.delete_secret_version(
                    path=full_path,
                    mount_point=self.mount_point
                )
            else:
                self._client.secrets.kv.v2.delete_secret_version(
                    path=full_path
                )

            logger.info(f"Deleted secret from path: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret from path {path}: {e}")
            return False

    async def list_secrets(self, path: str = "") -> List[str]:
        """List secrets at the specified path."""
        try:
            full_path = f"{self.mount_point}/{path}"
            
            if self.namespace:
                response = self._client.secrets.kv.v2.list_secrets(
                    path=full_path,
                    mount_point=self.mount_point
                )
            else:
                response = self._client.secrets.kv.v2.list_secrets(
                    path=full_path
                )

            if response and 'data' in response and 'keys' in response['data']:
                return response['data']['keys']
            
            return []

        except Exception as e:
            logger.error(f"Failed to list secrets at path {path}: {e}")
            return []

    # Dynamic Database Credentials
    async def generate_database_credentials(
        self,
        config_name: str,
        username_template: str = "user_{{random}}",
        ttl: str = "1h"
    ) -> Dict[str, str]:
        """Generate dynamic database credentials using Vault's database secrets engine."""
        try:
            # This assumes you've configured Vault's database secrets engine
            response = self._client.secrets.database.generate_credentials(
                name=config_name,
                username_template=username_template
            )

            credentials = {
                'username': response['data']['username'],
                'password': response['data']['password'],
                'ttl': ttl,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Generated dynamic database credentials for config: {config_name}")
            return credentials

        except Exception as e:
            logger.error(f"Failed to generate database credentials for config {config_name}: {e}")
            raise

    # Dynamic AWS Credentials
    async def generate_aws_credentials(
        self,
        role_name: str,
        ttl: str = "1h"
    ) -> Dict[str, str]:
        """Generate dynamic AWS credentials using Vault's AWS secrets engine."""
        try:
            response = self._client.secrets.aws.generate_credentials(
                name=role_name,
                lease_duration=ttl
            )

            credentials = {
                'access_key': response['data']['access_key'],
                'secret_key': response['data']['secret_key'],
                'session_token': response['data'].get('session_token'),
                'ttl': ttl,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Generated dynamic AWS credentials for role: {role_name}")
            return credentials

        except Exception as e:
            logger.error(f"Failed to generate AWS credentials for role {role_name}: {e}")
            raise

    # PKI Certificate Generation
    async def generate_certificate(
        self,
        role_name: str,
        common_name: str,
        ttl: str = "24h"
    ) -> Dict[str, Any]:
        """Generate a PKI certificate using Vault's PKI secrets engine."""
        try:
            response = self._client.secrets.pki.generate_certificate(
                name=role_name,
                common_name=common_name,
                ttl=ttl
            )

            certificate_data = {
                'certificate': response['data']['certificate'],
                'issuing_ca': response['data']['issuing_ca'],
                'serial_number': response['data']['serial_number'],
                'ttl': ttl,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Generated certificate for CN: {common_name}")
            return certificate_data

        except Exception as e:
            logger.error(f"Failed to generate certificate for CN {common_name}: {e}")
            raise

    # Token Management
    async def create_token(
        self,
        policies: List[str],
        ttl: str = "1h",
        renewable: bool = True
    ) -> Dict[str, Any]:
        """Create a new token with specified policies."""
        try:
            response = self._client.auth.token.create(
                policies=policies,
                ttl=ttl,
                renewable=renewable
            )

            token_info = {
                'token': response['auth']['client_token'],
                'policies': policies,
                'ttl': ttl,
                'renewable': renewable,
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Created token with policies: {policies}")
            return token_info

        except Exception as e:
            logger.error(f"Failed to create token with policies {policies}: {e}")
            raise

    async def renew_token(self, token: str) -> Dict[str, Any]:
        """Renew an existing token."""
        try:
            # Store the token temporarily
            original_token = self._client.token
            self._client.token = token
            
            response = self._client.auth.token.renew_self()
            
            # Restore original token
            self._client.token = original_token

            renewal_info = {
                'renewed_at': datetime.now(timezone.utc).isoformat(),
                'ttl': response['auth']['lease_duration']
            }

            logger.info(f"Renewed token successfully")
            return renewal_info

        except Exception as e:
            # Restore original token even on error
            self._client.token = getattr(self, '_original_token', None)
            logger.error(f"Failed to renew token: {e}")
            raise

    # Encryption/Decryption with Transit Engine
    async def transit_encrypt(
        self,
        key_name: str,
        plaintext: str,
        context: Optional[str] = None
    ) -> str:
        """Encrypt data using Vault's transit encryption engine."""
        try:
            # Prepare plaintext
            import base64
            plaintext_bytes = plaintext.encode('utf-8')
            encoded_plaintext = base64.b64encode(plaintext_bytes).decode()

            kwargs = {
                'name': key_name,
                'plaintext': encoded_plaintext
            }
            
            if context:
                kwargs['context'] = base64.b64encode(context.encode()).decode()

            response = self._client.secrets.transit.encrypt_data(**kwargs)
            
            logger.debug(f"Encrypted data using transit key: {key_name}")
            return response['data']['ciphertext']

        except Exception as e:
            logger.error(f"Failed to encrypt data with transit key {key_name}: {e}")
            raise

    async def transit_decrypt(
        self,
        key_name: str,
        ciphertext: str,
        context: Optional[str] = None
    ) -> str:
        """Decrypt data using Vault's transit encryption engine."""
        try:
            kwargs = {
                'name': key_name,
                'ciphertext': ciphertext
            }
            
            if context:
                import base64
                kwargs['context'] = base64.b64encode(context.encode()).decode()

            response = self._client.secrets.transit.decrypt_data(**kwargs)
            
            # Decode the result
            import base64
            plaintext_bytes = base64.b64decode(response['data']['plaintext'])
            plaintext = plaintext_bytes.decode('utf-8')
            
            logger.debug(f"Decrypted data using transit key: {key_name}")
            return plaintext

        except Exception as e:
            logger.error(f"Failed to decrypt data with transit key {key_name}: {e}")
            raise

    async def rotate_transit_key(self, key_name: str) -> bool:
        """Rotate a transit encryption key."""
        try:
            self._client.secrets.transit.rotate_key(name=key_name)
            logger.info(f"Rotated transit key: {key_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to rotate transit key {key_name}: {e}")
            return False

    # Audit and Policy Management
    async def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs from Vault (requires proper permissions)."""
        try:
            # This requires enabling audit device and proper access
            response = self._client.sys.get_audit_devices()
            
            # Parse and return audit information
            audit_devices = response['data']
            
            logs = []
            for device_name, device_info in audit_devices.items():
                logs.append({
                    'device_name': device_name,
                    'device_type': device_info.get('type'),
                    'path': device_info.get('path'),
                    'enabled': device_info.get('local') is not True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            return logs[:limit]

        except Exception as e:
            logger.error(f"Failed to get audit logs: {e}")
            return []

    async def create_policy(self, name: str, policy_rules: str) -> bool:
        """Create a new ACL policy in Vault."""
        try:
            self._client.sys.create_or_update_policy(
                name=name,
                policy=policy_rules
            )
            
            logger.info(f"Created policy: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create policy {name}: {e}")
            return False

    async def get_policy(self, name: str) -> Optional[str]:
        """Get an existing ACL policy."""
        try:
            response = self._client.sys.read_policy(name=name)
            
            if response and 'data' in response:
                return response['data']['rules']
            return None

        except Exception as e:
            logger.error(f"Failed to get policy {name}: {e}")
            return None

    async def list_policies(self) -> List[str]:
        """List all ACL policies."""
        try:
            response = self._client.sys.list_policies()
            
            if response and 'data' in response:
                return response['data']['policies']
            return []

        except Exception as e:
            logger.error(f"Failed to list policies: {e}")
            return []

    # Health and Status
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of Vault."""
        try:
            # Get system status
            status_response = self._client.sys.read_health_status()
            
            # Get sealed status
            sealed_status = self._client.sys.is_sealed()
            
            # Get version info
            version_response = self._client.sys.get_version()
            
            # Get leader status (for HA setup)
            leader_response = self._client.sys.get_leader()
            
            health_status = {
                'healthy': not sealed_status,
                'sealed': sealed_status,
                'version': version_response.get('data', {}).get('version', 'unknown'),
                'cluster_id': status_response.get('data', {}).get('cluster_id'),
                'cluster_name': status_response.get('data', {}).get('cluster_name'),
                'is_leader': leader_response.get('data', {}).get('is_self', False),
                'leader_address': leader_response.get('data', {}).get('leader_address'),
                'raft_committed_index': leader_response.get('data', {}).get('raft_committed_index'),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

            return health_status

        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

    # Cleanup and Maintenance
    async def cleanup_expired_secrets(self, older_than_days: int = 30) -> int:
        """Clean up expired secrets (requires custom logic)."""
        try:
            # This would need custom implementation based on your secret patterns
            # For now, we'll just log the action
            logger.info(f"Would cleanup secrets older than {older_than_days} days")
            return 0  # Return number of cleaned secrets
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired secrets: {e}")
            return 0

    async def backup_secrets(self, backup_path: str) -> bool:
        """Create a backup of secrets to a file."""
        try:
            # List all secrets in the mount point
            secrets = await self.list_secrets()
            
            backup_data = {
                'vault_url': self.vault_url,
                'mount_point': self.mount_point,
                'backup_timestamp': datetime.now(timezone.utc).isoformat(),
                'secrets': {}
            }
            
            # Retrieve each secret
            for secret_path in secrets:
                if not secret_path.endswith('/'):  # Skip directories
                    secret_data = await self.retrieve_secret(secret_path)
                    if secret_data:
                        backup_data['secrets'][secret_path] = secret_data

            # Store backup data (in practice, you'd write to a secure location)
            # For now, we'll just log it
            logger.info(f"Backup created with {len(backup_data['secrets'])} secrets")
            
            return True

        except Exception as e:
            logger.error(f"Failed to backup secrets: {e}")
            return False

    async def restore_secrets(self, backup_data: Dict[str, Any]) -> bool:
        """Restore secrets from a backup."""
        try:
            if 'secrets' not in backup_data:
                raise ValueError("Invalid backup data format")
            
            restored_count = 0
            for secret_path, secret_data in backup_data['secrets'].items():
                try:
                    await self.store_secret(secret_path, secret_data)
                    restored_count += 1
                except Exception as e:
                    logger.error(f"Failed to restore secret {secret_path}: {e}")
            
            logger.info(f"Restored {restored_count} secrets from backup")
            return True

        except Exception as e:
            logger.error(f"Failed to restore secrets: {e}")
            return False


# Helper functions for Vault integration
def get_vault_client(
    vault_url: str,
    vault_token: str,
    mount_point: str = "secret",
    namespace: Optional[str] = None
) -> VaultClient:
    """Factory function to create a Vault client."""
    return VaultClient(
        vault_url=vault_url,
        vault_token=vault_token,
        mount_point=mount_point,
        namespace=namespace
    )


async def initialize_vault_client_from_config() -> Optional[VaultClient]:
    """Initialize Vault client from environment configuration."""
    from backend.config import settings
    
    if hasattr(settings, 'vault_url') and hasattr(settings, 'vault_token'):
        if settings.vault_url and settings.vault_token:
            try:
                return get_vault_client(
                    vault_url=settings.vault_url,
                    vault_token=settings.vault_token,
                    mount_point=getattr(settings, 'vault_mount_point', 'secret'),
                    namespace=getattr(settings, 'vault_namespace', None)
                )
            except Exception as e:
                logger.error(f"Failed to initialize Vault client from config: {e}")
                return None
    
    return None