import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings
from app.credentials.crypto import CredentialCipher, CredentialDecryptionError
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.models import AuthenticatedUser


def user(subject: str, email: str = "same@example.com") -> AuthenticatedUser:
    return AuthenticatedUser(
        issuer="https://auth.example/issuer/", sub=subject, email=email,
        preferred_username=subject, scopes=["immich.read"],
    )


@pytest.mark.asyncio
async def test_encrypted_store_round_trip_and_no_plaintext(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32
    )
    await provider.initialize()
    await provider.store_api_key(
        user("one"), "immich-secret-value", {"id": "u1", "email": "i@example.com", "name": "I"}
    )
    credential = await provider.credential_for(user("one"))
    assert credential is not None and credential.token == "immich-secret-value"
    assert b"immich-secret-value" not in database.read_bytes()
    assert database.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_wrong_encryption_key_cannot_decrypt(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32
    )
    await provider.initialize()
    await provider.store_api_key(user("one"), "key-one", {"id": "u1"})
    wrong = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32
    )
    with pytest.raises(CredentialDecryptionError):
        await wrong.credential_for(user("one"))


@pytest.mark.asyncio
async def test_issuer_subject_isolation_and_disconnect(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32
    )
    await provider.initialize()
    await provider.store_api_key(user("one"), "key-one", {"id": "u1"})
    await provider.store_api_key(user("two"), "key-two", {"id": "u2"})
    one = await provider.credential_for(user("one"))
    two = await provider.credential_for(user("two"))
    assert one is not None and one.token == "key-one"
    assert two is not None and two.token == "key-two"
    await provider.delete_for(user("one"))
    assert await provider.credential_for(user("one")) is None
    assert await provider.credential_for(user("two")) is not None


def test_missing_encryption_configuration_fails():
    with pytest.raises(ValidationError, match="CREDENTIAL_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            immich_base_url="https://photo.example.com",
            oidc_issuer="https://auth.example/issuer/",
            oidc_client_id="mcp",
        )
