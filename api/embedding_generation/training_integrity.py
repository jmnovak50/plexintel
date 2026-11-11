"""Receipts for materialized training rows, separate from the unchanged fit dataset hash."""
import hashlib
import json
from uuid import uuid4
import numpy as np
from pgvector import Vector
from psycopg2 import sql
from psycopg2.extras import Json,RealDictCursor

from .contracts import ContractError,canonical,fingerprint,text_only,utc

ARTIFACT='training-materialization.json'
FORMAT='stored-training-rows-sha256/1.0'


def serialized_row(row):
    # Keep the original canonical-rows-jsonl/1.0 hash, including float64 means.
    return canonical({**{k:v for k,v in row.items() if k!='embedding'},
        'embedding':[float(v) if np.isfinite(v) else None for v in row['embedding']]}).encode()+b'\n'


def stored_vector(value,width):
    if hasattr(value,'to_numpy'):value=value.to_numpy()
    values=np.asarray(value,dtype=np.float32)
    if values.shape!=(width,) or not np.isfinite(values).all():
        raise ContractError('Invalid materialized training vector')
    return values.tolist()


def record_for_row(gid,row,text_mode):
    fields={k:v for k,v in row.items() if k not in ('embedding','dependencies')}
    if text_mode:fields.pop('poster_missing',None)
    record=dict(generation_id=gid,owner=row['owner'],media_key=row['media_key'],
        prediction_at=row['prediction_at'],label_available_at=row['label_available_at'],
        label=row['label'],features=fields,dependencies=row['dependencies'])
    if text_mode:record['embedding']=stored_vector(row['embedding'],1536)
    else:
        record.update(media_text=stored_vector(row['embedding'][:768],768),
            media_poster=None if row['poster_missing'] else stored_vector(row['embedding'][768:1536],768),
            user_embedding=stored_vector(row['embedding'][1536:],768))
    return record


def row_digest(record,text_mode):
    value=dict(record)
    value['prediction_at']=utc(value['prediction_at']).isoformat()
    value['label_available_at']=utc(value['label_available_at']).isoformat()
    for name,width in ([('embedding',1536)] if text_mode else [('media_text',768),('media_poster',768),('user_embedding',768)]):
        if value[name] is not None:value[name]=stored_vector(value[name],width)
    return fingerprint(value)


def manifest(generation,dataset,hashes,dataset_sha):
    return dict(format=FORMAT,generation_id=generation['generation_id'],contract_hash=generation['contract_hash'],
        dataset_hash=dataset['dataset_hash'],dataset_artifact_sha256=dataset_sha,rows=len(hashes),
        identity_policy=dataset.get('identity_policy'),supervision_policy=dataset.get('supervision_policy'),
        materialization_hash=hashlib.sha256('\n'.join(sorted(hashes)).encode()).hexdigest())


def insert_row(store,gid,row,text_mode):
    record=record_for_row(gid,row,text_mode)
    vector_names=['embedding'] if text_mode else ['media_text','media_poster','user_embedding']
    values=[gid,row['owner'],row['media_key'],row['prediction_at'],row['label_available_at'],row['label']]
    values.extend(Vector(record[k]) if record[k] is not None else None for k in vector_names)
    values.extend([Json(record['features']),Json(record['dependencies'])])
    table='text_training_rows' if text_mode else 'modality_training_rows'
    store.query(sql.SQL('INSERT INTO {} VALUES({})').format(store.table(table),sql.SQL(',').join([sql.Placeholder()]*len(values))),tuple(values))
    return row_digest(record,text_mode)


