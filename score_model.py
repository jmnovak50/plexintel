from dotenv import load_dotenv
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

SHAP_PRUNE_DAYS = int(os.getenv("SHAP_PRUNE_DAYS", "3"))
SHAP_MAX_ITEMS = int(os.getenv("SHAP_MAX_ITEMS", "500"))
SHAP_TOP_DIMS = int(os.getenv("SHAP_TOP_DIMS", "30"))
WATCHED_ENGAGEMENT_THRESHOLD = float(os.getenv("WATCHED_ENGAGEMENT_THRESHOLD", "0.5"))
WATCH_EMBED_MIN_ENGAGEMENT = float(os.getenv("WATCH_EMBED_MIN_ENGAGEMENT", "0.5"))
DB_URL = os.getenv("DATABASE_URL")
print("DB_URL is:", DB_URL)

import pandas as pd
import numpy as np
import joblib
import psycopg2
from sqlalchemy import create_engine, text
import ast
from datetime import datetime
import xgboost as xgb
from sklearn.preprocessing import MultiLabelBinarizer
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='sklearn')

def get_engine():
    return create_engine(DB_URL)

def parse_vector(x):
    if isinstance(x, str):
        return np.array(ast.literal_eval(x), dtype=np.float32)
    return np.array(x, dtype=np.float32)

