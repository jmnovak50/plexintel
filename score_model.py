from dotenv import load_dotenv
load_dotenv()

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
from api.db.connection import connect_db, get_database_url
from api.db.schema import ensure_app_schema
from api.services.app_settings import get_setting_value

warnings.filterwarnings("ignore", category=UserWarning, module='sklearn')

SHAP_PRUNE_DAYS = get_setting_value("scoring.shap_prune_days", default=3)
SHAP_TARGETING_STRATEGY = get_setting_value("scoring.shap_targeting_strategy", default="per_media_type")
SHAP_MAX_ITEMS = get_setting_value("scoring.shap_max_items", default=100)
SHAP_MAX_ITEMS_OVERALL = get_setting_value("scoring.shap_max_items_overall", default=100)
SHAP_MAX_ITEMS_MOVIE = get_setting_value("scoring.shap_max_items_movie", default=250)
SHAP_MAX_ITEMS_TV = get_setting_value("scoring.shap_max_items_tv", default=250)
SHAP_RAW_MIN_DIMS = get_setting_value("scoring.shap_raw_min_dims", default=5)
SHAP_RAW_MAX_DIMS = get_setting_value("scoring.shap_raw_max_dims", default=20)
SHAP_RAW_CUMABS_TARGET = get_setting_value("scoring.shap_raw_cumabs_target", default=0.90)
SHAP_AGG_TOP_DIMS = get_setting_value("scoring.shap_agg_top_dims", default=50)
WATCHED_ENGAGEMENT_THRESHOLD = get_setting_value("scoring.watched_engagement_threshold", default=0.5)
WATCH_EMBED_MIN_ENGAGEMENT = get_setting_value("training.watch_embed_min_engagement", default=0.5)
DB_URL = get_database_url()
SHAP_TV_DISPLAY_LEVEL = "show"
TV_ROLLUP_TOP_FRACTION = 0.20
RECOMMENDATIONS_TABLE = "recommendations"
RECOMMENDATIONS_STAGING_TABLE = "recommendations_new"
RECOMMENDATION_SWAP_COLUMNS = [
    "username",
    "rating_key",
    "predicted_probability",
    "model_name",
    "scored_at",
    "rank",
    "was_recommended",
    "shown_at",
    "watched_after",
    "explanation",
    "cosine_similarity",
    "embedding_theme",
]

def get_engine():
    return create_engine(DB_URL)

def prepare_recommendations_staging_table(engine):
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS public.{RECOMMENDATIONS_STAGING_TABLE}"))
        conn.execute(
            text(
                f"""
                CREATE TABLE public.{RECOMMENDATIONS_STAGING_TABLE}
                (LIKE public.{RECOMMENDATIONS_TABLE} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)
                """
            )
        )
        conn.execute(text(f"ALTER TABLE public.{RECOMMENDATIONS_STAGING_TABLE} ALTER COLUMN id DROP DEFAULT"))
        conn.execute(text(f"ALTER TABLE public.{RECOMMENDATIONS_STAGING_TABLE} ALTER COLUMN id DROP NOT NULL"))
    print(f"🧱 Prepared public.{RECOMMENDATIONS_STAGING_TABLE} for staged recommendations")

def drop_recommendations_staging_table(engine):
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS public.{RECOMMENDATIONS_STAGING_TABLE}"))

def swap_recommendations_from_staging(engine):
    columns_sql = ", ".join(RECOMMENDATION_SWAP_COLUMNS)
    with engine.begin() as conn:
        conn.execute(text(f"LOCK TABLE public.{RECOMMENDATIONS_TABLE} IN EXCLUSIVE MODE"))
        conn.execute(text(f"DELETE FROM public.{RECOMMENDATIONS_TABLE}"))
        conn.execute(
            text(
                f"""
                INSERT INTO public.{RECOMMENDATIONS_TABLE} ({columns_sql})
                SELECT {columns_sql}
                FROM public.{RECOMMENDATIONS_STAGING_TABLE}
                """
            )
        )
        conn.execute(text(f"DROP TABLE public.{RECOMMENDATIONS_STAGING_TABLE}"))
    print("🔁 Atomically swapped staged recommendations into public.recommendations")

