from __future__ import annotations

import csv
import unittest
import io
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

try:
    import pgvector.psycopg2  # noqa: F401
except ModuleNotFoundError:
    pgvector_module = types.ModuleType("pgvector")
    pgvector_psycopg2_module = types.ModuleType("pgvector.psycopg2")
    pgvector_psycopg2_module.register_vector = lambda _conn: None
    sys.modules.setdefault("pgvector", pgvector_module)
    sys.modules.setdefault("pgvector.psycopg2", pgvector_psycopg2_module)

try:
    import openai  # noqa: F401
except ModuleNotFoundError:
    openai_module = types.ModuleType("openai")
    openai_module.OpenAI = object
    sys.modules.setdefault("openai", openai_module)

import batch_label_embeddings
import gpt_utils
import label_embeddings


def coverage_candidate(
    dimension: int,
    username: str,
    rating_key: int,
    shap_value: float = 1.0,
    predicted_probability: float = 1.0,
    combined_score: float = 0.0,
) -> dict:
    return {
        "dimension": dimension,
        "username": username,
        "rating_key": rating_key,
        "shap_value": shap_value,
        "predicted_probability": predicted_probability,
        "usage_count": 1,
        "sum_abs_shap": abs(shap_value),
        "avg_abs_shap": abs(shap_value),
        "combined_score": combined_score,
        "user_count": 1,
        "stats_source": "aggregate",
    }


def select_positive_labels(shap_rows: list[tuple[int, float]], labels_by_dimension: dict[int, str]) -> str:
    label_scores: dict[str, float] = {}
    for dimension, shap_value in shap_rows:
        if shap_value <= 0:
            continue
        label = labels_by_dimension.get(dimension)
        if not label:
            continue
        label_scores[label] = max(label_scores.get(label, shap_value), shap_value)

    ranked = sorted(label_scores.items(), key=lambda item: item[1], reverse=True)
    return ", ".join(label for label, _score in ranked[:3])


class DimensionRoutingTests(unittest.TestCase):
    def test_media_dimensions_use_media_embedding_indexes(self):
        with patch.object(gpt_utils, "_get_ranked_embedding_ids", return_value=[101]) as mock_ranked:
            self.assertEqual(gpt_utils.get_top_media_for_dimension(0), [101])
            mock_ranked.assert_called_once_with(
                "media_embeddings",
                "rating_key",
                0,
                top_n=gpt_utils.DEFAULT_FETCH_ITEMS,
                ascending=False,
            )

        with patch.object(gpt_utils, "_get_ranked_embedding_ids", return_value=[202]) as mock_ranked:
            self.assertEqual(gpt_utils.get_bottom_media_for_dimension(767), [202])
            mock_ranked.assert_called_once_with(
                "media_embeddings",
                "rating_key",
                767,
                top_n=gpt_utils.DEFAULT_FETCH_ITEMS,
                ascending=True,
            )

    def test_user_dimensions_use_offset_user_embedding_indexes(self):
        with patch.object(gpt_utils, "_get_ranked_embedding_ids", return_value=["alice"]) as mock_ranked:
            self.assertEqual(gpt_utils.get_top_users_for_dimension(768), ["alice"])
            mock_ranked.assert_called_once_with(
                "user_embeddings",
                "username",
                0,
                top_n=gpt_utils.DEFAULT_FETCH_ITEMS,
                ascending=False,
            )

        with patch.object(gpt_utils, "_get_ranked_embedding_ids", return_value=["bob"]) as mock_ranked:
            self.assertEqual(gpt_utils.get_bottom_users_for_dimension(1535), ["bob"])
            mock_ranked.assert_called_once_with(
                "user_embeddings",
                "username",
                767,
                top_n=gpt_utils.DEFAULT_FETCH_ITEMS,
                ascending=True,
            )

    def test_fetch_dimension_samples_routes_to_correct_scope(self):
        with patch.object(batch_label_embeddings, "get_top_media_for_dimension", return_value=[11]) as top_media:
            with patch.object(batch_label_embeddings, "get_bottom_media_for_dimension", return_value=[12]) as bottom_media:
                with patch.object(batch_label_embeddings, "get_media_metadata", side_effect=["high-media", "low-media"]):
                    mode, positive, negative = batch_label_embeddings._fetch_dimension_samples(0)

        self.assertEqual((mode, positive, negative), ("media", "high-media", "low-media"))
        top_media.assert_called_once_with(0, top_n=batch_label_embeddings.DEFAULT_FETCH_ITEMS)
        bottom_media.assert_called_once_with(0, top_n=batch_label_embeddings.DEFAULT_FETCH_ITEMS)

        with patch.object(label_embeddings, "get_top_users_for_dimension", return_value=["u1"]) as top_users:
            with patch.object(label_embeddings, "get_bottom_users_for_dimension", return_value=["u2"]) as bottom_users:
                with patch.object(label_embeddings, "get_user_watch_history", side_effect=["high-user", "low-user"]):
                    mode, positive, negative = label_embeddings._fetch_dimension_samples(768, top_n=4)

        self.assertEqual((mode, positive, negative), ("user", "high-user", "low-user"))
        top_users.assert_called_once_with(768, top_n=4)
        bottom_users.assert_called_once_with(768, top_n=4)

    def test_batch_dimension_ranges_match_combined_embedding_layout(self):
        self.assertEqual(batch_label_embeddings._get_dimension_range("media"), (0, 768))
        self.assertEqual(batch_label_embeddings._get_dimension_range("user"), (768, 1536))
        self.assertEqual(batch_label_embeddings._get_dimension_range("all"), (0, 1536))

    def test_manual_batch_dimensions_keep_requested_order_and_stats(self):
        with patch.object(
            batch_label_embeddings,
            "get_ranked_dimension_stats",
            return_value=[
                {
                    "dimension": 300,
                    "usage_count": 12,
                    "sum_abs_shap": 4.5,
                    "avg_abs_shap": 0.3,
                    "combined_score": 9.1,
                    "user_count": 5,
                    "stats_source": "aggregate",
                }
            ],
        ):
            stats = batch_label_embeddings.get_dimension_stats_for_dimensions(None, [301, 300])

        self.assertEqual([stat["dimension"] for stat in stats], [301, 300])
        self.assertEqual(stats[0]["stats_source"], "manual")
        self.assertEqual(stats[0]["usage_count"], 0)
        self.assertEqual(stats[1]["stats_source"], "aggregate")
        self.assertEqual(stats[1]["combined_score"], 9.1)


