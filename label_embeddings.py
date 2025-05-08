# label_embeddings.py
# Summarize and label embedding dimensions using GPT and watch/metadata context

from dotenv import load_dotenv
load_dotenv()
from gpt_utils import call_gpt_for_label, insert_label
import psycopg2
import pandas as pd
from datetime import datetime
from pgvector.psycopg2 import register_vector
import argparse
import os
import openai


DB_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn

def label_single_dimension(dimension, top_n=10, gpt_label=False, save_label=False):
    mode, top_ids = get_top_entities_for_dimension(dimension, top_n)
    if mode == "user":
        df = get_user_watch_history(top_ids)
    else:
        df = get_media_metadata(top_ids)
        print("🔥 GETTING METADATA FOR:", top_ids)
    summary = generate_summary_text(df, dimension)
    print(f"📄 Prompt for GPT (dim {dimension}):")
    print(summary)

    if gpt_label:
        label = call_gpt_for_label(summary)
        print(f"🧠 Suggested label for dim {dimension}: {label}")
        if save_label:
            insert_label(dimension, label)

def get_top_entities_for_dimension(dimension, top_n=10):
    conn = connect_db()
    cur = conn.cursor()
    if dimension < 768:
        cur.execute("SELECT username, embedding FROM user_embeddings")
        df = pd.DataFrame(cur.fetchall(), columns=["username", "embedding"])
        df[f"emb_{dimension}"] = df["embedding"].apply(lambda v: v[dimension])
        top = df.sort_values(f"emb_{dimension}", ascending=False).head(top_n)
        return "user", top["username"].tolist()
    else:
        media_dim = dimension - 768
        cur.execute("SELECT rating_key, embedding FROM media_embeddings")
        df = pd.DataFrame(cur.fetchall(), columns=["rating_key", "embedding"])
        df[f"emb_{dimension}"] = df["embedding"].apply(lambda v: v[media_dim])
        top = df.sort_values(f"emb_{dimension}", ascending=False).head(top_n)
        return "media", top["rating_key"].tolist()

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
    print("\n🎬 DEBUG METADATA SAMPLE:")
    print(df[['rating_key', 'title', 'media_type', 'show_title', 'actor_tags', 'director_tags']].head(10).to_string(index=False))

    expected_cols = ["title", "year", "media_type", "show_title", "rating", "summary", "genre_tags", "actor_tags", "director_tags"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    return df

def generate_summary_text(df, dimension):
    print("\n🎬 DEBUG SUMMARY INPUT:")
    print(df[['title', 'actor_tags', 'director_tags']].head(5).to_string(index=False))
    lines = [f"Top items for embedding dimension {dimension}:\n"]
    for _, row in df.head(10).iterrows():
        media_type = row.get("media_type", "").strip().upper()
        media_type_label = f"[{media_type}]" if media_type else "[UNKNOWN]"

        show_title = row.get("show_title", "").strip()
        base_title = f"{show_title}: {row['title']}" if show_title else row['title']
        title = f"{media_type_label} {base_title} ({row['year']})"

        title_line = f"- {title} | {row['genre_tags']}"
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

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dimension", type=int, help="Single embedding dimension index")
    group.add_argument("--dimensions", nargs="+", type=int, help="List of embedding dimension indexes")
    parser.add_argument("--top_n", type=int, default=10, help="Number of top items or users to summarize")
    parser.add_argument("--gpt_label", action="store_true", help="Use GPT to generate a label")
    parser.add_argument("--save_label", action="store_true", help="Store the label in the embedding_labels table")
    args = parser.parse_args()

    dimensions = args.dimensions if args.dimensions else ([args.dimension])

    for dim in dimensions:
        label_single_dimension(dim, top_n=args.top_n, gpt_label=args.gpt_label, save_label=args.save_label)

if __name__ == "__main__":
    main()