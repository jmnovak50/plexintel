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

from api.services import mcp_server
from api.services.agent_tool_service import (
    AgentRecommendation,
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

    def _enabled_settings(self, *, origins=()):
        return mcp_server.MCPRuntimeSettings(
            enabled=True,
            api_key="test-mcp-token",
            allowed_origins=tuple(origins),
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
                            {"user": "jmnovak", "limit": 5},
                        )
                        search_result = await session.call_tool("search_library", {"q": "blade"})
                        item_result = await session.call_tool("get_library_item", {"rating_key": 42})
                        poster_result = await session.call_tool("get_poster_image", {"rating_key": 42})
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
            "search": search_result,
            "item": item_result,
            "poster": poster_result,
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
                ):
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
                "search_library",
                "get_library_item",
                "get_poster_image",
                "get_recent_library_additions",
                "get_watch_history",
            },
        )
        self.assertEqual(results["users"].structuredContent["items"][0]["username"], "jmnovak")
        self.assertEqual(results["recommendations"].structuredContent["items"][0]["title"], "Arrival")
        self.assertEqual(results["search"].structuredContent["items"][0]["rating_key"], 42)
        self.assertEqual(results["item"].structuredContent["summary"], "Replicants.")
        self.assertEqual(results["poster"].structuredContent["rating_key"], 42)
        self.assertTrue(results["poster"].structuredContent["found"])
        self.assertEqual(results["poster"].content[1].type, "image")
        self.assertEqual(results["poster"].content[1].mimeType, "image/jpeg")
        self.assertTrue(results["poster"].content[1].data)
        self.assertEqual(results["recent"].structuredContent["days"], 7)
        self.assertEqual(results["recent"].structuredContent["items"][0]["title"], "Black Bag")
        self.assertEqual(results["history"].structuredContent["results"][0]["title"], "Heat")

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
                api_key="test-mcp-token",
                allowed_origins=(),
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


if __name__ == "__main__":
    unittest.main()
