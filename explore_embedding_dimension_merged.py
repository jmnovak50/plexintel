import argparse
import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import matplotlib.pyplot as plt

def connect_db():
    conn = psycopg2.connect(
        dbname="plexintel",
        user="jmnovak",
        password="brigid",
        host="localhost"
    )
    register_vector(conn)
    return conn

def fetch_embeddings_with_metadata(cur, dim):
    cur.execute(f"""
        SELECT m.rating_key, m.title, m.year, m.media_type, m.show_title,
               COALESCE(g.genre_tags, '') AS genre_tags,
               COALESCE(a.actor_names, '') AS actor_names,
               COALESCE(d.director_names, '') AS director_names,
               COALESCE(e.embedding, NULL) AS embedding
        FROM media_embeddings e
        JOIN library m ON m.rating_key = e.rating_key

        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = m.rating_key

        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_names
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = m.rating_key

        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_names
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
        ) d ON d.media_id = m.rating_key
    """)
    rows = cur.fetchall()
    columns = ["rating_key", "title", "year", "media_type", "show",
               "genres", "actors", "directors", "embedding"]
    return pd.DataFrame(rows, columns=columns)

def fetch_embeddings_basic(cur, table, id_col):
    cur.execute(f"SELECT {id_col}, embedding FROM {table}")
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=[id_col, "embedding"])

def main():
    parser = argparse.ArgumentParser(description="Explore specific embedding dimensions.")
    parser.add_argument("--source", choices=["media", "user"], required=True,
                        help="Source of embeddings: 'media' or 'user'")
    parser.add_argument("--dimension", type=int, required=True,
                        help="Dimension index to explore (e.g. 531)")
    parser.add_argument("--limit", type=int, default=20,
                        help="How many top records to return")
    parser.add_argument("--export_csv", action="store_true",
                        help="Export the results to a CSV file")
    parser.add_argument("--with_metadata", action="store_true",
                        help="Include genres, actors, and directors (media only)")
    args = parser.parse_args()

    conn = connect_db()
    cur = conn.cursor()

    if args.source == "media":
        table = "media_embeddings"
        id_col = "rating_key"
    else:
        table = "user_embeddings"
        id_col = "username"

    # Get sample embedding to determine vector size
    cur.execute(f"SELECT embedding FROM {table} LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise ValueError(f"No embeddings found in {table}")
    vector_dim = len(row[0])
    if args.dimension >= vector_dim:
        raise ValueError(f"⚠️ Dimension {args.dimension} out of bounds (max = {vector_dim - 1})")

    # Fetch embeddings
    if args.source == "media" and args.with_metadata:
        df = fetch_embeddings_with_metadata(cur, args.dimension)
    else:
        df = fetch_embeddings_basic(cur, table, id_col)

    df[f"emb_{args.dimension}"] = df["embedding"].apply(lambda v: v[args.dimension])

    # Show top N sorted by dimension
    sort_df = df.sort_values(f"emb_{args.dimension}", ascending=False)
    top_df = sort_df.head(args.limit)

    # Output core info
    print("📊 Top items by embedding dimension:")
    print(top_df)

    # Stats
    print("\n📈 Dimension statistics:")
    print(df[f"emb_{args.dimension}"].describe())

    # Histogram
    plt.hist(df[f"emb_{args.dimension}"], bins=50)
    plt.title(f"Distribution of Dimension {args.dimension} in {table}")
    plt.xlabel("Value")
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # Optional CSV export
    if args.export_csv:
        filename = f"{args.source}_emb_{args.dimension}_analysis.csv"
        df.to_csv(filename, index=False)
        print(f"✅ Exported results to {filename}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
