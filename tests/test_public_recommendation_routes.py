from __future__ import annotations

import unittest
from unittest.mock import patch

from api.routes import public_recommendation_routes


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return {"count": 0}

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.closed = False

    def cursor(self, *_, **__):
        return self.cursor_obj

    def close(self):
        self.closed = True


class PublicRecommendationRouteTests(unittest.TestCase):
    def test_public_recommendations_filter_suppressing_feedback(self):
        conn = FakeConnection()

        with patch.object(public_recommendation_routes, "connect_db", return_value=conn):
            response = public_recommendation_routes.fetch_recommendations(
                "jmnovak",
                genre="Action",
                media_type="movie",
                score_threshold=0.70,
                page=2,
                page_size=10,
            )

        self.assertEqual(response["total_results"], 0)
        count_sql, count_params = conn.cursor_obj.executed[0]
        data_sql, data_params = conn.cursor_obj.executed[1]
        for sql in (count_sql, data_sql):
            self.assertIn("WITH latest_feedback AS", sql)
            self.assertIn("LEFT JOIN latest_feedback", sql)
            self.assertIn("WHEN lf.feedback = 'interested' THEN FALSE", sql)
            self.assertIn("ELSE COALESCE(lf.suppress, FALSE)", sql)

        self.assertEqual(count_params, ("jmnovak", "jmnovak", "%Action%", "movie", 0.70))
        self.assertEqual(data_params, ("jmnovak", "jmnovak", "%Action%", "movie", 0.70, 10, 10))


if __name__ == "__main__":
    unittest.main()
