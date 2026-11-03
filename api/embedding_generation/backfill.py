"""Serial, resumable generation workers. No mutation of active/legacy data."""
from dataclasses import asdict
from datetime import datetime, timezone
import math
import hashlib
import time
from functools import wraps

import numpy as np
from psycopg2 import sql
from psycopg2.extras import Json

from .contracts import (ContractError, Encoder, contract, fingerprint, metadata, media_text,
                        watch_text, vector, utc, embedding_input_hash,MEDIA_VERSION,WATCH_VERSION,IMAGE_VERSION,PROFILE_VERSION,POSTER_HIERARCHY)
from .io import Ollama, Poster, SourceError
from .store import Store


def safe_error(exc):
    return type(exc).__name__+(':'+str(exc)[:240] if isinstance(exc,(ContractError,SourceError)) else '')


def media_payload(plex,source):
    raw=plex.metadata(source['rating_key'])
    show=None;season=None
    if raw['type'] in ('season','episode'):
        key=raw.get('grandparentRatingKey') if raw['type']=='episode' else raw.get('parentRatingKey')
        if not key:raise ContractError('TV child lacks a parent-show key')
        show=plex.metadata(key)
        if raw['type']=='episode' and raw.get('parentRatingKey'):season=plex.metadata(raw['parentRatingKey'])
    return metadata(raw,show,season),raw


def generation_writer(function):
    @wraps(function)
    def run(store,gid,*args,**kwargs):
        with store.writer(gid):return function(store,gid,*args,**kwargs)
    return run


@generation_writer
def prepare_metadata(store,gid,plex,*,refresh=False,progress=lambda x:None):
    """Independent metadata checkpoints, with no poster retrieval or inference."""
    generation=store.mutable(gid)
    if generation['contract']['media_serializer']!=MEDIA_VERSION or generation['contract']['poster_hierarchy']!=POSTER_HIERARCHY:
        raise ContractError('Generation metadata/hierarchy version differs from this implementation')
    if refresh and hasattr(plex,'metadata_cache'):plex.metadata_cache.clear()
    revisions=plex.revisions()
    for row in store.items(gid,'media_text'):
        prepared=store.preparation(gid,row['item_key'],'metadata')
        if prepared and prepared['status']=='succeeded' and not refresh:continue
        started=time.perf_counter()
        try:
            relevant={row['item_key']}
            if row['source'].get('show_rating_key'):relevant.add(str(row['source']['show_rating_key']))
            if row['source'].get('parent_rating_key'):relevant.add(str(row['source']['parent_rating_key']))
            revision=fingerprint({k:revisions[k] for k in sorted(relevant)}) if relevant.issubset(revisions) else None
            prior=row
            if generation['parent_id']:
                prior=store.query(sql.SQL("SELECT * FROM {} WHERE generation_id=%s AND kind='media_text' AND item_key=%s")
                    .format(store.table('items')),(generation['parent_id'],row['item_key'])) or row
            parent_contract=(store.generation(generation['parent_id'],include_snapshot=False)['contract'] if generation['parent_id'] else generation['contract'])
            source_compatible=all(parent_contract.get(k)==generation['contract'].get(k) for k in ('media_serializer','poster_hierarchy'))
            reused=bool(source_compatible and revision and prior['source'].get('_plex_revision')==revision and 'metadata' in prior['source'])
            if reused:
                source={**row['source'],'metadata':prior['source']['metadata'],
                    'poster_reference':prior['source']['poster_reference'],'_plex_revision':revision}
                value=source['metadata']
            else:
                value,raw=media_payload(plex,row['source'])
                source={**row['source'],'metadata':value,'_plex_revision':revision}
                source['poster_reference']={k:raw.get(k) for k in ('type','ratingKey','thumb','parentRatingKey','grandparentRatingKey')}
                sources=[raw]
                if raw['type']=='season':sources=[raw,plex.metadata(raw['parentRatingKey'])]
                if raw['type']=='episode':sources=[plex.metadata(raw['grandparentRatingKey']),plex.metadata(raw['parentRatingKey']),raw]
                source['poster_reference']['_poster_sources']=[{k:r.get(k) for k in ('type','ratingKey','thumb')} for r in sources]
            store.upsert_source(gid,'media_text',row['item_key'],source,semantic_hash=fingerprint(value))
            if row['source'].get('poster_reference')!=source['poster_reference']:
                # Re-prepare changed references, retaining the old image vector
                # until actual prepared pixels establish whether it changed.
                store.query(sql.SQL("DELETE FROM {} WHERE generation_id=%s AND item_key=%s AND stage='poster'")
                    .format(store.table('preparations')),(gid,row['item_key']))
            store.preparation(gid,row['item_key'],'metadata',status='succeeded',content_hash=fingerprint(value),
                provenance=dict(source='Plex',fields_present=sorted(k for k,v in value.items() if v)),
                timing=dict(metadata_seconds=time.perf_counter()-started,revision_cache_hit=reused))
            store.conn.commit()
        except Exception as exc:
            store.conn.rollback()
            store.preparation(gid,row['item_key'],'metadata',status='failed',provenance=dict(error=safe_error(exc)),
                timing=dict(metadata_seconds=time.perf_counter()-started))
            store.conn.commit()
        prep=store.preparation(gid,row['item_key'],'metadata')
        progress({'stage':'metadata','item_key':row['item_key'],'error':prep['provenance'].get('error'),'reused':bool(prep['timing'].get('revision_cache_hit'))})


