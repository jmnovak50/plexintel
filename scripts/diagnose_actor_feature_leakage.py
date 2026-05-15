#!/usr/bin/env python3
"""
Read-only diagnostics for actor_* recommendation features.

Examples:
    python scripts/diagnose_actor_feature_leakage.py --actors "Drew Powell,Michael McKean"
    python scripts/diagnose_actor_feature_leakage.py --top-suspicious 50
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.db.connection import connect_db


TARGET_MEDIA_SQL = """
SELECT
    a.name AS actor_name,
    l.rating_key,
    l.title,
    l.media_type,
    parent.title AS parent_title,
    COALESCE(NULLIF(l.show_title, ''), show.title) AS grandparent_title,
    l.year
FROM media_actors ma
JOIN actors a ON a.id = ma.actor_id
JOIN library l ON l.rating_key = ma.media_id
LEFT JOIN library parent ON parent.rating_key = l.parent_rating_key
LEFT JOIN library show ON show.rating_key = l.show_rating_key
WHERE a.name = ANY(%s)
ORDER BY
    a.name,
    COALESCE(l.show_rating_key, l.rating_key),
    l.media_type,
    l.season_number NULLS LAST,
    l.episode_number NULLS LAST,
    l.rating_key
"""


ACTOR_MODEL_MEDIA_SUMMARY_SQL = """
WITH actor_media AS (
    SELECT
        a.id AS actor_id,
        a.name AS actor_name,
        l.rating_key,
        l.media_type,
        COALESCE(l.show_rating_key, l.rating_key) AS show_or_movie_key
    FROM media_actors ma
    JOIN actors a ON a.id = ma.actor_id
    JOIN library l ON l.rating_key = ma.media_id
    WHERE a.name = ANY(%s)
      AND l.media_type IN ('movie', 'episode')
)
SELECT
    actor_name,
    COUNT(*) AS media_item_count,
    COUNT(*) FILTER (WHERE media_type = 'episode') AS episode_count,
    COUNT(*) FILTER (WHERE media_type = 'movie') AS movie_count,
    COUNT(DISTINCT show_or_movie_key) AS distinct_show_or_movie_count
FROM actor_media
GROUP BY actor_name
ORDER BY actor_name
"""


ACTOR_SHOW_CONCENTRATION_SQL = """
SELECT
    a.name AS actor_name,
    COALESCE(NULLIF(l.show_title, ''), show.title, l.title) AS show_or_movie,
    COUNT(*) AS item_count,
    COUNT(*) FILTER (WHERE l.media_type = 'episode') AS episode_count,
    COUNT(*) FILTER (WHERE l.media_type = 'movie') AS movie_count
FROM media_actors ma
JOIN actors a ON a.id = ma.actor_id
JOIN library l ON l.rating_key = ma.media_id
LEFT JOIN library show ON show.rating_key = l.show_rating_key
WHERE a.name = ANY(%s)
  AND l.media_type IN ('movie', 'episode')
GROUP BY a.name, COALESCE(NULLIF(l.show_title, ''), show.title, l.title)
ORDER BY a.name, item_count DESC, show_or_movie
"""


ACTOR_TRAINING_LABEL_SQL = """
SELECT
    a.name AS actor_name,
    COUNT(*) AS training_rows,
    COUNT(DISTINCT td.username) AS training_user_count,
    COUNT(DISTINCT td.rating_key) AS training_item_count,
    SUM(CASE WHEN td.label = 1 THEN 1 ELSE 0 END) AS positive_training_rows,
    SUM(CASE WHEN td.label = 0 THEN 1 ELSE 0 END) AS negative_training_rows,
    AVG(td.label::numeric) AS positive_rate,
    SUM(CASE WHEN td.label = 1 THEN COALESCE(td.sample_weight, 1.0) ELSE 0 END) AS positive_weight,
    SUM(CASE WHEN td.label = 0 THEN COALESCE(td.sample_weight, 1.0) ELSE 0 END) AS negative_weight
FROM training_data td
JOIN media_actors ma ON ma.media_id = td.rating_key
JOIN actors a ON a.id = ma.actor_id
WHERE a.name = ANY(%s)
GROUP BY a.name
ORDER BY a.name
"""


ACTOR_ENGAGEMENT_SQL = """
SELECT
    a.name AS actor_name,
    td.label,
    COALESCE(td.engagement_type, td.label_source, 'unknown') AS engagement_type,
    COUNT(*) AS training_rows
