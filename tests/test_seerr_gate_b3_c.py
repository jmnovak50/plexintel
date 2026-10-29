"""B3-C: latest captured B3-B state, synthetic changes/failures, isolated PG only."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests
from psycopg2 import sql
from psycopg2.extras import Json

from api.db.seerr_discovery import JSON_COLUMNS, DiscoveryRepository
from api.services.seerr_client import SeerrClient, SeerrError
from tests.test_seerr_discovery import ROOT, database, database_v1, inventory_snapshot
from tests.test_seerr_gate_b3 import CONFIG, MOVIE, CaptureClient, query, run, titles

ARTIFACTS = ROOT/'artifacts/seerr-exploration'
CFG = replace(CONFIG, source_id='b3c-isolated-fixture', media_types=('movie',),
              retries=0, interval=0, failed_retry_hours=1)
NOW = datetime(2026, 10, 29, 5, 15, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Live HTTP forbidden in B3-C tests')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)


@pytest.fixture
def seeded_latest(database):
    """Copy snapshots only after the shared fixture verifies its disposable target."""
    data = deepcopy(json.loads((ARTIFACTS/'2026-10-29-gate-b3-b/after.json').read_text()))
    for item in data['discovery_runs']:
        item['source_key'] = CFG.source_key
        item['parameters'].update(source_key=CFG.source_key, source_id=CFG.source_id)
    for item in data['canonical_titles']:
        item['metadata_source_key'] = CFG.source_key
    json_columns = JSON_COLUMNS | {'parameters','pagination','counts','errors','warnings',
        'query_parameters','discovery_metadata','detail_metadata','eligibility'}
    with database:
        with database.cursor() as cur:
            for table, key in [('seerr_discovery_runs','discovery_runs'),
                               ('seerr_discovered_titles','canonical_titles'),
                               ('seerr_discovery_observations','observations')]:
                for row in data[key]:
                    names = list(row)
                    cur.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(
                        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier,names)),
                        sql.SQL(',').join(sql.Placeholder() for _ in names)),
                        [Json(row[k]) if k in json_columns and row[k] is not None else row[k] for k in names])
            cur.execute("SELECT setval('public.seerr_discovery_observations_observation_id_seq',48,true)")
    history = query(database,'SELECT * FROM public.seerr_discovery_runs ORDER BY run_id')
    observations = query(database,'SELECT * FROM public.seerr_discovery_observations ORDER BY observation_id')
    old_titles = titles(database)
    movie_times = [t['last_enriched_at'] for t in old_titles if t['media_type']=='movie']
    return dict(conn=database, history=history, observations=observations, titles=old_titles,
        before_ttl=min(movie_times)+timedelta(hours=24)-timedelta(microseconds=1),
        expired=max(movie_times)+timedelta(hours=24)+timedelta(microseconds=1))


class Client(CaptureClient):
    def __init__(self, extra=False):
        b2 = json.loads((ARTIFACTS/'2026-10-28-gate-b2/after.json').read_text())
        super().__init__(b2, extra_page=extra)

    def _detail(self, kind, ident):
        value = self.details[kind,ident]
        if isinstance(value, Exception):
            self.requests += 1
            self.detail_calls.append((kind,ident))
            raise value
        return super()._detail(kind,ident)


def unchanged_history(state):
    conn = state['conn']
    for old in state['history']:
        assert query(conn,'SELECT * FROM public.seerr_discovery_runs WHERE run_id=%s',(old['run_id'],)) == [old]
    assert query(conn,'SELECT * FROM public.seerr_discovery_observations WHERE observation_id<=48 ORDER BY observation_id') == state['observations']
    assert [t for t in titles(conn) if t['media_type']=='tv'] == [t for t in state['titles'] if t['media_type']=='tv']


def test_latest_state_fresh_prefix_adds20_without_rewriting_terminal_partials(seeded_latest):
    s=seeded_latest;client=Client(extra=True)
    result=run(s['conn'],client,when=NOW,config=replace(CFG,max_pages=2))
    assert result['status']=='partial' and result['counts']['titles']==40
    assert result['counts']['new_titles']==20 and result['counts']['enrichment_cached']==20
    assert result['counts']['enrichment_success']==20 and client.requests==22
    assert len(titles(s['conn']))==48
    assert len(query(s['conn'],'SELECT * FROM public.seerr_discovery_observations'))==88
    unchanged_history(s)


def test_latest_state_expired_prefix_refetches_old_and_adds_new_without_force(seeded_latest):
    s=seeded_latest;client=Client(extra=True)
    ident=next(t['tmdb_id'] for t in s['titles'] if t['media_type']=='movie')
    client.details['movie',ident]['overview']='Isolated natural-TTL metadata delta'
    result=run(s['conn'],client,when=s['expired'],config=replace(CFG,max_pages=2))
    assert result['status']=='partial' and result['counts']['new_titles']==20
    assert result['counts']['enrichment_success']==40 and result['counts']['enrichment_cached']==0
    assert result['counts']['updated_titles']==1 and client.requests==42
    assert len(client.detail_calls)==40 and len(titles(s['conn']))==48
    repo=DiscoveryRepository(s['conn'])
    for old in (t for t in s['titles'] if t['media_type']=='movie'):
        new=repo.get(old['tmdb_id'])
        assert new['first_discovery_run_id']==old['first_discovery_run_id']
        assert new['last_enriched_at']==s['expired']
        if old['tmdb_id']==ident:
            assert new['metadata_fingerprint']!=old['metadata_fingerprint']
            assert new['metadata_updated_at']==s['expired']
        else:
            assert new['metadata_fingerprint']==old['metadata_fingerprint']
            assert new['metadata_updated_at']==old['metadata_updated_at']
    unchanged_history(s)


def test_changed_detail_is_hidden_before_TTL_then_seen_naturally(seeded_latest):
    s=seeded_latest;client=Client()
    old=next(t for t in s['titles'] if t['media_type']=='movie');ident=old['tmdb_id']
    client.details['movie',ident]['overview']='New detail cannot bypass a fresh cache'
    first=run(s['conn'],client,when=s['before_ttl'],config=CFG)
    assert first['counts']['enrichment_cached']==20 and client.detail_calls==[]
    assert DiscoveryRepository(s['conn']).get(ident)['metadata_fingerprint']==old['metadata_fingerprint']
    second=run(s['conn'],client,when=s['expired'],config=CFG)
    assert second['counts']['enrichment_success']==20 and second['counts']['updated_titles']==1
    new=DiscoveryRepository(s['conn']).get(ident)
    assert new['last_enriched_at']==new['metadata_updated_at']==s['expired']
    assert new['media_status'] is None and new['media_state']['request_count'] is None
    unchanged_history(s)


def test_failed_detail_preserves_metadata_cooldown_defers_then_later_fetches(seeded_latest):
    s=seeded_latest;ident=next(t['tmdb_id'] for t in s['titles'] if t['media_type']=='movie')
    client=Client();client.details['movie',ident]=SeerrError('network_retries_exhausted')
    first=run(s['conn'],client,when=s['expired'],config=CFG)
    assert first['counts']['enrichment_failed']==1
    repo=DiscoveryRepository(s['conn']);failed=repo.get(ident)
    original=next(t for t in s['titles'] if t['media_type']=='movie' and t['tmdb_id']==ident)
    assert failed['metadata_fingerprint']==original['metadata_fingerprint']
    assert failed['last_enriched_at']==original['last_enriched_at']
    assert failed['last_enrichment_attempt_at']==s['expired']
    next_client=Client()
    second=run(s['conn'],next_client,when=s['expired']+timedelta(minutes=30),config=CFG)
    assert second['counts']['enrichment_cached']==19 and second['counts']['enrichment_deferred']==1
    assert next_client.detail_calls==[] and repo.get(ident)['last_enrichment_attempt_at']==s['expired']
    later_client=Client()
    third=run(s['conn'],later_client,when=s['expired']+timedelta(hours=1),config=CFG)
    assert third['counts']['enrichment_success']==1 and third['counts']['enrichment_cached']==19
    assert later_client.detail_calls==[('movie',ident)]
    assert repo.get(ident)['enrichment_status']=='success'
    unchanged_history(s)


def test_real_client_budget_exhaustion_defers_without_false_attempt_then_progresses(seeded_latest):
    s=seeded_latest;captured=Client();session=Mock();session.headers={}
    def get(url,**kwargs):
        response=Mock(status_code=200)
        if url.endswith('/discover/movies'):
            response.json.return_value=dict(page=1,totalPages=6,totalResults=111,results=captured.movie_rows)
        else:
            ident=int(url.rsplit('/',1)[-1]);response.json.return_value=captured.details['movie',ident]
        return response
    session.get.side_effect=get
    budget_cfg=replace(CFG,max_requests=2)
    client=SeerrClient(budget_cfg,session=session)
    first=run(s['conn'],client,when=s['expired'],config=budget_cfg)
    assert client.requests==session.get.call_count==2
    assert first['counts']['enrichment_success']==1 and first['counts']['enrichment_deferred']==19
    old={t['tmdb_id']:t for t in s['titles'] if t['media_type']=='movie'}
    for o in query(s['conn'],"SELECT * FROM public.seerr_discovery_observations WHERE run_id=%s AND enrichment_outcome='deferred'",(first['run_id'],)):
        row=DiscoveryRepository(s['conn']).get(o['tmdb_id'])
        assert row['last_enrichment_attempt_at']==old[o['tmdb_id']]['last_enrichment_attempt_at']
        assert row['metadata_fingerprint']==old[o['tmdb_id']]['metadata_fingerprint']
    first_run=query(s['conn'],'SELECT * FROM public.seerr_discovery_runs WHERE run_id=%s',(first['run_id'],))
    second=run(s['conn'],Client(),when=s['expired']+timedelta(minutes=1),config=CFG)
    assert second['counts']['enrichment_success']==19 and second['counts']['enrichment_cached']==1
    assert query(s['conn'],'SELECT * FROM public.seerr_discovery_runs WHERE run_id=%s',(first['run_id'],))==first_run
    unchanged_history(s)


def test_abandoned_running_is_recovered_only_after_source_guard_and_preserves_pending_evidence(seeded_latest):
    s=seeded_latest;conn=s['conn'];repo=DiscoveryRepository(conn);abandoned=str(uuid4())
    assert repo.acquire()
    repo.start(abandoned,NOW,'discover',CFG.source_key,{'source_id':CFG.source_id,'source_key':CFG.source_key})
    repo.discover_page(abandoned,MOVIE.key,MOVIE.name,MOVIE.parameters,Client().movie_rows[:3],NOW)
    repo.release()
    pending=query(conn,'SELECT * FROM public.seerr_discovery_observations WHERE run_id=%s ORDER BY observation_id',(abandoned,))
    before=inventory_snapshot(conn);bad_client=Client()
    bad=run(conn,bad_client,when=NOW+timedelta(minutes=1),config=replace(CFG,source_id='wrong-source'))
    assert bad['errors']==[{'code':'discovery_source_identity_mismatch'}]
    assert bad_client.requests==0 and inventory_snapshot(conn)==before
    good=run(conn,Client(),when=NOW+timedelta(minutes=2),config=CFG)
    assert good['counts']['enrichment_cached']==20
    recovered=query(conn,'SELECT * FROM public.seerr_discovery_runs WHERE run_id=%s',(abandoned,))[0]
    assert recovered['status']=='partial' and recovered['counts']['titles']==3
    assert recovered['counts']['enrichment_pending']==3
    assert recovered['errors']==[{'code':'interrupted_previous_execution'}]
    assert query(conn,'SELECT * FROM public.seerr_discovery_observations WHERE run_id=%s ORDER BY observation_id',(abandoned,))==pending
    unchanged_history(s)
