"""Conservative policy contracts and disposable PostgreSQL lifecycle tests."""
from copy import deepcopy
import os
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extensions import parse_dsn
import pytest
from starlette.middleware.sessions import SessionMiddleware

from api.routes import eligibility_admin_routes as routes
from api.routes.admin_routes import require_admin
from api.services import eligibility_workspace as ws
from api.services.global_eligibility import Policy, RULE_IDS, digest, evaluate, summarize
from tests.test_seerr_discovery import database, database_v1, sync, FixtureClient, movie
from tests.test_seerr_unified_discovery import UnifiedClient, tv, summary
from api.db.seerr_discovery import DiscoveryRepository
from api.services.seerr_discovery import sync_discovery, build_scopes
from tests.test_seerr_discovery import CFG, NOW
from dataclasses import replace
from datetime import date

MIGRATION = Path(__file__).parents[1]/'api/db/migrations/optional/global_eligibility/001_initial.sql'
HEADERS = {'Origin':'http://testserver','X-Eligibility-Action':'1'}


@pytest.fixture(autouse=True)
def guard(monkeypatch):
    actual = psycopg2.connect
    def connect(dsn=None, **kwargs):
        params = parse_dsn(dsn or '') | {k:str(v) for k,v in kwargs.items() if k in ('host','dbname','port')}
        assert params.get('dbname')=='plexintel_seerr_fixture' and params.get('host','').startswith('/tmp/plexintel-seerr-fixture.'), 'Non-fixture DB forbidden'
        return actual(dsn, **kwargs)
    monkeypatch.setattr(psycopg2, 'connect', connect)
    monkeypatch.setattr(ws, 'connect_db', Mock(side_effect=AssertionError('Fixture required')))
    monkeypatch.delenv('GLOBAL_ELIGIBILITY_WRITES_ENABLED', raising=False)
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request', Mock(side_effect=AssertionError('No HTTP')))


def title(**changes):
    return dict(media_type='movie',tmdb_id=1,title='Fixture',runtime=90,original_language='en',genres=[{'id':18}]) | changes


def changed_policy(key, **updates):
    p = Policy().model_dump()
    p['rules'][key].update(updates)
    return Policy.model_validate(p)


@pytest.mark.parametrize('runtime,outcome',[(1,'excluded'),(59,'excluded'),(60,'retained'),(61,'retained'),(None,'retained'),(0,'retained'),(-1,'retained'),('30','retained'),(False,'retained')])
def test_short_movie_boundary_and_unknown(runtime,outcome):
    row = evaluate(title(runtime=runtime), Policy())
    assert row['outcome']==outcome
    if runtime in (None,0,-1,'30',False):
        assert any(u['code']=='short_movie_evidence_unknown' for u in row['uncertainties'])


def test_tv_episode_runtime_not_a_short_movie():
    row = evaluate(title(media_type='tv',runtime=20),Policy())
    assert row['outcome']=='retained'
    assert row['rule_outcomes'][0]['state']=='not_applicable'


def test_retain_categories_never_override_runtime():
    row = evaluate(title(runtime=30,genres=[{'id':99},{'id':10770}],original_language='ja'),Policy())
    assert [r['rule_id'] for r in row['reasons']]==['short_movie']
    assert all(r['action']=='retain' for r in row['rule_outcomes'] if r['rule_id'] in ('documentary','tv_movie','foreign_language'))


def test_sporting_names_keywords_and_music_not_definitive():
    row = evaluate(title(title='World Cup Boxing Final Stand Up Concert',genres=[{'name':'Sports'},{'id':10402}],keywords=['sport']),Policy())
    assert row['outcome']=='retained'
    assert any(u['rule_id']=='recorded_sport' for u in row['uncertainties'])


def test_confirmed_sports_exclusion_typed_and_audited():
    p = changed_policy('recorded_sport',confirmed_titles=[dict(media_type='movie',tmdb_id=1,evidence='Operator verified event recording, source reference ABC')])
    row = evaluate(title(),p)
    assert row['reasons'][0]['evidence']['source']=='policy_confirmation'
    assert row['outcome']=='excluded'
    assert evaluate(title(media_type='tv'),p)['outcome']=='retained'


