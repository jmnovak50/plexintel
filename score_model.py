from dotenv import load_dotenv
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

SHAP_PRUNE_DAYS = int(os.getenv("SHAP_PRUNE_DAYS", "3"))  # default to 3 if not set

DB_URL = os.getenv("DATABASE_URL")
print("DB_URL is:", DB_URL)

import pandas as pd
import numpy as np
import joblib
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy import text
import ast
from datetime import datetime

import xgboost as xgb
from sklearn.preprocessing import MultiLabelBinarizer

import warnings  # 👈 add this
warnings.filterwarnings("ignore", category=UserWarning, module='sklearn')

def get_engine():
    return create_engine(DB_URL)

def get_unwatched_media(username):
    engine = get_engine()
    query = """
        SELECT 
            m.rating_key,
            m.media_type,
            m.title,
            e.embedding,
            m.year,
            g.genre_tags,
            a.actor_tags,
            d.director_tags,
            ue.embedding AS user_embedding
        FROM library m
        JOIN media_embeddings e ON m.rating_key = e.rating_key
        JOIN user_embeddings ue ON ue.username = %s
        LEFT JOIN watch_history w ON m.rating_key = w.rating_key AND w.username = %s

        -- JOIN genre tags
        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ',') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = m.rating_key

        -- JOIN actor tags
        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ',') AS actor_tags
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = m.rating_key

        -- JOIN director tags
        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ',') AS director_tags
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
        ) d ON d.media_id = m.rating_key

        WHERE w.rating_key IS NULL
    """
    df = pd.read_sql(query, engine, params=(username, username))
    return df

def preprocess_for_scoring(df, feature_names_template):
    def safe_embedding_parse(x):
        if isinstance(x, str):
            return np.array(ast.literal_eval(x), dtype=np.float32)
        return np.array(x, dtype=np.float32)

    def get_decade_flags(year):
        if year is None or pd.isna(year):
            return {}
        try:
            decade = int(year) // 10 * 10
            return {f"is_{decade}s": 1}
        except:
            return {}

    df['genres'] = df['genre_tags'].fillna('').apply(lambda x: x.split(',') if x else [])
    df['actors'] = df['actor_tags'].fillna('').apply(lambda x: x.split(',') if x else [])
    df['directors'] = df['director_tags'].fillna('').apply(lambda x: x.split(',') if x else [])
    df['media_embedding'] = df['embedding'].apply(safe_embedding_parse)
    df['user_embedding'] = df['user_embedding'].apply(safe_embedding_parse)
    df['embedding'] = df.apply(lambda row: np.concatenate([row['media_embedding'], row['user_embedding']]), axis=1)

    decade_df = df['year'].apply(get_decade_flags).apply(pd.Series).fillna(0).astype(int)

    genre_top = [f.split("_", 1)[1] for f in feature_names_template if f.startswith("genre_")]
    actor_top = [f.split("_", 1)[1] for f in feature_names_template if f.startswith("actor_")]
    director_top = [f.split("_", 1)[1] for f in feature_names_template if f.startswith("director_")]

    def filter_known(labels, allowed_set):
        return [label for label in labels if label in allowed_set]

    df['genres'] = df['genres'].apply(lambda x: filter_known(x, set(genre_top)))
    df['actors'] = df['actors'].apply(lambda x: filter_known(x, set(actor_top)))
    df['directors'] = df['directors'].apply(lambda x: filter_known(x, set(director_top)))

    genre_bin = MultiLabelBinarizer(classes=genre_top)
    actor_bin = MultiLabelBinarizer(classes=actor_top)
    director_bin = MultiLabelBinarizer(classes=director_top)

    genre_features = genre_bin.fit_transform(df['genres'])
    actor_features = actor_bin.fit_transform(df['actors'])
    director_features = director_bin.fit_transform(df['directors'])

    X = np.vstack(df['embedding'].values)
    X = np.hstack((X, genre_features, actor_features, director_features, decade_df.values))
    print("📆 Decade columns added:", list(decade_df.columns))

    return X

def cosine_similarity_batch(user_embeddings, media_embeddings):
    dot_products = np.einsum('ij,ij->i', user_embeddings, media_embeddings)
    norms_user = np.linalg.norm(user_embeddings, axis=1)
    norms_media = np.linalg.norm(media_embeddings, axis=1)
    similarities = dot_products / (norms_user * norms_media)
    return similarities

