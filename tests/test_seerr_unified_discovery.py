"""Unified discovery: synthetic GETs and guarded disposable PostgreSQL only."""
from dataclasses import replace
from datetime import date,timedelta
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json,RealDictCursor
import pytest
import requests

from api.services.seerr_client import SeerrClient,SeerrError,sanitize_movie,sanitize_tv,tv_eligibility
from api.services.seerr_discovery import DiscoveryScope,build_scopes,sync_discovery,collect_scope
from api.db.seerr_discovery import DiscoveryRepository,metadata_values,JSON_COLUMNS,inventory_summary
from tests.test_seerr_discovery import (database,database_v1,CFG,NOW,SCOPE,ROOT,MIGRATION,UPGRADE,
    movie,scalar,sync,inventory_snapshot,cli_module)

DUAL=replace(CFG,media_types=('movie','tv'))
TV=DiscoveryScope('all',SCOPE.start,SCOPE.end,'all','primary_release_date.asc','tv')


def tv(ident=1,**changes):
    return dict(id=ident,mediaType='tv',name=f'Series {ident}',originalName=f'Original series {ident}',
        overview='Series synopsis',originalLanguage='ja',firstAirDate='2026-10-28',type='Scripted',
        popularity=.3,voteCount=0,voteAverage=0,episodeRunTime=[24,48],createdBy=[{'id':9,'name':'Series Creator'}],
        inProduction=True,numberOfSeasons=1,numberOfEpisodes=12,seasons=[{'seasonNumber':0},
          {'seasonNumber':1,'airDate':changes.get('firstAirDate','2026-10-28')}],
        genres=[{'id':18,'name':'Drama'}],credits={'cast':[{'id':10,'name':'Series Actor','character':'Lead'}],
          'crew':[{'id':11,'name':'Series Director','job':'Director'}]})|changes


def summary(raw):
    return {k:v for k,v in raw.items() if k not in ('type','episodeRunTime','createdBy','inProduction',
        'numberOfSeasons','numberOfEpisodes','seasons','credits','releases','runtime')}


class UnifiedClient:
    def __init__(self,movies=None,television=None,details=None):
        self.movies=[movie()] if movies is None else movies
        self.television=[summary(tv())] if television is None else television
        self.details=details or {}
        self.requests=self.retry_count=0
        self.calls=[]
    def _discover(self,media_type,params):
        self.requests+=1;self.calls.append(('discover',media_type))
        rows=self.movies if media_type=='movie' else self.television
        return dict(page=1,totalPages=int(bool(rows)),totalResults=len(rows),results=rows)
    def discover(self,params):return self._discover('movie',params)
    def discover_tv(self,params):return self._discover('tv',params)
    def _detail(self,media_type,ident):
        self.requests+=1;self.calls.append(('detail',media_type,ident))
        value=self.details.get((media_type,ident),movie(ident) if media_type=='movie' else tv(ident))
        if isinstance(value,Exception):raise value
        return (sanitize_movie if media_type=='movie' else sanitize_tv)(value)
    def movie(self,ident):return self._detail('movie',ident)
    def tv(self,ident):return self._detail('tv',ident)


