from __future__ import annotations

import anyio
import base64
import httpx
import json
import logging
import time
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

RECENT_ADDITIONS_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tools/call",
    "params": {
        "name": "get_recent_library_additions",
        "arguments": {"media_type": "movie", "days": 7, "limit": 5},
    },
}


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (12, 18), color=(32, 64, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes(*, size: tuple[int, int] = (12, 18)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(32, 64, 128)).save(buffer, format="JPEG")
    return buffer.getvalue()


class MCPServerTests(unittest.TestCase):
    def setUp(self):
        self.http_app = FastAPI()
        self.http_app.add_middleware(mcp_server.MCPPathCompatibilityMiddleware)
        self.http_app.mount("/mcp", mcp_server.mcp_mount_app)

    async def _request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.http_app),
            base_url="http://testserver",
            follow_redirects=False,
        ) as client:
            return await client.request(method, path, **kwargs)

    def _enabled_settings(self, *, origins=(), auth_mode="static"):
        return mcp_server.MCPRuntimeSettings(
            enabled=True,
            auth_mode=auth_mode,
            api_key="test-mcp-token",
            allowed_origins=tuple(origins),
            oauth_issuer_url="https://auth.kabolly.com/application/o/plexintel-chatgpt/",
            oauth_audience=None,
            oauth_email_claim="email",
            oauth_resource_url="https://plexintel.kabolly.com/mcp",
            oauth_required_scopes=("plexintel.read",),
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
                    "http://testserver/mcp",
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
                        native_poster_result = await session.call_tool(
                            "get_poster_image_native",
                            {"rating_key": 42},
                        )
                        native_gallery_result = await session.call_tool(
                            "get_poster_gallery_native",
                            {
                                "items": [
                                    {"rating_key": 42, "title": "Blade Runner 2049"},
                                    {"rating_key": 88, "title": "Black Bag"},
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
            "native_poster": native_poster_result,
            "native_gallery": native_gallery_result,
            "recent": recent_result,
            "history": history_result,
        }

    async def _exercise_unauthenticated_protocol(self, *, call_tools: bool = False, headers=None):
        tool_arguments = {
            "list_users": {},
            "get_recommendations": {},
            "get_recommendation_score": {"rating_key": 37641},
            "search_library": {"q": "private-sentinel"},
            "get_library_item": {"rating_key": 42},
            "get_poster_image": {"rating_key": 42},
            "get_poster_gallery": {"rating_keys": [42]},
            "get_poster_image_native": {"rating_key": 42},
            "get_poster_gallery_native": {"rating_keys": [42]},
            "get_recent_library_additions": {},
            "get_watch_history": {},
        }
        async with mcp_server.mcp_runtime.lifespan():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.http_app),
                base_url="http://testserver",
                headers=headers,
                follow_redirects=True,
            ) as client:
                async with streamable_http_client(
                    "http://testserver/mcp",
                    http_client=client,
                ) as (read, write, _get_session_id):
                    async with ClientSession(read, write) as session:
                        initialize_result = await session.initialize()
                        tools_result = await session.list_tools()
                        call_results = {}
                        if call_tools:
                            for tool_name, arguments in tool_arguments.items():
                                call_results[tool_name] = await session.call_tool(tool_name, arguments)

        return initialize_result, tools_result, call_results

    async def _exercise_single_tool_call(self, name: str, arguments: dict, *, headers=None):
        async with mcp_server.mcp_runtime.lifespan():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.http_app),
                base_url="http://testserver",
                headers=headers,
                follow_redirects=True,
            ) as client:
                async with streamable_http_client(
                    "http://testserver/mcp/",
                    http_client=client,
                ) as (read, write, _get_session_id):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        return await session.call_tool(name, arguments)

    async def _raw_unauthenticated_tools_list(self):
        headers = {"Accept": "application/json, text/event-stream"}
        initialized_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        list_payload = {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/list",
            "params": {},
        }
        async with mcp_server.mcp_runtime.lifespan():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.http_app),
                base_url="http://testserver",
                follow_redirects=False,
            ) as client:
                initialize_response = await client.post(
                    "/mcp",
                    json=INITIALIZE_PAYLOAD,
                    headers=headers,
                )
                initialized_response = await client.post(
                    "/mcp",
                    json=initialized_payload,
                    headers=headers,
                )
                tools_response = await client.post(
                    "/mcp",
                    json=list_payload,
                    headers=headers,
                )
        return initialize_response, initialized_response, tools_response

    async def _raw_authenticated_tool_call(self, name: str, arguments: dict):
        payload = {
            "jsonrpc": "2.0",
            "id": "native-poster",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        async with mcp_server.mcp_runtime.lifespan():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.http_app),
                base_url="http://testserver",
                follow_redirects=False,
            ) as client:
                return await client.post(
                    "/mcp",
                    json=payload,
                    headers={
                        "Authorization": "Bearer test-mcp-token",
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": "2025-11-25",
                    },
                )

    async def _post_mcp_payload_variants(self, payload):
        encoded = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer test-mcp-token",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
        }

        async def streamed_body():
            midpoint = len(encoded) // 2
            yield encoded[:midpoint]
            await anyio.sleep(0)
            yield encoded[midpoint:]

        results = []
        async with mcp_server.mcp_runtime.lifespan():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.http_app),
                base_url="http://testserver",
                follow_redirects=False,
            ) as client:
                for path in ("/mcp", "/mcp/"):
                    for streamed in (False, True):
                        start = time.perf_counter()
                        response = await client.post(
                            path,
                            content=streamed_body() if streamed else encoded,
                            headers=headers,
                        )
                        results.append((path, streamed, response, time.perf_counter() - start))
        return results

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
                "get_poster_image_native",
                "get_poster_gallery_native",
                "get_recent_library_additions",
                "get_watch_history",
            },
        )
        for tool in results["tools"].tools:
            self.assertTrue(tool.annotations.readOnlyHint, tool.name)
            self.assertFalse(tool.annotations.destructiveHint, tool.name)
            self.assertTrue(tool.annotations.idempotentHint, tool.name)
            self.assertEqual(
                tool.securitySchemes,
                [{"type": "oauth2", "scopes": ["plexintel.read"]}],
                tool.name,
            )
            self.assertFalse(tool.meta and "securitySchemes" in tool.meta, tool.name)
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
        self.assertEqual(
            [item.type for item in results["native_poster"].content],
            ["text", "image"],
        )
        self.assertEqual(results["native_poster"].content[1].mimeType, "image/png")
        self.assertEqual(
            base64.b64decode(results["native_poster"].content[1].data, validate=True),
            _png_bytes(),
        )
        self.assertEqual(
            [item.type for item in results["native_gallery"].content],
            ["text", "image", "text", "image"],
        )
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

    def test_native_single_poster_serializes_real_image_content_through_transport(self):
        poster_bytes = _jpeg_bytes()
        library_item = LibraryItem(
            rating_key=42,
            title="Blade Runner 2049",
            media_type="movie",
            year=2017,
        )
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(),
        ):
            with patch.object(mcp_server, "get_agent_library_item", return_value=library_item):
                with patch.object(
                    mcp_server,
                    "fetch_poster_image_for_rating_key",
                    return_value={"content": poster_bytes, "content_type": "image/jpeg"},
                ):
                    response = anyio.run(
                        lambda: self._raw_authenticated_tool_call(
                            "get_poster_image_native",
                            {"rating_key": 42},
                        )
                    )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("location", response.headers)
        result = response.json()["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(len(result["content"]), 2)
        self.assertEqual(
            result["content"][0],
            {"type": "text", "text": "Poster for Blade Runner 2049 (2017)."},
        )
        image = result["content"][1]
        self.assertEqual(image["type"], "image")
        self.assertEqual(image["mimeType"], "image/jpeg")
        self.assertFalse(image["data"].startswith("data:"))
        decoded = base64.b64decode(image["data"], validate=True)
        self.assertEqual(decoded, poster_bytes)
        self.assertTrue(decoded.startswith(b"\xff\xd8\xff"))
        self.assertNotIn("data", result["structuredContent"])

    def test_native_gallery_preserves_label_image_order_and_continues_after_missing(self):
        first_bytes = _jpeg_bytes(size=(12, 18))
        third_bytes = _png_bytes()
        items_by_key = {
            11: LibraryItem(
                rating_key=11,
                title="First",
                media_type="movie",
                year=2001,
            ),
            22: LibraryItem(
                rating_key=22,
                title="Missing",
                media_type="movie",
                year=2002,
            ),
            33: LibraryItem(
                rating_key=33,
                title="Third",
                media_type="show",
                year=2003,
            ),
        }
        posters_by_key = {
            11: {"content": first_bytes, "content_type": "image/jpeg"},
            22: None,
            33: {"content": third_bytes, "content_type": "image/png"},
        }
        with patch.object(
            mcp_server,
            "get_agent_library_item",
            side_effect=lambda *, rating_key: items_by_key[rating_key],
        ):
            with patch.object(
                mcp_server,
                "fetch_poster_image_for_rating_key",
                side_effect=lambda rating_key: posters_by_key[rating_key],
            ):
                result = mcp_server.build_poster_gallery_native_result(
                    rating_keys=[11, 22, 33]
                )

        self.assertFalse(result.isError)
        self.assertEqual(
            [item.type for item in result.content],
            ["text", "image", "text", "text", "image"],
        )
        self.assertEqual(result.content[0].text, "Poster for First (2001).")
        self.assertEqual(base64.b64decode(result.content[1].data), first_bytes)
        self.assertEqual(result.content[2].text, "Poster unavailable for Missing (2002).")
        self.assertEqual(result.content[3].text, "Poster for Third (2003).")
        self.assertEqual(base64.b64decode(result.content[4].data), third_bytes)
        self.assertEqual(
            [item["rating_key"] for item in result.structuredContent["items"]],
            [11, 22, 33],
        )
        self.assertEqual(
            [item["found"] for item in result.structuredContent["items"]],
            [True, False, True],
        )

    def test_native_poster_rejects_invalid_identifiers_and_gallery_limit_before_fetch(self):
        with patch.object(mcp_server, "fetch_poster_image_for_rating_key") as fetch_poster:
            invalid_single = mcp_server.build_poster_image_native_result(-1)
            invalid_gallery = mcp_server.build_poster_gallery_native_result(
                items=[{"rating_key": "not-an-integer"}]
            )
            oversized_gallery = mcp_server.build_poster_gallery_native_result(
                rating_keys=list(range(1, mcp_server.NATIVE_POSTER_GALLERY_MAX_ITEMS + 2))
            )

        self.assertTrue(invalid_single.isError)
        self.assertIn("positive integer", invalid_single.content[0].text)
        self.assertTrue(invalid_gallery.isError)
        self.assertIn("positive integer", invalid_gallery.content[0].text)
        self.assertTrue(oversized_gallery.isError)
        self.assertIn("limited to 8", oversized_gallery.content[0].text)
        fetch_poster.assert_not_called()

    def test_native_single_poster_enforces_resized_image_limit(self):
        library_item = LibraryItem(rating_key=42, title="From", media_type="movie")
        with patch.object(mcp_server, "get_agent_library_item", return_value=library_item):
            with patch.object(
                mcp_server,
                "fetch_poster_image_for_rating_key",
                return_value={"content": _jpeg_bytes(), "content_type": "image/jpeg"},
            ):
                with patch.object(
                    mcp_server,
                    "resize_poster_image_to_width",
                    return_value={
                        "content": b"x" * (mcp_server.NATIVE_POSTER_MAX_BYTES + 1),
                        "content_type": "image/jpeg",
                    },
                ):
                    result = mcp_server.build_poster_image_native_result(42)

        self.assertTrue(result.isError)
        self.assertIn(str(mcp_server.NATIVE_POSTER_MAX_BYTES), result.content[0].text)
        self.assertNotIn("x" * 100, str(result.model_dump()))

    def test_native_poster_payload_is_not_logged(self):
        poster_bytes = _jpeg_bytes()
        encoded = base64.b64encode(poster_bytes).decode("ascii")
        records: list[str] = []

        class RecordingHandler(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))

        handler = RecordingHandler()
        mcp_server.logger.addHandler(handler)
        try:
            with patch.object(
                mcp_server,
                "get_agent_library_item",
                return_value=LibraryItem(rating_key=42, title="From", media_type="movie"),
            ):
                with patch.object(
                    mcp_server,
                    "fetch_poster_image_for_rating_key",
                    return_value={"content": poster_bytes, "content_type": "image/jpeg"},
                ):
                    result = mcp_server.build_poster_image_native_result(42)
        finally:
            mcp_server.logger.removeHandler(handler)

        self.assertFalse(result.isError)
        logged = "\n".join(records)
        self.assertNotIn(encoded, logged)
        self.assertNotIn(repr(poster_bytes), logged)

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
                oauth_resource_url=None,
                oauth_required_scopes=("plexintel.read",),
                trusted_user_email_header="X-OpenWebUI-User-Email",
            ),
        ):
            response = anyio.run(lambda: self._request("POST", "/mcp/", json=INITIALIZE_PAYLOAD))

        self.assertEqual(response.status_code, 404)

    def test_initialize_accepts_canonical_and_trailing_slash_paths_without_redirects(self):
        async def exercise_paths():
            async with mcp_server.mcp_runtime.lifespan():
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=self.http_app),
                    base_url="http://testserver",
                    follow_redirects=False,
                ) as client:
                    return [
                        await client.post(
                            path,
                            json=INITIALIZE_PAYLOAD,
                            headers={"Accept": "application/json, text/event-stream"},
                        )
                        for path in ("/mcp", "/mcp/")
                    ]

        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt_or_static"),
        ):
            responses = anyio.run(exercise_paths)

        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["result"]["serverInfo"]["name"])
            self.assertNotIn("location", response.headers)
            self.assertEqual(response.history, [])

    def test_identical_buffered_and_streamed_requests_reach_mcp_on_both_paths(self):
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
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt_or_static"),
        ):
            initialize_results = anyio.run(
                lambda: self._post_mcp_payload_variants(INITIALIZE_PAYLOAD)
            )
            with patch.object(
                mcp_server,
                "get_recent_library_additions",
                return_value=recent_payload,
            ) as data_access:
                call_results = anyio.run(
                    lambda: self._post_mcp_payload_variants(RECENT_ADDITIONS_PAYLOAD)
                )

        for path, streamed, response, duration in initialize_results:
            with self.subTest(path=path, streamed=streamed, method="initialize"):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["result"]["serverInfo"]["name"])
                self.assertNotIn("location", response.headers)
                self.assertEqual(response.history, [])
                self.assertLess(duration, 2.0)

        for path, streamed, response, duration in call_results:
            with self.subTest(path=path, streamed=streamed, method="tools/call"):
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["result"]["isError"])
                self.assertEqual(
                    response.json()["result"]["structuredContent"]["items"][0]["title"],
                    "Black Bag",
                )
                self.assertNotIn("location", response.headers)
                self.assertEqual(response.history, [])
                self.assertLess(duration, 2.0)
        self.assertEqual(data_access.call_count, 4)

    def test_no_slash_alias_preserves_scope_headers_raw_path_and_receive(self):
        captured = {}
        receive_messages = [
            {"type": "http.request", "body": b'{"jsonrpc":', "more_body": True},
            {"type": "http.request", "body": b'"2.0"}', "more_body": False},
        ]

        async def downstream(scope, receive, _send):
            captured["scope"] = scope
            captured["receive"] = receive
            captured["messages"] = [await receive(), await receive()]

        async def exercise_alias():
            async def receive():
                return receive_messages.pop(0)

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "raw_path": b"/mcp",
                "root_path": "",
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"accept", b"application/json, text/event-stream"),
                    (b"authorization", b"Bearer test-secret"),
                    (b"mcp-protocol-version", b"2025-11-25"),
                    (b"transfer-encoding", b"chunked"),
                ],
            }
            original_headers = list(scope["headers"])
            middleware = mcp_server.MCPPathCompatibilityMiddleware(downstream)
            with self.assertLogs(mcp_server.logger, level="INFO") as logs:
                await middleware(scope, receive, lambda _message: None)
            return receive, original_headers, logs.output

        original_receive, original_headers, logs = anyio.run(exercise_alias)

        self.assertEqual(captured["scope"]["path"], "/mcp/")
        self.assertEqual(captured["scope"]["raw_path"], b"/mcp")
        self.assertEqual(captured["scope"]["headers"], original_headers)
        self.assertIs(captured["receive"], original_receive)
        self.assertEqual(
            captured["messages"],
            [
                {"type": "http.request", "body": b'{"jsonrpc":', "more_body": True},
                {"type": "http.request", "body": b'"2.0"}', "more_body": False},
            ],
        )
        self.assertIn("content_type=application/json", logs[0])
        self.assertIn("transfer_encoding=chunked", logs[0])
        self.assertIn("authorization_present=True", logs[0])
        self.assertIn("no_slash_alias=True", logs[0])
        self.assertNotIn("test-secret", logs[0])

    def test_access_control_passes_original_receive_to_fastmcp_without_preconsuming_body(self):
        captured = {"receive_calls": 0}

        async def downstream(_scope, receive, send):
            captured["receive"] = receive
            captured["message"] = await receive()
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        class RuntimeStub:
            @staticmethod
            def get_asgi_app():
                return downstream

        async def exercise_access_control():
            async def receive():
                captured["receive_calls"] += 1
                return {
                    "type": "http.request",
                    "body": b'{"jsonrpc":"2.0"}',
                    "more_body": False,
                }

            async def send(_message):
                return None

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/",
                "root_path": "/mcp",
                "headers": [(b"authorization", b"Bearer test-mcp-token")],
                "client": ("127.0.0.1", 1234),
            }
            app = mcp_server.MCPAccessControlApp(RuntimeStub())
            with patch.object(
                mcp_server,
                "get_mcp_runtime_settings",
                return_value=self._enabled_settings(auth_mode="static"),
            ):
                await app(scope, receive, send)
            return receive

        original_receive = anyio.run(exercise_access_control)

        self.assertIs(captured["receive"], original_receive)
        self.assertEqual(captured["receive_calls"], 1)
        self.assertEqual(captured["message"]["body"], b'{"jsonrpc":"2.0"}')

    def test_unauthenticated_initialize_and_tools_list_are_data_free(self):
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt_or_static"),
        ):
            initialize_result, tools_result, _ = anyio.run(self._exercise_unauthenticated_protocol)

        self.assertTrue(initialize_result.serverInfo.name)
        serialized_discovery = f"{initialize_result.model_dump()} {tools_result.model_dump()}"
        self.assertNotIn("private-sentinel", serialized_discovery)
        self.assertNotIn("jason@sheffieldave.com", serialized_discovery)
        self.assertNotIn("Blade Runner 2049", serialized_discovery)

        expected_tools = {
            "list_users",
            "get_recommendations",
            "get_recommendation_score",
            "search_library",
            "get_library_item",
            "get_poster_image",
            "get_poster_gallery",
            "get_poster_image_native",
            "get_poster_gallery_native",
            "get_recent_library_additions",
            "get_watch_history",
        }
        self.assertEqual({tool.name for tool in tools_result.tools}, expected_tools)
        for tool in tools_result.tools:
            self.assertEqual(
                tool.securitySchemes,
                [{"type": "oauth2", "scopes": ["plexintel.read"]}],
                tool.name,
            )
            self.assertNotIn("noauth", str(tool.securitySchemes).lower(), tool.name)

    def test_raw_tools_list_serializes_oauth_security_schemes_at_top_level(self):
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt_or_static"),
        ):
            initialize_response, initialized_response, tools_response = anyio.run(
                self._raw_unauthenticated_tools_list
            )

        self.assertEqual(initialize_response.status_code, 200)
        self.assertIn(initialized_response.status_code, (200, 202))
        self.assertEqual(tools_response.status_code, 200)
        tools = tools_response.json()["result"]["tools"]
        self.assertEqual(
            {tool["name"] for tool in tools},
            {
                "list_users",
                "get_recommendations",
                "get_recommendation_score",
                "search_library",
                "get_library_item",
                "get_poster_image",
                "get_poster_gallery",
                "get_poster_image_native",
                "get_poster_gallery_native",
                "get_recent_library_additions",
                "get_watch_history",
            },
        )
        for tool in tools:
            self.assertEqual(
                tool["securitySchemes"],
                [{"type": "oauth2", "scopes": ["plexintel.read"]}],
                tool["name"],
            )
            self.assertNotIn("noauth", str(tool["securitySchemes"]).lower(), tool["name"])
            self.assertNotIn("securitySchemes", tool.get("_meta") or {}, tool["name"])

        tools_by_name = {tool["name"]: tool for tool in tools}
        single_schema = tools_by_name["get_poster_image_native"]["inputSchema"]
        self.assertEqual(single_schema["required"], ["rating_key"])
        self.assertEqual(single_schema["properties"]["rating_key"]["type"], "integer")
        gallery_schema = tools_by_name["get_poster_gallery_native"]["inputSchema"]
        self.assertEqual(set(gallery_schema["properties"]), {"rating_keys", "items"})
        self.assertNotIn("required", gallery_schema)

    def test_unauthenticated_calls_to_every_tool_return_native_oauth_error_without_data_access(self):
        protected_functions = (
            "list_agent_users",
            "get_agent_recommendations",
            "get_agent_recommendation_score",
            "search_agent_library",
            "get_agent_library_item",
            "build_poster_image_result",
            "build_poster_gallery_result",
            "build_poster_image_native_result",
            "build_poster_gallery_native_result",
            "get_recent_library_additions",
            "get_agent_watch_history",
        )
        mocks = []
        patches = [patch.object(mcp_server, name) for name in protected_functions]
        for active_patch in patches:
            mocks.append(active_patch.start())
        self.addCleanup(lambda: [active_patch.stop() for active_patch in reversed(patches)])

        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt_or_static"),
        ):
            _, _, call_results = anyio.run(
                lambda: self._exercise_unauthenticated_protocol(call_tools=True)
            )

        self.assertEqual(len(call_results), 11)
        for tool_name, result in call_results.items():
            self.assertTrue(result.isError, tool_name)
            self.assertEqual(result.content[0].text, "Authentication required.", tool_name)
            challenge = result.meta["mcp/www_authenticate"][0]
            self.assertIn(
                'resource_metadata="https://plexintel.kabolly.com/.well-known/oauth-protected-resource"',
                challenge,
            )
            self.assertIn('scope="plexintel.read"', challenge)
            self.assertIn('error="insufficient_scope"', challenge)
            self.assertIn('error_description="Sign in to PlexIntel to continue"', challenge)
            self.assertNotIn("private-sentinel", str(result.model_dump()))
        for data_access_mock in mocks:
            data_access_mock.assert_not_called()

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

    def test_invalid_or_insufficient_jwt_reaches_tool_layer_but_not_handler(self):
        for status in (
            mcp_server.MCPTokenStatus.INVALID,
            mcp_server.MCPTokenStatus.INSUFFICIENT_SCOPE,
            mcp_server.MCPTokenStatus.EXPIRED,
            mcp_server.MCPTokenStatus.WRONG_AUDIENCE,
            mcp_server.MCPTokenStatus.WRONG_ISSUER,
            mcp_server.MCPTokenStatus.UNMAPPED_EMAIL,
        ):
            with self.subTest(status=status):
                with patch.object(
                    mcp_server,
                    "get_mcp_runtime_settings",
                    return_value=self._enabled_settings(auth_mode="jwt_or_static"),
                ):
                    with patch.object(
                        mcp_server,
                        "validate_bearer_token",
                        return_value=mcp_server.MCPTokenValidation(status),
                    ):
                        with patch.object(mcp_server, "list_agent_users") as data_access:
                            result = anyio.run(
                                lambda: self._exercise_single_tool_call(
                                    "list_users",
                                    {},
                                    headers={"Authorization": "Bearer header.payload.signature"},
                                )
                            )

                self.assertTrue(result.isError)
                self.assertIn('error="insufficient_scope"', result.meta["mcp/www_authenticate"][0])
                data_access.assert_not_called()

    def test_mcp_jwt_mode_accepts_valid_token(self):
        jwt_context = MCPAuthContext(
            auth_method="jwt",
            email="jason@sheffieldave.com",
            plex_username="jmnovak",
        )
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings(auth_mode="jwt")
        headers = Headers({"authorization": "Bearer valid-jwt"})

        validation = mcp_server.MCPTokenValidation(mcp_server.MCPTokenStatus.VALID, jwt_context)
        with patch.object(mcp_server, "validate_bearer_token", return_value=validation):
            result = app._authenticate_request(headers=headers, settings=settings)

        self.assertIsNone(result.response)
        self.assertEqual(result.context, jwt_context)

    def test_valid_mapped_jwt_reaches_protected_tool_handler(self):
        jwt_context = MCPAuthContext(
            auth_method="jwt",
            email="jason@sheffieldave.com",
            plex_username="jmnovak",
            user_id=7,
        )
        users_payload = AgentUsersResponse(
            count=1,
            items=[AgentUser(username="jmnovak", friendly_name="Jason")],
        )
        validation = mcp_server.MCPTokenValidation(mcp_server.MCPTokenStatus.VALID, jwt_context)
        with patch.object(
            mcp_server,
            "get_mcp_runtime_settings",
            return_value=self._enabled_settings(auth_mode="jwt"),
        ):
            with patch.object(mcp_server, "validate_bearer_token", return_value=validation):
                with patch.object(
                    mcp_server,
                    "list_agent_users",
                    return_value=users_payload,
                ) as data_access:
                    result = anyio.run(
                        lambda: self._exercise_single_tool_call(
                            "list_users",
                            {},
                            headers={"Authorization": "Bearer valid.jwt.token"},
                        )
                    )

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["items"][0]["username"], "jmnovak")
        data_access.assert_called_once_with(username=None, friendly_name=None, limit=200)

    def test_mcp_jwt_or_static_falls_back_to_static_key(self):
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings(auth_mode="jwt_or_static")
        headers = Headers({"authorization": "Bearer test-mcp-token"})

        result = app._authenticate_request(headers=headers, settings=settings)

        self.assertIsNone(result.response)
        self.assertEqual(result.context.auth_method, "static")

    def test_mcp_jwt_or_static_does_not_fall_back_for_jwt_shaped_token(self):
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        settings = self._enabled_settings(auth_mode="jwt_or_static")
        headers = Headers({"authorization": "Bearer header.payload.signature"})

        with patch.object(
            mcp_server,
            "validate_bearer_token",
            return_value=mcp_server.MCPTokenValidation(mcp_server.MCPTokenStatus.INVALID),
        ):
            result = app._authenticate_request(headers=headers, settings=settings)

        self.assertIsNone(result.response)
        self.assertIsNone(result.context)

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

    def test_enrich_auth_context_ignores_trusted_header_for_jwt(self):
        app = mcp_server.MCPAccessControlApp(mcp_server.mcp_runtime)
        initial = app._AuthResult(
            response=None,
            context=MCPAuthContext(auth_method="jwt", email="unknown@example.com"),
        )
        with patch.object(mcp_server, "resolve_context_from_email") as resolve:
            result = app._enrich_auth_context(
                headers=Headers({"x-openwebui-user-email": "jason@sheffieldave.com"}),
                settings=self._enabled_settings(auth_mode="jwt"),
                auth_result=initial,
            )
        resolve.assert_not_called()
        self.assertEqual(result.context.email, "unknown@example.com")
        self.assertIsNone(result.context.plex_username)


if __name__ == "__main__":
    unittest.main()