def verify_materialization(store,gid,bundle):
    """Read-only, bounded verification; never trusts a receipt without hashing actual rows."""
    from .features import SUPERVISION_POLICY,available
    from .recovery import CanonicalTitles,IDENTITY_POLICY
    g=store.generation(gid);text_mode=text_only(g['contract'])
    data=store.artifact(gid,'dataset.json');dataset=json.loads(bytes(data['data']))
    saved=store.artifact(gid,ARTIFACT);expected=json.loads(bytes(saved['data']))
    if dataset['dataset_hash']!=bundle['dataset_hash'] or not dataset['rows']:
        raise ContractError('Training materialization has no matching nonempty fit dataset')
    identity=None
    if text_mode:
        media=store.query(sql.SQL("SELECT item_key,source FROM {} WHERE generation_id=%s AND kind='media_text'").format(store.table('items')),(gid,),many=True)
        identity=CanonicalTitles({r['item_key']:dict(source=r['source']) for r in media})
    events={str(e['watch_id']):e for e in g['snapshot']['events']}
    hashes=[];seen=set()
    table='text_training_rows' if text_mode else 'modality_training_rows'
    # A regular psycopg cursor buffers the entire result in libpq even when
    # fetchmany is used. A server cursor keeps dependency-heavy rows bounded.
    with store.conn.cursor(name='training_integrity_'+uuid4().hex,cursor_factory=RealDictCursor) as cur:
        cur.itersize=64
        cur.execute(sql.SQL('SELECT * FROM {} WHERE generation_id=%s').format(store.table(table)),(gid,))
        while True:
            batch=cur.fetchmany(64)
            if not batch:break
            for record in batch:
                fields=record['features'];deps=record['dependencies']
                if (fields.get('owner')!=record['owner'] or fields.get('media_key')!=record['media_key']
                    or fields.get('label')!=record['label']
                    or utc(fields['prediction_at'])!=utc(record['prediction_at'])
                    or utc(fields['label_available_at'])!=utc(record['label_available_at'])
                    or deps.get('generation_id')!=gid or deps.get('contract_hash')!=g['contract_hash']):
                    raise ContractError('Training materialization columns/provenance disagree')
                target=record['media_key'];key=(record['owner'],target)
                if identity:
                    key=(record['owner'],identity.identity(target));aliases=identity.aliases(target)
                    if (fields.get('canonical_identity')!=key[1]
                        or fields.get('identity_policy')!=IDENTITY_POLICY or fields.get('supervision_policy')!=SUPERVISION_POLICY
                        or deps.get('identity_policy')!=IDENTITY_POLICY or deps.get('supervision_policy')!=SUPERVISION_POLICY
                        or set(deps.get('target_aliases',[]))!=aliases or aliases.intersection(deps['profile_keys'])):
                        raise ContractError('Canonical target isolation/provenance mismatch')
                    cutoff=utc(record['prediction_at'])
                    for ident,digest,when in deps['watch_events']:
                        event=events[str(ident)]
                        if (event['username']!=record['owner'] or str(event['rating_key']) in aliases
                            or utc(when)>=cutoff or utc(event['watched_at'])>=cutoff
                            or available(event) is None or available(event)>=cutoff):
                            raise ContractError('Target/future watch in training materialization')
                if key in seen:raise ContractError('Duplicate canonical training outcome')
                seen.add(key);hashes.append(row_digest(record,text_mode))
    actual=manifest(g,dataset,hashes,data['sha256'])
    if len(hashes)!=dataset['rows'] or actual!=expected:
        raise ContractError('Training materialization count/hash mismatch')
    return dict(actual,receipt_sha256=saved['sha256'])


def restore_text_rows(store,gid,*,progress=lambda value:None):
    """Rebuild only private rows. Never changes saved model/dataset receipts or refits."""
    from .model import populations,load_bundle
    from .features import training_plan,planned_text_rows
    from .recovery import CanonicalTitles
    g,media,watches,_=populations(store,gid)
    if not text_only(g['contract']):raise ContractError('Resume reconstruction requires text production')
    # Never batch-commit partial restoration into permanent staging or live tables.
    if 'pg_temp' not in store.table('text_training_rows').as_string(store.conn):
        raise ContractError('Resume reconstruction requires connection-private training rows')
    bundle,_=load_bundle(store,gid);data=store.artifact(gid,'dataset.json');dataset=json.loads(bytes(data['data']))
    identity=CanonicalTitles(media);plan,skips=training_plan(g,media,identity,progress=progress)
    store.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(store.table('text_training_rows')),(gid,))
    hasher=hashlib.sha256();hashes=[]
    for index,row in enumerate(planned_text_rows(g,media,watches,plan,identity,progress=progress),1):
        hasher.update(serialized_row(row));hashes.append(insert_row(store,gid,row,True))
        if index%128==0:
            if hasattr(store,'observe_resources'):store.observe_resources('training-restore',index)
            store.conn.commit()
    if hasher.hexdigest()!=dataset['dataset_hash'] or len(hashes)!=dataset['rows'] or skips!=dataset['skips']:
        store.conn.rollback()
        raise ContractError('Resumed dataset differs from saved fit; model and dataset receipts preserved')
    receipt=manifest(g,dataset,hashes,data['sha256'])
    store.artifact(gid,ARTIFACT,canonical(receipt).encode(),dict(contract_hash=g['contract_hash']))
    store.conn.commit()
    return verify_materialization(store,gid,bundle)
