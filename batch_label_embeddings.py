from dotenv import load_dotenv

load_dotenv()

import argparse
import csv
import math
import re
from datetime import datetime, timedelta, timezone

from pgvector.psycopg2 import register_vector

from api.db.connection import connect_db as connect_bootstrap_db
from api.db.schema import ensure_app_schema
from gpt_utils import (
    COMBINED_EMBEDDING_DIMENSIONS,
    DEFAULT_FETCH_ITEMS,
    EMBEDDING_SIDE_DIMENSIONS,
    UNCLEAR_LABEL,
    build_dimension_prompt,
    call_llm_for_label_result,
    get_dimension_mode,
    get_bottom_media_for_dimension,
    get_bottom_users_for_dimension,
    get_media_metadata,
    get_top_media_for_dimension,
    get_top_users_for_dimension,
    get_user_watch_history,
    resolve_label_backend,
)

CSV_FIELDNAMES = [
    "dimension",
    "selection_mode",
    "label_repair_status",
    "selection_reason",
    "existing_label",
    "existing_display_label",
    "existing_label_type",
    "existing_explainable",
    "existing_needs_review",
    "last_reviewed_at",
    "review_attempt_count",
    "next_review_at",
    "unlock_count_total",
    "marginal_unlock_count",
    "marginal_weighted_unlock_score",
    "cumulative_unlocked_recommendations",
    "positive_shap_sum_on_unlabeled",
    "positive_shap_avg_on_unlabeled",
    "mode",
    "summary",
    "prompt_text",
    "label_provider",
    "label_model",
    "proposed_label",
    "proposed_label_confidence",
    "proposed_label_type",
    "gpt_label",
    "final_saved_label",
    "final_label_type",
    "final_explainable",
    "final_needs_review",
    "final_display_label",
    "review_cooldown_until",
    "label",
    "label_confidence",
    "label_type",
    "explainable",
    "needs_review",
    "display_label",
    "coverage_high_count",
    "coverage_high_total",
    "coverage_high_percent",
    "coverage_low_overlap_count",
    "coverage_low_total",
    "coverage_low_overlap_percent",
    "validation_status",
    "validation_notes",
    "label_explanation",
    "label_evidence_1",
    "label_evidence_2",
    "label_evidence_3",
    "valid_positive_count",
    "valid_negative_count",
    "flagged_item_count",
    "skipped_reason",
    "usage_count",
    "sum_abs_shap",
    "avg_abs_shap",
    "combined_score",
    "user_count",
    "stats_source",
]

DEFAULT_REPAIR_COOLDOWN_DAYS = 7
USABLE_LABEL_SQL_TEMPLATE = """
{alias}.explainable IS TRUE
AND {alias}.display_label IS NOT NULL
AND BTRIM({alias}.display_label) <> ''
"""
WEAK_LABEL_FRAGMENTS = ("unknown", "unclear", "mixed", "generic")
METADATA_LABEL_FRAGMENTS = ("rating", "released in", "release year", "release years", "recent")
PROPER_NOUN_LABEL_FRAGMENTS = ("friends", "always sunny", "ray donovan", "gossip girl", "icarly")
HARD_STRUCTURAL_LABELS = {
    "tv series episode",
    "tv series episodes",
    "tv episodes",
    "tv episode",
    "television episode",
    "television episodes",
    "television series episodes",
    "feature-length movies",
    "feature length movies",
    "feature films",
    "feature film preference",
    "feature-film movies",
    "standalone feature films",
    "single tv episode",
    "single television episode",
    "single-episode installments",
    "single-episode tv installments",
    "individual tv episode",
    "individual tv episode titles",
    "individual tv episode releases",
    "runtime over 45 minutes",
    "runtime at least 110 minutes",
    "under-130-minute runtimes",
    "movies longer than two hours",
    "feature films longer than two hours",
    "episodes under 45 minutes",
    "sub-hour tv episodes",
    "short-form episodes under 30 minutes",
    "standard sitcom runtime (≈20-35 min)",
    "titles with colon subtitle",
    "titles with colon subtitles",
    "titles without a colon subtitle",
    "single-word titles",
    "single-word title movies",
    "colon-separated episode subtitles",
    "colon titles with verb-oriented subtitle",
}
SOFT_STRUCTURAL_RE = re.compile(
    r"(^|[^a-z0-9])(episode|episodes|season|seasons|tv|television|movie|movies|film|films|title|titles)([^a-z0-9]|$)"
)
YEAR_LANGUAGE_RE = re.compile(
    r"(?<!\d)(?:18|19|20)\d{2}s?(?!\d)|\b(?:release|released|premiere|premiered|aired|airing)\b"
)
YEAR_RANGE_RE = re.compile(
    r"(?<!\d)(?:18|19|20)\d{2}s?\s*(?:-|–|—|to|through|thru)\s*(?:18|19|20)\d{2}s?(?!\d)"
)
NEGATIVE_SEMANTIC_RE = re.compile(r"(^|[^a-z0-9])non[-\s]+[a-z0-9]+")


def connect_db():
    conn = connect_bootstrap_db()
    register_vector(conn)
    return conn


def _get_dimension_range(dim_type):
    if dim_type == "media":
        return (0, EMBEDDING_SIDE_DIMENSIONS)
    if dim_type == "user":
        return (EMBEDDING_SIDE_DIMENSIONS, COMBINED_EMBEDDING_DIMENSIONS)
    return (0, COMBINED_EMBEDDING_DIMENSIONS)


def _should_persist_label(label: str) -> bool:
    return bool(label and label != UNCLEAR_LABEL)


def _clean_label_text(label: str | None) -> str:
    return re.sub(r"\s+", " ", str(label or "")).strip()


def _contains_any(value: str, fragments: tuple[str, ...]) -> bool:
    return any(fragment in value for fragment in fragments)


def _format_governed_display_label(label: str) -> str | None:
    label_lc = label.lower()
    raw_display_label = label

    if label_lc == "comedy-focused titles":
        raw_display_label = "comedy-focused stories"
    elif label_lc == "high-octane action-thriller titles":
        raw_display_label = "high-octane action thrillers"
    elif label_lc == "prestige tv drama episodes":
        raw_display_label = "prestige TV drama"
    elif label_lc == "episodes centered on real-world social commentary":
        raw_display_label = "real-world social commentary"
    elif label_lc == "light-hearted tv episodes":
        raw_display_label = "light-hearted TV stories"
    elif re.search(r"^episodes centered on .+", label_lc):
        raw_display_label = re.sub(r"^episodes centered on\s+", "", label, flags=re.IGNORECASE).strip()
    elif re.search(r"\s+tv episodes$", label_lc):
        raw_display_label = re.sub(r"\s+tv episodes$", " TV stories", label, flags=re.IGNORECASE).strip()
    elif re.search(r"\s+episodes$", label_lc) and not re.search(r"^episodes?(\s|$)", label_lc):
        raw_display_label = re.sub(r"\s+episodes$", "", label, flags=re.IGNORECASE).strip()
    elif re.search(r"\s+focused titles$", label_lc):
        raw_display_label = re.sub(r"\s+titles$", " stories", label, flags=re.IGNORECASE).strip()
    elif re.search(r"\s+titles$", label_lc):
        raw_display_label = re.sub(r"\s+titles$", "", label, flags=re.IGNORECASE).strip()
    elif re.search(r"\s+movies$", label_lc):
        without_suffix = re.sub(r"\s+movies$", "", label, flags=re.IGNORECASE).strip()
        if re.search(r"\s", without_suffix):
            raw_display_label = without_suffix
    elif re.search(r"\s+films$", label_lc):
        without_suffix = re.sub(r"\s+films$", "", label, flags=re.IGNORECASE).strip()
        if re.search(r"\s", without_suffix):
            raw_display_label = without_suffix

    display_label = re.sub(
        r"(^|[^A-Za-z0-9])tv([^A-Za-z0-9]|$)",
        r"\1TV\2",
        raw_display_label,
        flags=re.IGNORECASE,
    ).strip()
    return display_label or None