def ensure_shap_snapshot_schema(conn):
    """
    Ensure the current-run SHAP aggregate table exists.
    Raw shap_impact already exists in schema and is treated as the UI/debug snapshot.
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.shap_dimension_stats_current (
            dimension integer PRIMARY KEY,
            usage_count integer NOT NULL DEFAULT 0,
            sum_abs_shap double precision NOT NULL DEFAULT 0,
            avg_abs_shap double precision NOT NULL DEFAULT 0,
            combined_score double precision NOT NULL DEFAULT 0,
            user_count integer NOT NULL DEFAULT 0,
            modified_at timestamp without time zone NOT NULL DEFAULT now()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shap_dimension_stats_current_score
        ON public.shap_dimension_stats_current (combined_score DESC)
        """
    )
    conn.commit()
    cur.close()

def reset_shap_snapshot_tables():
    conn = connect_db()
    try:
        ensure_shap_snapshot_schema(conn)
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE shap_impact")
        cur.execute("TRUNCATE TABLE shap_dimension_stats_current")
        conn.commit()
        cur.close()
        print("🧹 Reset SHAP snapshot tables (shap_impact, shap_dimension_stats_current)")
    finally:
        conn.close()

def _sorted_embedding_shap_dims(shap_row, embed_dim=1536):
    dims = []
    for dim, shap_val in enumerate(shap_row[:embed_dim]):
        val = float(shap_val)
        if not np.isfinite(val):
            val = 0.0
        dims.append((dim, val, abs(val)))
    dims.sort(key=lambda x: x[2], reverse=True)
    return dims

def _select_raw_shap_dims(sorted_dims):
    max_dims = max(0, SHAP_RAW_MAX_DIMS)
    if max_dims == 0:
        return []

    min_dims = max(0, SHAP_RAW_MIN_DIMS)
    min_dims = min(min_dims, max_dims)
    cum_target = max(0.0, min(1.0, SHAP_RAW_CUMABS_TARGET))

    total_abs = sum(abs_val for _, _, abs_val in sorted_dims)
    target_abs = total_abs * cum_target

    selected = []
    cum_abs = 0.0
    for dim, val, abs_val in sorted_dims[:max_dims]:
        selected.append((dim, val))
        cum_abs += abs_val
        if len(selected) >= min_dims:
            if total_abs == 0.0 or cum_abs >= target_abs:
                break

    if len(selected) < min_dims:
        selected = [(dim, val) for dim, val, _ in sorted_dims[:min_dims]]

    return selected

def _select_agg_shap_dims(sorted_dims):
    if SHAP_AGG_TOP_DIMS <= 0:
        return []
    top_n = max(0, SHAP_AGG_TOP_DIMS)
    return sorted_dims[:top_n]

def _normalize_shap_strategy(strategy):
    normalized = str(strategy or "per_media_type").strip().lower().replace("-", "_")
    if normalized in {"global", "legacy", "legacy_global"}:
        return "global"
    return "per_media_type"

def _nonnegative_int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

def _sort_by_probability(df, *, stable_ties=False):
    if df.empty:
        return df.copy()
    if stable_ties and "rating_key" in df.columns:
        return df.sort_values(
            by=["predicted_probability", "rating_key"],
            ascending=[False, True],
        )
    return df.sort_values(by="predicted_probability", ascending=False)

