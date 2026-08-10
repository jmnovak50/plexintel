from dotenv import load_dotenv
import numpy as np
from pgvector.psycopg2 import register_vector
from pgvector import Vector

from api.db.connection import connect_db
from api.db.schema import ensure_app_schema
from api.services.app_settings import get_setting_value
from user_profile_embeddings import build_user_profiles, fetch_profile_title_rows

# ✅ Load environment variables
load_dotenv()

ENGAGEMENT_THRESHOLD = get_setting_value("user_embeddings.engagement_threshold", default=0.5)


def connect():
    conn = connect_db()
    register_vector(conn)
    return conn


def fetch_user_watch_history(conn):
    return fetch_profile_title_rows(conn)


def build_user_embeddings(watch_history, conn):
    profiles = build_user_profiles(
        watch_history,
        engagement_threshold=ENGAGEMENT_THRESHOLD,
    )

    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_embeddings")
        print("🧹 Cleared existing user embeddings before rebuild")

        for username, profile in profiles.items():
            avg_vector = profile.mean
            norm = np.linalg.norm(avg_vector)
            print(f"✅ {username} — titles: {profile.count} — norm: {norm:.4f}")

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
    print(f"🎬 Evaluated {len(watch_history)} unique watched user/title pairs")

    build_user_embeddings(watch_history, conn)

    conn.close()


if __name__ == "__main__":
    ensure_app_schema()
    main()