def classify_label_governance(label: str) -> dict:
    raw_label = _clean_label_text(label)
    label_lc = raw_label.lower()
    if not raw_label:
        return {
            "label_type": "weak",
            "explainable": False,
            "display_label": None,
            "needs_review": True,
        }

    if _contains_any(label_lc, WEAK_LABEL_FRAGMENTS):
        return {
            "label_type": "weak",
            "explainable": False,
            "display_label": None,
            "needs_review": True,
        }
    if (
        _contains_any(label_lc, METADATA_LABEL_FRAGMENTS)
        or YEAR_RANGE_RE.search(label_lc)
        or YEAR_LANGUAGE_RE.search(label_lc)
    ):
        return {
            "label_type": "metadata",
            "explainable": False,
            "display_label": None,
            "needs_review": False,
        }
    if label_lc in HARD_STRUCTURAL_LABELS:
        return {
            "label_type": "hard_structural",
            "explainable": False,
            "display_label": None,
            "needs_review": False,
        }
    if _contains_any(label_lc, PROPER_NOUN_LABEL_FRAGMENTS):
        return {
            "label_type": "proper_noun",
            "explainable": False,
            "display_label": None,
            "needs_review": False,
        }
    if NEGATIVE_SEMANTIC_RE.search(label_lc):
        return {
            "label_type": "semantic_candidate",
            "explainable": True,
            "display_label": _format_governed_display_label(raw_label),
            "needs_review": True,
        }

    is_soft_structural = bool(SOFT_STRUCTURAL_RE.search(label_lc))
    return {
        "label_type": "soft_structural" if is_soft_structural else "semantic_candidate",
        "explainable": True,
        "display_label": _format_governed_display_label(raw_label),
        "needs_review": is_soft_structural,
    }


def _usable_label_sql(alias: str) -> str:
    return USABLE_LABEL_SQL_TEMPLATE.format(alias=alias).strip()


def is_saved_label_usable_for_explanation(label_row) -> bool:
    if not label_row:
        return False
    if isinstance(label_row, dict):
        explainable = label_row.get("explainable")
        display_label = label_row.get("display_label")
    else:
        explainable = getattr(label_row, "explainable", None)
        display_label = getattr(label_row, "display_label", None)
    return explainable is True and display_label is not None and str(display_label).strip() != ""


def _label_repair_status(label_row) -> tuple[str, str]:
    if not label_row:
        return "missing_label", "missing_label"
    if is_saved_label_usable_for_explanation(label_row):
        return "usable_label", "usable_label"

    if isinstance(label_row, dict):
        label_type = label_row.get("label_type")
        explainable = label_row.get("explainable")
        display_label = label_row.get("display_label")
    else:
        label_type = getattr(label_row, "label_type", None)
        explainable = getattr(label_row, "explainable", None)
        display_label = getattr(label_row, "display_label", None)

    if label_type == "weak":
        return "unusable_label", "weak_label"
    if explainable is not True:
        return "unusable_label", "not_explainable"
    if display_label is None:
        return "unusable_label", "missing_display_label"
    if str(display_label).strip() == "":
        return "unusable_label", "blank_display_label"
    return "unusable_label", "unusable_label"


def _is_label_review_due(label_row, now=None) -> bool:
    if not label_row:
        return True
    next_review_at = (
        label_row.get("next_review_at")
        if isinstance(label_row, dict)
        else getattr(label_row, "next_review_at", None)
    )
    if not next_review_at:
        return True
    now = now or datetime.now(timezone.utc)
    if next_review_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elif next_review_at.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return next_review_at <= now


def is_review_label_eligible(label_row, now=None) -> bool:
    if not label_row:
        return False
    needs_review = (
        label_row.get("needs_review")
        if isinstance(label_row, dict)
        else getattr(label_row, "needs_review", None)
    )
    return needs_review is True and _is_label_review_due(label_row, now=now)


def _blank_coverage_fields(selection_mode: str) -> dict:
    return {
        "selection_mode": selection_mode,
        "label_repair_status": "",
        "selection_reason": "",
        "unlock_count_total": "",
        "marginal_unlock_count": "",
        "marginal_weighted_unlock_score": "",
        "cumulative_unlocked_recommendations": "",
        "positive_shap_sum_on_unlabeled": "",
        "positive_shap_avg_on_unlabeled": "",
    }


def _with_selection_fields(stat: dict, selection_mode: str) -> dict:
    enriched = dict(stat)
    for key, value in _blank_coverage_fields(selection_mode).items():
        enriched.setdefault(key, value)
    return enriched


def get_ranked_dimension_stats(cur):
    """
    Prefer the current-run aggregate SHAP table. Fall back to raw shap_impact counts if the
    aggregate table is missing or empty.
    """
    try:
        cur.execute(
            """
            SELECT
                dimension,
                usage_count,
                sum_abs_shap,
                avg_abs_shap,
                combined_score,
                user_count
            FROM shap_dimension_stats_current
            ORDER BY combined_score DESC, sum_abs_shap DESC, usage_count DESC
            """
        )
        rows = cur.fetchall()
        if rows:
            stats = []
            for dim, usage_count, sum_abs_shap, avg_abs_shap, combined_score, user_count in rows:
                stats.append(
                    {
                        "dimension": dim,
                        "usage_count": int(usage_count or 0),
                        "sum_abs_shap": float(sum_abs_shap or 0.0),
                        "avg_abs_shap": float(avg_abs_shap or 0.0),
                        "combined_score": float(combined_score or 0.0),
                        "user_count": int(user_count or 0),
                        "stats_source": "aggregate",
                    }
                )
            return stats
        print("⚠️ shap_dimension_stats_current is empty; falling back to raw shap_impact counts.")
    except Exception as exc:
        cur.connection.rollback()
        print(f"⚠️ Could not read shap_dimension_stats_current ({exc}); falling back to raw shap_impact counts.")

    cur.execute(
        """
        SELECT dimension, COUNT(*) AS usage_count
        FROM shap_impact
        GROUP BY dimension
        ORDER BY usage_count DESC
        """
    )
    rows = cur.fetchall()
    stats = []
    for dim, usage_count in rows:
        stats.append(
            {
                "dimension": dim,
                "usage_count": int(usage_count or 0),
                "sum_abs_shap": 0.0,
                "avg_abs_shap": 0.0,
                "combined_score": 0.0,
                "user_count": 0,
                "stats_source": "raw_count_fallback",
            }
        )
    return stats


def get_top_dimensions(cur, limit=25, dim_type="media", include_labeled=False):
    cur.execute("SELECT dimension FROM embedding_labels")
    labeled = {row[0] for row in cur.fetchall()}
    dim_min, dim_max = _get_dimension_range(dim_type)

    ranked_stats = get_ranked_dimension_stats(cur)
    filtered = [
        stat for stat in ranked_stats
        if (include_labeled or stat["dimension"] not in labeled)
        and dim_min <= stat["dimension"] < dim_max
    ]
    return filtered[:limit]


def get_top_unlabeled_dimensions(cur, limit=25, dim_type="media"):
    return get_top_dimensions(cur, limit=limit, dim_type=dim_type, include_labeled=False)


def get_dimension_stats_for_dimensions(cur, dimensions: list[int]):
    ranked_stats = {
        stat["dimension"]: stat
        for stat in get_ranked_dimension_stats(cur)
    }
    stats = []
    for dimension in dimensions:
        stats.append(
            ranked_stats.get(
                dimension,
                {
                    "dimension": dimension,
                    "usage_count": 0,
                    "sum_abs_shap": 0.0,
                    "avg_abs_shap": 0.0,
                    "combined_score": 0.0,
                    "user_count": 0,
                    "stats_source": "manual",
                },
            )
        )
    return stats