def get_user_watch_vector(username):
    """
    Build a per-user average watch-embedding vector (from watch_history + watch_embeddings).
    Only includes watch events above WATCH_EMBED_MIN_ENGAGEMENT.
    """
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            wh.played_duration,
            l.duration AS media_duration,
            we.embedding AS watch_embedding
        FROM watch_history wh
        JOIN library l ON wh.rating_key = l.rating_key
        JOIN watch_embeddings we ON wh.watch_id::text = we.watch_id::text
        WHERE wh.username = %s
          AND wh.played_duration IS NOT NULL
          AND l.duration IS NOT NULL
        """,
        (username,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return None

    vec_sum = None
    count = 0
    for played_duration, media_duration, watch_embedding in rows:
        if not media_duration:
            continue
        ratio = played_duration / (media_duration / 1000.0) if media_duration else 0.0
        if ratio < WATCH_EMBED_MIN_ENGAGEMENT:
            continue
        vec = parse_vector(watch_embedding)
        if vec_sum is None:
            vec_sum = vec.copy()
        else:
            vec_sum += vec
        count += 1

    if count == 0:
        return None
    return vec_sum / count

def get_unwatched_media(username):
    engine = get_engine()
    query = """
        SELECT 
            m.rating_key,
            m.media_type,
            m.title,
            m.parent_rating_key,
            e.embedding,
            m.year,
            g.genre_tags,
            a.actor_tags,
            d.director_tags,
            ue.embedding AS user_embedding
        FROM library m
        JOIN media_embeddings e ON m.rating_key = e.rating_key
        JOIN user_embeddings ue ON ue.username = %s
        LEFT JOIN watch_history w
            ON m.rating_key = w.rating_key
            AND w.username = %s
            AND (
                (
                    w.percent_complete IS NOT NULL
                    AND (
                        CASE
                            WHEN w.percent_complete > 1 THEN w.percent_complete / 100.0
                            ELSE w.percent_complete
                        END
                    ) >= %s
                )
                OR (
                    w.played_duration IS NOT NULL
                    AND m.duration IS NOT NULL
                    AND m.duration > 0
                    AND (w.played_duration::float / (m.duration / 1000.0)) >= %s
                )
            )
        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ',') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = m.rating_key
        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ',') AS actor_tags
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = m.rating_key
        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ',') AS director_tags
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
	        ) d ON d.media_id = m.rating_key
	        WHERE w.rating_key IS NULL
	        AND m.media_type IN ('movie', 'episode')
	        AND NOT EXISTS (
	            SELECT 1
	            FROM user_feedback f
	            WHERE f.username = %s
            AND f.rating_key = m.rating_key
            AND f.suppress = true
    )
    """
    df = pd.read_sql(
        query,
        engine,
        params=(
            username,
            username,
            WATCHED_ENGAGEMENT_THRESHOLD,
            WATCHED_ENGAGEMENT_THRESHOLD,
            username,
        ),
    )
    print(f"🔍 {len(df)} media items remaining after suppression filter.")
    return df

def preprocess_for_scoring(df, feature_names_template, user_watch_vec=None):
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

    # Parse embeddings before combination
    df['media_embedding'] = df['embedding'].apply(safe_embedding_parse)
    df['user_embedding'] = df['user_embedding'].apply(safe_embedding_parse)

    # Watch-embedding similarity (media_emb vs user watch-profile)
    media_embs = np.stack(df['media_embedding'])
    watch_sim = np.zeros(len(df), dtype=np.float32)
    if user_watch_vec is not None:
        user_watch_vec = np.array(user_watch_vec, dtype=np.float32)
        norm_user = np.linalg.norm(user_watch_vec)
        if norm_user > 0:
            norms_media = np.linalg.norm(media_embs, axis=1)
            denom = norms_media * norm_user
            valid = denom > 0
            watch_sim[valid] = (media_embs[valid] @ user_watch_vec) / denom[valid]
    df['watch_sim'] = watch_sim

    # Combine user and media embeddings
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
    X = np.hstack((X, genre_features, actor_features, director_features, decade_df.values, watch_sim.reshape(-1, 1)))
    print("📆 Decade columns added:", list(decade_df.columns))

    return X, df

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
    user_watch_vec = get_user_watch_vector(username)
    if user_watch_vec is None:
        print(f"⚠️ No watch-embedding profile for {username}; watch_sim will be 0.")
    X, df = preprocess_for_scoring(df, feature_names, user_watch_vec=user_watch_vec)

    # 🔍 Embedding Debug (NOW SAFE TO CALL)
    media_embs = np.stack(df['media_embedding'])
    print("✅ Unique media embeddings:", len(np.unique(media_embs, axis=0)))

    combo_embs = np.stack(df['embedding'])
    print("✅ Unique combined embeddings:", len(np.unique(combo_embs, axis=0)))
    

    combo_embs = np.stack(df['embedding'])
    unique_combo_count = len(np.unique(combo_embs, axis=0))
    print("🧠 Unique combined user-media embedding vectors:", unique_combo_count)

    print("🔮 Scoring predictions...")
    expected_features = model.feature_names_in_

    # ✅ Ensure X is a DataFrame, even if it was returned as a NumPy array
    if X.shape[1] != len(expected_features):
        print(f"⚠️ Feature mismatch: X has {X.shape[1]} columns, expected {len(expected_features)}")
        if X.shape[1] < len(expected_features):
            pad_width = len(expected_features) - X.shape[1]
            print(f"🔧 Padding X with {pad_width} zeros")
            X = np.hstack([X, np.zeros((X.shape[0], pad_width))])
        else:
            print(f"🔧 Trimming X from {X.shape[1]} to {len(expected_features)} columns")
            X = X[:, :len(expected_features)]

    X_df = pd.DataFrame(X, columns=expected_features)  # <-- always create this
    probabilities = model.predict_proba(X_df)[:, 1]

    df['predicted_probability'] = probabilities

    # -------------------------------------------------------------------------
    # 🔄 TV recommendations: prefer Season rollups, fallback to Episodes
    # -------------------------------------------------------------------------

    movie_df = df[df['media_type'] == 'movie'].copy()
    movie_df['shap_source_index'] = movie_df.index

    episode_df = df[df['media_type'] == 'episode'].copy()
    episode_df['shap_source_index'] = episode_df.index

    # Keep TV recommendations at the episode level for rollups/drilldowns later.
    tv_df = episode_df.copy()
    model_name = 'xgb_model'

    # Sort
    if not tv_df.empty:
        tv_df = tv_df.sort_values(by='predicted_probability', ascending=False)

    movie_df = movie_df.sort_values(by='predicted_probability', ascending=False)

    top_tv_df = tv_df.copy()
    top_movie_df = movie_df.copy()

    # Re-Rank
    if not top_tv_df.empty:
        top_tv_df['rank'] = top_tv_df['predicted_probability'].rank(method='first', ascending=False).astype(int)
    if not top_movie_df.empty:
        top_movie_df['rank'] = top_movie_df['predicted_probability'].rank(method='first', ascending=False).astype(int)


    top_df_list = [d for d in [top_tv_df, top_movie_df] if not d.empty]
    if top_df_list:
        top_df = pd.concat(top_df_list)
    else:
        top_df = pd.DataFrame()
    
    # Fill missing columns for final output if needed (e.g. episode_number might be null for seasons)
    if 'episode_number' not in top_df.columns:
        top_df['episode_number'] = None
    if 'season_number' not in top_df.columns:
        top_df['season_number'] = None

    df = top_df # replace original df with stored top_df
    
    df['username'] = username
    df['scored_at'] = datetime.now()
    df['model_name'] = model_name
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
    df_shap = df.sort_values(by='predicted_probability', ascending=False)
    if SHAP_MAX_ITEMS > 0:
        df_shap = df_shap.head(SHAP_MAX_ITEMS)
    else:
        df_shap = df_shap.head(0)

    if df_shap.empty:
        print("⏩ No rows selected for SHAP (SHAP_MAX_ITEMS=0).")
        return

    print(f"🔍 Limiting SHAP to top {len(df_shap)} items (SHAP_MAX_ITEMS={SHAP_MAX_ITEMS})")
    if 'shap_source_index' in df_shap.columns:
        shap_idx = [int(i) for i in df_shap['shap_source_index'].tolist()]
    else:
        shap_idx = [int(i) for i in df_shap.index.tolist()]

    X_top = X_df.loc[shap_idx]
    print("🔍 SHAP input shape:", X_top.shape)
    print("🔍 Unique rows in input:", np.unique(X_top.to_numpy(), axis=0).shape[0])
    print("🔍 Sample input rows:")
    print(X_top.head(3))  # or print(X_top[:3]) if it's a NumPy array

    # Optional deeper print
    for i in range(min(5, len(X_top))):
        print(f"Row {i} summary hash: {hash(tuple(np.round(X_top.iloc[i].values, 4)))}")
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

    for i, row in enumerate(df_shap.itertuples()):
        shap_row = shap_values[i]
        top_features = sorted(zip(feature_names, shap_row), key=lambda x: abs(x[1]), reverse=True)[:3]
        formatted = ", ".join([f"{name} ({value:+.2f})" for name, value in top_features])
        print(f"Rank {row.rank}: {row.rating_key} — {formatted}")

        if SHAP_TOP_DIMS <= 0:
            continue
        top_dims = sorted(enumerate(shap_row[:1536]), key=lambda x: abs(x[1]), reverse=True)[:SHAP_TOP_DIMS]
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
