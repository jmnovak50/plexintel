import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.credentials.crypto import CredentialCipher
from app.credentials.models import BrowserIdentity, BrowserSession, CredentialStatus, OAuthState
from app.immich.albums import PrivateImmichCredentialProvider
from app.immich.models import AuthenticatedUser, PrivateImmichCredential


USER_CREDENTIALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_credentials (
    identity_namespace TEXT NOT NULL,
    subject TEXT NOT NULL,
    source_issuer TEXT NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    oidc_email TEXT,
    oidc_username TEXT,
    immich_user_id TEXT,
    immich_email TEXT,
    immich_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_validated_at TEXT NOT NULL,
    PRIMARY KEY (identity_namespace, subject)
);
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS browser_sessions (
    session_hash TEXT PRIMARY KEY,
    identity_namespace TEXT NOT NULL,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    email TEXT,
    preferred_username TEXT,
    csrf_token TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_states (
    state_hash TEXT PRIMARY KEY,
    nonce TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


class SQLiteCredentialProvider(PrivateImmichCredentialProvider):
    def __init__(
        self, path: Path, cipher: CredentialCipher, session_secret: str, identity_namespace: str
    ) -> None:
        self.path = path
        self.cipher = cipher
        self._session_secret = session_secret.encode("utf-8")
        self.identity_namespace = identity_namespace

    async def initialize(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await self._migrate_user_credentials(db)
            await db.execute(USER_CREDENTIALS_SCHEMA)
            await db.executescript(SCHEMA)
            await self._migrate_browser_sessions(db)
            await db.commit()
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    async def ready(self) -> bool:
        try:
            async with aiosqlite.connect(self.path) as db:
                row = await (await db.execute("SELECT 1")).fetchone()
            return row == (1,)
        except (OSError, aiosqlite.Error):
            return False

    async def store_api_key(
        self, user: AuthenticatedUser | BrowserIdentity, api_key: str, immich_user: dict[str, Any]
    ) -> None:
        identity_namespace, subject = _identity_key(user)
        timestamp = _now().isoformat()
        encrypted = self.cipher.encrypt(api_key)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO user_credentials (
                    identity_namespace, subject, source_issuer, encrypted_api_key, oidc_email,
                    oidc_username, immich_user_id, immich_email, immich_name, created_at,
                    updated_at, last_validated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(identity_namespace, subject) DO UPDATE SET
                    source_issuer=excluded.source_issuer,
                    encrypted_api_key=excluded.encrypted_api_key,
                    oidc_email=excluded.oidc_email,
                    oidc_username=excluded.oidc_username,
                    immich_user_id=excluded.immich_user_id,
                    immich_email=excluded.immich_email,
                    immich_name=excluded.immich_name,
                    updated_at=excluded.updated_at,
                    last_validated_at=excluded.last_validated_at
                """,
                (
                    identity_namespace,
                    subject,
                    user.issuer,
                    encrypted,
                    user.email,
                    user.preferred_username,
                    _text(immich_user.get("id")),
                    _text(immich_user.get("email")),
                    _text(immich_user.get("name")),
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            await db.commit()

    async def credential_for(self, user: AuthenticatedUser) -> PrivateImmichCredential | None:
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute(
                    """SELECT encrypted_api_key FROM user_credentials
                       WHERE identity_namespace=? AND subject=?""",
                    (user.identity_namespace, user.sub),
                )
            ).fetchone()
        if row is None:
            return None
        return PrivateImmichCredential(kind="api_key", token=self.cipher.decrypt(str(row[0])))

    async def status_for(
        self, user: AuthenticatedUser | BrowserIdentity
    ) -> CredentialStatus | None:
        identity_namespace, subject = _identity_key(user)
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    """SELECT identity_namespace, source_issuer, subject, immich_user_id,
                              immich_email, immich_name, created_at, updated_at, last_validated_at
                       FROM user_credentials WHERE identity_namespace=? AND subject=?""",
                    (identity_namespace, subject),
                )
            ).fetchone()
        if row is None:
            return None
        return CredentialStatus(
            identity_namespace=row["identity_namespace"],
            source_issuer=row["source_issuer"],
            subject=row["subject"],
            immich_user_id=row["immich_user_id"],
            immich_email=row["immich_email"],
            immich_name=row["immich_name"],
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
            validated_at_on_connect=_parse(row["last_validated_at"]),
        )

    async def delete_for(self, user: AuthenticatedUser | BrowserIdentity) -> bool:
        identity_namespace, subject = _identity_key(user)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "DELETE FROM user_credentials WHERE identity_namespace=? AND subject=?",
                (identity_namespace, subject),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def create_oauth_state(self, state: str, nonce: str, code_verifier: str, ttl: int) -> None:
        expires = (_now() + timedelta(seconds=ttl)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (_now().isoformat(),))
            await db.execute(
                "INSERT INTO oauth_states (state_hash, nonce, code_verifier, expires_at) VALUES (?, ?, ?, ?)",
                (self._digest(state), nonce, code_verifier, expires),
            )
            await db.commit()

    async def consume_oauth_state(self, state: str) -> OAuthState | None:
        state_hash = self._digest(state)
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute(
                    "SELECT nonce, code_verifier, expires_at FROM oauth_states WHERE state_hash=?",
                    (state_hash,),
                )
            ).fetchone()
            await db.execute("DELETE FROM oauth_states WHERE state_hash=?", (state_hash,))
            await db.commit()
        if row is None or _parse(str(row[2])) <= _now():
            return None
        return OAuthState(nonce=str(row[0]), code_verifier=str(row[1]), expires_at=_parse(str(row[2])))

    async def create_browser_session(
        self, identity: BrowserIdentity, ttl: int
    ) -> tuple[str, BrowserSession]:
        session_id = secrets.token_urlsafe(32)
        session = BrowserSession(
            identity=identity,
            csrf_token=secrets.token_urlsafe(32),
            expires_at=_now() + timedelta(seconds=ttl),
        )
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM browser_sessions WHERE expires_at <= ?", (_now().isoformat(),)
            )
            await db.execute(
                """INSERT INTO browser_sessions
                   (session_hash, identity_namespace, issuer, subject, email, preferred_username,
                    csrf_token, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self._digest(session_id),
                    identity.identity_namespace,
                    identity.issuer,
                    identity.subject,
                    identity.email,
                    identity.preferred_username,
                    session.csrf_token,
                    session.expires_at.isoformat(),
                ),
            )
            await db.commit()
        return session_id, session

    async def browser_session(self, session_id: str | None) -> BrowserSession | None:
        if not session_id:
            return None
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute(
                    """SELECT identity_namespace, issuer, subject, email, preferred_username,
                              csrf_token, expires_at
                       FROM browser_sessions WHERE session_hash=?""",
                    (self._digest(session_id),),
                )
            ).fetchone()
        if row is None or _parse(str(row[6])) <= _now():
            return None
        return BrowserSession(
            identity=BrowserIdentity(
                identity_namespace=str(row[0]), issuer=str(row[1]), subject=str(row[2]),
                email=row[3], preferred_username=row[4],
            ),
            csrf_token=str(row[5]),
            expires_at=_parse(str(row[6])),
        )

    async def delete_browser_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM browser_sessions WHERE session_hash=?", (self._digest(session_id),)
            )
            await db.commit()

    def _digest(self, value: str) -> str:
        return hmac.new(self._session_secret, value.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _migrate_user_credentials(self, db: aiosqlite.Connection) -> None:
        columns = await _table_columns(db, "user_credentials")
        if not columns or "identity_namespace" in columns:
            return
        if "issuer" not in columns:
            raise RuntimeError("Unsupported credential database schema")
        duplicates = await (
            await db.execute(
                "SELECT subject FROM user_credentials GROUP BY subject HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).fetchone()
        if duplicates is not None:
            raise RuntimeError(
                "Credential migration found multiple issuer records for one subject; "
                "resolve the duplicate records before startup"
            )
        try:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute("ALTER TABLE user_credentials RENAME TO user_credentials_issuer_v1")
            await db.execute(USER_CREDENTIALS_SCHEMA)
            await db.execute(
                """INSERT INTO user_credentials (
                       identity_namespace, subject, source_issuer, encrypted_api_key, oidc_email,
                       oidc_username, immich_user_id, immich_email, immich_name, created_at,
                       updated_at, last_validated_at
                   )
                   SELECT ?, subject, issuer, encrypted_api_key, oidc_email, oidc_username,
                          immich_user_id, immich_email, immich_name, created_at, updated_at,
                          last_validated_at
                   FROM user_credentials_issuer_v1""",
                (self.identity_namespace,),
            )
            await db.execute("DROP TABLE user_credentials_issuer_v1")
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    async def _migrate_browser_sessions(self, db: aiosqlite.Connection) -> None:
        columns = await _table_columns(db, "browser_sessions")
        if columns and "identity_namespace" not in columns:
            await db.execute("ALTER TABLE browser_sessions ADD COLUMN identity_namespace TEXT")
            await db.execute(
                "UPDATE browser_sessions SET identity_namespace=? WHERE identity_namespace IS NULL",
                (self.identity_namespace,),
            )


def _identity_key(user: AuthenticatedUser | BrowserIdentity) -> tuple[str, str]:
    subject = user.sub if isinstance(user, AuthenticatedUser) else user.subject
    return user.identity_namespace, subject


async def _table_columns(db: aiosqlite.Connection, table: str) -> set[str]:
    rows = await (await db.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


def _text(value: Any) -> str | None:
    return None if value is None else str(value)