def get_coverage_dimension_candidates(cur, dim_type="all"):
    dim_min, dim_max = _get_dimension_range(dim_type)
    usable_existing_label_sql = _usable_label_sql("el_existing")
    query = """
        SELECT
            si.dimension,
            r.username,
            r.rating_key,
            si.shap_value,
            r.predicted_probability,
            COALESCE(s.usage_count, 0) AS usage_count,
            COALESCE(s.sum_abs_shap, 0.0) AS sum_abs_shap,
            COALESCE(s.avg_abs_shap, 0.0) AS avg_abs_shap,
            COALESCE(s.combined_score, 0.0) AS combined_score,
            COALESCE(s.user_count, 0) AS user_count,
            CASE
                WHEN s.dimension IS NULL THEN 'coverage'
                ELSE 'aggregate'
            END AS stats_source,
            CASE
                WHEN candidate_label.dimension IS NULL THEN 'missing_label'
                ELSE 'unusable_label'
            END AS label_repair_status,
            CASE
                WHEN candidate_label.dimension IS NULL THEN 'missing_label'
                WHEN candidate_label.label_type = 'weak' THEN 'weak_label'
                WHEN candidate_label.explainable IS NOT TRUE THEN 'not_explainable'
                WHEN candidate_label.display_label IS NULL THEN 'missing_display_label'
                WHEN BTRIM(candidate_label.display_label) = '' THEN 'blank_display_label'
                ELSE 'unusable_label'
            END AS selection_reason
        FROM recommendations r
        JOIN shap_impact si
          ON si.user_id = r.username
         AND si.rating_key = r.rating_key
        LEFT JOIN embedding_labels candidate_label
          ON candidate_label.dimension = si.dimension
        LEFT JOIN shap_dimension_stats_current s
          ON s.dimension = si.dimension
        WHERE si.shap_value > 0
          AND (
              candidate_label.dimension IS NULL
              OR candidate_label.label_type = 'weak'
              OR candidate_label.explainable IS NOT TRUE
              OR candidate_label.display_label IS NULL
              OR BTRIM(candidate_label.display_label) = ''
          )
          AND (
              candidate_label.dimension IS NULL
              OR candidate_label.next_review_at IS NULL
              OR candidate_label.next_review_at <= NOW()
          )
          AND si.dimension >= %s
          AND si.dimension < %s
          AND NOT EXISTS (
              SELECT 1
              FROM shap_impact si_existing
              JOIN embedding_labels el_existing
                ON el_existing.dimension = si_existing.dimension
              WHERE si_existing.user_id = r.username
                AND si_existing.rating_key = r.rating_key
                AND si_existing.shap_value > 0
                AND {usable_existing_label_sql}
          )
        ORDER BY si.dimension ASC, r.username ASC, r.rating_key ASC
    """.format(usable_existing_label_sql=usable_existing_label_sql)
    try:
        cur.execute(query, (dim_min, dim_max))
        return cur.fetchall()
    except Exception as exc:
        if hasattr(cur, "connection"):
            cur.connection.rollback()
        print(
            f"⚠️ Could not read shap_dimension_stats_current during coverage selection ({exc}); "
            "retrying without aggregate scores.",
            flush=True,
        )

    fallback_query = """
        SELECT
            si.dimension,
            r.username,
            r.rating_key,
            si.shap_value,
            r.predicted_probability,
            0 AS usage_count,
            0.0 AS sum_abs_shap,
            0.0 AS avg_abs_shap,
            0.0 AS combined_score,
            0 AS user_count,
            'coverage_raw' AS stats_source,
            CASE
                WHEN candidate_label.dimension IS NULL THEN 'missing_label'
                ELSE 'unusable_label'
            END AS label_repair_status,
            CASE
                WHEN candidate_label.dimension IS NULL THEN 'missing_label'
                WHEN candidate_label.label_type = 'weak' THEN 'weak_label'
                WHEN candidate_label.explainable IS NOT TRUE THEN 'not_explainable'
                WHEN candidate_label.display_label IS NULL THEN 'missing_display_label'
                WHEN BTRIM(candidate_label.display_label) = '' THEN 'blank_display_label'
                ELSE 'unusable_label'
            END AS selection_reason
        FROM recommendations r
        JOIN shap_impact si
          ON si.user_id = r.username
         AND si.rating_key = r.rating_key
        LEFT JOIN embedding_labels candidate_label
          ON candidate_label.dimension = si.dimension
        WHERE si.shap_value > 0
          AND (
              candidate_label.dimension IS NULL
              OR candidate_label.label_type = 'weak'
              OR candidate_label.explainable IS NOT TRUE
              OR candidate_label.display_label IS NULL
              OR BTRIM(candidate_label.display_label) = ''
          )
          AND (
              candidate_label.dimension IS NULL
              OR candidate_label.next_review_at IS NULL
              OR candidate_label.next_review_at <= NOW()
          )
          AND si.dimension >= %s
          AND si.dimension < %s
          AND NOT EXISTS (
              SELECT 1
              FROM shap_impact si_existing
              JOIN embedding_labels el_existing
                ON el_existing.dimension = si_existing.dimension
              WHERE si_existing.user_id = r.username
                AND si_existing.rating_key = r.rating_key
                AND si_existing.shap_value > 0
                AND {usable_existing_label_sql}
          )
        ORDER BY si.dimension ASC, r.username ASC, r.rating_key ASC
    """.format(usable_existing_label_sql=usable_existing_label_sql)
    cur.execute(fallback_query, (dim_min, dim_max))
    return cur.fetchall()


def get_coverage_selection_diagnostics(cur, dim_type="all") -> dict:
    diagnostics = {
        "uncovered_recommendation_cards": 0,
        "eligible_missing_dimensions": 0,
        "eligible_unusable_dimensions": 0,
        "cooldown_suppressed_dimensions": 0,
    }
    if cur is None:
        return diagnostics

    dim_min, dim_max = _get_dimension_range(dim_type)
    usable_existing_label_sql = _usable_label_sql("el_existing")
    query = """
        WITH coverage_candidates AS (
            SELECT DISTINCT
                si.dimension,
                r.username,
                r.rating_key,
                candidate_label.dimension AS saved_dimension,
                CASE
                    WHEN candidate_label.dimension IS NULL THEN 'missing_label'
                    ELSE 'unusable_label'
                END AS label_repair_status,
                (
                    candidate_label.dimension IS NULL
                    OR candidate_label.next_review_at IS NULL
                    OR candidate_label.next_review_at <= NOW()
                ) AS review_due
            FROM recommendations r
            JOIN shap_impact si
              ON si.user_id = r.username
             AND si.rating_key = r.rating_key
            LEFT JOIN embedding_labels candidate_label
              ON candidate_label.dimension = si.dimension
            WHERE si.shap_value > 0
              AND si.dimension >= %s
              AND si.dimension < %s
              AND (
                  candidate_label.dimension IS NULL
                  OR candidate_label.label_type = 'weak'
                  OR candidate_label.explainable IS NOT TRUE
                  OR candidate_label.display_label IS NULL
                  OR BTRIM(candidate_label.display_label) = ''
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM shap_impact si_existing
                  JOIN embedding_labels el_existing
                    ON el_existing.dimension = si_existing.dimension
                  WHERE si_existing.user_id = r.username
                    AND si_existing.rating_key = r.rating_key
                    AND si_existing.shap_value > 0
                    AND {usable_existing_label_sql}
              )
        )
        SELECT
            COUNT(DISTINCT (username, rating_key)) AS uncovered_recommendation_cards,
            COUNT(DISTINCT dimension) FILTER (
                WHERE label_repair_status = 'missing_label'
            ) AS eligible_missing_dimensions,
            COUNT(DISTINCT dimension) FILTER (
                WHERE label_repair_status = 'unusable_label'
                  AND review_due IS TRUE
            ) AS eligible_unusable_dimensions,
            COUNT(DISTINCT dimension) FILTER (
                WHERE label_repair_status = 'unusable_label'
                  AND review_due IS NOT TRUE
            ) AS cooldown_suppressed_dimensions
        FROM coverage_candidates
    """.format(usable_existing_label_sql=usable_existing_label_sql)
    try:
        cur.execute(query, (dim_min, dim_max))
        row = cur.fetchone()
    except Exception as exc:
        if hasattr(cur, "connection"):
            cur.connection.rollback()
        print(f"⚠️ Could not compute coverage diagnostics ({exc}).", flush=True)
        return diagnostics

    if not row:
        return diagnostics
    keys = list(diagnostics)
    return {key: int(value or 0) for key, value in zip(keys, row)}


def _review_row_to_dict(row) -> dict:
    if isinstance(row, dict):
        normalized = dict(row)
    else:
        fields = [
            "dimension",
            "existing_label",
            "existing_display_label",
            "existing_label_type",
            "existing_explainable",
            "existing_needs_review",
            "last_reviewed_at",
            "review_attempt_count",
            "next_review_at",
            "usage_count",
            "sum_abs_shap",
            "avg_abs_shap",
            "combined_score",
            "user_count",
            "stats_source",
        ]
        normalized = dict(zip(fields, row))

    dimension = int(normalized["dimension"])
    existing_needs_review = normalized.get("existing_needs_review", normalized.get("needs_review"))
    normalized.update(
        {
            "dimension": dimension,
            "selection_mode": "review",
            "label_repair_status": "review_label",
            "selection_reason": "needs_review",
            "side": get_dimension_mode(dimension),
            "existing_needs_review": existing_needs_review,
            "needs_review": existing_needs_review,
            "usage_count": int(normalized.get("usage_count") or 0),
            "sum_abs_shap": float(normalized.get("sum_abs_shap") or 0.0),
            "avg_abs_shap": float(normalized.get("avg_abs_shap") or 0.0),
            "combined_score": float(normalized.get("combined_score") or 0.0),
            "user_count": int(normalized.get("user_count") or 0),
            "review_attempt_count": int(normalized.get("review_attempt_count") or 0),
        }
    )
    return _with_selection_fields(normalized, "review")


