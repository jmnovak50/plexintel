from dotenv import load_dotenv

load_dotenv()

import argparse
import csv
import math

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
    "label",
    "gpt_label",
    "label_confidence",
    "label_type",
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


def _blank_coverage_fields(selection_mode: str) -> dict:
    return {
        "selection_mode": selection_mode,
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
            END AS stats_source
        FROM recommendations r
        JOIN shap_impact si
          ON si.user_id = r.username
         AND si.rating_key = r.rating_key
        LEFT JOIN embedding_labels candidate_label
          ON candidate_label.dimension = si.dimension
        LEFT JOIN shap_dimension_stats_current s
          ON s.dimension = si.dimension
        WHERE si.shap_value > 0
          AND candidate_label.dimension IS NULL
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
                AND el_existing.label IS NOT NULL
          )
        ORDER BY si.dimension ASC, r.username ASC, r.rating_key ASC
    """
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
            'coverage_raw' AS stats_source
        FROM recommendations r
        JOIN shap_impact si
          ON si.user_id = r.username
         AND si.rating_key = r.rating_key
        LEFT JOIN embedding_labels candidate_label
          ON candidate_label.dimension = si.dimension
        WHERE si.shap_value > 0
          AND candidate_label.dimension IS NULL
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
                AND el_existing.label IS NOT NULL
          )
        ORDER BY si.dimension ASC, r.username ASC, r.rating_key ASC
    """
    cur.execute(fallback_query, (dim_min, dim_max))
    return cur.fetchall()


def _coverage_row_to_dict(row) -> dict:
    if isinstance(row, dict):
        return row

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
    ]
    return dict(zip(fields, row))


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

    eligible = summary.get("eligible_unlabeled_recommendations") or 0
    potential = summary.get("potential_unlocked_recommendations") or 0
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
    print(
        "Rank | Dimension | Marginal Cards Unlocked | Cumulative Cards | "
        "Weighted Unlock Score | Aggregate Importance Score",
        flush=True,
    )
    for rank, stat in enumerate(selected_dimensions, start=1):
        if stat.get("selection_mode") not in {"coverage", "hybrid_coverage"}:
            continue
        print(
            f"{rank} | {stat['dimension']} | {stat.get('marginal_unlock_count', '')} | "
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
        choices=["importance", "coverage", "hybrid"],
        default="importance",
        help="Automatic dimension selection strategy",
    )
    parser.add_argument(
        "--coverage_share",
        type=float,
        default=0.80,
        help="Hybrid-mode share of dimensions to select through coverage ranking",
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
        scope = "all dimensions" if args.refresh_existing else "unlabeled dimensions"
        print(f"ℹ️ No {scope} selected for labeling.", flush=True)

    for dim_stats in top_dims:
        dimension = dim_stats["dimension"]
        mode, positive_df, negative_df = _fetch_dimension_samples(dimension)
        prompt_bundle = build_dimension_prompt(
            dimension,
            positive_df,
            negative_df,
            dimension_mode=mode,
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

        if args.export_csv:
            csv_rows.append(
                {
                    "dimension": dimension,
                    "selection_mode": dim_stats.get("selection_mode", args.selection_mode),
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
                    "label": generated_label,
                    "gpt_label": generated_label,
                    "label_confidence": label_result.get("label_confidence", ""),
                    "label_type": label_result.get("label_type", ""),
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

        if args.save_label and _should_persist_label(generated_label):
            cur.execute(
                """
                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at
                """,
                (dimension, generated_label),
            )
        conn.commit()

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
