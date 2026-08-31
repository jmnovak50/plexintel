import httpx
import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_mcp_publishes_resource_metadata_and_requires_bearer(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://mcp.example.com") as client:
        metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
        unauthorized = await client.get("/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "https://mcp.example.com/mcp"
    assert metadata.json()["scopes_supported"] == ["immich.read"]
    assert unauthorized.status_code == 401
    assert "resource_metadata=" in unauthorized.headers["www-authenticate"]
    await app.state.oidc_verifier.aclose()
    await app.state.immich.aclose()