def get_review_selection_diagnostics(cur, dim_type="all") -> dict:
    diagnostics = {
        "total_needing_review": 0,
        "current_shap_activity": 0,
        "zero_current_shap_activity": 0,
        "cooldown_suppressed_dimensions": 0,
    }
    if cur is None:
        return diagnostics

    dim_min, dim_max = _get_dimension_range(dim_type)
    query = """
        SELECT
            COUNT(*) AS total_needing_review,
            COUNT(*) FILTER (
                WHERE (
                    el.next_review_at IS NULL
                    OR el.next_review_at <= NOW()
                )
                AND COALESCE(s.usage_count, 0) > 0
            ) AS current_shap_activity,
            COUNT(*) FILTER (
                WHERE (
                    el.next_review_at IS NULL
                    OR el.next_review_at <= NOW()
                )
                AND COALESCE(s.usage_count, 0) = 0
            ) AS zero_current_shap_activity,
            COUNT(*) FILTER (
                WHERE el.next_review_at IS NOT NULL
                  AND el.next_review_at > NOW()
            ) AS cooldown_suppressed_dimensions
        FROM embedding_labels el
        LEFT JOIN shap_dimension_stats_current s
          ON s.dimension = el.dimension
        WHERE el.needs_review IS TRUE
          AND el.dimension >= %s
          AND el.dimension < %s
    """
    try:
        cur.execute(query, (dim_min, dim_max))
        row = cur.fetchone()
    except Exception as exc:
        if hasattr(cur, "connection"):
            cur.connection.rollback()
        print(f"⚠️ Could not compute review diagnostics ({exc}).", flush=True)
        return diagnostics

    if not row:
        return diagnostics
    keys = list(diagnostics)
    return {key: int(value or 0) for key, value in zip(keys, row)}


def get_review_dimension_candidates(cur, limit=25, dim_type="all") -> list[dict]:
    dim_min, dim_max = _get_dimension_range(dim_type)
    query = """
        SELECT
            el.dimension,
            el.label AS existing_label,
            el.display_label AS existing_display_label,
            el.label_type AS existing_label_type,
            el.explainable AS existing_explainable,
            el.needs_review AS existing_needs_review,
            el.last_reviewed_at,
            COALESCE(el.review_attempt_count, 0) AS review_attempt_count,
            el.next_review_at,
            COALESCE(s.usage_count, 0) AS usage_count,
            COALESCE(s.sum_abs_shap, 0.0) AS sum_abs_shap,
            COALESCE(s.avg_abs_shap, 0.0) AS avg_abs_shap,
            COALESCE(s.combined_score, 0.0) AS combined_score,
            COALESCE(s.user_count, 0) AS user_count,
            CASE
                WHEN s.dimension IS NULL OR COALESCE(s.usage_count, 0) = 0
                    THEN 'review_zero_activity'
                ELSE 'review_aggregate'
            END AS stats_source
        FROM embedding_labels el
        LEFT JOIN shap_dimension_stats_current s
          ON s.dimension = el.dimension
        WHERE el.needs_review IS TRUE
          AND el.dimension >= %s
          AND el.dimension < %s
          AND (
              el.next_review_at IS NULL
              OR el.next_review_at <= NOW()
          )
        ORDER BY
            COALESCE(s.combined_score, 0.0) DESC,
            COALESCE(s.sum_abs_shap, 0.0) DESC,
            COALESCE(s.usage_count, 0) DESC,
            el.dimension ASC
        LIMIT %s
    """
    cur.execute(query, (dim_min, dim_max, limit))
    return [_review_row_to_dict(row) for row in cur.fetchall()]


def select_review_dimensions(cur, limit=25, dim_type="all") -> tuple[list[dict], dict]:
    diagnostics = get_review_selection_diagnostics(cur, dim_type=dim_type)
    selected = get_review_dimension_candidates(cur, limit=limit, dim_type=dim_type)
    return selected, {
        "selection_mode": "review",
        "review_diagnostics": diagnostics,
        "review_selected_count": len(selected),
    }


def _coverage_row_to_dict(row) -> dict:
    if isinstance(row, dict):
        normalized = dict(row)
        normalized.setdefault("label_repair_status", "missing_label")
        normalized.setdefault("selection_reason", normalized["label_repair_status"])
        return normalized

    fields = [
        "dimension",
        "username",
        "rating_key",
        "shap_value",
        "predicted_probability",
        "usage_count",
        "sum_abs_shap",
        "avg_abs_shap",
        "combined_score",
        "user_count",
        "stats_source",
        "label_repair_status",
        "selection_reason",
    ]
    normalized = dict(zip(fields, row))
    normalized.setdefault("label_repair_status", "missing_label")
    normalized.setdefault("selection_reason", normalized["label_repair_status"])
    return normalized


def _build_coverage_dimension_index(candidate_rows, excluded_dimensions=None):
    excluded_dimensions = set(excluded_dimensions or [])
    dimensions = {}
    eligible_recommendations = set()

    for raw_row in candidate_rows:
        row = _coverage_row_to_dict(raw_row)
        dimension = int(row["dimension"])
        if dimension in excluded_dimensions:
            continue

        shap_value = float(row.get("shap_value") or 0.0)
        if shap_value <= 0:
            continue

        rec_key = (row["username"], int(row["rating_key"]))
        eligible_recommendations.add(rec_key)
        predicted_probability = float(row.get("predicted_probability") or 0.0)

        entry = dimensions.setdefault(
            dimension,
            {
                "dimension": dimension,
                "usage_count": int(row.get("usage_count") or 0),
                "sum_abs_shap": float(row.get("sum_abs_shap") or 0.0),
                "avg_abs_shap": float(row.get("avg_abs_shap") or 0.0),
                "combined_score": float(row.get("combined_score") or 0.0),
                "user_count": int(row.get("user_count") or 0),
                "stats_source": row.get("stats_source") or "coverage",
                "label_repair_status": row.get("label_repair_status") or "missing_label",
                "selection_reason": row.get("selection_reason") or row.get("label_repair_status") or "missing_label",
                "recommendations": {},
            },
        )

        existing = entry["recommendations"].get(rec_key)
        if not existing or shap_value > existing["shap_value"]:
            entry["recommendations"][rec_key] = {
                "shap_value": shap_value,
                "predicted_probability": predicted_probability,
            }

    return dimensions, eligible_recommendations


def _coverage_totals_for_entry(entry: dict) -> dict:
    recommendations = entry["recommendations"]
    unlock_count = len(recommendations)
    positive_shap_sum = sum(rec["shap_value"] for rec in recommendations.values())
    positive_shap_avg = positive_shap_sum / unlock_count if unlock_count else 0.0
    return {
        "unlock_count_total": unlock_count,
        "positive_shap_sum_on_unlabeled": positive_shap_sum,
        "positive_shap_avg_on_unlabeled": positive_shap_avg,
    }


def _public_coverage_stat(entry: dict) -> dict:
    stat = {
        "dimension": entry["dimension"],
        "usage_count": entry["usage_count"],
        "sum_abs_shap": entry["sum_abs_shap"],
        "avg_abs_shap": entry["avg_abs_shap"],
        "combined_score": entry["combined_score"],
        "user_count": entry["user_count"],
        "stats_source": entry["stats_source"],
        "label_repair_status": entry.get("label_repair_status", ""),
        "selection_reason": entry.get("selection_reason", ""),
    }
    stat.update(_coverage_totals_for_entry(entry))
    return stat


def get_coverage_totals_by_dimension(candidate_rows, excluded_dimensions=None) -> tuple[dict, set]:
    dimension_index, eligible_recommendations = _build_coverage_dimension_index(
        candidate_rows,
        excluded_dimensions=excluded_dimensions,
    )
    totals = {
        dimension: _public_coverage_stat(entry)
        for dimension, entry in dimension_index.items()
    }
    return totals, eligible_recommendations


def calculate_potential_unlocked_recommendations(candidate_rows, dimensions) -> int:
    selected_dimensions = set(dimensions)
    unlocked = set()
    for raw_row in candidate_rows:
        row = _coverage_row_to_dict(raw_row)
        if int(row["dimension"]) not in selected_dimensions:
            continue
        shap_value = float(row.get("shap_value") or 0.0)
        if shap_value <= 0:
            continue
        unlocked.add((row["username"], int(row["rating_key"])))
    return len(unlocked)


