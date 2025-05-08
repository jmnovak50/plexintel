# explore_embedding_dimension.py

import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import argparse

# DB connection
conn = psycopg2.connect("dbname=plexintel user=jmnovak password=brigid host=localhost")
register_vector(conn)
cursor = conn.cursor()

# Parse CLI
parser = argparse.ArgumentParser()
parser.add_argument("--dim", type=int, required=True, help="Embedding dimension to explore (e.g. 531)")
parser.add_argument("--limit", type=int, default=20, help="How many top media items to return")
args = parser.parse_args()

# Pandas output settings
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 0)

print(f"🔍 Exploring dimension emb_{args.dim}...")

# Query: get top media for that embedding dimension, including genres, actors, and directors
cursor.execute(f"""
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

rows = cursor.fetchall()
df = pd.DataFrame(rows, columns=[
    "rating_key", "title", "year", "media_type", "show",
    "genres", "actors", "directors", "embedding"
])

# Validate dimension
vector_dim = len(df["embedding"].iloc[0])
if args.dim >= vector_dim:
    raise ValueError(f"⚠️ Embedding dimension {args.dim} is out of bounds (max = {vector_dim - 1})")

# Add dimension column
df[f"emb_{args.dim}"] = df["embedding"].apply(lambda v: v[args.dim])

# Show top N media sorted by the dimension value
columns_to_show = ["title", "show", "year", "media_type", "genres", "actors", "directors", f"emb_{args.dim}"]
print(df.sort_values(f"emb_{args.dim}", ascending=False).head(args.limit)[columns_to_show])

cursor.close()
conn.close()