@pytest.mark.parametrize('key',RULE_IDS)
def test_each_rule_independently_configurable(key):
    p = Policy().model_dump()
    for r in p['rules'].values():r['enabled']=False
    p['rules'][key].update(enabled=True,action='exclude')
    t = title(runtime=20,original_language='ja',genres=[{'id':99},{'id':10770}])
    if key in ('recorded_sport','standup','concert'):
        p['rules'][key]['confirmed_titles']=[dict(media_type='movie',tmdb_id=1,evidence='Verified source XYZ')]
    row = evaluate(t,Policy.model_validate(p))
    assert [r['rule_id'] for r in row['reasons']]==[key]
    p['rules'][key]['action']='retain'
    assert evaluate(t,Policy.model_validate(p))['outcome']=='retained'


def test_all_matching_reasons_preserved_repeatable_no_mutation():
    t = title(runtime=20,genres=[{'id':99}]); original = deepcopy(t)
    p = changed_policy('documentary',action='exclude')
    a,b = evaluate(t,p),evaluate(t,p)
    assert a==b and t==original
    assert len(a['reasons'])==2
    s = summarize([a,evaluate(title(media_type='tv'),p)])
    assert s['counts']['total']==s['counts']['retained']+s['counts']['excluded']==2
    assert sum(s['exclusion_reasons'].values())==2


@pytest.mark.parametrize('changes',[
    {'minimum_movie_minutes':0},{'minimum_movie_minutes':True},{'minimum_movie_minutes':'60'},
    {'local_languages':[]},{'local_languages':['EN']},{'local_languages':['en','en']},
    {'local_languages':['en;drop']},{'rules':{}},{'unexpected':True},
])
def test_invalid_policy(changes):
    with pytest.raises(ValueError):Policy.model_validate(Policy().model_dump() | changes)


def test_policy_rejects_bad_or_duplicate_confirmations():
    c = dict(media_type='movie',tmdb_id=1,evidence='Known recording')
    with pytest.raises(ValueError):changed_policy('recorded_sport',confirmed_titles=[c,c])
    with pytest.raises(ValueError):changed_policy('short_movie',confirmed_titles=[c])
    with pytest.raises(ValueError):changed_policy('recorded_sport',confirmed_titles=[c|{'tmdb_id':True}])
    with pytest.raises(ValueError):changed_policy('recorded_sport',confirmed_titles=[c|{'evidence':'      '}])


@pytest.mark.parametrize('language',[None,'','??','EN','und','zxx','xx',True])
def test_uncertain_language_never_excludes(language):
    p = changed_policy('foreign_language',action='exclude')
    row = evaluate(title(original_language=language),p)
    assert row['outcome']=='retained'
    assert any(u['rule_id']=='foreign_language' for u in row['uncertainties'])


def test_comparison_new_changed_and_removed():
    a = evaluate(title(),Policy());b = evaluate(title(runtime=20),Policy())
    delta = ws.compare([a],[b,evaluate(title(tmdb_id=2),Policy())])
    assert delta['retained_to_excluded']==1 and delta['added']==1
    assert ws.compare([a],[])['no_longer_in_inventory']==1
    assert ws.compare([b],[a])['excluded_to_retained']==1


@pytest.fixture
def client():
    app = FastAPI();app.include_router(routes.router,prefix='/api')
    app.dependency_overrides[require_admin] = lambda:dict(username='admin',is_admin=True)
    return TestClient(app)


@pytest.mark.parametrize('path',['overview','policy','evaluations','results'])
def test_reads_require_admin(path):
    app = FastAPI();app.include_router(routes.router,prefix='/api')
    app.add_middleware(SessionMiddleware,secret_key='isolated-fixture-secret')
    assert TestClient(app).get('/api/admin/eligibility/'+path).status_code==401
    app.dependency_overrides[require_admin] = lambda:require_admin(user={'is_admin':False})
    assert TestClient(app).get('/api/admin/eligibility/'+path).status_code==403


@pytest.mark.parametrize('headers',[{}, {'Origin':'https://evil.invalid','X-Eligibility-Action':'1'}, {'Origin':'http://testserver'}, HEADERS|{'Sec-Fetch-Site':'cross-site'}])
def test_actions_reject_csrf(client,headers):
    assert client.post('/api/admin/eligibility/preview',json=Policy().model_dump(),headers=headers).status_code==403


def test_disabled_write_before_connection(client):
    assert client.post('/api/admin/eligibility/evaluations',json={'expected_version':0},headers=HEADERS).status_code==403
    assert client.put('/api/admin/eligibility/policy',json={'expected_version':0,'policy':Policy().model_dump()},headers=HEADERS).status_code==403
    assert not ws.connect_db.called


def test_schema_error_sanitized(client,monkeypatch):
    monkeypatch.setattr(ws,'overview',Mock(side_effect=RuntimeError('private DSN password')))
    r = client.get('/api/admin/eligibility/overview')
    assert r.status_code==503 and 'password' not in r.text


