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


if __name__ == "__main__":
    unittest.main()
