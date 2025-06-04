from dotenv import load_dotenv
import os
import psycopg2
import numpy as np
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
from pgvector import Vector
import ast

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
FEEDBACK_BONUS = 0.1        # 👍 Bonus applied to thumbs-up engagement
ENABLE_FEEDBACK = True      # Toggle feedback injection on/off
USE_SAMPLE_WEIGHT = True

def connect():
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    return conn

def parse_embedding(x):
    if isinstance(x, str):
        return np.array(ast.literal_eval(x), dtype=np.float32)
    return np.array(x, dtype=np.float32)

def build_training_data():
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

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
            ue.embedding AS user_embedding,
            f.feedback,
            f.reason_code
        FROM watch_history t
        JOIN library l ON t.rating_key = l.rating_key
        JOIN media_embeddings me ON t.rating_key = me.rating_key
        JOIN user_embeddings ue ON t.username = ue.username
        LEFT JOIN user_feedback f ON f.username = t.username AND f.rating_key = t.rating_key
        WHERE t.played_duration IS NOT NULL AND l.duration IS NOT NULL
    """)
    
    rows = cur.fetchall()
    print(f"✅ Retrieved {len(rows)} records.")

    print("⚙️  Processing features and computing engagement...")
    inserts = []
    for row in rows:
        username = row["username"]
        rating_key = row["rating_key"]
        played_duration = row["played_duration"]
        media_duration = row["media_duration"]
        release_year = row["release_year"]
        season_number = row["season_number"]
        episode_number = row["episode_number"]
        genres = row["genre_tags"]
        actors = row["actor_tags"]
        directors = row["director_tags"]
        media_embedding = parse_embedding(row["media_embedding"])
        user_embedding = parse_embedding(row["user_embedding"])
        feedback = row["feedback"]
        reason_code = row["reason_code"]

        if media_duration == 0:
            continue  # skip corrupt entries

        played_minutes = played_duration / 60
        media_minutes = media_duration / 1000 / 60
        engagement_ratio = played_minutes / media_minutes

        # 🎯 Feedback logic overrides engagement ratio
        if ENABLE_FEEDBACK and feedback in ["thumbs_up", "thumbs_down"]:
            if feedback == "thumbs_down":
                label = 0  # Explicit negative
            elif feedback == "thumbs_up":
                label = 1
                engagement_ratio += FEEDBACK_BONUS  # Boost
        else:
            if engagement_ratio > ENGAGEMENT_THRESHOLD:
                label = 1
            elif engagement_ratio < 0.5:
                label = 0
            else:
                continue  # skip ambiguous

        combined_emb = Vector(np.concatenate([media_embedding, user_embedding]).tolist())

        sample_weight = 1.0
        if ENABLE_FEEDBACK and feedback in ["thumbs_up", "thumbs_down"]:
            sample_weight = 2.0

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
            engagement_ratio,
            sample_weight
        ))

    print(f"🧠 Inserting {len(inserts)} training records...")
    insert_sql = """
    INSERT INTO training_data (
        username, rating_key, label, embedding,
        genre_tags, actor_tags, director_tags, release_year, season_number, episode_number,
        played_duration, media_duration, engagement_ratio,
        sample_weight
    )
    VALUES (%s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


    for row in inserts:
        cur.execute(insert_sql, row)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Training data build complete.")

if __name__ == "__main__":
    build_training_data()