@pytest.fixture(autouse=True)
def no_live_http(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Live HTTP forbidden in unified discovery tests')
    monkeypatch.setattr(requests.sessions.Session,'request',forbidden)


def both(conn,client=None,when=NOW,**kwargs):
    return sync(conn,client or UnifiedClient(),scopes=[SCOPE,TV],config=DUAL,when=when,**kwargs)


def test_scope_parameters_namespaces_and_defaults():
    assert TV.parameters==dict(firstAirDateGte='2026-10-26',firstAirDateLte='2026-11-01',sortBy='first_air_date.asc',language='all')
    assert TV.key!=SCOPE.key
    assert [s.media_type for s in build_scopes(DUAL,start=SCOPE.start,end=SCOPE.end)]==['movie','tv']
    assert all(s.media_type=='movie' for s in build_scopes(CFG,start=SCOPE.start,end=SCOPE.end))
    for value in ('series','episode','season',None,''):
        with pytest.raises(SeerrError):replace(TV,media_type=value)
        with pytest.raises(SeerrError):replace(CFG,media_types=(value,))


def test_movie_tv_id_collision_and_isolated_metadata(database):
    result=both(database)
    repo=DiscoveryRepository(database);m=repo.get(1);t=repo.get(1,'tv')
    assert result['status']=='success' and result['counts']['titles']==2 and result['counts']['movies']==1
    assert result['counts']['by_media_type']['tv']['eligible']==1
    assert m['title']=='Fixture 1' and t['title']=='Series 1'
    assert m['runtime']==90 and t['runtime'] is None
    assert m['release_events'][0]['type']==4 and t['release_events'] is None
    assert t['tv_metadata']['episode_run_times']==[24,48] and m['tv_metadata'] is None
    assert t['premiere_date']==date(2026,10,28) and t['directors']==['Series Director']
    assert m['metadata_fingerprint']!=t['metadata_fingerprint']
    assert scalar(database,'SELECT count(*) FROM public.seerr_discovery_observations')==2
    changed=UnifiedClient(details={('tv',1):tv(overview='New series synopsis')})
    both(database,changed,when=NOW+timedelta(days=1),refresh=True)
    assert repo.get(1)['synopsis']=='Descriptive synopsis' and repo.get(1,'tv')['synopsis']=='New series synopsis'


def test_same_source_both_repeat_refresh_is_idempotent(database):
    both(database);repo=DiscoveryRepository(database)
    before={t:repo.get(1,t) for t in ('movie','tv')}
    result=both(database,when=NOW+timedelta(days=1),refresh=True)
    assert result['counts']['new_titles']==result['counts']['updated_titles']==0
    for t in before:
        row=repo.get(1,t)
        assert row['metadata_fingerprint']==before[t]['metadata_fingerprint']
        assert row['metadata_updated_at']==before[t]['metadata_updated_at']
    assert scalar(database,'SELECT count(*) FROM public.seerr_discovered_titles')==2


@pytest.mark.parametrize('change',[{'source_id':'other'},{'url':'https://other-fixture.invalid'}])
def test_both_sources_fail_closed_before_network_or_mutation(database,change):
    both(database);before=inventory_snapshot(database);client=UnifiedClient()
    result=sync(database,client,scopes=[SCOPE,TV],config=replace(DUAL,**change),refresh=True)
    assert result['errors']==[{'code':'discovery_source_identity_mismatch'}]
    assert client.requests==0 and inventory_snapshot(database)==before


def test_tv_unknown_catalog_vs_known_request_status_and_privacy(database):
    status={'status':4,'status4k':1,'externalServiceId':123,'ratingKey':'private-id',
        'requests':[{'status':2,'is4k':False,'requestedBy':{'plexToken':'private-secret'},
                     'seasons':[{'id':77,'seasonNumber':1,'status':2}]}]}
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):tv(mediaInfo=status)}),scopes=[TV],config=replace(CFG,media_types=('tv',)))
    row=DiscoveryRepository(database).get(1,'tv')
    assert result['status']=='success' and row['media_status']==4 and row['media_status_4k']==1
    assert row['media_state']['request_count']==1
    assert row['media_state']['request_states'][0]['seasons']==[{'seasonNumber':1,'status':2}]
    assert 'private-secret' not in json.dumps(row['source_metadata']) and 'private-id' not in json.dumps(row['source_metadata'])
    changed=UnifiedClient(movies=[],details={('tv',1):tv(mediaInfo=None)})
    sync(database,changed,scopes=[TV],config=replace(CFG,media_types=('tv',)),refresh=True)
    row=DiscoveryRepository(database).get(1,'tv')
    assert row['media_status'] is None and row['media_state']['requests']=='omitted' and row['media_state']['request_count'] is None


@pytest.mark.parametrize('missing', [None,'','2026-99-99','20261028',42])
def test_unknown_or_malformed_tv_premiere_is_explicit_not_eligible(database,missing):
    row=summary(tv(firstAirDate=missing))
    result=sync(database,UnifiedClient(movies=[],television=[row]),scopes=[TV],config=replace(CFG,media_types=('tv',)))
    assert result['counts']['titles']==1 and result['discovery_complete']
    assert result['pagination'][0]['unresolved'][0]['reason']=='original_premiere_unknown'
    assert result['counts']['eligible']==1  # Detail resolves the unknown summary.
    assert DiscoveryRepository(database).get(1,'tv')['premiere_date']==date(2026,10,28)


