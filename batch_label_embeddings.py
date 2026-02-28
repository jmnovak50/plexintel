from dotenv import load_dotenv
load_dotenv()

import psycopg2
from pgvector.psycopg2 import register_vector
import argparse
import os
import csv
from gpt_utils import (
    call_llm_for_label,
    resolve_label_backend,
    get_top_media_for_dimension,
    get_top_users_for_dimension,
    get_media_metadata,
    get_user_watch_history,
    generate_summary_text
)


DB_URL = os.getenv("DATABASE_URL")

def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn

def _get_dimension_range(dim_type):
    if dim_type == 'media':
        return (768, 1536)
    if dim_type == 'user':
        return (0, 768)
    return (0, 1536)

def get_ranked_dimension_stats(cur):
    """
    Prefer the current-run aggregate SHAP table. Fall back to raw shap_impact counts if the
    aggregate table is missing or empty.
    """
    try:
        cur.execute("""
            SELECT
                dimension,
                usage_count,
                sum_abs_shap,
                avg_abs_shap,
                combined_score,
                user_count
            FROM shap_dimension_stats_current
            ORDER BY combined_score DESC, sum_abs_shap DESC, usage_count DESC
        """)
        rows = cur.fetchall()
        if rows:
            stats = []
            for dim, usage_count, sum_abs_shap, avg_abs_shap, combined_score, user_count in rows:
                stats.append({
                    "dimension": dim,
                    "usage_count": int(usage_count or 0),
                    "sum_abs_shap": float(sum_abs_shap or 0.0),
                    "avg_abs_shap": float(avg_abs_shap or 0.0),
                    "combined_score": float(combined_score or 0.0),
                    "user_count": int(user_count or 0),
                    "stats_source": "aggregate",
                })
            return stats
        print("⚠️ shap_dimension_stats_current is empty; falling back to raw shap_impact counts.")
    except Exception as e:
        cur.connection.rollback()
        print(f"⚠️ Could not read shap_dimension_stats_current ({e}); falling back to raw shap_impact counts.")

    cur.execute("""
        SELECT dimension, COUNT(*) as usage_count
        FROM shap_impact
        GROUP BY dimension
        ORDER BY usage_count DESC
    """)
    rows = cur.fetchall()
    stats = []
    for dim, usage_count in rows:
        stats.append({
            "dimension": dim,
            "usage_count": int(usage_count or 0),
            "sum_abs_shap": 0.0,
            "avg_abs_shap": 0.0,
            "combined_score": 0.0,
            "user_count": 0,
            "stats_source": "raw_count_fallback",
        })
    return stats

def get_top_unlabeled_dimensions(cur, limit=25, dim_type='media'):
    cur.execute("SELECT dimension FROM embedding_labels")
    labeled = {row[0] for row in cur.fetchall()}
    dim_min, dim_max = _get_dimension_range(dim_type)

    ranked_stats = get_ranked_dimension_stats(cur)
    filtered = [
        stat for stat in ranked_stats
        if stat["dimension"] not in labeled and dim_min <= stat["dimension"] < dim_max
    ]
    return filtered[:limit]

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

    if args.label:
        provider_name, model_name = resolve_label_backend(args.label_provider, args.label_model)

    conn = connect_db()
    cur = conn.cursor()

    top_dims = get_top_unlabeled_dimensions(cur, args.limit, args.dim_type)

    for dim_stats in top_dims:
        dimension = dim_stats["dimension"]
        generated_label = None
        mode = "user" if dimension < 768 else "media"

        if mode == "media":
            top_ids = get_top_media_for_dimension(dimension)
            df = get_media_metadata(top_ids)
        else:
            top_ids = get_top_users_for_dimension(dimension)
            df = get_user_watch_history(top_ids)

        summary = generate_summary_text(df, dimension)

        if args.label:
            generated_label = call_llm_for_label(summary, provider=provider_name, model=model_name)
            print(
                f"🧠 {mode.title()} dim {dimension} labeled via "
                f"{provider_name}:{model_name} as: {generated_label}"
            )

        if args.export_csv:
            csv_rows.append({
                "dimension": dimension,
                "mode": mode,
                "summary": summary,
                "label_provider": provider_name or "",
                "label_model": model_name or "",
                "label": generated_label or "",
                "gpt_label": generated_label or "",
                "usage_count": dim_stats["usage_count"],
                "sum_abs_shap": dim_stats.get("sum_abs_shap", 0.0),
                "avg_abs_shap": dim_stats.get("avg_abs_shap", 0.0),
                "combined_score": dim_stats.get("combined_score", 0.0),
                "user_count": dim_stats.get("user_count", 0),
                "stats_source": dim_stats.get("stats_source", "unknown"),
            })

        if generated_label and args.save_label:
            cur.execute(
                "INSERT INTO embedding_labels (dimension, label, created_at) VALUES (%s, %s, NOW())",
                (dimension, generated_label)
            )

    if args.export_csv and csv_rows:
        with open(args.export_csv, 'w', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "dimension",
                    "mode",
                    "summary",
                    "label_provider",
                    "label_model",
                    "label",
                    "gpt_label",
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
        print(f"✅ CSV export completed: {args.export_csv}")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
