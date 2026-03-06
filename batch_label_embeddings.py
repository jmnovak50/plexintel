from dotenv import load_dotenv

load_dotenv()

import argparse
import csv
import os

import psycopg2
from pgvector.psycopg2 import register_vector

from gpt_utils import (
    DEFAULT_FETCH_ITEMS,
    UNCLEAR_LABEL,
    build_dimension_prompt,
    call_llm_for_label_result,
    get_bottom_media_for_dimension,
    get_bottom_users_for_dimension,
    get_media_metadata,
    get_top_media_for_dimension,
    get_top_users_for_dimension,
    get_user_watch_history,
    resolve_label_backend,
)


DB_URL = os.getenv("DATABASE_URL")


def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn


def _get_dimension_range(dim_type):
    if dim_type == "media":
        return (768, 1536)
    if dim_type == "user":
        return (0, 768)
    return (0, 1536)


def _should_persist_label(label: str) -> bool:
    return bool(label and label != UNCLEAR_LABEL)


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


def get_top_unlabeled_dimensions(cur, limit=25, dim_type="media"):
    cur.execute("SELECT dimension FROM embedding_labels")
    labeled = {row[0] for row in cur.fetchall()}
    dim_min, dim_max = _get_dimension_range(dim_type)

    ranked_stats = get_ranked_dimension_stats(cur)
    filtered = [
        stat for stat in ranked_stats
        if stat["dimension"] not in labeled and dim_min <= stat["dimension"] < dim_max
    ]
    return filtered[:limit]


def _fetch_dimension_samples(dimension: int):
    if dimension < 768:
        positive_ids = get_top_users_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
        negative_ids = get_bottom_users_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
        return "user", get_user_watch_history(positive_ids), get_user_watch_history(negative_ids)

    positive_ids = get_top_media_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
    negative_ids = get_bottom_media_for_dimension(dimension, top_n=DEFAULT_FETCH_ITEMS)
    return "media", get_media_metadata(positive_ids), get_media_metadata(negative_ids)


def _default_label_result(skipped_reason: str = "") -> dict:
    if skipped_reason:
        return {
            "label": UNCLEAR_LABEL,
            "explanation": skipped_reason,
            "evidence": ["", "", ""],
        }
    return {
        "label": "",
        "explanation": "",
        "evidence": ["", "", ""],
    }


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
    args = parser.parse_args()

    csv_rows = []
    provider_name = None
    model_name = None
    should_call_model = args.label and not args.dry_run

    if args.label:
        provider_name, model_name = resolve_label_backend(args.label_provider, args.label_model)

    conn = connect_db()
    cur = conn.cursor()
    top_dims = get_top_unlabeled_dimensions(cur, args.limit, args.dim_type)

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
                    "mode": mode,
                    "summary": prompt_bundle["summary"],
                    "prompt_text": prompt_bundle["prompt_text"],
                    "label_provider": provider_name or "",
                    "label_model": model_name or "",
                    "label": generated_label,
                    "gpt_label": generated_label,
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

    if args.export_csv and csv_rows:
        with open(args.export_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "dimension",
                    "mode",
                    "summary",
                    "prompt_text",
                    "label_provider",
                    "label_model",
                    "label",
                    "gpt_label",
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
                ],
            )
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"✅ CSV export completed: {args.export_csv}", flush=True)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
