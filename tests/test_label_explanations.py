from __future__ import annotations

import unittest
import sys
import types
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
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("JOIN embedding_labels el_existing", sql)
        self.assertIn("el_existing.label IS NOT NULL", sql)

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
        ):
            self.assertIn(column, sql)

        self.assertIn("CREATE OR REPLACE VIEW public.embedding_label_governance_v", sql)
        self.assertIn("LEFT JOIN public.shap_impact si ON si.dimension = el.dimension", sql)
        self.assertIn("WHEN el.dimension < 768 THEN 'media'::text", sql)
        self.assertIn("ELSE 'user'::text", sql)
        self.assertIn("GROUP BY label_type, side, explainable, needs_review", sql)
        self.assertIn("el.explainable IS TRUE", sql)
        self.assertIn("el.display_label IS NOT NULL", sql)


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
        self.assertNotIn("cyborg / modified-human identity", gpt_utils.SYSTEM_PROMPT)
        self.assertNotIn("cyborg / modified-human identity", prompt_text)
        self.assertEqual(prompt_bundle["minimum_label_coverage_percent"], 80)
        self.assertEqual(prompt_bundle["maximum_low_overlap_percent"], 35)

    def test_json_label_response_normalizes_coverage_fields(self):
        result = gpt_utils._extract_label_result_from_response(
            """
            {
              "label": "spy action movies",
              "label_confidence": "medium",
              "label_type": "semantic",
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


if __name__ == "__main__":
    unittest.main()