def _top_displayed_show_representative_rows(df, limit):
    limit = _nonnegative_int(limit)
    if limit <= 0 or df.empty or "show_rating_key" not in df.columns:
        return df.head(0).copy()

    media_type = df["media_type"].fillna("").astype(str).str.lower()
    episodes = df[(media_type == "episode") & df["show_rating_key"].notna()].copy()
    if episodes.empty:
        return episodes

    episodes = episodes.sort_values(
        by=["show_rating_key", "predicted_probability", "rating_key"],
        ascending=[True, False, True],
    )
    group = episodes.groupby("show_rating_key", dropna=True)
    episodes["_visible_rank"] = group.cumcount() + 1
    episodes["_visible_episode_count"] = group["rating_key"].transform("count")
    episodes["_visible_top_k"] = np.ceil(
        episodes["_visible_episode_count"] * TV_ROLLUP_TOP_FRACTION
    ).astype(int).clip(lower=1)

    topk_rows = episodes[episodes["_visible_rank"] <= episodes["_visible_top_k"]]
    rollup_scores = topk_rows.groupby("show_rating_key")["predicted_probability"].mean()

    representatives = episodes[episodes["_visible_rank"] == 1].copy()
    representatives["_display_rollup_score"] = representatives["show_rating_key"].map(rollup_scores)
    representatives = representatives.sort_values(
        by=["_display_rollup_score", "predicted_probability", "rating_key"],
        ascending=[False, False, True],
    )
    return representatives.head(limit).drop(
        columns=[
            "_visible_rank",
            "_visible_episode_count",
            "_visible_top_k",
            "_display_rollup_score",
        ],
        errors="ignore",
    )

def _append_unique_targets(selected_indices, selected_keys, candidates, *, limit=None):
    added = 0
    max_add = None if limit is None else _nonnegative_int(limit)
    for idx, row in candidates.iterrows():
        if max_add is not None and added >= max_add:
            break
        try:
            rating_key = int(row["rating_key"])
        except (KeyError, TypeError, ValueError):
            continue
        if rating_key in selected_keys:
            continue
        selected_keys.add(rating_key)
        selected_indices.append(idx)
        added += 1
    return added

def select_shap_target_rows(
    df,
    *,
    strategy=None,
    global_limit=None,
    overall_limit=None,
    movie_limit=None,
    tv_limit=None,
):
    """
    Select scored recommendation rows that should receive raw SHAP rows.

    Recommendation rows are deduplicated by rating_key because shap_impact is
    stored by (user_id, rating_key, dimension). TV top-level cards are show
    rollups in the UI/digest; until SHAP storage gains a show-level aggregate,
    the selector targets the top contributing episode row for each selected show.
    """
    strategy = _normalize_shap_strategy(SHAP_TARGETING_STRATEGY if strategy is None else strategy)
    selected_indices = []
    selected_keys = set()

    if strategy == "global":
        limit = _nonnegative_int(SHAP_MAX_ITEMS if global_limit is None else global_limit)
        candidates = _sort_by_probability(df)
        added = _append_unique_targets(selected_indices, selected_keys, candidates, limit=limit)
        selected = df.loc[selected_indices].copy() if selected_indices else df.head(0).copy()
        summary = {
            "strategy": "global",
            "tv_display_level": SHAP_TV_DISPLAY_LEVEL,
            "source_counts": {"overall/global": added},
            "deduped_total": len(selected),
        }
        return selected, summary

    media_type = df["media_type"].fillna("").astype(str).str.lower()
    movie_limit = _nonnegative_int(SHAP_MAX_ITEMS_MOVIE if movie_limit is None else movie_limit)
    tv_limit = _nonnegative_int(SHAP_MAX_ITEMS_TV if tv_limit is None else tv_limit)
    overall_limit = _nonnegative_int(
        SHAP_MAX_ITEMS_OVERALL if overall_limit is None else overall_limit
    )

    source_counts = {}

    movie_candidates = _sort_by_probability(df[media_type == "movie"], stable_ties=True).head(movie_limit)
    source_counts["movie"] = _append_unique_targets(
        selected_indices,
        selected_keys,
        movie_candidates,
    )

    show_candidates = _top_displayed_show_representative_rows(df, tv_limit)
    source_counts[SHAP_TV_DISPLAY_LEVEL] = _append_unique_targets(
        selected_indices,
        selected_keys,
        show_candidates,
    )

    overall_candidates = _sort_by_probability(df, stable_ties=True)
    source_counts["overall/additional catch-all"] = _append_unique_targets(
        selected_indices,
        selected_keys,
        overall_candidates,
        limit=overall_limit,
    )

    selected = df.loc[selected_indices].copy() if selected_indices else df.head(0).copy()
    summary = {
        "strategy": "per-media-type",
        "tv_display_level": SHAP_TV_DISPLAY_LEVEL,
        "source_counts": source_counts,
        "deduped_total": len(selected),
    }
    return selected, summary

