#!/bin/bash

cd "$HOME/projects/plexintel" || exit 1

echo "🚀 Starting daily pipeline run: $(date)"

# Activate virtual environment
source /home/jmnovak/projects/plexintel/plexenv/bin/activate

# Run each script in sequence
echo "📦 Syncing Tautulli incremental data..."
python /home/jmnovak/projects/plexintel/fetch_tautulli_data.py --mode incremental

echo "🧠 Building library embeddings..."
python /home/jmnovak/projects/plexintel/fetch_tautulli_data.py --mode embeddings

echo "🧠 Building watch embeddings..."
python /home/jmnovak/projects/plexintel/fetch_tautulli_data.py --mode watch_embeddings

echo "🧠 Building user embeddings..."
python /home/jmnovak/projects/plexintel/build_user_embeddings.py

echo "📦 Building training data..."
python /home/jmnovak/projects/plexintel/build_training_data.py

echo "🎓 Re-training model..."
python /home/jmnovak/projects/plexintel/train_model.py

echo "🔮 Scoring recommendations..."
python /home/jmnovak/projects/plexintel/score_model.py --all-users

echo "🏷  Auto-labeling SHAP dimensions with GPT..."
python /home/jmnovak/projects/plexintel/batch_label_embeddings.py --gpt_label --save_label --export_csv shap_labels_$(date +%F).csv --limit 100

echo "✅ Daily pipeline complete: $(date)"