def test_original_tv_premiere_not_returning_season_or_episode(database):
    rows=[summary(tv(1,firstAirDate='2019-02-01',lastAirDate='2026-10-28',nextEpisodeToAir={'airDate':'2026-10-28','seasonNumber':4})),
          {'id':2,'mediaType':'episode','airDate':'2026-10-28','showId':1},
          {'id':3,'mediaType':'season','airDate':'2026-10-28','seasonNumber':4}]
    client=UnifiedClient(movies=[],television=rows)
    result=sync(database,client,scopes=[TV],config=replace(CFG,media_types=('tv',)))
    assert result['counts']['titles']==0
    assert result['pagination'][0]['excluded'][0]['reason']=='original_premiere_outside_window'
    assert result['pagination'][0]['invalid_rows']==2 and all(c[0]=='discover' for c in client.calls)


def test_historical_window_allows_late_discovered_new_series(database):
    scope=DiscoveryScope('late',date(2020,1,1),date(2020,1,10),media_type='tv')
    raw=tv(firstAirDate='2020-01-05')
    result=sync(database,UnifiedClient(movies=[],television=[summary(raw)],details={('tv',1):raw}),scopes=[scope],config=replace(CFG,media_types=('tv',)))
    assert result['status']=='success' and result['counts']['by_media_type']['tv']['eligible']==1
    assert DiscoveryRepository(database).get(1,'tv')['premiere_date']==date(2020,1,5)


@pytest.mark.parametrize('detail,reason',[
    (tv(type='Special'),'explicit_tv_special'),
    (tv(seasons=[{'seasonNumber':0}]),'specials_only')])
def test_detail_exclusions_remain_auditable_and_are_not_candidates(database,detail,reason):
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):detail}),scopes=[TV],config=replace(CFG,media_types=('tv',)))
    assert result['counts']['by_media_type']['tv']['excluded']==1
    assert result['counts']['by_media_type']['tv']['eligible']==0
    assert DiscoveryRepository(database).get(1,'tv')
    assessment=scalar(database,'SELECT eligibility FROM public.seerr_discovery_observations')
    assert assessment=={'state':'excluded','reason':reason}


def test_uncertain_classification_provisional_and_single_episode_not_assumed_special(database):
    uncertain=tv(type=None,seasons=None)
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):uncertain}),scopes=[TV],config=replace(CFG,media_types=('tv',)))
    assert result['counts']['provisional']==1 and result['counts']['excluded']==0
    good=tv(numberOfEpisodes=1,seasons=[{'seasonNumber':0},{'seasonNumber':1,'airDate':'2026-10-28'}],type='Miniseries')
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):good}),scopes=[TV],config=replace(CFG,media_types=('tv',)),refresh=True)
    assert result['counts']['eligible']==1


@pytest.mark.parametrize('field',['episodeRunTime','createdBy','seasons'])
@pytest.mark.parametrize('incoming',[None,[], 'invalid', 'omitted'])
def test_tv_collection_presence_semantics_and_repeat(database,field,incoming):
    config=replace(CFG,media_types=('tv',));client=UnifiedClient(movies=[])
    sync(database,client,scopes=[TV],config=config);repo=DiscoveryRepository(database);old=repo.get(1,'tv')
    detail=tv(**{field:incoming});column={'episodeRunTime':'episode_run_times','createdBy':'created_by','seasons':'season_numbers'}[field]
    if incoming=='omitted':detail.pop(field)
    sync(database,UnifiedClient(movies=[],details={('tv',1):detail}),scopes=[TV],config=config,refresh=True,when=NOW+timedelta(days=1))
    row=repo.get(1,'tv')
    assert row['tv_metadata'][column]==([] if incoming==[] else old['tv_metadata'][column])
    expected='empty' if incoming==[] else 'null' if incoming is None else 'omitted' if incoming=='omitted' else 'invalid'
    actual=row['field_states']['tv_'+column]
    assert actual==('value' if expected=='empty' else expected)
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):detail}),scopes=[TV],config=config,refresh=True,when=NOW+timedelta(days=2))
    assert result['counts']['updated_titles']==0 and repo.get(1,'tv')['metadata_updated_at']==row['metadata_updated_at']


