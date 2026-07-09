#!/usr/bin/env python3
"""
Read-only diagnostics for embedding label quality and recommendation explanation chips.

Examples:
    python scripts/diagnose_label_quality.py --top-labels 15
    python scripts/diagnose_label_quality.py --dimension 1385
    python scripts/diagnose_label_quality.py --label "professional settings" --user jmnovak
    python scripts/diagnose_label_quality.py --user jmnovak --title "A Complete Unknown"
    python scripts/diagnose_label_quality.py --audit-top-labels 10 --user jmnovak
    python scripts/diagnose_label_quality.py --audit-display-label "high-stakes competition narratives" --user jmnovak
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.db.connection import connect_db

EMBEDDING_SIDE_DIMENSIONS = 768
COMBINED_EMBEDDING_DIMENSIONS = EMBEDDING_SIDE_DIMENSIONS * 2

TOP_TASTE_LABELS_SQL = """
SELECT
    el.display_label,
    COUNT(DISTINCT (si.user_id, si.rating_key)) AS rec_count,
    COUNT(DISTINCT si.dimension) AS dim_count,
    ROUND(AVG(si.shap_value)::numeric, 4) AS avg_shap,
    ROUND(MAX(si.shap_value)::numeric, 4) AS max_shap
FROM shap_impact si
JOIN embedding_labels el ON el.dimension = si.dimension
WHERE si.dimension >= 768
  AND si.shap_value > 0
  AND el.explainable IS TRUE
  AND el.display_label IS NOT NULL
  AND BTRIM(el.display_label) <> ''
GROUP BY el.display_label
ORDER BY rec_count DESC
LIMIT %s
"""

DUPLICATE_DISPLAY_LABELS_SQL = """
SELECT
    display_label,
    COUNT(*) AS dim_count,
    ARRAY_AGG(dimension ORDER BY dimension) AS dimensions
FROM embedding_labels
WHERE explainable IS TRUE
  AND display_label IS NOT NULL
  AND BTRIM(display_label) <> ''
GROUP BY display_label
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT %s
"""

LABEL_LOOKUP_SQL = """
SELECT
    dimension,
    label,
    display_label,
    label_type,
    explainable,
    needs_review,
    created_at,
    updated_at
FROM embedding_labels
WHERE display_label ILIKE %s
   OR label ILIKE %s
ORDER BY dimension
"""

DIMENSION_SHAP_SQL = """
SELECT
    COUNT(*) AS shap_rows,
    COUNT(DISTINCT rating_key) AS distinct_recs,
    COUNT(DISTINCT user_id) AS distinct_users,
    ROUND(AVG(shap_value)::numeric, 4) AS avg_shap,
    ROUND(STDDEV_POP(shap_value)::numeric, 4) AS std_shap,
    ROUND(MIN(shap_value)::numeric, 4) AS min_shap,
    ROUND(MAX(shap_value)::numeric, 4) AS max_shap
FROM shap_impact
WHERE dimension = %s
  AND shap_value > 0
"""

USER_DIMENSION_SHAP_SQL = """
SELECT
    COUNT(*) AS shap_rows,
    COUNT(DISTINCT rating_key) AS distinct_recs,
    ROUND(AVG(shap_value)::numeric, 4) AS avg_shap,
    ROUND(STDDEV_POP(shap_value)::numeric, 4) AS std_shap,
    ROUND(MIN(shap_value)::numeric, 4) AS min_shap,
    ROUND(MAX(shap_value)::numeric, 4) AS max_shap
FROM shap_impact
WHERE user_id = %s
  AND dimension = %s
  AND shap_value > 0
"""

USER_TOTAL_SHAP_RECS_SQL = """
SELECT COUNT(DISTINCT rating_key) AS total_recs
FROM shap_impact
WHERE user_id = %s
"""

SAMPLE_RECS_SQL = """
SELECT
    si.rating_key,
    l.title,
    l.year,
    l.media_type,
    ROUND(si.shap_value::numeric, 4) AS shap
FROM shap_impact si
JOIN library l ON l.rating_key = si.rating_key
WHERE si.user_id = %s
  AND si.dimension = %s
  AND si.shap_value > 0
