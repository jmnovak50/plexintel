# reverse_lookup_embedding.py
# Show top embedding dimensions for a given media item, with labels if available

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import argparse
import os

DB_URL = os.getenv("DATABASE_URL")


def connect():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn


def get_embedding(rating_key):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT embedding FROM media_embeddings WHERE rating_key = %s", (rating_key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise ValueError("No embedding found for rating_key")
    return row[0]


def get_labels_for_dimensions(dimensions):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT dimension, label
        FROM embedding_labels
        WHERE dimension = ANY(%s)
        """,
        (dimensions,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {dim: label for dim, label in rows}


def show_top_dimensions(embedding, top_n=10):
    base_dim_offset = 768  # adjust for media embedding position in model input
    df = pd.DataFrame({
        "dimension": [base_dim_offset + i for i in range(len(embedding))],
        "value": embedding
    })
    df = df.reindex(df.value.abs().sort_values(ascending=False).index).head(top_n)
    labels = get_labels_for_dimensions(df["dimension"].tolist())
    df["label"] = df["dimension"].map(lambda d: labels.get(d, "[Unlabeled]"))
    print("\n🔍 Top dimensions for this media item:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rating_key", type=int, required=True, help="Media rating_key")
    parser.add_argument("--top_n", type=int, default=10, help="Number of top dimensions to show")
    args = parser.parse_args()

    emb = get_embedding(args.rating_key)
    show_top_dimensions(emb, args.top_n)
