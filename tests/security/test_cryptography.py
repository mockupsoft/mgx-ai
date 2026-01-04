import pytest


@pytest.mark.asyncio
async def test_fernet_backend_encrypt_decrypt_roundtrip() -> None:
    from backend.services.secrets.encryption import FernetBackend

    try:
        backend = FernetBackend()
    except ImportError:
        pytest.skip("cryptography not installed")

    plaintext = "hello"
    ciphertext = await backend.encrypt(plaintext)

    assert ciphertext != plaintext
    assert await backend.decrypt(ciphertext) == plaintext
