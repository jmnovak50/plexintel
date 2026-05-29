import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

import score_model


def rec(rating_key, media_type, probability, show_rating_key=None):
    return {
        "rating_key": rating_key,
        "media_type": media_type,
        "predicted_probability": probability,
        "show_rating_key": show_rating_key,
    }


class ShapTargetingTests(unittest.TestCase):
    def test_per_media_targeting_includes_top_movies_when_episodes_rank_higher(self):
        df = pd.DataFrame(
            [
                rec(1, "episode", 0.99, 10),
                rec(2, "episode", 0.98, 20),
                rec(101, "movie", 0.61),
                rec(102, "movie", 0.60),
                rec(103, "movie", 0.59),
            ]
        )

        selected, summary = score_model.select_shap_target_rows(
            df,
            strategy="per_media_type",
            movie_limit=2,
            tv_limit=0,
            overall_limit=0,
        )

        self.assertEqual(set(selected["rating_key"]), {101, 102})
        self.assertEqual(summary["source_counts"]["movie"], 2)

    def test_per_media_targeting_includes_top_displayed_tv_shows(self):
        df = pd.DataFrame(
            [
                rec(11, "episode", 0.91, 100),
                rec(12, "episode", 0.50, 100),
                rec(21, "episode", 0.86, 200),
                rec(22, "episode", 0.40, 200),
                rec(31, "episode", 0.71, 300),
            ]
        )

        selected, summary = score_model.select_shap_target_rows(
            df,
            strategy="per_media_type",
            movie_limit=0,
            tv_limit=2,
            overall_limit=0,
        )

        self.assertEqual(set(selected["rating_key"]), {11, 21})
        self.assertEqual(summary["source_counts"]["show"], 2)
        self.assertEqual(summary["tv_display_level"], "show")

    def test_deduplicates_rows_that_also_qualify_for_overall_catch_all(self):
        df = pd.DataFrame([rec(101, "movie", 0.99)])

        selected, summary = score_model.select_shap_target_rows(
            df,
            strategy="per_media_type",
            movie_limit=1,
            tv_limit=0,
            overall_limit=1,
        )

        self.assertEqual(selected["rating_key"].tolist(), [101])
        self.assertEqual(summary["source_counts"]["movie"], 1)
        self.assertEqual(summary["source_counts"]["overall/additional catch-all"], 0)
        self.assertEqual(summary["deduped_total"], 1)

    def test_global_strategy_matches_legacy_top_overall_selection(self):
        df = pd.DataFrame(
            [
                rec(1, "episode", 0.20, 10),
                rec(2, "movie", 0.95),
                rec(3, "episode", 0.70, 20),
            ]
        )

        selected, summary = score_model.select_shap_target_rows(
            df,
            strategy="global",
            global_limit=2,
        )

        self.assertEqual(selected["rating_key"].tolist(), [2, 3])
        self.assertEqual(summary["strategy"], "global")
        self.assertEqual(summary["source_counts"]["overall/global"], 2)

    def test_targeting_does_not_mutate_scored_recommendation_values(self):
        df = pd.DataFrame(
            [
                rec(1, "episode", 0.99, 10),
                rec(2, "movie", 0.75),
                rec(3, "movie", 0.70),
            ]
        )
        before = df.copy(deep=True)

        selected, _summary = score_model.select_shap_target_rows(
            df,
            strategy="per_media_type",
            movie_limit=1,
            tv_limit=1,
            overall_limit=0,
        )

        assert_frame_equal(df, before)
        selected_scores = dict(zip(selected["rating_key"], selected["predicted_probability"]))
        self.assertEqual(selected_scores[1], 0.99)
        self.assertEqual(selected_scores[2], 0.75)


if __name__ == "__main__":
    unittest.main()