def format_shap_targeting_summary(summaries):
    if isinstance(summaries, dict):
        summaries = [summaries]
    summaries = [summary for summary in summaries if summary]
    if not summaries:
        return "SHAP target selection strategy: none\nUsers scored: 0"

    strategy = summaries[0].get("strategy", "unknown")
    user_count = len(summaries)
    labels = []
    for summary in summaries:
        for label in summary.get("source_counts", {}):
            if label not in labels:
                labels.append(label)

    lines = [
        f"SHAP target selection strategy: {strategy}",
        f"Users scored: {user_count}",
        "",
        "Media Type | Selected Cards | Cards Per User Min | Cards Per User Max",
        "--- | ---: | ---: | ---:",
    ]
    for label in labels:
        counts = [int(summary.get("source_counts", {}).get(label, 0)) for summary in summaries]
        lines.append(f"{label} | {sum(counts)} | {min(counts)} | {max(counts)}")

    total = sum(int(summary.get("deduped_total", 0)) for summary in summaries)
    lines.extend([
        "",
        f"Deduplicated total recommendation cards receiving raw SHAP rows: {total}",
    ])
    if any(summary.get("tv_display_level") == "show" for summary in summaries):
        lines.append(
            "TV display level: show rollups; raw SHAP rows use the top contributing episode recommendation key for each selected show."
        )
    return "\n".join(lines)

def _upsert_shap_dimension_stats_current(cur, user_dim_agg):
    for dim, stats in user_dim_agg.items():
        usage_count = int(stats["usage_count"])
        sum_abs = float(stats["sum_abs_shap"])
        if usage_count <= 0:
            continue
        avg_abs = sum_abs / usage_count
        combined_score = sum_abs * np.log1p(usage_count)
        cur.execute(
            """
            INSERT INTO shap_dimension_stats_current (
                dimension, usage_count, sum_abs_shap, avg_abs_shap, combined_score, user_count, modified_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (dimension)
            DO UPDATE SET
                usage_count = shap_dimension_stats_current.usage_count + EXCLUDED.usage_count,
                sum_abs_shap = shap_dimension_stats_current.sum_abs_shap + EXCLUDED.sum_abs_shap,
                user_count = shap_dimension_stats_current.user_count + EXCLUDED.user_count,
                avg_abs_shap = (
                    shap_dimension_stats_current.sum_abs_shap + EXCLUDED.sum_abs_shap
                ) / NULLIF(shap_dimension_stats_current.usage_count + EXCLUDED.usage_count, 0),
                combined_score = (
                    shap_dimension_stats_current.sum_abs_shap + EXCLUDED.sum_abs_shap
                ) * LN(1 + (shap_dimension_stats_current.usage_count + EXCLUDED.usage_count)),
                modified_at = NOW()
            """,
            (dim, usage_count, sum_abs, avg_abs, float(combined_score), 1)
        )

def parse_vector(x):
    if isinstance(x, str):
        return np.array(ast.literal_eval(x), dtype=np.float32)
    return np.array(x, dtype=np.float32)

def normalize_tag_list(value):
    if isinstance(value, (list, tuple, set)):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if value is None or pd.isna(value):
        return []
    return [tag.strip() for tag in str(value).split(",") if tag.strip()]

