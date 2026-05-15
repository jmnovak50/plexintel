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

    def test_ingestion_enumerates_and_upserts_cast_order(self):
        source = read_repo_file("fetch_tautulli_data.py")

        self.assertIn("INSERT INTO media_actors (media_id, actor_id, cast_order)", source)
        self.assertIn("ON CONFLICT (media_id, actor_id) DO UPDATE SET", source)
        self.assertIn("cast_order = EXCLUDED.cast_order", source)
        self.assertIn("for cast_order, actor in enumerate(actors):", source)
        self.assertIn('"backfill_cast_order"', source)

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
            2,
        )
        self.assertIn("_split_tags(row.get(\"actor_tags\", row.get(\"actors\", \"\")), MAX_CAST_NAMES)", source)


if __name__ == "__main__":
    unittest.main()
