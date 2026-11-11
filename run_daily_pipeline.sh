#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${PLEXINTEL_PYTHON:-$ROOT/plexenv/bin/python}"
LOCK_PATH="${PIPELINE_LOCK_PATH:-$ROOT/logs/daily-pipeline.lock}"
mkdir -p -- "$(dirname -- "$LOCK_PATH")"
exec 9>"$LOCK_PATH"
flock -n 9 || { echo "Pipeline already running"; exit 75; }
# The child also holds the database advisory writer lock. No schema/activation lookup.
exec "$PYTHON" scripts/predictive_pipeline.py daily --execute "$@"