def prepare_posters(store,gid,plex,*,refresh=False,force=False,only_keys=None,progress=lambda x:None):
    """Independent retrieval checkpoint; metadata text vectors are untouched."""
    generation=store.mutable(gid)
    if generation['contract']['image']!=IMAGE_VERSION:raise ContractError('Image preparation version differs from this implementation')
    checked=set()
    with store.writer(gid):
        for row in store.items(gid,'media_text'):
            key=row['item_key'];prepared=store.preparation(gid,key,'poster')
            if only_keys is not None and key not in {str(k) for k in only_keys}:continue
            if prepared and prepared['status']=='succeeded' and not refresh and not force:continue
            meta=store.preparation(gid,key,'metadata')
            if not meta or meta['status']!='succeeded':continue
            error=None
            try:
                poster=plex.poster(row['source']['poster_reference'],store.cache,store.cache,force=force,force_checked=checked)
                content_hash=fingerprint({k:poster.provenance[k] for k in ('state','content_sha256','preprocessing')})
                old=store.query(sql.SQL("SELECT poster FROM {} WHERE generation_id=%s AND kind='media_poster' AND item_key=%s")
                    .format(store.table('items')),(gid,key))['poster']
                if old and fingerprint({k:old[k] for k in ('state','content_sha256','preprocessing')})!=content_hash:
                    store.invalidate_children(gid,'media_poster',key)
                    store.query(sql.SQL("UPDATE {} SET status='pending',embedding=NULL WHERE generation_id=%s AND kind='media_poster' AND item_key=%s")
                        .format(store.table('items')),(gid,key))
                store.query(sql.SQL("UPDATE {} SET poster=%s WHERE generation_id=%s AND kind='media_poster' AND item_key=%s")
                    .format(store.table('items')),(Json(poster.provenance),gid,key))
                store.preparation(gid,key,'poster',status='succeeded',content_hash=content_hash,
                    provenance=poster.provenance,timing=poster.timing)
                store.conn.commit()
            except Exception as exc:
                error=safe_error(exc);store.conn.rollback()
                store.preparation(gid,key,'poster',status='failed',provenance=dict(error=error));store.conn.commit()
            progress(dict(stage='poster-preparation',item_key=key,error=error,
                reused=not error and bool((poster.timing or {}).get('cache_hit'))))


def run_media_text(store,gid,ollama,*,batch_size=16,progress=lambda x:None):
    return _run_modality(store,gid,'media_text',None,ollama,batch_size=batch_size,progress=progress)


def run_media_poster(store,gid,cache,ollama,*,batch_size=16,progress=lambda x:None):
    return _run_modality(store,gid,'media_poster',cache,ollama,batch_size=batch_size,progress=progress)


