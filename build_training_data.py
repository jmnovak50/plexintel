from dotenv import load_dotenv
import os
import psycopg2
import numpy as np
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
from pgvector import Vector

# ✅ Load environment variables
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

ENGAGEMENT_THRESHOLD = 0.7  # Label threshold

def connect():
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)  # ✅ This tells psycopg2 how to handle Vector objects
    return conn

import ast

def parse_embedding(x):
    if isinstance(x, str):
        return np.array(ast.literal_eval(x), dtype=np.float32)
    return np.array(x, dtype=np.float32)

def build_training_data():
    conn = connect()
    cur = conn.cursor()

    print("🚧 Clearing existing training data...")
    cur.execute("DELETE FROM training_data;")
    conn.commit()

    print("📦 Fetching watch history with metadata and embeddings...")
    cur.execute("""
        SELECT
        t.username,
        t.rating_key,
        t.played_duration,
        l.duration AS media_duration,
        l.year AS release_year,
        t.season_number,
        t.episode_number,
        (
            SELECT string_agg(g.name, ', ')
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            WHERE mg.media_id = l.rating_key
        ) AS genre_tags,
        (
            SELECT string_agg(a.name, ', ')
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            WHERE ma.media_id = l.rating_key
        ) AS actor_tags,
        (
            SELECT string_agg(d.name, ', ')
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            WHERE md.media_id = l.rating_key
        ) AS director_tags,
        me.embedding AS media_embedding,
        ue.embedding AS user_embedding
    FROM watch_history t
    JOIN library l ON t.rating_key = l.rating_key
    JOIN media_embeddings me ON t.rating_key = me.rating_key
    JOIN user_embeddings ue ON t.username = ue.username
    WHERE t.played_duration IS NOT NULL AND l.duration IS NOT NULL
    """)
    
    rows = cur.fetchall()
    print(f"✅ Retrieved {len(rows)} records.")

    print("⚙️  Processing features and computing engagement...")
    inserts = []
    for row in rows:
        username, rating_key, played_duration, media_duration, release_year, season_number, episode_number, genres, actors, directors, media_embedding, user_embedding = row

        played_minutes = played_duration / 60
        media_minutes = media_duration / 1000 / 60  # Duration is in ms

        media_emb = parse_embedding(media_embedding)
        user_emb = parse_embedding(user_embedding)
        from pgvector import Vector

        combined_emb = Vector(np.concatenate([media_emb, user_emb]).tolist())

        if media_minutes == 0:
            continue  # skip corrupt or 0-length items

        engagement_ratio = played_minutes / media_minutes

        # Only keep strong signals: high engagement or explicit bailouts
        if engagement_ratio > ENGAGEMENT_THRESHOLD:
            label = 1
        elif engagement_ratio < 0.5:
            label = 0
        else:
            continue  # ❌ Skip ambiguous cases

        inserts.append((
            username,
            rating_key,
            label,
            combined_emb,
            genres or '',
            actors or '',
            directors or '',
            release_year,
            season_number,
            episode_number,
            played_duration,
            media_duration,
            engagement_ratio
        ))

    print(f"🧠 Inserting {len(inserts)} training records...")
    insert_sql = """
        INSERT INTO training_data (
            username, rating_key, label, embedding,
            genre_tags, actor_tags, director_tags, release_year, season_number, episode_number,
            played_duration, media_duration, engagement_ratio
        )
        VALUES %s
    """
    # This cast actually happens **within execute_values**, so you need to override the template:
    template = "(%s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    print(f"🧠 Inserting {len(inserts)} training records...")
    for row in inserts:
        cur.execute("""
            INSERT INTO training_data (
                username, rating_key, label, embedding,
                genre_tags, actor_tags, director_tags, release_year, season_number, episode_number,
                played_duration, media_duration, engagement_ratio
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, row)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Training data build complete.")

if __name__ == "__main__":
    build_training_data()
