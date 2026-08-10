from __future__ import annotations

import base64
import threading
import time
import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

import anyio
from PIL import Image

from api.services import mcp_server
from api.services.agent_tool_service import RecentLibraryAdditionsResponse, RecentLibraryItem


def _jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (12, 18), color=(32, 64, 128)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _movie_item(rating_key: int) -> dict:
    return {
        "rating_key": rating_key,
        "title": f"Movie {rating_key}",
        "year": 2000 + (rating_key % 20),
        "media_type": "movie",
        "added_at": "2026-08-09T23:19:25",
    }


class NativePosterFeedTests(unittest.TestCase):
    def setUp(self):
        self.poster_bytes = _jpeg_bytes()

    def _build_gallery(self, items: list[dict], **kwargs):
        with patch.object(
            mcp_server,
            "_fetch_native_poster",
            return_value=(self.poster_bytes, "image/jpeg"),
        ):
            return mcp_server.build_poster_gallery_native_result(items=items, **kwargs)

    def test_native_gallery_of_one_returns_label_then_real_image_content(self):
        result = self._build_gallery([_movie_item(1)])

        self.assertFalse(result.isError)
        self.assertEqual([block.type for block in result.content], ["text", "image"])
        self.assertEqual(result.content[0].text, "Movie 1 (2001)\nMovie · Added Aug 9, 2026")
        self.assertEqual(result.content[1].mimeType, "image/jpeg")
        self.assertEqual(base64.b64decode(result.content[1].data), self.poster_bytes)
        self.assertFalse(result.content[1].data.startswith("data:"))
        self.assertNotIn("![", result.content[0].text)
        self.assertNotIn("<img", result.content[0].text)

    def test_native_gallery_of_eight_preserves_interleaved_order(self):
        items = [_movie_item(index) for index in range(1, 9)]
        result = self._build_gallery(items)

        self.assertEqual(len(result.content), 16)
        self.assertEqual(
            [block.type for block in result.content],
            [kind for _ in items for kind in ("text", "image")],
        )
        self.assertEqual(
            [item["rating_key"] for item in result.structuredContent["items"]],
            list(range(1, 9)),
        )

    def test_native_gallery_of_forty_fetches_in_parallel_without_truncation(self):
        items = [_movie_item(index) for index in range(1, 41)]
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fetch(_rating_key):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return self.poster_bytes, "image/jpeg"

        started = time.perf_counter()
        with patch.object(mcp_server, "_fetch_native_poster", side_effect=fetch):
            result = mcp_server.build_poster_gallery_native_result(items=items)
        elapsed = time.perf_counter() - started

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["count"], 40)
        self.assertEqual(len(result.content), 80)
        self.assertGreater(max_active, 1)
        self.assertLess(elapsed, 0.5)
        self.assertEqual(
            [item["rating_key"] for item in result.structuredContent["items"]],
            list(range(1, 41)),
        )

    def test_native_gallery_accepts_fifty_and_rejects_fifty_one(self):
        accepted = self._build_gallery([_movie_item(index) for index in range(1, 51)])
        rejected = mcp_server.build_poster_gallery_native_result(
            items=[_movie_item(index) for index in range(1, 52)]
        )

        self.assertFalse(accepted.isError)
        self.assertEqual(accepted.structuredContent["count"], 50)
        self.assertTrue(rejected.isError)
        self.assertIn("limited to 50", rejected.content[0].text)

    def test_missing_poster_does_not_fail_or_reorder_gallery(self):
        items = [_movie_item(1), _movie_item(2), _movie_item(3)]

        def fetch(rating_key):
            if rating_key == 2:
                return None
            return self.poster_bytes, "image/jpeg"

        with patch.object(mcp_server, "_fetch_native_poster", side_effect=fetch):
            result = mcp_server.build_poster_gallery_native_result(items=items)

        self.assertFalse(result.isError)
        self.assertEqual(
            [block.type for block in result.content],
            ["text", "image", "text", "text", "image"],
        )
        self.assertIn("Movie 2", result.content[2].text)
        self.assertIn("Poster unavailable", result.content[2].text)
        self.assertEqual(
            [item["found"] for item in result.structuredContent["items"]],
            [True, False, True],
        )

    def test_mixed_movie_episode_show_and_season_labels(self):
        items = [
            _movie_item(1),
            {
                "rating_key": 2,
                "title": "The Drive",
                "show_title": "Silo",
                "media_type": "episode",
                "season_number": 3,
                "episode_number": 6,
                "added_at": "2026-08-07T12:00:00",
            },
            {"rating_key": 3, "title": "Silo", "media_type": "show", "year": 2023},
            {
                "rating_key": 4,
                "title": "Silo",
                "show_title": "Silo",
                "media_type": "season",
                "season_number": 3,
                "year": 2026,
            },
        ]
        result = self._build_gallery(items)
        labels = [result.content[index].text for index in range(0, 8, 2)]

        self.assertEqual(labels[0], "Movie 1 (2001)\nMovie · Added Aug 9, 2026")
        self.assertEqual(labels[1], "Silo · S3E6 · The Drive\nEpisode · Added Aug 7, 2026")
        self.assertEqual(labels[2], "Silo (2023)\nShow")
        self.assertEqual(labels[3], "Silo · S3 (2026)\nSeason")

    def test_episode_title_alias_is_supported(self):
        result = self._build_gallery(
            [
                {
                    "rating_key": 5,
                    "episode_title": "Pick a Sticker",
                    "show_title": "Furious",
                    "media_type": "episode",
                    "season_number": 1,
                    "episode_number": 5,
                }
            ]
        )

        self.assertEqual(result.content[0].text, "Furious · S1E5 · Pick a Sticker\nEpisode")

    def test_dedupe_posters_returns_one_image_per_show_season(self):
        items = [
            {
                "rating_key": index,
                "title": f"Episode {index}",
                "show_title": "Silo",
                "media_type": "episode",
                "season_number": 3,
                "episode_number": index,
            }
            for index in range(1, 4)
        ]
        with patch.object(
            mcp_server,
            "_fetch_native_poster",
            return_value=(self.poster_bytes, "image/jpeg"),
        ) as fetch:
            result = mcp_server.build_poster_gallery_native_result(
                items=items,
                dedupe_posters=True,
            )

        self.assertEqual([block.type for block in result.content], ["text", "image", "text", "text"])
        self.assertIn("Poster omitted (same season artwork)", result.content[2].text)
        self.assertIn("Poster omitted (same season artwork)", result.content[3].text)
        fetch.assert_called_once_with(1)

    def test_recent_additions_native_returns_interleaved_feed_in_one_call(self):
        recent = RecentLibraryAdditionsResponse(
            media_type=None,
            days=7,
            count=2,
            items=[
                RecentLibraryItem(
                    rating_key=37921,
                    title="Alien vs. Predator",
                    media_type="movie",
                    year=2004,
                    added_at=datetime(2026, 8, 9, 23, 19, 25),
                ),
                RecentLibraryItem(
                    rating_key=500,
                    title="Pick a Sticker",
                    show_title="Furious",
                    media_type="episode",
                    season_number=1,
                    episode_number=5,
                    added_at=datetime(2026, 8, 10, 8, 0, 0),
                ),
            ],
        )
        with patch.object(
            mcp_server,
            "get_recent_library_additions",
            return_value=recent,
        ) as lookup:
            with patch.object(
                mcp_server,
                "_fetch_native_poster",
                return_value=(self.poster_bytes, "image/jpeg"),
            ):
                result = mcp_server.build_recent_library_additions_native_result(days=7, limit=50)

        lookup.assert_called_once_with(media_type=None, days=7, limit=50)
        self.assertEqual([block.type for block in result.content], ["text", "image", "text", "image"])
        self.assertEqual(
            result.content[0].text,
            "Alien vs. Predator (2004)\nMovie · Added Aug 9, 2026",
        )
        self.assertEqual(
            result.content[2].text,
            "Furious · S1E5 · Pick a Sticker\nEpisode · Added Aug 10, 2026",
        )
        self.assertEqual(result.structuredContent["days"], 7)
        self.assertEqual(result.structuredContent["count"], 2)

    def test_recent_additions_native_is_discoverable_with_valid_schema(self):
        async def discover():
            server = mcp_server._build_mcp_server()
            return await server.list_tools()

        tools = anyio.run(discover)
        tool = next(tool for tool in tools if tool.name == "get_recent_library_additions_native")
        properties = tool.inputSchema["properties"]

        self.assertEqual(set(properties), {"days", "media_type", "limit", "dedupe_posters"})
        self.assertEqual(properties["days"]["default"], 7)
        self.assertEqual(properties["limit"]["default"], 50)
        self.assertEqual(properties["limit"]["maximum"], 50)
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertEqual(
            tool.securitySchemes,
            [{"type": "oauth2", "scopes": ["plexintel.read"]}],
        )


if __name__ == "__main__":
    unittest.main()