ORDER BY si.shap_value DESC
LIMIT %s
"""

CARD_TASTE_MATCH_SQL = """
SELECT
    si.dimension,
    ROUND(si.shap_value::numeric, 4) AS shap,
    el.display_label,
    el.label_type,
    el.explainable,
    el.needs_review
FROM shap_impact si
JOIN embedding_labels el ON el.dimension = si.dimension
WHERE si.user_id = %s
  AND si.rating_key = %s
  AND si.shap_value > 0
  AND si.dimension >= 768
  AND el.explainable IS TRUE
  AND el.display_label IS NOT NULL
  AND BTRIM(el.display_label) <> ''
ORDER BY si.shap_value DESC
LIMIT %s
"""

CARD_TITLE_TRAITS_SQL = """
SELECT
    si.dimension,
    ROUND(si.shap_value::numeric, 4) AS shap,
    el.display_label,
    el.label_type,
    el.explainable,
    el.needs_review
FROM shap_impact si
JOIN embedding_labels el ON el.dimension = si.dimension
WHERE si.user_id = %s
  AND si.rating_key = %s
  AND si.shap_value > 0
  AND si.dimension < 768
  AND el.explainable IS TRUE
  AND el.display_label IS NOT NULL
  AND BTRIM(el.display_label) <> ''
ORDER BY si.shap_value DESC
LIMIT %s
"""

CARD_EXPLANATION_SQL = """
SELECT
    si.dimension,
    CASE WHEN si.dimension >= 768 THEN 'taste' ELSE 'title' END AS side,
    ROUND(si.shap_value::numeric, 4) AS shap,
    el.display_label,
    el.label_type,
    el.explainable,
    el.needs_review
FROM shap_impact si
LEFT JOIN embedding_labels el ON el.dimension = si.dimension
WHERE si.user_id = %s
  AND si.rating_key = %s
  AND si.shap_value > 0
ORDER BY si.shap_value DESC
LIMIT %s
"""

WATCH_SAMPLE_SQL = """
SELECT
    m.title,
    m.year,
    m.media_type,
    COALESCE(g.genre_tags, '') AS genre_tags
FROM training_data td
JOIN library m ON m.rating_key = td.rating_key
LEFT JOIN (
    SELECT mg.media_id, STRING_AGG(g.name, ', ' ORDER BY g.name) AS genre_tags
    FROM media_genres mg
    JOIN genres g ON mg.genre_id = g.id
    GROUP BY mg.media_id
) g ON g.media_id = m.rating_key
WHERE td.username = ANY(%s)
  AND td.label = 1
  AND td.engagement_ratio >= 0.50
ORDER BY td.engagement_ratio DESC
LIMIT %s
"""

TITLE_LOOKUP_SQL = """
SELECT rating_key, title, year, media_type
FROM library
WHERE title ILIKE %s
ORDER BY year DESC NULLS LAST, rating_key
LIMIT %s
"""

TOP_LABEL_DIMENSIONS_SQL = """
SELECT
    el.display_label,
    el.dimension,
    el.label,
    el.label_type,
    el.explainable,
    el.needs_review,
    el.created_at,
    COUNT(DISTINCT (si.user_id, si.rating_key)) AS rec_count,
    COUNT(DISTINCT si.user_id) AS user_count,
    ROUND(AVG(si.shap_value)::numeric, 4) AS avg_shap,
    ROUND(STDDEV_POP(si.shap_value)::numeric, 4) AS std_shap,
    ROUND(MAX(si.shap_value)::numeric, 4) AS max_shap
FROM embedding_labels el
JOIN shap_impact si ON si.dimension = el.dimension
WHERE el.dimension >= 768
  AND si.shap_value > 0
  AND el.explainable IS TRUE
  AND el.display_label IS NOT NULL
  AND BTRIM(el.display_label) <> ''
  AND el.display_label = ANY(%s)
GROUP BY
    el.display_label,
    el.dimension,
    el.label,
    el.label_type,
    el.explainable,
    el.needs_review,
    el.created_at
