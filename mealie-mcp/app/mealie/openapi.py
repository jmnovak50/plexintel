from __future__ import annotations

import hashlib
import json
from typing import Any

from app.mealie.client import MealieClient
from app.mealie.errors import MealieInvalidResponse
from app.mealie.resolver import CapabilityMap, OperationResolver


class LoadedSchema:
    def __init__(self, document: dict[str, Any], capabilities: CapabilityMap) -> None:
        self.document = document
        self.capabilities = capabilities
        normalized = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.schema_hash = hashlib.sha256(normalized.encode()).hexdigest()


class OpenAPILoader:
    def __init__(self, client: MealieClient, resolver: OperationResolver | None = None) -> None:
        self.client = client
        self.resolver = resolver or OperationResolver()

    async def load(self, base_url: str, token: str) -> LoadedSchema:
        value = await self.client.request_json(
            base_url,
            token,
            "GET",
            "/openapi.json",
            operation="openapi.load",
            schema_response=True,
        )
        if not isinstance(value, dict):
            raise MealieInvalidResponse("Mealie OpenAPI response is not an object")
        version = value.get("openapi")
        if not isinstance(version, str) or not version.startswith("3."):
            raise MealieInvalidResponse("Mealie returned an unsupported OpenAPI document")
        return LoadedSchema(value, self.resolver.build(value))