class CoverageSelectionTests(unittest.TestCase):
    def test_existing_explainable_label_excludes_dimension(self):
        saved_label = {
            "label_type": "semantic_candidate",
            "explainable": True,
            "display_label": "space operas",
        }

        self.assertTrue(batch_label_embeddings.is_saved_label_usable_for_explanation(saved_label))
        self.assertEqual(batch_label_embeddings._label_repair_status(saved_label), ("usable_label", "usable_label"))

    def test_hard_structural_label_does_not_falsely_cover_a_recommendation_card(self):
        saved_label = {
            "label_type": "hard_structural",
            "explainable": False,
            "display_label": None,
        }

        self.assertFalse(batch_label_embeddings.is_saved_label_usable_for_explanation(saved_label))
        self.assertEqual(
            batch_label_embeddings._label_repair_status(saved_label),
            ("unusable_label", "not_explainable"),
        )

    def test_weak_label_can_be_selected_for_repair(self):
        saved_label = {
            "label_type": "weak",
            "explainable": False,
            "display_label": None,
            "next_review_at": None,
        }

        self.assertEqual(batch_label_embeddings._label_repair_status(saved_label), ("unusable_label", "weak_label"))
        self.assertTrue(batch_label_embeddings._is_label_review_due(saved_label))

    def test_display_label_null_can_be_selected_for_repair(self):
        saved_label = {
            "label_type": "semantic_candidate",
            "explainable": True,
            "display_label": None,
            "next_review_at": None,
        }

        self.assertEqual(
            batch_label_embeddings._label_repair_status(saved_label),
            ("unusable_label", "missing_display_label"),
        )
        self.assertTrue(batch_label_embeddings._is_label_review_due(saved_label))

    def test_valid_display_label_covers_the_card(self):
        saved_label = {
            "label_type": "semantic_candidate",
            "explainable": True,
            "display_label": "  noir mysteries  ",
        }

        self.assertTrue(batch_label_embeddings.is_saved_label_usable_for_explanation(saved_label))
        self.assertEqual(batch_label_embeddings._label_repair_status(saved_label), ("usable_label", "usable_label"))

    def test_cooldown_prevents_daily_repeat_attempts(self):
        now = datetime(2026, 6, 6, tzinfo=timezone.utc)
        saved_label = {
            "label_type": "weak",
            "explainable": False,
            "display_label": None,
            "next_review_at": now + timedelta(days=1),
        }

        self.assertFalse(batch_label_embeddings._is_label_review_due(saved_label, now=now))

        saved_label["next_review_at"] = now - timedelta(seconds=1)
        self.assertTrue(batch_label_embeddings._is_label_review_due(saved_label, now=now))

    def test_review_eligibility_respects_future_and_elapsed_cooldown(self):
        now = datetime(2026, 6, 6, tzinfo=timezone.utc)
        saved_label = {
            "needs_review": True,
            "next_review_at": now + timedelta(days=7),
        }

        self.assertFalse(batch_label_embeddings.is_review_label_eligible(saved_label, now=now))
        self.assertTrue(
            batch_label_embeddings.is_review_label_eligible(
                saved_label,
                now=now + timedelta(days=7, seconds=1),
            )
        )

        saved_label["needs_review"] = False
        self.assertFalse(
            batch_label_embeddings.is_review_label_eligible(
                saved_label,
                now=now + timedelta(days=7, seconds=1),
            )
        )

    def test_dimension_with_most_unique_unlabeled_recommendations_is_selected_first(self):
        rows = [
            coverage_candidate(10, "alice", 1),
            coverage_candidate(10, "alice", 2),
            coverage_candidate(10, "alice", 3),
            coverage_candidate(11, "alice", 4),
            coverage_candidate(11, "alice", 5),
        ]

        selected, summary = batch_label_embeddings.select_coverage_dimensions(rows, limit=1)

        self.assertEqual([stat["dimension"] for stat in selected], [10])
        self.assertEqual(selected[0]["unlock_count_total"], 3)
        self.assertEqual(selected[0]["marginal_unlock_count"], 3)
        self.assertEqual(summary["eligible_unlabeled_recommendations"], 5)

    def test_overlap_handling_prefers_next_best_marginal_coverage(self):
        rows = [
            coverage_candidate(10, "alice", 1),
            coverage_candidate(10, "alice", 2),
            coverage_candidate(10, "alice", 3),
            coverage_candidate(11, "alice", 1),
            coverage_candidate(11, "alice", 2),
            coverage_candidate(11, "alice", 3),
            coverage_candidate(12, "alice", 4),
            coverage_candidate(12, "alice", 5),
        ]

        selected, summary = batch_label_embeddings.select_coverage_dimensions(rows, limit=2)

        self.assertEqual([stat["dimension"] for stat in selected], [10, 12])
        self.assertEqual(selected[1]["marginal_unlock_count"], 2)
        self.assertEqual(summary["potential_unlocked_recommendations"], 5)

    def test_equal_marginal_coverage_ties_break_by_weighted_unlock_score(self):
        rows = [
            coverage_candidate(10, "alice", 1, shap_value=1.0, predicted_probability=0.2),
            coverage_candidate(11, "alice", 2, shap_value=1.0, predicted_probability=0.9),
        ]

        selected, _summary = batch_label_embeddings.select_coverage_dimensions(rows, limit=1)

        self.assertEqual(selected[0]["dimension"], 11)
        self.assertAlmostEqual(selected[0]["marginal_weighted_unlock_score"], 0.9)

    def test_selection_summary_prints_repair_diagnostics(self):
        selected = [
            {
                "dimension": 10,
                "selection_mode": "coverage",
                "label_repair_status": "unusable_label",
                "selection_reason": "weak_label",
                "marginal_unlock_count": 1,
                "cumulative_unlocked_recommendations": 1,
                "marginal_weighted_unlock_score": 0.5,
                "combined_score": 2.0,
            }
        ]
        summary = {
            "eligible_unlabeled_recommendations": 1,
            "potential_unlocked_recommendations": 1,
            "coverage_diagnostics": {
                "uncovered_recommendation_cards": 2,
                "eligible_missing_dimensions": 3,
                "eligible_unusable_dimensions": 4,
                "cooldown_suppressed_dimensions": 5,
            },
        }
        output = io.StringIO()

        with redirect_stdout(output):
            batch_label_embeddings.print_selection_summary("coverage", selected, summary)

        text = output.getvalue()
        self.assertIn("Recommendation cards with no usable positive-SHAP label: 2", text)
        self.assertIn("Eligible missing dimensions: 3", text)
        self.assertIn("Eligible unusable dimensions: 4", text)
        self.assertIn("Dimensions suppressed by cooldown: 5", text)
        self.assertIn("Selected dimensions by reason: weak_label=1", text)
        self.assertIn("Label Repair Status", text)
        self.assertIn("unusable_label | weak_label", text)

    def test_sql_candidate_query_matches_positive_unlabeled_view_logic(self):
        class FakeCursor:
            def __init__(self):
                self.executed = []

            def execute(self, sql, params=None):
                self.executed.append((sql, params))

            def fetchall(self):
                return []

        cur = FakeCursor()

        batch_label_embeddings.get_coverage_dimension_candidates(cur, dim_type="media")

        sql, params = cur.executed[0]
        self.assertEqual(params, (0, 768))
        self.assertIn("JOIN shap_impact si", sql)
        self.assertIn("LEFT JOIN embedding_labels candidate_label", sql)
        self.assertIn("LEFT JOIN shap_dimension_stats_current s", sql)
        self.assertIn("si.shap_value > 0", sql)
        self.assertIn("candidate_label.dimension IS NULL", sql)
        self.assertIn("candidate_label.label_type = 'weak'", sql)
        self.assertIn("candidate_label.explainable IS NOT TRUE", sql)
        self.assertIn("candidate_label.display_label IS NULL", sql)
        self.assertIn("BTRIM(candidate_label.display_label) = ''", sql)
        self.assertIn("candidate_label.next_review_at <= NOW()", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("JOIN embedding_labels el_existing", sql)
        self.assertIn("el_existing.explainable IS TRUE", sql)
        self.assertIn("el_existing.display_label IS NOT NULL", sql)
        self.assertIn("BTRIM(el_existing.display_label) <> ''", sql)
        self.assertNotIn("el_existing.label IS NOT NULL", sql)

    def test_existing_labeled_dimensions_can_be_excluded_from_coverage_selection(self):
        rows = [
            coverage_candidate(10, "alice", 1),
            coverage_candidate(10, "alice", 2),
            coverage_candidate(11, "alice", 3),
        ]

        selected, _summary = batch_label_embeddings.select_coverage_dimensions(
            rows,
            limit=2,
            excluded_dimensions={10},
        )

        self.assertEqual([stat["dimension"] for stat in selected], [11])

    def test_coverage_refresh_existing_still_uses_unlabeled_coverage_candidates_only(self):
        rows = [
            coverage_candidate(10, "alice", 1),
            coverage_candidate(11, "alice", 2),
        ]

        with patch.object(batch_label_embeddings, "get_coverage_dimension_candidates", return_value=rows):
            with patch.object(batch_label_embeddings, "get_top_dimensions") as top_dimensions:
                selected, summary = batch_label_embeddings.select_automatic_dimensions(
                    None,
                    limit=1,
                    dim_type="all",
                    selection_mode="coverage",
                    include_labeled=True,
                )

        top_dimensions.assert_not_called()
        self.assertEqual([stat["dimension"] for stat in selected], [10])
        self.assertEqual(summary["coverage_selected_count"], 1)

    def test_hybrid_dedupes_dimensions_and_fills_requested_limit(self):
        coverage_rows = [
            coverage_candidate(10, "alice", 1),
            coverage_candidate(20, "alice", 2),
        ]
        importance_rows = [
            {
                "dimension": 10,
                "usage_count": 3,
                "sum_abs_shap": 3.0,
                "avg_abs_shap": 1.0,
                "combined_score": 9.0,
                "user_count": 1,
                "stats_source": "aggregate",
            },
            {
                "dimension": 30,
                "usage_count": 3,
                "sum_abs_shap": 3.0,
                "avg_abs_shap": 1.0,
                "combined_score": 8.0,
                "user_count": 1,
                "stats_source": "aggregate",
            },
        ]

        with patch.object(batch_label_embeddings, "get_coverage_dimension_candidates", return_value=coverage_rows):
            with patch.object(batch_label_embeddings, "get_top_dimensions", return_value=importance_rows):
                selected, summary = batch_label_embeddings.select_automatic_dimensions(
                    None,
                    limit=3,
                    dim_type="all",
                    selection_mode="hybrid",
                    coverage_share=0.50,
                )

        self.assertEqual([stat["dimension"] for stat in selected], [10, 20, 30])
        self.assertEqual(len({stat["dimension"] for stat in selected}), 3)
        self.assertEqual(summary["coverage_selected_count"], 2)
        self.assertEqual(summary["importance_selected_count"], 1)


class ReviewSelectionTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, diagnostics_row=None, candidate_rows=None):
            self.diagnostics_row = diagnostics_row or (0, 0, 0, 0)
            self.candidate_rows = candidate_rows or []
            self.executed = []

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def fetchone(self):
            return self.diagnostics_row

        def fetchall(self):
            return self.candidate_rows

    def test_review_mode_selects_needs_review_rows_ranked_by_shap_activity(self):
        reviewed_at = datetime(2026, 6, 1, 8, 30)
        candidate_rows = [
            (
                12,
                "prestige tv drama episodes",
                "prestige TV drama",
                "soft_structural",
                True,
                True,
                reviewed_at,
                2,
                None,
                10,
                5.0,
                0.5,
                9.0,
                3,
                "review_aggregate",
            )
        ]
        cur = self.FakeCursor(diagnostics_row=(3, 1, 1, 1), candidate_rows=candidate_rows)

        selected, summary = batch_label_embeddings.select_automatic_dimensions(
            cur,
            limit=25,
            dim_type="media",
            selection_mode="review",
        )

        diagnostics_sql, diagnostics_params = cur.executed[0]
        candidate_sql, candidate_params = cur.executed[1]
        self.assertEqual(diagnostics_params, (0, 768))
        self.assertEqual(candidate_params, (0, 768, 25))
        self.assertIn("el.needs_review IS TRUE", diagnostics_sql)
        self.assertIn("el.needs_review IS TRUE", candidate_sql)
        self.assertIn("el.next_review_at <= NOW()", candidate_sql)
        self.assertIn("COALESCE(s.combined_score, 0.0) DESC", candidate_sql)
        self.assertIn("COALESCE(s.sum_abs_shap, 0.0) DESC", candidate_sql)
        self.assertIn("COALESCE(s.usage_count, 0) DESC", candidate_sql)
        self.assertIn("el.dimension ASC", candidate_sql)
        self.assertEqual(summary["selection_mode"], "review")
        self.assertEqual(summary["review_selected_count"], 1)
        self.assertEqual(summary["review_diagnostics"]["total_needing_review"], 3)
        self.assertEqual(selected[0]["dimension"], 12)
        self.assertEqual(selected[0]["side"], "media")
        self.assertEqual(selected[0]["existing_label"], "prestige tv drama episodes")
        self.assertEqual(selected[0]["existing_display_label"], "prestige TV drama")
        self.assertEqual(selected[0]["existing_label_type"], "soft_structural")
        self.assertEqual(selected[0]["usage_count"], 10)
        self.assertEqual(selected[0]["combined_score"], 9.0)
        self.assertEqual(selected[0]["last_reviewed_at"], reviewed_at)
        self.assertEqual(selected[0]["review_attempt_count"], 2)

    def test_review_summary_prints_required_diagnostics_and_selected_rows(self):
        selected = [
            {
                "dimension": 780,
                "selection_mode": "review",
                "side": "user",
                "existing_label": "light-hearted tv episodes",
                "existing_display_label": "light-hearted TV stories",
                "existing_label_type": "soft_structural",
                "usage_count": 7,
                "combined_score": 3.5,
                "last_reviewed_at": datetime(2026, 6, 1, 8, 30),
                "review_attempt_count": 1,
            }
        ]
        summary = {
            "review_diagnostics": {
                "total_needing_review": 4,
                "current_shap_activity": 2,
                "zero_current_shap_activity": 1,
                "cooldown_suppressed_dimensions": 1,
            }
        }
        output = io.StringIO()

        with redirect_stdout(output):
            batch_label_embeddings.print_selection_summary("review", selected, summary)

        text = output.getvalue()
        self.assertIn("Total dimensions needing review: 4", text)
        self.assertIn("Review candidates with current SHAP activity: 2", text)
        self.assertIn("Review candidates with zero current SHAP activity: 1", text)
        self.assertIn("Dimensions suppressed by cooldown: 1", text)
        self.assertIn("Review dimensions skipped because next_review_at is in the future: 1", text)
        self.assertIn("Selected dimensions: 1", text)
        self.assertIn("Existing Raw Label", text)
        self.assertIn("780 | user | light-hearted tv episodes", text)

    def test_governance_classifier_matches_soft_structural_review_rules(self):
        governance = batch_label_embeddings.classify_label_governance("prestige tv drama episodes")

        self.assertEqual(governance["label_type"], "soft_structural")
        self.assertTrue(governance["explainable"])
        self.assertEqual(governance["display_label"], "prestige TV drama")
        self.assertTrue(governance["needs_review"])

        hard_structural = batch_label_embeddings.classify_label_governance("feature films")
        self.assertEqual(hard_structural["label_type"], "hard_structural")
        self.assertFalse(hard_structural["explainable"])
        self.assertIsNone(hard_structural["display_label"])
        self.assertFalse(hard_structural["needs_review"])

        season_structural = batch_label_embeddings.classify_label_governance("season finale titles")
        self.assertEqual(season_structural["label_type"], "soft_structural")
        self.assertTrue(season_structural["needs_review"])

    def test_governance_classifier_reclassifies_dates_and_negative_constructions(self):
        date_label = batch_label_embeddings.classify_label_governance("1990s action releases")
        self.assertEqual(date_label["label_type"], "metadata")
        self.assertFalse(date_label["explainable"])
        self.assertIsNone(date_label["display_label"])
        self.assertFalse(date_label["needs_review"])

        range_label = batch_label_embeddings.classify_label_governance("movies released 1990-1999")
        self.assertEqual(range_label["label_type"], "metadata")
        self.assertFalse(range_label["explainable"])

        negative_label = batch_label_embeddings.classify_label_governance("non-comedy mysteries")
        self.assertEqual(negative_label["label_type"], "semantic_candidate")
        self.assertTrue(negative_label["explainable"])
        self.assertEqual(negative_label["display_label"], "non-comedy mysteries")
        self.assertTrue(negative_label["needs_review"])


class EligibleSelectionTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, diagnostics_row=None, candidate_rows=None):
            self.diagnostics_row = diagnostics_row or (0, 0, 0)
            self.candidate_rows = candidate_rows or []
            self.executed = []

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def fetchone(self):
            return self.diagnostics_row

        def fetchall(self):
            return self.candidate_rows

    @staticmethod
    def _new_row(dimension=100, max_abs_impact=5.0, shap_rows=50):
        return (
            dimension,
            max_abs_impact,
            shap_rows,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            None,
            "new_unlabeled_dimension",
        )

    @staticmethod
    def _review_due_row(dimension=770, max_abs_impact=3.0, shap_rows=20):
        return (
            dimension,
            max_abs_impact,
            shap_rows,
            "light-hearted tv episodes",
            "light-hearted TV stories",
            "soft_structural",
            True,
            True,
            datetime(2026, 6, 1, 8, 30),
            2,
            None,
            "review_due",
        )

    def test_candidate_query_uses_shap_impact_as_driving_source(self):
        cur = self.FakeCursor()

        batch_label_embeddings.get_eligible_dimension_candidates(cur, limit=25, dim_type="all")

        sql, params = cur.executed[0]
        self.assertEqual(params, (0, 1536, 25))
        self.assertIn("WITH active_dims AS", sql)
        self.assertIn("FROM shap_impact si", sql)
        self.assertIn("MAX(ABS(si.shap_value)) AS max_abs_impact", sql)
        self.assertIn("LEFT JOIN embedding_labels el", sql)
        self.assertIn("WHEN el.dimension IS NULL THEN 'new_unlabeled_dimension'", sql)
        self.assertIn("COALESCE(el.needs_review, false) = true", sql)
        self.assertIn("el.next_review_at IS NULL OR el.next_review_at <= now()", sql)
        self.assertIn("ELSE 'not_due'", sql)
        self.assertIn(
            "WHERE candidate_reason IN ('new_unlabeled_dimension', 'review_due')",
            sql,
        )
        self.assertIn("WHEN 'new_unlabeled_dimension' THEN 1", sql)
        self.assertIn("WHEN 'review_due' THEN 2", sql)
        self.assertIn("max_abs_impact DESC", sql)

    def test_media_dim_type_scopes_the_query_range(self):
        cur = self.FakeCursor()

        batch_label_embeddings.get_eligible_dimension_candidates(cur, limit=10, dim_type="media")

        _sql, params = cur.executed[0]
        self.assertEqual(params, (0, 768, 10))

    def test_new_and_review_due_rows_are_classified_and_routed(self):
        candidate_rows = [self._new_row(), self._review_due_row()]
        cur = self.FakeCursor(diagnostics_row=(431, 104, 419), candidate_rows=candidate_rows)

        selected, summary = batch_label_embeddings.select_automatic_dimensions(
            cur,
            limit=25,
            dim_type="all",
            selection_mode="eligible",
        )

        diagnostics_sql, diagnostics_params = cur.executed[0]
        _candidate_sql, candidate_params = cur.executed[1]
        self.assertEqual(diagnostics_params, (0, 1536))
        self.assertIn("COUNT(*) FILTER (WHERE candidate_reason = 'new_unlabeled_dimension')", diagnostics_sql)
        self.assertEqual(candidate_params, (0, 1536, 25))

        self.assertEqual(summary["selection_mode"], "eligible")
        self.assertEqual(summary["eligible_selected_count"], 2)
        self.assertEqual(summary["eligible_new_selected_count"], 1)
        self.assertEqual(summary["eligible_review_selected_count"], 1)
        self.assertEqual(summary["eligible_diagnostics"]["new_unlabeled"], 431)
        self.assertEqual(summary["eligible_diagnostics"]["review_due"], 104)
        self.assertEqual(summary["eligible_diagnostics"]["not_due"], 419)

        new_stat, review_stat = selected
        self.assertEqual(new_stat["dimension"], 100)
        self.assertEqual(new_stat["candidate_reason"], "new_unlabeled_dimension")
        self.assertEqual(new_stat["selection_mode"], "eligible_new")
        self.assertEqual(new_stat["label_repair_status"], "missing_label")
        self.assertIsNone(new_stat["existing_label"])
        self.assertEqual(new_stat["usage_count"], 50)
        self.assertEqual(new_stat["side"], "media")

        self.assertEqual(review_stat["dimension"], 770)
        self.assertEqual(review_stat["candidate_reason"], "review_due")
        self.assertEqual(review_stat["selection_mode"], "review")
        self.assertEqual(review_stat["existing_label"], "light-hearted tv episodes")
        self.assertEqual(review_stat["existing_display_label"], "light-hearted TV stories")
        self.assertEqual(review_stat["existing_label_type"], "soft_structural")
        self.assertEqual(review_stat["review_attempt_count"], 2)
        self.assertEqual(review_stat["side"], "user")

    def test_not_due_dimensions_are_excluded_by_the_candidate_query(self):
        # not_due rows are filtered by the SQL WHERE clause, so the cursor only
        # ever returns new_unlabeled and review_due rows.
        cur = self.FakeCursor(
            diagnostics_row=(0, 0, 419),
            candidate_rows=[],
        )

        selected, summary = batch_label_embeddings.select_eligible_dimensions(
            cur,
            limit=25,
            dim_type="all",
        )

        self.assertEqual(selected, [])
        self.assertEqual(summary["eligible_diagnostics"]["not_due"], 419)
        _candidate_sql, _params = cur.executed[1]
        self.assertNotIn("'not_due'", _candidate_sql.split("WHERE candidate_reason IN")[1])

    def test_eligible_summary_logs_required_counts(self):
        selected = [
            {
                "dimension": 100,
                "selection_mode": "eligible_new",
                "candidate_reason": "new_unlabeled_dimension",
                "side": "media",
                "usage_count": 50,
                "max_abs_impact": 5.0,
                "existing_display_label": None,
            },
            {
                "dimension": 770,
                "selection_mode": "review",
                "candidate_reason": "review_due",
                "side": "user",
                "usage_count": 20,
                "max_abs_impact": 3.0,
                "existing_display_label": "light-hearted TV stories",
            },
        ]
        summary = {
            "eligible_diagnostics": {
                "new_unlabeled": 431,
                "review_due": 104,
                "not_due": 419,
            },
            "eligible_new_selected_count": 1,
            "eligible_review_selected_count": 1,
        }
        output = io.StringIO()

        with redirect_stdout(output):
            batch_label_embeddings.print_selection_summary("eligible", selected, summary)

        text = output.getvalue()
        self.assertIn("New unlabeled candidates: 431", text)
        self.assertIn("Review-due candidates: 104", text)
        self.assertIn("Skipped because not due (labeled or in cooldown): 419", text)
        self.assertIn("Selected dimensions for labeling: 2", text)
        self.assertIn("Selected breakdown: new_unlabeled=1, review_due=1", text)
        self.assertIn("Candidate Reason", text)
        self.assertIn("100 | media | new_unlabeled_dimension", text)
        self.assertIn("770 | user | review_due", text)


class LabelRepairSaveTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, existing_row):
            self.existing_row = existing_row
            self.executed = []

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def fetchone(self):
            return self.existing_row

    def test_invalid_unclear_llm_response_does_not_overwrite_existing_label(self):
        existing_row = (
            42,
            "old structural label",
            "hard_structural",
            False,
            None,
            False,
            None,
            0,
            None,
        )
        cur = self.FakeCursor(existing_row)
        label_result = {
            "label": gpt_utils.UNCLEAR_LABEL,
            "label_type": "unclear",
            "validation_status": "invalid",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            42,
            label_result,
            label_repair_status="unusable_label",
            selection_reason="not_explainable",
            repair_cooldown_days=7,
        )

        self.assertFalse(saved)
        self.assertEqual(status, "repair_cooldown_scheduled")
        executed_sql = "\n".join(sql for sql, _params in cur.executed)
        self.assertIn("review_attempt_count = COALESCE(review_attempt_count, 0) + 1", executed_sql)
        self.assertIn("next_review_at = NOW() + (%s * INTERVAL '1 day')", executed_sql)
        self.assertNotIn("INSERT INTO embedding_label_history", executed_sql)
        self.assertNotIn("label = %s", executed_sql)

    def test_valid_semantic_repair_preserves_old_label_history(self):
        existing_row = (
            84,
            "old weak label",
            "weak",
            False,
            None,
            True,
            None,
            1,
            None,
        )
        cur = self.FakeCursor(existing_row)
        label_result = {
            "label": "spy thrillers",
            "label_type": "semantic",
            "validation_status": "valid",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            84,
            label_result,
            label_repair_status="unusable_label",
            selection_reason="weak_label",
            repair_cooldown_days=7,
        )

        self.assertTrue(saved)
        self.assertEqual(status, "updated_unusable_label")
        executed_sql = "\n".join(sql for sql, _params in cur.executed)
        self.assertIn("INSERT INTO embedding_label_history", executed_sql)
        self.assertIn("old_label", executed_sql)
        self.assertIn("old_needs_review", executed_sql)
        self.assertIn("UPDATE embedding_labels", executed_sql)
        self.assertIn("label = %s", executed_sql)

    def test_save_uses_application_governance_not_llm_proposed_type(self):
        cur = self.FakeCursor(existing_row=None)
        label_result = {
            "label": "movies released 1990-1999",
            "label_type": "semantic",
            "validation_status": "valid",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            122,
            label_result,
            repair_cooldown_days=7,
        )

        self.assertTrue(saved)
        self.assertEqual(status, "inserted_missing_label")
        insert_params = cur.executed[-1][1]
        self.assertEqual(insert_params, (122, "movies released 1990-1999", "metadata", False, None, False))

    def test_valid_review_replacement_updates_existing_usable_label_with_history(self):
        existing_row = (
            120,
            "prestige tv drama episodes",
            "soft_structural",
            True,
            "prestige TV drama",
            True,
            datetime(2026, 6, 1, 8, 30),
            2,
            None,
        )
        cur = self.FakeCursor(existing_row)
        label_result = {
            "label": "prestige drama",
            "label_type": "semantic",
            "validation_status": "valid",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            120,
            label_result,
            label_repair_status="review_label",
            selection_reason="needs_review",
            repair_cooldown_days=7,
            review_mode=True,
        )

        self.assertTrue(saved)
        self.assertEqual(status, "updated_review_label")
        executed_sql = "\n".join(sql for sql, _params in cur.executed)
        self.assertIn("INSERT INTO embedding_label_history", executed_sql)
        self.assertIn("old_needs_review", executed_sql)
        self.assertIn("review_attempt_count = COALESCE(review_attempt_count, 0) + 1", executed_sql)
        update_params = cur.executed[-1][1]
        self.assertEqual(
            update_params,
            ("prestige drama", "semantic_candidate", True, "prestige drama", False, False, 7, 120),
        )
        self.assertIn("ELSE NULL", cur.executed[-1][0])

    def test_valid_review_soft_structural_result_gets_future_next_review_at(self):
        existing_row = (
            122,
            "light-hearted tv episodes",
            "soft_structural",
            True,
            "light-hearted TV stories",
            True,
            datetime(2026, 6, 1, 8, 30),
            2,
            None,
        )
        cur = self.FakeCursor(existing_row)
        label_result = {
            "label": "prestige tv drama episodes",
            "label_type": "semantic",
            "validation_status": "valid",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            122,
            label_result,
            label_repair_status="review_label",
            selection_reason="needs_review",
            repair_cooldown_days=7,
            review_mode=True,
        )

        self.assertTrue(saved)
        self.assertEqual(status, "updated_review_label_cooldown_scheduled")
        update_sql, update_params = cur.executed[-1]
        self.assertIn("next_review_at = CASE", update_sql)
        self.assertIn("NOW() + (%s * INTERVAL '1 day')", update_sql)
        self.assertEqual(
            update_params,
            (
                "prestige tv drama episodes",
                "soft_structural",
                True,
                "prestige TV drama",
                True,
                True,
                7,
                122,
            ),
        )

    def test_downgraded_review_result_gets_future_next_review_at_without_overwrite(self):
        existing_row = (
            123,
            "light-hearted tv episodes",
            "soft_structural",
            True,
            "light-hearted TV stories",
            True,
            datetime(2026, 6, 1, 8, 30),
            2,
            None,
        )
        cur = self.FakeCursor(existing_row)
        label_result = {
            "label": "dominant cluster label",
            "label_type": "cluster",
            "validation_status": "downgraded",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            123,
            label_result,
            label_repair_status="review_label",
            selection_reason="needs_review",
            repair_cooldown_days=7,
            review_mode=True,
        )

        self.assertFalse(saved)
        self.assertEqual(status, "invalid_review_replacement_not_saved")
        executed_sql = "\n".join(sql for sql, _params in cur.executed)
        self.assertIn("review_attempt_count = COALESCE(review_attempt_count, 0) + 1", executed_sql)
        self.assertIn("next_review_at = NOW() + (%s * INTERVAL '1 day')", executed_sql)
        self.assertNotIn("label = %s", executed_sql)

    def test_invalid_review_response_does_not_overwrite_existing_usable_label(self):
        existing_row = (
            121,
            "light-hearted tv episodes",
            "soft_structural",
            True,
            "light-hearted TV stories",
            True,
            datetime(2026, 6, 1, 8, 30),
            2,
            None,
        )
        cur = self.FakeCursor(existing_row)
        label_result = {
            "label": gpt_utils.UNCLEAR_LABEL,
            "label_type": "unclear",
            "validation_status": "invalid",
        }

        saved, status = batch_label_embeddings.save_label_result(
            cur,
            121,
            label_result,
            label_repair_status="review_label",
            selection_reason="needs_review",
            repair_cooldown_days=7,
            review_mode=True,
        )

        self.assertFalse(saved)
        self.assertEqual(status, "repair_cooldown_scheduled")
        executed_sql = "\n".join(sql for sql, _params in cur.executed)
        self.assertIn("next_review_at = NOW() + (%s * INTERVAL '1 day')", executed_sql)
        self.assertNotIn("INSERT INTO embedding_label_history", executed_sql)
        self.assertNotIn("label = %s", executed_sql)

    def test_hybrid_refresh_existing_allows_labeled_dimensions_only_in_importance_portion(self):
        coverage_rows = [
            coverage_candidate(10, "alice", 1),
        ]
        refreshed_importance_row = {
            "dimension": 20,
            "usage_count": 10,
            "sum_abs_shap": 5.0,
            "avg_abs_shap": 0.5,
            "combined_score": 12.0,
            "user_count": 4,
            "stats_source": "aggregate",
        }

        with patch.object(batch_label_embeddings, "get_coverage_dimension_candidates", return_value=coverage_rows):
            with patch.object(
                batch_label_embeddings,
                "get_top_dimensions",
                return_value=[refreshed_importance_row],
            ) as top_dimensions:
                selected, summary = batch_label_embeddings.select_automatic_dimensions(
                    None,
                    limit=2,
                    dim_type="all",
                    selection_mode="hybrid",
                    coverage_share=0.50,
                    include_labeled=True,
                )

        top_dimensions.assert_called_once()
        self.assertTrue(top_dimensions.call_args.kwargs["include_labeled"])
        self.assertEqual([stat["selection_mode"] for stat in selected], ["hybrid_coverage", "hybrid_importance"])
        self.assertEqual([stat["dimension"] for stat in selected], [10, 20])
        self.assertEqual(selected[1]["unlock_count_total"], "")
        self.assertEqual(summary["potential_unlocked_recommendations"], 1)

    def test_importance_refresh_existing_behavior_is_unchanged(self):
        importance_rows = [
            {
                "dimension": 20,
                "usage_count": 10,
                "sum_abs_shap": 5.0,
                "avg_abs_shap": 0.5,
                "combined_score": 12.0,
                "user_count": 4,
                "stats_source": "aggregate",
            }
        ]

        with patch.object(
            batch_label_embeddings,
            "get_top_dimensions",
            return_value=importance_rows,
        ) as top_dimensions:
            selected, summary = batch_label_embeddings.select_automatic_dimensions(
                None,
                limit=1,
                dim_type="all",
                selection_mode="importance",
                include_labeled=True,
            )

        top_dimensions.assert_called_once_with(
            None,
            limit=1,
            dim_type="all",
            include_labeled=True,
        )
        self.assertEqual(selected[0]["dimension"], 20)
        self.assertEqual(selected[0]["selection_mode"], "importance")
        self.assertEqual(summary["importance_selected_count"], 1)


