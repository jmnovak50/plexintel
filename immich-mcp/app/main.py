import html
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import quote

import httpx
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from mcp.server.transport_security import TransportSecuritySettings

from app.account.routes import account_router
from app.auth.account_oidc import AccountOIDC
from app.auth.oidc import OIDCJWTVerifier
from app.config import Settings, get_settings
from app.credentials.crypto import CredentialCipher
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient, ImmichError
from app.immich.shares import validate_share_key
from app.mcp.server import create_mcp_server


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s")
    # httpx's INFO request line includes query parameters; Immich thumbnail URLs contain share keys.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
    )


def create_app(
    settings: Settings | None = None,
    *,
    immich_client: ImmichClient | None = None,
    oidc_client: httpx.AsyncClient | None = None,
    account_oidc_client: httpx.AsyncClient | None = None,
    credential_provider: SQLiteCredentialProvider | None = None,
    account_oidc: AccountOIDC | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    client = immich_client or ImmichClient(settings)
    verifier = OIDCJWTVerifier(settings, oidc_client)
    account_verifier = (
        OIDCJWTVerifier(
            settings,
            account_oidc_client,
            issuer=str(settings.account_oidc_issuer),
            audience=str(settings.account_oidc_client_id),
            required_scopes=[],
        )
        if settings.private_access_enabled and account_oidc is None
        else None
    )
    provider = credential_provider
    if settings.private_access_enabled and provider is None:
        assert settings.credential_encryption_key is not None
        assert settings.account_session_secret is not None
        provider = SQLiteCredentialProvider(
            settings.credential_db_path,
            CredentialCipher(settings.credential_encryption_key.get_secret_value()),
            settings.account_session_secret.get_secret_value(),
            settings.identity_namespace,
        )
    browser_oidc = account_oidc or (
        AccountOIDC(settings, account_verifier)
        if provider is not None and account_verifier is not None
        else None
    )
    mcp = create_mcp_server(settings, client, verifier, provider)
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[value.strip() for value in settings.allowed_hosts.split(",") if value.strip()],
        allowed_origins=[value.strip() for value in settings.allowed_origins.split(",") if value.strip()],
    )
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=security,
        host="0.0.0.0",
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            if provider is not None:
                await provider.initialize()
            async with mcp.session_manager.run():
                yield
        finally:
            if account_verifier is not None:
                await account_verifier.aclose()
            await verifier.aclose()
            await client.aclose()

    app = FastAPI(title="Immich MCP", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.immich = client
    app.state.oidc_verifier = verifier
    app.state.account_oidc_verifier = account_verifier
    app.state.mcp = mcp
    app.state.credentials = provider
    app.state.account_oidc = browser_oidc

    if provider is not None and browser_oidc is not None:
        app.include_router(account_router(settings, provider, client, browser_oidc))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        try:
            await verifier.warm()
            if account_verifier is not None:
                await account_verifier.warm()
            await client.ping()
            if provider is not None and not await provider.ready():
                raise RuntimeError("credential storage is unavailable")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Required upstream is unavailable") from exc
        return {"status": "ready"}

    @app.get("/public/shared-albums/{share_key}")
    async def shared_album_metadata(share_key: str) -> dict:
        try:
            key = validate_share_key(share_key)
            link = await client.get_shared_link(key)
            if link.type.upper() != "ALBUM" or link.album is None:
                raise HTTPException(status_code=400, detail="Share is not an album")
            buckets = await client.get_timeline_buckets(key, link.album.id)
            return {
                "sharedLink": link.model_dump(by_alias=True, exclude={"assets"}),
                "assetCount": sum(bucket.count for bucket in buckets),
            }
        except ImmichError as exc:
            raise _public_http_error(exc) from exc

    @app.get("/public/shared-albums/{share_key}/assets")
    async def shared_album_assets(share_key: str) -> list[dict]:
        try:
            key = validate_share_key(share_key)
            link = await client.get_shared_link(key)
            if link.type.upper() != "ALBUM" or link.album is None:
                raise HTTPException(status_code=400, detail="Share is not an album")
            return await client.list_shared_album_assets(key, link.album.id)
        except ImmichError as exc:
            raise _public_http_error(exc) from exc

    @app.get("/simple-share/{share_key}", response_class=HTMLResponse)
    async def simple_share(share_key: str) -> HTMLResponse:
        try:
            key = validate_share_key(share_key)
            link = await client.get_shared_link(key)
            if link.type.upper() != "ALBUM" or link.album is None:
                raise HTTPException(status_code=400, detail="Share is not an album")
            assets = await client.list_shared_album_assets(key, link.album.id)
        except ImmichError as exc:
            raise _public_http_error(exc) from exc
        title = html.escape(link.album.album_name or "Shared album")
        key_path = quote(key, safe="")
        figures = []
        for asset in assets:
            if asset.get("isImage") is False or not asset.get("id"):
                continue
            asset_id = quote(str(asset["id"]), safe="")
            alt = html.escape(str(asset.get("fileCreatedAt") or "Shared photo"))
            figures.append(
                f'<figure><img loading="lazy" src="/simple-share/{key_path}/assets/{asset_id}" '
                f'alt="{alt}"><figcaption>{alt}</figcaption></figure>'
            )
        document = (
            "<!doctype html><html><head><meta charset=utf-8>"
            f"<meta name=referrer content=no-referrer><title>{title}</title>"
            "<style>body{font:16px system-ui;margin:2rem}main{display:grid;gap:1rem;"
            "grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}figure{margin:0}"
            "img{width:100%;height:auto;display:block}figcaption{padding:.35rem 0;color:#555}</style>"
            f"</head><body><h1>{title}</h1><main>{''.join(figures)}</main></body></html>"
        )
        return HTMLResponse(
            document,
            headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.get("/simple-share/{share_key}/assets/{asset_id}")
    async def simple_share_image(share_key: str, asset_id: str) -> Response:
        try:
            key = validate_share_key(share_key)
            # Immich itself verifies that this asset is visible under this exact share credential.
            image = await client.get_shared_asset_thumbnail(key, asset_id)
        except ImmichError as exc:
            raise _public_http_error(exc) from exc
        return Response(
            content=image.data,
            media_type=image.mime_type,
            headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
        )

    # Route ordering matters: the MCP Starlette app is the final catch-all mount.
    app.mount("/", mcp_app)
    return app


def _public_http_error(exc: ImmichError) -> HTTPException:
    name = type(exc).__name__
    if name in {"InvalidShareLink", "ExpiredShareLink"}:
        return HTTPException(status_code=401, detail=str(exc))
    if name == "ImmichForbidden":
        return HTTPException(status_code=403, detail=str(exc))
    if name == "ImmichNotFound":
        return HTTPException(status_code=404, detail=str(exc))
    if name == "ImmichRateLimited":
        return HTTPException(status_code=429, detail=str(exc))
    if name in {"ImmichUnavailable", "ImmichTimeout"}:
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))