def get_user_watch_vector(username):
    """
    Build a per-user average watch-embedding vector (from watch_history + watch_embeddings).
    Only includes watch events above WATCH_EMBED_MIN_ENGAGEMENT.
    """
    conn = connect_db()
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
            m.show_rating_key,
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
                            WHEN w.percent_complete >= 1 THEN w.percent_complete / 100.0
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
            SELECT ma.media_id, STRING_AGG(a.name, ',' ORDER BY ma.cast_order NULLS LAST, a.name) AS actor_tags
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
              AND f.feedback <> 'interested'
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
    feature_names_template = [str(name) for name in feature_names_template]

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

    df['genres'] = df['genre_tags'].apply(normalize_tag_list)
    df['actors'] = df['actor_tags'].apply(normalize_tag_list)
    df['directors'] = df['director_tags'].apply(normalize_tag_list)

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

    genre_top = [f.split("_", 1)[1] for f in feature_names_template if f.startswith("genre_")]
    actor_top = [f.split("_", 1)[1] for f in feature_names_template if f.startswith("actor_")]
    director_top = [f.split("_", 1)[1] for f in feature_names_template if f.startswith("director_")]
    decade_features = [f for f in feature_names_template if f.startswith("is_") and f.endswith("s")]

    def filter_known(labels, allowed_set):
        return [label for label in labels if label in allowed_set]

    df['genres'] = df['genres'].apply(lambda x: filter_known(x, set(genre_top)))
    df['actors'] = df['actors'].apply(lambda x: filter_known(x, set(actor_top)))
    df['directors'] = df['directors'].apply(lambda x: filter_known(x, set(director_top)))

    genre_bin = MultiLabelBinarizer(classes=genre_top)
    actor_bin = MultiLabelBinarizer(classes=actor_top)
    director_bin = MultiLabelBinarizer(classes=director_top)

    embedding_features = [f"emb_{i}" for i in range(len(df['embedding'].iloc[0]))]
    feature_df = pd.DataFrame(
        np.vstack(df['embedding'].values),
        columns=embedding_features,
        index=df.index,
    )
    feature_df = pd.concat(
        [
            feature_df,
            pd.DataFrame(
                genre_bin.fit_transform(df['genres']),
                columns=[f"genre_{genre}" for genre in genre_top],
                index=df.index,
            ),
            pd.DataFrame(
                actor_bin.fit_transform(df['actors']),
                columns=[f"actor_{actor}" for actor in actor_top],
                index=df.index,
            ),
            pd.DataFrame(
                director_bin.fit_transform(df['directors']),
                columns=[f"director_{director}" for director in director_top],
                index=df.index,
            ),
        ],
        axis=1,
    )

    decade_df = pd.DataFrame(0, columns=decade_features, index=df.index, dtype=np.int8)
    for idx, flags in df['year'].apply(get_decade_flags).items():
        for feature in flags:
            if feature in decade_df.columns:
                decade_df.at[idx, feature] = 1
    feature_df = pd.concat([feature_df, decade_df], axis=1)
    feature_df["watch_sim"] = watch_sim

    feature_df = feature_df.reindex(columns=feature_names_template, fill_value=0)
    X = feature_df.values
    active_decades = [col for col in decade_features if feature_df[col].any()]
    print("📆 Decade columns active:", active_decades)

    return X, df

def cosine_similarity_batch(user_embeddings, media_embeddings):
    dot_products = np.einsum('ij,ij->i', user_embeddings, media_embeddings)
    norms_user = np.linalg.norm(user_embeddings, axis=1)
    norms_media = np.linalg.norm(media_embeddings, axis=1)
    similarities = dot_products / (norms_user * norms_media)
    return similarities