class PositiveLabelSelectionTests(unittest.TestCase):
    def test_positive_label_selection_excludes_negative_dedupes_and_limits(self):
        selected = select_positive_labels(
            [
                (10, -9.0),
                (11, 0.2),
                (12, 0.9),
                (13, 0.4),
                (14, 0.8),
                (15, 0.7),
                (16, 0.6),
            ],
            {
                10: "negative-only",
                11: "duplicate",
                12: "top",
                13: "duplicate",
                14: "second",
                15: "third",
                16: "fourth",
            },
        )

        self.assertEqual(selected, "top, second, third")

    def test_positive_label_migration_uses_positive_ordered_grouped_labels(self):
        sql = Path("db_update_positive_recommendation_labels.sql").read_text(encoding="utf-8")

        self.assertIn("si.shap_value > (0)::double precision", sql)
        self.assertIn("el.explainable IS TRUE", sql)
        self.assertIn("el.display_label IS NOT NULL", sql)
        self.assertIn("BTRIM(el.display_label) <> ''::text", sql)
        self.assertIn("GROUP BY el.display_label", sql)
        self.assertIn("string_agg(top_labels.display_label", sql)
        self.assertIn("ORDER BY top_labels.max_shap DESC", sql)
        self.assertIn("LIMIT 3", sql)
        self.assertNotIn("abs(si.shap_value)", sql.lower())
        self.assertNotIn("LIMIT 5", sql)

    def test_label_governance_migration_adds_diagnostics_and_validation(self):
        sql = Path("sql/add_embedding_label_governance.sql").read_text(encoding="utf-8")

        for column in (
            "ADD COLUMN IF NOT EXISTS label_type text",
            "ADD COLUMN IF NOT EXISTS explainable boolean",
            "ADD COLUMN IF NOT EXISTS display_label text",
            "ADD COLUMN IF NOT EXISTS needs_review boolean DEFAULT false",
            "ADD COLUMN IF NOT EXISTS updated_at timestamp without time zone DEFAULT now()",
            "ADD COLUMN IF NOT EXISTS last_reviewed_at timestamp without time zone",
            "ADD COLUMN IF NOT EXISTS review_attempt_count integer NOT NULL DEFAULT 0",
            "ADD COLUMN IF NOT EXISTS next_review_at timestamp without time zone",
        ):
            self.assertIn(column, sql)

        self.assertIn("CREATE TABLE IF NOT EXISTS public.embedding_label_history", sql)
        self.assertIn("old_label text", sql)
        self.assertIn("old_needs_review boolean", sql)
        self.assertIn("old_review_attempt_count integer", sql)
        self.assertIn("new_label text", sql)
        self.assertIn("CREATE OR REPLACE VIEW public.embedding_label_governance_v", sql)
        self.assertIn("LEFT JOIN public.shap_impact si ON si.dimension = el.dimension", sql)
        self.assertIn("WHEN el.dimension < 768 THEN 'media'::text", sql)
        self.assertIn("ELSE 'user'::text", sql)
        self.assertIn("GROUP BY label_type, side, explainable, needs_review", sql)
        self.assertIn("el.explainable IS TRUE", sql)
        self.assertIn("el.display_label IS NOT NULL", sql)
        self.assertIn("BTRIM(el.display_label) <> ''::text", sql)