ORDER BY el.display_label, rec_count DESC
"""

GENRE_SAMPLE_SQL = """
SELECT DISTINCT g.name
FROM training_data td
JOIN media_genres mg ON mg.media_id = td.rating_key
JOIN genres g ON g.id = mg.genre_id
WHERE td.username = ANY(%s)
  AND td.label = 1
  AND td.engagement_ratio >= 0.50
"""

CLUSTER_LABEL_LOOKUP_SQL = """
SELECT
    el.dimension,
    el.label,
    el.display_label,
    el.label_type,
    el.explainable,
    el.needs_review,
    el.created_at,
    COUNT(DISTINCT (si.user_id, si.rating_key)) AS rec_count,
    COUNT(DISTINCT si.user_id) AS user_count,
    ROUND(AVG(si.shap_value)::numeric, 4) AS avg_shap,
    ROUND(STDDEV_POP(si.shap_value)::numeric, 4) AS std_shap
FROM embedding_labels el
LEFT JOIN shap_impact si ON si.dimension = el.dimension AND si.shap_value > 0
WHERE regexp_replace(el.display_label, '[‑–—\\-]', ' ', 'g') ILIKE %s
   OR regexp_replace(el.label, '[‑–—\\-]', ' ', 'g') ILIKE %s
GROUP BY
    el.dimension,
    el.label,
    el.display_label,
    el.label_type,
    el.explainable,
    el.needs_review,
    el.created_at
