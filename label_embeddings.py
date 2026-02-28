# label_embeddings.py
# Summarize and label embedding dimensions using a configurable LLM provider.

from dotenv import load_dotenv
load_dotenv()
from gpt_utils import call_llm_for_label, insert_label, resolve_label_backend
import psycopg2
import pandas as pd
from pgvector.psycopg2 import register_vector
import argparse
import os


DB_URL = os.getenv("DATABASE_URL")

def connect_db():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn

def label_single_dimension(
    dimension,
    top_n=10,
    generate_label=False,
    save_label=False,
    label_provider=None,
    label_model=None,
):
    mode, top_ids = get_top_entities_for_dimension(dimension, top_n)
    if mode == "user":
        df = get_user_watch_history(top_ids)
    else:
        df = get_media_metadata(top_ids)
    summary = generate_summary_text(df, dimension)
    print(f"📄 Prompt for label generation (dim {dimension}):")
    print(summary)

    if generate_label:
        provider_name, model_name = resolve_label_backend(label_provider, label_model)
        label = call_llm_for_label(summary, provider=provider_name, model=model_name)
        print(f"🧠 Suggested label for dim {dimension} via {provider_name}:{model_name}: {label}")
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

    lines = [f"Top items for embedding dimension {dimension}:\n"]
    for _, row in df.head(6).iterrows():
        media_type = _safe_str(row.get("media_type", "")).strip().upper()
        media_type_label = f"[{media_type}]" if media_type else "[UNKNOWN]"

        show_title = _safe_str(row.get("show_title", "")).strip()
        title_value = _safe_str(row.get("title", "")).strip()
        year_value = _safe_str(row.get("year", "")).strip()
        base_title = f"{show_title}: {title_value}" if show_title else title_value
        title = f"{media_type_label} {base_title} ({year_value})"

        genre_tags = ", ".join(
            tag.strip() for tag in _safe_str(row.get("genre_tags", "")).split(",")[:3] if tag.strip()
        )
        title_line = f"- {title}"
        if genre_tags:
            title_line += f" | {genre_tags}"
        extras = []

        if pd.notna(row.get('director_tags')) and row['director_tags']:
            trimmed_directors = ", ".join(row['director_tags'].split(", ")[:2])
            extras.append(f"Director(s): {trimmed_directors}")

        if pd.notna(row.get('actor_tags')) and row['actor_tags']:
            trimmed_actors = ", ".join(row['actor_tags'].split(", ")[:2])
            extras.append(f"Actor(s): {trimmed_actors}")

        if pd.notna(row.get('rating')) and _safe_str(row.get('rating')).strip():
            extras.append(f"Rating: {row['rating']}")

        if extras:
            title_line += "\n  " + " | ".join(extras)

        if pd.notna(row.get('summary')) and row['summary']:
            summary_text = row['summary'][:220].strip()
            if len(row['summary']) > 220:
                summary_text += "..."
            title_line += f"\n  {summary_text}"

        lines.append(title_line + "\n")
    return "".join(lines)

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dimension", type=int, help="Single embedding dimension index")
    group.add_argument("--dimensions", nargs="+", type=int, help="List of embedding dimension indexes")
    parser.add_argument("--top_n", type=int, default=10, help="Number of top items or users to summarize")
    parser.add_argument("--label", action="store_true", help="Generate a label using the configured LLM provider")
    parser.add_argument("--gpt_label", dest="label", action="store_true", help="Deprecated alias for --label")
    parser.add_argument("--label_provider", choices=["openai", "ollama"], default=None, help="Override label provider")
    parser.add_argument("--label_model", default=None, help="Override label model name")
    parser.add_argument("--save_label", action="store_true", help="Store the label in the embedding_labels table")
    args = parser.parse_args()

    dimensions = args.dimensions if args.dimensions else ([args.dimension])

    for dim in dimensions:
        label_single_dimension(
            dim,
            top_n=args.top_n,
            generate_label=args.label,
            save_label=args.save_label,
            label_provider=args.label_provider,
            label_model=args.label_model,
        )

if __name__ == "__main__":
    main()
