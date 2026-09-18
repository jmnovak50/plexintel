from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class SecretDecryptionError(RuntimeError):
    pass


class SecretProvider(Protocol):
    def encrypt(self, secret: SecretStr) -> str: ...

    def reveal(self, ciphertext: str) -> Iterator[str]: ...


class LocalEncryptedSecretProvider:
    """Authenticated local encryption behind the future KMS boundary."""

    def __init__(self, key: SecretStr | str) -> None:
        raw = key.get_secret_value() if isinstance(key, SecretStr) else key
        try:
            self._fernet = Fernet(raw.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("credential encryption key is invalid") from exc

    def encrypt(self, secret: SecretStr) -> str:
        value = secret.get_secret_value()
        if not value:
            raise ValueError("credential must not be empty")
        return self._fernet.encrypt(value.encode()).decode("ascii")

    @contextmanager
    def reveal(self, ciphertext: str) -> Iterator[str]:
        try:
            value = self._fernet.decrypt(ciphertext.encode("ascii")).decode()
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise SecretDecryptionError("stored credential cannot be decrypted") from exc
        try:
            yield value
        finally:
            value = ""