@pytest.fixture
def seeded(request,monkeypatch):
    dsn = os.getenv('SEERR_DISCOVERY_TEST_DSN')
    if not dsn:pytest.skip('Disposable PostgreSQL required')
    # Drop our dependents BEFORE the existing discovery fixture recreates V2.
    conn = psycopg2.connect(dsn)
    with conn:
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS eligibility_results,eligibility_runs,eligibility_policies')
    conn.close()
    db = request.getfixturevalue('database')
    cfg = replace(CFG,media_types=('movie','tv'))
    m = movie(1,runtime=30);t = tv(1,seasons=[])
    source = UnifiedClient(movies=[m],television=[summary(t)],details={('movie',1):m,('tv',1):t})
    result = sync_discovery(source,cfg,build_scopes(cfg,start=date(2026,10,26),end=date(2026,11,1)),repository=DiscoveryRepository(db),dry_run=False,clock=lambda:NOW)
    assert result['status']=='success'
    with db:
        with db.cursor() as cur:cur.execute(MIGRATION.read_text())
    monkeypatch.setattr(ws,'connect_db',lambda:psycopg2.connect(dsn))
    monkeypatch.setenv('GLOBAL_ELIGIBILITY_WRITES_ENABLED','true')
    yield db
    db.rollback()
    with db:
        with db.cursor() as cur:cur.execute('DROP TABLE IF EXISTS eligibility_results,eligibility_runs,eligibility_policies')


def rows(db,table):
    with db:
        with db.cursor() as cur:
            cur.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text')
            return [r[0] for r in cur.fetchall()]


def test_full_lifecycle_identities_history_and_canonical_preserved(seeded,client):
    before = {t:rows(seeded,t) for t in ('seerr_discovered_titles','seerr_discovery_observations','seerr_discovery_runs')}
    assert ws.overview()['unevaluated']==2
    a = ws.run_evaluation(0,'admin');b = ws.run_evaluation(a['policy_version'],'admin')
    assert a['summary']['counts']['excluded']==1 and a['summary']['counts']['retained']==1
    assert a['inventory_hash']==b['inventory_hash'] and a['summary']==b['summary']
    assert b['changes']['added']==0 and b['changes']['explanation_changed']==0
    assert ws.history()['total']==2 and ws.results()['total']==2
    assert ws.results(media_type='tv')['items'][0]['tmdb_id']==1
    assert ws.results(search='%')['total']==0
    assert ws.results(limit=1)['total']==2
    p = changed_policy('short_movie',enabled=False)
    version = ws.save_policy(p,b['policy_version'],'other-admin')['version']
    assert ws.overview()['policy_changed'] is True
    c = ws.run_evaluation(version,'admin')
    assert c['changes']['excluded_to_retained']==1
    assert ws.results(a['run_id'],outcome='excluded')['total']==1
    assert ws.results(c['run_id'],outcome='excluded')['total']==0
    assert ws.save_policy(p,version,'admin')['version']==version
    for table, old in before.items():assert rows(seeded,table)==old
    assert client.get('/api/admin/eligibility/overview').json()['inventory']['total']==2
    assert client.get('/api/admin/eligibility/results?sort=bad').status_code==422


def test_unknown_provisional_and_failed_enrichment_remain_retained(seeded):
    with seeded:
        with seeded.cursor() as cur:
            cur.execute("UPDATE seerr_discovered_titles SET runtime=NULL,enrichment_status='failed',media_status=NULL,media_state='{}'")
    r = ws.run_evaluation(0,'admin')
    assert r['summary']['counts']['retained']==2
    entries = ws.results()['items']
    assert all(e['uncertainties'] for e in entries)
    assert all(e['input_snapshot']['enrichment_status']=='failed' for e in entries)


def test_policy_conflict_rolls_back_no_history(seeded):
    ws.save_policy(Policy(),0,'admin')
    with pytest.raises(ws.EligibilityError,match='policy_version_conflict'):ws.run_evaluation(0,'admin')
    with pytest.raises(ws.EligibilityError):ws.save_policy(Policy(),0,'admin')
    assert ws.history()['total']==0


def test_failed_atomic_evaluation_preserves_everything(seeded,monkeypatch):
    monkeypatch.setattr(ws,'execute_values',Mock(side_effect=RuntimeError('isolated failure')))
    with pytest.raises(RuntimeError):ws.run_evaluation(0,'admin')
    assert not rows(seeded,'eligibility_runs') and not rows(seeded,'eligibility_policies')
    assert not rows(seeded,'eligibility_results')