ORDER BY rec_count DESC NULLS LAST, el.dimension
"""


def print_section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print("(none)")
        return
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("-+-".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" | ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def parse_embedding(value: Any) -> np.ndarray:
    if isinstance(value, str):
        return np.array(ast.literal_eval(value), dtype=float)
    return np.array(list(value), dtype=float)


def dimension_mode(dimension: int) -> str:
    if 0 <= dimension < EMBEDDING_SIDE_DIMENSIONS:
        return "media"
    if EMBEDDING_SIDE_DIMENSIONS <= dimension < COMBINED_EMBEDDING_DIMENSIONS:
        return "user"
    raise ValueError(f"Dimension {dimension} is outside 0-{COMBINED_EMBEDDING_DIMENSIONS - 1}")


def fetch_all(conn, sql: str, params=()) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(conn, sql: str, params=()) -> dict[str, Any] | None:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def rank_users_on_dimension(conn, dimension: int) -> list[tuple[str, float]]:
    if dimension_mode(dimension) != "user":
        raise ValueError(f"Dimension {dimension} is not a user-preference dimension")
    index = dimension - EMBEDDING_SIDE_DIMENSIONS
    rows = fetch_all(conn, "SELECT username, embedding::text AS embedding FROM user_embeddings")
    ranked: list[tuple[str, float]] = []
    for row in rows:
        value = float(parse_embedding(row["embedding"])[index])
        ranked.append((row["username"], value))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def print_top_labels(conn, limit: int) -> None:
    print_section(f"Top Taste Match Labels (limit {limit})")
    rows = fetch_all(conn, TOP_TASTE_LABELS_SQL, (limit,))
    print_table(
        rows,
        ["rec_count", "dim_count", "avg_shap", "max_shap", "display_label"],
    )


def print_duplicate_labels(conn, limit: int) -> None:
    print_section(f"Duplicate Explainable display_label Values (limit {limit})")
    rows = fetch_all(conn, DUPLICATE_DISPLAY_LABELS_SQL, (limit,))
    for row in rows:
        dims = row.get("dimensions") or []
        dim_text = ", ".join(str(dim) for dim in dims[:8])
        if len(dims) > 8:
            dim_text += f", ... (+{len(dims) - 8} more)"
        print(f"{row['dim_count']} dims | {row['display_label']} | [{dim_text}]")


def print_label_lookup(conn, label_pattern: str) -> list[dict[str, Any]]:
    print_section(f"Labels Matching {label_pattern!r}")
    pattern = f"%{label_pattern}%"
    rows = fetch_all(conn, LABEL_LOOKUP_SQL, (pattern, pattern))
    print_table(
        rows,
        ["dimension", "label", "display_label", "label_type", "explainable", "needs_review"],
    )
    return rows


def print_dimension_deep_dive(conn, dimension: int, user: str | None, sample_limit: int) -> None:
    mode = dimension_mode(dimension)
    label_row = fetch_one(
        conn,
        """
        SELECT dimension, label, display_label, label_type, explainable, needs_review,
               created_at, updated_at
        FROM embedding_labels
        WHERE dimension = %s
        """,
        (dimension,),
    )
    print_section(f"Dimension {dimension} ({mode})")
    if label_row:
        print_table([label_row], list(label_row.keys()))
    else:
        print("No saved label for this dimension.")

    shap_summary = fetch_one(conn, DIMENSION_SHAP_SQL, (dimension,))
    if shap_summary:
        print("\nGlobal positive SHAP summary:")
        print_table([shap_summary], list(shap_summary.keys()))

    if user:
        total_recs = fetch_one(conn, USER_TOTAL_SHAP_RECS_SQL, (user,))
        user_summary = fetch_one(conn, USER_DIMENSION_SHAP_SQL, (user, dimension))
        if total_recs and user_summary and total_recs["total_recs"]:
            pct = 100.0 * float(user_summary["distinct_recs"]) / float(total_recs["total_recs"])
            user_summary = dict(user_summary)
            user_summary["coverage_pct"] = round(pct, 1)
            print(f"\nUser {user} positive SHAP summary:")
            print_table([user_summary], list(user_summary.keys()))

        print(f"\nTop recommendation cards for {user} on dim {dimension}:")
        sample_rows = fetch_all(conn, SAMPLE_RECS_SQL, (user, dimension, sample_limit))
        print_table(sample_rows, ["shap", "title", "year", "media_type", "rating_key"])

    if mode == "user":
        ranked = rank_users_on_dimension(conn, dimension)
        print("\nTop users on this dimension:")
        for username, value in ranked[:8]:
            print(f"  {username}: {value:.4f}")
        print("Bottom users:")
        for username, value in ranked[-8:]:
            print(f"  {username}: {value:.4f}")

        if user:
            for index, (username, value) in enumerate(ranked, start=1):
                if username == user:
                    print(
                        f"\n{user} rank: {index}/{len(ranked)} "
                        f"(value={value:.4f}, spread={ranked[0][1] - ranked[-1][1]:.4f})"
                    )
                    break

        high_users = [username for username, _ in ranked[:3]]
        low_users = [username for username, _ in ranked[-3:]]
        print("\nLabeling evidence sample (engaged training watches):")
        print("HIGH users:", ", ".join(high_users))
        for row in fetch_all(conn, WATCH_SAMPLE_SQL, (high_users, sample_limit)):
            print(f"  - {row['title']} ({row['year']}) {row['media_type']} | {row['genre_tags'][:60]}")
        print("LOW users:", ", ".join(low_users))
        for row in fetch_all(conn, WATCH_SAMPLE_SQL, (low_users, sample_limit)):
            print(f"  - {row['title']} ({row['year']}) {row['media_type']} | {row['genre_tags'][:60]}")


def _genre_sets(conn, usernames: list[str]) -> set[str]:
    if not usernames:
        return set()
    rows = fetch_all(conn, GENRE_SAMPLE_SQL, (usernames,))
    return {row["name"] for row in rows}


def _watch_titles(conn, usernames: list[str], limit: int) -> list[str]:
    rows = fetch_all(conn, WATCH_SAMPLE_SQL, (usernames, limit))
    return [
        f"{row['title']} ({row['year']}) [{row['media_type']}]"
        for row in rows
    ]


def _quality_flags(
    *,
    std_shap: float | None,
    coverage_pct: float | None,
    user_rank: int | None,
    user_total: int | None,
    axis_spread: float | None,
    needs_review: bool,
    dim_count_for_label: int,
    high_genres: set[str],
    low_genres: set[str],
) -> list[str]:
    flags: list[str] = []
    if needs_review:
        flags.append("needs_review")
    if dim_count_for_label > 1:
        flags.append("duplicate_display_label")
    if std_shap is not None and coverage_pct is not None:
        if std_shap < 0.02 and coverage_pct >= 75:
            flags.append("flat_booster")
    if axis_spread is not None and axis_spread < 0.06:
        flags.append("weak_user_axis")
    if user_rank is not None and user_total is not None and coverage_pct is not None:
        percentile = 100.0 * user_rank / user_total
        if 25 <= percentile <= 75 and coverage_pct >= 60:
            flags.append("middle_user_high_coverage")
    if high_genres and low_genres:
        overlap = len(high_genres & low_genres)
        union = len(high_genres | low_genres)
        if union and overlap / union > 0.55:
            flags.append("weak_high_low_genre_separation")
    return flags


def _verdict(flags: list[str]) -> str:
    severe = {"flat_booster", "weak_high_low_genre_separation", "weak_user_axis"}
    if severe & set(flags):
        return "SUSPECT"
    if "middle_user_high_coverage" in flags or "needs_review" in flags:
        return "REVIEW"
    if "duplicate_display_label" in flags:
        return "REVIEW"
    return "OK"


def audit_top_taste_labels(
    conn,
    limit: int,
    user: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    top_labels = fetch_all(conn, TOP_TASTE_LABELS_SQL, (limit,))
    if not top_labels:
        print_section("Top Taste Label Audit")
        print("No explainable taste-match labels found.")
        return []

    display_labels = [row["display_label"] for row in top_labels]
    dim_rows = fetch_all(conn, TOP_LABEL_DIMENSIONS_SQL, (display_labels,))
    dims_by_label: dict[str, list[dict[str, Any]]] = {}
    for row in dim_rows:
        dims_by_label.setdefault(row["display_label"], []).append(row)

    print_section(f"Top {limit} Taste-Match Label Audit (user={user})")
    summary_rows: list[dict[str, Any]] = []

    for rank, label_row in enumerate(top_labels, start=1):
        display_label = label_row["display_label"]
        dimensions = dims_by_label.get(display_label, [])
        dim_count = int(label_row["dim_count"])
        print(f"\n{'-' * 72}")
        print(
            f"#{rank} {display_label}\n"
            f"    rec_count={label_row['rec_count']} | dims={dim_count} | "
            f"global_avg_shap={label_row['avg_shap']} | global_max_shap={label_row['max_shap']}"
        )

        for dim_row in dimensions:
            dimension = int(dim_row["dimension"])
            print(
                f"\n  Dimension {dimension} | rec_count={dim_row['rec_count']} | "
                f"users={dim_row['user_count']} | avg_shap={dim_row['avg_shap']} | "
                f"std_shap={dim_row['std_shap']}"
            )
            print(
                f"    label_type={dim_row['label_type']} | needs_review={dim_row['needs_review']} | "
                f"created={dim_row['created_at']}"
            )

            total_recs = fetch_one(conn, USER_TOTAL_SHAP_RECS_SQL, (user,))
            user_summary = fetch_one(conn, USER_DIMENSION_SHAP_SQL, (user, dimension))
            coverage_pct = None
            if total_recs and user_summary and total_recs["total_recs"]:
                coverage_pct = round(
                    100.0 * float(user_summary["distinct_recs"]) / float(total_recs["total_recs"]),
                    1,
                )
                print(
                    f"    {user}: coverage={coverage_pct}% "
                    f"({user_summary['distinct_recs']}/{total_recs['total_recs']} cards) | "
                    f"avg_shap={user_summary['avg_shap']} | std_shap={user_summary['std_shap']}"
                )

            ranked = rank_users_on_dimension(conn, dimension)
            user_rank = None
            user_value = None
            axis_spread = ranked[0][1] - ranked[-1][1]
            for index, (username, value) in enumerate(ranked, start=1):
                if username == user:
                    user_rank = index
                    user_value = value
                    break
            if user_rank is not None:
                print(
                    f"    {user} axis rank={user_rank}/{len(ranked)} "
                    f"value={user_value:.4f} spread={axis_spread:.4f}"
                )

            high_users = [username for username, _ in ranked[:3]]
            low_users = [username for username, _ in ranked[-3:]]
            high_genres = _genre_sets(conn, high_users)
            low_genres = _genre_sets(conn, low_users)
            high_only = sorted(high_genres - low_genres)[:8]
            low_only = sorted(low_genres - high_genres)[:8]
            print(f"    HIGH users: {', '.join(high_users)}")
            for title in _watch_titles(conn, high_users, min(5, sample_limit)):
                print(f"      - {title}")
            print(f"    LOW users: {', '.join(low_users)}")
            for title in _watch_titles(conn, low_users, min(5, sample_limit)):
                print(f"      - {title}")
            if high_only or low_only:
                print(f"    Genre contrast HIGH-only: {', '.join(high_only) or '(none)'}")
                print(f"    Genre contrast LOW-only:  {', '.join(low_only) or '(none)'}")

            std_shap = float(dim_row["std_shap"]) if dim_row["std_shap"] is not None else None
            flags = _quality_flags(
                std_shap=std_shap,
                coverage_pct=coverage_pct,
                user_rank=user_rank,
                user_total=len(ranked),
                axis_spread=axis_spread,
                needs_review=bool(dim_row["needs_review"]),
                dim_count_for_label=dim_count,
                high_genres=high_genres,
                low_genres=low_genres,
            )
            verdict = _verdict(flags)
            print(f"    FLAGS: {', '.join(flags) if flags else '(none)'}")
            print(f"    VERDICT: {verdict}")

            sample_recs = fetch_all(conn, SAMPLE_RECS_SQL, (user, dimension, 5))
            if sample_recs:
                sample_text = ", ".join(
                    f"{row['title']} ({row['year']})"
                    for row in sample_recs
                )
                print(f"    Top {user} recs with this chip: {sample_text}")

            summary_rows.append(
                {
                    "rank": rank,
                    "display_label": display_label,
                    "dimension": dimension,
                    "rec_count": dim_row["rec_count"],
                    "user_coverage_pct": coverage_pct,
                    "std_shap": dim_row["std_shap"],
                    "user_rank": user_rank,
                    "axis_spread": round(axis_spread, 4),
                    "needs_review": dim_row["needs_review"],
                    "flags": ", ".join(flags) if flags else "",
                    "verdict": verdict,
                }
            )

    print_section("Audit Summary")
    print_table(
        summary_rows,
        [
            "rank",
            "verdict",
            "display_label",
            "dimension",
            "rec_count",
            "user_coverage_pct",
            "std_shap",
            "user_rank",
            "flags",
        ],
    )

    verdict_counts: dict[str, int] = {}
    for row in summary_rows:
        verdict_counts[row["verdict"]] = verdict_counts.get(row["verdict"], 0) + 1
    print(
        "\nVerdict counts: "
        + ", ".join(f"{key}={value}" for key, value in sorted(verdict_counts.items()))
    )
    return summary_rows


def audit_display_label_cluster(
    conn,
    label_pattern: str,
    user: str,
    sample_limit: int,
) -> list[dict[str, Any]]:
    normalized_pattern = label_pattern.replace("‑", " ").replace("–", " ").replace("—", " ").replace("-", " ")
    normalized_pattern = " ".join(normalized_pattern.split())
    pattern = f"%{normalized_pattern}%"
    cluster_rows = fetch_all(conn, CLUSTER_LABEL_LOOKUP_SQL, (pattern, pattern))
    print_section(f"Display Label Cluster Audit: {label_pattern!r}")
    if not cluster_rows:
        print("No matching dimensions found.")
        return []

    explainable_count = sum(1 for row in cluster_rows if row["explainable"] is True)
    print(
        f"Dimensions in cluster: {len(cluster_rows)} "
        f"(explainable={explainable_count}, not explainable={len(cluster_rows) - explainable_count})"
    )
    print_table(
        cluster_rows,
        [
            "dimension",
            "rec_count",
            "user_count",
            "avg_shap",
            "std_shap",
            "explainable",
            "needs_review",
            "display_label",
        ],
    )

    summary_rows: list[dict[str, Any]] = []
    for row in cluster_rows:
        dimension = int(row["dimension"])
        if dimension_mode(dimension) != "user":
            print(f"\n--- Dimension {dimension} (media) — skipping user-axis evidence ---")
            print(f"    label={row['label']}")
            summary_rows.append(
                {
                    "dimension": dimension,
                    "side": "media",
                    "rec_count": row["rec_count"],
                    "explainable": row["explainable"],
                    "verdict": "MEDIA_DIM",
                    "flags": "",
                }
            )
            continue

        ranked = rank_users_on_dimension(conn, dimension)
        axis_spread = ranked[0][1] - ranked[-1][1]
        high_users = [username for username, _ in ranked[:3]]
        low_users = [username for username, _ in ranked[-3:]]
        high_genres = _genre_sets(conn, high_users)
        low_genres = _genre_sets(conn, low_users)

        total_recs = fetch_one(conn, USER_TOTAL_SHAP_RECS_SQL, (user,))
        user_summary = fetch_one(conn, USER_DIMENSION_SHAP_SQL, (user, dimension))
        coverage_pct = None
        if total_recs and user_summary and total_recs["total_recs"]:
            coverage_pct = round(
                100.0 * float(user_summary["distinct_recs"]) / float(total_recs["total_recs"]),
                1,
            )

        user_rank = None
        for index, (username, _value) in enumerate(ranked, start=1):
            if username == user:
                user_rank = index
                break

        std_shap = float(row["std_shap"]) if row["std_shap"] is not None else None
        flags = _quality_flags(
            std_shap=std_shap,
            coverage_pct=coverage_pct,
            user_rank=user_rank,
            user_total=len(ranked),
            axis_spread=axis_spread,
            needs_review=bool(row["needs_review"]),
            dim_count_for_label=len(cluster_rows),
            high_genres=high_genres,
            low_genres=low_genres,
        )
        if row["explainable"] is not True:
            flags.append("depublished")
        verdict = _verdict(flags)

        print(f"\n--- Dimension {dimension} ---")
        print(
            f"    display_label={row['display_label']} | explainable={row['explainable']} | "
            f"rec_count={row['rec_count']} | std_shap={row['std_shap']}"
        )
        if coverage_pct is not None:
            print(f"    {user} coverage={coverage_pct}% rank={user_rank}/{len(ranked)}")
        print(f"    HIGH users: {', '.join(high_users)}")
        for title in _watch_titles(conn, high_users, min(4, sample_limit)):
            print(f"      - {title}")
        print(f"    LOW users: {', '.join(low_users)}")
        for title in _watch_titles(conn, low_users, min(4, sample_limit)):
            print(f"      - {title}")
        high_only = sorted(high_genres - low_genres)[:6]
        low_only = sorted(low_genres - high_genres)[:6]
        print(f"    Genre HIGH-only: {', '.join(high_only) or '(none)'}")
        print(f"    Genre LOW-only:  {', '.join(low_only) or '(none)'}")
        print(f"    FLAGS: {', '.join(flags) if flags else '(none)'} | VERDICT: {verdict}")

        summary_rows.append(
            {
                "dimension": dimension,
                "side": "user",
                "rec_count": row["rec_count"],
                "explainable": row["explainable"],
                "user_coverage_pct": coverage_pct,
                "std_shap": row["std_shap"],
                "user_rank": user_rank,
                "flags": ", ".join(flags) if flags else "",
                "verdict": verdict,
            }
        )

    print_section("Cluster Audit Summary")
    print_table(
        summary_rows,
        ["dimension", "side", "verdict", "rec_count", "explainable", "user_coverage_pct", "std_shap", "flags"],
    )
    return summary_rows


def depublish_dimensions(conn, dimensions: list[int]) -> list[dict[str, Any]]:
    if not dimensions:
        return []
    rows = fetch_all(
        conn,
        """
        UPDATE embedding_labels
        SET explainable = FALSE,
            needs_review = TRUE,
            updated_at = NOW()
        WHERE dimension = ANY(%s)
        RETURNING dimension, display_label, explainable, needs_review
        """,
        (dimensions,),
    )
    conn.commit()
    return rows


def print_card_audit(conn, user: str, title_pattern: str, limit: int) -> None:
    print_section(f"Card Audit for {user!r} / title ~ {title_pattern!r}")
    candidates = fetch_all(conn, TITLE_LOOKUP_SQL, (f"%{title_pattern}%", limit))
    if not candidates:
        print("No matching library titles.")
        return

    for candidate in candidates:
        print(
            f"\n{candidate['title']} ({candidate['year']}) "
            f"[{candidate['media_type']}] rating_key={candidate['rating_key']}"
        )
        taste_rows = fetch_all(
            conn,
            CARD_TASTE_MATCH_SQL,
            (user, candidate["rating_key"], 3),
        )
        title_rows = fetch_all(
            conn,
            CARD_TITLE_TRAITS_SQL,
            (user, candidate["rating_key"], 3),
        )

        print("Taste match chips (UI):")
        if taste_rows:
            print_table(
                taste_rows,
                ["dimension", "shap", "display_label", "label_type", "needs_review"],
            )
        else:
            print("  (none)")

        print("Title trait chips (UI):")
        if title_rows:
            print_table(
                title_rows,
                ["dimension", "shap", "display_label", "label_type", "needs_review"],
            )
        else:
            print("  (none)")

        print("Raw top positive SHAP contributors (all sides):")
        rows = fetch_all(
            conn,
            CARD_EXPLANATION_SQL,
            (user, candidate["rating_key"], 12),
        )
        if rows:
            print_table(
                rows,
                ["side", "dimension", "shap", "display_label", "label_type", "explainable", "needs_review"],
            )
        else:
            print("  No positive SHAP rows stored for this card.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only diagnostics for embedding label quality and explanation chips."
    )
    parser.add_argument("--top-labels", type=int, default=15, help="Show the most common taste-match labels.")
    parser.add_argument(
        "--duplicate-labels",
        type=int,
        default=15,
        help="Show explainable display_label values shared by multiple dimensions.",
    )
    parser.add_argument("--dimension", type=int, help="Deep dive on one embedding dimension.")
    parser.add_argument("--label", help="Find labels/display labels matching this substring.")
    parser.add_argument("--user", default="jmnovak", help="Username for user-specific SHAP/card views.")
    parser.add_argument("--title", action="append", help="Audit positive SHAP contributors for a library title.")
    parser.add_argument("--sample-limit", type=int, default=12, help="Rows to show in sample sections.")
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip the global top-label and duplicate-label summaries.",
    )
    parser.add_argument(
        "--audit-top-labels",
        type=int,
        metavar="N",
        help="Run a structured quality audit on the top N taste-match labels.",
    )
    parser.add_argument(
        "--audit-display-label",
        metavar="TEXT",
        help="Audit all dimensions whose label/display_label matches this substring.",
    )
    parser.add_argument(
        "--depublish-dimensions",
        nargs="+",
        type=int,
        metavar="DIM",
        help="Set explainable=false and needs_review=true for the given dimensions.",
    )
    args = parser.parse_args()

    load_dotenv()
    conn = connect_db()
    readonly = not args.depublish_dimensions
    try:
        if readonly:
            conn.set_session(readonly=True, autocommit=True)
    except Exception:
        pass

    try:
        if args.depublish_dimensions:
            print_section(f"Depublishing dimensions: {args.depublish_dimensions}")
            rows = depublish_dimensions(conn, args.depublish_dimensions)
            print_table(rows, ["dimension", "display_label", "explainable", "needs_review"])
            if not args.audit_display_label and not args.audit_top_labels:
                return 0

        if args.audit_top_labels:
            audit_top_taste_labels(conn, args.audit_top_labels, args.user, args.sample_limit)
            if not args.audit_display_label:
                return 0

        if args.audit_display_label:
            audit_display_label_cluster(
                conn,
                args.audit_display_label,
                args.user,
                args.sample_limit,
            )
            return 0

        if not args.skip_summary:
            print_top_labels(conn, args.top_labels)
            print_duplicate_labels(conn, args.duplicate_labels)

        matched_rows: list[dict[str, Any]] = []
        if args.label:
            matched_rows = print_label_lookup(conn, args.label)

        dimensions = []
        if args.dimension is not None:
            dimensions.append(args.dimension)
        elif matched_rows:
            dimensions.extend(int(row["dimension"]) for row in matched_rows)

        for dimension in dimensions:
            print_dimension_deep_dive(conn, dimension, args.user, args.sample_limit)

        if args.title:
            for title_pattern in args.title:
                print_card_audit(conn, args.user, title_pattern, args.sample_limit)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
