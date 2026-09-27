from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from api.services import agent_tool_service
from tests.test_agent_tool_service import FakeConnection
from tests.test_openwebui_pipeline import FakePipeline, USERS
from openwebui_pipelines.plexintel_recommendation_pipeline import PipelineHttpError


def event(watch_id, username, title="Heat", rating_key=777, pct=.1, date="2026-09-26T12:00:00", **extra):
    return dict(watch_id=watch_id, username=username, title=title, rating_key=rating_key,
                percent_complete=pct, engaged=pct >= .5, watched_at=date, media_type="movie", **extra)


class HistoryPipeline(FakePipeline):
    def __init__(self):
        super().__init__()
        self.rows = {
            "jmnovak": [
                event(1, "jmnovak", pct=.9, rating=1.0),
                event(2, "jmnovak"),
                event(3, "jmnovak"),
                event(4, "jmnovak", "Arrival", 101, pct=1),
                event(5, "jmnovak", "Old Movie", 102, date="2026-09-01T12:00:00", rating=9.9),
            ],
            "other": [
                event(6, "other", "Spa Weekend", 103),
                event(7, "other", "Arrival", 101, pct=1),
                event(8, "other", "Episode One", 104, show_title="Lanterns"),
            ],
        }
        self.rows["other"][-1]["media_type"] = "episode"
        self.failed_users = set()
        self.overrides = {}

    def _history_now(self):
        return datetime(2026, 9, 27, 12, tzinfo=ZoneInfo("America/Chicago"))

    def _plex_get(self, path, params=None):
        if path == "/api/agent/users":
            self.calls.append(("GET", path, params))
            offset = params.get("offset", 0)
            return {"items": USERS["items"][offset:offset + 1], "next_offset": 1 if offset == 0 else None}
        if path == "/api/agent/watch-history":
            self.calls.append(("GET", path, params))
            user = params["user"]
            if user in self.failed_users:
                raise PipelineHttpError(endpoint=path, status_code=403, detail="access denied")
            if user in self.overrides:
                return self.overrides[user]
            rows = self.rows[user]
            if params["engaged_only"]:
                rows = [row for row in rows if row["engaged"]]
            offset = params["offset"]
            return {"user": user, "results": rows[offset:offset + 2],
                    "next_offset": offset + 2 if len(rows) > offset + 2 else None}
        return super()._plex_get(path, params)


