from dotenv import load_dotenv
import numpy as np
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from pgvector import Vector

from api.db.connection import connect_db
from api.db.schema import ensure_app_schema
from api.services.app_settings import get_setting_value

# ✅ Load environment variables
load_dotenv()

EMBEDDING_DIMENSION = 768
ENGAGEMENT_THRESHOLD = get_setting_value("user_embeddings.engagement_threshold", default=0.5)


def connect():
    conn = connect_db()
    register_vector(conn)
    return conn


def fetch_user_watch_history(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                wh.username,
                wh.rating_key,
                wh.played_duration,
                l.duration
            FROM watch_history wh
            JOIN library l ON wh.rating_key = l.rating_key
            WHERE l.duration > 0
              AND wh.played_duration IS NOT NULL
              AND (wh.played_duration::float / (l.duration / 1000.0)) > %s
        """, (ENGAGEMENT_THRESHOLD,))
        return cur.fetchall()


def build_user_embeddings(watch_history, conn):
    user_vectors = {}

    for record in watch_history:
        username = record['username']
        rating_key = record['rating_key']

        with conn.cursor() as cur:
            cur.execute("SELECT embedding FROM media_embeddings WHERE rating_key = %s", (rating_key,))
            row = cur.fetchone()
            if not row:
                continue
            embedding = row[0]
            if username not in user_vectors:
                user_vectors[username] = []
            user_vectors[username].append(np.array(embedding))

    with conn.cursor() as cur:
        for username, vectors in user_vectors.items():
            if len(vectors) == 0:
                continue

            avg_vector = np.mean(vectors, axis=0)
            norm = np.linalg.norm(avg_vector)
            print(f"✅ {username} — vectors: {len(vectors)} — norm: {norm:.4f}")

            cur.execute("""
                INSERT INTO user_embeddings (username, embedding)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET embedding = EXCLUDED.embedding
            """, (username, Vector(avg_vector.tolist())))

    conn.commit()


def main():
    conn = connect()

    print("🔍 Fetching engaged watch history...")
    watch_history = fetch_user_watch_history(conn)
    print(f"🎬 Found {len(watch_history)} engaged watch events")

    build_user_embeddings(watch_history, conn)

    conn.close()


if __name__ == "__main__":
    ensure_app_schema()
    main()
