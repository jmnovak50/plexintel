from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ActorCastOrderTests(unittest.TestCase):
    def test_migration_adds_cast_order_and_updates_actor_views(self):
        sql = read_repo_file("db_update_actor_cast_order.sql")

        self.assertIn("ADD COLUMN IF NOT EXISTS cast_order integer", sql)
        self.assertIn(
            "string_agg(a.name, ', '::text ORDER BY ma.cast_order NULLS LAST, a.name) AS actors",
            sql,
        )
        self.assertIn(
            "array_agg(ac.name ORDER BY ma.cast_order NULLS LAST, ac.name) AS actors_arr_raw",
            sql,
        )
        self.assertIn(
            "string_agg(ac.name, ', '::text ORDER BY ma.cast_order NULLS LAST, ac.name) AS actors",
            sql,
        )

    def test_cast_order_completion_preserves_membership_and_known_orders(self):
        from unittest.mock import patch
        from api.services import metadata_ingestion as metadata
        before = dict(rating_key=1, title='Fixture', media_type='movie',
                      plex_guid='plex://movie/fixture', actors=[
                          dict(id=7, name='Alice', cast_order=None),
                          dict(id=9, name='Bob', cast_order=5)])
        raw = dict(rating_key=1, media_type='movie', guid='plex://movie/fixture',
                   actors=['Alice', 'Not a member', 'Bob'])
        with patch.object(metadata, 'snapshot', return_value=before), patch.object(metadata, 'ingestion_status', return_value={'accepted': False}):
            plan = metadata.cast_order_plan(None, 1, raw, operator='fixture', reason='Missing order')
        self.assertEqual(plan['mode'], 'complete')
        self.assertEqual(plan['relationships'], {'actors': {'action': 'orders', 'values': [dict(id=7, cast_order=0)]}})
        self.assertEqual(plan['fields'], {})

    def test_actor_aggregations_are_ordered_in_runtime_queries(self):
        expected_actor_order = "ORDER BY ma.cast_order NULLS LAST, a.name"
        for relative_path in (
            "fetch_tautulli_data.py",
            "gpt_utils.py",
            "build_training_data.py",
            "score_model.py",
            "create.sql",
            "db_update_positive_recommendation_labels.sql",
            "db_update_poster_views.sql",
            "db_update_tv_rollups.sql",
        ):
            with self.subTest(path=relative_path):
                self.assertIn(expected_actor_order, read_repo_file(relative_path))

    def test_labeling_fallback_queries_order_cast_before_prompt_cap(self):
        source = read_repo_file("gpt_utils.py")

        self.assertGreaterEqual(
            source.count("STRING_AGG(a.name, ', ' ORDER BY ma.cast_order NULLS LAST, a.name)"),
            1,  # Media-only labeling no longer fetches user training watches.
        )
        self.assertIn("_split_tags(row.get(\"actor_tags\", row.get(\"actors\", \"\")), MAX_CAST_NAMES)", source)


if __name__ == "__main__":
    unittest.main()