class WatchHistoryRulesTests(unittest.TestCase):
    def history_calls(self, pipe):
        return [call[2] for call in pipe.calls if call[1] == "/api/agent/watch-history"]

    def test_server_wide_examples_route_to_history(self):
        pipe = HistoryPipeline()
        for prompt in (
            "all watch history", "everyone's watch history", "all users", "server-wide history",
            "what has everyone watched?", "what was watched this week?", "who watched Spa Weekend?",
            "has anyone watched Lanterns?", "what is the most watched movie?",
            "what is the most watched show?", "what are people watching?", "who has been active?",
            "most popular by viewing", "most watched over the last 7 days",
            "show all users watch history", "most viewers", "most plays",
        ):
            with self.subTest(prompt=prompt):
                self.assertTrue(pipe._history_is_server_wide(prompt))
                self.assertEqual(pipe._select_workflow(prompt), "watch_history")

    def test_first_person_resolves_explicit_username(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("What have I watched?", body={"user": {"name": "Jason"}})
        self.assertIn("**Scope:** `jmnovak`", result)
        self.assertEqual({call["user"] for call in self.history_calls(pipe)}, {"jmnovak"})
        self.assertTrue(all(call["engaged_only"] is False for call in self.history_calls(pipe)))
        self.assertNotIn("Spa Weekend", result)

    def test_named_user_and_unknown_identity_never_fall_back_to_all_users(self):
        for prompt in ("Show Paul's recent viewing", "What has Ava watched?", "Show my watch history"):
            pipe = HistoryPipeline()
            result = pipe.pipe(prompt)
            self.assertIn("Which Plex user?", result)
            self.assertEqual(self.history_calls(pipe), [])
        pipe = HistoryPipeline()
        result = pipe.pipe("Show me Jason's watch history")
        self.assertIn("**Scope:** `jmnovak`", result)

    def test_all_user_and_history_pages_are_retrieved_before_display_limit(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("all watch history limit 1", body={"user": {"name": "Jason"}})
        calls = self.history_calls(pipe)
        self.assertEqual({c["user"] for c in calls}, {"jmnovak", "other"})
        self.assertEqual([c["offset"] for c in calls if c["user"] == "jmnovak"], [0, 2, 4])
        self.assertIn("8 playback events; 2 unique viewers. Showing 1.", result)
        self.assertIn("2/2 queried successfully", result)

    def test_title_lookup_finds_other_users_partial_play(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("Who watched Spa Weekend even partially?")
        self.assertIn("- `other`: 1 playback events; 0 engaged; 0 completed; 1 partial.", result)
        self.assertNotIn("- `jmnovak`:", result)
        self.assertEqual({c["user"] for c in self.history_calls(pipe)}, {"jmnovak", "other"})

    def test_viewer_lookup_groups_repeat_plays_and_supports_series(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("Who watched Heat?")
        self.assertIn("3 playback events; 1 unique viewers.", result)
        self.assertEqual(result.count("- `jmnovak`:"), 1)
        result = pipe.pipe("Has anyone watched Lanterns?")
        self.assertIn("- `other`:", result)

    def test_rating_key_lookup(self):
        result = HistoryPipeline().pipe("Who watched rating_key 103?")
        self.assertIn("- `other`:", result)
        self.assertNotIn("- `jmnovak`:", result)

    def test_missing_title_reference_clarifies(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("Who watched this even partially?")
        self.assertIn("Which title", result)
        self.assertEqual(self.history_calls(pipe), [])

    def test_dates_filter_after_merge_and_before_ranking(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("most watched movie over the last 7 days")
        self.assertIn("1. **Heat** — 3 playback events; 1 unique viewers", result)
        self.assertIn("2. **Arrival** — 2 playback events; 2 unique viewers", result)
        self.assertNotIn("Old Movie", result)
        self.assertNotIn("Episode One", result)

    def test_unique_viewers_use_distinct_users_not_repeat_plays_or_ratings(self):
        result = HistoryPipeline().pipe("movies with most viewers")
        self.assertIn("1. **Arrival** — 2 playback events; 2 unique viewers", result)
        self.assertIn("Ranked by unique viewers", result)

    def test_completed_and_engaged_are_distinct(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("all watch history completed only")
        self.assertIn("2 playback events; 2 unique viewers", result)
        self.assertNotIn("**Heat**", result)
        self.assertTrue(all(c["engaged_only"] for c in self.history_calls(pipe)))
        result = HistoryPipeline().pipe("all watch history engaged only")
        self.assertIn("**Heat**", result)
        self.assertIn("90% complete (partial)", result)

    def test_failed_user_query_marks_coverage_incomplete(self):
        pipe = HistoryPipeline()
        pipe.failed_users.add("other")
        result = pipe.pipe("Who watched Spa Weekend?")
        self.assertIn("Incomplete coverage", result)
        self.assertIn("1/2 queried successfully", result)
        self.assertIn("No matching playback events in the retrieved data", result)
        self.assertNotIn("No playback events matched this request.", result)

    def test_response_username_is_validated(self):
        pipe = HistoryPipeline()
        pipe.overrides["other"] = {"user": "other", "results": [event(99, "jmnovak", "Wrong User")], "next_offset": None}
        result = pipe.pipe("all watch history")
        self.assertIn("Incomplete coverage", result)
        self.assertIn("did not match", result)
        self.assertNotIn("Wrong User", result)

    def test_unpaginated_truncated_response_is_not_complete(self):
        pipe = HistoryPipeline()
        pipe.overrides["other"] = {"user": "other", "results": [event(i, "other") for i in range(200)]}
        result = pipe.pipe("all watch history")
        self.assertIn("Incomplete coverage", result)
        self.assertIn("may be truncated", result)

    def test_empty_user_history_is_successful_coverage(self):
        pipe = HistoryPipeline()
        pipe.rows["other"] = []
        result = pipe.pipe("Who watched Missing Title?")
        self.assertIn("2/2 queried successfully", result)
        self.assertIn("No playback events matched this request.", result)

    def test_repeated_page_events_are_not_double_counted(self):
        pipe = HistoryPipeline()
        pipe.rows["jmnovak"] = [event(1, "jmnovak")] * 3
        result = pipe.pipe("Who watched Heat?")
        self.assertIn("1 playback events; 1 unique viewers", result)

    def test_date_windows_use_configured_timezone_and_end_exclusive(self):
        pipe = HistoryPipeline()
        for prompt, start, end in (
            ("all watch history this week", "2026-09-21T00:00:00-05:00", "2026-09-27T12:00:00-05:00"),
            ("all watch history last week", "2026-09-14T00:00:00-05:00", "2026-09-21T00:00:00-05:00"),
            ("all watch history yesterday", "2026-09-26T00:00:00-05:00", "2026-09-27T00:00:00-05:00"),
            ("all watch history on 2026-09-26", "2026-09-26T00:00:00-05:00", "2026-09-27T00:00:00-05:00"),
            ("all watch history between 2026-09-25 and 2026-09-26", "2026-09-25T00:00:00-05:00", "2026-09-27T00:00:00-05:00"),
        ):
            with self.subTest(prompt=prompt):
                lower, upper, _ = pipe._history_window(prompt)
                self.assertEqual(lower.isoformat(), start)
                self.assertEqual(upper.isoformat(), end)

    def test_series_rankings_combine_episode_events(self):
        pipe = HistoryPipeline()
        pipe.rows["jmnovak"] += [dict(event(9, "jmnovak", "Episode Two", 105, show_title="Lanterns"), media_type="episode")]
        result = pipe.pipe("most watched show")
        self.assertIn("1. **Lanterns** — 2 playback events; 2 unique viewers", result)

    def test_title_with_temporal_word_is_not_a_date_window(self):
        pipe = HistoryPipeline()
        pipe.rows["other"] = [event(99, "other", "The Last of Us")]
        result = pipe.pipe("Who watched The Last of Us?")
        self.assertIn("- `other`:", result)

    def test_title_words_do_not_become_filters(self):
        for title in ("Yesterday", "Engaged", "This Month"):
            pipe = HistoryPipeline()
            pipe.rows["other"] = [event(99, "other", title, date="2026-01-01T12:00:00")]
            result = pipe.pipe(f'Who watched "{title}"?')
            self.assertIn("- `other`:", result)
            self.assertIn("all available history", result)
            self.assertTrue(all(not c["engaged_only"] for c in self.history_calls(pipe)))

    def test_completed_only_does_not_include_partial_when_excluding_partial(self):
        result = HistoryPipeline().pipe("all watch history completed only, no partial plays")
        self.assertIn("2 playback events; 2 unique viewers", result)
        self.assertNotIn("**Heat**", result)

    def test_iso_timestamp_bounds_preserve_offsets(self):
        pipe = HistoryPipeline()
        start, end, _ = pipe._history_window(
            "all watch history from 2026-09-26T10:00:00-05:00 to 2026-09-26T18:00:00Z"
        )
        self.assertEqual(start.isoformat(), "2026-09-26T10:00:00-05:00")
        self.assertEqual(end.isoformat(), "2026-09-26T18:00:00+00:00")
        self.assertIn("No playback events matched", pipe.pipe(
            "all watch history since 2026-09-26T18:00:00Z"
        ))

    def test_highest_rated_uses_metadata_search_and_popular_explains_measures(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("highest rated movies")
        search = next(c[2] for c in pipe.calls if c[1] == "/api/agent/search")
        self.assertEqual(search["sort_by"], "rating")
        self.assertIn("Ranked by metadata rating", result)
        self.assertEqual(self.history_calls(pipe), [])
        self.assertIn("most unique viewers", pipe.pipe("popular movies"))


class HistoryPaginationTests(unittest.TestCase):
    def test_user_page_exposes_next_offset_without_extra_row(self):
        conn = FakeConnection([{"username": "a", "friendly_name": None}, {"username": "b", "friendly_name": None}])
        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            page = agent_tool_service.list_agent_users(limit=1, offset=5)
        self.assertEqual([u.username for u in page.items], ["a"])
        self.assertEqual(page.next_offset, 6)
        self.assertEqual(conn.cursor_obj.executed[0][1], [2, 5])

    def test_history_page_retains_partial_and_has_deterministic_order(self):
        fields = {"friendly_name": None, "played_duration": None, "media_duration": None,
                  "show_title": None, "summary": None, "season_number": None, "episode_number": None,
                  "year": None, "genres": None, "actors": None, "directors": None}
        conn = FakeConnection([dict(event(i, "a"), **fields) for i in (1, 2)])
        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            page = agent_tool_service.get_agent_watch_history(user="a", limit=1, offset=3)
        self.assertEqual(page.count, 1)
        self.assertEqual(page.next_offset, 4)
        self.assertFalse(page.engaged_only)
        self.assertFalse(page.results[0].engaged)
        sql, params = conn.cursor_obj.executed[0]
        self.assertIn("username = %s", sql)
        self.assertNotIn("engaged = TRUE", sql)
        self.assertIn("watched_at DESC NULLS LAST, watch_id DESC", sql)
        self.assertEqual(params, ["a", 2, 3])

    def test_empty_page_finishes_pagination(self):
        with patch.object(agent_tool_service, "connect_db", return_value=FakeConnection()):
            self.assertIsNone(agent_tool_service.get_agent_watch_history(user="a").next_offset)
            self.assertIsNone(agent_tool_service.list_agent_users().next_offset)

    def test_invalid_pagination_is_rejected_before_database_access(self):
        for function in (agent_tool_service.get_agent_watch_history, agent_tool_service.list_agent_users):
            for kwargs in ({"limit": 0}, {"offset": -1}, {"limit": 1001}):
                with self.subTest(function=function.__name__, kwargs=kwargs):
                    with patch.object(agent_tool_service, "connect_db") as connect:
                        with self.assertRaises(HTTPException):
                            function(**kwargs)
                        connect.assert_not_called()

    def test_rating_sort_uses_metadata_and_puts_missing_values_last(self):
        conn = FakeConnection()
        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            agent_tool_service.search_agent_library(q="", sort_by="rating", sort_dir="desc")
        self.assertIn("ORDER BY rating DESC NULLS LAST", conn.cursor_obj.executed[0][0])

class HistoryRouteTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.routes import agent_tools
        self.routes = agent_tools
        app = FastAPI()
        app.include_router(agent_tools.router, prefix="/api/agent")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_history_pagination_and_partial_default_reach_service(self):
        payload = agent_tool_service.WatchHistoryResponse(
            user="other", engaged_only=False, count=0, results=[], next_offset=400,
        )
        with patch.object(self.routes, "get_agent_watch_history", return_value=payload) as history:
            response = self.client.get("/api/agent/watch-history", params={"user": "other", "offset": 200})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["next_offset"], 400)
        history.assert_called_once_with(
            user="other", limit=50, engaged_only=False, offset=200,
            since=None, until=None, include_metadata=False,
        )

    def test_users_pagination_reaches_service(self):
        payload = agent_tool_service.AgentUsersResponse(count=0, items=[], next_offset=None)
        with patch.object(self.routes, "list_agent_users", return_value=payload) as users:
            response = self.client.get("/api/agent/users", params={"offset": 1000, "limit": 1000})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["next_offset"])
        users.assert_called_once_with(username=None, friendly_name=None, limit=1000, offset=1000)

    def test_negative_offset_is_rejected(self):
        with patch.object(self.routes, "get_agent_watch_history") as history:
            response = self.client.get("/api/agent/watch-history", params={"user": "other", "offset": -1})
        self.assertEqual(response.status_code, 422)
        history.assert_not_called()

    def test_metadata_rating_sort_is_accepted_by_rest_api(self):
        payload = agent_tool_service.LibrarySearchResponse(query="", count=0, items=[])
        with patch.object(self.routes, "search_agent_library", return_value=payload) as search:
            response = self.client.get("/api/agent/search", params={"q": "", "sort_by": "rating", "sort_dir": "desc"})
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with(q="", media_type=None, sort_by="rating", sort_dir="desc", limit=20)
