from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routes import agent_tools
from api.services import agent_tool_service as service
from tests.test_agent_tool_service import FakeConnection
from tests.test_watch_history_rules import HistoryPipeline, event


METADATA_FIELDS = {"summary", "rating", "year", "genres", "actors", "directors"}


def make_history_row(watch_id=1):
    return {
        "watch_id": watch_id,
        "username": "other",
        "friendly_name": "Other User",
        "rating_key": 103,
        "watched_at": datetime(2026, 9, 26, 12),
        "played_duration": 120,
        "media_duration": 2400,
        "percent_complete": .05,
        "engaged": False,
        "media_type": "movie",
        "show_title": None,
        "title": "Spa Weekend",
        "season_number": None,
        "episode_number": None,
        "summary": "large-metadata-sentinel " * 1000,
        "rating": "8.2",
        "year": 2026,
        "genres": "Comedy",
        "actors": "Long cast list " * 500,
        "directors": "Director",
    }


class CompactHistoryServiceTests(unittest.TestCase):
    def test_personal_and_global_history_are_compact_by_default(self):
        for username in ("other", None):
            with self.subTest(user=username):
                conn = FakeConnection([make_history_row()])
                with patch.object(service, "connect_db", return_value=conn):
                    response = service.get_agent_watch_history(user=username)
                payload = response.model_dump(mode="json")
                row = payload["results"][0]
                self.assertTrue(METADATA_FIELDS.isdisjoint(row))
                self.assertEqual(row["title"], "Spa Weekend")
                self.assertEqual(row["watched_at"], "2026-09-26T12:00:00Z")
                self.assertFalse(row["engaged"])
                self.assertNotIn("large-metadata-sentinel", response.model_dump_json())
                self.assertLess(len(response.model_dump_json()), 1000)
                sql, params = conn.cursor_obj.executed[0]
                columns = sql.split("FROM")[0]
                for field in METADATA_FIELDS:
                    self.assertNotIn(field, columns.replace("rating_key", ""))
                self.assertEqual(params, ([username] if username else []) + [51, 0])

    def test_metadata_requires_explicit_opt_in(self):
        conn = FakeConnection([make_history_row()])
        with patch.object(service, "connect_db", return_value=conn):
            response = service.get_agent_watch_history(include_metadata=True)
        row = response.model_dump()["results"][0]
        self.assertTrue(METADATA_FIELDS.issubset(row))
        self.assertEqual(row["rating"], 8.2)
        self.assertIn("large-metadata-sentinel", row["summary"])
        columns = conn.cursor_obj.executed[0][0].split("FROM")[0]
        for field in METADATA_FIELDS:
            self.assertIn(field, columns)

    def test_sql_bounds_are_parameterized_before_pagination_for_both_scopes(self):
        since = datetime.fromisoformat("2026-09-01T00:00:00-05:00")
        until = datetime.fromisoformat("2026-10-01T00:00:00-05:00")
        for username in ("other", None):
            for enriched in (False, True):
                with self.subTest(user=username, include_metadata=enriched):
                    conn = FakeConnection()
                    with patch.object(service, "connect_db", return_value=conn):
                        service.get_agent_watch_history(
                            user=username, since=since, until=until,
                            engaged_only=True, offset=50, include_metadata=enriched,
                        )
                    sql, params = conn.cursor_obj.executed[0]
                    self.assertIn("watched_at >= %s", sql)
                    self.assertIn("watched_at < %s", sql)
                    self.assertIn("engaged = TRUE", sql)
                    self.assertLess(sql.index("watched_at >= %s"), sql.index("ORDER BY"))
                    self.assertLess(sql.index("watched_at < %s"), sql.index("LIMIT"))
                    self.assertNotIn("2026-09", sql)
                    self.assertEqual(params, ([username] if username else []) + [
                        datetime(2026, 9, 1, 5), datetime(2026, 10, 1, 5), 51, 50,
                    ])

    def test_single_bounds_and_naive_utc_are_supported(self):
        bound = datetime(2026, 9, 1)
        for key, comparison in (("since", ">="), ("until", "<")):
            conn = FakeConnection()
            with patch.object(service, "connect_db", return_value=conn):
                service.get_agent_watch_history(**{key: bound})
            sql, params = conn.cursor_obj.executed[0]
            self.assertIn(f"watched_at {comparison} %s", sql)
            self.assertEqual(params, [bound, 51, 0])

    def test_invalid_ranges_and_oversized_limits_fail_before_database_access(self):
        for kwargs in (
            {"since": datetime(2026, 10, 1), "until": datetime(2026, 9, 1)},
            {"since": datetime(2026, 9, 1), "until": datetime(2026, 9, 1, tzinfo=timezone.utc)},
            {"limit": 201},
            {"limit": 201, "include_metadata": True},
        ):
            with self.subTest(kwargs=kwargs), patch.object(service, "connect_db") as connect:
                with self.assertRaises(HTTPException) as raised:
                    service.get_agent_watch_history(**kwargs)
                self.assertEqual(raised.exception.status_code, 400)
                connect.assert_not_called()

    def test_page_size_is_bounded_in_compact_and_enriched_modes(self):
        for enriched in (False, True):
            conn = FakeConnection([make_history_row(i) for i in range(201)])
            with patch.object(service, "connect_db", return_value=conn):
                result = service.get_agent_watch_history(limit=200, include_metadata=enriched)
            self.assertEqual(result.count, 200)
            self.assertEqual(len(result.results), 200)
            self.assertEqual(result.next_offset, 200)
            self.assertEqual(conn.cursor_obj.executed[0][1], [201, 0])


class CompactHistoryHTTPTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(agent_tools.router, prefix="/api/agent")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_global_json_omits_metadata_unless_requested(self):
        for query, enriched in (({}, False), ({"include_metadata": "false"}, False), ({"include_metadata": "true"}, True)):
            with self.subTest(query=query):
                with patch.object(service, "connect_db", return_value=FakeConnection([make_history_row()])):
                    response = self.client.get("/api/agent/watch-history", params=query)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIsNone(payload["user"])
                row = payload["results"][0]
                self.assertEqual(METADATA_FIELDS.issubset(row), enriched)
                if not enriched:
                    self.assertTrue(METADATA_FIELDS.isdisjoint(row))
                    self.assertNotIn("large-metadata-sentinel", response.text)
                self.assertEqual(row["watched_at"], "2026-09-26T12:00:00Z")

    def test_http_date_bounds_reach_sql(self):
        conn = FakeConnection()
        with patch.object(service, "connect_db", return_value=conn):
            response = self.client.get("/api/agent/watch-history", params={
                "user": "other", "since": "2026-09-01T00:00:00-05:00",
                "until": "2026-10-01T00:00:00Z", "offset": 50,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(conn.cursor_obj.executed[0][1], [
            "other", datetime(2026, 9, 1, 5), datetime(2026, 10, 1), 51, 50,
        ])

    def test_http_rejects_invalid_filters_and_limits(self):
        for query, status in (
            ({"since": "not a date"}, 422),
            ({"since": "2026-10-01T00:00:00Z", "until": "2026-09-01T00:00:00Z"}, 400),
            ({"limit": 201}, 422),
            ({"limit": 0}, 422),
            ({"limit": 201, "include_metadata": True}, 422),
        ):
            with self.subTest(query=query), patch.object(service, "connect_db") as connect:
                response = self.client.get("/api/agent/watch-history", params=query)
                self.assertEqual(response.status_code, status)
                connect.assert_not_called()


class CompactHistoryPipelineTests(unittest.TestCase):
    def test_every_user_and_page_receives_identical_sql_bounds(self):
        pipe = HistoryPipeline()
        result = pipe.pipe("all watch history this week")
        self.assertIn("2/2 queried successfully", result)
        calls = [call[2] for call in pipe.calls if call[1] == "/api/agent/watch-history"]
        self.assertEqual({call["user"] for call in calls}, {"jmnovak", "other"})
        self.assertGreater(len(calls), 2)
        for call in calls:
            self.assertEqual(call["since"], "2026-09-21T00:00:00-05:00")
            self.assertEqual(call["until"], "2026-09-27T12:00:00-05:00")
            self.assertEqual(call["limit"], 50)
            self.assertIs(call["include_metadata"], False)

    def test_utc_history_timestamps_are_compared_to_local_calendar_bounds(self):
        pipe = HistoryPipeline()
        pipe.rows["jmnovak"] = []
        pipe.rows["other"] = [
            event(1, "other", "Before Local Monday", date="2026-09-21T03:00:00"),
            event(2, "other", "After Local Monday", date="2026-09-21T06:00:00"),
        ]
        result = pipe.pipe("all watch history this week")
        self.assertNotIn("Before Local Monday", result)
        self.assertIn("After Local Monday", result)
        self.assertEqual(pipe._history_timestamp("2026-09-21T03:00:00").utcoffset().total_seconds(), 0)
