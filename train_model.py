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


def preprocess(df, top_k=20, genre_top_k=None, actor_top_k=None, director_top_k=None):
    # Turn vector column into actual np.ndarray
    if df.empty:
        raise RuntimeError(
            "training_data has no rows with non-null embeddings. "
            "Run build_training_data.py and confirm it reports inserted rows in the same database."
        )

    missing_columns = [
        col for col in ("embedding", "label", "genre_tags", "actor_tags", "director_tags", "release_year")
        if col not in df.columns
    ]
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
    df['actors'] = df['actor_tags'].apply(normalize_tag_list)
    df['directors'] = df['director_tags'].apply(normalize_tag_list)

    # Binarize top-k tags for each category
    def binarize_tags(col_name, tag_limit):
        mlb = MultiLabelBinarizer()
        tag_counts = df[col_name].explode().dropna().value_counts()
        all_tags = tag_counts.index if tag_limit is None else tag_counts.nlargest(tag_limit).index
        df[col_name] = df[col_name].apply(lambda tags: [tag for tag in tags if tag in all_tags])
        return pd.DataFrame(mlb.fit_transform(df[col_name]), columns=[f"{col_name[:-1]}_{t}" for t in mlb.classes_])

    actor_top_k = top_k if actor_top_k is None else actor_top_k
    director_top_k = top_k if director_top_k is None else director_top_k
    genre_features = binarize_tags('genres', genre_top_k)
    actor_features = binarize_tags('actors', actor_top_k)
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
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score, recall_score
import matplotlib.pyplot as plt
import joblib
from sklearn.model_selection import train_test_split

def train_and_evaluate(X, y, sample_weight):
    from sklearn.model_selection import train_test_split

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

    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()

    if neg_count > 0 and pos_count > 0:
        class_sample_weights = np.where(
            y_train == 0,
            pos_count / neg_count,
            1.0
        )
        sample_weights = sample_weight[train_idx] * class_sample_weights
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
        class_0_recall = recall_score(y_test, y_pred_at_threshold, pos_label=0, zero_division=0)
        class_0_f1 = f1_score(y_test, y_pred_at_threshold, pos_label=0, zero_division=0)
        macro_f1 = f1_score(y_test, y_pred_at_threshold, average="macro", zero_division=0)
        threshold_metrics.append((threshold, class_0_recall, class_0_f1, macro_f1))

    print("📊 Threshold comparison:")
    print("threshold | class_0_recall | class_0_f1 | macro_f1")
    for threshold, class_0_recall, class_0_f1, macro_f1 in threshold_metrics:
        print(f"{threshold:.2f}      | {class_0_recall:.3f}          | {class_0_f1:.3f}      | {macro_f1:.3f}")

    recommended_threshold, recommended_class_0_recall, recommended_class_0_f1, recommended_macro_f1 = max(
        threshold_metrics,
        key=lambda m: (m[2], m[3])
    )
    macro_threshold, macro_class_0_recall, macro_class_0_f1, macro_macro_f1 = max(
        threshold_metrics,
        key=lambda m: (m[3], m[2])
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

    for threshold, _class_0_recall, _class_0_f1, _macro_f1 in threshold_metrics:
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

    model.get_booster().feature_names = feature_names

    # 📝 Log top N features to file
    importance_dict = model.get_booster().get_score(importance_type='gain')
    sorted_importances = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)

    with open("feature_importance_log.txt", "w") as f:
        f.write("Top XGBoost Feature Importances (by gain):\n\n")
        for feature, score in sorted_importances[:30]:  # Top 30
            f.write(f"{feature}: {score:.4f}\n")

    print("📝 Feature importance written to feature_importance_log.txt")

    # 📊 Feature importance plot
    plt.figure(figsize=(12, 6))
    plot_importance(model, max_num_features=20, importance_type='gain')
    plt.title("Top 20 Most Important Features (Gain)")
    plt.tight_layout()
    plt.savefig("feature_importance_plot.png")  # 💾 Save to file
    plt.show()
    print("🖼️ Feature importance plot saved to feature_importance_plot.png")

    joblib.dump(model, "xgb_model.pkl")
    print("✅ XGBoost model saved to xgb_model.pkl")

    # Add this after training
    for feature, score in sorted_importances:
        if feature.startswith("is_"):
            print(f"{feature}: {score:.4f}")


if __name__ == "__main__":
    print("📥 Loading training data...")
    df = load_training_data()

    print("🧹 Preprocessing...")
    X, y, sample_weight, feature_names = preprocess(df)

    print(f"📊 Training on {X.shape[0]} samples with {X.shape[1]} features...")
    train_and_evaluate(X, y, sample_weight)  # Switch this depending on model you want
