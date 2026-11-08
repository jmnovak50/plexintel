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
    if config.get('feature_groups'):
        for group in feature_groups(config):
            if group['start']<=dimension<group['start']+group['width']:
                return dict(dimension=dimension,feature_name=f"{group['name']}_{dimension-group['start']}",
                    side=group['name'],local_index=dimension-group['start'])
        raise ValueError('Unknown embedding dimension')
    media, user = config['media_dimensions'], config['user_dimensions']
    if not 0 <= dimension < media + user:
        raise ValueError('Unknown embedding dimension')
    return dict(dimension=dimension, feature_name=f'emb_{dimension}',
                side='media' if dimension < media else 'user',
                local_index=dimension if dimension < media else dimension - media)


def feature_groups(config):
    groups=config.get('feature_groups')
    if not groups:
        return [dict(name='media',start=0,width=config['media_dimensions']),
                dict(name='user',start=config['media_dimensions'],width=config['user_dimensions'])]
    expected=[dict(name='media_text',start=0,width=768),dict(name='media_poster',start=768,width=768),dict(name='user',start=1536,width=768)]
    if config.get('ordering')=='media_text,user':
        expected=[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)]
    if groups!=expected or config.get('ordering') not in ('media_text,media_poster,user','media_text,user'):
        raise ValueError('Unsupported modality feature inventory')
    return groups


def build_independent_metadata(feature_names,model_sha256,*,generation_id,contract_hash,encoder_digest,serializer):
    groups=[dict(name='media_text',start=0,width=768),dict(name='media_poster',start=768,width=768),dict(name='user',start=1536,width=768)]
    expected=[f"{g['name']}_{i}" for g in groups for i in range(g['width'])]
    if list(feature_names[:2304])!=expected:raise ValueError('Independent feature layout must retain all native text/poster/user dimensions')
    config_id=hashlib.sha256(json.dumps(dict(contract_hash=contract_hash,ordering='media_text,media_poster,user'),sort_keys=True).encode()).hexdigest()[:24]
    return dict(config_id=config_id,generation_id=generation_id,contract_hash=contract_hash,
        media_dimensions=1536,user_dimensions=768,embedding_dimensions=2304,ordering='media_text,media_poster,user',
        embedding_model='embeddinggemma-2',encoder_digest=encoder_digest,serializer=serializer,
        model_sha256=model_sha256,feature_names=list(feature_names),embedding_features=expected,feature_groups=groups,
        user_profile='semantic-text-mean; no independently learned visual preference',visual_user_profile=None,
        missing_poster='null vector; NaN XGBoost slots and poster_missing=1',shap_output='raw margin (log-odds)')


def build_text_metadata(feature_names,model_sha256,*,generation_id,contract_hash,encoder_digest,serializer):
    groups=[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)]
    expected=[f"{g['name']}_{i}" for g in groups for i in range(g['width'])]
    if list(feature_names[:1536])!=expected or any(n.startswith('media_poster_') or n=='poster_missing' for n in feature_names):
        raise ValueError('Text production must retain all native text/user dimensions and no poster features')
    config_id=hashlib.sha256(json.dumps(dict(contract_hash=contract_hash,ordering='media_text,user'),sort_keys=True).encode()).hexdigest()[:24]
    return dict(config_id=config_id,generation_id=generation_id,contract_hash=contract_hash,
        media_dimensions=768,user_dimensions=768,embedding_dimensions=1536,ordering='media_text,user',
        embedding_model='embeddinggemma-2',encoder_digest=encoder_digest,serializer=serializer,
        model_sha256=model_sha256,feature_names=list(feature_names),embedding_features=expected,feature_groups=groups,
        user_profile='semantic-text-mean; no independently learned visual preference',visual_user_profile=None,
        poster_inference='disabled/1.0',shap_output='raw margin (log-odds)')