class LabelCoveragePromptTests(unittest.TestCase):
    def test_prompt_includes_configured_coverage_gate_and_json_fields(self):
        positive_df = pd.DataFrame(
            [
                {"title": "Spy One", "year": 2001, "media_type": "movie", "genre_tags": "Action, Spy"},
                {"title": "Spy Two", "year": 2002, "media_type": "movie", "genre_tags": "Action, Spy"},
                {"title": "Spy Three", "year": 2003, "media_type": "movie", "genre_tags": "Action, Spy"},
            ]
        )
        negative_df = pd.DataFrame(
            [
                {"title": "Quiet Drama", "year": 2004, "media_type": "movie", "genre_tags": "Drama"},
                {"title": "Slow Romance", "year": 2005, "media_type": "movie", "genre_tags": "Romance"},
            ]
        )

        prompt_bundle = gpt_utils.build_dimension_prompt(
            12,
            positive_df,
            negative_df,
            min_valid_items=1,
            minimum_label_coverage_percent=80,
            maximum_low_overlap_percent=35,
        )
        prompt_text = prompt_bundle["prompt_text"]

        self.assertIn("Minimum Label Coverage Percent = 80", prompt_text)
        self.assertIn("Maximum Low Overlap Percent = 35", prompt_text)
        self.assertIn("Find the strongest reusable semantic separator", prompt_text)
        self.assertIn("plot hints reveal a stronger common concept", prompt_text)
        self.assertIn("Prefer concrete story/entity labels", prompt_text)
        self.assertIn("Good labels are compact evidence-derived noun phrases", prompt_text)
        self.assertIn("Never copy wording from these instructions", prompt_text)
        self.assertIn("choose the narrower nuance", prompt_text)
        self.assertIn("If fewer than 80% of HIGH examples clearly support", prompt_text)
        self.assertIn("LOW overlap is above 35%", prompt_text)
        self.assertIn("labels that separate HIGH from LOW", prompt_text)
        self.assertIn("return UNCLEAR / MIXED SIGNAL", prompt_text)
        self.assertIn('"coverage_high_count": 0', prompt_text)
        self.assertIn('"coverage_low_overlap_count": 0', prompt_text)
        self.assertIn('"coverage_low_overlap_percent": 0', prompt_text)
        self.assertIn('"label_confidence": "high, medium, low, or unclear"', prompt_text)
        self.assertIn('"proposed_label_type": "semantic, cluster, mechanical, or unclear"', prompt_text)
        self.assertNotIn("cyborg / modified-human identity", gpt_utils.SYSTEM_PROMPT)
        self.assertNotIn("cyborg / modified-human identity", prompt_text)
        self.assertEqual(prompt_bundle["minimum_label_coverage_percent"], 80)
        self.assertEqual(prompt_bundle["maximum_low_overlap_percent"], 35)

    def test_review_prompt_includes_existing_governance_without_forcing_replacement(self):
        positive_df = pd.DataFrame(
            [
                {"title": "Spy One", "year": 2001, "media_type": "movie", "genre_tags": "Action, Spy"},
                {"title": "Spy Two", "year": 2002, "media_type": "movie", "genre_tags": "Action, Spy"},
                {"title": "Spy Three", "year": 2003, "media_type": "movie", "genre_tags": "Action, Spy"},
            ]
        )
        negative_df = pd.DataFrame(
            [
                {"title": "Quiet Drama", "year": 2004, "media_type": "movie", "genre_tags": "Drama"},
                {"title": "Slow Romance", "year": 2005, "media_type": "movie", "genre_tags": "Romance"},
            ]
        )

        prompt_bundle = gpt_utils.build_dimension_prompt(
            12,
            positive_df,
            negative_df,
            min_valid_items=1,
            existing_label="prestige tv drama episodes",
            existing_display_label="prestige TV drama",
            existing_label_type="soft_structural",
        )
        prompt_text = prompt_bundle["prompt_text"]

        self.assertIn("Existing label: prestige tv drama episodes", prompt_text)
        self.assertIn("Existing display label: prestige TV drama", prompt_text)
        self.assertIn("Existing label type: soft_structural", prompt_text)
        self.assertIn("Re-evaluate the existing label using only the current HIGH/LOW evidence.", prompt_text)
        self.assertIn("The HIGH/LOW examples are the source of truth", prompt_text)
        self.assertIn("Do not preserve the existing wording unless the evidence independently supports it.", prompt_text)
        self.assertIn("UNCLEAR / MIXED SIGNAL remains a valid outcome.", prompt_text)
        self.assertIn("Do not force a replacement merely because this row is in review mode.", prompt_text)

    def test_json_label_response_normalizes_coverage_fields(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "spy action movies",
              "label_confidence": "medium",
              "proposed_label_type": "semantic",
              "coverage_high_count": 7,
              "coverage_high_total": 10,
              "coverage_low_overlap_count": 2,
              "coverage_low_total": 8,
              "coverage_low_overlap_percent": 25,
              "explanation": "Most high examples are spy action movies while low examples are not.",
              "evidence": ["Spy titles repeat", "Action genre repeats", "LOW examples are dramas"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["label"], "spy action movies")
        self.assertEqual(result["label_confidence"], "medium")
        self.assertEqual(result["label_type"], "semantic")
        self.assertEqual(result["proposed_label_type"], "semantic")
        self.assertEqual(result["coverage_high_count"], 7)
        self.assertEqual(result["coverage_high_total"], 10)
        self.assertEqual(result["coverage_high_percent"], 70)
        self.assertEqual(result["coverage_low_overlap_count"], 2)
        self.assertEqual(result["coverage_low_total"], 8)
        self.assertEqual(result["coverage_low_overlap_percent"], 25)
        self.assertEqual(result["validation_status"], "valid")

    def test_low_overlap_above_fifty_invalidates_broad_label(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "Comedy genre",
              "label_confidence": "high",
              "label_type": "semantic",
              "coverage_high_count": 5,
              "coverage_high_total": 6,
              "coverage_low_overlap_count": 3,
              "coverage_low_total": 4,
              "explanation": "Most high examples are comedies.",
              "evidence": ["Comedy appears repeatedly", "Genres mention comedy", "LOW examples overlap"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["coverage_high_percent"], 83)
        self.assertEqual(result["coverage_low_overlap_percent"], 75)
        self.assertEqual(result["label"], gpt_utils.UNCLEAR_LABEL)
        self.assertEqual(result["label_confidence"], "unclear")
        self.assertEqual(result["label_type"], "unclear")
        self.assertEqual(result["validation_status"], "invalid")
        self.assertIn("LOW-side overlap was 75%", " ".join(result["validation_notes"]))

    def test_low_overlap_above_threshold_downgrades_high_confidence(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "crime comedies",
              "label_confidence": "high",
              "label_type": "semantic",
              "coverage_high_count": 5,
              "coverage_high_total": 6,
              "coverage_low_overlap_count": 2,
              "coverage_low_total": 5,
              "explanation": "High examples are mostly crime comedies.",
              "evidence": ["Crime repeats", "Comedy repeats", "LOW overlap exists"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["coverage_low_overlap_percent"], 40)
        self.assertEqual(result["label"], "crime comedies")
        self.assertEqual(result["label_confidence"], "high")
        self.assertEqual(result["validation_status"], "valid")

        stricter = gpt_utils.validate_label_result(
            result,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=35,
        )

        self.assertEqual(stricter["label"], "crime comedies")
        self.assertEqual(stricter["label_confidence"], "medium")
        self.assertEqual(stricter["validation_status"], "downgraded")

    def test_missing_coverage_fields_are_marked_for_review(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "spy action movies",
              "label_confidence": "medium",
              "label_type": "semantic",
              "explanation": "The high examples seem similar.",
              "evidence": ["Spy title", "Action metadata", "LOW contrast unclear"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["label"], "spy action movies")
        self.assertEqual(result["validation_status"], "needs_review")
        self.assertIn("HIGH coverage percent was missing", " ".join(result["validation_notes"]))
        self.assertIn("LOW overlap percent was missing", " ".join(result["validation_notes"]))

    def test_low_high_coverage_invalidates_broad_label(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "prestige dramas",
              "label_confidence": "medium",
              "label_type": "semantic",
              "coverage_high_count": 3,
              "coverage_high_total": 6,
              "coverage_low_overlap_count": 0,
              "coverage_low_total": 4,
              "explanation": "Some high examples are dramas.",
              "evidence": ["Drama appears", "Only some HIGH examples match", "LOW examples do not overlap"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["coverage_high_percent"], 50)
        self.assertEqual(result["label"], gpt_utils.UNCLEAR_LABEL)
        self.assertEqual(result["label_confidence"], "unclear")
        self.assertEqual(result["validation_status"], "invalid")
        self.assertIn("HIGH coverage was 50%", " ".join(result["validation_notes"]))

    def test_near_threshold_dominant_cluster_is_kept_low_confidence(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "modified-human identity",
              "label_confidence": "medium",
              "label_type": "semantic",
              "coverage_high_count": 4,
              "coverage_high_total": 6,
              "coverage_low_overlap_count": 1,
              "coverage_low_total": 4,
              "explanation": "Most high examples involve modified or artificial beings while low examples mostly do not.",
              "evidence": ["Cyborgs and androids repeat", "One or two HIGH outliers remain", "LOW overlap is limited"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["coverage_high_percent"], 67)
        self.assertEqual(result["coverage_low_overlap_percent"], 25)
        self.assertEqual(result["label"], "modified-human identity")
        self.assertEqual(result["label_confidence"], "low")
        self.assertEqual(result["validation_status"], "downgraded")
        self.assertIn("dominant-cluster label", " ".join(result["validation_notes"]))

    def test_unclear_with_strong_high_and_low_separation_needs_review(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "UNCLEAR / MIXED SIGNAL",
              "label_confidence": "unclear",
              "label_type": "unclear",
              "coverage_high_count": 5,
              "coverage_high_total": 6,
              "coverage_low_overlap_count": 0,
              "coverage_low_total": 4,
              "explanation": "The pattern is unclear.",
              "evidence": ["Some HIGH examples match", "LOW examples do not match", "Review needed"]
            }
            """,
            minimum_label_coverage_percent=70,
            maximum_low_overlap_percent=40,
        )

        self.assertEqual(result["coverage_high_percent"], 83)
        self.assertEqual(result["coverage_low_overlap_percent"], 0)
        self.assertEqual(result["label"], gpt_utils.UNCLEAR_LABEL)
        self.assertEqual(result["validation_status"], "needs_review")
        self.assertIn("Label marked unclear despite meeting HIGH coverage threshold", " ".join(result["validation_notes"]))

    def test_llm_generation_error_includes_root_cause(self):
        with patch.object(gpt_utils, "resolve_label_backend", return_value=("ollama", "example-model")):
            with patch.object(
                gpt_utils,
                "_call_ollama_for_label_result",
                side_effect=RuntimeError("model not found"),
            ):
                with self.assertRaisesRegex(RuntimeError, "model not found"):
                    gpt_utils.call_llm_for_label_result("prompt", max_retries=1)


class ReviewCsvExportTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self):
            self.executed = []
            self.closed = False

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def fetchone(self):
            return None

        def fetchall(self):
            return []

        def close(self):
            self.closed = True

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = ReviewCsvExportTests.FakeCursor()
            self.commits = 0
            self.closed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

        def close(self):
            self.closed = True

    def test_review_dry_run_export_keeps_existing_governance_and_proposals_separate(self):
        reviewed_at = datetime(2026, 6, 1, 8, 30)
        next_review_at = datetime(2026, 6, 10, 8, 30)
        selected = [
            {
                "dimension": 12,
                "selection_mode": "review",
                "label_repair_status": "review_label",
                "selection_reason": "needs_review",
                "existing_label": "prestige tv drama episodes",
                "existing_display_label": "prestige TV drama",
                "existing_label_type": "soft_structural",
                "existing_explainable": True,
                "existing_needs_review": True,
                "last_reviewed_at": reviewed_at,
                "review_attempt_count": 2,
                "next_review_at": next_review_at,
                "usage_count": 10,
                "sum_abs_shap": 5.0,
                "avg_abs_shap": 0.5,
                "combined_score": 9.0,
                "user_count": 3,
                "stats_source": "review_aggregate",
            }
        ]
        prompt_bundle = {
            "prompt_text": "Review context:\nExisting label: prestige tv drama episodes",
            "summary": "summary",
            "skipped_reason": "",
            "valid_positive_count": 6,
            "valid_negative_count": 4,
            "flagged_item_count": 0,
        }
        fake_conn = self.FakeConnection()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "review.csv"
            argv = [
                "batch_label_embeddings.py",
                "--selection_mode",
                "review",
                "--dry_run",
                "--save_label",
                "--export_csv",
                str(csv_path),
            ]
            with patch.object(sys, "argv", argv):
                with patch.object(batch_label_embeddings, "ensure_app_schema"):
                    with patch.object(batch_label_embeddings, "connect_db", return_value=fake_conn):
                        with patch.object(
                            batch_label_embeddings,
                            "select_automatic_dimensions",
                            return_value=(selected, {"review_diagnostics": {}}),
                        ):
                            with patch.object(
                                batch_label_embeddings,
                                "_fetch_dimension_samples",
                                return_value=("media", pd.DataFrame(), pd.DataFrame()),
                            ):
                                with patch.object(
                                    batch_label_embeddings,
                                    "build_dimension_prompt",
                                    return_value=prompt_bundle,
                                ) as build_prompt:
                                    with patch.object(
                                        batch_label_embeddings,
                                        "save_label_result",
                                    ) as save_label:
                                        with patch.object(
                                            batch_label_embeddings,
                                            "call_llm_for_label_result",
                                        ) as call_llm:
                                            with redirect_stdout(io.StringIO()):
                                                batch_label_embeddings.main()

            with csv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        for column in (
            "existing_label",
            "existing_display_label",
            "existing_label_type",
            "existing_explainable",
            "existing_needs_review",
            "last_reviewed_at",
            "review_attempt_count",
            "next_review_at",
            "proposed_label",
            "gpt_label",
            "final_saved_label",
        ):
            self.assertIn(column, row)

        self.assertEqual(row["existing_label"], "prestige tv drama episodes")
        self.assertEqual(row["existing_display_label"], "prestige TV drama")
        self.assertEqual(row["existing_label_type"], "soft_structural")
        self.assertEqual(row["existing_explainable"], "True")
        self.assertEqual(row["existing_needs_review"], "True")
        self.assertEqual(row["last_reviewed_at"], "2026-06-01 08:30:00")
        self.assertEqual(row["review_attempt_count"], "2")
        self.assertEqual(row["next_review_at"], "2026-06-10 08:30:00")
        self.assertEqual(row["proposed_label"], "")
        self.assertEqual(row["gpt_label"], "")
        self.assertEqual(row["final_saved_label"], "")
        self.assertEqual(row["label"], "")
        self.assertEqual(row["label_type"], "")
        self.assertEqual(row["proposed_label_type"], "")
        self.assertEqual(row["final_label_type"], "")
        self.assertEqual(row["final_explainable"], "")
        self.assertEqual(row["final_needs_review"], "")
        self.assertEqual(row["final_display_label"], "")
        self.assertEqual(row["review_cooldown_until"], "")

        build_prompt.assert_called_once()
        self.assertEqual(build_prompt.call_args.kwargs["existing_label"], "prestige tv drama episodes")
        self.assertEqual(build_prompt.call_args.kwargs["existing_display_label"], "prestige TV drama")
        self.assertEqual(build_prompt.call_args.kwargs["existing_label_type"], "soft_structural")
        save_label.assert_not_called()
        call_llm.assert_not_called()
        self.assertEqual(fake_conn.cursor_obj.executed, [])

    def test_csv_exposes_llm_proposed_type_separately_from_final_governance(self):
        selected = [
            {
                "dimension": 12,
                "selection_mode": "review",
                "label_repair_status": "review_label",
                "selection_reason": "needs_review",
                "existing_label": "old comedy label",
                "existing_display_label": "old comedy",
                "existing_label_type": "semantic_candidate",
                "existing_explainable": True,
                "existing_needs_review": True,
                "last_reviewed_at": "",
                "review_attempt_count": 0,
                "next_review_at": "",
                "usage_count": 10,
                "sum_abs_shap": 5.0,
                "avg_abs_shap": 0.5,
                "combined_score": 9.0,
                "user_count": 3,
                "stats_source": "review_aggregate",
            }
        ]
        prompt_bundle = {
            "prompt_text": "prompt",
            "summary": "summary",
            "skipped_reason": "",
            "valid_positive_count": 6,
            "valid_negative_count": 4,
            "flagged_item_count": 0,
        }
        label_result = {
            "label": "non-comedy mysteries",
            "label_confidence": "medium",
            "proposed_label_type": "semantic",
            "label_type": "semantic",
            "validation_status": "valid",
            "validation_notes": [],
            "evidence": ["", "", ""],
        }
        fake_conn = self.FakeConnection()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "review.csv"
            argv = [
                "batch_label_embeddings.py",
                "--selection_mode",
                "review",
                "--label",
                "--export_csv",
                str(csv_path),
            ]
            with patch.object(sys, "argv", argv):
                with patch.object(batch_label_embeddings, "ensure_app_schema"):
                    with patch.object(batch_label_embeddings, "connect_db", return_value=fake_conn):
                        with patch.object(
                            batch_label_embeddings,
                            "resolve_label_backend",
                            return_value=("ollama", "example-model"),
                        ):
                            with patch.object(
                                batch_label_embeddings,
                                "select_automatic_dimensions",
                                return_value=(selected, {"review_diagnostics": {}}),
                            ):
                                with patch.object(
                                    batch_label_embeddings,
                                    "_fetch_dimension_samples",
                                    return_value=("media", pd.DataFrame(), pd.DataFrame()),
                                ):
                                    with patch.object(
                                        batch_label_embeddings,
                                        "build_dimension_prompt",
                                        return_value=prompt_bundle,
                                    ):
                                        with patch.object(
                                            batch_label_embeddings,
                                            "call_llm_for_label_result",
                                            return_value=label_result,
                                        ):
                                            with redirect_stdout(io.StringIO()):
                                                batch_label_embeddings.main()

            with csv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["proposed_label"], "non-comedy mysteries")
        self.assertEqual(row["proposed_label_type"], "semantic")
        self.assertEqual(row["proposed_label_confidence"], "medium")
        self.assertEqual(row["final_label_type"], "semantic_candidate")
        self.assertEqual(row["label_type"], "semantic_candidate")
        self.assertEqual(row["final_explainable"], "True")
        self.assertEqual(row["explainable"], "True")
        self.assertEqual(row["final_needs_review"], "True")
        self.assertEqual(row["needs_review"], "True")
        self.assertEqual(row["final_display_label"], "non-comedy mysteries")
        self.assertEqual(row["display_label"], "non-comedy mysteries")


if __name__ == "__main__":
    unittest.main()
