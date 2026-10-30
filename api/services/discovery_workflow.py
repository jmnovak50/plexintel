"""Independent workflow using existing pipeline jobs, scheduler and resource lock.

No ML stages, shell commands, schema bootstrap or new scheduling service.
All network/background capabilities are server gated and off by default.
"""
from dataclasses import replace
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
import json,os,threading
from threading import Thread

from pydantic import BaseModel, ConfigDict, Field, model_validator
from api.services import pipeline_service as pipeline
from api.services.app_settings import SETTINGS_BY_KEY,parse_value,save_settings
from api.services.discovery_workspace import reader,effective_config
from api.services.seerr_client import SeerrClient,SeerrError
from api.services.seerr_discovery import build_scopes,sync_discovery
from api.db.seerr_discovery import DiscoveryRepository
from api.db.connection import connect_db

PREFIX='content_discovery_'
SCHEDULE_KEYS=tuple(k for k in SETTINGS_BY_KEY if k.startswith('discovery.'))

class WorkflowError(ValueError):
    def __init__(self,code,status=409):self.code,self.status=code,status;super().__init__(code)

def flag(name):return os.getenv('SEERR_DISCOVERY_'+name,'false').lower()=='true'

class Execution(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: UUID
    media_types:list[str]=Field(default_factory=lambda:['movie','tv'],min_length=1,max_length=2)
    start:date
    end:date
    languages:list[str]=Field(default_factory=lambda:['all'],min_length=1,max_length=20)
    max_pages:int=Field(default=50,ge=1,le=500)
    max_requests:int=Field(default=1000,ge=1,le=10000)
    persist:bool=False
    confirmed:bool=False

    @model_validator(mode='after')
    def validate_scope(self):
        if self.start>self.end or (self.end-self.start).days>7300:
            raise ValueError('Date range must be ordered and at most 7301 dates')
        if len(set(self.media_types))!=len(self.media_types) or any(x not in ('movie','tv') for x in self.media_types):
            raise ValueError('Select distinct movie/TV scopes')
        if len(set(self.languages))!=len(self.languages):raise ValueError('Duplicate language scopes')
        return self

def configuration(request=None):
    cfg,public=effective_config()
    if request:
        if request.max_pages>cfg.max_pages or request.max_requests>cfg.max_requests:
            raise WorkflowError('request_exceeds_instance_limits',422)
        try:
            cfg=replace(cfg,media_types=tuple(request.media_types),languages=tuple(request.languages),
                        max_pages=request.max_pages,max_requests=request.max_requests)
        except SeerrError as e:raise WorkflowError(e.code,422) from None
    return cfg,public

def scheduling_settings():
    # Existing settings registry and parser, but explicitly read-only: no lazy DDL,
    # description bootstrap or credential/environment copying during UI reads.
    with reader() as cur:
        cur.execute('SELECT key,raw_value FROM public.app_settings WHERE key=ANY(%s)',(list(SCHEDULE_KEYS),))
        rows={r['key']:r['raw_value'] for r in cur.fetchall()}
    return {k:parse_value(SETTINGS_BY_KEY[k],rows[k]) if rows.get(k) is not None else SETTINGS_BY_KEY[k].default for k in SCHEDULE_KEYS}

def next_slot(operation,settings,now=None):
    now=now or datetime.now(timezone.utc);tz=ZoneInfo(settings['discovery.timezone']);local=now.astimezone(tz)
    h,m=map(int,settings[f'discovery.{operation}.time'].split(':'))
    for i in range(9):
        day=local.date()+timedelta(days=i)
        if operation=='sweep' and day.weekday()!=settings['discovery.sweep.day']:continue
        candidate=datetime(day.year,day.month,day.day,h,m,tzinfo=tz)
        # Skip non-existent DST wall times; repeated hour executes once (fold=0).
        if candidate.astimezone(timezone.utc).astimezone(tz).replace(fold=0)!=candidate:continue
        if candidate>=local:return candidate
    raise WorkflowError('invalid_schedule_time',422)

def settings_payload():
    cfg,public=configuration();s=scheduling_settings()
    allowed=dict(preview=flag('WEB_PREVIEW_ENABLED'),persistence=flag('WEB_WRITES_ENABLED') and cfg.enabled,
                 scheduling=flag('SCHEDULING_ENABLED') and flag('WEB_WRITES_ENABLED') and cfg.enabled)
    return dict(provider='Seerr',effective=public,editable_schedule=s,capabilities=allowed,
        controls_read_only=['provider credentials','source identity','discovery scope defaults','metadata policy','API limits'],
        next_executions={op:next_slot(op,s) if allowed['scheduling'] and s[f'discovery.{op}.enabled'] else None for op in ('daily','sweep','refresh')},
        precedence='Private provider file, overridden by process environment, owns ingestion configuration. UI app_settings owns scheduling intent only. Manual request may narrow instance limits. Server feature gates cannot be enabled through settings.')

def update_settings(updates,user):
    if not flag('SCHEDULING_ENABLED'):raise WorkflowError('scheduling_management_disabled',403)
    if any(k not in SCHEDULE_KEYS for k in updates):raise WorkflowError('setting_not_editable',422)
    for k,v in updates.items():
        try:parse_value(SETTINGS_BY_KEY[k],v)
        except ValueError:raise WorkflowError('invalid_schedule_setting',422) from None
    save_settings(updates=updates,clear_keys=[],updated_by=user)

def plan(request):
    cfg,_=configuration(request);scopes=build_scopes(cfg,start=request.start,end=request.end)
    if len(scopes)>128:raise WorkflowError('too_many_query_scopes_stage_date_ranges',422)
    with reader() as cur:
        cur.execute('SELECT count(*) AS count FROM public.seerr_discovered_titles WHERE media_type=ANY(%s) AND premiere_date BETWEEN %s AND %s',(request.media_types,request.start,request.end))
        known=cur.fetchone()['count']
    return dict(scopes=[dict(media_type=s.media_type,scope_key=s.key,query=s.parameters) for s in scopes],
        known_inventory_matches=known,estimated_HTTP=None,
        workload_note='Known inventory is not an upstream result count. Unknown new titles prevent a reliable HTTP estimate. Each scope has a page ceiling; the request budget covers all scopes and details.',
        max_pages=cfg.max_pages,max_requests=cfg.max_requests,timeout=cfg.timeout,retries=cfg.retries,
        persist=request.persist,confirmation_required=request.persist,cache_enabled=cfg.cache_enabled)

def _active_external_process():
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:args=(path/'cmdline').read_bytes().split(b'\0')
        except (OSError,PermissionError):continue
        if any(a.decode(errors='replace').split('/')[-1] in pipeline.PIPELINE_PROCESS_MARKERS for a in args):return True
    return False

def _check_gate(request,cfg,operation):
    if request.persist:
        if not flag('WEB_WRITES_ENABLED') or not cfg.enabled:raise WorkflowError('persistence_disabled',403)
        if not request.confirmed:raise WorkflowError('explicit_confirmation_required',422)
        cfg.require_source_identity()
    elif not flag('WEB_PREVIEW_ENABLED'):raise WorkflowError('preview_disabled',403)
    if operation not in ('manual','daily','sweep','refresh'):raise WorkflowError('invalid_operation',422)

def _update_job(run_id,*,status=None,note=None):
    with pipeline._pipeline_connection() as c:
        with c.cursor() as cur:
            cur.execute('''UPDATE public.pipeline_runs SET last_heartbeat_at=now(),notes=%s,
            status=COALESCE(%s,status),completed_at=CASE WHEN %s IS NULL THEN completed_at ELSE now() END
            WHERE run_id=%s''',(json.dumps(note or {},default=str),status,status,run_id))

@contextmanager
def _submission_transaction():
    locks=[]
    try:
        with pipeline._pipeline_connection() as conn:yield conn,locks
    except BaseException:
        for lock in locks:lock.release()
        raise

def submit(request,user,*,operation='manual',schedule_key=None):
    cfg,_=configuration(request);_check_gate(request,cfg,operation)
    # Config validation, including language syntax, before jobs/threads/network.
    scopes=[] if operation=='refresh' else build_scopes(cfg,start=request.start,end=request.end)
    if len(scopes)>128:raise WorkflowError('too_many_query_scopes_stage_date_ranges',422)
    key=schedule_key or 'discovery:request:'+str(request.request_id)
    lock=None
    with _submission_transaction() as (c,held_locks):
        with c.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='5s'")
            cur.execute("SET LOCAL lock_timeout='2s'")
            cur.execute('SELECT pg_advisory_xact_lock(184725,31)')
            cur.execute('SELECT run_id,status,notes,triggered_by FROM public.pipeline_runs WHERE schedule_key=%s ORDER BY run_id LIMIT 1',(key,))
            old=cur.fetchone()
            if old:
                stored=json.loads(old['notes'] or '{}')
                if stored.get('request')!=request.model_dump(mode='json') or old['triggered_by']!=user:
                    raise WorkflowError('idempotency_key_scope_conflict')
                return dict(job_id=old['run_id'],status=old['status'],duplicate=True)
            cur.execute("SELECT 1 FROM public.pipeline_runs WHERE status IN ('started','cancel_requested') LIMIT 1")
            if cur.fetchone() or _active_external_process():raise WorkflowError('resource_intensive_pipeline_active')
            lock=pipeline.try_acquire_pipeline_lock(source='content-discovery')
            if lock is None:raise WorkflowError('resource_intensive_pipeline_locked')
            held_locks.append(lock)
            try:
                # Refuse unexpected orphaned writer state; do not use web UI to
                # authorize historical recovery implicitly.
                cur.execute("SELECT 1 FROM public.seerr_discovery_runs WHERE status='running' LIMIT 1")
                if cur.fetchone():raise WorkflowError('discovery_recovery_review_required')
                cur.execute("SELECT pid FROM pg_locks WHERE locktype='advisory' AND classid=184725 AND objid=30 AND database=(SELECT oid FROM pg_database WHERE datname=current_database())")
                if cur.fetchone():raise WorkflowError('discovery_already_running')
                cur.execute('''INSERT INTO public.pipeline_runs(delivery_type,schedule_key,triggered_by,status,notes,current_stage_key)
                VALUES(%s,%s,%s,'started',%s,'content_discovery') RETURNING run_id''',
                (PREFIX+('persist' if request.persist else 'preview'),key,user,json.dumps(dict(request=request.model_dump(mode='json'),operation=operation))))
                job_id=cur.fetchone()['run_id']
            except Exception:
                lock.release();raise
    def worker():
        conn=None
        try:
            current,_=configuration(request);_check_gate(request,current,operation)
            note=dict(request=request.model_dump(mode='json'),operation=operation)
            def progress(event):
                note.update(progress=event);_update_job(job_id,note=note)
            if request.persist:conn=connect_db()
            result=sync_discovery(SeerrClient(current),current,scopes,repository=DiscoveryRepository(conn) if conn else None,
                                 dry_run=not request.persist,enrich_due=operation=='refresh',log=progress)
            # Keep bounded accounting, not potentially huge title/pagination JSON,
            # in shared pipeline notes. Canonical run remains authoritative.
            note.update(discovery_run_id=result['run_id'] if request.persist else None,
                result={k:result.get(k) for k in ('run_id','dry_run','status','counts','discovery_complete','enrichment_complete')},
                errors=result.get('errors',[])[:20],warnings=result.get('warnings',[])[:20],
                scope_results=[{k:(p.get(k,[])[:10] if k=='errors' else p.get(k)) for k in ('scope_key','media_type','reported_total','expected_pages','unique_titles','complete','errors')} for p in result.get('pagination',[])][:128])
            _update_job(job_id,status=result['status'],note=note)
            pipeline._log_run_event(job_id,'Content discovery completed status='+result['status'])
        except Exception:
            try:
                _update_job(job_id,status='failed',note=dict(request=request.model_dump(mode='json'),operation=operation,error='discovery_job_failed_inspect_canonical_history'))
            except Exception:
                # Database failure can leave a started job. Preserve uncertainty;
                # never leak a driver exception or pretend durable finalization.
                print('Content discovery job finalization unavailable; operator review required.')
        finally:
            if conn:conn.close()
            lock.release()
    thread=Thread(target=worker,daemon=True,name=f'content-discovery-{job_id}')
    try:thread.start()
    except Exception:
        lock.release();_update_job(job_id,status='failed',note=dict(error='worker_start_failed',request=request.model_dump(mode='json')));raise WorkflowError('worker_start_failed',503) from None
    return dict(job_id=job_id,status='started',duplicate=False)

def jobs(job_id=None,page=1,limit=25):
    with reader() as cur:
        args=[PREFIX+'%'];where='delivery_type LIKE %s'
        if job_id is not None:where+=' AND run_id=%s';args.append(job_id)
        cur.execute(f'SELECT count(*) AS total FROM public.pipeline_runs WHERE {where}',args);total=cur.fetchone()['total']
        cur.execute(f'''SELECT run_id AS job_id,status,started_at,completed_at,last_heartbeat_at,triggered_by,notes
        FROM public.pipeline_runs WHERE {where} ORDER BY started_at DESC,run_id DESC LIMIT %s OFFSET %s''',[*args,limit,(page-1)*limit])
        items=[]
        for row in cur.fetchall():
            item=dict(row)
            try:item['details']=json.loads(item.pop('notes') or '{}')
            except ValueError:item['details']={}
            item['stale']=item['status']=='started' and (not item['last_heartbeat_at'] or (datetime.now(timezone.utc)-item['last_heartbeat_at']).total_seconds()>300)
            items.append(item)
        return dict(items=items,total=total,page=page,limit=limit)

def run_scheduled_discovery(now=None):
    # Called by the EXISTING scheduler loop; no DB/config access while disabled.
    if not flag('SCHEDULING_ENABLED') or not flag('WEB_WRITES_ENABLED'):return dict(status='disabled')
    cfg,_=configuration()
    if not cfg.enabled:return dict(status='disabled')
    s=scheduling_settings();now=now or datetime.now(timezone.utc);local=now.astimezone(ZoneInfo(s['discovery.timezone']))
    for op in ('daily','sweep','refresh'):
        if not s[f'discovery.{op}.enabled']:continue
        # Five-minute window; do not backfill missed schedules or partial runs.
        slot=next_slot(op,s,now-timedelta(minutes=5))
        if not slot<=local<=slot+timedelta(minutes=5):continue
        anchor=now.astimezone(timezone.utc).date()
        request=Execution(request_id=uuid4(),start=anchor-timedelta(days=s['discovery.sweep.lookback'] if op=='sweep' else cfg.lookback_days),
            end=anchor+timedelta(days=s['discovery.sweep.lookahead'] if op=='sweep' else cfg.lookahead_days),
            media_types=['movie','tv'],languages=list(cfg.languages),max_pages=cfg.max_pages,max_requests=min(cfg.max_requests,10000),persist=True,confirmed=True)
        key=f'discovery:{op}:{slot.date()}:{s["discovery."+op+".time"]}:{s["discovery.timezone"]}'
        # Deterministic request ID allows repeated scheduler polls to return the
        # same terminal/partial job without resubmission.
        from uuid import uuid5,NAMESPACE_URL
        request.request_id=uuid5(NAMESPACE_URL,key)
        try:return submit(request,'app-scheduler',operation=op,schedule_key=key)
        except WorkflowError as e:return dict(status='blocked',code=e.code)
    return dict(status='not_due')