def select_coverage_dimensions(candidate_rows, limit=25, selection_mode="coverage", excluded_dimensions=None):
    dimension_index, eligible_recommendations = _build_coverage_dimension_index(
        candidate_rows,
        excluded_dimensions=excluded_dimensions,
    )
    remaining_dimensions = set(dimension_index)
    covered_recommendations = set()
    selected = []

    while len(selected) < limit:
        best = None
        for dimension in remaining_dimensions:
            entry = dimension_index[dimension]
            new_keys = set(entry["recommendations"]) - covered_recommendations
            marginal_unlock_count = len(new_keys)
            if marginal_unlock_count <= 0:
                continue

            marginal_weighted_unlock_score = sum(
                entry["recommendations"][key]["shap_value"]
                * entry["recommendations"][key]["predicted_probability"]
                for key in new_keys
            )
            marginal_positive_shap_sum = sum(
                entry["recommendations"][key]["shap_value"]
                for key in new_keys
            )
            sort_key = (
                marginal_unlock_count,
                marginal_weighted_unlock_score,
                marginal_positive_shap_sum,
                entry["combined_score"],
                -dimension,
            )
            if best is None or sort_key > best["sort_key"]:
                best = {
                    "sort_key": sort_key,
                    "dimension": dimension,
                    "new_keys": new_keys,
                    "marginal_unlock_count": marginal_unlock_count,
                    "marginal_weighted_unlock_score": marginal_weighted_unlock_score,
                }

        if best is None:
            break

        dimension = best["dimension"]
        entry = dimension_index[dimension]
        covered_recommendations.update(best["new_keys"])

        stat = _public_coverage_stat(entry)
        stat.update(
            {
                "selection_mode": selection_mode,
                "marginal_unlock_count": best["marginal_unlock_count"],
                "marginal_weighted_unlock_score": best["marginal_weighted_unlock_score"],
                "cumulative_unlocked_recommendations": len(covered_recommendations),
            }
        )
        selected.append(stat)
        remaining_dimensions.remove(dimension)

    summary = {
        "eligible_unlabeled_recommendations": len(eligible_recommendations),
        "potential_unlocked_recommendations": len(covered_recommendations),
    }
    return selected, summary


def _decorate_importance_dimensions(stats, selection_mode="importance", coverage_totals=None):
    coverage_totals = coverage_totals or {}
    decorated = []
    for stat in stats:
        enriched = _with_selection_fields(stat, selection_mode)
        totals = coverage_totals.get(stat["dimension"])
        if totals:
            enriched["unlock_count_total"] = totals["unlock_count_total"]
            enriched["positive_shap_sum_on_unlabeled"] = totals["positive_shap_sum_on_unlabeled"]
            enriched["positive_shap_avg_on_unlabeled"] = totals["positive_shap_avg_on_unlabeled"]
        decorated.append(enriched)
    return decorated


def select_automatic_dimensions(
    cur,
    limit=25,
    dim_type="all",
    selection_mode="importance",
    coverage_share=0.80,
    include_labeled=False,
):
    if selection_mode == "importance":
        selected = get_top_dimensions(
            cur,
            limit=limit,
            dim_type=dim_type,
            include_labeled=include_labeled,
        )
        decorated = _decorate_importance_dimensions(selected, selection_mode="importance")
        return decorated, {
            "selection_mode": "importance",
            "eligible_unlabeled_recommendations": None,
            "potential_unlocked_recommendations": None,
            "coverage_selected_count": 0,
            "importance_selected_count": len(decorated),
        }

    if selection_mode == "review":
        return select_review_dimensions(cur, limit=limit, dim_type=dim_type)

    coverage_diagnostics = get_coverage_selection_diagnostics(cur, dim_type=dim_type)
    coverage_rows = get_coverage_dimension_candidates(cur, dim_type=dim_type)

    if selection_mode == "coverage":
        selected, summary = select_coverage_dimensions(
            coverage_rows,
            limit=limit,
            selection_mode="coverage",
        )
        summary.update(
            {
                "selection_mode": "coverage",
                "coverage_selected_count": len(selected),
                "importance_selected_count": 0,
                "coverage_diagnostics": coverage_diagnostics,
            }
        )
        return selected, summary

    coverage_limit = int(math.floor((limit * coverage_share) + 0.5))
    coverage_limit = max(0, min(limit, coverage_limit))
    coverage_ranked, coverage_summary = select_coverage_dimensions(
        coverage_rows,
        limit=limit,
        selection_mode="hybrid_coverage",
    )
    selected_coverage = coverage_ranked[:coverage_limit]
    selected_dimensions = {stat["dimension"] for stat in selected_coverage}

    importance_slots = limit - len(selected_coverage)
    importance_ranked = get_top_dimensions(
        cur,
        limit=COMBINED_EMBEDDING_DIMENSIONS,
        dim_type=dim_type,
        include_labeled=include_labeled,
    )
    importance_fill = []
    for stat in importance_ranked:
        if stat["dimension"] in selected_dimensions:
            continue
        importance_fill.append(stat)
        selected_dimensions.add(stat["dimension"])
        if len(importance_fill) >= importance_slots:
            break

    selected = list(selected_coverage)
    coverage_totals, eligible_recommendations = get_coverage_totals_by_dimension(coverage_rows)
    selected.extend(
        _decorate_importance_dimensions(
            importance_fill,
            selection_mode="hybrid_importance",
            coverage_totals=coverage_totals,
        )
    )

    if len(selected) < limit:
        for stat in coverage_ranked[coverage_limit:]:
            if stat["dimension"] in selected_dimensions:
                continue
            selected.append(_with_selection_fields(stat, "hybrid_coverage"))
            selected_dimensions.add(stat["dimension"])
            if len(selected) >= limit:
                break

    potential_unlocked = calculate_potential_unlocked_recommendations(
        coverage_rows,
        [stat["dimension"] for stat in selected],
    )
    summary = {
        "selection_mode": "hybrid",
        "eligible_unlabeled_recommendations": len(eligible_recommendations),
        "potential_unlocked_recommendations": potential_unlocked,
        "coverage_selected_count": sum(
            1 for stat in selected if stat.get("selection_mode") == "hybrid_coverage"
        ),
        "importance_selected_count": sum(
            1 for stat in selected if stat.get("selection_mode") == "hybrid_importance"
        ),
        "coverage_greedy_potential_unlocked_recommendations": coverage_summary[
            "potential_unlocked_recommendations"
        ],
        "coverage_diagnostics": coverage_diagnostics,
    }
    return selected, summary


def _format_float(value, digits=4):
    if value == "" or value is None:
        return ""
    return f"{float(value):.{digits}f}"


