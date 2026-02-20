import openai
from datetime import datetime
import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn

def call_gpt_for_label(prompt_text):
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an assistant helping to label semantic themes in movie or user preferences."
            },
            {
                "role": "user",
                "content": f"""
You're a semantic analysis engine designed to find common narrative or stylistic themes across media. 
Given the following film and TV examples, identify their shared storytelling essence.

Avoid generic genre labels like 'drama' or 'comedy' unless they are truly the strongest possible signal. 
Instead, describe shared traits like tone, narrative structure, character arcs, emotional themes, setting, or creative intent.

Use a short, descriptive phrase — not a full sentence — that helps a human understand what unites these items in a recommendation engine.

You may use available data like plot summaries, genre tags, cast, and directors to identify deeper narrative or stylistic similarities.

🧠 Examples of high-quality labels:
- Melancholy character-driven indie dramas
- Stylized ensemble satire with dry humor
- Upbeat redemption stories in sports settings
- Psychological thrillers centered on isolation and obsession
- Family comedies rooted in nostalgic Americana

Items:
{prompt_text}

Label:
"""
            }
        ],
        max_tokens=50,
        temperature=0.7
    )
    label = response.choices[0].message.content.strip()
    return label.strip('"').strip("'")

def insert_label(dimension, label):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO embedding_labels (dimension, label, created_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (dimension)
        DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at
        """,
        (dimension, label, datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Saved label '{label}' for dimension {dimension}")

def get_top_media_for_dimension(dimension, top_n=10):
    media_dim = dimension - 768
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT rating_key, embedding FROM media_embeddings")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=["rating_key", "embedding"])
    df[f"emb_{dimension}"] = df["embedding"].apply(lambda v: v[media_dim])
    top = df.sort_values(f"emb_{dimension}", ascending=False).head(top_n)
    return top["rating_key"].tolist()

def get_top_users_for_dimension(dimension, top_n=10):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT username, embedding FROM user_embeddings")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=["username", "embedding"])
    df[f"emb_{dimension}"] = df["embedding"].apply(lambda v: v[dimension])
    top = df.sort_values(f"emb_{dimension}", ascending=False).head(top_n)
    return top["username"].tolist()

def get_media_metadata(rating_keys):
    from psycopg2.extras import execute_values
    if isinstance(rating_keys, int):
        rating_keys = [rating_keys]

    conn = connect_db()
    cur = conn.cursor()
    sql = """
        SELECT
        m.rating_key,
        m.title,
        m.year,
        m.media_type,
        m.show_title,
        m.rating,
        m.summary,
        COALESCE(g.genre_tags, '') AS genre_tags,
        COALESCE(a.actor_tags, '') AS actor_tags,
        COALESCE(d.director_tags, '') AS director_tags
        FROM library m
        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = m.rating_key
        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_tags
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = m.rating_key
        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_tags
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
        ) d ON d.media_id = m.rating_key
        WHERE m.rating_key = ANY(%s)
    """
    cur.execute(sql, (rating_keys,))
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=colnames)
    expected_cols = ["title", "year", "media_type", "show_title", "rating", "summary", "genre_tags", "actor_tags", "director_tags"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    return df

def get_user_watch_history(usernames):
    conn = connect_db()
    cur = conn.cursor()
    sql = """
        SELECT
            w.username,
            m.rating_key,
            m.title,
            m.year,
            m.media_type,
            m.show_title,
            m.rating,
            m.summary,
            COALESCE(g.genre_tags, '') AS genre_tags,
            COALESCE(a.actor_tags, '') AS actor_tags,
            COALESCE(d.director_tags, '') AS director_tags
        FROM watch_history w
        JOIN library m ON w.rating_key = m.rating_key
        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = m.rating_key
        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_tags
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = m.rating_key
        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_tags
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
        ) d ON d.media_id = m.rating_key
        WHERE w.username = ANY(%s)
        ORDER BY w.watched_at DESC NULLS LAST
    """
    cur.execute(sql, (usernames,))
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=colnames)
    expected_cols = ["title", "year", "media_type", "show_title", "rating", "summary", "genre_tags", "actor_tags", "director_tags"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    return df

def generate_summary_text(df, dimension):
    def _safe_str(value):
        if value is None or pd.isna(value):
            return ""
        return str(value)

    lines = [f"Top items for embedding dimension {dimension}:"]
    for _, row in df.head(10).iterrows():
        media_type = _safe_str(row.get("media_type", "")).strip().upper()
        media_type_label = f"[{media_type}]" if media_type else "[UNKNOWN]"

        show_title = _safe_str(row.get("show_title", "")).strip()
        title_value = _safe_str(row.get("title", "")).strip()
        year_value = _safe_str(row.get("year", "")).strip()

        base_title = f"{show_title}: {title_value}" if show_title else title_value
        title = f"{media_type_label} {base_title} ({year_value})"

        genre_tags = _safe_str(row.get("genre_tags", "")).strip()
        title_line = f"- {title} | {genre_tags}"
        extras = []

        if pd.notna(row.get('director_tags')) and row['director_tags']:
            trimmed_directors = ", ".join(row['director_tags'].split(", ")[:3]) + "..."
            extras.append(f"Director(s): {trimmed_directors}")

        if pd.notna(row.get('actor_tags')) and row['actor_tags']:
            trimmed_actors = ", ".join(row['actor_tags'].split(", ")[:4]) + "..."
            extras.append(f"Actor(s): {trimmed_actors}")

        if pd.notna(row.get('rating')):
            extras.append(f"Rating: {row['rating']}")

        if extras:
            title_line += "\n  " + " | ".join(extras)

        if pd.notna(row.get('summary')) and row['summary']:
            summary_text = row['summary'][:500] + "..." if len(row['summary']) > 500 else row['summary']
            title_line += f"\n  {summary_text}"

        lines.append(title_line + "\n")
    return "".join(lines)
