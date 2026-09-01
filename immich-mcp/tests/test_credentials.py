import sqlite3

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings
from app.credentials.crypto import CredentialCipher, CredentialDecryptionError
from app.credentials.models import BrowserIdentity
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.models import AuthenticatedUser


def user(
    subject: str,
    email: str = "same@example.com",
    *,
    namespace: str = "authentik",
    issuer: str = "https://auth.example/application/o/immich-mcp/",
) -> AuthenticatedUser:
    return AuthenticatedUser(
        identity_namespace=namespace, issuer=issuer, sub=subject, email=email,
        preferred_username=subject, scopes=["immich.read"],
    )


@pytest.mark.asyncio
async def test_encrypted_store_round_trip_and_no_plaintext(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32, "authentik"
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
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32, "authentik"
    )
    await provider.initialize()
    await provider.store_api_key(user("one"), "key-one", {"id": "u1"})
    wrong = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32, "authentik"
    )
    with pytest.raises(CredentialDecryptionError):
        await wrong.credential_for(user("one"))


@pytest.mark.asyncio
async def test_namespace_subject_isolation_and_disconnect(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32, "authentik"
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


@pytest.mark.asyncio
async def test_account_and_mcp_issuers_share_namespace_subject_credential(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32, "authentik"
    )
    await provider.initialize()
    account_identity = BrowserIdentity(
        identity_namespace="authentik",
        issuer="https://auth.example.com/application/o/immich-mcp-account/",
        subject="abc123",
    )
    await provider.store_api_key(account_identity, "shared-key", {"id": "u1"})

    mcp_identity = user(
        "abc123", issuer="https://auth.example.com/application/o/immich-mcp/"
    )
    credential = await provider.credential_for(mcp_identity)
    assert credential is not None and credential.token == "shared-key"


@pytest.mark.asyncio
async def test_same_subject_in_different_namespaces_is_isolated(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    provider = SQLiteCredentialProvider(
        database, CredentialCipher(Fernet.generate_key().decode()), "s" * 32, "authentik"
    )
    await provider.initialize()
    await provider.store_api_key(user("abc123"), "key-one", {"id": "u1"})
    await provider.store_api_key(
        user("abc123", namespace="another-idp"), "key-two", {"id": "u2"}
    )
    first = await provider.credential_for(user("abc123"))
    second = await provider.credential_for(user("abc123", namespace="another-idp"))
    assert first is not None and first.token == "key-one"
    assert second is not None and second.token == "key-two"


@pytest.mark.asyncio
async def test_legacy_issuer_schema_migrates_without_discarding_credential(tmp_path):
    database = tmp_path / "credentials.sqlite3"
    cipher = CredentialCipher(Fernet.generate_key().decode())
    with sqlite3.connect(database) as db:
        db.execute(
            """CREATE TABLE user_credentials (
                issuer TEXT NOT NULL, subject TEXT NOT NULL, encrypted_api_key TEXT NOT NULL,
                oidc_email TEXT, oidc_username TEXT, immich_user_id TEXT, immich_email TEXT,
                immich_name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                last_validated_at TEXT NOT NULL, PRIMARY KEY (issuer, subject))"""
        )
        db.execute(
            """INSERT INTO user_credentials VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL,
                                                      ?, ?, ?)""",
            ("https://old.example/issuer/", "abc123", cipher.encrypt("legacy-key"),
             "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
             "2026-01-01T00:00:00+00:00"),
        )
    provider = SQLiteCredentialProvider(database, cipher, "s" * 32, "authentik")
    await provider.initialize()
    credential = await provider.credential_for(user("abc123"))
    assert credential is not None and credential.token == "legacy-key"
    with sqlite3.connect(database) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(user_credentials)")}
    assert "identity_namespace" in columns
    assert "source_issuer" in columns
    assert "issuer" not in columns


def test_missing_encryption_configuration_fails():
    with pytest.raises(ValidationError, match="CREDENTIAL_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            immich_base_url="https://photo.example.com",
            oidc_issuer="https://auth.example/issuer/",
            oidc_client_id="mcp",
        )
