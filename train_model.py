# train_model.py

from dotenv import load_dotenv
load_dotenv()
import pandas as pd
import numpy as np
import psycopg2
from sqlalchemy import create_engine
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Configs (adapt this to your actual setup)
DB_URL = os.getenv("DATABASE_URL")

def load_training_data():
    engine = create_engine(DB_URL)
    query = "SELECT * FROM training_data"
    df = pd.read_sql(query, engine)
    return df

from sklearn.preprocessing import MultiLabelBinarizer
import ast

def preprocess(df, top_k=20):
    # Turn vector column into actual np.ndarray

    def safe_embedding_parse(x):
        if isinstance(x, str):
            return np.array(ast.literal_eval(x), dtype=np.float32)
        return np.array(x, dtype=np.float32)

    df['embedding'] = df['embedding'].apply(safe_embedding_parse)

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


    # Split tags into lists
    df['genres'] = df['genre_tags'].fillna('').apply(lambda x: x.split(',') if x else [])
    df['actors'] = df['actor_tags'].fillna('').apply(lambda x: x.split(',') if x else [])
    df['directors'] = df['director_tags'].fillna('').apply(lambda x: x.split(',') if x else [])

    # Binarize top-k tags for each category
    def binarize_tags(col_name):
        mlb = MultiLabelBinarizer()
        all_tags = df[col_name].explode().value_counts().nlargest(top_k).index
        df[col_name] = df[col_name].apply(lambda tags: [tag for tag in tags if tag in all_tags])
        return pd.DataFrame(mlb.fit_transform(df[col_name]), columns=[f"{col_name[:-1]}_{t}" for t in mlb.classes_])

    genre_features = binarize_tags('genres')
    actor_features = binarize_tags('actors')
    director_features = binarize_tags('directors')

    # Stack features: embedding + tag binarizations
    X = np.vstack(df['embedding'].values)
    X = np.hstack((X, genre_features.values, actor_features.values, director_features.values, decade_df.values))

    y = df['label'].astype(int).values

    embedding_dim = len(df['embedding'].iloc[0])
    feature_names = [f"emb_{i}" for i in range(embedding_dim)]  # ✅ Auto-detect
    feature_names += list(genre_features.columns)
    feature_names += list(actor_features.columns)
    feature_names += list(director_features.columns)
    feature_names += list(decade_df.columns)

    return X, y, feature_names

import xgboost as xgb
from xgboost import plot_importance
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt
import joblib
from sklearn.model_selection import train_test_split

from collections import Counter

def train_and_evaluate(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    class_counts = Counter(y)
    neg = class_counts[0]
    pos = class_counts[1]
    scale_pos_weight = neg / pos  # float
    print(f"📊 Using scale_pos_weight = {scale_pos_weight:.2f}")

    model = xgb.XGBClassifier(
        objective='binary:logistic',
        eval_metric='aucpr',
        scale_pos_weight=1.5,  # ✅ Fix: let XGBoost balance by class frequency
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42
    )

    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.6).astype(int)
    print(classification_report(y_test, y_pred))

    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm)
    disp.plot()
    plt.title("XGBoost Confusion Matrix")
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
    X, y, feature_names = preprocess(df)

    print(f"📊 Training on {X.shape[0]} samples with {X.shape[1]} features...")
    train_and_evaluate(X, y)  # Switch this depending on model you want

