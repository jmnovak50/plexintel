"""Workspace regressions. Network mocked; SQL tests refuse non-fixture targets."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import date,datetime,timezone,timedelta
import json,os
from unittest.mock import Mock
from uuid import uuid4
import pytest,psycopg2,requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.routes import discovery_admin_routes as routes
from api.routes.admin_routes import require_admin
from api.services import discovery_workspace as ws,discovery_workflow as wf,pipeline_service as pipeline
from api.services.app_settings import parse_value,SETTINGS_BY_KEY
from api.services import app_settings
from api.db.seerr_discovery import DiscoveryRepository
from api.services.seerr_discovery import sync_discovery,build_scopes
from tests.test_seerr_discovery import database,database_v1,CFG,NOW,movie
from tests.test_seerr_unified_discovery import UnifiedClient,tv,summary

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    actual_connect=psycopg2.connect
    def guarded_connect(dsn=None,**kwargs):
        from psycopg2.extensions import parse_dsn
        parsed=parse_dsn(dsn or '')
        parsed.update({k:str(v) for k,v in kwargs.items() if k in ('host','port','dbname','user')})
        assert parsed.get('dbname')=='plexintel_seerr_fixture' and parsed.get('host','').startswith('/tmp/plexintel-seerr-fixture.'),'Refusing any non-fixture database connection'
        return actual_connect(dsn,**kwargs)
    monkeypatch.setattr(psycopg2,'connect',guarded_connect)
    monkeypatch.setattr(requests.sessions.Session,'request',Mock(side_effect=AssertionError('No live HTTP')))
    for key in ('WEB_PREVIEW_ENABLED','WEB_WRITES_ENABLED','SCHEDULING_ENABLED'):monkeypatch.delenv('SEERR_DISCOVERY_'+key,raising=False)
    for module in (ws,wf,pipeline,app_settings):
        monkeypatch.setattr(module,'connect_db',Mock(side_effect=AssertionError('Database connection requires guarded fixture')))

@pytest.fixture
def client():
    app=FastAPI();app.include_router(routes.router,prefix='/api')
    app.dependency_overrides[require_admin]=lambda:{'username':'admin','is_admin':True}
    return TestClient(app)

@pytest.fixture
def config(monkeypatch):
    cfg=replace(CFG,enabled=False,media_types=('movie','tv'),max_requests=1000,retries=0)
    monkeypatch.setattr(ws,'load_seerr_config',lambda:cfg)
    return cfg

def execution(**kwargs):
    return wf.Execution(request_id=uuid4(),start='2026-10-26',end='2026-11-01',**kwargs)

HEADERS={'Origin':'http://testserver','X-Discovery-Action':'1'}

@pytest.mark.parametrize('path',['/overview','/titles','/titles/movie/1','/runs','/settings','/jobs'])
def test_read_endpoints_require_session_admin(path):
    app=FastAPI();app.include_router(routes.router,prefix='/api')
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware,secret_key='test-only-secret')
    assert TestClient(app).get('/api/admin/discovery'+path).status_code==401
    assert all(any(d.call is require_admin for d in r.dependant.dependencies) for r in routes.router.routes)
    # Dependency calls retain real non-admin rejection semantics.
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:require_admin(user={'is_admin':False})
    assert e.value.status_code==403

@pytest.mark.parametrize('headers',[{}, {'Origin':'https://evil.invalid','X-Discovery-Action':'1'}, {'Origin':'http://testserver'}, {'Origin':'http://testserver','X-Discovery-Action':'1','Sec-Fetch-Site':'cross-site'}])
def test_mutations_require_origin_and_action_header(client,headers):
    assert client.post('/api/admin/discovery/jobs',json=execution().model_dump(mode='json'),headers=headers).status_code==403

def test_disabled_jobs_never_open_DB_or_spawn(client,config,monkeypatch):
    acquire=Mock(side_effect=AssertionError('No lock/DB'));monkeypatch.setattr(pipeline,'_pipeline_connection',acquire)
    thread=Mock();monkeypatch.setattr(wf,'Thread',thread)
    for persist in (False,True):
        r=client.post('/api/admin/discovery/jobs',json=execution(persist=persist,confirmed=True).model_dump(mode='json'),headers=HEADERS)
        assert r.status_code==403
    assert not acquire.called and not thread.called

@pytest.mark.parametrize('changes',[{'start':'2026-11-02','end':'2026-10-26'}, {'media_types':['movie','movie']}, {'media_types':['season']},{'languages':['all','all']},{'max_requests':10001},{'unexpected':'a'}])
def test_manual_parameters_rejected(client,changes):
    body=execution().model_dump(mode='json')|changes
    assert client.post('/api/admin/discovery/jobs',json=body,headers=HEADERS).status_code==422

def test_instance_limits_and_language_syntax(config):
    with pytest.raises(wf.WorkflowError):wf.configuration(execution(max_requests=1001))
    with pytest.raises(wf.WorkflowError):wf.configuration(execution(languages=['en;curl']))

def test_config_never_exposes_credentials(config):
    cfg,public=ws.effective_config();text=json.dumps(public)
    assert cfg.api_key not in text and cfg.url not in text and 'api_key' not in public and 'url' not in public

def test_scheduler_disabled_without_config_or_DB(monkeypatch):
    monkeypatch.setattr(wf,'configuration',Mock(side_effect=AssertionError('No config/DB')))
    assert wf.run_scheduled_discovery()=={'status':'disabled'}

@pytest.mark.parametrize('key,value',[('discovery.timezone','invalid/zone'),('discovery.daily.time','25:00'),('discovery.sweep.day',7),('discovery.sweep.lookback',-1)])
def test_schedule_setting_validation(key,value):
    with pytest.raises(ValueError):parse_value(SETTINGS_BY_KEY[key],value)

def settings(**changes):
    return {k:d.default for k,d in SETTINGS_BY_KEY.items() if k in wf.SCHEDULE_KEYS}|changes

def test_schedule_defaults_and_DST():
    s=settings(**{'discovery.timezone':'America/Chicago','discovery.daily.time':'02:30'})
    assert not any(s[f'discovery.{op}.enabled'] for op in ('daily','sweep','refresh'))
    # Spring gap skipped, no two executions in the repeated autumn wall hour.
    slot=wf.next_slot('daily',s,datetime(2026,3,8,6,tzinfo=timezone.utc))
    assert slot.date()==date(2026,3,9)
    s['discovery.daily.time']='01:30'
    early=wf.next_slot('daily',s,datetime(2026,11,1,5,tzinfo=timezone.utc))
    assert early.fold==0

@pytest.fixture
def seeded(database,monkeypatch,tmp_path):
    cfg=replace(CFG,media_types=('movie','tv'),retries=0)
    rawmovie=movie(1,title='Alpha Movie',runtime=None)
    rawtv=tv(1,name='Beta Series',seasons=[])
    source=UnifiedClient(movies=[rawmovie],television=[summary(rawtv)],details={('movie',1):rawmovie,('tv',1):rawtv})
    result=sync_discovery(source,cfg,build_scopes(cfg,start=date(2026,10,26),end=date(2026,11,1)),repository=DiscoveryRepository(database),dry_run=False,clock=lambda:NOW)
    assert result['status']=='success'
    with database:
        with database.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS app_settings(key text PRIMARY KEY,raw_value text,source text NOT NULL,updated_at timestamptz DEFAULT now(),updated_by text,description text);
            CREATE TABLE IF NOT EXISTS pipeline_runs(run_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,delivery_type text,schedule_key text,triggered_by text,status text,notes text,started_at timestamptz DEFAULT now(),completed_at timestamptz,last_heartbeat_at timestamptz,current_stage_key text,current_pid integer,cancel_requested_at timestamptz,cancel_requested_by text);
            TRUNCATE app_settings,pipeline_runs RESTART IDENTITY;''')
    def connect(**kw):return psycopg2.connect(os.environ['SEERR_DISCOVERY_TEST_DSN'],**kw)
    monkeypatch.setattr(ws,'connect_db',connect);monkeypatch.setattr(wf,'connect_db',connect);monkeypatch.setattr(pipeline,'connect_db',connect);monkeypatch.setattr(app_settings,'connect_db',connect)
    monkeypatch.setattr(ws,'load_seerr_config',lambda:replace(cfg,enabled=False))
    monkeypatch.setenv('PIPELINE_LOCK_PATH',str(tmp_path/'pipeline.lock'))
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    monkeypatch.setattr(wf,'_active_external_process',lambda:False)
    return cfg,database,result

def test_inventory_filtering_pagination_typed_identity_and_literal_search(seeded):
    assert ws.inventory()['total']==2
    page=ws.inventory(limit=1,sort='title',direction='asc');assert page['items'][0]['title']=='Alpha Movie'
    assert len(page['items'])==1 and page['total']==2
    assert ws.inventory(media_type='tv')['items'][0]['tmdb_id']==1
    assert ws.inventory(search='ALPHA')['total']==1
    assert ws.inventory(search='%')['total']==0
    assert ws.inventory(language='ja')['total']==1
    assert ws.inventory(media_state='requests_unknown')['total']==2
    assert ws.inventory(media_state='requested')['total']==0
    assert ws.inventory(classification='provisional')['total']==1
    assert ws.inventory(release_from=date(2027,1,1))['total']==0
    assert ws.inventory(discovered_from=NOW+timedelta(seconds=1))['total']==0

def test_read_views_no_mutation_raw_json_or_status_coercion(seeded):
    _,db,result=seeded
    with db.cursor() as cur:
        cur.execute('SELECT to_jsonb(o) FROM seerr_discovery_observations o ORDER BY observation_id');before=cur.fetchall()
    t=ws.title('movie',1);v=ws.title('tv',1)
    assert t['runtime'] is None and t['media_status'] is None and t['media_state']['request_count'] is None
    assert 'source_metadata' not in t and 'source_diagnostics' not in t
    assert 'source_diagnostics' in ws.title('movie',1,diagnostics=True)
    assert v['classification']['state']=='provisional' and v['tv_metadata']['season_numbers']==[]
    assert len(t['history']['items'])==1 and t['first_discovery_run_id']==result['run_id']
    run=ws.run_detail(result['run_id'],limit=1);assert len(run['memberships']['items'])==1 and run['memberships']['total']==2
    o=ws.overview();assert o['inventory']['movies']==o['inventory']['tv']==1 and o['tv_classification']['provisional']==1
    with db.cursor() as cur:
        cur.execute('SELECT to_jsonb(o) FROM seerr_discovery_observations o ORDER BY observation_id');assert cur.fetchall()==before

def test_partial_run_is_not_last_complete(seeded):
    _,db,result=seeded
    with db:
        with db.cursor() as cur:cur.execute("UPDATE seerr_discovery_runs SET status='partial',discovery_complete=false WHERE run_id=%s",(result['run_id'],))
    o=ws.overview();assert o['latest_run']['status']=='partial' and o['last_complete_discovery'] is None

def test_api_filters_details_and_not_found(client,seeded):
    assert client.get('/api/admin/discovery/titles?limit=1').json()['total']==2
    assert client.get('/api/admin/discovery/titles/tv/1').json()['media_type']=='tv'
    assert client.get('/api/admin/discovery/titles/movie/99').status_code==404
    assert client.get('/api/admin/discovery/titles?discovered_from=2026-10-01T00:00:00').status_code==422
    assert client.get('/api/admin/discovery/titles?sort=title;DELETE').status_code==422

def test_preview_plan_has_no_HTTP_and_no_job(seeded):
    p=wf.plan(execution());assert p['estimated_HTTP'] is None and p['known_inventory_matches']==2 and len(p['scopes'])==2
    assert wf.jobs()['total']==0
    assert wf.settings_payload()['capabilities']==dict(preview=False,persistence=False,scheduling=False)

def test_background_submission_duplicate_and_scope_conflict(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    thread=Mock();monkeypatch.setattr(wf,'Thread',thread)
    req=execution();first=wf.submit(req,'admin');again=wf.submit(req,'admin')
    assert first['job_id']==again['job_id'] and again['duplicate'] and thread.call_count==1
    with pytest.raises(wf.WorkflowError,match='idempotency_key_scope_conflict'):
        wf.submit(req.model_copy(update={'languages':['en']}),'admin')
    # Release the test's deliberately unstarted worker lock.
    target=thread.call_args.kwargs['target']
    dict(zip(target.__code__.co_freevars,[c.cell_contents for c in target.__closure__]))['lock'].release()

def test_existing_pipeline_blocks_discovery(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    with seeded[1]:
        with seeded[1].cursor() as cur:cur.execute("INSERT INTO pipeline_runs(delivery_type,status) VALUES('scheduled','started')")
    with pytest.raises(wf.WorkflowError,match='resource_intensive_pipeline_active'):wf.submit(execution(),'admin')

def test_preview_worker_uses_discovery_only_and_preserves_canonical(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    monkeypatch.setattr(wf,'SeerrClient',lambda cfg:UnifiedClient())
    class Inline:
        def __init__(self,**kw):self.worker=kw['target']
        def start(self):self.worker()
    monkeypatch.setattr(wf,'Thread',Inline)
    before=ws.overview()['inventory']['total'];job=wf.submit(execution(),'admin')
    row=wf.jobs(job['job_id'])['items'][0]
    assert row['status']=='success' and row['details']['result']['dry_run'] and row['details']['discovery_run_id'] is None
    assert ws.overview()['inventory']['total']==before
    assert wf.jobs()['total']==1

def test_manual_persistence_requires_flag_instance_and_confirmation(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_WRITES_ENABLED','true')
    with pytest.raises(wf.WorkflowError,match='persistence_disabled'):wf.submit(execution(persist=True,confirmed=True),'admin')
    cfg=seeded[0];monkeypatch.setattr(ws,'load_seerr_config',lambda:cfg)
    with pytest.raises(wf.WorkflowError,match='explicit_confirmation_required'):wf.submit(execution(persist=True),'admin')

def test_settings_write_allowlist_and_gates(seeded,monkeypatch):
    with pytest.raises(wf.WorkflowError):wf.update_settings({'discovery.daily.enabled':True},'admin')
    monkeypatch.setenv('SEERR_DISCOVERY_SCHEDULING_ENABLED','true')
    with pytest.raises(wf.WorkflowError):wf.update_settings({'SEERR_API_KEY':'no'},'admin')
    wf.update_settings({'discovery.daily.time':'13:00','discovery.daily.enabled':True},'admin')
    assert wf.scheduling_settings()['discovery.daily.time']=='13:00'
    assert wf.settings_payload()['capabilities']['scheduling'] is False

def test_guard_refuses_production_DSN_before_connect():
    with pytest.raises(AssertionError,match='non-fixture'):
        psycopg2.connect('host=production.invalid dbname=plexintel')

def test_concurrent_same_key_creates_one_job(seeded,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    thread=Mock();monkeypatch.setattr(wf,'Thread',thread)
    request=execution()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:wf.submit(request,'admin'),range(2)))
    assert results[0]['job_id']==results[1]['job_id'] and sum(r['duplicate'] for r in results)==1 and thread.call_count==1
    target=thread.call_args.kwargs['target']
    dict(zip(target.__code__.co_freevars,[c.cell_contents for c in target.__closure__]))['lock'].release()

def test_existing_shared_resource_lock_blocks_discovery(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    lock=pipeline.try_acquire_pipeline_lock(source='isolated-ML-test')
    try:
        with pytest.raises(wf.WorkflowError,match='resource_intensive_pipeline_locked'):wf.submit(execution(),'admin')
    finally:lock.release()
    assert wf.jobs()['total']==0

def test_external_model_process_blocks_without_new_job(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    monkeypatch.setattr(wf,'_active_external_process',lambda:True)
    with pytest.raises(wf.WorkflowError,match='resource_intensive_pipeline_active'):wf.submit(execution(),'admin')
    assert wf.jobs()['total']==0

def test_scheduled_slots_are_idempotent_and_do_not_retry_partial(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_WRITES_ENABLED','true');monkeypatch.setenv('SEERR_DISCOVERY_SCHEDULING_ENABLED','true')
    monkeypatch.setattr(ws,'load_seerr_config',lambda:seeded[0])
    monkeypatch.setattr(wf,'scheduling_settings',lambda:settings(**{'discovery.daily.enabled':True}))
    thread=Mock();monkeypatch.setattr(wf,'Thread',thread)
    now=datetime(2026,10,29,9,1,tzinfo=timezone.utc)
    first=wf.run_scheduled_discovery(now);assert first['status']=='started'
    with seeded[1]:
        with seeded[1].cursor() as cur:cur.execute("UPDATE pipeline_runs SET status='partial' WHERE run_id=%s",(first['job_id'],))
    again=wf.run_scheduled_discovery(now+timedelta(seconds=60))
    assert again['duplicate'] and again['status']=='partial' and thread.call_count==1
    target=thread.call_args.kwargs['target']
    dict(zip(target.__code__.co_freevars,[c.cell_contents for c in target.__closure__]))['lock'].release()

def test_schedule_outside_grace_window_does_not_catch_up(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_WRITES_ENABLED','true');monkeypatch.setenv('SEERR_DISCOVERY_SCHEDULING_ENABLED','true')
    monkeypatch.setattr(ws,'load_seerr_config',lambda:seeded[0]);monkeypatch.setattr(wf,'scheduling_settings',lambda:settings(**{'discovery.daily.enabled':True}))
    assert wf.run_scheduled_discovery(datetime(2026,10,29,10,tzinfo=timezone.utc))=={'status':'not_due'}
    assert wf.jobs()['total']==0

def test_isolated_persistence_reuses_canonical_service_without_ML(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_WRITES_ENABLED','true');monkeypatch.setattr(ws,'load_seerr_config',lambda:seeded[0])
    monkeypatch.setattr(wf,'SeerrClient',lambda cfg:UnifiedClient(movies=[movie(2)],television=[summary(tv(2))]))
    class Inline:
        def __init__(self,**kwargs):self.worker=kwargs['target']
        def start(self):self.worker()
    monkeypatch.setattr(wf,'Thread',Inline)
    job=wf.submit(execution(persist=True,confirmed=True),'admin');row=wf.jobs(job['job_id'])['items'][0]
    assert row['status']=='success' and row['details']['discovery_run_id']
    assert ws.overview()['inventory']['total']==4
    assert ws.title('movie',1)['title']=='Alpha Movie' and ws.title('tv',1)['title']=='Beta Series'

def test_abandoned_discovery_requires_explicit_recovery_review(seeded,monkeypatch):
    monkeypatch.setenv('SEERR_DISCOVERY_WEB_PREVIEW_ENABLED','true')
    with seeded[1]:
        with seeded[1].cursor() as cur:cur.execute("UPDATE seerr_discovery_runs SET status='running',completed_at=NULL")
    with pytest.raises(wf.WorkflowError,match='discovery_recovery_review_required'):wf.submit(execution(),'admin')
    assert wf.jobs()['total']==0

def test_ML_cancellation_cannot_falsely_cancel_discovery(seeded):
    with seeded[1]:
        with seeded[1].cursor() as cur:
            cur.execute("INSERT INTO pipeline_runs(delivery_type,status) VALUES('content_discovery_preview','started') RETURNING run_id");ident=cur.fetchone()[0]
    assert pipeline.request_pipeline_cancel(run_id=ident,requested_by='admin')['status']=='independent_workflow'
    assert wf.jobs(ident)['items'][0]['status']=='started'

def test_poster_path_rejects_external_urls_and_traversal(seeded):
    db=seeded[1]
    for path in ('https://evil.invalid/a.jpg','/../secret.jpg','//evil.invalid/x.png','/safe.jpg'):
        with db:
            with db.cursor() as cur:cur.execute("UPDATE seerr_discovered_titles SET source_metadata=jsonb_set(source_metadata,'{detail,posterPath}',%s::jsonb) WHERE media_type='movie'",(json.dumps(path),))
        assert ws.poster_path('movie',1)==('/safe.jpg' if path=='/safe.jpg' else None)