FROM training_data td
JOIN media_actors ma ON ma.media_id = td.rating_key
JOIN actors a ON a.id = ma.actor_id
WHERE a.name = ANY(%s)
GROUP BY a.name, td.label, COALESCE(td.engagement_type, td.label_source, 'unknown')
ORDER BY a.name, td.label DESC, training_rows DESC
"""


SUSPICIOUS_ACTORS_SQL = """
WITH actor_media AS (
    SELECT
        a.id AS actor_id,
        a.name AS actor_name,
        l.rating_key,
        l.media_type,
        COALESCE(l.show_rating_key, l.rating_key) AS show_or_movie_key,
        COALESCE(NULLIF(l.show_title, ''), show.title, l.title) AS show_or_movie
    FROM media_actors ma
    JOIN actors a ON a.id = ma.actor_id
    JOIN library l ON l.rating_key = ma.media_id
    LEFT JOIN library show ON show.rating_key = l.show_rating_key
    WHERE l.media_type IN ('movie', 'episode')
),
media_counts AS (
    SELECT
        actor_id,
        actor_name,
        COUNT(*) AS media_item_count,
        COUNT(*) FILTER (WHERE media_type = 'episode') AS episode_count,
        COUNT(*) FILTER (WHERE media_type = 'movie') AS movie_count,
        COUNT(DISTINCT show_or_movie_key) AS distinct_show_or_movie_count
    FROM actor_media
    GROUP BY actor_id, actor_name
),
show_counts AS (
    SELECT
        actor_id,
        show_or_movie,
        COUNT(*) AS show_item_count,
        ROW_NUMBER() OVER (
            PARTITION BY actor_id
            ORDER BY COUNT(*) DESC, show_or_movie
        ) AS rn
    FROM actor_media
    GROUP BY actor_id, show_or_movie
),
training_counts AS (
    SELECT
        a.id AS actor_id,
        COUNT(*) AS training_rows,
        SUM(CASE WHEN td.label = 1 THEN 1 ELSE 0 END) AS positive_training_rows,
        SUM(CASE WHEN td.label = 0 THEN 1 ELSE 0 END) AS negative_training_rows,
        AVG(td.label::numeric) AS positive_rate
    FROM training_data td
    JOIN media_actors ma ON ma.media_id = td.rating_key
    JOIN actors a ON a.id = ma.actor_id
    GROUP BY a.id
)
SELECT
    mc.actor_name,
    mc.media_item_count,
    mc.episode_count,
    mc.movie_count,
    mc.distinct_show_or_movie_count,
    sc.show_or_movie AS top_show_or_movie,
    sc.show_item_count AS top_show_item_count,
    COALESCE(tc.training_rows, 0) AS training_rows,
    COALESCE(tc.positive_training_rows, 0) AS positive_training_rows,
    COALESCE(tc.negative_training_rows, 0) AS negative_training_rows,
    tc.positive_rate
FROM media_counts mc
LEFT JOIN show_counts sc ON sc.actor_id = mc.actor_id AND sc.rn = 1
LEFT JOIN training_counts tc ON tc.actor_id = mc.actor_id
WHERE mc.media_item_count >= %s
ORDER BY mc.media_item_count DESC, mc.actor_name
"""


SHAP_ACTOR_FEATURE_SQL = """
SELECT
    feature_name,
    COUNT(*) AS top_feature_rows,
    COUNT(DISTINCT user_id) AS user_count,
    COUNT(DISTINCT rating_key) AS item_count,
    AVG(shap_value) AS avg_shap_value,
    AVG(ABS(shap_value)) AS avg_abs_shap_value
