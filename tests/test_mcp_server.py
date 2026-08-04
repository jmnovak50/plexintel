from __future__ import annotations

import anyio
import httpx
import unittest
from io import BytesIO
from datetime import datetime
from unittest.mock import patch

from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from PIL import Image
from starlette.datastructures import Headers

from api.services import mcp_server
from api.services.mcp_auth import MCPAuthContext
from api.services.agent_tool_service import (
    AgentRecommendation,
    AgentRecommendationScore,
    AgentRecommendationsResponse,
    AgentUser,
    AgentUsersResponse,
    LibraryItem,
    LibrarySearchResponse,
    RecentLibraryAdditionsResponse,
    RecentLibraryItem,
    WatchHistoryItem,
    WatchHistoryResponse,
)


INITIALIZE_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": "1",
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "plexintel-tests", "version": "1.0.0"},
    },
}


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (12, 18), color=(32, 64, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


class MCPServerTests(unittest.TestCase):
    def setUp(self):
        self.http_app = FastAPI()
        self.http_app.mount("/mcp", mcp_server.mcp_mount_app)

    async def _request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.http_app),
            base_url="http://testserver",
            follow_redirects=True,
        ) as client:
            return await client.request(method, path, **kwargs)

    def _enabled_settings(self, *, origins=(), auth_mode="static"):
        return mcp_server.MCPRuntimeSettings(
            enabled=True,
            auth_mode=auth_mode,
            api_key="test-mcp-token",
            allowed_origins=tuple(origins),
            oauth_issuer_url="https://authentik.example/application/o/openwebui",
            oauth_audience=None,
            oauth_email_claim="email",
            trusted_user_email_header="X-OpenWebUI-User-Email",
        )

    async def _exercise_mcp_protocol(self):
        async with mcp_server.mcp_runtime.lifespan():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.http_app),
                base_url="http://testserver",
                headers={"authorization": "Bearer test-mcp-token"},
                follow_redirects=True,
            ) as client:
                async with streamable_http_client(
                    "http://testserver/mcp/",
                    http_client=client,
                ) as (read, write, _get_session_id):
                    async with ClientSession(read, write) as session:
                        initialize_result = await session.initialize()
                        tools_result = await session.list_tools()
                        users_result = await session.call_tool("list_users", {"username": "jm"})
                        recommendations_result = await session.call_tool(
                            "get_recommendations",
                            {"user": "jmnovak", "view": "shows", "media_type": "episode", "limit": 5},
                        )
                        score_result = await session.call_tool(
                            "get_recommendation_score",
                            {"user": "jmnovak", "rating_key": 37641},
                        )
                        search_result = await session.call_tool("search_library", {"q": "blade"})
                        item_result = await session.call_tool("get_library_item", {"rating_key": 42})
                        poster_result = await session.call_tool("get_poster_image", {"rating_key": 42})
                        gallery_result = await session.call_tool(
                            "get_poster_gallery",
                            {
                                "items": [
                                    {
                                        "rating_key": 42,
                                        "title": "Blade Runner 2049",
                                        "media_type": "movie",
                                    },
                                    {
                                        "rating_key": 88,
                                        "title": "Black Bag",
                                        "media_type": "movie",
                                    },
                                ]
                            },
                        )
                        recent_result = await session.call_tool(
                            "get_recent_library_additions",
                            {"media_type": "movie", "days": 7, "limit": 5},
                        )
                        history_result = await session.call_tool(
                            "get_watch_history",
                            {"user": "jmnovak", "limit": 5},
                        )

        return {
            "initialize": initialize_result,
            "tools": tools_result,
            "users": users_result,
            "recommendations": recommendations_result,
            "score": score_result,
            "search": search_result,
            "item": item_result,
            "poster": poster_result,
            "gallery": gallery_result,
            "recent": recent_result,
            "history": history_result,
        }

    def test_mcp_protocol_lists_tools_and_calls_each_read_only_tool(self):
        users_payload = AgentUsersResponse(
            count=1,
            items=[AgentUser(username="jmnovak", friendly_name="Jason")],
        )
        recommendations_payload = AgentRecommendationsResponse(
            user="jmnovak",
            count=1,
            items=[
                AgentRecommendation(
                    rating_key=101,
                    title="Arrival",
                    media_type="movie",
                    score=0.93,
                )
            ],
        )
        score_payload = AgentRecommendationScore(
            user="jmnovak",
            rating_key=37641,
            title="Disclosure Day",
            media_type="movie",
            score=0.8734,
        )
        search_payload = LibrarySearchResponse(
            query="blade",
            count=1,
            items=[
                LibraryItem(
                    rating_key=42,
                    title="Blade Runner 2049",
                    media_type="movie",
                )
            ],
        )
        item_payload = LibraryItem(
            rating_key=42,
            title="Blade Runner 2049",
            media_type="movie",
            summary="Replicants.",
        )
        recent_payload = RecentLibraryAdditionsResponse(
            media_type="movie",
            days=7,
            count=1,
            items=[
                RecentLibraryItem(
                    rating_key=88,
                    title="Black Bag",
                    media_type="movie",
                    year=2025,
                    duration_formatted="00:00:00",
                )
            ],
        )
        history_payload = WatchHistoryResponse(
            user="jmnovak",
            engaged_only=False,
            count=1,
            results=[
                WatchHistoryItem(
                    watch_id=1,
                    username="jmnovak",
                    friendly_name="Jason",
                    rating_key=777,
                    watched_at=datetime(2026, 3, 2, 8, 30, 0),
                    played_duration=3500,
                    media_duration=4000,
                    percent_complete=0.875,
                    engaged=True,
                    media_type="movie",
                    show_title=None,
                    title="Heat",
                    summary="Crime drama",
                    season_number=None,
                    episode_number=None,
                    rating=8.4,
                    year=1995,
                    genres="Crime",
                    actors="Al Pacino",
                    directors="Michael Mann",
                )
            ],
        )

        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(),
        ):
            with patch.object(mcp_server, "list_agent_users", return_value=users_payload):
                with patch.object(
                    mcp_server,
                    "get_agent_recommendations",
                    return_value=recommendations_payload,
                ) as mock_recommendations:
                    with patch.object(
                        mcp_server,
                        "get_agent_recommendation_score",
                        return_value=score_payload,
                    ) as mock_score:
                        with patch.object(mcp_server, "search_agent_library", return_value=search_payload):
                            with patch.object(mcp_server, "get_agent_library_item", return_value=item_payload):
                                with patch.object(
                                    mcp_server,
                                    "get_recent_library_additions",
                                    return_value=recent_payload,
                                ):
                                    with patch.object(
                                        mcp_server,
                                        "get_agent_watch_history",
                                        return_value=history_payload,
                                    ):
                                        with patch.object(
                                            mcp_server,
                                            "build_public_poster_url",
                                            side_effect=lambda rating_key, width=None, thumb=False: (
                                                f"https://plexintel.example.com/api/posters/{rating_key}?w={width}"
                                            ),
                                        ):
                                            with patch.object(
                                                mcp_server,
                                                "fetch_poster_image_for_rating_key",
                                                return_value={
                                                    "content": _png_bytes(),
                                                    "content_type": "image/png",
                                                },
                                            ):
                                                results = anyio.run(self._exercise_mcp_protocol)

        self.assertTrue(results["initialize"].serverInfo.name)
        tool_names = {tool.name for tool in results["tools"].tools}
        self.assertEqual(
            tool_names,
            {
                "list_users",
                "get_recommendations",
                "get_recommendation_score",
                "search_library",
                "get_library_item",
                "get_poster_image",
                "get_poster_gallery",
                "get_recent_library_additions",
                "get_watch_history",
            },
        )
        self.assertEqual(results["users"].structuredContent["items"][0]["username"], "jmnovak")
        self.assertEqual(results["recommendations"].structuredContent["items"][0]["title"], "Arrival")
        mock_recommendations.assert_called_once_with(
            user="jmnovak",
            view="shows",
            media_type="episode",
            limit=5,
            min_score=None,
            max_score=None,
        )
        self.assertEqual(results["score"].structuredContent["rating_key"], 37641)
        self.assertEqual(results["score"].structuredContent["score"], 0.8734)
        mock_score.assert_called_once_with(user="jmnovak", rating_key=37641)
        self.assertEqual(results["search"].structuredContent["items"][0]["rating_key"], 42)
        self.assertEqual(results["item"].structuredContent["summary"], "Replicants.")
        self.assertIsNone(results["poster"].structuredContent)
        self.assertEqual(results["poster"].content[0].type, "text")
        self.assertEqual(
            results["poster"].content[0].text,
            "### Blade Runner 2049\n"
            "![Poster for Blade Runner 2049](https://plexintel.example.com/api/posters/42?w=240)",
        )
        self.assertIsNone(results["gallery"].structuredContent)
        self.assertIn(
            "### Blade Runner 2049\n![Poster for Blade Runner 2049](https://plexintel.example.com/api/posters/42?w=180)",
            results["gallery"].content[0].text,
        )
        self.assertIn("### Black Bag", results["gallery"].content[0].text)
        self.assertIn("https://plexintel.example.com/api/posters/88?w=180", results["gallery"].content[0].text)
        self.assertEqual(results["recent"].structuredContent["days"], 7)
        self.assertEqual(results["recent"].structuredContent["items"][0]["title"], "Black Bag")
        self.assertEqual(results["recent"].structuredContent["items"][0]["duration_formatted"], "00:00:00")
        self.assertEqual(results["history"].structuredContent["results"][0]["title"], "Heat")

    def test_build_poster_markup_payload_uses_public_agent_url(self):
        with patch.object(
            mcp_server,
            "build_public_poster_url",
            return_value="https://plexintel.example.com/api/posters/42?w=240",
        ):
            payload = mcp_server.build_poster_markup_payload(42, title="From", width=240)

        self.assertEqual(payload["title"], "From")
        self.assertEqual(payload["rating_key"], 42)
        self.assertEqual(payload["poster_url"], "https://plexintel.example.com/api/posters/42?w=240")
        self.assertEqual(payload["image_url"], payload["poster_url"])
        self.assertIn("![Poster for From]", payload["markdown"])
        self.assertIn('<img src="https://plexintel.example.com/api/posters/42?w=240"', payload["html"])

    def test_build_poster_markup_payload_unescapes_html_entities_in_title(self):
        with patch.object(
            mcp_server,
            "build_public_poster_url",
            return_value="https://plexintel.example.com/api/posters/42?w=240",
        ):
            payload = mcp_server.build_poster_markup_payload(42, title="Tom &amp; Jerry", width=240)

        self.assertEqual(payload["title"], "Tom & Jerry")
        self.assertEqual(
            payload["markdown"],
            "![Poster for Tom & Jerry](https://plexintel.example.com/api/posters/42?w=240)",
        )
        self.assertIn('alt="Poster for Tom &amp; Jerry"', payload["html"])

    def test_build_poster_gallery_result_accepts_items_and_rating_keys(self):
        with patch.object(
            mcp_server,
            "build_public_poster_url",
            side_effect=lambda rating_key, width=None, thumb=False: (
                f"https://plexintel.example.com/api/posters/{rating_key}?w={width}"
            ),
        ):
            result = mcp_server.build_poster_gallery_result(
                rating_keys=[88],
                items=[{"rating_key": 42, "title": "From"}],
            )

        self.assertIsNone(result.structuredContent)
        self.assertIn(
            "### From\n![Poster for From](https://plexintel.example.com/api/posters/42?w=180)",
            result.content[0].text,
        )
        self.assertIn(
            "### rating_key 88\n![Poster for rating_key 88](https://plexintel.example.com/api/posters/88?w=180)",
            result.content[0].text,
        )

    def test_build_poster_image_result_returns_not_found_when_poster_is_missing(self):
        with patch.object(
            mcp_server,
            "get_agent_library_item",
            return_value=LibraryItem(
                rating_key=42,
                title="Blade Runner 2049",
                media_type="movie",
            ),
        ):
            with patch.object(
                mcp_server,
                "fetch_poster_image_for_rating_key",
                return_value=None,
            ):
                result = mcp_server.build_poster_image_result(42)

        self.assertFalse(result.isError)
        self.assertFalse(result.structuredContent["found"])
        self.assertEqual(result.structuredContent["title"], "Blade Runner 2049")
        self.assertEqual(result.content[0].type, "text")
        self.assertIn("Poster not found", result.content[0].text)

    def test_build_poster_image_result_returns_tool_error_for_fetch_failure(self):
        with patch.object(
            mcp_server,
            "get_agent_library_item",
            return_value=LibraryItem(
                rating_key=42,
                title="Blade Runner 2049",
                media_type="movie",
            ),
        ):
            with patch.object(
                mcp_server,
                "fetch_poster_image_for_rating_key",
                side_effect=RuntimeError("Poster proxy is not configured."),
            ):
                result = mcp_server.build_poster_image_result(42)

        self.assertTrue(result.isError)
        self.assertFalse(result.structuredContent["found"])
        self.assertEqual(result.structuredContent["error"], "Poster proxy is not configured.")
        self.assertIn("Unable to fetch poster", result.content[0].text)

    def test_mcp_returns_404_when_disabled(self):
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=mcp_server.MCPRuntimeSettings(
                enabled=False,
                auth_mode="static",
                api_key="test-mcp-token",
                allowed_origins=(),
                oauth_issuer_url=None,
                oauth_audience=None,
                oauth_email_claim="email",
                trusted_user_email_header="X-OpenWebUI-User-Email",
            ),
        ):
            response = anyio.run(lambda: self._request("POST", "/mcp/", json=INITIALIZE_PAYLOAD))

        self.assertEqual(response.status_code, 404)

    def test_mcp_rejects_missing_or_invalid_bearer_token(self):
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(),
        ):
            missing_response = anyio.run(lambda: self._request("POST", "/mcp/", json=INITIALIZE_PAYLOAD))
            invalid_response = anyio.run(
                lambda: self._request(
                    "POST",
                    "/mcp/",
                    json=INITIALIZE_PAYLOAD,
                    headers={"Authorization": "Bearer wrong-token"},
                )
            )

        self.assertEqual(missing_response.status_code, 403)
        self.assertEqual(invalid_response.status_code, 403)

    def test_mcp_rejects_disallowed_origin(self):
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(origins=("https://allowed.example",)),
        ):
            response = anyio.run(
                lambda: self._request(
                    "POST",
                    "/mcp/",
                    json=INITIALIZE_PAYLOAD,
                    headers={
                        "Authorization": "Bearer test-mcp-token",
                        "Origin": "https://blocked.example",
                    },
                )
            )

        self.assertEqual(response.status_code, 403)

    def test_resolve_mcp_user_auto_scopes_jwt_identity(self):
        token = mcp_server.mcp_auth_context.set(
            MCPAuthContext(
                auth_method="jwt",
                email="jason@sheffieldave.com",
                plex_username="jmnovak",
                user_id=7,
                is_admin=False,
            )
        )
        try:
            resolved = mcp_server._resolve_mcp_user(None)
        finally:
            mcp_server.mcp_auth_context.reset(token)

        self.assertEqual(resolved, "jmnovak")

    def test_resolve_mcp_user_auto_scopes_trusted_header_identity(self):
        token = mcp_server.mcp_auth_context.set(
            MCPAuthContext(
                auth_method="static",
                email="jason@sheffieldave.com",
                plex_username="jmnovak",
            )
        )
        try:
            resolved = mcp_server._resolve_mcp_user(None)
        finally:
            mcp_server.mcp_auth_context.reset(token)

        self.assertEqual(resolved, "jmnovak")

    def test_resolve_mcp_user_blocks_impersonation_for_non_admin(self):
        token = mcp_server.mcp_auth_context.set(
            MCPAuthContext(
                auth_method="jwt",
                email="jason@sheffieldave.com",
                plex_username="jmnovak",
                is_admin=False,
            )
        )
        try:
            with self.assertRaises(mcp_server.MCPUserAccessError):
                mcp_server._resolve_mcp_user("otheruser")
        finally:
            mcp_server.mcp_auth_context.reset(token)

    def test_resolve_mcp_user_allows_admin_impersonation(self):
        token = mcp_server.mcp_auth_context.set(
            MCPAuthContext(
                auth_method="jwt",
                email="admin@example.com",
                plex_username="admin",
                is_admin=True,
            )
        )
        try:
            resolved = mcp_server._resolve_mcp_user("otheruser")
        finally:
            mcp_server.mcp_auth_context.reset(token)

        self.assertEqual(resolved, "otheruser")

    def test_resolve_mcp_user_requires_explicit_user_in_static_mode(self):
        token = mcp_server.mcp_auth_context.set(MCPAuthContext(auth_method="static"))
        try:
            with self.assertRaises(mcp_server.MCPUserAccessError):
                mcp_server._resolve_mcp_user(None)
        finally:
            mcp_server.mcp_auth_context.reset(token)

    def test_mcp_jwt_mode_rejects_missing_token(self):
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt"),
        ):
            response = anyio.run(lambda: self._request("POST", "/mcp/", json=INITIALIZE_PAYLOAD))

        self.assertEqual(response.status_code, 401)

    def test_mcp_jwt_mode_accepts_valid_token(self):
        jwt_context = MCPAuthContext(
            auth_method="jwt",
            email="jason@sheffieldave.com",
            plex_username="jmnovak",
        )
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings(auth_mode="jwt")
        headers = Headers({"authorization": "Bearer valid-jwt"})

        with patch.object(mcp_server, "authenticate_bearer_token", return_value=jwt_context):
            result = app._authenticate_request(headers=headers, settings=settings)

        self.assertIsNone(result.response)
        self.assertEqual(result.context, jwt_context)

    def test_mcp_jwt_or_static_falls_back_to_static_key(self):
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings(auth_mode="jwt_or_static")
        headers = Headers({"authorization": "Bearer test-mcp-token"})

        with patch.object(mcp_server, "authenticate_bearer_token", return_value=None):
            result = app._authenticate_request(headers=headers, settings=settings)

        self.assertIsNone(result.response)
        self.assertEqual(result.context.auth_method, "static")

    def test_mcp_jwt_or_static_does_not_fall_back_for_jwt_shaped_token(self):
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings(auth_mode="jwt_or_static")
        headers = Headers({"authorization": "Bearer header.payload.signature"})

        with patch.object(mcp_server, "authenticate_bearer_token", return_value=None):
            result = app._authenticate_request(headers=headers, settings=settings)

        self.assertIsNotNone(result.response)
        self.assertEqual(result.response.status_code, 403)

    def test_enrich_auth_context_maps_trusted_email_header(self):
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings()
        headers = Headers({"x-openwebui-user-email": "jason@sheffieldave.com"})
        initial = app._AuthResult(
            response=None,
            context=MCPAuthContext(auth_method="static"),
        )

        with patch.object(
            mcp_server,
            "resolve_context_from_email",
            return_value=MCPAuthContext(
                auth_method="static",
                email="jason@sheffieldave.com",
                plex_username="jmnovak",
            ),
        ) as mock_resolve:
            result = app._enrich_auth_context(headers=headers, settings=settings, auth_result=initial)

        mock_resolve.assert_called_once_with("jason@sheffieldave.com", "static")
        self.assertEqual(result.context.plex_username, "jmnovak")


if __name__ == "__main__":
    unittest.main()
