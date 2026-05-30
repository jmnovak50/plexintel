📺 PlexIntel Recommendation System

PlexIntel is a personalized media recommendation system built for Plex users. It uses watch history, content metadata, and vector embeddings to generate personalized recommendations powered by machine learning.

🔧 Tech Stack

Frontend: React + Tailwind CSS (Vite)

Backend API: FastAPI (Python)

Database: PostgreSQL with pgvector extension

Embeddings: SentenceTransformers (768-dim vectors)

Modeling: XGBoost with SHAP explainability

Production training excludes direct `actor_*` binary model features by default because actor rows can behave like TV/show proxy signals. Actor metadata is still retained for UI, labels, prompts, and analytics. Use `python train_model.py --include-actors` only for actor-feature experiments.

Auth: Plex OAuth PIN-based login

Hosting: Raspberry Pi (or any Linux system)

🚀 Features

🎯 Personalized recommendations using user/media embeddings

📊 Machine learning scoring with XGBoost

📈 Explainability via SHAP

📺 Filter by media type, score, themes, and more

🔄 Nightly update pipeline (media sync, embeddings, scoring)

🧠 Embedding dimension explorer

🔐 Plex login support

🛠️ Setup

1. Clone the repo

git clone https://github.com/jmnovak50/plexintel.git
cd plexintel

2. Install frontend dependencies

cd frontend
npm install

3. Build frontend

npm run build

4. Set up environment variables

Create a bootstrap-only `.env` file in the project root:

```
DATABASE_URL=postgresql://username:password@localhost:5432/plexintel
SESSION_SECRET=replace-me
```

Optional: if you are migrating from an older `.env`-driven install, you can temporarily keep legacy config vars in `.env`. PlexIntel now auto-imports missing settings into the database on startup, and after that you should manage them from the admin settings workspace at `/admin/settings`.

An example bootstrap file is included at `.env.bootstrap.example`.

5. Start the backend

uvicorn api.main:app --host 0.0.0.0 --port 8489

6. Configure integrations in admin

Start the app, sign in as an admin user, then open `/admin/settings` to configure:

- Tautulli connectivity
- Plex client metadata
- Public API access
- Ollama / OpenAI / labeling defaults
- Training and scoring thresholds

⚙️ Nightly Pipeline

The repo includes `run_daily_pipeline.sh`, which runs the full sequence (Tautulli sync, embeddings, training data, train, score, batch labeling). You can either:

**Option A — In-app scheduler (recommended when the API is always running)**
In **Admin → Settings → Nightly pipeline**, enable the scheduler and set frequency, day (for weekly), local run time, and timezone. The FastAPI process runs a background poll (default every 60s; override with `PIPELINE_SCHEDULER_INTERVAL_SECONDS`). Disable with `PIPELINE_SCHEDULER_ENABLED=false`. When this is enabled, **do not** also cron the same shell script, or you may double-run the pipeline. Monitor runs under **Admin → Pipeline runs** (`/admin/pipeline`).

The scheduled pipeline scores all users with `score_model.py --all-users`. SHAP targeting is media-aware by default: it separately targets the configured top movie recommendations, displayed TV show recommendations, and a modest overall catch-all instead of relying on one global rank list. The legacy global SHAP mode remains available in Admin settings, but the recommended default is per-media-type targeting so movie explanations are not crowded out by episode-heavy rankings.

Daily scheduled labeling is coverage-oriented by default. The batch label stage runs `batch_label_embeddings.py --selection_mode coverage --limit 25 --dim_type all --label --save_label`, which labels only dimensions that can unlock missing semantic themes for currently SHAP-enabled recommendation cards. `importance`, `hybrid`, and `refresh_existing_labels` are available in Admin settings for manual quality-review or broader label expansion runs; they should not be the daily default because they can spend LLM work on dimensions that do not unlock current recommendation cards, or revisit labels that are already saved.

In-app pipeline runs also append the complete stdout/stderr for every stage to `logs/pipeline.log` by default. Override the destination with `PIPELINE_LOG_PATH`; in Docker, map the host log directory to `/app/logs` and set `PIPELINE_LOG_PATH=/app/logs/pipeline.log`.

Admins can cancel an active in-app run from **Admin → Pipeline runs**. Cancellation is cooperative: the API marks the run for cancellation, the active stage receives `SIGTERM`, and it is force-killed if it does not exit within the grace period. Cancelled scheduled runs count as terminal for that schedule slot, so the scheduler will not immediately retry the same nightly run. This control does not apply to host cron jobs that launch `run_daily_pipeline.sh` outside the API process.

**Option B — Cron**
Schedule `run_daily_pipeline.sh` (or the individual Python steps) with cron on the host. If you use cron, leave the in-app pipeline scheduler **disabled** in admin settings.

The cron script uses the same coverage-oriented label defaults. To explicitly pass `--refresh_existing` for a manual quality-review run, use `run_daily_pipeline.sh --refresh-existing` or set `PIPELINE_REFRESH_EXISTING_LABELS=true`. Keep it off for normal daily runs.

📦 Prerequisites

Python 3.11+

PostgreSQL 15+ with vector chord

Node.js 18+

Plex Media Server

Tautulli installed anf API access

📂 Project Structure

plexintel/
├── api/                  # FastAPI routes
├── frontend/             # React + Tailwind app
├── fetch_tautulli_data.py
├── build_user_embeddings.py
├── build_training_data.py
├── train_model.py
├── score_model.py
├── explore_embedding_dimension.py
├── .env.bootstrap.example
└── run_daily_pipeline.sh

🧪 Testing

Use Vite dev server during development:

cd frontend
npm run dev

🧠 Credits

Built by Jason Novak to bring smarter discovery to Plex libraries. 🧩
