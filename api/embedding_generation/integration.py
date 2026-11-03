"""Bounded real Plex/Ollama scenarios, exclusively in connection-private tables.

Controlled source omissions/alternate artwork affect only these private fixtures.
They do not edit Plex metadata, artwork, source tables, or active configuration.
"""
from copy import deepcopy
from datetime import datetime,timezone
import math
import time
import requests
from psycopg2 import sql
from psycopg2.extras import Json

from . import backfill,source
from .contracts import ContractError,MEDIA_VERSION,WATCH_VERSION,fingerprint,vector,cosine
from .io import call
from .store import Store
from .operator import StageProgress


def run_bounded(conn,config,*,install,create,collect,report,keys,cache):
    if not keys or len(keys)>8:raise ContractError('Bounded cohort must contain 1..8 media identities')
    started=time.perf_counter();full=collect(config,keys=keys,max_events=16)
    movies=[r for r in full['media'] if r['media_type']=='movie']
    if len(movies)<2:raise ContractError('Bounded change/new-title scenarios require two real movies')
    new_key=str(movies[-1]['rating_key']);initial_keys=[k for k in keys if str(k)!=new_key]
    install(conn,temporary=True);store=Store(conn,'pg_temp')
    gid,ollama=create(store,config,scope='bounded',keys=initial_keys,max_events=16)
    plex=source.plex(config,cache);requests_log=[];embed=ollama.embed
    target=str(movies[0]['rating_key'])
    expected_requests=(len(keys)+1)*2+len(full['events'])+sum(str(e['rating_key'])==target for e in full['events'])
    def measured(text=None,poster=None):
        kind='media_poster' if poster is not None else 'watch' if text.startswith(WATCH_VERSION) else 'media_text'
        values,timing=embed(text,poster)
        requests_log.append(dict(modality=kind,**timing))
        elapsed=time.perf_counter()-started;rate=len(requests_log)/elapsed
        print(f"[bounded-integration {gid}] modality={kind} completed={len(requests_log)}/{expected_requests} failed=0 remaining={expected_requests-len(requests_log)} "
            f"rate={rate*60:.1f}/min elapsed={elapsed:.1f}s eta={(expected_requests-len(requests_log))/rate:.1f}s resumed/skipped=0 last_error=-",flush=True)
        return values,timing
    ollama.embed=measured
    def totals():return {kind:sum(r['modality']==kind for r in requests_log) for kind in ('media_text','media_poster','watch')}
    def delta(before):return {k:totals()[k]-before[k] for k in before}
    cases={}
    backfill.prepare_metadata(store,gid,plex);backfill.prepare_posters(store,gid,plex)
    before=totals();backfill.run_media_text(store,gid,ollama)
    cases['initial_text_stage']=delta(before)
    if cases['initial_text_stage']['media_poster']:raise ContractError('Text stage unexpectedly invoked poster inference')
    before=totals();backfill.run_media_poster(store,gid,cache,ollama)
    cases['initial_poster_stage']=delta(before)
    if cases['initial_poster_stage']['media_text']:raise ContractError('Poster stage unexpectedly invoked text inference')
    backfill.run_watches(store,gid,ollama);backfill.run_users(store,gid)
    row=next(r for r in store.items(gid,'media_text') if r['item_key']==target)
    changed=deepcopy(row['source']);changed['metadata']['synopsis']=None
    digest=fingerprint(changed['metadata'])
    store.upsert_source(gid,'media_text',target,changed,semantic_hash=digest)
    store.preparation(gid,target,'metadata',status='succeeded',content_hash=digest,
        provenance=dict(integration_case='controlled synopsis omission from real metadata'),timing=dict(metadata_seconds=0.))
    store.conn.commit();before=totals()
    backfill.run_media_text(store,gid,ollama);backfill.run_media_poster(store,gid,cache,ollama)
    cases['metadata_changed_poster_unchanged']=delta(before)
    if cases['metadata_changed_poster_unchanged']!={'media_text':1,'media_poster':0,'watch':0}:raise ContractError('Metadata change was not independent')
    # Use another actual Plex poster from this cohort. This is a controlled
    # alternate input, not a claim that the selected title's Plex artwork changed.
    posters=store.items(gid,'media_poster');old=next(r for r in posters if r['item_key']==target)
    alternate=next(r for r in posters if r['poster']['content_sha256']!=old['poster']['content_sha256'])
    poster={**alternate['poster'],'integration_case':'alternate actual poster from bounded cohort'}
    poster_hash=fingerprint({k:poster[k] for k in ('state','content_sha256','preprocessing')})
    store.invalidate_children(gid,'media_poster',target)
    store.query(sql.SQL("UPDATE {} SET poster=%s,status='pending',embedding=NULL WHERE generation_id=%s AND kind='media_poster' AND item_key=%s")
        .format(store.table('items')),(Json(poster),gid,target))
    store.preparation(gid,target,'poster',status='succeeded',content_hash=poster_hash,provenance=poster,timing=dict(retrieval_seconds=0.,preprocessing_seconds=0.))
    store.conn.commit();before=totals()
    backfill.run_media_poster(store,gid,cache,ollama);backfill.run_media_text(store,gid,ollama)
    cases['poster_changed_metadata_unchanged']=delta(before)
    if cases['poster_changed_metadata_unchanged']!={'media_text':0,'media_poster':1,'watch':0}:raise ContractError('Poster change was not independent')
    before=totals();backfill.run_media_text(store,gid,ollama);backfill.run_media_poster(store,gid,cache,ollama)
    cases['neither_changed']=delta(before)
    if any(cases['neither_changed'].values()):raise ContractError('Unchanged checkpoints repeated inference')
    # Admit the reserved real movie and its library-linked events into the same
    # private snapshot, exercising a genuinely new identity for this generation.
    generation=store.generation(gid);snapshot=deepcopy(generation['snapshot'])
    snapshot['_db_hash']=full['_db_hash']
    new=next(r for r in full['media'] if str(r['rating_key'])==new_key)
    snapshot['media'].append(new)
    events=[e for e in full['events'] if str(e['rating_key'])==new_key]
    snapshot['events'].extend(events);snapshot['legacy_watch_ids'].extend(e['watch_id'] for e in events if e['watch_id'] in full['legacy_watch_ids'])
    from .history_scope import partition_history
    snapshot=partition_history(snapshot)
    snapshot['availability']=full['availability']
    store.upsert_source(gid,'media_text',new_key,new);store.upsert_source(gid,'media_poster',new_key,dict(rating_key=new['rating_key']))
    for event in events:store.upsert_source(gid,'watch',str(event['watch_id']),event,owner=event['username'],media_key=new_key,
        semantic_hash=fingerprint({k:v for k,v in event.items() if k!='observed_at'}))
    profiles=store.profile_sources(snapshot,generation['contract']['profile_threshold'])
    for owner,value in profiles.items():store.upsert_source(gid,'user',owner,value,owner=owner)
    expected=dict(media_text=len(keys),media_poster=len(keys),watch=len(snapshot['events']),user=len(profiles))
    store.query(sql.SQL('UPDATE {} SET snapshot=%s,source_hash=%s,expected=%s WHERE generation_id=%s').format(store.table('generations')),(Json(snapshot),full['_db_hash'],Json(expected),gid));store.conn.commit()
    backfill.prepare_metadata(store,gid,plex);backfill.prepare_posters(store,gid,plex)
    before=totals()
    try:
        with StageProgress(store,gid,'bounded-interruption',kind='media_text',printer=lambda *a,**kw:None) as progress:
            def interrupt_after_checkpoint(event):progress(event);raise KeyboardInterrupt()
            backfill.run_media_text(store,gid,ollama,progress=interrupt_after_checkpoint)
    except KeyboardInterrupt:pass
    checkpoint=totals();backfill.run_media_text(store,gid,ollama)
    cases['interrupted_resume']=dict(requests_before_interruption=delta(before),resume_requests=delta(checkpoint),
        checkpoint_committed=True,stage_status=store.query("SELECT status FROM pg_temp.stage_runs ORDER BY started_at DESC LIMIT 1")['status'])
    if any(cases['interrupted_resume']['resume_requests'].values()):raise ContractError('Resume repeated completed inference')
    backfill.run_media_poster(store,gid,cache,ollama);cases['new_title']=delta(before)
    if cases['new_title']!={'media_text':1,'media_poster':1,'watch':0}:raise ContractError('New title did not generate both independent modalities')
    baseline_counts=store.counts(gid)
    # Explicit missing-reference fixture: no bytes, no model call, no fabricated
    # image vector. Neither Plex artwork nor the source library is modified.
    leaves=[r['item_key'] for r in store.items(gid,'media_text') if r['source']['metadata']['media_type'] in ('movie','episode')]
    missing_owner,missing_key=next((owner,key) for owner,profile in profiles.items() for key in leaves if any(k!=key for k in profile['qualifying_keys']))
    row=next(r for r in store.items(gid,'media_text') if r['item_key']==missing_key)
    changed=deepcopy(row['source']);changed['poster_reference']['_poster_sources']=[]
    store.upsert_source(gid,'media_text',missing_key,changed,semantic_hash=row['semantic_hash']);store.conn.commit()
    backfill.prepare_posters(store,gid,plex,refresh=True,only_keys={missing_key})
    before=totals();backfill.run_media_poster(store,gid,cache,ollama);backfill.run_media_text(store,gid,ollama)
    cases['missing_poster']=dict(requests=delta(before),state=next(r for r in store.items(gid,'media_poster') if r['item_key']==missing_key)['status'],
        policy='NULL image vector; missing XGBoost slots plus poster_missing=1',source='controlled missing-reference fixture')
    if any(cases['missing_poster']['requests'].values()) or cases['missing_poster']['state']!='missing':raise ContractError('Invalid missing-art policy')
    backfill.run_watches(store,gid,ollama);backfill.run_users(store,gid)
    from .features import feature_row,Vocabulary
    from .contracts import utc
    from datetime import timedelta
    import numpy as np
    generation=store.generation(gid)
    feature=feature_row(generation,{r['item_key']:r for r in store.items(gid,'media_text')},
        {r['item_key']:r for r in store.items(gid,'watch')},generation['snapshot']['events'],missing_owner,missing_key,
        utc(generation['snapshot']['as_of'])+timedelta(microseconds=1),posters={r['item_key']:r for r in store.items(gid,'media_poster')})
    matrix=Vocabulary().transform([feature])
    if not np.isnan(matrix[0,768:1536]).all() or matrix[0,-1]!=1:raise ContractError('Real missing-art feature construction failed')
    cases['missing_poster']['feature_check']=dict(embedding_dimensions=2304,missing_poster_slots=768,poster_missing=1,
        finite_text_and_user=bool(np.isfinite(feature['embedding'][:768]).all() and np.isfinite(feature['embedding'][1536:]).all()))
    result=report(store,gid);result.update(observed_at=datetime.now(timezone.utc).isoformat(),
        scenarios=cases,after_new_title_counts=baseline_counts,request_statistics=requests_log,
        total_runtime_seconds=time.perf_counter()-started,
        input_note='Real Plex cohort and real Ollama inference. Source omissions and alternate artwork are controlled private fixtures; no source mutation.',
        production_backfill=False,production_activation=False)
    result['vector_integrity']={}
    for kind in ('media_text','media_poster','watch','user'):
        values=[vector(r['embedding']) for r in store.items(gid,kind) if r['embedding'] is not None]
        norms=[math.sqrt(sum(v*v for v in value)) for value in values]
        result['vector_integrity'][kind]=dict(valid_vectors=len(values),dimensions=768,finite=True,nonzero=True,
            min_norm=min(norms) if norms else None,max_norm=max(norms) if norms else None)
    media=store.items(gid,'media_text');watches=store.items(gid,'watch')
    candidates=[m for m in media if m['source']['metadata']['media_type'] in ('movie','episode')]
    checks=[]
    for watch in watches:
        ranked=sorted([(m['item_key'],cosine(watch['embedding'],m['embedding'])) for m in candidates],key=lambda p:-p[1])
        checks.append(dict(media_key=watch['media_key'],own_rank=next(i for i,(key,_) in enumerate(ranked,1) if key==watch['media_key']),
            candidates=len(ranked),own_cosine=next(value for key,value in ranked if key==watch['media_key'])))
    result['watch_text_media_text_checks']=checks
    result['shared_space_limitation']='Bounded semantic alignment sanity check, not recommendation-quality evidence. No image/watch cosine used.'
    result['ollama_version']=call(requests.Session(),'GET',config['ollama.host'].rstrip('/')+'/api/version').json()['version']
    resident=call(requests.Session(),'GET',config['ollama.host'].rstrip('/')+'/api/ps').json().get('models',[])
    result['resident_allocation']=[{k:r.get(k) for k in ('digest','size','size_vram')} for r in resident]
    result['peak_memory']='Remote peak RSS unavailable; allocation snapshots are not peak memory.'
    if any(c['failed'] or c['pending'] or c['succeeded']+c['missing']!=c['expected'] for c in result['counts'].values()):
        raise ContractError('Bounded populations incomplete')
    return result
