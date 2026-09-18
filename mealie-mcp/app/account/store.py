from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AccountOAuthState, AccountSession


@dataclass(frozen=True)
class OAuthState:
    nonce: str
    code_verifier: str
    expires_at: datetime


@dataclass(frozen=True)
class BrowserSession:
    subject: str
    issuer: str
    email: str | None
    preferred_username: str | None
    csrf_token: str
    expires_at: datetime


class AccountStore:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        session_secret: SecretStr,
    ) -> None:
        self._sessions = sessions
        self._secret = session_secret.get_secret_value().encode("utf-8")

    async def create_oauth_state(
        self,
        state: str,
        nonce: str,
        code_verifier: str,
        ttl_seconds: int,
    ) -> None:
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            await session.execute(delete(AccountOAuthState).where(AccountOAuthState.expires_at <= now))
            session.add(
                AccountOAuthState(
                    state_hash=self._digest("state", state),
                    nonce=nonce,
                    code_verifier=code_verifier,
                    expires_at=now + timedelta(seconds=ttl_seconds),
                )
            )

    async def consume_oauth_state(self, state: str) -> OAuthState | None:
        async with self._sessions.begin() as session:
            result = await session.execute(
                delete(AccountOAuthState)
                .where(AccountOAuthState.state_hash == self._digest("state", state))
                .returning(
                    AccountOAuthState.nonce,
                    AccountOAuthState.code_verifier,
                    AccountOAuthState.expires_at,
                )
            )
            row = result.first()
        if row is None or _as_utc(row.expires_at) <= datetime.now(UTC):
            return None
        return OAuthState(
            nonce=row.nonce,
            code_verifier=row.code_verifier,
            expires_at=_as_utc(row.expires_at),
        )

    async def create_session(
        self,
        *,
        subject: str,
        issuer: str,
        email: str | None,
        preferred_username: str | None,
        ttl_seconds: int,
    ) -> str:
        token = secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            await session.execute(delete(AccountSession).where(AccountSession.expires_at <= now))
            session.add(
                AccountSession(
                    token_hash=self._digest("session", token),
                    subject=subject,
                    issuer=issuer,
                    email=email,
                    preferred_username=preferred_username,
                    expires_at=now + timedelta(seconds=ttl_seconds),
                )
            )
        return token

    async def get_session(self, token: str | None) -> BrowserSession | None:
        if not token:
            return None
        digest = self._digest("session", token)
        async with self._sessions.begin() as session:
            value = await session.scalar(select(AccountSession).where(AccountSession.token_hash == digest))
            if value is None:
                return None
            expires_at = _as_utc(value.expires_at)
            if expires_at <= datetime.now(UTC):
                await session.delete(value)
                return None
            return BrowserSession(
                subject=value.subject,
                issuer=value.issuer,
                email=value.email,
                preferred_username=value.preferred_username,
                csrf_token=self._csrf_token(token),
                expires_at=expires_at,
            )

    async def delete_session(self, token: str | None) -> None:
        if not token:
            return
        async with self._sessions.begin() as session:
            await session.execute(
                delete(AccountSession).where(AccountSession.token_hash == self._digest("session", token))
            )

    def _digest(self, purpose: str, value: str) -> str:
        return hmac.new(
            self._secret,
            f"{purpose}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _csrf_token(self, session_token: str) -> str:
        digest = hmac.new(
            self._secret,
            f"csrf:{session_token}".encode(),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
