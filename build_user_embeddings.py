import os
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from pgvector import Vector
import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Connect to PostgreSQL using env vars
db_conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT", 5432)
)
register_vector(db_conn)
cursor = db_conn.cursor(cursor_factory=RealDictCursor)

# Detect the vector dimension dynamically from first embedding
cursor.execute("SELECT embedding FROM media_embeddings WHERE embedding IS NOT NULL LIMIT 1")
example = cursor.fetchone()
if example is None or example['embedding'] is None or len(example['embedding']) == 0:
    raise ValueError("❌ No embeddings found in media_embeddings to determine vector dimension.")

vector_dim = len(example['embedding'])
print(f"🧠 Detected embedding vector dimension: {vector_dim}")

# Get list of unique users
cursor.execute("SELECT DISTINCT username FROM watch_history;")
users = cursor.fetchall()

for user_row in users:
    username = user_row['username']
    print(f"\n👤 Processing user: {username}")

    # Get engagement + rewatch count per rating_key
    cursor.execute("""
        SELECT
            wh.rating_key,
            COUNT(*) AS watch_count,
            MAX(wh.played_duration::float / NULLIF(lib.duration, 0)) AS engagement_ratio
        FROM watch_history wh
        JOIN library lib ON wh.rating_key = lib.rating_key
        WHERE wh.username = %s
        GROUP BY wh.rating_key
    """, (username,))

    rows = cursor.fetchall()
    engaged_vectors = []

    for row in rows:
        rating_key = row['rating_key']
        engagement_ratio = row['engagement_ratio'] or 0
        watch_count = row['watch_count']

        if engagement_ratio > 0.5 or watch_count >= 5:
            cursor.execute("SELECT embedding FROM media_embeddings WHERE rating_key = %s", (rating_key,))
            emb_result = cursor.fetchone()
            if emb_result and emb_result['embedding'] is not None:
                vec = np.array(emb_result['embedding'])
                if len(vec) == vector_dim:
                    engaged_vectors.append(vec)
                else:
                    print(f"[WARN] Skipping mismatched vector length for {rating_key}")

    if len(engaged_vectors) == 0 and len(rows) > 0:
        best = sorted(rows, key=lambda r: (r['watch_count'], r['engagement_ratio'] or 0), reverse=True)[0]
        rating_key = best['rating_key']
        cursor.execute("SELECT embedding FROM media_embeddings WHERE rating_key = %s", (rating_key,))
        fallback = cursor.fetchone()
        if fallback and fallback['embedding'] is not None:
            vec = np.array(fallback['embedding'])
            if len(vec) == vector_dim:
                engaged_vectors.append(vec)
            print(f"[FALLBACK] {username}: using most-watched or engaged media item (rating_key={rating_key})")

    if len(engaged_vectors) == 0:
        print(f"[SKIP] {username}: no qualifying watched media (engagement or rewatch count)")
        continue

    user_embedding = np.mean(engaged_vectors, axis=0)

    cursor.execute("""
        INSERT INTO user_embeddings (username, embedding)
        VALUES (%s, %s)
        ON CONFLICT (username) DO UPDATE SET embedding = EXCLUDED.embedding;
    """, (username, Vector(user_embedding.tolist())))

    db_conn.commit()
    print(f"✅ Embedded user '{username}' with {len(engaged_vectors)} media items")

cursor.close()
db_conn.close()
print("\n🚀 Done generating user embeddings.")
