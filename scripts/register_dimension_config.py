"""Register observed model metadata without training, scoring, or labeling."""
import argparse
from contextlib import closing
import hashlib
import json
import pickle
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from psycopg2.extras import Json
from api.db.connection import connect_db
from api.services.app_settings import get_setting_value
from api.services.dimension_config import build_metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='xgb_model.pkl')
    parser.add_argument('--inspect-only', action='store_true')
    args = parser.parse_args()
    load_dotenv()
    model_path = Path(args.model)
    # This is the same trusted local artifact used by score_model.py.
    model = pickle.loads(model_path.read_bytes())
    if model.get_xgb_params().get('objective') != 'binary:logistic':
        raise ValueError('Unsupported explanation output: expected binary:logistic')
    with closing(connect_db()) as conn, conn:
        with conn.cursor() as cur:
            sizes = []
            for table in ('media_embeddings', 'user_embeddings'):
                cur.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid = %s::regclass AND attname = 'embedding'", (table,))
                sizes.append(cur.fetchone()[0])
            metadata = build_metadata(model.get_booster().feature_names, *sizes,
                get_setting_value('ollama.embedding_model'), hashlib.sha256(model_path.read_bytes()).hexdigest())
            print(json.dumps({k: v for k, v in metadata.items() if k not in ('feature_names', 'embedding_features')}, indent=2))
            if args.inspect_only:
                return
            cur.execute('SELECT config_id FROM embedding_feature_config WHERE active FOR UPDATE')
            active = cur.fetchone()
            if active and active[0] != metadata['config_id']:
                raise ValueError('Configuration changed. Existing unversioned labels/SHAP require an explicit migration; automatic reassignment is refused.')
            cur.execute('''INSERT INTO embedding_feature_config(config_id, metadata, active)
                VALUES (%s, %s, true) ON CONFLICT(config_id) DO UPDATE SET metadata=EXCLUDED.metadata''',
                (metadata['config_id'], Json(metadata)))


if __name__ == '__main__':
    main()