def score_and_store(username, skip_shap=False):
    import shap
    print("📥 Loading model...")
    model = joblib.load("xgb_model.pkl")
    booster = model.get_booster()

    print(f"📊 Fetching unwatched media for {username}...")
    df = get_unwatched_media(username)
    if df.empty:
        print("✅ No unwatched items to score.")
        return

    print("🧹 Preprocessing...")
    feature_names = booster.feature_names
    X = preprocess_for_scoring(df, feature_names)

    print("🔮 Scoring predictions...")
    probabilities = model.predict_proba(X)[:, 1]
    df['predicted_probability'] = probabilities

    # ✅ SHAP target selection (inside the function!)
    tv_df = df[df['media_type'] == 'episode'].sort_values(by='predicted_probability', ascending=False)
    movie_df = df[df['media_type'] == 'movie'].sort_values(by='predicted_probability', ascending=False)

    def top_percent(df, pct=0.05, min_items=10):
        k = max(min_items, int(len(df) * pct))
        return df.head(k)

    top_tv_df = top_percent(tv_df, pct=0.05, min_items=10)
    top_movie_df = top_percent(movie_df, pct=0.05, min_items=10)
    top_tv_df['rank'] = top_tv_df['predicted_probability'].rank(method='first', ascending=False).astype(int)
    top_movie_df['rank'] = top_movie_df['predicted_probability'].rank(method='first', ascending=False).astype(int)

    top_df = pd.concat([top_tv_df, top_movie_df])

    df['username'] = username
    df['scored_at'] = datetime.now()
    df['model_name'] = 'xgb_model'
    df['rank'] = df['predicted_probability'].rank(method='first', ascending=False).astype(int)

    df['cosine_similarity'] = cosine_similarity_batch(
        np.stack(df['user_embedding']),
        np.stack(df['media_embedding'])
    )

    df['explanation'] = np.where(
        df['cosine_similarity'] > 0.85,
        "Very similar to your viewing preferences",
        ""
    )

    output = df[['username', 'rating_key', 'predicted_probability', 'model_name', 'scored_at', 'rank', 'cosine_similarity', 'explanation']]
    engine = get_engine()
    output.to_sql("recommendations", engine, if_exists="append", index=False)
    print(f"✅ Stored {len(output)} recommendations for {username}.")
    if skip_shap:
        print("⏩ Skipping SHAP impact generation.")
        return
    explainer = shap.TreeExplainer(model)
    X_top = X[top_df.index]
    shap_values = explainer.shap_values(X_top)

    print("\n🔍 SHAP Feature Impact (Top Rows):")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute(f"""
        DELETE FROM shap_impact
        WHERE user_id = %s AND modified_at < now() - INTERVAL '{SHAP_PRUNE_DAYS} days';
    """, (username,))
    pruned = cur.rowcount
    conn.commit()
    print(f"🧹 Pruned {pruned:,} old SHAP rows for {username} (older than {SHAP_PRUNE_DAYS} days)")

    for i, row in enumerate(top_df.itertuples()):
        shap_row = shap_values[i]
        top_features = sorted(zip(feature_names, shap_row), key=lambda x: abs(x[1]), reverse=True)[:3]
        formatted = ", ".join([f"{name} ({value:+.2f})" for name, value in top_features])
        print(f"Rank {row.rank}: {row.rating_key} — {formatted}")

        top_dims = sorted(enumerate(shap_row[:1536]), key=lambda x: abs(x[1]), reverse=True)[:100]
        for dim, shap_val in top_dims:
            cur.execute(
                """
                INSERT INTO shap_impact (user_id, rating_key, dimension, shap_value, created_at, modified_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id, rating_key, dimension)
                DO UPDATE SET 
                    shap_value = EXCLUDED.shap_value,
                    modified_at = NOW()
                WHERE shap_impact.shap_value IS DISTINCT FROM EXCLUDED.shap_value;
                """,
                (username, row.rating_key, dim, float(shap_val))
            )

    conn.commit()
    cur.close()
    conn.close()

def get_all_users():
    engine = get_engine()
    query = "SELECT DISTINCT username FROM watch_history"
    df = pd.read_sql(query, engine)
    return df['username'].tolist()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user", type=str, help="Username to score recommendations for")
    group.add_argument("--all-users", action="store_true", help="Score recommendations for all users with watch history")
    parser.add_argument("--skip-shap", action="store_true", help="Skip SHAP impact generation")
    args = parser.parse_args()

    if args.all_users:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE recommendations"))
        users = get_all_users()
        print(f"🔁 Scoring for all users: {users}")
        for user in users:
            score_and_store(user, skip_shap=args.skip_shap)
    else:
        score_and_store(args.user, skip_shap=args.skip_shap)
