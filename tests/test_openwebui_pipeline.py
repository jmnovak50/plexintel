from __future__ import annotations

import unittest

from openwebui_pipelines.plexintel_recommendation_pipeline import Pipeline, PipelineHttpError


USERS = {
    "count": 2,
    "items": [
        {"username": "jmnovak", "friendly_name": "Jason"},
        {"username": "other", "friendly_name": "Other User"},
    ],
}


RECOMMENDATIONS = {
    "user": "jmnovak",
    "count": 2,
    "items": [
        {
            "rating_key": 101,
            "title": "Arrival",
            "media_type": "movie",
            "score": 0.93,
            "year": 2016,
            "genres": "Science Fiction, Drama",
            "explanation": "thoughtful science fiction",
        },
        {
            "rating_key": 202,
            "title": "Severance",
            "media_type": "show",
            "score": 0.91,
            "year": 2022,
            "genres": "Science Fiction, Thriller",
        },
    ],
}


GALLERY = {
    "count": 2,
    "items": [
        {
            "rating_key": 101,
            "title": "Arrival",
            "media_type": "movie",
            "poster_url": "https://plexintel.example.com/api/posters/101?w=180",
            "image_url": "https://plexintel.example.com/api/posters/101?w=180",
            "url": "https://plexintel.example.com/api/posters/101?w=180",
            "markdown": "![Poster for Arrival](https://plexintel.example.com/api/posters/101?w=180)",
            "html": "",
        },
        {
            "rating_key": 202,
            "title": "Severance",
            "media_type": "show",
            "poster_url": "https://plexintel.example.com/api/posters/202?w=180",
            "image_url": "https://plexintel.example.com/api/posters/202?w=180",
            "url": "https://plexintel.example.com/api/posters/202?w=180",
            "markdown": "![Poster for Severance](https://plexintel.example.com/api/posters/202?w=180)",
            "html": "",
        },
    ],
    "markdown": (
        "### Arrival\n"
        "![Poster for Arrival](https://plexintel.example.com/api/posters/101?w=180)\n\n"
        "### Severance\n"
        "![Poster for Severance](https://plexintel.example.com/api/posters/202?w=180)"
    ),
}


SEARCH_RESULTS = {
    "query": "blade",
    "count": 1,
    "items": [
        {
            "rating_key": 42,
            "title": "Blade Runner 2049",
            "media_type": "movie",
            "year": 2017,
        }
    ],
}


WATCH_HISTORY = {
    "user": "jmnovak",
    "engaged_only": False,
    "count": 1,
    "results": [
        {
            "watch_id": 1,
            "username": "jmnovak",
            "rating_key": 777,
            "watched_at": "2026-03-02T08:30:00",
            "percent_complete": 0.875,
            "title": "Heat",
            "media_type": "movie",
        }
    ],
}


class FakePipeline(Pipeline):
    def __init__(self):
        super().__init__()
        self.calls: list[tuple[str, str, dict | None]] = []
        self.valves.ENABLE_GEMMA_NARRATION = False

    def _plex_get(self, path, params=None):
        self.calls.append(("GET", path, params or {}))
        if path == "/api/agent/users":
            return USERS
        if path == "/api/agent/recommendations":
            return RECOMMENDATIONS
        if path == "/api/agent/search":
            return SEARCH_RESULTS
        if path == "/api/agent/watch-history":
            return WATCH_HISTORY
        if path == "/api/agent/items/42":
            return SEARCH_RESULTS["items"][0]
        raise AssertionError(f"Unexpected GET {path}")

    def _plex_post(self, path, payload):
        self.calls.append(("POST", path, payload))
        if path == "/api/agent/poster-gallery":
            return GALLERY
        raise AssertionError(f"Unexpected POST {path}")


