from dotenv import load_dotenv
load_dotenv()

import psycopg2
import pandas as pd
from datetime import datetime
from pgvector.psycopg2 import register_vector
import argparse
import os
import csv
from gpt_utils import (
    call_gpt_for_label,
    get_top_media_for_dimension,
    get_top_users_for_dimension,
    get_media_metadata,
    get_user_watch_history,
    generate_summary_text
)


DB_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn

def get_top_unlabeled_dimensions(limit=25, dim_type='media'):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT dimension FROM embedding_labels")
    labeled = {row[0] for row in cur.fetchall()}

    if dim_type == 'media':
        dim_range = (768, 1536)
    elif dim_type == 'user':
        dim_range = (0, 768)
    else:
        dim_range = (0, 1536)

    cur.execute("""
        SELECT dimension, COUNT(*) as usage_count
        FROM shap_impact
        GROUP BY dimension
        ORDER BY usage_count DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [(dim, count) for dim, count in rows if dim not in labeled and dim_range[0] <= dim < dim_range[1]]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpt_label", action="store_true")
    parser.add_argument("--export_csv", type=str)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--save_label", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--dim_type", choices=["media", "user", "all"], default="all")
    args = parser.parse_args()

    csv_rows = []

    conn = connect_db()
    cur = conn.cursor()

    shap_usage_counts = {}
    cur.execute("SELECT dimension, COUNT(*) FROM shap_impact GROUP BY dimension")
    for dim, count in cur.fetchall():
        shap_usage_counts[dim] = count

    top_dims = get_top_unlabeled_dimensions(args.limit, args.dim_type)

    for dimension, _ in top_dims:
        gpt_label = None
        mode = "user" if dimension < 768 else "media"

        if mode == "media":
            top_ids = get_top_media_for_dimension(dimension)
            df = get_media_metadata(top_ids)
        else:
            top_ids = get_top_users_for_dimension(dimension)
            df = get_user_watch_history(top_ids)

        summary = generate_summary_text(df, dimension)

        if args.gpt_label:
            gpt_label = call_gpt_for_label(summary)
            print(f"🧠 {mode.title()} dim {dimension} labeled as: {gpt_label}")

        if args.export_csv:
            usage_count = shap_usage_counts.get(dimension, 0)
            csv_rows.append({
                "dimension": dimension,
                "mode": mode,
                "summary": summary,
                "gpt_label": gpt_label or '',
                "usage_count": usage_count
            })

        if gpt_label and args.save_label:
            cur.execute(
                "INSERT INTO embedding_labels (dimension, label, created_at) VALUES (%s, %s, NOW())",
                (dimension, gpt_label)
            )

    if args.export_csv and csv_rows:
        with open(args.export_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["dimension", "mode", "summary", "gpt_label", "usage_count"])
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"✅ CSV export completed: {args.export_csv}")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