def print_selection_summary(selection_mode: str, selected_dimensions: list[dict], summary: dict, manual=False):
    if manual:
        print("Selection mode: manual", flush=True)
        print(f"Selected dimensions: {len(selected_dimensions)}", flush=True)
        return

    print(f"Selection mode: {selection_mode}", flush=True)
    if selection_mode == "importance":
        print(f"Selected dimensions: {len(selected_dimensions)}", flush=True)
        print("Ranking source: aggregate/global SHAP importance", flush=True)
        return

    if selection_mode == "review":
        diagnostics = summary.get("review_diagnostics") or {}
        print(
            "Total dimensions needing review: "
            f"{diagnostics.get('total_needing_review', 0)}",
            flush=True,
        )
        print(
            "Review candidates with current SHAP activity: "
            f"{diagnostics.get('current_shap_activity', 0)}",
            flush=True,
        )
        print(
            "Review candidates with zero current SHAP activity: "
            f"{diagnostics.get('zero_current_shap_activity', 0)}",
            flush=True,
        )
        print(
            "Dimensions suppressed by cooldown: "
            f"{diagnostics.get('cooldown_suppressed_dimensions', 0)}",
            flush=True,
        )
        print(
            "Review dimensions skipped because next_review_at is in the future: "
            f"{diagnostics.get('cooldown_suppressed_dimensions', 0)}",
            flush=True,
        )
        print(f"Selected dimensions: {len(selected_dimensions)}", flush=True)
        print(
            "Rank | Dimension | Side | Existing Raw Label | Existing Display Label | "
            "Existing Label Type | SHAP Usage Count | Combined Score | "
            "Last Reviewed At | Review Attempt Count",
            flush=True,
        )
        for rank, stat in enumerate(selected_dimensions, start=1):
            print(
                f"{rank} | {stat['dimension']} | {stat.get('side', '')} | "
                f"{stat.get('existing_label') or ''} | "
                f"{stat.get('existing_display_label') or ''} | "
                f"{stat.get('existing_label_type') or ''} | "
                f"{stat.get('usage_count', 0)} | "
                f"{_format_float(stat.get('combined_score'))} | "
                f"{stat.get('last_reviewed_at') or ''} | "
                f"{stat.get('review_attempt_count', 0)}",
                flush=True,
            )
        return

    eligible = summary.get("eligible_unlabeled_recommendations") or 0
    potential = summary.get("potential_unlocked_recommendations") or 0
    diagnostics = summary.get("coverage_diagnostics") or {}
    print(
        "Recommendation cards with no usable positive-SHAP label: "
        f"{diagnostics.get('uncovered_recommendation_cards', eligible)}",
        flush=True,
    )
    print(
        "Eligible missing dimensions: "
        f"{diagnostics.get('eligible_missing_dimensions', 0)}",
        flush=True,
    )
    print(
        "Eligible unusable dimensions: "
        f"{diagnostics.get('eligible_unusable_dimensions', 0)}",
        flush=True,
    )
    print(
        "Dimensions suppressed by cooldown: "
        f"{diagnostics.get('cooldown_suppressed_dimensions', 0)}",
        flush=True,
    )
    print(f"Currently unlabeled recommendation cards eligible for unlock: {eligible}", flush=True)
    if selection_mode == "hybrid":
        print(f"Coverage-selected dimensions: {summary.get('coverage_selected_count', 0)}", flush=True)
        print(f"Importance-selected dimensions: {summary.get('importance_selected_count', 0)}", flush=True)
        print(
            "Total unique potentially unlocked cards from the entire selected batch: "
            f"{potential}",
            flush=True,
        )
    else:
        print(f"Selected dimensions: {len(selected_dimensions)}", flush=True)
        print(
            "Potential cards unlocked if all selected labels are valid: "
            f"{potential}",
            flush=True,
        )

    if eligible:
        percent = (potential / eligible) * 100
        print(f"Potential coverage improvement: {potential} / {eligible} = {percent:.1f}%", flush=True)
    else:
        print("Potential coverage improvement: 0 / 0 = 0.0%", flush=True)
    print(
        "Note: this is potentially unlocked coverage; UNCLEAR / MIXED SIGNAL labels are not persisted.",
        flush=True,
    )
    print("", flush=True)
    selected_reasons = {}
    for stat in selected_dimensions:
        if stat.get("selection_mode") not in {"coverage", "hybrid_coverage"}:
            continue
        reason = stat.get("selection_reason") or stat.get("label_repair_status") or "unknown"
        selected_reasons[reason] = selected_reasons.get(reason, 0) + 1
    if selected_reasons:
        print(
            "Selected dimensions by reason: "
            + ", ".join(f"{reason}={count}" for reason, count in sorted(selected_reasons.items())),
            flush=True,
        )
    else:
        print("Selected dimensions by reason: none", flush=True)
    print(
        "Rank | Dimension | Label Repair Status | Selection Reason | "
        "Marginal Cards Unlocked | Cumulative Cards | Weighted Unlock Score | "
        "Aggregate Importance Score",
        flush=True,
    )
    for rank, stat in enumerate(selected_dimensions, start=1):
        if stat.get("selection_mode") not in {"coverage", "hybrid_coverage"}:
            continue
        print(
            f"{rank} | {stat['dimension']} | {stat.get('label_repair_status', '')} | "
            f"{stat.get('selection_reason', '')} | {stat.get('marginal_unlock_count', '')} | "
            f"{stat.get('cumulative_unlocked_recommendations', '')} | "
            f"{_format_float(stat.get('marginal_weighted_unlock_score'))} | "
            f"{_format_float(stat.get('combined_score'))}",
            flush=True,
        )


def _fetch_dimension_samples(dimension: int):
    if get_dimension_mode(dimension) == "media":
        positive_ids = get_top_media_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
        negative_ids = get_bottom_media_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
        return "media", get_media_metadata(positive_ids), get_media_metadata(negative_ids)

    positive_ids = get_top_users_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
    negative_ids = get_bottom_users_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
    return "user", get_user_watch_history(positive_ids), get_user_watch_history(negative_ids)


def _default_label_result(skipped_reason: str = "") -> dict:
    if skipped_reason:
        return {
            "label": UNCLEAR_LABEL,
            "label_confidence": "unclear",
            "label_type": "unclear",
            "coverage_high_count": None,
            "coverage_high_total": None,
            "coverage_high_percent": None,
            "coverage_low_overlap_count": None,
            "coverage_low_total": None,
            "coverage_low_overlap_percent": None,
            "validation_status": "invalid",
            "validation_notes": [skipped_reason],
            "explanation": skipped_reason,
            "evidence": ["", "", ""],
        }
    return {
        "label": "",
        "label_confidence": "",
        "label_type": "",
        "coverage_high_count": None,
        "coverage_high_total": None,
        "coverage_high_percent": None,
        "coverage_low_overlap_count": None,
        "coverage_low_total": None,
        "coverage_low_overlap_percent": None,
        "validation_status": "",
        "validation_notes": [],
        "explanation": "",
        "evidence": ["", "", ""],
    }


def _format_validation_notes(notes) -> str:
    if isinstance(notes, list):
        return " | ".join(str(note) for note in notes if str(note).strip())
    return str(notes or "")


def _format_result_validation(result: dict) -> str:
    status = result.get("validation_status")
    notes = _format_validation_notes(result.get("validation_notes", []))
    if status and notes:
        return f"{status}: {notes}"
    return status or notes


def _format_review_cooldown_until(cooldown_days: int, now=None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now + timedelta(days=cooldown_days)).isoformat(timespec="seconds")


def _blank_governance() -> dict:
    return {
        "label_type": "",
        "explainable": "",
        "display_label": "",
        "needs_review": "",
    }


def _csv_governance_for_label(label_result: dict) -> dict:
    if not _valid_generated_label(label_result):
        return _blank_governance()
    return classify_label_governance(label_result.get("label", ""))


def _existing_label_row_to_dict(row) -> dict | None:
    if not row:
        return None
    fields = [
        "dimension",
        "label",
        "label_type",
        "explainable",
        "display_label",
        "needs_review",
        "last_reviewed_at",
        "review_attempt_count",
        "next_review_at",
    ]
    return dict(zip(fields, row))


def get_existing_label_row(cur, dimension: int) -> dict | None:
    cur.execute(
        """
        SELECT
            dimension,
            label,
            label_type,
            explainable,
            display_label,
            needs_review,
            last_reviewed_at,
            review_attempt_count,
            next_review_at
        FROM embedding_labels
        WHERE dimension = %s
        """,
        (dimension,),
    )
    return _existing_label_row_to_dict(cur.fetchone())


def _valid_generated_label(label_result: dict) -> bool:
    return (
        _should_persist_label(label_result.get("label"))
        and label_result.get("validation_status") != "invalid"
    )


def _valid_semantic_repair_label(label_result: dict) -> bool:
    return (
        _valid_generated_label(label_result)
        and label_result.get("validation_status") == "valid"
        and label_result.get("label_type") == "semantic"
    )


def _valid_review_replacement_label(label_result: dict) -> bool:
    return (
        _valid_generated_label(label_result)
        and label_result.get("validation_status") == "valid"
    )


def _mark_label_review_attempt(cur, dimension: int, repair_cooldown_days: int) -> None:
    cur.execute(
        """
        UPDATE embedding_labels
        SET
            last_reviewed_at = NOW(),
            review_attempt_count = COALESCE(review_attempt_count, 0) + 1,
            next_review_at = NOW() + (%s * INTERVAL '1 day'),
            updated_at = NOW()
        WHERE dimension = %s
        """,
        (repair_cooldown_days, dimension),
    )


def _history_change_reason(existing_row: dict, label_repair_status: str, selection_reason: str) -> str:
    _status, derived_reason = _label_repair_status(existing_row)
    reason = selection_reason or derived_reason
    return f"coverage_repair:{label_repair_status or 'unusable_label'}:{reason}"


