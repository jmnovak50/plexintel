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


def process_row(row, from_feedback_only=False):
    username = row["username"]
    rating_key = row["rating_key"]
    feedback = row.get("feedback")
    reason_code = row.get("reason_code")
    genres = row.get("genre_tags") or ''
    actors = row.get("actor_tags") or ''
    directors = row.get("director_tags") or ''
    media_embedding = parse_embedding(row["media_embedding"])
    user_embedding = parse_embedding(row["user_embedding"])
    combined_emb = Vector(np.concatenate([media_embedding, user_embedding]).tolist())

    if from_feedback_only:
        if feedback == "down":
            label = 0
            sample_weight = 5.0
            engagement_ratio = 0
        elif feedback == "up":
            label = 1
            sample_weight = 2.0
            engagement_ratio = FEEDBACK_BONUS
        else:
            return None

        return (
            username,
            rating_key,
            label,
            combined_emb,
            genres,
            actors,
            directors,
            row.get("release_year"),
            None,
            None,
            0,
            0,
            engagement_ratio,
            sample_weight
        )

    # Normal path with watch history
    media_duration = row["media_duration"]
    played_duration = row["played_duration"]
    if not media_duration:
        return None

    played_minutes = played_duration / 60
    media_minutes = media_duration / 1000 / 60
    if media_minutes == 0:
        return None

    engagement_ratio = played_minutes / media_minutes

    if ENABLE_FEEDBACK and feedback in ["up", "down"]:
        if feedback == "down":
            label = 0
            engagement_ratio = 0
            sample_weight = 5.0
        elif feedback == "up":
            label = 1
            engagement_ratio += FEEDBACK_BONUS
            sample_weight = 2.0
    else:
        if engagement_ratio > ENGAGEMENT_THRESHOLD:
            label = 1
            sample_weight = 1.0
        elif engagement_ratio < 0.5:
            label = 0
            sample_weight = 1.0
        else:
            return None  # skip ambiguous

    return (
        username,
        rating_key,
        label,
        combined_emb,
        genres,
        actors,
        directors,
        row.get("release_year"),
        row.get("season_number"),
        row.get("episode_number"),
        played_duration,
        media_duration,
        engagement_ratio,
        sample_weight
    )


def build_training_data():
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("🚧 Clearing existing training data...")
    cur.execute("DELETE FROM training_data;")
    conn.commit()

    print("📦 Fetching watch-based rows...")
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
        LEFT JOIN user_feedback f ON f.username = t.username AND f.rating_key = l.rating_key
        WHERE t.played_duration IS NOT NULL AND l.duration IS NOT NULL
    """)
    watched_rows = cur.fetchall()

    print("📥 Fetching feedback-only rows (no watch history)...")
    cur.execute("""
        SELECT
            f.username,
            f.rating_key,
            f.feedback,
            f.reason_code,
            l.year AS release_year,
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
        FROM user_feedback f
        JOIN library l ON f.rating_key = l.rating_key
        JOIN media_embeddings me ON f.rating_key = me.rating_key
        JOIN user_embeddings ue ON f.username = ue.username
        LEFT JOIN watch_history w ON w.username = f.username AND w.rating_key = f.rating_key
        WHERE w.rating_key IS NULL
    """)
    feedback_only_rows = cur.fetchall()

    print(f"✅ Retrieved {len(watched_rows)} watched + {len(feedback_only_rows)} feedback-only rows")

    inserts = []
    for row in watched_rows:
        result = process_row(row)
        if result:
            inserts.append(result)

    for row in feedback_only_rows:
        result = process_row(row, from_feedback_only=True)
        if result:
            inserts.append(result)

    thumbs_down_count = sum(1 for r in inserts if r[2] == 0 and r[-1] == 5.0)
    thumbs_up_count = sum(1 for r in inserts if r[2] == 1 and r[-1] == 2.0)
    print(f"👎 Feedback rows (label=0, weight=5.0): {thumbs_down_count}")
    print(f"👍 Feedback rows (label=1, weight=2.0): {thumbs_up_count}")

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

    with conn.cursor() as insert_cur:
        for row in inserts:
            insert_cur.execute(insert_sql, row)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Training data build complete.")


if __name__ == "__main__":
    build_training_data()