def test_preview_is_read_only_even_without_optional_migration(seeded,monkeypatch):
    with seeded:
        with seeded.cursor() as cur:cur.execute('DROP TABLE eligibility_results,eligibility_runs,eligibility_policies')
    monkeypatch.setenv('GLOBAL_ELIGIBILITY_WRITES_ENABLED','false')
    assert ws.preview(Policy())['counts']['excluded']==1
    assert ws.policy_payload()['schema_installed'] is False
    assert ws.overview()['unevaluated']==2
    with seeded:
        with seeded.cursor() as cur:cur.execute(MIGRATION.read_text())


def test_changed_inventory_detected_without_overwriting_old_evaluation(seeded):
    a = ws.run_evaluation(0,'admin');old = ws.results()['items']
    with seeded:
        with seeded.cursor() as cur:
            cur.execute("UPDATE seerr_discovered_titles SET runtime=100,metadata_fingerprint='updated' WHERE media_type='movie'")
    assert ws.overview()['changed_since_evaluation']==1
    b = ws.run_evaluation(a['policy_version'],'admin')
    assert b['changes']['excluded_to_retained']==1 and a['inventory_hash']!=b['inventory_hash']
    assert ws.results(a['run_id'])['items']==old


def test_busy_writer_rejected_without_retry(seeded):
    with seeded.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(184725,41)')
    try:
        with pytest.raises(ws.EligibilityError,match='eligibility_writer_busy'):ws.run_evaluation(0,'admin')
    finally:seeded.rollback()


def test_result_constraints_and_query_plan(seeded):
    a = ws.run_evaluation(0,'admin')
    with pytest.raises(psycopg2.IntegrityError):
        with seeded:
            with seeded.cursor() as cur:
                cur.execute('INSERT INTO eligibility_results SELECT * FROM eligibility_results')
    with seeded:
        with seeded.cursor() as cur:
            cur.execute('SET LOCAL enable_seqscan=off')
            cur.execute('EXPLAIN SELECT * FROM eligibility_results WHERE run_id=%s AND outcome=%s ORDER BY media_type,tmdb_id LIMIT 25',(a['run_id'],'retained'))
            assert 'eligibility_results_outcome_idx' in str(cur.fetchall())


def test_complete_inventory_at_scale_and_indexed_page(seeded):
    # Replicate canonical fixtures locally; never an artificial evaluation cap.
    with seeded:
        with seeded.cursor() as cur:
            cur.execute('''INSERT INTO seerr_discovered_titles SELECT (jsonb_populate_record(NULL::seerr_discovered_titles,
                to_jsonb(t) || jsonb_build_object('tmdb_id',g,'title','Scale '||g))).*
                FROM seerr_discovered_titles t CROSS JOIN generate_series(2,2001) g WHERE t.media_type='movie' ''')
    run = ws.run_evaluation(0,'admin')
    assert run['summary']['counts']['total']==2002
    page = ws.results(limit=25,page=2,sort='tmdb_id')
    assert page['total']==2002 and len(page['items'])==25
    assert len(rows(seeded,'eligibility_results'))==2002


@pytest.mark.parametrize('sql',[
    'ALTER TABLE eligibility_results DROP CONSTRAINT eligibility_results_pkey',
    'ALTER TABLE eligibility_results DROP CONSTRAINT eligibility_results_media_type_tmdb_id_fkey',
    'ALTER TABLE eligibility_results DROP CONSTRAINT eligibility_results_outcome_check',
    'ALTER TABLE eligibility_results ALTER COLUMN title TYPE varchar(200)',
    'DROP TABLE eligibility_results',
])
def test_incompatible_optional_schema_rejected_before_write(seeded,sql):
    with seeded:
        with seeded.cursor() as cur:cur.execute(sql)
    with pytest.raises(ws.EligibilityError,match='eligibility_schema_incompatible'):
        ws.run_evaluation(0,'admin')
    assert not rows(seeded,'eligibility_policies') and not rows(seeded,'eligibility_runs')


def test_policy_hash_tamper_rejected(seeded):
    p = ws.save_policy(Policy(),0,'admin')
    with seeded:
        with seeded.cursor() as cur:cur.execute("UPDATE eligibility_policies SET policy_hash='wrong'")
    with pytest.raises(ws.EligibilityError,match='eligibility_policy_incompatible'):
        ws.run_evaluation(p['version'],'admin')
    assert not rows(seeded,'eligibility_runs')