class OpenWebUIPipelineTests(unittest.TestCase):
    def test_me_unresolved_returns_clarification_without_recommendation_call(self):
        pipe = FakePipeline()

        response = pipe.pipe(
            "Show me 2 movie recommendations for me",
            messages=[],
            body={"user": {"email": "unknown@example.com"}},
        )

        self.assertIn("## Which Plex user?", response)
        self.assertIn("`jmnovak` (Jason)", response)
        self.assertNotIn(("GET", "/api/agent/recommendations", {"user": "jmnovak", "limit": 2}), pipe.calls)
        self.assertFalse(any(call[1] == "/api/agent/recommendations" for call in pipe.calls))

    def test_alias_mapping_selects_user_and_calls_gallery_every_time(self):
        pipe = FakePipeline()
        pipe.valves.USER_ALIASES_JSON = '{"unknown@example.com": "jmnovak"}'

        response = pipe.pipe(
            "Show me top 2 movie recommendations for me",
            body={"user": {"email": "unknown@example.com"}},
        )

        self.assertIn("# PlexIntel Ultimate Recommendations", response)
        self.assertIn("**User:** `jmnovak (Jason)`", response)
        self.assertNotIn("## Poster Gallery", response)
        self.assertIn("![Poster for Arrival](http://192.168.1.9:8489/api/posters/101?w=180)", response)
        self.assertLess(
            response.index("1. **Arrival**"),
            response.index("![Poster for Arrival](http://192.168.1.9:8489/api/posters/101?w=180)"),
        )
        self.assertLess(response.index("1. **Arrival**"), response.index("2. **Severance**"))
        self.assertIn(("POST", "/api/agent/poster-gallery", {
            "items": [
                {"rating_key": 101, "title": "Arrival", "media_type": "movie"},
                {"rating_key": 202, "title": "Severance", "media_type": "show"},
            ],
            "width": 180,
        }), pipe.calls)

    def test_poster_gallery_405_falls_back_to_local_inline_posters(self):
        class FallbackPipeline(FakePipeline):
            def _plex_post(self, path, payload):
                self.calls.append(("POST", path, payload))
                raise PipelineHttpError(endpoint=path, status_code=405, detail="Method Not Allowed")

        pipe = FallbackPipeline()
        pipe.valves.USER_ALIASES_JSON = '{"unknown@example.com": "jmnovak"}'
        pipe.valves.POSTER_BASE_URL = "https://plexintel.example.com"

        response = pipe.pipe(
            "Show me top 2 movie recommendations for me",
            body={"user": {"email": "unknown@example.com"}},
        )

        self.assertNotIn("## PlexIntel Request Failed", response)
        self.assertIn("![Poster for Arrival](https://plexintel.example.com/api/posters/101?w=180)", response)
        self.assertIn("![Poster for Severance](https://plexintel.example.com/api/posters/202?w=180)", response)

    def test_poster_path_prefix_supports_reverse_proxy_mounts(self):
        pipe = FakePipeline()
        pipe.valves.USER_ALIASES_JSON = '{"unknown@example.com": "jmnovak"}'
        pipe.valves.POSTER_BASE_URL = "https://lumina-ai.kabolly.com"
        pipe.valves.POSTER_PATH_PREFIX = "/plexintel/api/posters"

        response = pipe.pipe(
            "Show me top 2 movie recommendations for me",
            body={"user": {"email": "unknown@example.com"}},
        )

        self.assertIn(
            "![Poster for Arrival](https://lumina-ai.kabolly.com/plexintel/api/posters/101?w=180)",
            response,
        )

    def test_exact_openwebui_identity_match_selects_user(self):
        pipe = FakePipeline()

        response = pipe.pipe(
            "Show me top 1 recommendation for me",
            body={"user": {"name": "Jason"}},
        )

        self.assertIn("**User:** `jmnovak (Jason)`", response)
        self.assertIn(("GET", "/api/agent/recommendations", {"user": "jmnovak", "limit": 1}), pipe.calls)

    def test_gemma_narration_cannot_replace_deterministic_items(self):
        class GemmaPipeline(FakePipeline):
            def _ollama_post(self, path, payload):
                self.calls.append(("POST", path, payload))
                return {
                    "message": {
                        "content": "# Ignore order\n1. Wrong Title\nThese fit your mood."
                    }
                }

        pipe = GemmaPipeline()
        pipe.valves.USER_ALIASES_JSON = '{"unknown@example.com": "jmnovak"}'
        pipe.valves.ENABLE_GEMMA_NARRATION = True

        response = pipe.pipe(
            "Show me recommendations for me",
            body={"user": {"email": "unknown@example.com"}},
        )

        self.assertIn("1. **Arrival**", response)
        self.assertIn("2. **Severance**", response)
        self.assertIn("## Gemma Notes", response)
        self.assertIn("Wrong Title", response)
        self.assertLess(response.index("1. **Arrival**"), response.index("## Gemma Notes"))
        self.assertTrue(any(call[1] == "/api/chat" for call in pipe.calls))

    def test_search_with_posters_renders_stable_markdown(self):
        pipe = FakePipeline()

        response = pipe.pipe("Search library for blade with posters")

        self.assertIn("## PlexIntel Library Search", response)
        self.assertIn("**Query:** `blade`", response)
        self.assertIn("### Posters", response)
        self.assertIn("**Blade Runner 2049** (2017)", response)
        self.assertTrue(any(call[1] == "/api/agent/search" for call in pipe.calls))
        self.assertTrue(any(call[1] == "/api/agent/poster-gallery" for call in pipe.calls))

    def test_watch_history_for_named_user_renders_rows(self):
        pipe = FakePipeline()

        response = pipe.pipe("Show watch history for Jason limit 1")

        self.assertIn("## PlexIntel Watch History", response)
        self.assertIn("**Scope:** `jmnovak`", response)
        self.assertIn("**Heat**", response)
        self.assertIn(("GET", "/api/agent/watch-history", {"limit": 1, "user": "jmnovak"}), pipe.calls)

    def test_list_users_workflow_renders_users(self):
        pipe = FakePipeline()

        response = pipe.pipe("List Plex users")

        self.assertIn("## PlexIntel Users", response)
        self.assertIn("`jmnovak` (Jason)", response)
        self.assertIn("`other` (Other User)", response)


if __name__ == "__main__":
    unittest.main()
