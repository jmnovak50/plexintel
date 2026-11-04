"""Operational CPU policy and a three-request, non-writing poster benchmark.

Do not rewrite legacy generation/modality/input hashes when execution changes.
Compatibility evidence is bound to their existing immutable manifest instead.
"""
from contextlib import nullcontext
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import time
import numpy as np
import requests
from psycopg2 import sql
from .contracts import ContractError,Encoder,fingerprint,vector,embedding_input_hash
from .io import Ollama,call

POLICY='ollama-cpu-threads/1.0'
COSINE_MIN=1-1e-6
MAX_ABSOLUTE_ERROR=1e-4
RELATIVE_L2_MAX=1e-3


def receipt_path(cache,gid):
    return Path(cache).parent/('thread-benchmark-'+gid+'.json')


def compare(left,right):
    a=np.asarray(vector(left,unit=True),dtype=np.float64)
    b=np.asarray(vector(right,unit=True),dtype=np.float64)
    similarity=float(np.clip(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)),-1,1))
    maximum=float(np.max(np.abs(a-b)))
    relative=float(np.linalg.norm(a-b)/np.linalg.norm(b))
    return dict(cosine=similarity,max_absolute_error=maximum,relative_l2_error=relative,
        consistent=similarity>=COSINE_MIN and maximum<=MAX_ABSOLUTE_ERROR and relative<=RELATIVE_L2_MAX)


def state(store,gid):
    rows=store.query(sql.SQL('''SELECT kind,status,count(*) AS n,
        md5(string_agg(md5(item_key || COALESCE(embedding::text,'') || COALESCE(input_hash,'') ||
            COALESCE(modality_contract_hash,'') || COALESCE(provenance::text,'') || COALESCE(timing::text,'')),'' ORDER BY item_key)) AS checksum
        FROM {} WHERE generation_id=%s GROUP BY kind,status ORDER BY kind,status''').format(store.table('items')),(gid,),many=True)
    return [dict(r) for r in rows]


def binding(generation,host,version):
    encoder=Encoder(**generation['contract']['encoder'])
    return dict(policy=POLICY,generation_id=generation['generation_id'],contract_hash=generation['contract_hash'],
        semantic_encoder_hash=encoder.semantic_identity,encoder_digest=encoder.digest,
        image_contract=generation['contract']['image'],ollama_host=host.rstrip('/'),ollama_version=version,modality='media_poster')


def authorize(store,gid,host,threads,cache,*,path=None,version=None):
    """Read-only receipt check. No mutation or stage orchestration."""
    generation=store.generation(gid,include_snapshot=False)
    encoder=Encoder(**generation['contract']['encoder'])
    if type(threads) is not int or not 1<=threads<=encoder.num_thread:
        raise ContractError('Thread override must be a positive reduction of the pinned default')
    path=Path(path) if path else receipt_path(cache,gid)
    try:report=json.loads(path.read_text())
    except (OSError,ValueError):raise ContractError('No valid thread benchmark receipt; run benchmark-threads first') from None
    if version is None:version=call(requests.Session(),'GET',host.rstrip('/')+'/api/version').json()['version']
    if report.get('binding')!=binding(generation,host,version) or not report.get('state_unchanged') or not report.get('baseline_consistent'):
        raise ContractError('Thread benchmark receipt is incompatible or incomplete')
    if threads not in report.get('compatible_threads',[]):
        raise ContractError('Requested thread count has not passed same-record vector validation')
    return dict(policy=POLICY,receipt=str(path),receipt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        validated_num_thread=threads,benchmark_item_key=report['item_key'])


