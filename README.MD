📺 PlexIntel Recommendation System

PlexIntel is a personalized media recommendation system built for Plex users. It uses watch history, content metadata, and vector embeddings to generate personalized recommendations powered by machine learning.

🔧 Tech Stack

Frontend: React + Tailwind CSS (Vite)

Backend API: FastAPI (Python)

Database: PostgreSQL with pgvector extension

Embeddings: SentenceTransformers (768-dim vectors)

Modeling: XGBoost with SHAP explainability

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

Create a bash script like run_daily_pipeline.sh:

#!/bin/bash
python fetch_tautulli_data.py --mode incremental
python build_user_embeddings.py
python build_training_data.py
python train_model.py
python score_model.py

Schedule it with cron to run daily.

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
