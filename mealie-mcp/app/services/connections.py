from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.auth.principal import Principal
from app.db.models import ConnectionStatus, MealieConnection, SchemaSource
from app.db.repository import ConnectionRepository
from app.mealie.capabilities import CAPABILITY_SPECS
from app.mealie.client import MealieClient
from app.mealie.errors import MealieError, MealieInvalidResponse, MealieNotFound
from app.mealie.openapi import OpenAPILoader
from app.mealie.resolver import CapabilityMap
from app.security.destinations import DestinationPolicy
from app.security.secrets import SecretProvider


class ConnectionCreate(BaseModel):
    name: str = Field(default="Default", min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2048)
    api_token: SecretStr
    is_default: bool = True


class CredentialUpdate(BaseModel):
    api_token: SecretStr


class ConnectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    is_default: bool
    mealie_user_id: str | None
    mealie_version: str | None
    openapi_schema_hash: str | None
    status: ConnectionStatus
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ValidationResult(BaseModel):
    connection: ConnectionView
    capabilities: list[str]
    added_capabilities: list[str] = Field(default_factory=list)
    removed_capabilities: list[str] = Field(default_factory=list)
    schema_changed: bool = False


class ConnectionService:
    def __init__(
        self,
        repository: ConnectionRepository,
        secrets: SecretProvider,
        destinations: DestinationPolicy,
        client: MealieClient,
        openapi: OpenAPILoader,
    ) -> None:
        self.repository = repository
        self.secrets = secrets
        self.destinations = destinations
        self.client = client
        self.openapi = openapi

    async def create(self, principal: Principal, request: ConnectionCreate) -> ValidationResult:
        destination = await self.destinations.validate(request.base_url)
        token = request.api_token.get_secret_value()
        metadata = await self._validate(destination.base_url, token)
        connection = MealieConnection(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            name=request.name,
            base_url=destination.base_url,
            encrypted_api_token=self.secrets.encrypt(request.api_token),
            is_default=request.is_default,
            mealie_user_id=metadata["mealie_user_id"],
            mealie_version=metadata["mealie_version"],
            openapi_schema_hash=metadata["schema_hash"],
            capabilities=metadata["capabilities"].model_dump(mode="json"),
            schema_source=SchemaSource.live,
            status=_status_for(metadata["capabilities"]),
            last_validated_at=datetime.now(UTC),
        )
        await self.repository.add(connection)
        return ValidationResult(
            connection=ConnectionView.model_validate(connection),
            capabilities=sorted(metadata["capabilities"].names),
            added_capabilities=sorted(metadata["capabilities"].names),
        )

    async def list(self, principal: Principal) -> list[ConnectionView]:
        return [ConnectionView.model_validate(value) for value in await self.repository.list_for(principal)]

    async def get(self, principal: Principal, connection_id: uuid.UUID) -> MealieConnection:
        value = await self.repository.get_for(principal, connection_id)
        if value is None:
            raise MealieNotFound("Mealie connection not found")
        return value

    async def validate(self, principal: Principal, connection_id: uuid.UUID) -> ValidationResult:
        connection = await self.get(principal, connection_id)
        with self.secrets.reveal(connection.encrypted_api_token) as token:
            metadata = await self._validate(connection.base_url, token)
        previous = CapabilityMap.model_validate(connection.capabilities)
        current: CapabilityMap = metadata["capabilities"]
        old_hash = connection.openapi_schema_hash
        connection.mealie_user_id = metadata["mealie_user_id"]
        connection.mealie_version = metadata["mealie_version"]
        connection.openapi_schema_hash = metadata["schema_hash"]
        connection.capabilities = current.model_dump(mode="json")
        connection.schema_source = SchemaSource.live
        connection.status = _status_for(current)
        connection.last_validated_at = datetime.now(UTC)
        connection = await self.repository.save(connection)
        return ValidationResult(
            connection=ConnectionView.model_validate(connection),
            capabilities=sorted(current.names),
            added_capabilities=sorted(current.names - previous.names),
            removed_capabilities=sorted(previous.names - current.names),
            schema_changed=old_hash is not None and old_hash != metadata["schema_hash"],
        )

    async def replace_credential(
        self, principal: Principal, connection_id: uuid.UUID, request: CredentialUpdate
    ) -> ValidationResult:
        connection = await self.get(principal, connection_id)
        token = request.api_token.get_secret_value()
        metadata = await self._validate(connection.base_url, token)
        previous = CapabilityMap.model_validate(connection.capabilities)
        current: CapabilityMap = metadata["capabilities"]
        old_hash = connection.openapi_schema_hash
        connection.encrypted_api_token = self.secrets.encrypt(request.api_token)
        connection.mealie_user_id = metadata["mealie_user_id"]
        connection.mealie_version = metadata["mealie_version"]
        connection.openapi_schema_hash = metadata["schema_hash"]
        connection.capabilities = current.model_dump(mode="json")
        connection.schema_source = SchemaSource.live
        connection.status = _status_for(current)
        connection.last_validated_at = datetime.now(UTC)
        connection = await self.repository.save(connection)
        return ValidationResult(
            connection=ConnectionView.model_validate(connection),
            capabilities=sorted(current.names),
            added_capabilities=sorted(current.names - previous.names),
            removed_capabilities=sorted(previous.names - current.names),
            schema_changed=old_hash is not None and old_hash != metadata["schema_hash"],
        )

    async def delete(self, principal: Principal, connection_id: uuid.UUID) -> None:
        if not await self.repository.delete_for(principal, connection_id):
            raise MealieNotFound("Mealie connection not found")

    async def capability_names(self, principal: Principal, connection_id: uuid.UUID) -> list[str]:
        connection = await self.get(principal, connection_id)
        return sorted(CapabilityMap.model_validate(connection.capabilities).names)

    async def _validate(self, base_url: str, token: str) -> dict[str, Any]:
        loaded = await self.openapi.load(base_url, token)
        identity_operation = loaded.capabilities.require("identity.self")
        identity = await self.client.execute(base_url, token, identity_operation)
        if not isinstance(identity, dict) or not identity.get("id"):
            raise MealieInvalidResponse("Mealie user identity response is malformed")
        version: str | None = None
        try:
            about = await self.client.request_json(
                base_url, token, "GET", "/api/app/about", operation="app.about"
            )
            if isinstance(about, dict):
                raw_version = about.get("version") or about.get("versionLatest")
                if raw_version is not None:
                    version = str(raw_version)[:64]
        except MealieError:
            pass
        return {
            "mealie_user_id": str(identity["id"])[:128],
            "mealie_version": version,
            "schema_hash": loaded.schema_hash,
            "capabilities": loaded.capabilities,
        }


def _status_for(capabilities: CapabilityMap) -> ConnectionStatus:
    expected = {spec.name for spec in CAPABILITY_SPECS}
    return ConnectionStatus.active if expected.issubset(capabilities.names) else ConnectionStatus.degraded


class ConnectionExecutor:
    def __init__(
        self,
        repository: ConnectionRepository,
        secrets: SecretProvider,
        client: MealieClient,
    ) -> None:
        self.repository = repository
        self.secrets = secrets
        self.client = client

    async def call(
        self,
        principal: Principal,
        capability: str,
        *,
        path_values: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        connection = await self.repository.default_for(principal)
        if connection is None:
            raise MealieNotFound("No default Mealie connection is configured for this user")
        if connection.status not in {ConnectionStatus.active, ConnectionStatus.degraded}:
            raise MealieError("The default Mealie connection is not active")
        operation = CapabilityMap.model_validate(connection.capabilities).require(capability)
        with self.secrets.reveal(connection.encrypted_api_token) as token:
            return await self.client.execute(
                connection.base_url,
                token,
                operation,
                path_values=path_values,
                query=query,
            )
