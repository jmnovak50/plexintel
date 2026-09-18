from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from app.security.redaction import redact_text, safe_fields
from app.security.secrets import LocalEncryptedSecretProvider, SecretDecryptionError


def test_token_is_encrypted_and_never_in_provider_errors_or_repr(settings, caplog):
    token = "mealie-secret-canary"
    provider = LocalEncryptedSecretProvider(settings.credential_encryption_key)
    ciphertext = provider.encrypt(SecretStr(token))
    assert token not in ciphertext
    with provider.reveal(ciphertext) as plaintext:
        assert plaintext == token
    with pytest.raises(SecretDecryptionError) as caught, provider.reveal(ciphertext[:-2] + "xx"):
        pass
    logging.getLogger("test").error("%s", caught.value)
    assert token not in str(caught.value) + caplog.text


def test_redaction_removes_bearer_credentials_and_sensitive_fields():
    token = "secret.header.payload"
    assert token not in redact_text(f"Authorization: Bearer {token}")
    assert safe_fields({"authorization": token, "status": 200}) == {
        "authorization": "[REDACTED]",
        "status": "200",
    }
