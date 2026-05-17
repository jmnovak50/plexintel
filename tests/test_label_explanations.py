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
        self.assertIn("GROUP BY el.label", sql)
        self.assertIn("ORDER BY top_labels.max_shap DESC", sql)
        self.assertIn("LIMIT 3", sql)
        self.assertNotIn("abs(si.shap_value)", sql.lower())
        self.assertNotIn("LIMIT 5", sql)


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
        self.assertIn("If fewer than 80% of HIGH examples clearly support", prompt_text)
        self.assertIn("LOW overlap is above 35%", prompt_text)
        self.assertIn("labels that separate HIGH from LOW", prompt_text)
        self.assertIn("return UNCLEAR / MIXED SIGNAL", prompt_text)
        self.assertIn('"coverage_high_count": 0', prompt_text)
        self.assertIn('"coverage_low_overlap_count": 0', prompt_text)
        self.assertIn('"coverage_low_overlap_percent": 0', prompt_text)
        self.assertIn('"label_confidence": "high, medium, low, or unclear"', prompt_text)
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


if __name__ == "__main__":
    unittest.main()
