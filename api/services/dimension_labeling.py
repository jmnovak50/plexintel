"""Current-generation evidence for the original HIGH/LOW labeling workflow.

No embedding inference, model fitting or scoring. Full vectors are read once per
manual batch; coordinate values and their canonical physical lineage are checked.
"""
import hashlib
import re
import json

from psycopg2.extras import RealDictCursor

from api.services.dimension_config import get_active_config, feature_groups


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
    return dict(config_id=config['config_id'],feature_space_id=config['feature_space_id'],
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
            for side,table,key,kind in [('media','media_embeddings','rating_key','media_text'),('user','user_embeddings','username','user')]:
                cur.execute(f'''SELECT e.{key} AS id,e.embedding::text AS embedding,e.provenance AS record
                    FROM public.{table} e ORDER BY e.{key}''')
                self.vectors[side] = checked_vectors(cur.fetchall(),self.context)
        self.media = gpt.get_media_metadata(self.vectors['media'][0])
        self.user = gpt.get_user_positive_training_examples(self.vectors['user'][0])
        # Keep the user grouping required by the original prompt, without sending
        # account names to a cloud interpreter. The mapping is batch-local only.
        aliases = {name:f'Viewer {i+1}' for i,name in enumerate(self.vectors['user'][0])}
        self.aliases = aliases
        self.prompt_cache = {}
        self.prepare_user_cache()

    def prepare_user_cache(self):
        import gpt_utils as gpt
        self.user_prepared = gpt.prepare_dimension_items(self.user,dimension_mode='user')
        self.user_candidates = {}
        for username,group in self.user_prepared['valid_items'].groupby('username',sort=False) if not self.user_prepared['valid_items'].empty else []:
            # Selection is round-robin and capped per user. Cache exactly those
            # candidates, while retaining full-population quality gate counts.
            self.user_candidates[username] = gpt._select_prompt_rows(group,gpt.MAX_ITEMS_PER_USER_IN_PROMPT,'user')

    def ranked(self, side, index, count, ascending=False):
        import numpy as np
        ids,values = self.vectors[side]
        order = np.argsort(values[:,index] if ascending else -values[:,index],kind='stable')
        # Disjoint tails even for the small population of user vectors.
        count = min(count,len(ids)//2)
        if ascending:
            high = set(np.argsort(-values[:,index],kind='stable')[:count])
            order = [i for i in order if i not in high]
        return [ids[i] for i in order[:count]]

    def variable(self, dimension):
        import numpy as np
        side,index = ('media',dimension) if dimension<768 else ('user',dimension-768)
        _,values = self.vectors[side]
        return len(values)>=2 and bool(np.ptp(values[:,index])>1e-12)

    def samples(self, dimension, count):
        import gpt_utils as gpt
        side,index = ('media',dimension) if dimension<768 else ('user',dimension-768)
        frame,key = (self.media,'rating_key') if side=='media' else (self.user,'username')
        selected = []
        for ascending in (False,True):
            ids = self.ranked(side,index,count,ascending)
            if frame.empty or key not in frame:
                selected.append(frame.copy())
                continue
            result = gpt._order_dataframe(frame[frame[key].isin(ids)].copy(),key,ids,
                                         secondary_desc_column='engagement_ratio' if side=='user' else None)
            if side=='user':
                result['username'] = result['username'].map(self.aliases)
            selected.append(result)
        return side,*selected

    def prompt(self, dimension):
        import gpt_utils as gpt
        if dimension not in self.prompt_cache:
            if dimension<768:
                side,high,low = self.samples(dimension,self.fetch_count)
                bundle = gpt.build_dimension_prompt(dimension,high,low,dimension_mode=side)
            else:
                high = self.user_bundle(self.ranked('user',dimension-768,self.fetch_count))
                low = self.user_bundle(self.ranked('user',dimension-768,self.fetch_count,True))
                bundle = gpt.build_dimension_prompt(dimension,None,dimension_mode='user',
                    prepared_positive=high,prepared_negative=low)
            if not self.variable(dimension):
                bundle['skipped_reason'] = 'Constant or insufficient coordinate population'
            elif len(bundle['negative_items'])<min(gpt.MIN_VALID_ITEMS,gpt.DEFAULT_TOP_NEGATIVE_ITEMS):
                bundle['skipped_reason'] = 'Insufficient valid LOW examples for contrast'
            self.prompt_cache[dimension] = bundle
        return self.prompt_cache[dimension]

    def user_bundle(self, usernames):
        import pandas as pd
        pieces = [self.user_candidates[u] for u in usernames if u in self.user_candidates]
        valid = pd.concat(pieces,ignore_index=True) if pieces else self.user_prepared['valid_items'].iloc[:0].copy()
        if not valid.empty:
            valid['username'] = valid['username'].map(self.aliases)
        result = {'valid_items':valid}
        for key in ('all_items','flagged_items'):
            frame = self.user_prepared[key]
            result[key] = frame[frame['username'].isin(usernames)] if not frame.empty else frame
        frame = self.user_prepared['valid_items']
        result['valid_count'] = len(frame[frame['username'].isin(usernames)]) if not frame.empty else 0
        return result
