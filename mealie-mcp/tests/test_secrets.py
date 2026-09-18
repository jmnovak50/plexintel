from __future__ import annotations

import logging

import pytest
import structlog
from pydantic import SecretStr

from app.observability.logging import configure_logging
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
        "status": 200,
    }


def test_structured_logging_pipeline_redacts_nested_secrets(capsys):
    canaries = {
        "authorization": "Bearer authorization-canary",
        "api_token": "api-token-canary",
        "client_secret": "client-secret-canary",
        "refresh_token": "refresh-token-canary",
    }
    configure_logging("INFO")
    structlog.get_logger("redaction-test").info(
        "Bearer event-canary",
        nested={
            "values": [canaries, {"safe": "Bearer nested-canary"}],
            "tuple": ("visible", {"credential": "credential-canary"}),
        },
    )
    output = capsys.readouterr().out
    for canary in (
        "authorization-canary",
        "api-token-canary",
        "client-secret-canary",
        "refresh-token-canary",
        "event-canary",
        "nested-canary",
        "credential-canary",
    ):
        assert canary not in output
    assert output.count("[REDACTED]") >= 7
