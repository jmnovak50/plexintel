# train_model.py

from dotenv import load_dotenv
load_dotenv()
import pandas as pd
import numpy as np
import psycopg2
from sqlalchemy import create_engine
import os
from urllib.parse import urlsplit, urlunsplit

from api.db.connection import get_database_url

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Configs (adapt this to your actual setup)
DB_URL = get_database_url()


def _redact_db_url(url):
    if not url:
        return "<missing>"

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        netloc = hostname
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        if parsed.username:
            netloc = f"{parsed.username}:***@{netloc}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except Exception:
        return "<unparseable>"


def load_training_data():
    if not DB_URL:
        raise RuntimeError(
            "No database connection configured. Set DATABASE_URL or DB_NAME/DB_USER/DB_HOST/DB_PORT."
        )

    print(f"🔌 Loading training_data from {_redact_db_url(DB_URL)}")
    engine = create_engine(DB_URL)
    query = "SELECT * FROM training_data WHERE embedding IS NOT NULL"
    df = pd.read_sql(query, engine)
    print(f"📦 Loaded {len(df)} training rows with non-null embeddings.")
    return df

from sklearn.preprocessing import MultiLabelBinarizer
import ast


def normalize_tag_list(value):
    if isinstance(value, (list, tuple, set)):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if value is None or pd.isna(value):
        return []
    return [tag.strip() for tag in str(value).split(",") if tag.strip()]


def load_actor_distinct_title_stats():
    """
    Count actor coverage and concentration by distinct show/movie keys.

    Episodes use show_rating_key when available so a long TV series counts as one
    title. Movies use their own rating_key.
    """
    engine = create_engine(DB_URL)
    query = """
        WITH actor_media AS (
            SELECT
                a.name AS actor_name,
                l.rating_key,
                l.media_type,
                COALESCE(l.show_rating_key, l.rating_key) AS title_key,
                COALESCE(NULLIF(l.show_title, ''), show.title, l.title) AS title_name
            FROM media_actors ma
            JOIN actors a ON a.id = ma.actor_id
            JOIN library l ON l.rating_key = ma.media_id
            LEFT JOIN library show ON show.rating_key = l.show_rating_key
            WHERE l.media_type IN ('movie', 'episode')
        ),
        actor_counts AS (
            SELECT
                actor_name,
                COUNT(*) AS raw_media_row_count,
                COUNT(*) FILTER (WHERE media_type = 'episode') AS episode_count,
                COUNT(DISTINCT title_key) AS distinct_show_movie_count
            FROM actor_media
            GROUP BY actor_name
        ),
        title_counts AS (
            SELECT
                actor_name,
                title_key,
                MAX(title_name) AS title_name,
                COUNT(*) AS title_row_count
            FROM actor_media
            GROUP BY actor_name, title_key
        ),
        ranked_titles AS (
            SELECT
                actor_name,
                title_name,
                title_row_count,
                ROW_NUMBER() OVER (
                    PARTITION BY actor_name
                    ORDER BY title_row_count DESC, title_name
                ) AS rn
            FROM title_counts
        ),
        title_concentration AS (
            SELECT
                actor_name,
                MAX(title_name) FILTER (WHERE rn = 1) AS top_show_movie,
                MAX(title_row_count) FILTER (WHERE rn = 1) AS top_show_movie_count,
                SUM(title_row_count) FILTER (WHERE rn <= 3) AS top3_show_movie_count
            FROM ranked_titles
            GROUP BY actor_name
        )
        SELECT
            ac.actor_name,
            ac.raw_media_row_count,
            ac.episode_count,
            ac.distinct_show_movie_count,
            tc.top_show_movie,
            COALESCE(tc.top_show_movie_count, 0) AS top_show_movie_count,
            COALESCE(tc.top3_show_movie_count, 0) AS top3_show_movie_count,
            COALESCE(tc.top_show_movie_count, 0)::float / NULLIF(ac.raw_media_row_count, 0) AS top1_concentration,
            COALESCE(tc.top3_show_movie_count, 0)::float / NULLIF(ac.raw_media_row_count, 0) AS top3_concentration
        FROM actor_counts ac
        LEFT JOIN title_concentration tc
            ON tc.actor_name = ac.actor_name
    """
    return pd.read_sql(query, engine).set_index("actor_name").to_dict("index")


