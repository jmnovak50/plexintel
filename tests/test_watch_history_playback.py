"""Session isolation and compatibility against an explicitly disposable PostgreSQL DB."""
import ast
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.services import watch_history_sync as grouped
from api.services import watch_session_sync as sessions
from api.services import agent_tool_service as service
from api.routes import agent_tools
from tests.test_agent_tool_service import FakeConnection
from tests.test_watch_history_compact import make_history_row
from user_profile_embeddings import fetch_profile_title_rows, build_user_profiles

MIGRATION = Path('api/db/migrations/004_watch_sessions.sql').read_text()
ROLES = Path('sql/provision_watch_session_roles.sql').read_text()
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def event(event_id=100, **kwargs):
    row = dict(id=event_id, row_id=event_id, rating_key=500, date=int((NOW-timedelta(hours=1)).timestamp()),
               started=int((NOW-timedelta(hours=1)).timestamp()), stopped=int((NOW-timedelta(minutes=45)).timestamp()),
               user='fixture', user_id=5, title='Movie', media_type='movie', reference_id=77,
               play_duration=900, percent_complete=40, group_count=1, group_ids=str(event_id))
    row.update(kwargs)
    return row


def history_group(**kwargs):
    row = event(play_duration=1800, percent_complete=75, group_count=2, group_ids='100,101')
    row.update(kwargs)
    return row


@pytest.mark.parametrize('address', ['192.0.2.1', '2001:db8::1'])
def test_source_identity_and_context_mapping(address):
    values, supplied = sessions.map_session(event(ip_address=address, player=' TV ', session_id=42))
    assert values['source_event_id'] == 100 and values['source_reference_id'] == 77
    assert values['ip_address'] == address and values['player'] == 'TV'
    assert values['session_id'] == '42'
    assert supplied == {'ip_address', 'player', 'session_id'}


@pytest.mark.parametrize('value', ['', ' ', [], {}, True, 'bad', '192.0.2.1/24', 'fe80::1%eth0'])
def test_malformed_ip_is_not_persisted(value):
    values, supplied = sessions.map_session(event(ip_address=value))
    assert values['ip_address'] is None and 'ip_address' not in supplied


def test_persistence_rejects_wrong_source_semantics():
    with pytest.raises(ValueError, match='ungrouped'):
        sessions.map_session(history_group())
    with pytest.raises(ValueError, match='grouping=1'):
        grouped.persist_grouped_history(None, None, [event()], source_grouping=0)
    assert grouped.group_members(history_group()) == [100, 101]
    assert grouped.group_members(history_group(group_ids='100,bad')) is None


def test_each_path_sets_its_own_grouping_and_detects_pagination_drift():
    calls = []
    def fetch(command, params):
        calls.append(params)
        return dict(recordsFiltered=2, data=[event(100+params['start'])])
    assert len(list(grouped.iter_history_pages(fetch, grouping=0, page_size=10))) == 2
    assert calls[1]['start'] == 1 and calls[0]['grouping'] == 0
    assert calls[0]['include_activity'] == 0
    calls.clear()
    list(grouped.iter_history_pages(fetch, grouping=1, page_size=10))
    assert all(p['grouping'] == 1 for p in calls)
    with pytest.raises(RuntimeError):
        list(grouped.iter_history_pages(lambda *a: dict(recordsFiltered=3, data=[event()]), grouping=0, page_size=1))


def test_api_metadata_filters_and_privacy_contract():
    app = FastAPI()
    app.include_router(agent_tools.router, prefix='/api/agent')
    row = dict(make_history_row(), player='TV', platform='Linux', product='Plex', device='HTPC',
               platform_version='1', product_version='2', ip_address='192.0.2.99', session_id='secret')
    conn = FakeConnection([row])
    with TestClient(app) as client, patch.object(service, 'connect_db', return_value=conn):
        response = client.get('/api/agent/watch-history', params=dict(user='fixture', player='TV', platform='Linux', device='HTPC'))
    assert response.status_code == 200
    payload = response.json()['results'][0]
    assert payload['device'] == 'HTPC' and payload['product_version'] == '2'
    assert 'ip_address' not in payload and 'session_id' not in payload
    sql, params = conn.cursor_obj.executed[0]
    assert params == ['fixture', 'TV', 'Linux', 'HTPC', 51, 0]
    assert 'watch_history_playback_v' in sql
    assert 'ip_address' not in sql and 'session_id' not in sql