def _run_modality(store,gid,kind,cache,ollama,*,batch_size,progress):
    generation=store.mutable(gid)
    if not 1<=batch_size<=128:raise ContractError('Batch bound must be 1..128')
    if (kind=='media_text' and generation['contract']['media_serializer']!=MEDIA_VERSION
        or kind=='media_poster' and generation['contract']['image']!=IMAGE_VERSION):
        raise ContractError('Modality serializer/preprocessing version differs from this implementation')
    if asdict(ollama.encoder)!=generation['contract']['encoder']:raise ContractError('Worker encoder differs from pinned generation')
    with store.writer('ollama:'+ollama.encoder.digest),store.writer(gid):
        for row in (r for batch in store.batches(gid,kind,size=batch_size,pending=True) for r in batch):
            key=row['item_key'];error=None;attempted=False;timing=None;request_start=None;inherited=None
            try:
                stage='metadata' if kind=='media_text' else 'poster'
                prep=store.preparation(gid,key,stage)
                if not prep or prep['status']!='succeeded':raise ContractError('Required modality preparation is incomplete')
                if kind=='media_text':
                    value=row['source']['metadata'];digest=embedding_input_hash(generation['contract'],kind,metadata=value)
                else:
                    if row['poster']['preprocessing']!=generation['contract']['image']:
                        raise ContractError('Prepared image policy differs from encoder input contract')
                    digest=embedding_input_hash(generation['contract'],kind,poster_hash=prep['content_hash'])
                inherited=store.inherited(gid,kind,key,digest)
                if kind=='media_poster' and row['poster']['state']=='missing_art':
                    store.complete_missing_poster(gid,key,digest,row['poster'],origin=inherited['origin_generation'] if inherited else None)
                else:
                    if inherited:result=vector(inherited['embedding']);timing=dict(inherited=True)
                    elif kind=='media_text':
                        attempted=True;request_start=time.perf_counter();result,timing=ollama.embed(media_text(value))
                    else:
                        from pathlib import Path
                        data=(Path(cache)/(row['poster']['content_sha256']+'.png')).read_bytes()
                        if hashlib.sha256(data).hexdigest()!=row['poster']['content_sha256']:raise ContractError('Prepared image checksum mismatch')
                        attempted=True;request_start=time.perf_counter();result,timing=ollama.embed(poster=data)
                    if attempted:store.log_inference(gid,kind,key,digest,'succeeded',timing)
                    store.complete(gid,kind,key,result,digest,poster=row['poster'] if kind=='media_poster' else None,
                        timing=timing,origin=inherited['origin_generation'] if inherited else None)
                store.conn.commit()
            except Exception as exc:
                error=safe_error(exc);store.conn.rollback();store.fail(gid,kind,key,error);store.conn.commit()
                if attempted:
                    store.log_inference(gid,kind,key,digest,'failed',dict(timing or {},error=error,attempt_elapsed_seconds=time.perf_counter()-request_start));store.conn.commit()
            except KeyboardInterrupt:
                store.conn.rollback()
                if attempted:
                    store.log_inference(gid,kind,key,digest,'interrupted',dict(error='KeyboardInterrupt',attempt_elapsed_seconds=time.perf_counter()-request_start,server_completion='unknown'));store.conn.commit()
                raise
            progress(dict(stage=kind,item_key=key,error=error,reused=bool(inherited)))
    return store.counts(gid)


def run_watches(store,gid,ollama,*,progress=lambda x:None):
    generation=store.mutable(gid)
    if generation['contract']['watch_serializer']!=WATCH_VERSION or generation['contract']['media_serializer']!=MEDIA_VERSION:
        raise ContractError('Behavioral/media serializer version differs from this implementation')
    if asdict(ollama.encoder)!=generation['contract']['encoder']:
        raise ContractError('Watch encoder differs from generation')
    if store.counts(gid)['media_text']['succeeded']!=generation['expected']['media_text']:
        raise ContractError('Complete and validate media before watch generation')
    media={r['item_key']:r for r in store.items(gid,'media_text')}
    with store.writer('ollama:'+ollama.encoder.digest),store.writer(gid):
        for row in (row for batch in store.batches(gid,'watch',size=32,pending=True) for row in batch):
            error=None;attempted=False;timing=None;request_start=None;inherited=None
            try:
                parent=media[row['media_key']]
                text=watch_text(row['source'],parent['source']['metadata'])
                digest=embedding_input_hash(generation['contract'],'watch',text=text,
                    event_hash=row['semantic_hash'],media_hash=parent['semantic_hash'])
                inherited=store.inherited(gid,'watch',row['item_key'],digest)
                if inherited:result=vector(inherited['embedding']);timing=dict(inherited=True)
                else:
                    attempted=True;request_start=time.perf_counter();result,timing=ollama.embed(text)
                    store.log_inference(gid,'watch',row['item_key'],digest,'succeeded',timing)
                store.complete(gid,'watch',row['item_key'],result,digest,timing=timing,
                    dependencies=[('media_text',row['media_key'],parent['semantic_hash'])],
                    origin=inherited['origin_generation'] if inherited else None)
                store.conn.commit()
            except Exception as exc:
                error=safe_error(exc);store.conn.rollback();store.fail(gid,'watch',row['item_key'],error);store.conn.commit()
                if attempted:
                    store.log_inference(gid,'watch',row['item_key'],digest,'failed',dict(timing or {},error=error,attempt_elapsed_seconds=time.perf_counter()-request_start));store.conn.commit()
            except KeyboardInterrupt:
                store.conn.rollback()
                if attempted:
                    store.log_inference(gid,'watch',row['item_key'],digest,'interrupted',dict(error='KeyboardInterrupt',attempt_elapsed_seconds=time.perf_counter()-request_start,server_completion='unknown'));store.conn.commit()
                raise
            progress(dict(stage='watch',item_key=row['item_key'],error=error,reused=bool(inherited)))
        progress(store.counts(gid))


