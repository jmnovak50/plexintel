from __future__ import annotations

import unittest
from unittest.mock import patch

from api.routes import recommendation_routes


class RecommendationPagingTests(unittest.TestCase):
    def test_page_rows_uses_limit_plus_one_without_total_count(self):
        rows = [{"rating_key": 1}, {"rating_key": 2}, {"rating_key": 3}]

        page_rows, has_more, next_offset = recommendation_routes._page_rows(rows, limit=2, offset=20)

        self.assertEqual(page_rows, [{"rating_key": 1}, {"rating_key": 2}])
        self.assertTrue(has_more)
        self.assertEqual(next_offset, 22)

    def test_page_rows_marks_last_page(self):
        rows = [{"rating_key": 1}, {"rating_key": 2}]

        page_rows, has_more, next_offset = recommendation_routes._page_rows(rows, limit=2, offset=0)

        self.assertEqual(page_rows, rows)
        self.assertFalse(has_more)
        self.assertIsNone(next_offset)

    def test_order_clause_allowlists_sort_columns(self):
        order_clause = recommendation_routes._build_order_clause(
            ["title:desc", "bad_column:asc", "season_number:sideways"],
        )

        self.assertEqual(
            order_clause,
            " ORDER BY title DESC NULLS LAST, season_number ASC NULLS LAST, "
            "predicted_probability DESC NULLS LAST, rating_key ASC",
        )

    def test_search_filter_escapes_like_wildcards(self):
        params = ["user"]

        sql = recommendation_routes._append_search_filter(
            "SELECT * FROM recs WHERE username = %s",
            params,
            "100% fun_",
            ["title", "genres"],
        )

        self.assertIn("title ILIKE %s ESCAPE E'\\\\'", sql)
        self.assertEqual(params, ["user", "%100\\% fun\\_%", "%100\\% fun\\_%"])

    def test_decorate_rows_resolves_plex_context_once(self):
        rows = [{"rating_key": 1}, {"rating_key": 2}]

        with patch.object(
            recommendation_routes,
            "get_plex_item_url_context",
            return_value={"web_base_url": "https://app.plex.tv/desktop", "server_identifier": "server"},
        ) as mock_context:
            recommendation_routes._decorate_recommendation_rows(rows)

        self.assertEqual(mock_context.call_count, 1)
        self.assertEqual(rows[0]["poster_url"], "/api/posters/1")
        self.assertEqual(
            rows[0]["plex_item_url"],
            "https://app.plex.tv/desktop/#!/server/server/details?key=%2Flibrary%2Fmetadata%2F1",
        )

    def test_feedback_rollup_tracks_suppressing_descendants(self):
        sql = recommendation_routes._feedback_rollup_cte("show_rating_key", "group_rating_key")

        self.assertIn("descendant_feedback_suppress_count", sql)
        self.assertIn("COALESCE(f.suppress, FALSE) = TRUE", sql)
        self.assertIn("visible_recommendation_descendants", sql)
        self.assertIn("FROM public.expanded_recs_w_label_v recs", sql)
        self.assertIn("recs.predicted_probability >= %s", sql)
        self.assertIn("WHEN lf.feedback = 'interested' THEN FALSE", sql)
        self.assertIn("ELSE COALESCE(lf.suppress, FALSE)", sql)

    def test_recommendations_route_treats_interested_as_visible(self):
        class FakeRequest:
            session = {"plex_token": "token"}

        class FakeCursor:
            closed = False

            def __init__(self):
                self.calls = []

            def execute(self, sql, params):
                self.calls.append((sql, params))

            def fetchall(self):
                return []

            def close(self):
                self.closed = True

        class FakeConn:
            closed = False

            def __init__(self):
                self.cursor_obj = FakeCursor()

            def cursor(self, *_, **__):
                return self.cursor_obj

            def close(self):
                self.closed = True

        conn = FakeConn()

        with patch.object(recommendation_routes, "connect_db", return_value=conn):
            with patch.object(recommendation_routes, "register_vector"):
                with patch.object(recommendation_routes, "get_plex_username", return_value="member"):
                    recommendation_routes.get_recommendations(
                        FakeRequest(),
                        view="all",
                        show_rating_key=None,
                        season_rating_key=None,
                        search=None,
                        limit=100,
                        offset=0,
                        sort=None,
                        min_probability=0.70,
                    )

        rec_sql = conn.cursor_obj.calls[0][0]
        self.assertIn("WHEN lf.feedback = 'interested' THEN FALSE", rec_sql)
        self.assertIn("ELSE COALESCE(lf.suppress, FALSE)", rec_sql)
        self.assertIn("END = FALSE", rec_sql)

    def test_show_rollups_require_visible_recommendation_descendants(self):
        class FakeRequest:
            session = {"plex_token": "token"}

        class FakeCursor:
            closed = False

            def __init__(self):
                self.calls = []

            def execute(self, sql, params):
                self.calls.append((sql, params))

            def fetchall(self):
                return []

            def close(self):
                self.closed = True

        class FakeConn:
            closed = False

            def __init__(self):
                self.cursor_obj = FakeCursor()

            def cursor(self, *_, **__):
                return self.cursor_obj

            def close(self):
                self.closed = True

        conn = FakeConn()

        with patch.object(recommendation_routes, "connect_db", return_value=conn):
            with patch.object(recommendation_routes, "register_vector"):
                with patch.object(recommendation_routes, "get_plex_username", return_value="member"):
                    recommendation_routes.get_recommendations(
                        FakeRequest(),
                        view="shows",
                        show_rating_key=None,
                        season_rating_key=None,
                        search=None,
                        limit=100,
                        offset=0,
                        sort=None,
                        min_probability=0.70,
                    )

        rec_sql = conn.cursor_obj.calls[0][0]
        rec_params = conn.cursor_obj.calls[0][1]
        self.assertIn("JOIN visible_recommendation_scored vr", rec_sql)
        self.assertIn("vr.visible_rollup_score AS predicted_probability", rec_sql)
        self.assertIn("COALESCE(vr.visible_recommendation_episode_count, 0)", rec_sql)
        self.assertNotIn("sr.rollup_score >= %s", rec_sql)
        self.assertNotIn(
            "COALESCE(df.descendant_episode_count, 0) > "
            "COALESCE(df.descendant_feedback_suppress_count, 0)",
            rec_sql,
        )
        self.assertEqual(rec_params, ("member", "member", 0.70, "member", 101, 0))

    def test_season_rollups_require_visible_recommendation_descendants(self):
        class FakeRequest:
            session = {"plex_token": "token"}

        class FakeCursor:
            closed = False

            def __init__(self):
                self.calls = []

            def execute(self, sql, params):
                self.calls.append((sql, params))

            def fetchall(self):
                return []

            def close(self):
                self.closed = True

        class FakeConn:
            closed = False

            def __init__(self):
                self.cursor_obj = FakeCursor()

            def cursor(self, *_, **__):
                return self.cursor_obj

            def close(self):
                self.closed = True

        conn = FakeConn()

        with patch.object(recommendation_routes, "connect_db", return_value=conn):
            with patch.object(recommendation_routes, "register_vector"):
                with patch.object(recommendation_routes, "get_plex_username", return_value="member"):
                    recommendation_routes.get_recommendations(
                        FakeRequest(),
                        view="seasons",
                        show_rating_key=15965,
                        season_rating_key=None,
                        search=None,
                        limit=100,
                        offset=0,
                        sort=None,
                        min_probability=0.70,
                    )

        rec_sql = conn.cursor_obj.calls[0][0]
        rec_params = conn.cursor_obj.calls[0][1]
        self.assertIn("JOIN visible_recommendation_scored vr", rec_sql)
        self.assertIn("vr.visible_rollup_score AS predicted_probability", rec_sql)
        self.assertIn("AND vr.group_rating_key = sr.season_rating_key", rec_sql)
        self.assertIn("AND sr.show_rating_key = %s", rec_sql)
        self.assertNotIn("sr.rollup_score >= %s", rec_sql)
        self.assertEqual(rec_params, ("member", "member", 0.70, "member", 15965, 101, 0))


if __name__ == "__main__":
    unittest.main()