def actor_filter_reasons(
    actor,
    actor_stats,
    min_distinct_titles=None,
    max_top1_concentration=None,
    max_top3_concentration=None,
):
    stats = actor_stats.get(actor, {})
    reasons = []

    distinct_count = int(stats.get("distinct_show_movie_count", 0) or 0)
    top1_concentration = float(stats.get("top1_concentration", 0) or 0)
    top3_concentration = float(stats.get("top3_concentration", 0) or 0)

    if min_distinct_titles is not None and distinct_count < min_distinct_titles:
        reasons.append(f"distinct_titles<{min_distinct_titles}")
    if max_top1_concentration is not None and top1_concentration > max_top1_concentration:
        reasons.append(f"top1_concentration>{max_top1_concentration:.2f}")
    if max_top3_concentration is not None and top3_concentration > max_top3_concentration:
        reasons.append(f"top3_concentration>{max_top3_concentration:.2f}")

    return reasons


def print_actor_filter_diagnostics(
    raw_actor_candidates,
    eligible_actor_candidates,
    actor_stats,
    excluded_reasons,
    min_distinct_titles=None,
    max_top1_concentration=None,
    max_top3_concentration=None,
):
    raw_set = set(raw_actor_candidates)
    eligible_set = set(eligible_actor_candidates)
    excluded = []
    for actor in raw_actor_candidates:
        if actor in eligible_set:
            continue
        stats = actor_stats.get(actor, {})
        excluded.append({
            "actor": actor,
            "raw_media_row_count": int(stats.get("raw_media_row_count", 0) or 0),
            "episode_count": int(stats.get("episode_count", 0) or 0),
            "distinct_show_movie_count": int(stats.get("distinct_show_movie_count", 0) or 0),
            "top_show_movie": stats.get("top_show_movie", ""),
            "top_show_movie_count": int(stats.get("top_show_movie_count", 0) or 0),
            "top1_concentration": float(stats.get("top1_concentration", 0) or 0),
            "top3_concentration": float(stats.get("top3_concentration", 0) or 0),
            "reason": ", ".join(excluded_reasons.get(actor, [])),
        })
    excluded.sort(key=lambda row: row["raw_media_row_count"], reverse=True)

    print("🎭 Actor feature eligibility filters:")
    if min_distinct_titles is not None:
        print(f"   - minimum distinct shows/movies = {min_distinct_titles}")
    if max_top1_concentration is not None:
        print(f"   - maximum top-1 show/movie concentration = {max_top1_concentration:.2f}")
    if max_top3_concentration is not None:
        print(f"   - maximum top-3 show/movie concentration = {max_top3_concentration:.2f}")
    print(f"🎭 Actor features before filtering: {len(raw_set)}")
    print(f"🎭 Actor features after filtering: {len(eligible_set)}")
    if not excluded:
        print("🎭 No top actor candidates were excluded by actor eligibility filtering.")
    else:
        concentration_excluded = [
            row for row in excluded
            if "concentration>" in row["reason"]
        ]
        print(f"🎭 Actors excluded by concentration: {len(concentration_excluded)}")
        print("🎭 Top excluded actor candidates by raw media row count:")
        print(
            "actor | total_rows | episode_count | distinct_shows_movies | "
            "top1_show_movie | top1_rows | top1_concentration | top3_concentration | reason"
        )
        for row in excluded[:15]:
            print(
                f"{row['actor']} | "
                f"{row['raw_media_row_count']} | "
                f"{row['episode_count']} | "
                f"{row['distinct_show_movie_count']} | "
                f"{row['top_show_movie']} | "
                f"{row['top_show_movie_count']} | "
                f"{row['top1_concentration']:.3f} | "
                f"{row['top3_concentration']:.3f} | "
                f"{row['reason']}"
            )

    print("🎭 Focus actor status:")
    print(
        "actor | status | total_rows | distinct_shows_movies | top1_show_movie | "
        "top1_rows | top1_concentration | top3_concentration | reason"
    )
    for actor in ["Drew Powell", "Michael McKean"]:
        stats = actor_stats.get(actor, {})
        if actor in raw_set:
            status = "retained" if actor in eligible_set else "excluded"
        else:
            status = "not in top actor candidates"
        reason = ", ".join(excluded_reasons.get(actor, [])) if actor in excluded_reasons else ""
        print(
            f"{actor} | "
            f"{status} | "
            f"{int(stats.get('raw_media_row_count', 0) or 0)} | "
            f"{int(stats.get('distinct_show_movie_count', 0) or 0)} | "
            f"{stats.get('top_show_movie', '')} | "
            f"{int(stats.get('top_show_movie_count', 0) or 0)} | "
            f"{float(stats.get('top1_concentration', 0) or 0):.3f} | "
            f"{float(stats.get('top3_concentration', 0) or 0):.3f} | "
            f"{reason}"
        )


