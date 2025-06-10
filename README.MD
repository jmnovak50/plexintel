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

Create a .env file in the root of the backend:

DATABASE_URL=postgresql://username:password@localhost:5432/plexintel
PLEX_CLIENT_ID=your_plex_client_id
PLEX_PRODUCT=plexintel
PLEX_DEVICE=plexintel-client
PLEX_REDIRECT_URI=http://localhost:8489/auth/callback
OPENAI_API_KEY=sk-...

5. Start the backend

uvicorn api.main:app --host 0.0.0.0 --port 8489

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

Tautulli API access

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
├── .env                  # Environment config
└── run_daily_pipeline.sh

🧪 Testing

Use Vite dev server during development:

cd frontend
npm run dev

🧠 Credits

Built by Jason Novak to bring smarter discovery to Plex libraries. 🧩

