from __future__ import annotations

import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