def score_and_store(
    username,
    skip_shap=False,
    recommendations_table=RECOMMENDATIONS_TABLE,
    replace_existing=True,
):
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
    with engine.begin() as conn:
        if replace_existing:
            conn.execute(
                text(f"DELETE FROM public.{RECOMMENDATIONS_TABLE} WHERE username = :username"),
                {"username": username},
            )
        output.to_sql(recommendations_table, conn, if_exists="append", index=False, schema="public")
    if recommendations_table == RECOMMENDATIONS_TABLE:
        print(f"✅ Replaced recommendations for {username} with {len(output)} scored items.")
    else:
        print(f"✅ Staged recommendations for {username} with {len(output)} scored items.")
    if skip_shap:
        print("⏩ Skipping SHAP impact generation.")
        return None
    explainer = shap.TreeExplainer(model)
    df_shap, shap_target_summary = select_shap_target_rows(df)

    if df_shap.empty:
        print(format_shap_targeting_summary(shap_target_summary))
        print("⏩ No rows selected for SHAP.")
        return shap_target_summary

    print(format_shap_targeting_summary(shap_target_summary))
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
    conn = connect_db()
    cur = conn.cursor()
    ensure_shap_snapshot_schema(conn)

    # Per-user reset keeps single-user runs consistent when not using all-users snapshot reset.
    cur.execute("DELETE FROM shap_impact WHERE user_id = %s", (username,))
    deleted = cur.rowcount
    conn.commit()
    print(f"🧹 Reset {deleted:,} existing SHAP rows for {username} before rebuild")

    user_dim_agg = {}

    for i, row in enumerate(df_shap.itertuples()):
        shap_row = shap_values[i]
        top_features = sorted(zip(feature_names, shap_row), key=lambda x: abs(x[1]), reverse=True)[:3]
        formatted = ", ".join([f"{name} ({value:+.2f})" for name, value in top_features])
        print(f"Rank {row.rank}: {row.rating_key} — {formatted}")

        sorted_dims = _sorted_embedding_shap_dims(shap_row)
        raw_dims = _select_raw_shap_dims(sorted_dims)
        for dim, shap_val in raw_dims:
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

        for dim, _shap_val, abs_val in _select_agg_shap_dims(sorted_dims):
            stats = user_dim_agg.setdefault(dim, {"usage_count": 0, "sum_abs_shap": 0.0})
            stats["usage_count"] += 1
            stats["sum_abs_shap"] += float(abs_val)

    _upsert_shap_dimension_stats_current(cur, user_dim_agg)
    conn.commit()
    print(f"📊 Upserted {len(user_dim_agg)} aggregate SHAP dimension rows for {username}")
    cur.close()
    conn.close()
    return shap_target_summary

def get_all_users():
    engine = get_engine()
    query = "SELECT DISTINCT username FROM watch_history"
    df = pd.read_sql(query, engine)
    return df['username'].tolist()

if __name__ == "__main__":
    import argparse

    ensure_app_schema()
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user", type=str, help="Username to score recommendations for")
    group.add_argument("--all-users", action="store_true", help="Score recommendations for all users with watch history")
    parser.add_argument("--skip-shap", action="store_true", help="Skip SHAP impact generation")
    args = parser.parse_args()

    if args.all_users:
        engine = get_engine()
        prepare_recommendations_staging_table(engine)
        swapped_recommendations = False
        try:
            if not args.skip_shap:
                reset_shap_snapshot_tables()
            users = get_all_users()
            print(f"🔁 Scoring for all users: {users}")
            shap_target_summaries = []
            for user in users:
                summary = score_and_store(
                    user,
                    skip_shap=args.skip_shap,
                    recommendations_table=RECOMMENDATIONS_STAGING_TABLE,
                    replace_existing=False,
                )
                if summary:
                    shap_target_summaries.append(summary)
            swap_recommendations_from_staging(engine)
            swapped_recommendations = True
            if shap_target_summaries:
                print("\n📊 All-user SHAP targeting summary")
                print(format_shap_targeting_summary(shap_target_summaries))
        finally:
            if not swapped_recommendations:
                drop_recommendations_staging_table(engine)
    else:
        score_and_store(args.user, skip_shap=args.skip_shap)
