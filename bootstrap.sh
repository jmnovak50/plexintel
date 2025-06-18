#!/bin/bash
set -e

echo "🔁 Waiting for database..."
until pg_isready -d "$DATABASE_URL"; do
  sleep 1
done

echo "✅ Postgres is available!"
echo "🔍 Checking for existing schema..."

# Explicit schema check with logging
psql "$DATABASE_URL" -tAc "SELECT 1 FROM media_embeddings LIMIT 1;" || {
  echo "⚠️ Table check failed or missing. Running create.sql..."
  psql -v ON_ERROR_STOP=1 "$DATABASE_URL" -f create.sql || {
    echo "❌ Failed to apply schema."
    exit 2
  }
}

echo "✅ Schema check and setup complete!"
echo "🚀 Starting FastAPI..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8489
