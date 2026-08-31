"""Encrypted per-user Immich credential storage."""

from app.credentials.sqlite import SQLiteCredentialProvider

__all__ = ["SQLiteCredentialProvider"]