def save_label_result(
    cur,
    dimension: int,
    label_result: dict,
    label_repair_status: str = "",
    selection_reason: str = "",
    repair_cooldown_days: int = DEFAULT_REPAIR_COOLDOWN_DAYS,
    review_mode: bool = False,
) -> tuple[bool, str]:
    existing_row = get_existing_label_row(cur, dimension)
    existing_status, existing_reason = _label_repair_status(existing_row)
    effective_status = label_repair_status or existing_status
    effective_reason = selection_reason or existing_reason

    if not _valid_generated_label(label_result):
        if existing_row and (existing_status == "unusable_label" or review_mode):
            _mark_label_review_attempt(cur, dimension, repair_cooldown_days)
            return False, "repair_cooldown_scheduled"
        return False, "invalid_label_not_saved"

    generated_label = label_result["label"]
    governance = classify_label_governance(generated_label)
    if not existing_row:
        cur.execute(
            """
            INSERT INTO embedding_labels (
                dimension,
                label,
                created_at,
                label_type,
                explainable,
                display_label,
                needs_review,
                updated_at,
                last_reviewed_at,
                review_attempt_count,
                next_review_at
            )
            VALUES (
                %s,
                %s,
                NOW(),
                %s,
                %s,
                %s,
                %s,
                NOW(),
                NOW(),
                0,
                NULL
            )
            """,
            (
                dimension,
                generated_label,
                governance["label_type"],
                governance["explainable"],
                governance["display_label"],
                governance["needs_review"],
            ),
        )
        return True, "inserted_missing_label"

    if review_mode:
        if not _valid_review_replacement_label(label_result):
            _mark_label_review_attempt(cur, dimension, repair_cooldown_days)
            return False, "invalid_review_replacement_not_saved"
        cur.execute(
            """
            INSERT INTO embedding_label_history (
                dimension,
                old_label,
                old_label_type,
                old_explainable,
                old_display_label,
                old_needs_review,
                old_last_reviewed_at,
                old_review_attempt_count,
                old_next_review_at,
                new_label,
                change_reason,
                changed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                dimension,
                existing_row.get("label"),
                existing_row.get("label_type"),
                existing_row.get("explainable"),
                existing_row.get("display_label"),
                existing_row.get("needs_review"),
                existing_row.get("last_reviewed_at"),
                existing_row.get("review_attempt_count"),
                existing_row.get("next_review_at"),
                generated_label,
                "review:needs_review",
            ),
        )
        cur.execute(
            """
            UPDATE embedding_labels
            SET
                label = %s,
                label_type = %s,
                explainable = %s,
                display_label = %s,
                needs_review = %s,
                created_at = NOW(),
                updated_at = NOW(),
                last_reviewed_at = NOW(),
                review_attempt_count = COALESCE(review_attempt_count, 0) + 1,
                next_review_at = CASE
                    WHEN %s IS TRUE THEN NOW() + (%s * INTERVAL '1 day')
                    ELSE NULL
                END
            WHERE dimension = %s
            """,
            (
                generated_label,
                governance["label_type"],
                governance["explainable"],
                governance["display_label"],
                governance["needs_review"],
                governance["needs_review"],
                repair_cooldown_days,
                dimension,
            ),
        )
        if governance["needs_review"]:
            return True, "updated_review_label_cooldown_scheduled"
        return True, "updated_review_label"

    if existing_status == "usable_label":
        return False, "existing_usable_label_preserved"

    if not _valid_semantic_repair_label(label_result):
        _mark_label_review_attempt(cur, dimension, repair_cooldown_days)
        return False, "non_semantic_repair_not_saved"

    cur.execute(
        """
        INSERT INTO embedding_label_history (
            dimension,
            old_label,
            old_label_type,
            old_explainable,
            old_display_label,
            old_needs_review,
            old_last_reviewed_at,
            old_review_attempt_count,
            old_next_review_at,
            new_label,
            change_reason,
            changed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            dimension,
            existing_row.get("label"),
            existing_row.get("label_type"),
            existing_row.get("explainable"),
            existing_row.get("display_label"),
            existing_row.get("needs_review"),
            existing_row.get("last_reviewed_at"),
            existing_row.get("review_attempt_count"),
            existing_row.get("next_review_at"),
            generated_label,
            _history_change_reason(existing_row, effective_status, effective_reason),
        ),
    )
    cur.execute(
        """
        UPDATE embedding_labels
        SET
            label = %s,
            label_type = %s,
            explainable = %s,
            display_label = %s,
            needs_review = %s,
            created_at = NOW(),
            updated_at = NOW(),
            last_reviewed_at = NOW(),
            review_attempt_count = 0,
            next_review_at = NULL
        WHERE dimension = %s
        """,
        (
            generated_label,
            governance["label_type"],
            governance["explainable"],
            governance["display_label"],
            governance["needs_review"],
            dimension,
        ),
    )
    return True, "updated_unusable_label"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", action="store_true", help="Generate labels using the configured LLM provider")
    parser.add_argument("--gpt_label", dest="label", action="store_true", help="Deprecated alias for --label")
    parser.add_argument("--label_provider", choices=["openai", "ollama"], default=None, help="Override label provider")
    parser.add_argument("--label_model", default=None, help="Override label model name")
    parser.add_argument("--export_csv", type=str)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--save_label", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--dim_type", choices=["media", "user", "all"], default="all")
    parser.add_argument(
        "--selection_mode",
        choices=["importance", "coverage", "hybrid", "review"],
        default="importance",
        help="Automatic dimension selection strategy",
    )
    parser.add_argument(
        "--coverage_share",
        type=float,
        default=0.80,
        help="Hybrid-mode share of dimensions to select through coverage ranking",
    )
    parser.add_argument(
        "--repair_cooldown_days",
        type=int,
        default=DEFAULT_REPAIR_COOLDOWN_DAYS,
        help="Days to wait before retrying an unusable saved label after a failed repair attempt",
    )
    dimension_group = parser.add_mutually_exclusive_group()
    dimension_group.add_argument("--dimension", type=int, help="Process one exact embedding dimension")
    dimension_group.add_argument("--dimensions", nargs="+", type=int, help="Process exact embedding dimensions")
    parser.add_argument(
        "--refresh_existing",
        "--include_labeled",
        action="store_true",
        help="Process top SHAP dimensions even when they already have saved labels",
    )
    args = parser.parse_args()

    if not 0.0 <= args.coverage_share <= 1.0:
        parser.error("--coverage_share must be between 0.0 and 1.0")
    if args.repair_cooldown_days < 0:
        parser.error("--repair_cooldown_days must be zero or greater")

    csv_rows = []
    provider_name = None
    model_name = None
    should_call_model = args.label and not args.dry_run

    if args.label:
        provider_name, model_name = resolve_label_backend(args.label_provider, args.label_model)

    ensure_app_schema()

    conn = connect_db()
    cur = conn.cursor()

    requested_dimensions = args.dimensions or (
        [args.dimension] if args.dimension is not None else []
    )
    if requested_dimensions:
        dim_min, dim_max = _get_dimension_range(args.dim_type)
        for dimension in requested_dimensions:
            if dimension < 0 or dimension >= COMBINED_EMBEDDING_DIMENSIONS:
                parser.error(
                    f"dimension {dimension} is outside the valid range "
                    f"0-{COMBINED_EMBEDDING_DIMENSIONS - 1}"
                )
            if not (dim_min <= dimension < dim_max):
                parser.error(
                    f"dimension {dimension} is outside --dim_type {args.dim_type}; "
                    "use --dim_type all or the matching scope"
                )
        top_dims = get_dimension_stats_for_dimensions(cur, requested_dimensions)
        top_dims = _decorate_importance_dimensions(top_dims, selection_mode="manual")
        selection_summary = {
            "selection_mode": "manual",
            "importance_selected_count": len(top_dims),
            "coverage_selected_count": 0,
        }
    else:
        if args.selection_mode == "coverage" and args.refresh_existing:
            print(
                "ℹ️ --refresh_existing is ignored in coverage mode because coverage selection "
                "only targets unlabeled dimensions that can unlock currently unlabeled "
                "recommendation cards.",
                flush=True,
            )
        elif args.selection_mode == "hybrid" and args.refresh_existing:
            print(
                "ℹ️ --refresh_existing applies only to the importance portion of hybrid "
                "selection; coverage-selected dimensions remain unlabeled-only.",
                flush=True,
            )

        top_dims, selection_summary = select_automatic_dimensions(
            cur,
            limit=args.limit,
            dim_type=args.dim_type,
            selection_mode=args.selection_mode,
            coverage_share=args.coverage_share,
            include_labeled=args.refresh_existing,
        )

    print_selection_summary(
        args.selection_mode,
        top_dims,
        selection_summary,
        manual=bool(requested_dimensions),
    )

    if not top_dims:
        if args.selection_mode == "review":
            scope = "review dimensions"
        else:
            scope = "all dimensions" if args.refresh_existing else "unlabeled dimensions"
        print(f"ℹ️ No {scope} selected for labeling.", flush=True)

    review_cooldown_events = []
    for dim_stats in top_dims:
        dimension = dim_stats["dimension"]
        mode, positive_df, negative_df = _fetch_dimension_samples(dimension)
        prompt_bundle = build_dimension_prompt(
            dimension,
            positive_df,
            negative_df,
            dimension_mode=mode,
            existing_label=dim_stats.get("existing_label") if dim_stats.get("selection_mode") == "review" else None,
            existing_display_label=(
                dim_stats.get("existing_display_label") if dim_stats.get("selection_mode") == "review" else None
            ),
            existing_label_type=(
                dim_stats.get("existing_label_type") if dim_stats.get("selection_mode") == "review" else None
            ),
        )
        skipped_reason = prompt_bundle["skipped_reason"]
        label_result = _default_label_result(skipped_reason)

        print(f"📄 Prepared contrast prompt for {mode} dim {dimension}", flush=True)
        if args.dry_run:
            print(prompt_bundle["prompt_text"], flush=True)

        if skipped_reason:
            print(f"⚠️ Skipping LLM for dim {dimension}: {skipped_reason}", flush=True)
        elif should_call_model:
            try:
                label_result = call_llm_for_label_result(
                    prompt_bundle["prompt_text"],
                    provider=provider_name,
                    model=model_name,
                )
                print(
                    f"🧠 {mode.title()} dim {dimension} labeled via "
                    f"{provider_name}:{model_name} as: {label_result['label']}",
                    flush=True,
                )
                validation_message = _format_result_validation(label_result)
                if validation_message:
                    print(f"   validation={validation_message}", flush=True)
            except Exception as exc:
                skipped_reason = f"LLM error: {str(exc).strip()}"
                label_result = _default_label_result(skipped_reason)
                print(f"⚠️ Skipping dim {dimension} due to LLM error: {exc}", flush=True)

        generated_label = label_result["label"]
        evidence = label_result.get("evidence", ["", "", ""])
        final_governance = _csv_governance_for_label(label_result)
        final_saved_label = ""
        save_status = ""
        review_cooldown_until = ""

        if args.save_label and not args.dry_run:
            saved, save_status = save_label_result(
                cur,
                dimension,
                label_result,
                label_repair_status=dim_stats.get("label_repair_status", ""),
                selection_reason=dim_stats.get("selection_reason", ""),
                repair_cooldown_days=args.repair_cooldown_days,
                review_mode=dim_stats.get("selection_mode") == "review",
            )
            if saved:
                final_saved_label = generated_label
                print(f"✅ Saved label for dim {dimension}: {save_status}", flush=True)
            elif save_status in {
                "repair_cooldown_scheduled",
                "non_semantic_repair_not_saved",
                "invalid_review_replacement_not_saved",
            }:
                print(f"ℹ️ Dim {dimension} not overwritten: {save_status}", flush=True)
            if dim_stats.get("selection_mode") == "review" and save_status in {
                "updated_review_label_cooldown_scheduled",
                "repair_cooldown_scheduled",
                "invalid_review_replacement_not_saved",
            }:
                review_cooldown_until = _format_review_cooldown_until(args.repair_cooldown_days)
                review_cooldown_events.append(
                    {
                        "dimension": dimension,
                        "status": save_status,
                        "cooldown_until": review_cooldown_until,
                    }
                )
                print(
                    f"ℹ️ Review dim {dimension} remains unresolved; "
                    f"cooldown expiration date: {review_cooldown_until}",
                    flush=True,
                )

        if args.export_csv:
            csv_rows.append(
                {
                    "dimension": dimension,
                    "selection_mode": dim_stats.get("selection_mode", args.selection_mode),
                    "label_repair_status": dim_stats.get("label_repair_status", ""),
                    "selection_reason": dim_stats.get("selection_reason", ""),
                    "existing_label": dim_stats.get("existing_label", ""),
                    "existing_display_label": dim_stats.get("existing_display_label", ""),
                    "existing_label_type": dim_stats.get("existing_label_type", ""),
                    "existing_explainable": dim_stats.get("existing_explainable", ""),
                    "existing_needs_review": dim_stats.get("existing_needs_review", dim_stats.get("needs_review", "")),
                    "last_reviewed_at": dim_stats.get("last_reviewed_at", ""),
                    "review_attempt_count": dim_stats.get("review_attempt_count", ""),
                    "next_review_at": dim_stats.get("next_review_at", ""),
                    "unlock_count_total": dim_stats.get("unlock_count_total", ""),
                    "marginal_unlock_count": dim_stats.get("marginal_unlock_count", ""),
                    "marginal_weighted_unlock_score": dim_stats.get("marginal_weighted_unlock_score", ""),
                    "cumulative_unlocked_recommendations": dim_stats.get(
                        "cumulative_unlocked_recommendations",
                        "",
                    ),
                    "positive_shap_sum_on_unlabeled": dim_stats.get(
                        "positive_shap_sum_on_unlabeled",
                        "",
                    ),
                    "positive_shap_avg_on_unlabeled": dim_stats.get(
                        "positive_shap_avg_on_unlabeled",
                        "",
                    ),
                    "mode": mode,
                    "summary": prompt_bundle["summary"],
                    "prompt_text": prompt_bundle["prompt_text"],
                    "label_provider": provider_name or "",
                    "label_model": model_name or "",
                    "proposed_label": generated_label,
                    "proposed_label_confidence": label_result.get("label_confidence", ""),
                    "proposed_label_type": label_result.get(
                        "proposed_label_type",
                        label_result.get("label_type", ""),
                    ),
                    "gpt_label": generated_label,
                    "final_saved_label": final_saved_label,
                    "final_label_type": final_governance["label_type"],
                    "final_explainable": final_governance["explainable"],
                    "final_needs_review": final_governance["needs_review"],
                    "final_display_label": final_governance["display_label"],
                    "review_cooldown_until": review_cooldown_until,
                    "label": generated_label,
                    "label_confidence": label_result.get("label_confidence", ""),
                    "label_type": final_governance["label_type"],
                    "explainable": final_governance["explainable"],
                    "needs_review": final_governance["needs_review"],
                    "display_label": final_governance["display_label"],
                    "coverage_high_count": label_result.get("coverage_high_count"),
                    "coverage_high_total": label_result.get("coverage_high_total"),
                    "coverage_high_percent": label_result.get("coverage_high_percent"),
                    "coverage_low_overlap_count": label_result.get("coverage_low_overlap_count"),
                    "coverage_low_total": label_result.get("coverage_low_total"),
                    "coverage_low_overlap_percent": label_result.get("coverage_low_overlap_percent"),
                    "validation_status": label_result.get("validation_status", ""),
                    "validation_notes": _format_validation_notes(label_result.get("validation_notes", [])),
                    "label_explanation": label_result.get("explanation", ""),
                    "label_evidence_1": evidence[0] if len(evidence) > 0 else "",
                    "label_evidence_2": evidence[1] if len(evidence) > 1 else "",
                    "label_evidence_3": evidence[2] if len(evidence) > 2 else "",
                    "valid_positive_count": prompt_bundle["valid_positive_count"],
                    "valid_negative_count": prompt_bundle["valid_negative_count"],
                    "flagged_item_count": prompt_bundle["flagged_item_count"],
                    "skipped_reason": skipped_reason,
                    "usage_count": dim_stats["usage_count"],
                    "sum_abs_shap": dim_stats.get("sum_abs_shap", 0.0),
                    "avg_abs_shap": dim_stats.get("avg_abs_shap", 0.0),
                    "combined_score": dim_stats.get("combined_score", 0.0),
                    "user_count": dim_stats.get("user_count", 0),
                    "stats_source": dim_stats.get("stats_source", "unknown"),
                }
            )
        conn.commit()

    if review_cooldown_events:
        print(
            "Review unresolved dimensions placed on cooldown: "
            f"{len(review_cooldown_events)}",
            flush=True,
        )
        for event in review_cooldown_events:
            print(
                f"  Dimension {event['dimension']} | {event['status']} | "
                f"cooldown expiration date: {event['cooldown_until']}",
                flush=True,
            )

    if args.export_csv:
        with open(args.export_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=CSV_FIELDNAMES,
            )
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"✅ CSV export completed: {args.export_csv}", flush=True)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
