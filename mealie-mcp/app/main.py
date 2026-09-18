from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from app.api.connections import router as connections_router
from app.api.health import router as health_router
from app.auth.authentik import AuthentikIdentityProvider
from app.config import Settings, get_settings
from app.db.repository import ConnectionRepository
from app.db.session import Database
from app.mcp.server import create_mcp_server
from app.mealie.client import MealieClient
from app.mealie.openapi import OpenAPILoader
from app.observability.logging import configure_logging, request_context_middleware
from app.security.destinations import DestinationPolicy
from app.security.secrets import LocalEncryptedSecretProvider
from app.services.connections import ConnectionExecutor, ConnectionService
from app.services.mealplans import MealPlanService
from app.services.recipes import RecipeService
from app.services.shopping import ShoppingService


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    identity_client: httpx.AsyncClient | None = None,
    mealie_http_client: httpx.AsyncClient | None = None,
    destination_policy: DestinationPolicy | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    db = database or Database(settings.database_url)
    identity = AuthentikIdentityProvider(settings, identity_client)
    destinations = destination_policy or DestinationPolicy(settings)
    secrets = LocalEncryptedSecretProvider(settings.credential_encryption_key)
    mealie = MealieClient(settings, destinations, mealie_http_client)
    repository = ConnectionRepository(db.sessions)
    openapi = OpenAPILoader(mealie)
    connection_service = ConnectionService(repository, secrets, destinations, mealie, openapi)
    executor = ConnectionExecutor(repository, secrets, mealie)
    recipes = RecipeService(executor)
    mealplans = MealPlanService(executor)
    shopping = ShoppingService(executor)
    mcp = create_mcp_server(settings, identity, recipes, mealplans, shopping)
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.mcp_allowed_hosts,
        allowed_origins=settings.mcp_allowed_origins,
    )
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=transport_security,
        host="0.0.0.0",
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            await identity.aclose()
            await mealie.aclose()
            await db.aclose()

    app = FastAPI(
        title="Mealie MCP Service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.middleware("http")(request_context_middleware)
    app.state.settings = settings
    app.state.database = db
    app.state.identity = identity
    app.state.mealie = mealie
    app.state.connections = repository
    app.state.connection_service = connection_service
    app.state.mcp = mcp
    app.include_router(health_router)
    app.include_router(connections_router)
    # The MCP SDK app publishes protected-resource metadata and is the final catch-all mount.
    app.mount("/", mcp_app)
    return app
