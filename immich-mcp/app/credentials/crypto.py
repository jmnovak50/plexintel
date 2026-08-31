from cryptography.fernet import Fernet, InvalidToken


class CredentialDecryptionError(RuntimeError):
    """A stored credential cannot be decrypted with the configured key."""


class CredentialCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ValueError("credential encryption key is invalid") from exc

    def encrypt(self, value: str) -> str:
        if not value:
            raise ValueError("credential must not be empty")
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise CredentialDecryptionError("stored credential could not be decrypted") from exc
