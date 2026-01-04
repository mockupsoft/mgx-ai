import pytest

from backend.config import Settings


def test_production_rejects_default_db_password() -> None:
    with pytest.raises(ValueError):
        Settings(
            mgx_env="production",
            db_password="postgres",
            secret_encryption_backend="aws_kms",
            aws_kms_key_id="dummy",
        )


def test_production_requires_fernet_key_if_backend_fernet() -> None:
    with pytest.raises(ValueError):
        Settings(
            mgx_env="production",
            db_password="not-default",
            secret_encryption_backend="fernet",
        )