def preprocess(
    df,
    top_k=20,
    genre_top_k=None,
    actor_top_k=None,
    director_top_k=None,
    exclude_actors=False,
    min_actor_distinct_titles=None,
    max_actor_top1_concentration=None,
    max_actor_top3_concentration=None,
):
    # Turn vector column into actual np.ndarray
    if df.empty:
        raise RuntimeError(
            "training_data has no rows with non-null embeddings. "
            "Run build_training_data.py and confirm it reports inserted rows in the same database."
        )

    required_columns = ["embedding", "label", "genre_tags", "director_tags", "release_year"]
    if not exclude_actors:
        required_columns.append("actor_tags")
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise RuntimeError(
            "training_data is missing required columns: " + ", ".join(missing_columns)
        )

    def safe_embedding_parse(x):
        if isinstance(x, str):
            return np.array(ast.literal_eval(x), dtype=np.float32)
        return np.array(x, dtype=np.float32)

    df['embedding'] = df['embedding'].apply(safe_embedding_parse)
    df = df[df['embedding'].apply(lambda value: value.size > 0)].copy()
    if df.empty:
        raise RuntimeError("training_data rows were found, but every embedding was empty.")

    # 🎞️ Decade features from release_year
    def get_decade_flags(year):
        if year is None or pd.isna(year):
            return {}

        try:
            decade = int(year) // 10 * 10
            return {f"is_{decade}s": 1}
        except:
            return {}

    decade_df = df['release_year'].apply(get_decade_flags).apply(pd.Series).fillna(0).astype(int)


    # Split tags into normalized lists.
    df['genres'] = df['genre_tags'].apply(normalize_tag_list)
    if exclude_actors:
        df['actors'] = [[] for _ in range(len(df))]
    else:
        df['actors'] = df['actor_tags'].apply(normalize_tag_list)
    df['directors'] = df['director_tags'].apply(normalize_tag_list)

    def top_tags(col_name, tag_limit):
        tag_counts = df[col_name].explode().dropna().value_counts()
        return list(tag_counts.index if tag_limit is None else tag_counts.nlargest(tag_limit).index)

    # Binarize top-k tags for each category.
    def binarize_tags(col_name, tag_limit, allowed_tags=None):
        mlb = MultiLabelBinarizer()
        all_tags = top_tags(col_name, tag_limit)
        if allowed_tags is not None:
            allowed_set = set(allowed_tags)
            all_tags = [tag for tag in all_tags if tag in allowed_set]
        df[col_name] = df[col_name].apply(lambda tags: [tag for tag in tags if tag in all_tags])
        return pd.DataFrame(mlb.fit_transform(df[col_name]), columns=[f"{col_name[:-1]}_{t}" for t in mlb.classes_])

    actor_top_k = top_k if actor_top_k is None else actor_top_k
    director_top_k = top_k if director_top_k is None else director_top_k
    genre_features = binarize_tags('genres', genre_top_k)
    if exclude_actors:
        actor_features = pd.DataFrame(index=df.index)
    else:
        raw_actor_candidates = top_tags('actors', actor_top_k)
        allowed_actor_candidates = raw_actor_candidates
        if (
            min_actor_distinct_titles is not None
            or max_actor_top1_concentration is not None
            or max_actor_top3_concentration is not None
        ):
            actor_stats = load_actor_distinct_title_stats()
            excluded_reasons = {}
            allowed_actor_candidates = []
            for actor in raw_actor_candidates:
                reasons = actor_filter_reasons(
                    actor,
                    actor_stats,
                    min_distinct_titles=min_actor_distinct_titles,
                    max_top1_concentration=max_actor_top1_concentration,
                    max_top3_concentration=max_actor_top3_concentration,
                )
                if reasons:
                    excluded_reasons[actor] = reasons
                else:
                    allowed_actor_candidates.append(actor)
            # Experiment-only actor filtering: keep actor metadata intact, but
            # only eligible broad actor signals become direct actor_* model inputs.
            print_actor_filter_diagnostics(
                raw_actor_candidates,
                allowed_actor_candidates,
                actor_stats,
                excluded_reasons,
                min_distinct_titles=min_actor_distinct_titles,
                max_top1_concentration=max_actor_top1_concentration,
                max_top3_concentration=max_actor_top3_concentration,
            )
        actor_features = binarize_tags('actors', actor_top_k, allowed_tags=allowed_actor_candidates)
    director_features = binarize_tags('directors', director_top_k)

    # Stack features: embedding + tag binarizations
    X = np.vstack(df['embedding'].values)
    X = np.hstack((X, genre_features.values, actor_features.values, director_features.values, decade_df.values))

    # Optional: watch-embedding similarity feature
    if 'watch_sim' in df.columns:
        watch_sim = df['watch_sim'].fillna(0).astype(float).values.reshape(-1, 1)
    else:
        watch_sim = np.zeros((len(df), 1), dtype=np.float32)
    X = np.hstack((X, watch_sim))

    y = df['label'].astype(int).values

    if 'sample_weight' in df.columns:
        sample_weight = df['sample_weight'].fillna(1.0).astype(float).values
    else:
        sample_weight = np.ones(len(df), dtype=np.float32)

    embedding_dim = len(df['embedding'].iloc[0])
    feature_names = [f"emb_{i}" for i in range(embedding_dim)]  # ✅ Auto-detect
    feature_names += list(genre_features.columns)
    feature_names += list(actor_features.columns)
    feature_names += list(director_features.columns)
    feature_names += list(decade_df.columns)
    feature_names += ["watch_sim"]

    return X, y, sample_weight, feature_names


