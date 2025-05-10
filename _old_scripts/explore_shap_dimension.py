# explore_shap_dimension.py (updated logic for user dimensions)
import argparse
import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def connect_db():
    conn = psycopg2.connect(
        dbname="plexintel",
        user="jmnovak",
        password="brigid",
        host="localhost"
    )
    register_vector(conn)
    return conn

def explore_dimension(dimension, limit, export_csv=False, filter_genre=None, gpt_prompt=False, save_label=None):
    conn = connect_db()
    cur = conn.cursor()

    is_user_dim = dimension < 768
    id_col = "username" if is_user_dim else "rating_key"
    true_dim = dimension if is_user_dim else dimension - 768

    print(f"🔍 Dimension {dimension} is a {'USER' if is_user_dim else 'MEDIA'} embedding dimension (actual dim {true_dim}).")

    if is_user_dim:
        cur.execute("SELECT username, embedding FROM user_embeddings")
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["username", "embedding"])
    else:
        cur.execute("""
            SELECT m.rating_key, m.title, m.year, m.media_type, m.show_title,
                   COALESCE(g.genre_tags, '') AS genre_tags,
                   COALESCE(a.actor_names, '') AS actor_names,
                   COALESCE(d.director_names, '') AS director_names,
                   e.embedding
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
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=[
            "rating_key", "title", "year", "media_type", "show",
            "genres", "actors", "directors", "embedding"
        ])

    if len(df) == 0:
        print("⚠️ No rows found.")
        return

    vector_dim = len(df["embedding"].iloc[0])
    if true_dim >= vector_dim:
        raise ValueError(f"⚠️ Dimension {true_dim} out of bounds (max = {vector_dim - 1})")

    dim_col = f"emb_{dimension}"
    df[dim_col] = df["embedding"].apply(lambda v: v[true_dim])

    if filter_genre and "genres" in df.columns:
        df = df[df["genres"].str.contains(filter_genre, case=False, na=False)]
        print(f"🔎 Filtered to genre containing '{filter_genre}', remaining rows: {len(df)}")

    sorted_df = df.sort_values(dim_col, ascending=False).head(limit)

    print("\n📊 Top items by dimension value:")
    if is_user_dim:
        for _, row in sorted_df.iterrows():
            print(f"- {row['username']} | {dim_col}: {row[dim_col]:+.5f}")
    else:
        print(sorted_df[[id_col, dim_col] + [col for col in df.columns if col not in ['embedding', dim_col]]])

    print("\n📈 Dimension statistics:")
    print(df[dim_col].describe())

    plt.hist(df[dim_col], bins=50)
    plt.title(f"Distribution of Dimension {dimension} ({'user' if is_user_dim else 'media'})")
    plt.xlabel("Value")
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    if export_csv:
        filename = f"shap_dim_{dimension}_top_{limit}.csv"
        sorted_df.to_csv(filename, index=False)
        print(f"✅ Exported top items to {filename}")

    if gpt_prompt and not is_user_dim:
        prompt_file = f"gpt_summary_dim_{dimension}.txt"
        with open(prompt_file, "w") as f:
            f.write(f"Top items for embedding dimension {dimension} (used in model explanation):\n\n")
            for _, row in sorted_df.iterrows():
                summary = f"- {row.get('title', '')} ({row.get('year', '')}) | {row.get('genres', '')}"
                f.write(summary.strip() + "\n")
        print(f"🧠 GPT prompt written to {prompt_file}")

    if save_label:
        cur.execute(
            "INSERT INTO embedding_labels (dimension, label, created_at) VALUES (%s, %s, %s) ON CONFLICT (dimension) DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at",
            (dimension, save_label, datetime.utcnow())
        )
        conn.commit()
        print(f"✅ Saved label '{save_label}' for dimension {dimension} to embedding_labels")

    cur.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Explore and label a SHAP-referenced embedding dimension.")
    parser.add_argument("--dimension", type=int, required=True, help="Combined embedding dimension index (0–1535)")
    parser.add_argument("--limit", type=int, default=20, help="How many top items to return")
    parser.add_argument("--export_csv", action="store_true", help="Export results to a CSV file")
    parser.add_argument("--filter_genre", type=str, help="Optional genre filter substring match")
    parser.add_argument("--gpt_prompt", action="store_true", help="Write a GPT-friendly prompt file (media only)")
    parser.add_argument("--save_label", type=str, help="Optional: save a label to embedding_labels")
    args = parser.parse_args()

    explore_dimension(
        dimension=args.dimension,
        limit=args.limit,
        export_csv=args.export_csv,
        filter_genre=args.filter_genre,
        gpt_prompt=args.gpt_prompt,
        save_label=args.save_label
    )
