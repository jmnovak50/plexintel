#!/bin/bash
set -euo pipefail

APP="/home/jmnovak/projects/plexintel"
VENV="/home/jmnovak/projects/plexintel/plexenv"
PY="$VENV/bin/python"

cd "$APP" || exit 1

echo "🚀 Starting daily pipeline run: $(date)"

# Venv hard-lock: PATH + source; also pin PG to 17 on 5432
export PATH="$VENV/bin:$PATH"
[ -f "$VENV/bin/activate" ] && source "$VENV/bin/activate"
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"

# 🔎 Debug (temporary): confirm the exact Python & packages in use
echo "PY used: $PY"
"$PY" - <<'PY' 2>&1 | sed 's/^/[pipelog] /' >&2
import sys, importlib.metadata as md, sysconfig
print("python:", sys.executable)
print("site-packages:", sysconfig.get_paths().get("purelib"))
for n in ("pgvector","psycopg2-binary"):
    try: print(n, md.version(n))
    except Exception: print(n, "<missing>")
try:
    import pgvector, importlib
    print("Vector has __conform__:", hasattr(pgvector.Vector, "__conform__"))
except Exception as e:
    print("Vector check failed:", e)
PY

# Run each script in sequence using the venv's python explicitly
echo "📦 Syncing Tautulli incremental data..."
"$PY" "$APP/fetch_tautulli_data.py" --mode incremental

echo "🧠 Building library embeddings..."
"$PY" "$APP/fetch_tautulli_data.py" --mode embeddings

echo "🧠 Building watch embeddings..."
"$PY" "$APP/fetch_tautulli_data.py" --mode watch_embeddings

echo "🧠 Building user embeddings..."
"$PY" "$APP/build_user_embeddings.py"

echo "📦 Building training data..."
"$PY" "$APP/build_training_data.py"

echo "🎓 Re-training model..."
"$PY" "$APP/train_model.py"

echo "🔮 Scoring recommendations..."
"$PY" "$APP/score_model.py" --all-users

echo "🏷  Auto-labeling SHAP dimensions with GPT..."
"$PY" "$APP/batch_label_embeddings.py" --gpt_label --save_label --export_csv shap_labels_$(date +%F).csv --limit 100

echo "✅ Daily pipeline complete: $(date)"
