"""Verified, finite embedding inventory. No ML dependencies in the web process."""
import hashlib
import json


def build_metadata(feature_names, media_dimensions, user_dimensions, embedding_model, model_sha256):
    size = media_dimensions + user_dimensions
    if media_dimensions <= 0 or user_dimensions <= 0:
        raise ValueError('Embedding widths must be positive')
    expected = [f'emb_{i}' for i in range(size)]
    if list(feature_names[:size]) != expected or any(str(n).startswith('emb_') for n in feature_names[size:]):
        raise ValueError('Model feature names do not match media-then-user embedding construction')
    identity = dict(media_dimensions=media_dimensions, user_dimensions=user_dimensions,
                    embedding_model=embedding_model, embedding_features=expected, ordering='media,user')
    config_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    return dict(identity, config_id=config_id, model_sha256=model_sha256,
                feature_names=list(feature_names), shap_output='raw margin (log-odds)')


def get_active_config(cur):
    cur.execute('SELECT metadata FROM public.embedding_feature_config WHERE active')
    row = cur.fetchone()
    if not row:
        raise ValueError('No verified feature configuration. Run scripts/register_dimension_config.py on the model host; see docs/dimension-explorer.md.')
    return row['metadata'] if isinstance(row, dict) else row[0]


def identity(config, dimension):
    media, user = config['media_dimensions'], config['user_dimensions']
    if not 0 <= dimension < media + user:
        raise ValueError('Unknown embedding dimension')
    return dict(dimension=dimension, feature_name=f'emb_{dimension}',
                side='media' if dimension < media else 'user',
                local_index=dimension if dimension < media else dimension - media)
