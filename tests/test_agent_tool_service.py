from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException

from api.services import agent_tool_service


class FakeCursor:
    def __init__(self, fetch_rows=None):
        self.fetch_rows = list(fetch_rows or [])
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))

    def fetchall(self):
        return list(self.fetch_rows)

    def fetchone(self):
        return self.fetch_rows[0] if self.fetch_rows else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, fetch_rows=None):
        self.cursor_obj = FakeCursor(fetch_rows=fetch_rows)

    def cursor(self):
        return self.cursor_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class AgentToolServiceTests(unittest.TestCase):
    def test_get_agent_recommendations_maps_rows(self):
        conn = FakeConnection(
            fetch_rows=[
                {
                    "rating_key": 101,
                    "show_title": None,
                    "title": "Arrival",
                    "media_type": "movie",
                    "season_number": None,
                    "episode_number": None,
                    "year": 2016,
                    "genres": "Sci-Fi",
                    "actors": "Amy Adams",
                    "directors": "Denis Villeneuve",
                    "summary": "First contact.",
                    "duration": 116,
                    "rating": "8.0",
                    "added_at": datetime(2026, 3, 1, 12, 0, 0),
                    "predicted_probability": 0.91,
                    "semantic_themes": "linguistics",
                }
            ]
        )

        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            response = agent_tool_service.get_agent_recommendations(
                user="jmnovak",
                media_type="movie",
                min_score=0.5,
                max_score=0.99,
                limit=25,
            )

        self.assertEqual(response.user, "jmnovak")
        self.assertEqual(response.count, 1)
        self.assertEqual(response.items[0].title, "Arrival")
        self.assertEqual(response.items[0].rating, 8.0)
        executed_sql, executed_params = conn.cursor_obj.executed[0]
        self.assertIn("LEFT JOIN latest_feedback", executed_sql)
        self.assertIn("WHEN lf.feedback = 'interested' THEN FALSE", executed_sql)
        self.assertIn("recs.media_type ILIKE %s", executed_sql)
        self.assertIn("recs.predicted_probability >=", executed_sql)
        self.assertIn("recs.predicted_probability <=", executed_sql)
        self.assertEqual(executed_params, ["jmnovak", "jmnovak", "movie", 0.5, 0.99, 25])

    def test_search_agent_library_maps_rows(self):
        conn = FakeConnection(
            fetch_rows=[
                {
                    "rating_key": 42,
                    "media_type": "movie",
                    "show_title": None,
                    "title": "Blade Runner 2049",
                    "summary": "Replicants.",
                    "season_number": None,
                    "episode_number": None,
                    "rating": "7.7",
                    "year": 2017,
                    "duration": 164,
                    "genres": "Sci-Fi",
                    "actors": "Ryan Gosling",
                    "directors": "Denis Villeneuve",
                }
            ]
        )

        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            response = agent_tool_service.search_agent_library(
                q="blade",
                media_type="movie",
                sort_by="year",
                sort_dir="desc",
                limit=5,
            )

        self.assertEqual(response.query, "blade")
        self.assertEqual(response.count, 1)
        self.assertEqual(response.items[0].year, 2017)
        executed_sql, executed_params = conn.cursor_obj.executed[0]
        self.assertIn("ORDER BY year DESC", executed_sql)
        self.assertEqual(executed_params[-2:], ["movie", 5])

    def test_get_agent_library_item_raises_404_when_missing(self):
        conn = FakeConnection(fetch_rows=[])

        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            with self.assertRaises(HTTPException) as raised:
                agent_tool_service.get_agent_library_item(rating_key=404)

        self.assertEqual(raised.exception.status_code, 404)

    def test_get_recent_library_additions_maps_rows(self):
        conn = FakeConnection(
            fetch_rows=[
                {
                    "rating_key": 88,
                    "media_type": "movie",
                    "show_title": None,
                    "title": "Black Bag",
                    "summary": "Spy thriller.",
                    "season_number": None,
                    "episode_number": None,
                    "rating": "7.4",
                    "year": 2025,
                    "duration": 123,
                    "genres": "Thriller",
                    "actors": "Cate Blanchett",
                    "directors": "Steven Soderbergh",
                    "added_at": datetime(2026, 4, 1, 10, 0, 0),
                    "changed_at": datetime(2026, 4, 1, 12, 0, 0),
                }
            ]
        )

        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            response = agent_tool_service.get_recent_library_additions(
                media_type="movie",
                days=7,
                limit=10,
            )

        self.assertEqual(response.media_type, "movie")
        self.assertEqual(response.days, 7)
        self.assertEqual(response.count, 1)
        self.assertEqual(response.items[0].title, "Black Bag")
        self.assertEqual(response.items[0].rating, 7.4)
        executed_sql, executed_params = conn.cursor_obj.executed[0]
        self.assertIn("FROM library_catalog_v", executed_sql)
        self.assertIn("media_type ILIKE %s", executed_sql)
        self.assertIn("COALESCE(added_at, changed_at) >= NOW()", executed_sql)
        self.assertIn("COALESCE(added_at, changed_at) DESC", executed_sql)
        self.assertEqual(executed_params, ["movie", 7, 10])

    def test_get_recent_library_additions_rejects_invalid_days(self):
        with self.assertRaises(HTTPException) as raised:
            agent_tool_service.get_recent_library_additions(days=0)

        self.assertEqual(raised.exception.status_code, 400)

    def test_list_agent_users_maps_rows(self):
        conn = FakeConnection(
            fetch_rows=[
                {"username": "jmnovak", "friendly_name": "Jason"},
                {"username": "plexfan", "friendly_name": None},
            ]
        )

        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            response = agent_tool_service.list_agent_users(username="j", limit=10)

        self.assertEqual(response.count, 2)
        self.assertEqual(response.items[0].friendly_name, "Jason")
        executed_sql, executed_params = conn.cursor_obj.executed[0]
        self.assertIn("username ILIKE %s", executed_sql)
        self.assertEqual(executed_params, ["%j%", 10])

    def test_get_agent_watch_history_maps_rows(self):
        conn = FakeConnection(
            fetch_rows=[
                {
                    "watch_id": 1,
                    "username": "jmnovak",
                    "friendly_name": "Jason",
                    "rating_key": 777,
                    "watched_at": datetime(2026, 3, 2, 8, 30, 0),
                    "played_duration": 3500,
                    "media_duration": 4000,
                    "percent_complete": 0.875,
                    "engaged": True,
                    "media_type": "movie",
                    "show_title": None,
                    "title": "Heat",
                    "summary": "Crime drama",
                    "season_number": None,
                    "episode_number": None,
                    "rating": "8.4",
                    "year": 1995,
                    "genres": "Crime",
                    "actors": "Al Pacino",
                    "directors": "Michael Mann",
                }
            ]
        )

        with patch.object(agent_tool_service, "connect_db", return_value=conn):
            response = agent_tool_service.get_agent_watch_history(
                user="jmnovak",
                limit=20,
                engaged_only=True,
            )

        self.assertEqual(response.count, 1)
        self.assertEqual(response.results[0].rating, 8.4)
        executed_sql, executed_params = conn.cursor_obj.executed[0]
        self.assertIn("username = %s", executed_sql)
        self.assertIn("engaged = TRUE", executed_sql)
        self.assertEqual(executed_params, ["jmnovak", 20])


if __name__ == "__main__":
    unittest.main()
