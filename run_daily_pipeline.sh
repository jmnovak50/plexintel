#!/bin/bash
set -euo pipefail

APP="/home/jmnovak/projects/plexintel"
VENV="/home/jmnovak/projects/plexintel/plexenv"
PY="$VENV/bin/python"
REFRESH_EXISTING_LABELS="${PIPELINE_REFRESH_EXISTING_LABELS:-false}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --refresh-existing|--refresh_existing)
      REFRESH_EXISTING_LABELS=true
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--refresh-existing]" >&2
      exit 2
      ;;
  esac
  shift
done

cd "$APP" || exit 1

echo "🚀 Starting daily pipeline run: $(date)"
echo "⚠️  Use either this cron script or the Admin in-app scheduler, not both."

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

echo "🏷  Auto-labeling SHAP dimensions in coverage mode..."
LABEL_ARGS=(
  "$PY"
  "$APP/batch_label_embeddings.py"
  --selection_mode coverage
  --limit 25
  --dim_type all
  --label
  --save_label
  --export_csv "shap_labels_$(date +%F).csv"
)
case "$REFRESH_EXISTING_LABELS" in
  true|TRUE|True|1|yes|YES|Yes|on|ON|On)
    echo "⚠️  Adding --refresh_existing to the coverage label stage."
    LABEL_ARGS+=(--refresh_existing)
    ;;
esac
"${LABEL_ARGS[@]}"

echo "✅ Daily pipeline complete: $(date)"