FROM shap_impact
WHERE feature_name LIKE 'actor_%'
GROUP BY feature_name
ORDER BY top_feature_rows DESC, avg_abs_shap_value DESC
LIMIT %s
"""


def parse_actor_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def fetch_all(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def column_exists(conn, table_name: str, column_name: str) -> bool:
    rows = fetch_all(
        conn,
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(rows)


def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.3f}"
    return str(value)


def print_section(title: str) -> None:
    print()
    print("=" * len(title))
    print(title)
    print("=" * len(title))


def print_table(rows: list[dict[str, Any]], columns: list[str] | None = None, limit: int | None = None) -> None:
    if not rows:
        print("(no rows)")
        return

    visible = rows[:limit] if limit is not None else rows
    columns = columns or list(visible[0].keys())
    rendered = [[format_value(row.get(col)) for col in columns] for row in visible]
    widths = [
        min(44, max(len(col), *(len(row[idx]) for row in rendered)))
        for idx, col in enumerate(columns)
    ]

    def clip(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        return text[: max(0, width - 3)] + "..."

    header = " | ".join(clip(col, widths[idx]).ljust(widths[idx]) for idx, col in enumerate(columns))
    divider = "-+-".join("-" * width for width in widths)
    print(header)
    print(divider)
    for row in rendered:
        print(" | ".join(clip(row[idx], widths[idx]).ljust(widths[idx]) for idx in range(len(columns))))

    if limit is not None and len(rows) > limit:
        print(f"... {len(rows) - limit} more row(s) not shown")


def rows_capped_by_actor(rows: list[dict[str, Any]], max_per_actor: int) -> list[dict[str, Any]]:
    if max_per_actor <= 0:
        return rows

    counts: Counter[str] = Counter()
    capped = []
    skipped: Counter[str] = Counter()
    for row in rows:
        actor = row.get("actor_name", "")
        if counts[actor] < max_per_actor:
            capped.append(row)
            counts[actor] += 1
        else:
            skipped[actor] += 1

    if skipped:
        skipped_text = ", ".join(f"{actor}: {count}" for actor, count in skipped.items())
        print(f"(capped media rows per actor; skipped {skipped_text})")
    return capped


def parse_score_log(log_path: Path) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "top_feature_rows": 0,
            "positive_rows": 0,
            "negative_rows": 0,
            "sum_abs_shap": 0.0,
            "users": set(),
            "rating_keys": set(),
        }
    )
    if not log_path.exists():
        return {}

    current_user = None
    rank_re = re.compile(r"Rank\s+\d+:\s+(\d+)\s+.*?[-\u2014]\s+(.*)")
    actor_feature_re = re.compile(r"\b(actor_[^()]+?)\s+\(([+-]?\d+(?:\.\d+)?)\)")
    user_re = re.compile(r"Fetching unwatched media for\s+(.+?)\.\.\.")

    for line in log_path.read_text(errors="ignore").splitlines():
        user_match = user_re.search(line)
        if user_match:
            current_user = user_match.group(1).strip()

        rank_match = rank_re.search(line)
        if not rank_match:
            continue

        rating_key = rank_match.group(1)
        features_text = rank_match.group(2)
        for feature_match in actor_feature_re.finditer(features_text):
            feature_name = feature_match.group(1).strip()
            shap_value = float(feature_match.group(2))
            actor_name = feature_name.removeprefix("actor_")
            actor_stats = stats[actor_name]
            actor_stats["top_feature_rows"] += 1
            actor_stats["positive_rows"] += int(shap_value > 0)
            actor_stats["negative_rows"] += int(shap_value < 0)
            actor_stats["sum_abs_shap"] += abs(shap_value)
            actor_stats["rating_keys"].add(rating_key)
            if current_user:
                actor_stats["users"].add(current_user)

    return stats


def shap_log_rows(log_stats: dict[str, dict[str, Any]], actors: list[str] | None = None) -> list[dict[str, Any]]:
    selected = set(actors or [])
    rows = []
    for actor_name, stats in log_stats.items():
        if selected and actor_name not in selected:
            continue
        count = stats["top_feature_rows"]
        rows.append(
            {
                "actor_name": actor_name,
                "top_feature_rows": count,
                "distinct_users": len(stats["users"]),
                "distinct_items": len(stats["rating_keys"]),
                "positive_rows": stats["positive_rows"],
                "negative_rows": stats["negative_rows"],
                "avg_abs_shap": stats["sum_abs_shap"] / count if count else None,
            }
        )
    rows.sort(key=lambda row: (row["top_feature_rows"], row["avg_abs_shap"] or 0), reverse=True)
    return rows


def load_model_actor_info(model_path: Path) -> tuple[dict[str, float], list[str], str | None]:
    if not model_path.exists():
        return {}, [], f"Model file not found: {model_path}"
    try:
        import joblib  # type: ignore
    except Exception as exc:
        return {}, [], f"Could not import joblib to inspect {model_path}: {exc}"

    try:
        model = joblib.load(model_path)
        booster = model.get_booster()
        feature_names = [str(name) for name in (booster.feature_names or [])]
        actor_features = [name for name in feature_names if name.startswith("actor_")]
        gain = booster.get_score(importance_type="gain")
        actor_gain = {
            feature.removeprefix("actor_"): float(gain[feature])
            for feature in actor_features
            if feature in gain
        }
        return actor_gain, actor_features, None
    except Exception as exc:
        return {}, [], f"Could not inspect model {model_path}: {exc}"


def add_suspicion_fields(
    rows: list[dict[str, Any]],
    shap_stats: dict[str, dict[str, Any]],
    model_gain: dict[str, float],
) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        row = dict(row)
        media_count = int(row.get("media_item_count") or 0)
        episode_count = int(row.get("episode_count") or 0)
        distinct_count = int(row.get("distinct_show_or_movie_count") or 0)
        top_show_count = int(row.get("top_show_item_count") or 0)
        training_rows = int(row.get("training_rows") or 0)
        positive_rate = row.get("positive_rate")
        positive_rate_float = float(positive_rate) if positive_rate is not None else None
        actor_name = row.get("actor_name", "")
        shap_count = int(shap_stats.get(actor_name, {}).get("top_feature_rows", 0))
        gain = model_gain.get(actor_name)

        episode_ratio = episode_count / media_count if media_count else 0.0
        top_show_ratio = top_show_count / media_count if media_count else 0.0
        reasons = []
        score = 0.0

        if media_count >= 10:
            reasons.append("many media rows")
            score += 1.0
        if episode_ratio >= 0.80:
            reasons.append("mostly episodes")
            score += 2.0
        if distinct_count and distinct_count <= 2 and media_count >= 10:
            reasons.append("few distinct shows/movies")
            score += 2.0
        if top_show_ratio >= 0.75 and media_count >= 10:
            reasons.append("top title concentration")
            score += 2.0
        if training_rows >= 5 and positive_rate_float is not None:
            if positive_rate_float >= 0.80:
                reasons.append("positive-label skew")
                score += 1.0
            elif positive_rate_float <= 0.20:
                reasons.append("negative-label skew")
                score += 1.0
        if shap_count:
            reasons.append("appears in logged top SHAP")
            score += min(2.0, shap_count / 25.0)
        if gain:
            reasons.append("used by XGBoost splits")
            score += 1.0

        row["positive_rate"] = positive_rate_float
        row["logged_top_shap_rows"] = shap_count
        row["actor_feature_gain"] = gain
        row["suspicion_score"] = score
        row["suspicious_reason"] = "; ".join(reasons) or "weak signal"
        enriched.append(row)

    enriched.sort(
        key=lambda row: (
            row["suspicion_score"],
            row["logged_top_shap_rows"],
            row["media_item_count"],
        ),
        reverse=True,
    )
    return enriched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only actor feature leakage/show-proxy diagnostics."
    )
    parser.add_argument(
        "--actors",
        default="",
        help='Comma-separated actor names, for example "Drew Powell,Michael McKean".',
    )
    parser.add_argument(
        "--top-suspicious",
        type=int,
        default=25,
        help="Number of suspicious actors to print. Use 0 to skip this section.",
    )
    parser.add_argument(
        "--min-media-rows",
        type=int,
        default=10,
        help="Minimum movie/episode rows for suspicious-actor ranking.",
    )
    parser.add_argument(
        "--max-items-per-actor",
        type=int,
        default=40,
        help="Maximum raw media rows to print per named actor. Use 0 for no cap.",
    )
    parser.add_argument(
        "--log-file",
        default=str(REPO_ROOT / "logs" / "pipeline.log"),
        help="Score log to parse for printed top SHAP actor features.",
    )
    parser.add_argument(
        "--model-path",
        default=str(REPO_ROOT / "xgb_model.pkl"),
        help="Trained XGBoost model path to inspect for actor feature names/gain.",
    )
    args = parser.parse_args()

    load_dotenv()
    actors = parse_actor_list(args.actors)
    log_path = Path(args.log_file)
    model_path = Path(args.model_path)

    conn = connect_db()
    try:
        conn.set_session(readonly=True, autocommit=True)
    except Exception:
        pass

    try:
        shap_stats = parse_score_log(log_path)
        model_gain, actor_features, model_error = load_model_actor_info(model_path)

        print_section("Model Actor Features")
        if model_error:
            print(model_error)
        print(f"Actor feature count in model: {len(actor_features)}")
        if actor_features:
            print_table(
                [
                    {
                        "actor_feature": feature,
                        "xgb_gain": model_gain.get(feature.removeprefix("actor_")),
                    }
                    for feature in actor_features
                ],
                ["actor_feature", "xgb_gain"],
            )

        print_section("Top Logged Actor SHAP Features")
        print_table(
            shap_log_rows(shap_stats),
            [
                "actor_name",
                "top_feature_rows",
                "distinct_users",
                "distinct_items",
                "positive_rows",
                "negative_rows",
                "avg_abs_shap",
            ],
            limit=max(1, args.top_suspicious or 25),
        )

        if actors:
            print_section("Named Actor Media Rows")
            media_rows = fetch_all(conn, TARGET_MEDIA_SQL, (actors,))
            capped_rows = rows_capped_by_actor(media_rows, args.max_items_per_actor)
            print_table(
                capped_rows,
                [
                    "actor_name",
                    "rating_key",
                    "title",
                    "media_type",
                    "parent_title",
                    "grandparent_title",
                    "year",
                ],
            )

            print_section("Named Actor Model-Relevant Counts")
            print_table(
                fetch_all(conn, ACTOR_MODEL_MEDIA_SUMMARY_SQL, (actors,)),
                [
                    "actor_name",
                    "media_item_count",
                    "episode_count",
                    "movie_count",
                    "distinct_show_or_movie_count",
                ],
            )

            print_section("Named Actor Show Concentration")
            print_table(
                fetch_all(conn, ACTOR_SHOW_CONCENTRATION_SQL, (actors,)),
                [
                    "actor_name",
                    "show_or_movie",
                    "item_count",
                    "episode_count",
                    "movie_count",
                ],
            )

            print_section("Named Actor Training Labels")
            print_table(
                fetch_all(conn, ACTOR_TRAINING_LABEL_SQL, (actors,)),
                [
                    "actor_name",
                    "training_rows",
                    "training_user_count",
                    "training_item_count",
                    "positive_training_rows",
                    "negative_training_rows",
                    "positive_rate",
                    "positive_weight",
                    "negative_weight",
                ],
            )

            print_section("Named Actor Engagement Breakdown")
            print_table(
                fetch_all(conn, ACTOR_ENGAGEMENT_SQL, (actors,)),
                ["actor_name", "label", "engagement_type", "training_rows"],
            )

            print_section("Named Actor Logged Top SHAP Features")
            print_table(
                shap_log_rows(shap_stats, actors),
                [
                    "actor_name",
                    "top_feature_rows",
                    "distinct_users",
                    "distinct_items",
                    "positive_rows",
                    "negative_rows",
                    "avg_abs_shap",
                ],
            )

        print_section("Database SHAP Actor Feature Support")
        if column_exists(conn, "shap_impact", "feature_name"):
            print_table(fetch_all(conn, SHAP_ACTOR_FEATURE_SQL, (args.top_suspicious or 25,)))
        else:
            print(
                "shap_impact does not store feature_name, only embedding dimensions. "
                "Direct actor_* SHAP frequencies are available from score logs only unless "
                "scoring starts persisting non-embedding feature names."
            )

        if args.top_suspicious > 0:
            print_section("Top Suspicious Actor Features")
            suspicious_rows = fetch_all(
                conn,
                SUSPICIOUS_ACTORS_SQL,
                (max(1, args.min_media_rows),),
            )
            suspicious_rows = add_suspicion_fields(suspicious_rows, shap_stats, model_gain)
            print_table(
                suspicious_rows,
                [
                    "actor_name",
                    "media_item_count",
                    "episode_count",
                    "movie_count",
                    "distinct_show_or_movie_count",
                    "top_show_or_movie",
                    "top_show_item_count",
                    "positive_training_rows",
                    "negative_training_rows",
                    "positive_rate",
                    "logged_top_shap_rows",
                    "actor_feature_gain",
                    "suspicion_score",
                    "suspicious_reason",
                ],
                limit=args.top_suspicious,
            )

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
