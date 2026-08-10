from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

import anyio
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

from api.services import mcp_server
from api.services.mcp_auth import MCPAuthContext


CANONICAL_BASE_URL = "https://plexintel.kabolly.com"


def _item(
    rating_key: int = 37921,
    *,
    title: str = "Alien vs. Predator",
    media_type: str = "movie",
    **overrides,
) -> mcp_server.RecentAdditionRenderItem:
    values = {
        "rating_key": rating_key,
        "title": title,
        "media_type": media_type,
        "year": 2004,
        "added_at": datetime(2026, 8, 9, 23, 19, 25),
        **overrides,
    }
    return mcp_server.RecentAdditionRenderItem(**values)


class RecentAdditionsMCPAppsTests(unittest.TestCase):
    async def _discover(self):
        server = mcp_server._build_mcp_server()
        return await server.list_tools(), await server.list_resources(), server

    def test_ui_resource_registration_mime_type_and_csp(self):
        tools, resources, server = anyio.run(self._discover)
        del tools
        resource = next(
            resource
            for resource in resources
            if str(resource.uri) == mcp_server.RECENT_ADDITIONS_WIDGET_URI
        )

        self.assertEqual(resource.mimeType, "text/html;profile=mcp-app")
        self.assertEqual(
            resource.meta["ui"]["csp"]["resourceDomains"],
            [CANONICAL_BASE_URL],
        )
        self.assertEqual(
            resource.meta["openai/widgetCSP"]["resource_domains"],
            [CANONICAL_BASE_URL],
        )

        contents = anyio.run(server.read_resource, mcp_server.RECENT_ADDITIONS_WIDGET_URI)
        content = list(contents)[0]
        self.assertEqual(content.mime_type, "text/html;profile=mcp-app")
        self.assertIn("ui/notifications/tool-result", content.content)
        self.assertIn("window.openai?.toolOutput", content.content)

    def test_render_tool_registration_schema_metadata_and_annotations(self):
        tools, _, _ = anyio.run(self._discover)
        tool = next(tool for tool in tools if tool.name == "render_recent_library_additions")

        self.assertEqual(
            tool.meta["ui"]["resourceUri"],
            mcp_server.RECENT_ADDITIONS_WIDGET_URI,
        )
        self.assertEqual(
            tool.meta["openai/outputTemplate"],
            mcp_server.RECENT_ADDITIONS_WIDGET_URI,
        )
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertFalse(tool.annotations.destructiveHint)
        self.assertEqual(tool.inputSchema["required"], ["items"])
        item_schema = tool.inputSchema["$defs"]["RecentAdditionRenderItem"]
        self.assertEqual(item_schema["properties"]["rating_key"]["exclusiveMinimum"], 0)
        self.assertEqual(
            set(tool.outputSchema["properties"]),
            {"items", "count", "days"},
        )
        self.assertEqual(tool.outputSchema["required"], ["items", "count"])

    def test_render_item_input_validation_rejects_invalid_rating_keys(self):
        for invalid_rating_key in (0, -1, True, "37921"):
            with self.subTest(rating_key=invalid_rating_key):
                with self.assertRaises(ValidationError):
                    _item(rating_key=invalid_rating_key)

    def test_render_tool_applies_input_validation(self):
        async def call_invalid_tool():
            server = mcp_server._build_mcp_server()
            token = mcp_server.mcp_auth_context.set(MCPAuthContext(auth_method="static"))
            try:
                return await server.call_tool(
                    "render_recent_library_additions",
                    {"items": [{"rating_key": 0, "title": "Invalid", "media_type": "movie"}]},
                )
            finally:
                mcp_server.mcp_auth_context.reset(token)

        with self.assertRaisesRegex(ToolError, "rating_key"):
            anyio.run(call_invalid_tool)

    def test_missing_poster_url_is_constructed_from_rating_key(self):
        expected = f"{CANONICAL_BASE_URL}/api/posters/37921?w=180"
        with patch.object(mcp_server, "build_public_poster_url", return_value=expected) as builder:
            result = mcp_server.build_recent_additions_render_result([_item()], days=7)

        builder.assert_called_once_with(37921, width=180)
        self.assertEqual(result.structuredContent["items"][0]["poster_url"], expected)
        self.assertEqual(result.structuredContent["items"][0]["rating_key"], 37921)
        self.assertEqual(result.structuredContent["items"][0]["title"], "Alien vs. Predator")
        self.assertEqual(result.structuredContent["count"], 1)
        self.assertEqual(result.structuredContent["days"], 7)
        self.assertEqual(
            result.content[0].text,
            "Displaying 1 PlexIntel library additions from the past 7 days.",
        )

    def test_matching_canonical_poster_url_is_accepted(self):
        expected = f"{CANONICAL_BASE_URL}/api/posters/42?w=180"
        item = _item(42, poster_url=expected)
        with patch.object(mcp_server, "build_public_poster_url", return_value=expected):
            result = mcp_server.build_recent_additions_render_result([item])

        self.assertEqual(result.structuredContent["items"][0]["poster_url"], expected)

    def test_arbitrary_external_poster_host_is_rejected(self):
        item = _item(poster_url="https://attacker.example/poster.jpg")
        expected = f"{CANONICAL_BASE_URL}/api/posters/37921?w=180"
        with patch.object(mcp_server, "build_public_poster_url", return_value=expected):
            with self.assertRaisesRegex(ValueError, "must be omitted or match"):
                mcp_server.build_recent_additions_render_result([item])

    def test_movie_and_episode_fields_are_preserved(self):
        movie = _item()
        episode = _item(
            500,
            title="The We We Are",
            media_type="episode",
            show_title="Severance",
            season_number=3,
            episode_number=2,
            year=2026,
        )

        with patch.object(
            mcp_server,
            "build_public_poster_url",
            side_effect=lambda rating_key, width: (
                f"{CANONICAL_BASE_URL}/api/posters/{rating_key}?w={width}"
            ),
        ):
            result = mcp_server.build_recent_additions_render_result([movie, episode], days=7)

        self.assertEqual(result.structuredContent["items"][0]["media_type"], "movie")
        episode_payload = result.structuredContent["items"][1]
        self.assertEqual(episode_payload["show_title"], "Severance")
        self.assertEqual(episode_payload["season_number"], 3)
        self.assertEqual(episode_payload["episode_number"], 2)

    def test_widget_preserves_titles_and_formats_episodes_safely(self):
        html = mcp_server._read_recent_additions_widget()
        self.assertIn('appendText(titleWrap, item.title, "title")', html)
        self.assertIn('`S${String(season).padStart(2, "0")}`', html)
        self.assertIn('`E${String(episode).padStart(2, "0")}`', html)
        self.assertIn("posterPlaceholder(frame, title)", html)
        self.assertIn('image.loading = "lazy"', html)
        self.assertIn("image.alt = `Poster for ${title}`", html)
        self.assertNotIn("titleWrap.innerHTML", html)

    def test_empty_result_has_structured_output_and_widget_empty_state(self):
        result = mcp_server.build_recent_additions_render_result([], days=7)

        self.assertEqual(result.structuredContent, {"items": [], "count": 0, "days": 7})
        self.assertIn("Displaying 0 PlexIntel library additions", result.content[0].text)
        self.assertIn(
            "No recent library additions were supplied for this view.",
            mcp_server._read_recent_additions_widget(),
        )

    def test_thirty_seven_items_are_not_truncated_to_native_gallery_limit(self):
        items = [_item(index, title=f"Title {index}") for index in range(1, 38)]
        with patch.object(
            mcp_server,
            "build_public_poster_url",
            side_effect=lambda rating_key, width: (
                f"{CANONICAL_BASE_URL}/api/posters/{rating_key}?w={width}"
            ),
        ):
            result = mcp_server.build_recent_additions_render_result(items, days=7)

        self.assertEqual(result.structuredContent["count"], 37)
        self.assertEqual(len(result.structuredContent["items"]), 37)
        self.assertEqual(result.structuredContent["items"][-1]["title"], "Title 37")


if __name__ == "__main__":
    unittest.main()