def benchmark(store,gid,config,cache,*,item_key=None,publication_lock=None,progress=print,client_class=Ollama):
    """Exactly 8,6,16, once each on ONE completed cached poster. Never persist vectors.

    Caller uses a read-only DB connection. Advisory session locks prevent an
    active migration worker from overlapping. A busy lock fails immediately.
    """
    started=time.perf_counter();generation=store.generation(gid,include_snapshot=False)
    encoder=Encoder(**generation['contract']['encoder'])
    if encoder.num_thread!=16:raise ContractError('This bounded comparison requires an existing 16-thread generation')
    row=store.query(sql.SQL("SELECT * FROM {} WHERE generation_id=%s AND kind='media_poster' AND status='succeeded' AND embedding IS NOT NULL AND (%s::text IS NULL OR item_key=%s) ORDER BY item_key::integer LIMIT 1")
        .format(store.table('items')),(gid,item_key,item_key))
    if not row:raise ContractError('A previously completed native poster embedding is required')
    prep=store.preparation(gid,row['item_key'],'poster')
    if not prep or prep['status']!='succeeded':raise ContractError('Completed poster has no compatible preparation checkpoint')
    expected=embedding_input_hash(generation['contract'],'media_poster',poster_hash=prep['content_hash'])
    if row['input_hash']!=expected:raise ContractError('Stored poster input differs from its generation contract')
    digest=row['poster']['content_sha256'];data=(Path(cache)/(digest+'.png')).read_bytes()
    if hashlib.sha256(data).hexdigest()!=digest:raise ContractError('Cached poster bytes fail the persisted hash')
    results=[];outputs={}
    # No StageProgress: it persists stage_runs; this benchmark must be read-only.
    with (publication_lock or nullcontext()),store.writer('ollama:'+encoder.digest),store.writer(gid):
        before=state(store,gid)
        version=call(requests.Session(),'GET',config['ollama.host'].rstrip('/')+'/api/version').json()['version']
        client_class(config['ollama.host'],encoder,timeout=config['ollama.timeout_s']).verify_pinned()
        for threads in (8,6,16):
            progress(f'[benchmark-threads {gid}] item={row["item_key"]} threads={threads} completed={len(results)}/3',flush=True)
            client=client_class(config['ollama.host'],encoder,timeout=config['ollama.timeout_s'],num_thread=threads,inference_attempts=1)
            values,timing=client.embed(poster=data)
            if timing.get('request_attempts')!=1:raise ContractError('Benchmark exceeded its one-request bound')
            outputs[threads]=values
            results.append(dict(threads=threads,**timing,versus_persisted=compare(values,row['embedding'])))
        after=state(store,gid)
        if after!=before or store.generation(gid,include_snapshot=False)['contract_hash']!=generation['contract_hash']:
            raise ContractError('Generation state changed during benchmark')
    baseline=next(r for r in results if r['threads']==16)['versus_persisted']['consistent']
    compatible=[]
    for result in results:
        result['versus_16']=compare(outputs[result['threads']],outputs[16])
        if baseline and result['versus_persisted']['consistent'] and result['versus_16']['consistent']:compatible.append(result['threads'])
    choices={r['threads']:r.get('server_nonload_seconds',r['client_seconds']) for r in results if r['threads'] in compatible}
    recommended=6 if 6 in choices and (8 not in choices or choices[6]<=choices[8]*1.10) else 8 if 8 in choices else None
    return dict(binding=binding(generation,config['ollama.host'],version),observed_at=datetime.now(timezone.utc).isoformat(),
        item_key=row['item_key'],poster_content_sha256=digest,persisted_embedding_input_hash=row['input_hash'],
        state_before=before,state_after=after,state_unchanged=before==after,baseline_consistent=baseline,
        results=results,compatible_threads=sorted(compatible),recommended_threads=recommended,
        recommendation_rule='Prefer 6 when its server non-load time is within 10% of 8; otherwise prefer 8. Thermal benefit is unmeasured.',
        tolerances=dict(cosine_min=COSINE_MIN,max_absolute_error=MAX_ABSOLUTE_ERROR,relative_l2_max=RELATIVE_L2_MAX),
        telemetry=dict(available=False,temperatures=None,throttling=None,
            reason='Ollama API has no host sensors; existing SSH attempt was denied. Requested thread count is not measured CPU utilization.'),
        inference_requests=3,records=1,repetitions_per_setting=1,execution_order=[8,6,16],total_seconds=time.perf_counter()-started,
        limitations='One record, one request per setting; model reloads and shared-host load affect timings. No steady-state thermal or peak-memory claim.',
        production_backfill=False,persisted_vectors_written=False)
