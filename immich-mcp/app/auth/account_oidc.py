import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlsplit

from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.auth.oidc import OIDCConfigurationError, OIDCJWTVerifier
from app.config import Settings


class AccountOIDC:
    def __init__(self, settings: Settings, verifier: OIDCJWTVerifier) -> None:
        self.settings = settings
        self.verifier = verifier

    async def authorization_url(self, state: str, nonce: str, code_verifier: str) -> str:
        metadata = await self.verifier.metadata()
        endpoint = self._issuer_endpoint(metadata, "authorization_endpoint")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        async with self._oauth_client() as oauth:
            url, _ = oauth.create_authorization_url(
                endpoint,
                state=state,
                nonce=nonce,
                code_challenge=challenge,
                code_challenge_method="S256",
            )
        return url

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        metadata = await self.verifier.metadata()
        endpoint = self._issuer_endpoint(metadata, "token_endpoint")
        async with self._oauth_client() as oauth:
            token = await oauth.fetch_token(
                endpoint,
                code=code,
                grant_type="authorization_code",
                redirect_uri=str(self.settings.account_redirect_uri),
                code_verifier=code_verifier,
            )
        if not isinstance(token, dict):
            raise OIDCConfigurationError("OIDC token response is malformed")
        return token

    def _oauth_client(self) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=str(self.settings.account_oidc_client_id),
            client_secret=self.settings.account_oidc_client_secret.get_secret_value(),  # type: ignore[union-attr]
            redirect_uri=str(self.settings.account_redirect_uri),
            scope=self.settings.account_scopes,
            timeout=self.settings.http_timeout_seconds,
            verify=self.settings.tls_verify,
        )

    def _issuer_endpoint(self, metadata: dict[str, Any], name: str) -> str:
        endpoint = metadata.get(name)
        if not isinstance(endpoint, str):
            raise OIDCConfigurationError(f"OIDC discovery is missing {name}")
        issuer = urlsplit(str(self.settings.oidc_issuer))
        candidate = urlsplit(endpoint)
        if (candidate.scheme, candidate.hostname, candidate.port) != (
            issuer.scheme,
            issuer.hostname,
            issuer.port,
        ):
            raise OIDCConfigurationError(f"OIDC {name} must use the issuer host")
        return endpoint


def new_oauth_values() -> tuple[str, str, str]:
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