import xgboost as xgb
from xgboost import plot_importance
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score, precision_score, recall_score
import matplotlib.pyplot as plt
import joblib
from sklearn.model_selection import train_test_split

def train_and_evaluate(
    X,
    y,
    sample_weight,
    feature_names,
    model_output_path="xgb_model.pkl",
    importance_log_path="feature_importance_log.txt",
    importance_plot_path="feature_importance_plot.png",
    experiment_label="production no-direct-actor model",
):
    from sklearn.model_selection import train_test_split

    def class_balanced_sample_weights(labels, base_weights):
        neg_count = (labels == 0).sum()
        pos_count = (labels == 1).sum()
        if neg_count > 0 and pos_count > 0:
            return base_weights * np.where(labels == 0, pos_count / neg_count, 1.0), neg_count, pos_count
        return None, neg_count, pos_count

    print(f"🧪 Training mode: {experiment_label}")

    X_train, X_test, y_train, y_test, train_idx, test_idx = train_test_split(
        X, y, np.arange(len(y)), test_size=0.2, stratify=y, random_state=42
    )

    model = xgb.XGBClassifier(
        objective='binary:logistic',
        eval_metric='aucpr',
        scale_pos_weight=1.0,
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42
    )

    sample_weights, neg_count, pos_count = class_balanced_sample_weights(
        y_train,
        sample_weight[train_idx],
    )
    if sample_weights is not None:
        print(
            "📊 Class-balanced sample weights: "
            f"neg={neg_count}, pos={pos_count}, neg_weight={pos_count / neg_count:.2f}"
        )
    else:
        sample_weights = None
        print("⚠️ Skipping class-balanced sample weights because one class is missing from the train split.")

    model.fit(X_train, y_train, sample_weight=sample_weights)

    y_prob = model.predict_proba(X_test)[:, 1]
    threshold_metrics = []
    for threshold in np.arange(0.50, 0.701, 0.05):
        y_pred_at_threshold = (y_prob >= threshold).astype(int)
        class_0_precision = precision_score(y_test, y_pred_at_threshold, pos_label=0, zero_division=0)
        class_0_recall = recall_score(y_test, y_pred_at_threshold, pos_label=0, zero_division=0)
        class_0_f1 = f1_score(y_test, y_pred_at_threshold, pos_label=0, zero_division=0)
        class_1_f1 = f1_score(y_test, y_pred_at_threshold, pos_label=1, zero_division=0)
        macro_f1 = f1_score(y_test, y_pred_at_threshold, average="macro", zero_division=0)
        weighted_f1 = f1_score(y_test, y_pred_at_threshold, average="weighted", zero_division=0)
        threshold_metrics.append((
            threshold,
            class_0_precision,
            class_0_recall,
            class_0_f1,
            class_1_f1,
            macro_f1,
            weighted_f1,
        ))

    print("📊 Threshold comparison:")
    print("threshold | class_0_recall | class_0_f1 | macro_f1")
    for threshold, _class_0_precision, class_0_recall, class_0_f1, _class_1_f1, macro_f1, _weighted_f1 in threshold_metrics:
        print(f"{threshold:.2f}      | {class_0_recall:.3f}          | {class_0_f1:.3f}      | {macro_f1:.3f}")

    (
        recommended_threshold,
        recommended_class_0_precision,
        recommended_class_0_recall,
        recommended_class_0_f1,
        recommended_class_1_f1,
        recommended_macro_f1,
        recommended_weighted_f1,
    ) = max(
        threshold_metrics,
        key=lambda m: (m[3], m[5])
    )
    (
        macro_threshold,
        _macro_class_0_precision,
        macro_class_0_recall,
        macro_class_0_f1,
        _macro_class_1_f1,
        macro_macro_f1,
        _macro_weighted_f1,
    ) = max(
        threshold_metrics,
        key=lambda m: (m[5], m[3])
    )

    print(
        "🎯 Recommended operating threshold by class_0_f1, then macro_f1: "
        f"{recommended_threshold:.2f} "
        f"(class_0_recall={recommended_class_0_recall:.3f}, "
        f"class_0_f1={recommended_class_0_f1:.3f}, macro_f1={recommended_macro_f1:.3f})"
    )
    print(
        "📌 Best threshold by macro_f1, then class_0_f1: "
        f"{macro_threshold:.2f} "
        f"(class_0_recall={macro_class_0_recall:.3f}, "
        f"class_0_f1={macro_class_0_f1:.3f}, macro_f1={macro_macro_f1:.3f})"
    )
    print(
        "📝 Recommendation note: validation currently suggests a display threshold "
        "around 0.65-0.70 may be better than the default 0.50 for recommendation display. "
        "score_model.py is unchanged."
    )
    print("📊 Experiment summary row:")
    print("variant | feature_count | actor_feature_count | best_threshold | class_0_precision | class_0_recall | class_0_f1 | class_1_f1 | macro_f1 | weighted_f1")
    print(
        f"{experiment_label} | "
        f"{len(feature_names)} | "
        f"{sum(1 for name in feature_names if str(name).startswith('actor_'))} | "
        f"{recommended_threshold:.2f} | "
        f"{recommended_class_0_precision:.3f} | "
        f"{recommended_class_0_recall:.3f} | "
        f"{recommended_class_0_f1:.3f} | "
        f"{recommended_class_1_f1:.3f} | "
        f"{recommended_macro_f1:.3f} | "
        f"{recommended_weighted_f1:.3f}"
    )

    for threshold, *_unused_metrics in threshold_metrics:
        y_pred_at_threshold = (y_prob >= threshold).astype(int)
        print(f"\n📋 Classification report at threshold {threshold:.2f}")
        print(classification_report(y_test, y_pred_at_threshold, zero_division=0))
        print(f"🧮 Confusion matrix at threshold {threshold:.2f}")
        print(confusion_matrix(y_test, y_pred_at_threshold))

    y_pred = (y_prob >= recommended_threshold).astype(int)
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm)
    disp.plot()
    plt.title(f"XGBoost Confusion Matrix (threshold {recommended_threshold:.2f})")
    plt.show()

    final_sample_weights, full_neg_count, full_pos_count = class_balanced_sample_weights(
        y,
        sample_weight,
    )
    if final_sample_weights is not None:
        print(
            "📦 Re-training final model on all rows before saving: "
            f"neg={full_neg_count}, pos={full_pos_count}, neg_weight={full_pos_count / full_neg_count:.2f}"
        )
    else:
        print("⚠️ Saving split-trained model because one class is missing from the full dataset.")
    model.fit(X, y, sample_weight=final_sample_weights)
    model.get_booster().feature_names = feature_names

    # 📝 Log top N features to file
    importance_dict = model.get_booster().get_score(importance_type='gain')
    sorted_importances = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
    actor_importances = [
        (feature, score)
        for feature, score in sorted_importances
        if str(feature).startswith("actor_")
    ]

    print(f"📊 Final feature count: {len(feature_names)}")
    print(f"🎭 Final actor_* feature count: {sum(1 for name in feature_names if str(name).startswith('actor_'))}")
    if actor_importances:
        print("🎭 Top actor_* features by XGBoost gain:")
        for feature, score in actor_importances[:10]:
            print(f"{feature}: {score:.4f}")
    else:
        print("🎭 No actor_* features have nonzero XGBoost gain.")

    with open(importance_log_path, "w") as f:
        f.write(f"Top XGBoost Feature Importances (by gain) — {experiment_label}:\n\n")
        for feature, score in sorted_importances[:30]:  # Top 30
            f.write(f"{feature}: {score:.4f}\n")

    print(f"📝 Feature importance written to {importance_log_path}")

    # 📊 Feature importance plot
    plt.figure(figsize=(12, 6))
    plot_importance(model, max_num_features=20, importance_type='gain')
    plt.title(f"Top 20 Most Important Features (Gain) — {experiment_label}")
    plt.tight_layout()
    plt.savefig(importance_plot_path)  # 💾 Save to file
    plt.show()
    print(f"🖼️ Feature importance plot saved to {importance_plot_path}")

    joblib.dump(model, model_output_path)
    print(f"✅ XGBoost model saved to {model_output_path}")

    # Add this after training
    for feature, score in sorted_importances:
        if feature.startswith("is_"):
            print(f"{feature}: {score:.4f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train the PlexIntel XGBoost recommendation model.")
    parser.add_argument(
        "--exclude-actors",
        action="store_true",
        help=(
            "Deprecated no-op: direct actor_* binary features are now disabled "
            "by default. Kept so older scripts do not fail."
        ),
    )
    parser.add_argument(
        "--include-actors",
        action="store_true",
        help=(
            "Experimental: include direct actor_* binary features. These can "
            "behave like TV/show proxy features and make SHAP explanations less intuitive."
        ),
    )
    parser.add_argument(
        "--min-actor-distinct-titles",
        type=int,
        default=None,
        help=(
            "Train an experimental model that keeps actor_* features only for actors "
            "appearing across at least this many distinct shows/movies."
        ),
    )
    parser.add_argument(
        "--max-actor-top1-concentration",
        type=float,
        default=None,
        help=(
            "Train an experimental model that keeps actor_* features only when "
            "the actor's largest single show/movie accounts for no more than this "
            "fraction of the actor's media rows, e.g. 0.50."
        ),
    )
    parser.add_argument(
        "--max-actor-top3-concentration",
        type=float,
        default=None,
        help=(
            "Train an experimental model that keeps actor_* features only when "
            "the actor's three largest shows/movies account for no more than this "
            "fraction of the actor's media rows, e.g. 0.80."
        ),
    )
    parser.add_argument(
        "--model-output",
        default=None,
        help="Optional output path for the trained model. Experiment flags choose safe separate defaults.",
    )
    parser.add_argument(
        "--importance-log",
        default=None,
        help="Optional feature-importance log path. Experiment flags choose safe separate defaults.",
    )
    parser.add_argument(
        "--importance-plot",
        default=None,
        help="Optional feature-importance plot path. Experiment flags choose safe separate defaults.",
    )
    args = parser.parse_args()

    concentration_filter_supplied = (
        args.max_actor_top1_concentration is not None
        or args.max_actor_top3_concentration is not None
    )
    actor_eligibility_filter_supplied = (
        args.min_actor_distinct_titles is not None
        or concentration_filter_supplied
    )
    include_actor_features = args.include_actors or actor_eligibility_filter_supplied

    if args.exclude_actors and args.include_actors:
        parser.error("--exclude-actors is deprecated and cannot be combined with --include-actors.")
    if args.exclude_actors and actor_eligibility_filter_supplied:
        parser.error("--exclude-actors cannot be combined with actor eligibility filter experiments.")
    if args.min_actor_distinct_titles is not None and args.min_actor_distinct_titles < 1:
        parser.error("--min-actor-distinct-titles must be 1 or greater.")
    for flag_name, flag_value in [
        ("--max-actor-top1-concentration", args.max_actor_top1_concentration),
        ("--max-actor-top3-concentration", args.max_actor_top3_concentration),
    ]:
        if flag_value is not None and not (0 < flag_value <= 1):
            parser.error(f"{flag_name} must be greater than 0 and less than or equal to 1.")

    def concentration_slug(value):
        return f"{int(round(value * 100)):03d}"

    actor_filter_slug = None
    if args.min_actor_distinct_titles is not None:
        actor_filter_slug = f"actor_distinct_titles_{args.min_actor_distinct_titles}"
    if concentration_filter_supplied:
        slug_parts = ["actor_concentration"]
        if args.min_actor_distinct_titles is not None:
            slug_parts.append(f"min{args.min_actor_distinct_titles}")
        if args.max_actor_top1_concentration is not None:
            slug_parts.append(f"top1_{concentration_slug(args.max_actor_top1_concentration)}")
        if args.max_actor_top3_concentration is not None:
            slug_parts.append(f"top3_{concentration_slug(args.max_actor_top3_concentration)}")
        actor_filter_slug = "_".join(slug_parts)
    elif args.include_actors:
        actor_filter_slug = "include_actors"

    model_output_path = args.model_output or (
        "xgb_model_no_actors.pkl"
        if args.exclude_actors
        else f"xgb_model_{actor_filter_slug}.pkl"
        if actor_filter_slug
        else "xgb_model.pkl"
    )
    importance_log_path = args.importance_log or (
        "feature_importance_log_no_actors.txt"
        if args.exclude_actors
        else f"feature_importance_log_{actor_filter_slug}.txt"
        if actor_filter_slug
        else "feature_importance_log.txt"
    )
    importance_plot_path = args.importance_plot or (
        "feature_importance_plot_no_actors.png"
        if args.exclude_actors
        else f"feature_importance_plot_{actor_filter_slug}.png"
        if actor_filter_slug
        else "feature_importance_plot.png"
    )
    if args.exclude_actors:
        experiment_label = "production no-direct-actor model (--exclude-actors deprecated)"
    elif actor_eligibility_filter_supplied:
        experiment_flags = []
        if args.include_actors:
            experiment_flags.append("--include-actors")
        if args.min_actor_distinct_titles is not None:
            experiment_flags.append(f"--min-actor-distinct-titles {args.min_actor_distinct_titles}")
        if args.max_actor_top1_concentration is not None:
            experiment_flags.append(f"--max-actor-top1-concentration {args.max_actor_top1_concentration:.2f}")
        if args.max_actor_top3_concentration is not None:
            experiment_flags.append(f"--max-actor-top3-concentration {args.max_actor_top3_concentration:.2f}")
        experiment_label = "experimental actor eligibility model (" + " ".join(experiment_flags) + ")"
    elif args.include_actors:
        experiment_label = "experimental actor-inclusive model (--include-actors)"
    else:
        experiment_label = "production no-direct-actor model"

    if args.exclude_actors:
        print("⚠️  --exclude-actors is deprecated because direct actor_* features are disabled by default.")
        print("⚠️  Keeping legacy no-actor artifact names unless explicit output paths are provided.")
    if include_actor_features:
        print("🧪 EXPERIMENT: direct actor_* binary features are enabled.")
        print("🧪 Actor features may behave like TV/show proxies and can make SHAP explanations less intuitive.")
        print("🧪 Actor metadata remains in the database and production scoring is unchanged.")
    if actor_eligibility_filter_supplied:
        print("🧪 EXPERIMENT: filtering direct actor_* binary features by actor eligibility.")
        if args.min_actor_distinct_titles is not None:
            print(f"🧪 Minimum distinct shows/movies: {args.min_actor_distinct_titles}")
        if args.max_actor_top1_concentration is not None:
            print(f"🧪 Maximum top-1 show/movie concentration: {args.max_actor_top1_concentration:.2f}")
        if args.max_actor_top3_concentration is not None:
            print(f"🧪 Maximum top-3 show/movie concentration: {args.max_actor_top3_concentration:.2f}")
        print(f"🧪 Experimental model output: {model_output_path}")
    elif args.include_actors:
        print(f"🧪 Experimental model output: {model_output_path}")
    else:
        print("🎭 Direct actor features: disabled by default")
        print("🎭 Actor metadata remains available for UI, labels, prompts, and analytics.")
        print(f"📦 Production model output: {model_output_path}")

    print("📥 Loading training data...")
    df = load_training_data()

    print("🧹 Preprocessing...")
    X, y, sample_weight, feature_names = preprocess(
        df,
        # Production training excludes direct actor_* binary features. The
        # actor_tags metadata stays in training_data; it is simply not expanded
        # into model columns unless an actor experiment opts in.
        exclude_actors=not include_actor_features,
        min_actor_distinct_titles=args.min_actor_distinct_titles,
        max_actor_top1_concentration=args.max_actor_top1_concentration,
        max_actor_top3_concentration=args.max_actor_top3_concentration,
    )
    actor_feature_count = sum(1 for name in feature_names if str(name).startswith("actor_"))
    print(f"🎭 Number of actor_* features included: {actor_feature_count}")

    print(f"📊 Training on {X.shape[0]} samples with {X.shape[1]} features...")
    train_and_evaluate(
        X,
        y,
        sample_weight,
        feature_names,
        model_output_path=model_output_path,
        importance_log_path=importance_log_path,
        importance_plot_path=importance_plot_path,
        experiment_label=experiment_label,
    )  # Switch this depending on model you want