def test_tv_never_manufactures_movie_runtime_or_release_events():
    clean=sanitize_tv(tv(runtime=120,releaseDate='2030-01-01',releases={'results':[]}))
    row=metadata_values(clean,media_type='tv')
    assert 'releaseDate' not in clean and 'releases' not in clean and 'runtime' not in clean
    assert row['runtime'] is None and row['release_events'] is None and row['premiere_date']==date(2026,10,28)
    assert row['tv_metadata']['episode_run_times']==[24,48]
    assert row['field_states']['release_events']=='not_applicable'


def test_movie_sanitizer_golden_compatibility():
    golden=json.loads((ROOT/'tests/fixtures/seerr_movie_v1_record.json').read_text())
    assert sanitize_movie(golden['raw_movie'])==golden['sanitized_movie']


def seed_v1(conn):
    golden=json.loads((ROOT/'tests/fixtures/seerr_movie_v1_record.json').read_text());row=golden['canonical_movie_v1']
    with conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.seerr_discovery_runs
                (run_id,started_at,completed_at,status,operation,source_key,parameters,discovery_complete,enrichment_complete)
                VALUES (%s,%s,%s,'success','discover',%s,%s,true,true)""",(row['first_discovery_run_id'],NOW,NOW,CFG.source_key,Json({'source_id':CFG.source_id})))
            keys=list(row)
            cur.execute(sql.SQL('INSERT INTO public.seerr_discovered_movies ({}) VALUES ({})').format(
                sql.SQL(',').join(map(sql.Identifier,keys)),sql.SQL(',').join(sql.Placeholder() for _ in keys)),
                [Json(row[k]) if k in JSON_COLUMNS else row[k] for k in keys])
            cur.execute("""INSERT INTO public.seerr_discovery_observations
                (run_id,tmdb_id,scope_key,scope_name,observation_kind,query_parameters,observed_at,discovery_metadata,source_fingerprint,metadata_fingerprint,is_new)
                VALUES (%s,701,'legacy-movie-scope','legacy','discovery',%s,%s,%s,%s,%s,true)""",(row['first_discovery_run_id'],Json(SCOPE.parameters),NOW,Json(golden['sanitized_movie']),'legacy-fingerprint',row['metadata_fingerprint']))
    return golden


def test_populated_v1_migration_preserves_history_and_identical_refresh_hash(database_v1):
    golden=seed_v1(database_v1)
    with database_v1:
        with database_v1.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM public.seerr_discovered_movies');old=dict(cur.fetchone())
            cur.execute('SELECT to_jsonb(t) FROM public.seerr_discovery_runs t');run_before=cur.fetchone()['to_jsonb']
            cur.execute('SELECT to_jsonb(t) FROM public.seerr_discovery_observations t');obs_before=cur.fetchone()['to_jsonb']
            cur.execute(UPGRADE.read_text())
    repo=DiscoveryRepository(database_v1);row=repo.get(701)
    for key,value in old.items():
        assert row[{'release_date':'premiere_date','discovery_release_date':'discovery_premiere_date'}.get(key,key)]==value
    assert row['media_type']=='movie' and row['tv_metadata'] is None
    assert scalar(database_v1,'SELECT to_jsonb(t) FROM public.seerr_discovery_runs t')==run_before
    obs=scalar(database_v1,'SELECT to_jsonb(t) FROM public.seerr_discovery_observations t')
    assert obs==dict(obs_before,media_type='movie',eligibility=None)
    result=sync(database_v1,UnifiedClient(movies=[golden['raw_movie']],television=[],details={('movie',701):golden['raw_movie']}),refresh=True,when=NOW+timedelta(days=1))
    after=repo.get(701)
    assert result['counts']['updated_movies']==0
    assert after['metadata_fingerprint']==golden['canonical_movie_v1']['metadata_fingerprint']
    assert after['metadata_updated_at']==old['metadata_updated_at']
    both(database_v1,UnifiedClient(movies=[golden['raw_movie']],television=[summary(tv(701))],
        details={('movie',701):golden['raw_movie'],('tv',701):tv(701)}),when=NOW+timedelta(days=2))
    assert repo.get(701,'tv')['title']=='Series 701'
    assert repo.get(701)['metadata_fingerprint']==old['metadata_fingerprint']


def test_unified_writer_fails_safely_on_installed_v1_schema(database_v1):
    seed_v1(database_v1);client=UnifiedClient()
    before=scalar(database_v1,'SELECT count(*) FROM public.seerr_discovery_runs')
    result=both(database_v1,client)
    assert result['errors']==[{'code':'seerr_unified_schema_required'}] and client.requests==0
    assert scalar(database_v1,'SELECT count(*) FROM public.seerr_discovery_runs')==before


def test_both_request_budget_is_one_client_budget(database):
    config=replace(DUAL,max_requests=3,retries=0)
    session=Mock();session.headers={}
    def get(url,**kwargs):
        response=Mock(status_code=200)
        if url.endswith('/discover/movies'):response.json.return_value=dict(page=1,totalPages=1,totalResults=1,results=[movie()])
        elif url.endswith('/discover/tv'):response.json.return_value=dict(page=1,totalPages=1,totalResults=1,results=[summary(tv())])
        elif url.endswith('/movie/1'):response.json.return_value=movie()
        else:raise AssertionError('Global budget must stop before TV detail HTTP')
        return response
    session.get.side_effect=get
    client=SeerrClient(config,session=session)
    result=sync(database,client,scopes=[SCOPE,TV],config=config)
    assert client.requests==session.get.call_count==3 and result['status']=='partial'
    assert result['counts']['titles']==2 and result['counts']['enrichment_deferred']==1
    assert DiscoveryRepository(database).get(1,'tv')['last_enrichment_attempt_at'] is None
    session.post.assert_not_called();session.put.assert_not_called();session.delete.assert_not_called()
    for endpoint in ('/tv/1/season/1','/tv/1/episode/1','/request','/radarr','/sonarr'):
        with pytest.raises(SeerrError,match='endpoint_not_allowlisted'):client._get(endpoint,{})


def test_tv_cache_and_explicit_refresh_are_not_new_series_monitoring(database):
    both(database)
    client=UnifiedClient();result=both(database,client)
    assert result['counts']['enrichment_cached']==2 and not any(c[0]=='detail' for c in client.calls)
    before=DiscoveryRepository(database).get(1,'tv')
    result=sync(database,UnifiedClient(),config=DUAL,enrich_due=True,when=NOW+timedelta(days=100))
    after=DiscoveryRepository(database).get(1,'tv')
    assert result['counts']['new_titles']==0 and result['counts']['titles']==2
    assert after['first_discovered_at']==before['first_discovered_at'] and after['last_observed_at']==before['last_observed_at']
    assessment=scalar(database,"SELECT eligibility FROM public.seerr_discovery_observations WHERE run_id=%s AND media_type='tv'",(result['run_id'],))
    assert assessment['reason']=='refresh_not_new_series_discovery'


def test_refresh_fairness_rotates_across_media_types(database):
    failures={(t,i):SeerrError('http_404') for t,i in [('movie',1),('tv',1),('tv',2)]}
    both(database,UnifiedClient(television=[summary(tv(1)),summary(tv(2))],details=failures))
    config=replace(DUAL,refresh_batch_size=2,failed_retry_hours=1)
    repo=DiscoveryRepository(database)
    assert [(r['media_type'],r['tmdb_id']) for r in repo.due(config,NOW+timedelta(days=1))]==[('movie',1),('tv',1)]
    sync(database,UnifiedClient(details=failures),config=config,enrich_due=True,when=NOW+timedelta(days=1))
    assert [(r['media_type'],r['tmdb_id']) for r in repo.due(config,NOW+timedelta(days=2))]==[('tv',2),('movie',1)]
    assert all(r['media_type']=='tv' for r in repo.due(replace(config,media_types=('tv',)),NOW+timedelta(days=2)))


def test_interrupted_mixed_run_recovers_both_namespaces(database):
    repo=DiscoveryRepository(database);run=str(uuid4());assert repo.acquire()
    repo.start(run,NOW,'discover',CFG.source_key,{'source_id':CFG.source_id})
    repo.discover_page(run,SCOPE.key,SCOPE.name,SCOPE.parameters,[sanitize_movie(movie())],NOW)
    repo.discover_page(run,TV.key,TV.name,TV.parameters,[sanitize_tv(tv())],NOW,media_type='tv')
    repo.release()
    result=both(database,UnifiedClient(movies=[],television=[]),when=NOW+timedelta(hours=1))
    assert result['status']=='success'
    counts=scalar(database,'SELECT counts FROM public.seerr_discovery_runs WHERE run_id=%s',(run,))
    assert counts['titles']==2 and counts['movies']==1 and counts['by_media_type']['tv']['titles']==1
    assert scalar(database,'SELECT count(*) FROM public.seerr_discovery_observations WHERE run_id=%s',(run,))==2


@pytest.mark.parametrize('drift',[
    'ALTER TABLE public.seerr_discovered_movies ALTER COLUMN runtime TYPE bigint',
    'ALTER TABLE public.seerr_discovered_movies ADD COLUMN unexpected text',
    'ALTER TABLE public.seerr_discovered_movies DROP CONSTRAINT seerr_discovered_movies_runtime_check',
    'DROP INDEX public.seerr_movies_last_seen_idx; CREATE INDEX seerr_movies_last_seen_idx ON public.seerr_discovered_movies(title)',
    'ALTER SEQUENCE public.seerr_discovery_observations_observation_id_seq INCREMENT BY 2',
    'CREATE TABLE public.seerr_shadow(id integer)',
    'CREATE TABLE public.fixture_external_reference(id bigint REFERENCES public.seerr_discovered_movies(tmdb_id))'])
def test_forward_migration_rejects_schema_drift_without_changes(database_v1,drift):
    with database_v1:
        with database_v1.cursor() as cur:cur.execute(drift)
    before=scalar(database_v1,"SELECT array_agg(c.relname::text ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'")
    with pytest.raises(psycopg2.Error,match='seerr_unified_upgrade_'):
        with database_v1:
            with database_v1.cursor() as cur:cur.execute(UPGRADE.read_text())
    assert scalar(database_v1,"SELECT to_regclass('public.seerr_discovered_titles')") is None
    assert scalar(database_v1,"SELECT array_agg(c.relname::text ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'")==before
    # Isolated-only drift fixtures must be removed before the next fixture reset.
    with database_v1:
        with database_v1.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS public.fixture_external_reference')
            cur.execute('DROP TABLE IF EXISTS public.seerr_shadow')


def test_upgrade_is_atomic_even_in_autocommit_on_late_failure(database_v1):
    seed_v1(database_v1)
    injected=UPGRADE.read_text().replace('    ALTER TABLE public.seerr_discovered_titles\n        ADD COLUMN',"    RAISE EXCEPTION 'isolated_fixture_failure_after_rename';\n    ALTER TABLE public.seerr_discovered_titles\n        ADD COLUMN",1)
    database_v1.autocommit=True
    try:
        with pytest.raises(psycopg2.Error,match='isolated_fixture_failure_after_rename'):
            with database_v1.cursor() as cur:cur.execute(injected)
        assert scalar(database_v1,"SELECT to_regclass('public.seerr_discovered_titles')") is None
        assert scalar(database_v1,'SELECT count(*) FROM public.seerr_discovered_movies')==1
        assert scalar(database_v1,"SELECT count(*) FROM information_schema.columns WHERE table_name='seerr_discovered_movies' AND column_name='release_date'")==1
    finally:database_v1.autocommit=False


def test_already_upgraded_schema_is_rejected_without_rewriting_data(database):
    both(database);before=inventory_snapshot(database)
    with pytest.raises(psycopg2.Error,match='already_present'):
        with database:
            with database.cursor() as cur:cur.execute(UPGRADE.read_text())
    assert inventory_snapshot(database)==before


def test_tv_pagination_cap_and_accounting():
    client=UnifiedClient(movies=[])
    def page(params):
        return dict(page=1,totalPages=2,totalResults=2,results=[summary(tv())])
    client.discover_tv=page
    accepted=[];metrics,_=collect_scope(client,TV,1,accepted.extend)
    assert len(accepted)==metrics['unique_titles']==1 and metrics['unique_movies']==0 and not metrics['complete']
    assert metrics['errors']==[{'code':'page_limit_exceeded'}]


def test_get_only_tv_transport_and_missing_type_is_endpoint_context():
    session=Mock();session.headers={};r=Mock(status_code=200);raw=tv();raw.pop('mediaType');r.json.return_value=raw;session.get.return_value=r
    client=SeerrClient(DUAL,session=session)
    assert client.tv(1)['mediaType']=='tv'
    assert session.get.call_args.args[0].endswith('/api/v1/tv/1')
    r.json.return_value=tv(mediaType='movie')
    with pytest.raises(SeerrError,match='media_type_mismatch'):client.tv(1)
    with pytest.raises(SeerrError,match='media_type_mismatch'):sanitize_movie(tv())


def test_cli_combined_preview_never_connects(monkeypatch,capsys):
    module=cli_module();monkeypatch.setattr(module,'load_dotenv',lambda *a,**k:None)
    def cfg(*a,**k):return replace(DUAL,enabled=False,**{name:value for name,value in k.items() if value is not None})
    monkeypatch.setattr(module,'load_seerr_config',cfg)
    monkeypatch.setattr(module,'SeerrClient',lambda _:UnifiedClient())
    connection=Mock(side_effect=AssertionError('preview cannot connect'));monkeypatch.setattr(module,'connect_db',connection)
    assert module.main(['--dry-run','--media-type','movie','--media-type','tv','--start','2026-10-26','--end','2026-11-01','--json'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['counts']['titles']==2 and result['counts']['movies']==1
    connection.assert_not_called()


@pytest.mark.parametrize('detail,reason',[
    (tv(type='Special',firstAirDate=None),'explicit_tv_special'),
    (tv(seasons=[{'seasonNumber':0}],firstAirDate=None),'specials_only')])
def test_confirmed_special_exclusion_survives_unknown_dates_and_refresh(database,detail,reason):
    config=replace(CFG,media_types=('tv',))
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):detail}),scopes=[TV],config=config)
    assert result['counts']['excluded']==1
    refreshed=sync(database,UnifiedClient(movies=[],details={('tv',1):detail}),config=config,
        enrich_due=True,refresh=True,when=NOW+timedelta(days=1))
    assert refreshed['counts']['excluded']==1 and refreshed['counts']['provisional']==0
    assert scalar(database,'SELECT eligibility FROM public.seerr_discovery_observations WHERE run_id=%s',
        (refreshed['run_id'],))=={'state':'excluded','reason':reason}


@pytest.mark.parametrize('field,column,known',[
    ('genres','genres',[{'id':18,'name':'Drama'}]),
    ('genreIds','genres',[{'id':18,'name':'Drama'}]),
    ('productionCountries','production_countries',[{'iso_3166_1':'JP','name':'Japan'}]),
    ('productionCompanies','production_companies',[{'id':9,'name':'Studio'}])])
@pytest.mark.parametrize('malformed',[[None],[{}],['wrong'],[{'id':[]} ]])
def test_tv_malformed_collection_members_preserve_known_and_empty_clears(field,column,known,malformed):
    old={column:known}
    raw=tv(**{field:malformed})
    if field=='genreIds':raw.pop('genres')
    clean=sanitize_tv(raw);mapped=metadata_values(clean,old,media_type='tv')
    assert clean['_fields'][field]=='invalid' and mapped[column]==known
    raw[field]=[]
    assert metadata_values(sanitize_tv(raw),old,media_type='tv')[column]==[]


def test_tv_unknown_detail_premiere_remains_provisional_with_discovery_evidence(database):
    result=sync(database,UnifiedClient(movies=[],details={('tv',1):tv(firstAirDate=None)}),
        scopes=[TV],config=replace(CFG,media_types=('tv',)))
    row=DiscoveryRepository(database).get(1,'tv')
    assert result['counts']['provisional']==1 and result['counts']['eligible']==0
    assert row['premiere_date'] is None and row['discovery_premiere_date']==date(2026,10,28)


def test_combined_http_budget_includes_retries(database):
    config=replace(DUAL,max_requests=4,retries=1)
    session=Mock();session.headers={}
    responses=[Mock(status_code=429,headers={'Retry-After':'0'})]
    for raw in (dict(page=1,totalPages=1,totalResults=1,results=[movie()]),
                dict(page=1,totalPages=1,totalResults=1,results=[summary(tv())]),movie()):
        response=Mock(status_code=200);response.json.return_value=raw;responses.append(response)
    session.get.side_effect=responses
    client=SeerrClient(config,session=session,sleep=lambda _:None)
    result=sync(database,client,scopes=[SCOPE,TV],config=config)
    assert session.get.call_count==client.requests==4 and client.retry_count==1
    assert result['status']=='partial' and result['counts']['enrichment_deferred']==1
