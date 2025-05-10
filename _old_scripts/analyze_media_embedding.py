# analyze_media_embedding.py
# Explore which embedding dimensions are most activated for a specific media item

import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import argparse

DB_URL = "postgresql://jmnovak:brigid@localhost:5432/plexintel"


def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn


def fetch_media_embedding(rating_key):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT embedding FROM media_embeddings WHERE rating_key = %s", (rating_key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise ValueError(f"No embedding found for rating_key {rating_key}")
    return row[0]  # this should be a list/vector


def show_top_dimensions(embedding, top_n=10):
    df = pd.DataFrame({
        "dimension": list(range(len(embedding))),
        "value": embedding
    })
    df = df.sort_values("value", ascending=False).head(top_n)
    print("\n🔍 Top activated embedding dimensions:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rating_key", type=int, required=True, help="Media rating_key to analyze")
    parser.add_argument("--top_n", type=int, default=10, help="Top N dimensions to display")
    args = parser.parse_args()

    embedding = fetch_media_embedding(args.rating_key)
    show_top_dimensions(embedding, args.top_n)