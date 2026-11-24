"""Current-generation evidence for the original HIGH/LOW labeling workflow.

No embedding inference, model fitting or scoring. Full vectors are read once per
manual batch; coordinate values and their canonical physical lineage are checked.
"""
import hashlib
import re
import json

from psycopg2.extras import RealDictCursor

from api.services.dimension_config import get_active_config, feature_groups, require_semantic_media


def compatible_label_sql(label='saved', config='c'):
    return f"""({config}.metadata->>'architecture'='public-text-predictor/1.0'
        AND {config}.metadata->>'ordering'='media_text,user'
        AND {label}.config_id={config}.config_id
        AND {label}.feature_space_id={config}.metadata->>'feature_space_id'
        AND {label}.contract_hash={config}.metadata->>'contract_hash'
        AND {label}.encoder_digest={config}.metadata->>'encoder_digest')"""


def validate_context(config, state=None, control=None):
    from api.predictive.contracts import fingerprint
    from api.predictive.features import SUPERVISION_POLICY
    from api.predictive.recovery import IDENTITY_POLICY
    expected=[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)]
    contract=config.get('contract') or {}
    if (config.get('architecture')!='public-text-predictor/1.0' or feature_groups(config)!=expected
        or config.get('ordering')!='media_text,user' or config.get('embedding_model')!='embeddinggemma-2'
        or config.get('feature_space_id')!=fingerprint(contract) or config.get('contract_hash')!=fingerprint(contract)
        or config.get('encoder_digest')!=contract.get('encoder',{}).get('digest')
        or contract.get('encoder',{}).get('name')!='embeddinggemma-2:latest'
        or not re.fullmatch('[a-f0-9]{64}',str(config.get('model_sha256','')))
        or config.get('identity_policy')!=IDENTITY_POLICY or config.get('supervision_policy')!=SUPERVISION_POLICY):
        raise ValueError('Labeling requires verified Gemma 2 text/user provenance')
    names=[f"{g['name']}_{i}" for g in expected for i in range(768)]
    if config.get('feature_names',[])[:1536]!=names:raise ValueError('Invalid dimension coordinates')
    return dict(feature_groups=feature_groups(config),ordering=config['ordering'],config_id=config['config_id'],feature_space_id=config['feature_space_id'],
        contract_hash=config['contract_hash'],encoder_digest=config['encoder_digest'],
        encoder_model=contract['encoder']['name'],media_serializer=contract['media_serializer'],profile=contract['profile'],
        model_sha256=config['model_sha256'],publication_id=config.get('workload_id'),
        interpretation='Approximate coordinate interpretation; not a causal explanation')


def current_context(conn):
    from pathlib import Path
    with conn.cursor(cursor_factory=RealDictCursor) as cur:config=get_active_config(cur)
    context=validate_context(config)
    if hashlib.sha256(Path(config['model_path']).read_bytes()).hexdigest()!=context['model_sha256']:
        raise ValueError('Published model file checksum mismatch')
    return context


def checked_vectors(rows, context):
    import numpy as np
    ids, values = [], []
    for row in rows:
        record = row['record']
        raw = row['embedding']
        array = np.asarray(json.loads(raw) if isinstance(raw,str) else raw,dtype='<f4')
        if (array.shape != (768,) or not np.isfinite(array).all()
            or not record or record.get('feature_space_id') != context['feature_space_id']
            or hashlib.sha256(array.tobytes()).hexdigest() != record.get('vector_sha256')
            or record.get('encoder_digest') != context['encoder_digest']):
            raise ValueError('Physical labeling vector differs from canonical generation provenance')
        ids.append(row['id']); values.append(array)
    return ids,np.asarray(values,dtype='<f4').reshape((-1,768))


class Evidence:
    def __init__(self, conn, fetch_count=None):
        import gpt_utils as gpt
        self.fetch_count = fetch_count or gpt.DEFAULT_FETCH_ITEMS
        self.context = current_context(conn)
        self.vectors = {}
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for side,table,key,kind in [('media','media_embeddings','rating_key','media_text')]:
                cur.execute(f'''SELECT e.{key} AS id,e.embedding::text AS embedding,e.provenance AS record
                    FROM public.{table} e ORDER BY e.{key}''')
                self.vectors[side] = checked_vectors(cur.fetchall(),self.context)
            cur.execute('SELECT rating_key,media_type,plex_guid,show_rating_key FROM public.library ORDER BY rating_key')
            from api.services.dimension_sampling import sample_groups
            self.groups = sample_groups(cur.fetchall())
        self.media = gpt.get_media_metadata(self.vectors['media'][0])
        self.prompt_cache = {}

    def ranked(self, side, index, count, ascending=False):
        if side != 'media':
            raise ValueError('User/watch evidence is ineligible for semantic labeling')
        from api.services.dimension_sampling import representative_tail
        ids, values = self.vectors['media']
        return representative_tail(ids, values, index, count, self.groups, ascending)

    def variable(self, dimension):
        import numpy as np
        index = require_semantic_media(self.context, dimension)
        _,values = self.vectors['media']
        return len(values)>=2 and bool(np.ptp(values[:,index])>1e-12)

    def samples(self, dimension, count):
        import gpt_utils as gpt
        index = require_semantic_media(self.context, dimension)
        selected = []
        for ascending in (False, True):
            ids = self.ranked('media', index, count, ascending)
            frame = self.media
            if frame.empty or 'rating_key' not in frame:
                selected.append(frame.copy())
                continue
            selected.append(gpt._order_dataframe(frame[frame.rating_key.isin(ids)].copy(), 'rating_key', ids))
        return 'media', *selected

    def prompt(self, dimension):
        import gpt_utils as gpt
        require_semantic_media(self.context, dimension)
        if dimension not in self.prompt_cache:
            side, high, low = self.samples(dimension, self.fetch_count)
            bundle = gpt.build_dimension_prompt(dimension, high, low, dimension_mode=side)
            from api.services.dimension_sampling import SAMPLE_POLICY, TAIL_FRACTION
            bundle['sampling'] = dict(policy=SAMPLE_POLICY,tail_fraction=TAIL_FRACTION,
                population=len(self.vectors['media'][0]),maximum_per_canonical_or_series=1,
                unknown_identity_count=sum(not g['known'] for g in self.groups.values()),
                franchise_coverage='Unknown; no franchise identity inferred')
            bundle['prompt_text'] += ('\nSampling: rank-ordered representatives from each extreme 5% tail; '
                'at most one example per known canonical title or television series in each tail. '
                'The full coordinate population is unchanged. Unknown identities and cross-tail series '
                'overlap are not independent semantic validation.\n')
            if not self.variable(dimension):
                bundle['skipped_reason'] = 'Constant or insufficient coordinate population'
            elif len(bundle['negative_items'])<min(gpt.MIN_VALID_ITEMS,gpt.DEFAULT_TOP_NEGATIVE_ITEMS):
                bundle['skipped_reason'] = 'Insufficient valid LOW examples for contrast'
            self.prompt_cache[dimension] = bundle
        return self.prompt_cache[dimension]
