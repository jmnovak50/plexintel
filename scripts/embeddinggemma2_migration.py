#!/usr/bin/env python3
"""Staged EmbeddingGemma 2 migration. No production work is a default action."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
import time
from uuid import uuid4
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)

from api.embedding_generation.contracts import ContractError, Encoder, canonical, contract, fingerprint,media_text,vector,text_only
from api.embedding_generation.io import Ollama
from api.embedding_generation.store import Store
from api.embedding_generation import backfill, source
from api.embedding_generation.model import train,score
from api.embedding_generation.history_scope import partition_history,coverage_report
from api.embedding_generation.operator import StageProgress,approve_review,require_review,require_preparation
from api.embedding_generation.promotion import promote,rollback
from api.embedding_generation.runtime import MARKER,TRANSITION,active_generation,code_hash,legacy_writer_pids
from api.db.connection import connect_db
from psycopg2 import sql
from psycopg2.extras import Json

SCHEMA=ROOT/'api/db/migrations/optional/embedding_generation'
CACHE=ROOT/'artifacts/embeddinggemma2/posters'


def install(conn,*,temporary=False):
    for path in sorted(SCHEMA.glob('*.sql')):
        text=path.read_text()
        if temporary:
            text='\n'.join(line for line in text.splitlines() if not line.startswith(('CREATE SCHEMA','REVOKE')))
            text=text.replace('embedding_v2.','pg_temp.')
        with conn.cursor() as cur:cur.execute(text)
    conn.commit()


def collect(config,*,keys=None,max_events=None,progress=lambda value:None):
    snapshot=source.snapshot(media_keys=keys)
    db_hash=fingerprint(snapshot)
    if max_events is not None:
        # Round-robin source keys prevents a repeatedly played single title from
        # filling the entire bounded integration cohort.
        by_key={key:[e for e in snapshot['events'] if e['rating_key']==key] for key in keys}
        events=[]
        while any(by_key.values()) and len(events)<max_events:
            for key in sorted(by_key):
                if by_key[key] and len(events)<max_events:events.append(by_key[key].pop(0))
        snapshot['events']=events
        selected={str(e['watch_id']) for e in events}
        snapshot['legacy_watch_ids']=[key for key in snapshot['legacy_watch_ids'] if str(key) in selected]
    snapshot['_db_hash']=db_hash
    snapshot=partition_history(snapshot)
    snapshot['as_of']=datetime.now(timezone.utc).isoformat()
    availability=source.event_availability(config,snapshot,bounded=keys is not None,progress=progress)
    snapshot['availability']=availability
    for event in snapshot['events']:event['observed_at']=snapshot['as_of']
    return snapshot


def create(store,config,*,scope='full',keys=None,max_events=None,parent=None,progress=lambda value:None,require_parent_contract=False):
    pinned=Encoder(**store.generation(parent,include_snapshot=False)['contract']['encoder']) if parent else None
    ollama=Ollama(config['ollama.host'],pinned,timeout=config['ollama.timeout_s'])
    encoder=ollama.verify_pinned() if pinned else ollama.resolve(config['ollama.threads'])
    specification=contract(encoder,config['user_embeddings.engagement_threshold'])
    specification.update(movie_revisit_days=config['training.movie_revisit_pending_days'],
                         tv_revisit_days=config['training.tv_revisit_pending_days'])
    if require_parent_contract and fingerprint(specification)!=store.generation(parent,include_snapshot=False)['contract_hash']:
        raise ContractError('Daily encoder/feature contract changed; explicit manual shadow migration required')
    gid=str(uuid4())
    snapshot=collect(config,keys=keys,max_events=max_events,
        progress=lambda value:progress(dict(value,generation_id=gid)))
    if parent:
        previous={str(e['watch_id']):e for e in store.generation(parent)['snapshot']['events']}
        for event in snapshot['events']:
            old=previous.get(str(event['watch_id']))
            if old and fingerprint({k:v for k,v in old.items() if k!='observed_at'})==fingerprint({k:v for k,v in event.items() if k!='observed_at'}):
                event['observed_at']=old['observed_at']
    gid=store.create(specification,snapshot,scope=scope,parent=parent,gid=gid,progress=progress)
    return gid,ollama


def legacy_vectors():
    conn=connect_db();conn.set_session(readonly=True)
    try:
        from pgvector.psycopg2 import register_vector
        register_vector(conn)
        result={}
        with conn.cursor() as cur:
            for kind,table,key in [('media','media_embeddings','rating_key'),('watch','watch_embeddings','watch_id')]:
                cur.execute(sql.SQL('SELECT {},embedding FROM public.{}').format(sql.Identifier(key),sql.Identifier(table)))
                result[kind]={str(k):v.to_numpy().tolist() if hasattr(v,'to_numpy') else list(v) for k,v in cur.fetchall()}
        return result
    finally:conn.rollback();conn.close()


def report(store,gid):
    generation=store.generation(gid)
    counts=store.counts(gid)
    stages=store.query(sql.SQL('SELECT stage,status,count(*) AS n,sum((timing->>\'metadata_seconds\')::numeric) AS metadata_seconds,sum((timing->>\'retrieval_seconds\')::numeric) AS retrieval_seconds,sum((timing->>\'preprocessing_seconds\')::numeric) AS preprocessing_seconds FROM {} WHERE generation_id=%s GROUP BY stage,status')
        .format(store.table('preparations')),(gid,),many=True)
    stages=[{k:float(v) if k.endswith('_seconds') and v is not None else v for k,v in dict(r).items()} for r in stages]
    stage_counts={}
    for stage in ('metadata','poster'):
        expected=0 if stage=='poster' and text_only(generation['contract']) else generation['expected']['media_text']
        stage_counts[stage]=dict(expected=expected,succeeded=0,failed=0,pending=expected)
    for row in stages:
        stage_counts[row['stage']][row['status']]=row['n'];stage_counts[row['stage']]['pending']-=row['n']
    history=store.query(sql.SQL("""SELECT stage,status,count(*) AS attempts,
        sum((timing->>'metadata_seconds')::numeric) AS metadata_seconds,
        sum((timing->>'retrieval_seconds')::numeric) AS retrieval_seconds,
        sum((timing->>'preprocessing_seconds')::numeric) AS preprocessing_seconds
        FROM {} WHERE generation_id=%s GROUP BY stage,status""").format(store.table('preparation_attempts')),(gid,),many=True)
    history=[{k:float(v) if k.endswith('_seconds') and v is not None else v for k,v in r.items()} for r in history]
    timing={}
    for kind in ('media_text','media_poster','watch','user'):
        rows=store.items(gid,kind)
        requests=store.query(sql.SQL('SELECT item_key,status,stats FROM {} WHERE generation_id=%s AND kind=%s').format(store.table('inference_requests')),(gid,kind),many=True)
        real=[r['stats'] for r in requests]
        timing[kind]=dict(inference_requests=len(requests),successful_requests=sum(r['status']=='succeeded' for r in requests),
            regenerated_items=len({r['item_key'] for r in requests if r['status']=='succeeded'}),
            failed_or_interrupted_attempts=sum(r['status']!='succeeded' for r in requests),
            inherited=sum(bool((r.get('timing') or {}).get('inherited')) for r in rows),
            profiles_rebuilt=sum(bool((r.get('timing') or {}).get('rebuilt')) for r in rows),
            profile_seconds=sum((r.get('timing') or {}).get('profile_seconds',0) for r in rows),
            client_seconds=sum(t.get('client_seconds',0) for t in real),
            server_nonload_seconds=sum(t.get('server_nonload_seconds',0) for t in real))
    return dict(generation_id=gid,scope=generation['scope'],status=generation['status'],
        contract_hash=generation['contract_hash'],encoder=generation['contract']['encoder'],counts=counts,
        preparations=[dict(r) for r in stages],preparation_history=history,preparation_counts=stage_counts,timing=timing,
        source_availability=generation['snapshot'].get('availability'),
        watch_coverage=coverage_report(generation['snapshot']),
        missing_art=sum(r['status']=='missing' for r in store.items(gid,'media_poster')),
        validation=generation['validation'],
        metadata_sources=[dict(r) for r in store.query(sql.SQL("SELECT source->'metadata_origin'->'components'->'media'->>'source' AS source,count(*) AS records FROM {} WHERE generation_id=%s AND kind='media_text' AND source ? '_metadata_recovery' GROUP BY 1 ORDER BY 1")
            .format(store.table('items')),(gid,),many=True)],
        preparation_errors=[dict(r) for r in store.query(sql.SQL("SELECT stage,item_key,provenance->>'error' AS error FROM {} WHERE generation_id=%s AND status='failed' ORDER BY stage,item_key LIMIT 20")
            .format(store.table('preparations')),(gid,),many=True)],
        errors=[dict(r) for r in store.query(sql.SQL("SELECT kind,CASE WHEN kind='user' THEN '<user profile>' ELSE item_key END AS item_key,error FROM {} WHERE generation_id=%s AND status='failed' ORDER BY kind,item_key LIMIT 20")
            .format(store.table('items')),(gid,),many=True)],
        stage_runs=[{**dict(r),'started_at':r['started_at'].isoformat(),'finished_at':r['finished_at'].isoformat() if r['finished_at'] else None} for r in store.query(
            sql.SQL('SELECT stage,status,metrics,started_at,finished_at FROM {} WHERE generation_id=%s ORDER BY started_at DESC LIMIT 20').format(store.table('stage_runs')),(gid,),many=True)])


def bounded_keys():
    conn=connect_db();conn.set_session(readonly=True)
    try:
        with conn.cursor() as cur:
            cur.execute('''WITH candidates AS (
                SELECT DISTINCT l.media_type,l.rating_key,l.parent_rating_key,l.show_rating_key
                FROM public.library l JOIN public.watch_history wh USING(rating_key)
                WHERE l.media_type IN('movie','episode') AND wh.played_duration IS NOT NULL AND l.duration>0),
                ranked AS (SELECT *,row_number() OVER(PARTITION BY media_type ORDER BY rating_key) AS n FROM candidates)
                SELECT rating_key,parent_rating_key,show_rating_key FROM ranked WHERE n<=2''')
            return sorted({int(key) for row in cur.fetchall() for key in row if key is not None})
    finally:conn.rollback();conn.close()


def refresh_source(store,gid,config,*,progress=lambda value:None):
    generation=store.mutable(gid)
    if generation['scope']!='full':raise ContractError('Refresh-source expects full inventory')
    snapshot=collect(config,progress=progress)
    with store.writer(gid):
        total=len(snapshot['media'])+len(snapshot['events']);completed=0
        old_media={r['item_key']:r for r in store.items(gid,'media_text')}
        new_keys={str(r['rating_key']) for r in snapshot['media']}
        if not set(old_media).issubset(new_keys):raise ContractError('Removed/orphan keys require explicit reconciliation')
        for row in snapshot['media']:
            key=str(row['rating_key']);old=old_media.get(key)
            merged={**(old['source'] if old else {}),**row}
            store.upsert_source(gid,'media_text',key,merged,semantic_hash=old['semantic_hash'] if old else None)
            if old is None and not text_only(generation['contract']):store.upsert_source(gid,'media_poster',key,dict(rating_key=row['rating_key']))
            completed+=1
            if completed%32==0:progress(dict(expected=total,completed=completed,failed=0,phase='atomic source reconciliation',persist=False))
        old_watches={r['item_key']:r for r in store.items(gid,'watch')}
        if not set(old_watches).issubset({str(e['watch_id']) for e in snapshot['events']}):
            raise ContractError('Removed watch keys require explicit reconciliation')
        for row in snapshot['events']:
            digest=fingerprint({k:v for k,v in row.items() if k!='observed_at'})
            store.upsert_source(gid,'watch',str(row['watch_id']),row,owner=row['username'],media_key=str(row['rating_key']),semantic_hash=digest)
            completed+=1
            if completed%32==0:progress(dict(expected=total,completed=completed,failed=0,phase='atomic source reconciliation',persist=False))
        # Qualification/history dependencies can change even if poster pixels do
        # not. Profiles are cheap and explicitly rebuilt after a source refresh.
        store.query(sql.SQL("DELETE FROM {} WHERE generation_id=%s AND child_kind='user'").format(store.table('dependencies')),(gid,))
        store.query(sql.SQL("DELETE FROM {} WHERE generation_id=%s AND kind='user'").format(store.table('items')),(gid,))
        for table in ('artifacts','modality_training_rows','text_training_rows','predictions'):
            store.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(store.table(table)),(gid,))
        profiles=store.profile_sources(snapshot,generation['contract']['profile_threshold'])
        for owner,profile in profiles.items():store.upsert_source(gid,'user',owner,profile,owner=owner)
        expected=dict(media_text=len(snapshot['media']),media_poster=0 if text_only(generation['contract']) else len(snapshot['media']),watch=len(snapshot['events']),user=len(profiles))
        store.query(sql.SQL('UPDATE {} SET snapshot=%s,source_hash=%s,expected=%s WHERE generation_id=%s')
            .format(store.table('generations')),(Json(snapshot),snapshot['_db_hash'],Json(expected),gid))
        store.conn.commit()
        progress(dict(expected=total,completed=total,failed=0,phase='source snapshot committed'))


def execute_stages(store,gid,ollama,plex,cache,progress=print):
    total=store.generation(gid)['expected']['media_text']
    completed={'metadata':0,'poster':0}
    def prepared(value):
        stage='poster' if value['stage']=='poster-preparation' else value['stage'];completed[stage]+=1
        if completed[stage]%32==0 or completed[stage]==total:
            progress(dict(generation_id=gid,stage=stage,processed=completed[stage],expected=total))
    backfill.prepare_metadata(store,gid,plex,progress=prepared)
    backfill.prepare_posters(store,gid,plex,progress=prepared)
    backfill.run_media_text(store,gid,ollama,progress=progress)
    backfill.run_media_poster(store,gid,cache,ollama,progress=progress)
    backfill.run_watches(store,gid,ollama,progress=progress)
    backfill.run_users(store,gid)


def argument_parser():
    parser=argparse.ArgumentParser(description='Manual staged migration: no stage automatically starts the next. Inference, promotion and rollback are separate commands.')
    parser.add_argument('operation',choices=['preflight','coverage','inspect','export','install','create','metadata','recover-metadata','posters','media-text','media-poster',
        'watch','users','refresh-source','adopt-text','review','train','score','validate','status','verify','promote','rollback','recover-transition','benchmark-threads','smoke','daily','active'])
    parser.add_argument('--generation')
    parser.add_argument('--reuse-generation',help='Reuse only matching per-modality contracts from a validated independent generation')
    parser.add_argument('--approved-production-change',action='store_true',help='Explicit operator authorization for THIS stage only')
    parser.add_argument('--gate',choices=['text','poster','profiles','quality'])
    parser.add_argument('--reason')
    parser.add_argument('--quality-go',action='store_true')
    parser.add_argument('--missing-art-limit',type=int,default=0)
    parser.add_argument('--deployment-receipt',type=Path)
    parser.add_argument('--promotion-id')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--force-poster-check',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--item-key',help='Media identity for read-only input/vector inspection')
    parser.add_argument('--artifact',choices=['dataset.json','evaluation.json','scoring.json','dimensions.json','daily-performance.json'])
    parser.add_argument('--pipeline-lock-held',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--num-thread',type=int,help='Validated operational CPU thread reduction for media-poster only; preserves the generation contract')
    parser.add_argument('--thread-validation',type=Path,help='Optional benchmark receipt path; defaults to this generation\'s local thread-benchmark artifact')
    return parser


def preflight(conn,config):
    import shutil
    from api.embedding_generation.io import call
    import requests
    from urllib.parse import urlsplit,urlunsplit
    conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
    snapshot=source.read_snapshot(conn);scoped=partition_history(snapshot)
    ollama=Ollama(config['ollama.host'],timeout=config['ollama.timeout_s']);encoder=ollama.resolve(config['ollama.threads'])
    version=call(requests.Session(),'GET',config['ollama.host'].rstrip('/')+'/api/version').json()['version']
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('embedding_v2.modality_training_rows')")
        installed=cur.fetchone()[0] is not None
    redirect=urlsplit(config['plex.redirect_uri'])
    return dict(observed_at=datetime.now(timezone.utc).isoformat(),host='birch',read_only=True,
        ollama_host=config['ollama.host'],ollama_version=version,encoder=asdict(encoder),schema_v2_installed=installed,
        backend_origin=urlunsplit((redirect.scheme,redirect.netloc,'','','')),
        target_counts=dict(media_text=len(scoped['media']),media_poster=len(scoped['media']),watch=len(scoped['events']),
            user=len(Store.profile_sources(scoped,config['user_embeddings.engagement_threshold']))),
        watch_coverage=coverage_report(scoped),project_free_bytes=shutil.disk_usage(ROOT).free,
        legacy_model_sha256=hashlib.sha256((ROOT/'xgb_model.pkl').read_bytes()).hexdigest(),
        activation_marker_present=MARKER.exists(),next_stage='Review scope/resources, then explicitly run install/create. No inference was performed.')


def verify(store,gid=None,*,live_schema='public'):
    if live_schema not in ('public','pg_temp'):raise ContractError('Unknown verification schema')
    control=store.query(sql.SQL('SELECT active_generation FROM {} WHERE singleton').format(store.table('control')))
    active=control['active_generation']
    if not active or gid and active!=gid:raise ContractError('Requested independent generation is not active')
    from api.embedding_generation.text_production import load_production,verify_current_production
    current=load_production(store)
    if current and current[0]['generation_id']==active:return verify_current_production(store,live_schema=live_schema)
    generation=store.generation(active)
    if generation['status']!='active':raise ContractError('Active generation status mismatch')
    from api.embedding_generation.model import load_bundle
    bundle,_=load_bundle(store,active)
    from api.embedding_generation.text_production import physical_verification
    physical=physical_verification(store,active,live_schema)
    for kind,table in [('media_text','media_embeddings'),('watch','watch_embeddings'),('user','user_embeddings')]:
        actual=store.query(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(live_schema,table)))['n']
        if actual!=generation['expected'][kind]:raise ContractError('Active materialization count mismatch')
        key='username' if kind=='user' else 'watch_id' if kind=='watch' else 'rating_key'
        mismatch=store.query(sql.SQL('''SELECT count(*) AS n FROM {} p JOIN {} i ON i.generation_id=%s AND i.kind=%s AND i.item_key=p.{}::text WHERE p.embedding<>i.embedding''')
            .format(sql.Identifier(live_schema,table),store.table('items'),sql.Identifier(key)),(active,kind))['n']
        if mismatch:raise ContractError('Active compatibility vector values mismatch')
    for kind,count in store.counts(active).items():
        if count['succeeded']+(count['missing'] if kind=='media_poster' else 0)!=count['expected'] or count['failed'] or count['pending']:
            raise ContractError('Active modality population is incomplete')
    result=report(store,active)
    result.update(verified=True,feature_order=bundle['ordering'],embedding_dimensions=sum(bundle['dimensions']),physical_vectors=physical)
    if text_only(generation['contract']):
        from api.embedding_generation.text_production import load_production
        production=load_production(store)
        if not production or production[0]['generation_id']!=active:raise ContractError('Canonical production model is not active')
        result['canonical_model_sha256']=production[0]['model_sha256']
        result['poster_inference']='disabled/1.0'
    return result


def dispatch_stage(store,gid,args,config):
    """Exactly one manual stage. Real dependency reviews never invoke producers."""
    operation=args.operation
    if args.num_thread is not None and operation!='media-poster':
        raise ContractError('--num-thread is supported only for media-poster')
    if operation=='recover-metadata' and not args.reason:
        raise ContractError('recover-metadata requires --reason recording the historical-source decision')
    selected=store.generation(gid,include_snapshot=False)['contract']
    if text_only(selected) and operation in ('posters','media-poster'):
        raise ContractError('Poster preparation and inference are disabled by the text production contract')
    if operation in ('posters','media-text'):require_preparation(store,gid,'metadata')
    if operation=='media-poster':require_preparation(store,gid,'poster')
    if operation=='review':
        if not args.gate or not args.reason:raise ContractError('review requires --gate and --reason')
        return approve_review(store,gid,args.gate,args.reason,missing_art_limit=args.missing_art_limit,quality_go=args.quality_go)
    if operation in ('watch','users','train','score','validate'):
        require_review(store,gid,'text')
        if not text_only(selected):require_review(store,gid,'poster')
    if operation in ('train','score','validate'):require_review(store,gid,'profiles')
    if operation in ('score','validate'):require_review(store,gid,'quality')
    g=store.generation(gid)
    if operation=='users':
        watch=store.counts(gid)['watch']
        if watch['succeeded']!=watch['expected'] or watch['failed']:raise ContractError('Watch stage is incomplete')
    if operation in ('media-text','media-poster','watch'):
        execution={}
        if args.num_thread is not None:
            from api.embedding_generation.execution import authorize
            execution=authorize(store,gid,config['ollama.host'],args.num_thread,CACHE,path=args.thread_validation)
        ollama=Ollama(config['ollama.host'],Encoder(**g['contract']['encoder']),timeout=config['ollama.timeout_s'],num_thread=args.num_thread)
        if execution:ollama.execution_validation=execution
        if not args.pipeline_lock_held:ollama.before_request=yield_to_existing_pipeline
    if operation in ('metadata','recover-metadata','posters'):
        plex=source.plex(config,CACHE)
    kind={'media-text':'media_text','media-poster':'media_poster','watch':'watch','users':'user'}.get(operation)
    prep={'metadata':'metadata','recover-metadata':'metadata','posters':'poster'}.get(operation)
    with StageProgress(store,gid,operation,kind=kind,preparation=prep,rescan=bool((args.refresh or args.force_poster_check) and prep)) as progress:
        if operation=='metadata':backfill.prepare_metadata(store,gid,plex,refresh=args.refresh,progress=progress)
        elif operation=='recover-metadata':
            from api.embedding_generation.recovery import prepare
            prepare(store,gid,plex,reason=args.reason,progress=progress)
        elif operation=='posters':backfill.prepare_posters(store,gid,plex,refresh=args.refresh,force=args.force_poster_check,progress=progress)
        elif operation=='media-text':backfill.run_media_text(store,gid,ollama,progress=progress)
        elif operation=='media-poster':backfill.run_media_poster(store,gid,CACHE,ollama,progress=progress)
        elif operation=='watch':backfill.run_watches(store,gid,ollama,progress=progress)
        elif operation=='users':backfill.run_users(store,gid,progress=progress)
        elif operation=='refresh-source':
            refresh_source(store,gid,config,progress=progress)
        elif operation=='train':train(store,gid,legacy_populations=legacy_vectors() if g['base_generation'] is None else None,progress=progress)
        elif operation=='score':score(store,gid,progress=progress)
        elif operation=='validate':
            store.validate(gid,quality_go=args.quality_go,missing_art_limit=args.missing_art_limit,progress=progress)
        else:raise ContractError('Not a manual stage')
    return report(store,gid)


def main(argv=None):
    parser=argument_parser();args=parser.parse_args(argv)
    if args.operation!='daily':return _main(args,parser)
    from api.embedding_generation.run_safety import classify_failure,failure_message,VERIFICATION_ONLY_EXIT
    try:result=_main(args,parser)
    except Exception as exc:
        failure=classify_failure(exc)
        print(canonical(dict(error=failure_message(exc),**failure)),flush=True)
        raise SystemExit(75 if failure['retryable'] else 78) from None
    if result and result.get('verification_only'):raise SystemExit(VERIFICATION_ONLY_EXIT)
    return result


def _main(args,parser):
    if args.num_thread is not None and args.operation!='media-poster':parser.error('--num-thread is supported only for media-poster')
    if args.thread_validation is not None and (args.operation!='media-poster' or args.num_thread is None):
        parser.error('--thread-validation requires media-poster --num-thread')
    if args.operation=='active':raise SystemExit(0 if active_generation() else 3)
    read_only={'preflight','coverage','status','verify','inspect','export'}
    if args.operation not in read_only|{'smoke','daily'} and not args.approved_production_change:
        parser.error('THIS stage requires operator approval and --approved-production-change')
    conn=None;primary_error=None;completed_result=None
    try:
        conn=connect_db()
        if args.operation in read_only|{'benchmark-threads'}:conn.set_session(readonly=True)
        if args.operation=='coverage':
            conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
            generation=Store(conn).generation(args.generation) if args.generation else None
            snapshot=generation['snapshot'] if generation else source.read_snapshot(conn)
            result=dict(observed_at=datetime.now(timezone.utc).isoformat(),generation_id=args.generation,
                source_hash=generation['source_hash'] if generation else fingerprint(snapshot),**coverage_report(snapshot,details=True))
            if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
            print(canonical({k:v for k,v in result.items() if k!='quarantined_events'}));return
        config=source.settings()
        if args.operation=='preflight':
            result=preflight(conn,config)
            if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
            print(canonical(result));return
        if args.operation=='install':
            install(conn);MARKER.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            MARKER.write_text(canonical(dict(schema=2,code_sha256=code_hash())))
            print('Optional schema installed; no generation activated or stage started');return
        if args.operation=='smoke':
            from api.embedding_generation.integration import run_bounded
            result=run_bounded(conn,config,install=install,create=create,collect=collect,report=report,keys=bounded_keys(),cache=CACHE)
            if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
            print(canonical(result));return
        store=Store(conn)
        if args.operation=='benchmark-threads':
            from api.embedding_generation.execution import benchmark,receipt_path
            if not args.generation:parser.error('--generation is required')
            result=benchmark(store,args.generation,config,CACHE,item_key=args.item_key,publication_lock=publication_lock())
            target=args.output or receipt_path(CACHE,args.generation)
            target.parent.mkdir(parents=True,exist_ok=True)
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile(mode='w',dir=target.parent,delete=False) as handle:
                json.dump(result,handle,indent=2);handle.flush();os.fsync(handle.fileno());temporary=Path(handle.name)
            temporary.replace(target)
            print(canonical(dict(receipt=str(target),**result)))
            if result['recommended_threads'] is None:raise ContractError('No reduced thread setting passed vector compatibility; resume override remains blocked')
            return
        if args.operation=='daily':
            completed_result=daily(store,config,pipeline_lock_held=args.pipeline_lock_held)
            return completed_result
        if args.operation=='create':
            started=time.monotonic();last=[-100.]
            def creating(value):
                elapsed=time.monotonic()-started
                if elapsed-last[0]<5 and value['completed']!=value['expected']:return
                last[0]=elapsed;done=value['completed'];expected=value['expected'];rate=done/elapsed if elapsed else 0
                eta=f'{(expected-done)/rate:.0f}s' if rate else 'unknown'
                print(f"[create {value['generation_id']}] completed={done}/{expected} failed=0 remaining={expected-done} rate={rate*60:.1f}/min elapsed={elapsed:.0f}s eta={eta} resumed/skipped=0 record={value.get('phase','item seeding')} last_error=-",flush=True)
            print('[create] Inspecting source inventory/model identity; no inference will run.',flush=True)
            gid,_=create(store,config,parent=args.reuse_generation,progress=creating)
            print(canonical(report(store,gid)));return
        if args.operation=='verify':print(canonical(verify(store,args.generation)));return
        if args.operation=='rollback':
            if not args.promotion_id:parser.error('--promotion-id is required')
            with publication_lock(args.pipeline_lock_held):rollback(store,args.promotion_id,approved=True)
            print('Rollback restored verified prior generation');return
        if args.operation=='recover-transition':
            with publication_lock():
                if not TRANSITION.exists():print('No stale transition marker');return
                marker=json.loads(TRANSITION.read_text())
                if Path('/proc',str(marker['pid'])).exists() or legacy_writer_pids():raise ContractError('Transition/legacy writer still present')
                with conn.cursor() as cur:
                    cur.execute('SELECT pg_try_advisory_lock(184725,42)')
                    if not cur.fetchone()[0]:raise ContractError('Publication transaction is still running')
                control=store.query(sql.SQL('SELECT active_generation FROM {} WHERE singleton FOR UPDATE').format(store.table('control')))
                if control['active_generation']:verify(store,control['active_generation'])
                conn.commit();TRANSITION.unlink();print('Verified atomic database state; stale marker cleared')
            return
        if not args.generation:parser.error('--generation is required')
        gid=args.generation
        if args.operation=='status':
            from api.embedding_generation.text_production import load_production,verify_current_production
            current=load_production(store)
            if current and current[0]['generation_id']==gid:print(canonical(verify_current_production(store)))
            else:print(canonical(report(store,gid)))
            return
        if args.operation=='inspect':
            if not args.item_key:parser.error('--item-key is required')
            from api.embedding_generation.text_production import load_production
            current=load_production(store)
            if current and current[0]['generation_id']==gid:
                record=store.query(sql.SQL("SELECT record FROM {} WHERE kind='media_text' AND item_key=%s").format(store.table('production_inputs')),(args.item_key,))
                if not record:raise ContractError('Unknown production media identity')
                values=store.query('SELECT embedding FROM public.media_embeddings WHERE rating_key=%s',(int(args.item_key),))
                native=vector(values['embedding'],unit=True);record=record['record']
                result=dict(generation_id=gid,publication_id=current[0].get('publication_id'),item_key=args.item_key,
                    canonical_text=media_text(record['source']['metadata']),provenance=record['provenance'],
                    input_hash=record['input_hash'],origin_generation=record['origin_generation'],
                    output_dimensions=len(native),norm=sum(v*v for v in native)**.5,
                    poster_inference='disabled/1.0',model_sha256=current[0]['model_sha256'])
                if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
                print(canonical(result));return
            result=dict(generation_id=gid,item_key=args.item_key,modalities={})
            result['preparations']=[dict(r) for r in store.query(sql.SQL("SELECT stage,status,content_hash,provenance->>'error' AS error,timing FROM {} WHERE generation_id=%s AND item_key=%s ORDER BY stage")
                .format(store.table('preparations')),(gid,args.item_key),many=True)]
            kinds=('media_text',) if text_only(store.generation(gid,include_snapshot=False)['contract']) else ('media_text','media_poster')
            for kind in kinds:
                row=store.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s').format(store.table('items')),(gid,kind,args.item_key))
                if not row:raise ContractError('Unknown media identity')
                values=vector(row['embedding']) if row['embedding'] is not None else None
                result['modalities'][kind]=dict(status=row['status'],input_hash=row['input_hash'],
                    modality_contract_hash=row['modality_contract_hash'],provenance=row['provenance'],
                    output_dimensions=len(values) if values else None,norm=sum(v*v for v in values)**.5 if values else None,error=row['error'])
                result['modalities'][kind]['execution']=(row['timing'] or {}).get('execution')
                if kind=='media_text':result['canonical_text']=media_text(row['source']['metadata']) if row['source'].get('metadata') else None
                if kind=='media_text':
                    result['metadata_origin']=row['source'].get('metadata_origin')
                    result['metadata_recovery']=row['source'].get('_metadata_recovery')
                else:result['poster']=row['poster']
            if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
            print(canonical(result));return
        if args.operation=='export':
            if not args.artifact or not args.output:parser.error('export requires --artifact and --output')
            artifact=store.artifact(gid,args.artifact);args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_bytes(bytes(artifact['data']));print(canonical(dict(artifact=args.artifact,sha256=artifact['sha256'],output=str(args.output))));return
        if args.operation=='adopt-text':
            from api.embedding_generation.text_production import adopt
            with publication_lock(args.pipeline_lock_held):
                result=adopt(store,gid,reason=args.reason,progress=lambda value:print(canonical(value),flush=True))
        elif args.operation=='promote':
            if not args.deployment_receipt:parser.error('--deployment-receipt is required')
            receipt=json.loads(args.deployment_receipt.read_text())
            if receipt.get('generation_api')!=1:raise ContractError('Backend deployment receipt incompatible')
            if text_only(store.generation(gid,include_snapshot=False)['contract']) and receipt.get('text_production_api')!=1:
                raise ContractError('Backend lacks physical text production support; deploy reviewed code before promotion')
            with publication_lock(args.pipeline_lock_held):result=promote(store,gid,approved=True,deployed_code=receipt['deployed_code_sha256'])
        else:result=dispatch_stage(store,gid,args,config)
        print(canonical(result))
    except BaseException as exc:
        primary_error=exc
        raise
    finally:
        if conn is not None:
            try:conn.close()
            except Exception:
                if primary_error is None:
                    if completed_result and completed_result.get('promotion_id'):
                        from api.embedding_generation.run_safety import RunFailure
                        raise RunFailure('COMPLETION_CLEANUP','Cleanup failed after a recorded publication/recovery; operator review required') from None
                    raise



from contextlib import contextmanager
@contextmanager
def publication_lock(already_held=False):
    if already_held:
        yield;return
    from api.services.pipeline_service import try_acquire_pipeline_lock
    lock=try_acquire_pipeline_lock(source='embedding-generation-publication')
    if lock is None:raise ContractError('Existing pipeline is running; publication refused')
    try:yield
    finally:lock.release()


def daily(store,config,*,pipeline_lock_held=False):
    from api.embedding_generation.text_production import daily as text_daily
    result=text_daily(store,config,collect=collect,plex_factory=source.plex,cache=CACHE,
        publication_lock=publication_lock,pipeline_lock_held=pipeline_lock_held,
        progress=lambda value:print(canonical(value),flush=True))
    summary=result['summary']
    print(canonical(dict(run_id=result['run_id'],generation_id=result['generation_id'],promotion_id=result['promotion_id'],
        verification_only=bool(result.get('verification_only')),outcome='verification_only' if result.get('verification_only') else 'daily_completed',
        counts=summary['counts'],inference=summary['inference'],poster_inference_requests=0,
        scoring=summary['scoring'],stages=summary['stages'],model_before=summary['model_before'],model_after=summary['model_after'],
        no_new_shadow_generation=True,elapsed_seconds=summary['elapsed_seconds'],
        total_elapsed_seconds=summary.get('elapsed_seconds_total',summary['elapsed_seconds']),
        semantic_labeling='disabled; incompatible legacy dimension labeler')))
    return result


def yield_to_existing_pipeline():
    """Shadow inference yields between records to existing scheduled production.
    Do not hold this lock over inference and starve the scheduler; an already
    running request may overlap the beginning of an ingestion stage briefly.
    """
    import fcntl
    from api.services.pipeline_service import get_pipeline_lock_path
    path=get_pipeline_lock_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+') as handle:
        while True:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                fcntl.flock(handle,fcntl.LOCK_UN)
                return
            except BlockingIOError:time.sleep(5)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:
        print('Interrupted by operator; committed checkpoints are preserved. Resume the SAME stage and generation ID.',file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        # No tracebacks/response payloads can leak credentials or private history.
        print(f'Embedding generation operation failed: {type(exc).__name__}',file=sys.stderr)
        if isinstance(exc,ContractError):print(str(exc),file=sys.stderr)
        raise SystemExit(1)
