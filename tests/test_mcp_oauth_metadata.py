from __future__ import annotations

import anyio
import httpx
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from api.routes import mcp_oauth_metadata
from api.services.mcp_auth import MCPOAuthSettings
from api.services.mcp_server import MCPPathCompatibilityMiddleware


class MCPProtectedResourceMetadataTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(MCPPathCompatibilityMiddleware)
        self.app.include_router(mcp_oauth_metadata.router)

        @self.app.get("/{path:path}")
        async def spa_fallback(path: str):
            return HTMLResponse("<html>SPA index</html>")

    async def _get(self, path: str):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="https://plexintel.example",
        ) as client:
            return await client.get(path)

    def test_both_metadata_routes_return_exact_oauth_document_not_spa(self):
        settings = MCPOAuthSettings(
            issuer_url="https://auth.kabolly.com/application/o/plexintel-chatgpt/",
            audience="https://plexintel.kabolly.com/mcp",
            email_claim="email",
            resource_url="https://plexintel.kabolly.com/mcp",
            required_scopes=("plexintel.read",),
        )
        with patch.object(mcp_oauth_metadata, "get_mcp_oauth_settings", return_value=settings):
            responses = [
                anyio.run(lambda: self._get("/.well-known/oauth-protected-resource")),
                anyio.run(lambda: self._get("/.well-known/oauth-protected-resource/mcp")),
            ]
        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "application/json")
            self.assertEqual(
                response.json(),
                {
                    "resource": "https://plexintel.kabolly.com/mcp",
                    "authorization_servers": [
                        "https://auth.kabolly.com/application/o/plexintel-chatgpt/"
                    ],
                    "scopes_supported": ["plexintel.read"],
                },
            )
            self.assertNotIn("SPA index", response.text)

    def test_incomplete_metadata_configuration_returns_json_503(self):
        settings = MCPOAuthSettings(None, None, "email", None, ())
        with patch.object(mcp_oauth_metadata, "get_mcp_oauth_settings", return_value=settings):
            response = anyio.run(lambda: self._get("/.well-known/oauth-protected-resource"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertIn("not configured", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
