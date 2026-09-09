"""Prospective provenance only; never changes feature values, scores or SHAP selection."""
import hashlib
from psycopg2.extras import Json
from api.services.dimension_config import build_metadata
from api.services.app_settings import get_setting_value


def persist_scoring_context(cur, model, model_bytes, media_dimensions, user_dimensions, username, predictions):
    metadata = build_metadata(model.get_booster().feature_names, media_dimensions, user_dimensions,
                              get_setting_value('ollama.embedding_model'), hashlib.sha256(model_bytes).hexdigest())
    # Register observed metadata automatically only when there is no incompatible active layout.
    cur.execute('SELECT config_id FROM embedding_feature_config WHERE active')
    active = cur.fetchone()
    if not active or active[0] == metadata['config_id']:
        cur.execute('''INSERT INTO embedding_feature_config(config_id,metadata,active) VALUES (%s,%s,true)
            ON CONFLICT(config_id) DO UPDATE SET metadata=EXCLUDED.metadata''',
            (metadata['config_id'],Json(metadata)))
    for rating_key,scored_at in predictions:
        cur.execute('''INSERT INTO shap_prediction_context(username,rating_key,config_id,model_version,scored_at)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(username,rating_key) DO UPDATE SET
            config_id=EXCLUDED.config_id,model_version=EXCLUDED.model_version,
            scored_at=EXCLUDED.scored_at,generated_at=now()''',
            (username,int(rating_key),metadata['config_id'],metadata['model_sha256'],scored_at))
