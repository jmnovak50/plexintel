from __future__ import annotations

import asyncio

import httpx
import pytest
from conftest import principal, public_resolver
from pydantic import SecretStr

from app.db.models import ConnectionStatus, MealieConnection
from app.db.repository import ConnectionRepository
from app.mealie.client import MealieClient
from app.mealie.resolver import CapabilityMap, OperationDescriptor
from app.security.destinations import DestinationPolicy
from app.security.secrets import LocalEncryptedSecretProvider
from app.services.connections import ConnectionExecutor
from app.services.recipes import RecipeService


@pytest.mark.asyncio
async def test_concurrent_users_cannot_cross_credentials_or_destinations(settings, database):
    seen: list[tuple[str, str]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        authorization = request.headers.get("authorization", "")
        host = request.url.host
        seen.append((host, authorization))
        expected = {
            "mealie-a.example": "Bearer token-a-secret",
            "mealie-b.example": "Bearer token-b-secret",
        }
        assert authorization == expected[host]
        return httpx.Response(200, json={"items": [{"owner": host}]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    policy = DestinationPolicy(settings, public_resolver)
    client = MealieClient(settings, policy, http)
    secrets = LocalEncryptedSecretProvider(settings.credential_encryption_key)
    repository = ConnectionRepository(database.sessions)
    descriptor = OperationDescriptor(
        capability="recipe.search",
        method="GET",
        path="/api/recipes",
        query_parameters=frozenset({"search", "page", "perPage"}),
    )
    capabilities = CapabilityMap(operations={"recipe.search": descriptor}).model_dump(mode="json")
    user_a, user_b = principal("a"), principal("b")
    for user, host, token in [
        (user_a, "mealie-a.example", "token-a-secret"),
        (user_b, "mealie-b.example", "token-b-secret"),
    ]:
        await repository.add(
            MealieConnection(
                tenant_id=user.tenant_id,
                user_id=user.user_id,
                name="Default",
                base_url=f"https://{host}",
                encrypted_api_token=secrets.encrypt(SecretStr(token)),
                is_default=True,
                capabilities=capabilities,
                status=ConnectionStatus.active,
            )
        )
    service = RecipeService(ConnectionExecutor(repository, secrets, client))

    async def repeat(user, expected):
        for index in range(25):
            result = await service.search(user, search=f"query-{index}")
            assert result["items"][0]["owner"] == expected

    await asyncio.gather(repeat(user_a, "mealie-a.example"), repeat(user_b, "mealie-b.example"))
    assert len(seen) == 50
    assert all(
        (host == "mealie-a.example" and auth == "Bearer token-a-secret")
        or (host == "mealie-b.example" and auth == "Bearer token-b-secret")
        for host, auth in seen
    )
    await http.aclose()


@pytest.mark.asyncio
async def test_connection_id_does_not_bypass_owner_predicates(settings, database):
    repository = ConnectionRepository(database.sessions)
    secrets = LocalEncryptedSecretProvider(settings.credential_encryption_key)
    owner = principal("owner", "tenant-a")
    intruder_user = principal("intruder", "tenant-a")
    intruder_tenant = principal("owner", "tenant-b")
    value = MealieConnection(
        tenant_id=owner.tenant_id,
        user_id=owner.user_id,
        name="Default",
        base_url="https://mealie.example",
        encrypted_api_token=secrets.encrypt(SecretStr("secret")),
        is_default=True,
        capabilities={},
        status=ConnectionStatus.active,
    )
    await repository.add(value)
    assert await repository.get_for(owner, value.id) is not None
    assert await repository.get_for(intruder_user, value.id) is None
    assert await repository.get_for(intruder_tenant, value.id) is None
    assert not await repository.delete_for(intruder_user, value.id)
    assert not await repository.delete_for(intruder_tenant, value.id)