def qualifying_profiles(events,media,threshold):
    """Exact original qualification/weighting: max ratio > threshold OR count >=5.

    Media vectors are each used once per rating key; means are not normalized.
    Availability cutoffs are applied separately by the historical feature builder.
    """
    pairs={}
    for event in events:
        key=str(event['rating_key'])
        parent=media.get(key)
        if not parent or event.get('played_seconds') is None:continue
        runtime=runtime_seconds(parent)
        if not runtime or runtime<=0:continue
        pair=pairs.setdefault((event['username'],key),dict(count=0,ratio=0))
        pair['count']+=1
        pair['ratio']=max(pair['ratio'],event['played_seconds']/runtime)
    profiles={}
    for (owner,key),stats in pairs.items():
        if stats['ratio']>threshold or stats['count']>=5:
            profiles.setdefault(owner,[]).append(key)
    return {owner:sorted(keys) for owner,keys in profiles.items()}


def runtime_seconds(parent):
    source=parent['source']
    if 'duration' in source:
        return source['duration']/1000 if source['duration'] is not None else None
    value=source['metadata'].get('runtime_minutes')
    return value*60 if value is not None else None


def run_users(store,gid,*,progress=lambda x:None):
    generation=store.mutable(gid)
    if generation['contract']['profile']!=PROFILE_VERSION:raise ContractError('Profile version differs from this implementation')
    counts=store.counts(gid)
    if counts['media_text']['succeeded']!=generation['expected']['media_text']:
        raise ContractError('All media must succeed before building user profiles')
    media={r['item_key']:r for r in store.items(gid,'media_text')}
    profiles=qualifying_profiles(generation['snapshot']['events'],media,generation['contract']['profile_threshold'])
    existing={r['item_key']:r for r in store.items(gid,'user')}
    with store.writer(gid):
        expected={**generation['expected'],'user':len(profiles)}
        store.query(sql.SQL('UPDATE {} SET expected=%s WHERE generation_id=%s').format(store.table('generations')),(Json(expected),gid))
        store.conn.commit()
        for owner,keys in profiles.items():
            deps=[('media_text',key,media[key]['input_hash']) for key in keys]
            source=dict(qualifying_keys=keys,history_hash=fingerprint([e for e in generation['snapshot']['events'] if e['username']==owner]))
            digest=embedding_input_hash(generation['contract'],'user',source=source,dependencies=deps)
            if owner in existing and existing[owner]['status']=='succeeded' and existing[owner]['input_hash']==digest:continue
            store.upsert_source(gid,'user',owner,source,owner=owner)
            store.conn.commit()
            error=None;inherited=None
            try:
                inherited=store.inherited(gid,'user',owner,digest);started=time.perf_counter()
                if inherited:result=vector(inherited['embedding']);timing=dict(inherited=True)
                else:
                    result=np.mean(np.array([vector(media[key]['embedding']) for key in keys],dtype=np.float64),axis=0).tolist()
                    timing=dict(rebuilt=True,profile_seconds=time.perf_counter()-started)
                store.complete(gid,'user',owner,result,digest,dependencies=deps,timing=timing,
                    origin=inherited['origin_generation'] if inherited else None)
                store.conn.commit()
            except Exception as exc:
                error=type(exc).__name__;store.conn.rollback();store.fail(gid,'user',owner,error);store.conn.commit()
            progress(dict(stage='user',error=error,reused=bool(inherited)))
    return store.counts(gid)