@pytest.fixture
def database():
    dsn = os.getenv('WATCH_HISTORY_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('WATCH_HISTORY_TEST_DATABASE_URL must name the isolated session fixture')
    if psycopg2.extensions.parse_dsn(dsn).get('dbname') != 'plexintel_watch_fixture':
        pytest.fail('Refusing any database except plexintel_watch_fixture')
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        cur.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public; REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        cur.execute('''CREATE TABLE watch_history (
            watch_id integer PRIMARY KEY, username text, title text, media_type text,
            watched_at timestamp, played_duration integer, percent_complete double precision,
            rating_key integer, show_rating_key integer, episode_title text,
            season_number integer, episode_number integer, friendly_name text);
            CREATE TABLE library (rating_key integer PRIMARY KEY, duration integer, media_type text,
              title text, show_title text, episode_title text, summary text, episode_summary text,
              year integer, rating text, season_number integer, episode_number integer);
            CREATE TABLE media_embeddings (rating_key integer PRIMARY KEY, embedding double precision[]);
            CREATE TABLE watch_embeddings (watch_id integer PRIMARY KEY, embedding double precision[]);
            CREATE TABLE recommendations (username text, rating_key integer, predicted_probability double precision);
            CREATE TABLE user_feedback (id integer, username text, rating_key integer, feedback text,
              modified_at timestamp, created_at timestamp);
            CREATE TABLE genres (id integer,name text); CREATE TABLE media_genres (media_id integer,genre_id integer);
            CREATE TABLE actors (id integer,name text); CREATE TABLE media_actors (media_id integer,actor_id integer,cast_order integer);
            CREATE TABLE directors (id integer,name text); CREATE TABLE media_directors (media_id integer,director_id integer);
            INSERT INTO library(rating_key,duration,media_type,title,year) VALUES (500,2400000,'movie','Movie',2020),(501,2400000,'movie','Other',2020);
            INSERT INTO watch_history(watch_id,username,title,media_type,watched_at,played_duration,percent_complete,rating_key)
              VALUES (100,'fixture','Movie','movie','2026-01-01',1800,75,500),(200,'fixture','Other','movie','2026-01-02',250,10,501);
            INSERT INTO recommendations VALUES ('fixture',500,.9),('fixture',501,.8);
            CREATE VIEW watch_history_enriched_v AS
              SELECT w.watch_id,w.username,w.friendly_name,w.rating_key,w.watched_at,w.played_duration,
              l.duration AS media_duration, w.played_duration::numeric / (l.duration/1000.0) AS percent_complete,
              w.played_duration >= l.duration/2000.0 AS engaged,w.media_type,l.show_title,w.title,
              w.season_number,w.episode_number,l.summary,l.rating,l.year,
              NULL::text AS genres,NULL::text AS actors,NULL::text AS directors
              FROM watch_history w JOIN library l USING (rating_key);
            CREATE VIEW fixture_dependent AS SELECT * FROM watch_history_enriched_v;
            CREATE MATERIALIZED VIEW fixture_materialized AS SELECT * FROM fixture_dependent;
            GRANT SELECT(watch_id) ON watch_history_enriched_v TO PUBLIC;
        ''')
        cur.execute('INSERT INTO media_embeddings VALUES (500,%s),(501,%s)', ([1.0]+[0.0]*767,[0.0,1.0]+[0.0]*766))
        cur.execute('INSERT INTO watch_embeddings VALUES (100,%s)', ([0.5]+[0.0]*767,))
        conn.commit()
        before_migration = model_snapshot(conn)
        cur.execute("SELECT oid,pg_get_viewdef(oid),relowner,relacl::text FROM pg_class WHERE oid='watch_history_enriched_v'::regclass")
        original_view = cur.fetchone()
        cur.execute(MIGRATION)
        cur.execute("SELECT oid,pg_get_viewdef(oid),relowner,relacl::text FROM pg_class WHERE oid='watch_history_enriched_v'::regclass")
        assert cur.fetchone() == original_view
        cur.execute(ROLES)
        cur.execute('''DO $$ BEGIN
          IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='watch_fixture_ingest') THEN
            CREATE ROLE watch_fixture_ingest LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
          END IF;
          IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='watch_fixture_reader') THEN
            CREATE ROLE watch_fixture_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
          END IF;
        END $$;
        GRANT plexintel_session_writer TO watch_fixture_ingest;
        GRANT plexintel_history_reader TO watch_fixture_reader;
        ''')
    conn.commit()
    assert model_snapshot(conn) == before_migration
    worker = psycopg2.connect(dsn, user='watch_fixture_ingest')
    yield conn, worker, dsn
    worker.rollback(); worker.close(); conn.rollback(); conn.close()


def persist(worker, rows, **kwargs):
    with worker.cursor() as cur:
        result = sessions.persist_sessions(cur, rows, **kwargs)
    worker.commit()
    return result


def sql_constants(path, needle):
    return next(n.value for n in ast.walk(ast.parse(Path(path).read_text()))
                if isinstance(n, ast.Constant) and isinstance(n.value,str) and needle in n.value)


def model_snapshot(conn):
    # Execute SQL directly from the actual production sources; never invoke model jobs.
    queries = {
        'history': 'SELECT * FROM watch_history ORDER BY watch_id',
        'training': sql_constants('build_training_data.py', 'watch_agg AS'),
        'watch_vectors': sql_constants('build_training_data.py', 'we.embedding AS watch_embedding'),
        'pending_watch_embeddings': sql_constants('fetch_tautulli_data.py', 'COALESCE(l.media_type, wh.media_type)'),
    }
    exclusion = Path('api/db/migrations/002_dimension_explanation_view.sql').read_text().split('  WHERE NOT EXISTS (',1)[1]
    queries['recommendation_exclusion'] = ('SELECT r.username,r.rating_key,r.predicted_probability FROM recommendations r JOIN library m USING(rating_key) WHERE NOT EXISTS (' + exclusion)
    result = {}
    with conn.cursor() as cur:
        for name, sql in queries.items():
            cur.execute(sql)
            result[name] = sorted(cur.fetchall(), key=repr)
    profiles = fetch_profile_title_rows(conn)
    result['profiles_sql'] = profiles
    result['profile_embeddings'] = {k:p.mean.tolist() for k,p in build_user_profiles(profiles,engagement_threshold=.5).items()}
    conn.rollback()
    return result


def mock_source(rows, groups=None):
    def fetch(command, params):
        source = rows if params['grouping']==0 else (groups or [history_group()])
        return dict(recordsFiltered=len(source),data=source[params['start']:params['start']+params['length']])
    return fetch


def test_raw_backfill_preserves_model_sql_results_and_grouped_rows(database):
    admin, worker, _ = database
    before = model_snapshot(admin)
    with admin.cursor() as cur:
        cur.execute("SELECT pg_get_viewdef('watch_history_enriched_v'),relowner,relacl::text FROM pg_class WHERE oid='watch_history_enriched_v'::regclass")
        view_before = cur.fetchone()
    admin.rollback()
    rows = [event(player='Old TV'), event(101,player='New TV',started=int((NOW-timedelta(minutes=50)).timestamp())),event(301,reference_id=None)]
    stats = sessions.ingest_sessions(worker,fetch=mock_source(rows))
    assert stats['inserted']==3 and stats['errors']==stats['failed']==0
    assert model_snapshot(admin)==before
    assert sessions.ingest_sessions(worker,fetch=mock_source(rows))['unchanged']==3
    assert model_snapshot(admin)==before
    with admin.cursor() as cur:
        cur.execute('SELECT watch_id,player FROM watch_history_playback_v ORDER BY watch_id')
        assert cur.fetchall()==[(100,'New TV'),(200,None)]
        cur.execute('SELECT watch_id,source_event_id FROM watch_session_memberships ORDER BY source_event_id')
        assert cur.fetchall()==[(100,100),(100,101)]
        cur.execute(MIGRATION);cur.execute(MIGRATION)
        cur.execute("SELECT pg_get_viewdef('watch_history_enriched_v'),relowner,relacl::text FROM pg_class WHERE oid='watch_history_enriched_v'::regclass")
        assert cur.fetchone()==view_before
        cur.execute('SELECT count(*) FROM fixture_materialized')
        assert cur.fetchone()==(2,)
    admin.commit()
    assert model_snapshot(admin)==before


def test_grouped_updates_match_legacy_contract_and_raw_writes_are_denied(database):
    admin, worker, _ = database
    with admin.cursor() as cur:
        stats=grouped.persist_grouped_history(admin,cur,[history_group()],source_grouping=1)
        assert stats['updated']==1  # Same aggregate; only source watch time differs.
        cur.execute('SELECT played_duration FROM watch_history WHERE watch_id=100')
        assert cur.fetchone()==(1800,)
        corrected=history_group(play_duration=1900)
        assert grouped.persist_grouped_history(admin,cur,[corrected],source_grouping=1)['updated']==1
        cur.execute('SELECT played_duration FROM watch_history WHERE watch_id=100')
        assert cur.fetchone()==(1900,)
    admin.commit()
    with worker.cursor() as cur:
        sessions.require_session_writer(cur)
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute('UPDATE watch_history SET played_duration=1 WHERE watch_id=100')
    worker.rollback()
    with admin.cursor() as cur, pytest.raises(RuntimeError,match='non-privileged'):
        sessions.require_session_writer(cur)
    admin.rollback()


def test_raw_upsert_identity_null_enrichment_and_savepoints(database):
    admin, worker, _ = database
    assert persist(worker,[event()])['inserted']==1
    assert persist(worker,[event(player='TV')])['updated']==1
    assert persist(worker,[event(player='TV')])['unchanged']==1
    assert persist(worker,[event(player='')])['unchanged']==1
    assert persist(worker,[event(player=None)])['updated']==1
    assert persist(worker,[event(rating_key=501)])['skipped']==1
    assert persist(worker,[event(101,play_duration=2**63)])['failed']==1
    with admin.cursor() as cur:
        cur.execute('SELECT count(*),max(played_duration) FROM watch_sessions')
        assert cur.fetchone()==(1,900)
        cur.execute('SELECT played_duration FROM watch_history WHERE watch_id=100')
        assert cur.fetchone()==(1800,)


def test_ip_disabled_by_default_and_retention_cannot_be_bypassed(database):
    admin, worker, _ = database
    assert persist(worker,[event(ip_address='192.0.2.1')])['inserted']==1
    with admin.cursor() as cur:
        cur.execute('SELECT ip_address,ip_suppressed_at IS NOT NULL FROM watch_sessions WHERE source_event_id=100')
        assert cur.fetchone()==(None,True)
        cur.execute('UPDATE watch_session_policy SET ip_retention_days=2')
    admin.commit()
    persist(worker,[event(ip_address='192.0.2.1')])  # Opt-out suppression survives enablement.
    old=event(101,date=int((NOW-timedelta(days=3)).timestamp()),started=int((NOW-timedelta(days=3)).timestamp()),ip_address='2001:db8::1')
    persist(worker,[old,event(102,ip_address='2001:db8::2')])
    persist(worker,[old,event(101,ip_address='2001:db8::1')])  # Timestamp correction cannot resurrect IP.
    with admin.cursor() as cur:
        cur.execute('SELECT source_event_id,ip_address::text FROM watch_sessions ORDER BY source_event_id')
        assert cur.fetchall()==[(100,None),(101,None),(102,'2001:db8::2/128')]
        cur.execute('UPDATE watch_sessions SET ip_address=NULL WHERE source_event_id=102')
    admin.commit()
    persist(worker,[event(102,ip_address='2001:db8::2')])
    with admin.cursor() as cur:
        cur.execute('SELECT ip_address FROM watch_sessions WHERE source_event_id=102')
        assert cur.fetchone()==(None,)
    persist(worker,[old])  # Restore the source watch timestamp after the correction probe.
    assert persist(worker,[old])['unchanged']==1


def test_repeat_historical_ingestion_suppresses_expired_ips_and_dry_run_is_read_only(database):
    admin,worker,_=database
    with admin.cursor() as cur:
        cur.execute('UPDATE watch_session_policy SET ip_retention_days=2')
    admin.commit()
    old=event(date=int((NOW-timedelta(days=3)).timestamp()),started=int((NOW-timedelta(days=3)).timestamp()),ip_address='192.0.2.1')
    before=model_snapshot(admin)
    stats=sessions.ingest_sessions(worker,fetch=mock_source([old]),dry_run=True)
    assert stats['inserted']==1 and stats['errors']==0
    with admin.cursor() as cur:
        cur.execute('SELECT count(*) FROM watch_sessions');assert cur.fetchone()==(0,)
    admin.rollback()
    assert sessions.ingest_sessions(worker,fetch=mock_source([old]))['inserted']==1
    assert sessions.ingest_sessions(worker,fetch=mock_source([old]))['unchanged']==1
    assert model_snapshot(admin)==before
    with admin.cursor() as cur:
        cur.execute('SELECT ip_address FROM watch_sessions');assert cur.fetchone()==(None,)


def test_view_representation_filters_and_reader_privileges(database,monkeypatch):
    admin,worker,dsn=database
    rows=[event(player='A'),event(101,player='B')]
    assert sessions.ingest_sessions(worker,fetch=mock_source(rows))['errors']==0
    # Same timestamp tie resolves to highest source ID, never row duplication.
    monkeypatch.setenv('WATCH_HISTORY_DATABASE_URL', psycopg2.extensions.make_dsn(dsn,user='watch_fixture_reader'))
    result=service.get_agent_watch_history(user='fixture',player='B')
    assert result.count==1 and result.results[0].watch_id==100
    assert result.results[0].played_duration==1800
    assert service.get_agent_watch_history(player='A').count==0
    assert service.get_agent_watch_history().count==2
    reader=psycopg2.connect(dsn,user='watch_fixture_reader')
    try:
        with reader.cursor() as cur,pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute('SELECT ip_address FROM watch_sessions')
    finally:
        reader.rollback();reader.close()


def test_memberships_require_explicit_correct_identity_and_are_repeatable(database):
    admin,worker,_=database
    persist(worker,[event(),event(101,user='other'),event(300,reference_id=100)])
    with worker.cursor() as cur:
        assert sessions.reconcile_memberships(cur,[history_group()])==1
        assert sessions.reconcile_memberships(cur,[history_group()])==0
        assert sessions.reconcile_memberships(cur,[dict(history_group(),id=999,group_ids='999,300')])==0
        cur.execute('SELECT source_event_id FROM watch_session_memberships')
        assert cur.fetchall()==[(100,)]
    worker.rollback()


def test_retention_sweep_is_durable_and_role_cannot_undo_it(database):
    admin,worker,_=database
    old=event(started=int((NOW-timedelta(days=3)).timestamp()),ip_address='192.0.2.1')
    with admin.cursor() as cur:
        cur.execute('UPDATE watch_session_policy SET ip_retention_days=5')
    admin.commit()
    persist(worker,[old])
    with admin.cursor() as cur:
        cur.execute('SELECT ip_address IS NOT NULL FROM watch_sessions');assert cur.fetchone()==(True,)
        cur.execute('UPDATE watch_session_policy SET ip_retention_days=2')
    admin.commit()
    with worker.cursor() as cur:
        assert sessions.purge_expired_ips(cur)==1
    worker.commit()
    assert persist(worker,[old])['unchanged']==1
    with worker.cursor() as cur:
        cur.execute('SELECT ip_address,ip_suppressed_at IS NOT NULL FROM watch_sessions')
        assert cur.fetchone()==(None,True)
        for statement in ('UPDATE watch_session_policy SET ip_retention_days=365',
                          'DELETE FROM watch_sessions', 'ALTER TABLE watch_sessions DISABLE TRIGGER ALL'):
            cur.execute('SAVEPOINT denied_action')
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute(statement)
            cur.execute('ROLLBACK TO SAVEPOINT denied_action')
            cur.execute('RELEASE SAVEPOINT denied_action')
    worker.rollback()


def test_missing_start_suppresses_ip_even_if_watch_date_is_recent(database):
    admin,worker,_=database
    with admin.cursor() as cur:
        cur.execute('UPDATE watch_session_policy SET ip_retention_days=2')
    admin.commit()
    persist(worker,[event(started=None,ip_address='192.0.2.1')])
    persist(worker,[event(ip_address='192.0.2.1')])
    with worker.cursor() as cur:
        cur.execute('SELECT ip_address,ip_suppressed_at IS NOT NULL FROM watch_sessions')
        assert cur.fetchone()==(None,True)
    worker.rollback()


def test_interrupted_session_backfill_commits_only_successful_pages(database):
    admin,worker,_=database
    before=model_snapshot(admin)
    def fetch(command,params):
        if params['grouping']==1:
            return dict(recordsFiltered=1,data=[history_group()])
        if params['start']:
            raise KeyboardInterrupt
        return dict(recordsFiltered=2,data=[event()])
    stats=sessions.ingest_sessions(worker,fetch=fetch,page_size=1)
    assert stats['inserted']==stats['errors']==1
    assert model_snapshot(admin)==before
    stats=sessions.ingest_sessions(worker,fetch=mock_source([event(),event(101)]),page_size=1)
    assert stats['inserted']==stats['unchanged']==1 and stats['errors']==0
    assert model_snapshot(admin)==before


def test_source_group_changes_cannot_reassociate_other_users_or_invent_history(database):
    admin,worker,_=database
    rows=[event(900,reference_id=77)]
    # Same media/reference as an existing group is insufficient evidence.
    stats=sessions.ingest_sessions(worker,fetch=mock_source(rows,groups=[history_group()]))
    assert stats['inserted']==1 and stats['linked']==0 and stats['errors']==0
    with worker.cursor() as cur:
        cur.execute('SELECT count(*) FROM watch_session_memberships');assert cur.fetchone()==(0,)
    worker.rollback()
    with admin.cursor() as cur:
        cur.execute('SELECT watch_id,played_duration FROM watch_history ORDER BY watch_id')
        assert cur.fetchall()==[(100,1800),(200,250)]


def test_missing_optional_start_preserves_existing_retained_ip(database):
    admin,worker,_=database
    with admin.cursor() as cur:
        cur.execute('UPDATE watch_session_policy SET ip_retention_days=2')
    admin.commit()
    persist(worker,[event(ip_address='192.0.2.1')])
    assert persist(worker,[event(started=None)])['unchanged']==1
    with worker.cursor() as cur:
        cur.execute('SELECT ip_address::text,ip_suppressed_at FROM watch_sessions')
        assert cur.fetchone()==('192.0.2.1/32',None)
    worker.rollback()
