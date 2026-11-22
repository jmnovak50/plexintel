"""Acceptance contract on disposable PostgreSQL; never an operator database."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pytest

from api.services import metadata_ingestion as m, metadata_collection as c

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    dsn=os.environ.get('PLEXINTEL_METADATA_TEST_DSN')
    if not dsn: pytest.skip('Requires a private disposable metadata PostgreSQL cluster')
    admin=psycopg2.connect(dsn); params=admin.get_dsn_parameters()
    if not params['host'].startswith('/tmp/plexintel-metadata-pg-'):
        admin.close(); pytest.fail('Refusing non-disposable PostgreSQL host')
    admin.autocommit=True; name='metadata_'+uuid4().hex
    with admin.cursor() as q: q.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    params['dbname']=name; conn=psycopg2.connect(**params)
    try:
        with conn.cursor() as q:
            q.execute('''CREATE TABLE library(rating_key integer PRIMARY KEY,title text,year integer,duration integer,
                added_at timestamp,media_type text,rating text,summary text,season_number integer,episode_number integer,
                parent_rating_key integer,show_title text,episode_title text,episode_summary text,show_rating_key integer,
                thumb_path text,parent_thumb_path text,grandparent_thumb_path text,plex_guid text);
                CREATE TABLE actors(id serial PRIMARY KEY,name text UNIQUE);
                CREATE TABLE directors(id serial PRIMARY KEY,name text UNIQUE);
                CREATE TABLE genres(id serial PRIMARY KEY,name text UNIQUE);
                CREATE TABLE media_actors(media_id integer REFERENCES library,actor_id integer REFERENCES actors,cast_order integer,PRIMARY KEY(media_id,actor_id));
                CREATE TABLE media_directors(media_id integer REFERENCES library,director_id integer REFERENCES directors,PRIMARY KEY(media_id,director_id));
                CREATE TABLE media_genres(media_id integer REFERENCES library,genre_id integer REFERENCES genres,PRIMARY KEY(media_id,genre_id));
                CREATE TABLE operational_probe(label text);''')
            q.execute((ROOT/'api/db/migrations/optional/metadata_ingestion/001_contract.sql').read_text())
        conn.commit(); yield conn
    finally:
        conn.close()
        with admin.cursor() as q: q.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


def raw(key=1,kind='movie',**extra):
    return dict(rating_key=str(key),title='Fixture '+str(key),media_type=kind,
                guid=f'plex://{kind}/fixture-{key}',duration='5400000' if kind in ('movie','episode') else None,
                summary='Original synopsis',year='2020',added_at='1700000000',
                actors=['Alice','Bob'],genres=['Drama'],directors=['Director'],**extra)


def item(key=1,kind='movie',**extra):
    r=raw(key,kind);r.update(extra);return m.normalize_metadata(key,r)


def accepted(db,value=None):
    value=value or item()
    with db.cursor() as q: result=m.accept(q,value,operation_id=uuid4())
    db.commit(); assert result=='accepted'


def snap(db,key=1):
    with db.cursor() as q:return m.snapshot(q,key)


def scalar(db,query,params=None):
    with db.cursor() as q:q.execute(query,params);return q.fetchone()[0]


def plan(db,**kwargs):
    with db.cursor() as q:return m.make_plan(q,1,operator='fixture-operator',reason='fixture correction',**kwargs)


def test_atomic_acceptance_repeat_and_legacy_unknown(db):
    accepted(db); before=snap(db)
    changed=item(summary='Upstream changed',actors=['Someone Else'])
    with db.cursor() as q:assert m.accept(q,changed,operation_id=uuid4())=='skipped_existing'
    db.commit();assert snap(db)==before
    assert scalar(db,'SELECT count(*) FROM metadata_ingestion_events')==1
    with db.cursor() as q:q.execute("INSERT INTO library(rating_key,title,media_type) VALUES(2,'Legacy','movie')")
    db.commit()
    with db.cursor() as q:assert m.accept(q,item(2),operation_id=uuid4())=='skipped_existing'
    db.commit();assert scalar(db,'SELECT count(*) FROM metadata_ingestion_events WHERE rating_key=2')==0


@pytest.mark.parametrize('change',[{'rating_key':'2'},{'guid':None},{'media_type':'other'},
    {'title':''},{'duration':None},{'actors':{'name':'Not a collection'}},{'year':'bad'}])
def test_incomplete_identity_and_payloads_rejected(change):
    value=raw();value.update(change)
    with pytest.raises(m.MetadataError):m.normalize_metadata(1,value)


def test_optional_empty_unavailable_and_scope(db):
    r=raw(10,'show');r.update(directors=None,year=None,summary=None,actors=[])
    value=m.normalize_metadata(10,r);accepted(db,value)
    assert value['_ingestion_evidence']['presence']['directors']=='unavailable'
    assert value['_ingestion_evidence']['presence']['actors']=='empty'
    assert snap(db,10)['duration'] is None


def test_parent_numeric_zero_normalization_preserves_legacy_nullable_values():
    r=raw(10,'show');r.update(year=0,duration=0)
    value=m.normalize_metadata(10,r)
    assert value['year'] is None and value['duration'] is None
    assert value['_ingestion_evidence']['presence']['duration']=='unavailable'
    assert m.integer(2020.0)==2020
    with pytest.raises(m.MetadataError):m.integer(2020.5)


def test_parent_first_and_zero_indexes(db):
    show=item(10,'show');accepted(db,show)
    season=item(20,'season',parent_rating_key='10',media_index=0);accepted(db,season)
    r=raw(30,'episode');r.update(parent_rating_key='20',grandparent_rating_key='10',
                              parent_media_index=0,media_index=0,actors=[],genres=[])
    ep=m.normalize_metadata(30,r,show=show);accepted(db,ep)
    s=snap(db,30);assert s['season_number']==0 and s['episode_number']==0
    assert ep['_ingestion_evidence']['scopes']['actors']=={'scope':'series','source_key':10}
    assert [x['name'] for x in s['actors']]==['Alice','Bob']


def test_absent_or_wrong_parent_is_not_accepted(db):
    value=item(30,'episode',parent_rating_key=20,grandparent_rating_key=10,parent_media_index=1,media_index=1)
    with pytest.raises(m.MetadataError):
        with db.cursor() as q:m.accept(q,value,operation_id=uuid4())
    db.rollback();assert snap(db,30) is None


@pytest.mark.parametrize('stage',['genres','actors','directors','receipt'])
def test_real_postgres_failure_rolls_back_entire_title(db,monkeypatch,stage):
    original=m._write_relationships
    def injected(q,key,name,values,**kwargs):
        original(q,key,name,values,**kwargs)
        if name==stage: q.execute('SELECT 1/0')
    monkeypatch.setattr(m,'_write_relationships',injected)
    if stage=='receipt':
        def fail(*a,**k):raise RuntimeError('synthetic receipt failure')
        monkeypatch.setattr(m,'_event',fail)
    result=c.store_candidates(db,[item()])
    assert result['accepted']==0 and result['failed']==1
    assert snap(db) is None
    assert scalar(db,'SELECT count(*) FROM actors')==0
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='applied'")==0
    assert result['receipt_failed']==(1 if stage=='receipt' else 0)
    if stage!='receipt':
        assert scalar(db,"SELECT evidence->>'sqlstate' FROM metadata_ingestion_events WHERE outcome='failed'")=='22012'


def test_precommit_disconnect_and_postcommit_replay(db):
    other=psycopg2.connect(db.dsn)
    with other.cursor() as q:m.accept(q,item(),operation_id=uuid4())
    other.close();assert snap(db) is None
    accepted(db)
    p=plan(db,fields={'summary':'Corrected'})
    with db.cursor() as q:assert m.apply_plan(q,p)=='applied'
    db.commit()
    with db.cursor() as q:assert m.apply_plan(q,p)=='replayed'
    db.commit();assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE operation='correct'")==1
    changed=deepcopy(p);changed['fields']['summary']='Different operation'
    with pytest.raises(m.Conflict):
        with db.cursor() as q:m.apply_plan(q,changed)
    db.rollback()


def test_two_connection_ingest_and_correction_races(db):
    other=psycopg2.connect(db.dsn)
    try:
        with db.cursor() as q:m.accept(q,item(),operation_id=uuid4())
        with pytest.raises(m.Busy):
            with other.cursor() as q:m.accept(q,item(actors=['Other']),operation_id=uuid4())
        other.rollback();db.commit()
        with other.cursor() as q:assert m.accept(q,item(actors=['Other']),operation_id=uuid4())=='skipped_existing'
        other.commit()
        p=plan(db,fields={'summary':'First'});p2=plan(db,fields={'summary':'Second'});db.rollback()
        with db.cursor() as q:m.apply_plan(q,p)
        with pytest.raises(m.Busy):
            with other.cursor() as q:m.apply_plan(q,p2)
        other.rollback();db.commit()
        with pytest.raises(m.Conflict,match='stale_preview'):
            with other.cursor() as q:m.apply_plan(q,p2)
        other.rollback();assert snap(db)['summary']=='First'
    finally:other.close()


def test_external_row_lock_is_bounded_and_stricter_caller_timeout_is_preserved(db):
    accepted(db);p=plan(db,fields={'summary':'Should defer'});db.rollback()
    other=psycopg2.connect(db.dsn)
    try:
        with other.cursor() as q:q.execute('SELECT rating_key FROM library WHERE rating_key=1 FOR UPDATE')
        with db.cursor() as q:q.execute("SET LOCAL lock_timeout='50ms'")
        with pytest.raises(psycopg2.errors.LockNotAvailable):
            with db.cursor() as q:m.apply_plan(q,p)
        db.rollback();assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE operation='correct'")==0
    finally:other.rollback();other.close()


def test_explicit_membership_removal_and_scoped_fields(db):
    accepted(db); before=snap(db)
    p=plan(db,fields={'summary':'Corrected'},relationships={'actors':{'action':'remove','values':[before['actors'][0]['id']]}})
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();after=snap(db)
    for field in m.FIELDS:
        if field!='summary':assert after[field]==before[field]
    assert len(after['actors'])==1 and scalar(db,'SELECT count(*) FROM actors')==2
    assert scalar(db,"SELECT changes->'before'->>'summary' FROM metadata_ingestion_events WHERE operation='correct'")=='Original synopsis'
    with pytest.raises(m.Conflict):plan(db,fields={'summary':'Silent overwrite'},mode='complete')
    with pytest.raises(m.MetadataError):plan(db,fields={'rating_key':10})


def test_explicit_empty_not_implicit_membership_deletion(db):
    accepted(db)
    p=plan(db,relationships={'genres':{'action':'replace','values':[]}})
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();assert snap(db)['genres']==[]
    assert len(snap(db)['actors'])==2


def test_guid_only_completion_and_race(db):
    accepted(db)
    with db.cursor() as q:q.execute('UPDATE library SET plex_guid=NULL WHERE rating_key=1')
    db.commit();before=snap(db)
    with db.cursor() as q:p=m.guid_plan(q,1,raw())
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();after=snap(db)
    assert {k:v for k,v in before.items() if k!='plex_guid'}=={k:v for k,v in after.items() if k!='plex_guid'}
    assert after['plex_guid']==raw()['guid']
    wrong=raw();wrong['guid']='plex://movie/different'
    with pytest.raises(m.Conflict):
        with db.cursor() as q:m.guid_plan(q,1,wrong)


@pytest.mark.parametrize('raw_change',[{'rating_key':2},{'media_type':'show'},{'title':'Reused key'},{'year':2021}])
def test_guid_identity_mismatch(db,raw_change):
    accepted(db)
    with db.cursor() as q:q.execute('UPDATE library SET plex_guid=NULL WHERE rating_key=1')
    db.commit();value=raw();value.update(raw_change)
    with pytest.raises(m.MetadataError):
        with db.cursor() as q:m.guid_plan(q,1,value)


def test_cast_order_repair_never_changes_membership_or_known_orders(db):
    accepted(db)
    with db.cursor() as q:q.execute('UPDATE media_actors SET cast_order=CASE WHEN actor_id=(SELECT id FROM actors WHERE name=\'Alice\') THEN NULL ELSE 5 END')
    db.commit();before=snap(db)
    value=raw();value['actors']=['Alice','Unrelated Person','Bob']
    with db.cursor() as q:p=m.cast_order_plan(q,1,value,operator='fixture',reason='missing order')
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();after=snap(db)
    assert [(x['id'],x['name']) for x in after['actors']]==[(x['id'],x['name']) for x in before['actors']]
    assert [x['cast_order'] for x in after['actors']]==[0,5]
    assert scalar(db,'SELECT count(*) FROM actors')==2


def test_order_alias_applies_only_reviewed_values_without_refetch(db):
    from scripts.correct_metadata import order_repairs
    accepted(db)
    with db.cursor() as q:q.execute("UPDATE media_actors SET cast_order=NULL WHERE actor_id=(SELECT id FROM actors WHERE name='Alice')")
    db.commit()
    with db.cursor() as q:p=m.cast_order_plan(q,1,raw(),operator='fixture',reason='Reviewed order')
    db.rollback()
    def forbidden(*a,**kw):raise AssertionError('apply must not refetch source or regenerate preview')
    a=SimpleNamespace(connect_db=lambda:psycopg2.connect(db.dsn),fetch_tautulli_data=forbidden)
    with pytest.raises(m.MetadataError,match='reviewed_plan_required'):
        order_repairs(a,rating_keys=[1],operator='fixture',reason='Reviewed order',apply=True)
    order_repairs(a,rating_keys=[1],operator='fixture',reason='Reviewed order',apply=False,plans=[p])
    assert snap(db)['actors'][0]['cast_order'] is None
    order_repairs(a,rating_keys=[1],operator='fixture',reason='Reviewed order',apply=True,plans=[p])
    db.rollback();assert snap(db)['actors'][0]['cast_order']==0


def test_order_collision_requires_explicit_reorder(db):
    accepted(db)
    with db.cursor() as q:q.execute("UPDATE media_actors SET cast_order=NULL WHERE actor_id=(SELECT id FROM actors WHERE name='Bob')")
    db.commit();value=raw();value['actors']=['Bob','Alice','Not a member']
    with pytest.raises(m.Conflict):
        with db.cursor() as q:m.cast_order_plan(q,1,value,operator='fixture',reason='missing')
    with db.cursor() as q:p=m.cast_order_plan(q,1,value,operator='fixture',reason='reviewed reorder',reorder=True)
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();assert scalar(db,'SELECT count(*) FROM actors')==2


@pytest.mark.parametrize('factory',[None,RealDictCursor])
def test_feedback_repair_failure_savepoint_preserves_caller(db,monkeypatch,factory):
    from api.services import library_service
    accepted(db)
    with db.cursor() as q:q.execute('UPDATE library SET plex_guid=NULL WHERE rating_key=1; DROP TABLE metadata_ingestion_events')
    db.commit();monkeypatch.setattr(library_service,'fetch_tautulli_metadata',lambda key:raw())
    with db.cursor(cursor_factory=factory) as q:
        q.execute("INSERT INTO operational_probe VALUES('feedback caller remains pending')")
        result=library_service.ensure_library_guid(q,1)
    assert result['plex_guid'] is None
    db.commit();assert scalar(db,'SELECT count(*) FROM operational_probe')==1
    assert snap(db)['plex_guid'] is None


@pytest.mark.parametrize('payloads',[
    [{'data':[{'rating_key':1},{'rating_key':2}]},{}],
    [{'data':[{'rating_key':1},{'rating_key':2}]},{'data':[{'rating_key':2}]}],
    [{'data':[{'rating_key':1}], 'recordsFiltered':3}],
    [{'data':[{'rating_key':1},{'rating_key':2}],'recordsFiltered':4},{'data':[],'recordsFiltered':3}],
])
def test_discovery_partial_failure_not_complete(payloads):
    values=iter(payloads)
    with pytest.raises(c.DiscoveryError):c.pages(lambda *a:next(values),'endpoint',{},'data',2)


def test_valid_discovery_total_and_missing_headers(db):
    values=iter([{'data':[{'rating_key':1},{'rating_key':2}],'recordsFiltered':3},{'data':[{'rating_key':3}],'recordsFiltered':3}])
    assert len(c.pages(lambda *a:next(values),'endpoint',{},'data',2))==3
    with db.cursor() as q:
        q.execute("INSERT INTO library(rating_key,media_type,parent_rating_key,show_rating_key) VALUES(30,'episode',20,10)")
        assert set(c.missing_headers(q))=={(20,'season'),(10,'show')}


def adapter(db, *, invalid=False):
    def get_metadata(key,**kwargs):
        value=raw(key)
        if invalid:value['guid']=None
        return m.normalize_metadata(key,value)
    def users(conn,q):q.execute("INSERT INTO operational_probe VALUES('users')")
    def history(conn,q):q.execute("INSERT INTO operational_probe VALUES('history')");conn.commit();return True
    return SimpleNamespace(connect_db=lambda:psycopg2.connect(db.dsn),_METADATA_CACHE={},_METADATA_DRY_RUN=False,
        get_library_media_info=lambda section_id:[{'rating_key':1,'media_type':'movie'}] if section_id==1 else [],
        get_children_metadata=lambda key:[],get_metadata=get_metadata,
        clear_tautulli_cache=lambda:None,sync_users_from_tautulli=users,sync_new_watch_history=history,
        get_watch_history=lambda:[],store_watch_history=lambda conn,q,rows,**kw:history(conn,q))


def test_history_and_users_commit_even_when_metadata_fails(db,capsys):
    with pytest.raises(m.MetadataError):c.run(adapter(db,invalid=True),mode='full')
    db.rollback();assert scalar(db,'SELECT count(*) FROM operational_probe')==2
    assert snap(db) is None
    assert '"history": "committed"' in capsys.readouterr().out


def test_readonly_preview_no_receipt_schema_sequences_or_writes(db):
    with db.cursor() as q:q.execute('DROP TABLE metadata_ingestion_events')
    db.commit();a=adapter(db)
    result=c.run(a,mode='full',dry_run=True)
    assert result['metadata']['previewed']==1
    db.rollback();assert scalar(db,'SELECT count(*) FROM library')==0
    assert scalar(db,'SELECT count(*) FROM operational_probe')==0
    assert scalar(db,'SELECT is_called FROM actors_id_seq') is False


def test_full_and_incremental_history_modes_keep_their_original_scope(db):
    a=adapter(db);a.get_library_media_info=lambda section_id:[]
    full_calls=[];incremental_calls=[]
    a.get_watch_history=lambda:full_calls.append('all_history') or []
    a.store_watch_history=lambda conn,cur,rows,**kw:full_calls.append('persist_grouped')
    a.sync_new_watch_history=lambda conn,cur:incremental_calls.append('bounded_window') or True
    c.run(a,mode='full');assert full_calls==['all_history','persist_grouped'] and incremental_calls==[]
    c.run(a,mode='incremental');assert incremental_calls==['bounded_window']


def test_importer_cli_no_args_is_readonly_and_failed_collection_exits_nonzero(db):
    env={**os.environ,'DATABASE_URL':db.dsn}
    noargs=subprocess.run([sys.executable,'fetch_tautulli_data.py'],cwd=ROOT,env=env,capture_output=True,text=True)
    assert noargs.returncode==2
    script='''import fetch_tautulli_data as f
from api.services.metadata_ingestion import MetadataError
def fail(**kwargs): raise MetadataError('synthetic_coverage_failure')
f.main=fail
raise SystemExit(f.cli(['--mode','full']))
'''
    failed=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True)
    assert failed.returncode==1 and 'Importer failed: MetadataError' in failed.stderr


def test_optional_migration_not_in_startup_glob():
    assert not any('metadata_ingestion_events' in x.read_text() for x in (ROOT/'api/db/migrations').glob('*.sql'))
    assert 'metadata_ingestion_events' in (ROOT/'create.sql').read_text()
    for name in ['run_daily_pipeline.sh','api/services/pipeline_service.py']:
        assert 'fetch_tautulli_data.py.bk' not in (ROOT/name).read_text()


def test_wrong_response_rejected_before_parent_requests(monkeypatch):
    import fetch_tautulli_data as f
    f._METADATA_CACHE.clear();calls=[]
    def fetch(endpoint,params):
        calls.append(params['rating_key'])
        return {'rating_key':2,'media_type':'episode','grandparent_rating_key':999}
    monkeypatch.setattr(f,'fetch_tautulli_data',fetch)
    with pytest.raises(m.MetadataError,match='requested_key_mismatch'):f.get_metadata(1)
    assert calls==[1]


def test_parent_cycle_cannot_cause_unbounded_reads(monkeypatch):
    import fetch_tautulli_data as f
    f._METADATA_CACHE.clear();calls=[]
    def fetch(endpoint,params):
        key=params['rating_key'];calls.append(key)
        return {'rating_key':key,'media_type':'season','parent_rating_key':2 if key==1 else 1}
    monkeypatch.setattr(f,'fetch_tautulli_data',fetch)
    with pytest.raises(m.MetadataError,match='discovered_kind_mismatch'):f.get_metadata(1)
    assert calls==[1,2]


def test_retained_guid_conflict_defers_completion(db):
    accepted(db)
    with db.cursor() as q:
        q.execute("UPDATE library SET plex_guid=NULL WHERE rating_key=1; CREATE TABLE media_embeddings(rating_key integer,provenance jsonb)")
        q.execute("INSERT INTO media_embeddings VALUES(1,%s)",(json.dumps({'source':{'plex_guid':'plex://movie/previous-identity'}}),))
    db.commit()
    with pytest.raises(m.Conflict,match='retained_identity_conflict'):
        with db.cursor() as q:m.guid_plan(q,1,raw())


def test_receipt_status_does_not_certify_legacy_or_downgrade_acceptance(db):
    with db.cursor() as q:
        q.execute("INSERT INTO library(rating_key,title,media_type) VALUES(2,'Legacy','movie')")
        assert m.ingestion_status(q,2)['status']=='historical_unknown'
        m.record_failure(q,3,uuid4(),m.MetadataError('missing_runtime'))
        assert m.ingestion_status(q,3)['status']=='failed_initial'
    db.commit();accepted(db)
    with db.cursor() as q:
        m.record_failure(q,1,uuid4(),m.Conflict('stale_preview'),operation='correct')
        assert m.ingestion_status(q,1)['status']=='accepted'
    db.commit()
    p=plan(db,fields={'summary':'Reviewed correction'})
    with db.cursor() as q:
        m.apply_plan(q,p)
        assert m.ingestion_status(q,1)['status']=='corrected'
    db.commit()


@pytest.mark.parametrize('applied',[True,False])
def test_lost_commit_ack_is_resolved_without_false_failure_receipt(db,applied):
    operation=uuid4()
    with db.cursor() as q:m.accept(q,item(),operation_id=operation)
    class LostAcknowledgement:
        dsn=db.dsn
        def commit(self):
            if applied:db.commit()
            else:db.rollback()
            raise psycopg2.OperationalError('synthetic lost acknowledgement')
    with pytest.raises(m.CommitUncertain) as caught:m.commit_metadata(LostAcknowledgement(),1,operation)
    assert caught.value.resolved==('applied' if applied else 'not_applied')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='failed'")==0
    if not applied:assert snap(db) is None
    with db.cursor() as q:status=m.accept(q,item(),operation_id=operation)
    db.commit();assert status==('skipped_existing' if applied else 'accepted')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='applied'")==1


def test_correction_operator_defers_during_predictive_writer(db):
    from scripts.correct_metadata import apply_transaction
    accepted(db);p=plan(db,fields={'summary':'Reviewed'});db.rollback()
    owner=psycopg2.connect(db.dsn)
    try:
        with owner.cursor() as q:q.execute('SELECT pg_advisory_lock(184726,72)')
        with pytest.raises(m.Busy,match='predictive_writer_busy'):apply_transaction(db,p)
        assert snap(db)['summary']=='Original synopsis'
    finally:
        with owner.cursor() as q:q.execute('SELECT pg_advisory_unlock(184726,72)')
        owner.close()


def test_correction_cli_preview_apply_dry_run_and_replay(db,tmp_path):
    accepted(db)
    changes=tmp_path/'changes.json';changes.write_text(json.dumps({'fields':{'summary':'Reviewed via CLI'}}))
    preview=tmp_path/'preview.json';env={**os.environ,'DATABASE_URL':db.dsn}
    def command(*args):return subprocess.run([sys.executable,'scripts/correct_metadata.py',*args],cwd=ROOT,env=env,capture_output=True,text=True)
    prepared=command('preview','--rating-key','1','--changes',str(changes),'--operator','fixture','--reason','Approved fixture','--output',str(preview))
    assert prepared.returncode==0,prepared.stderr
    assert preview.stat().st_mode&0o777==0o600
    dry=command('apply','--plan',str(preview),'--dry-run');assert dry.returncode==0,dry.stderr
    assert snap(db)['summary']=='Original synopsis'
    applied=command('apply','--plan',str(preview));assert applied.returncode==0,applied.stderr
    db.rollback();assert snap(db)['summary']=='Reviewed via CLI'
    again=command('apply','--plan',str(preview));assert again.returncode==0 and 'replayed' in again.stdout
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE operation='correct' AND outcome='applied'")==1
    prepared=json.loads(preview.read_text())
    assert prepared['preview_before']=={'summary':'Original synopsis'}


def test_inverse_plan_restores_scoped_memberships_and_records_new_event(db):
    accepted(db);before=snap(db)
    p=plan(db,fields={'summary':'Changed'},relationships={'actors':{'action':'remove','values':[before['actors'][0]['id']]}})
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();event=scalar(db,"SELECT max(event_id) FROM metadata_ingestion_events WHERE operation='correct'")
    with db.cursor() as q:
        inverse=m.inverse_plan(q,event,operator='fixture',reason='Approved inverse')
        m.apply_plan(q,inverse)
    db.commit();assert snap(db)==before
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE operation='correct' AND outcome='applied'")==2


def test_inverse_missing_guid_repair_preserves_unknown_legacy_state(db):
    with db.cursor() as q:q.execute("INSERT INTO library(rating_key,title,year,media_type) VALUES(1,'Fixture 1',2020,'movie')")
    db.commit()
    with db.cursor() as q:
        p=m.guid_plan(q,1,raw());m.apply_plan(q,p)
    db.commit();event=scalar(db,"SELECT max(event_id) FROM metadata_ingestion_events WHERE outcome='applied'")
    with db.cursor() as q:
        inverse=m.inverse_plan(q,event,operator='fixture',reason='Approved reversal')
        m.apply_plan(q,inverse)
    db.commit();assert snap(db)['plex_guid'] is None
    with db.cursor() as q:assert m.ingestion_status(q,1)['status']=='historical_unknown'


def test_accepted_identity_cannot_be_cleared_and_inverse_rejects_stale_title(db):
    accepted(db)
    with pytest.raises(m.MetadataError):plan(db,fields={'plex_guid':None})
    p=plan(db,fields={'summary':'First edit'})
    with db.cursor() as q:m.apply_plan(q,p)
    db.commit();event=scalar(db,"SELECT max(event_id) FROM metadata_ingestion_events WHERE operation='correct'")
    p2=plan(db,fields={'summary':'Second edit'})
    with db.cursor() as q:m.apply_plan(q,p2)
    db.commit()
    with pytest.raises(m.Conflict,match='title_changed_since_correction'):
        with db.cursor() as q:m.inverse_plan(q,event,operator='fixture',reason='Would be stale')


def test_accepted_fields_match_original_importer_and_predictive_signature(db):
    """Portable old/new replay; original results were recorded on synthetic data."""
    from api.predictive.publication import source_signature
    fixture=json.loads((ROOT/'tests/fixtures/metadata_ingestion_v0.json').read_text())
    with db.cursor() as q:
        q.execute("SET TIME ZONE 'UTC'")
        q.execute('''CREATE TABLE media_embeddings(rating_key integer);
            CREATE TABLE watch_embeddings(watch_id integer);
            CREATE TABLE watch_history(watch_id integer,username text,rating_key integer,watched_at timestamp,played_duration integer,percent_complete double precision);
            CREATE TABLE user_feedback(id integer,username text,rating_key integer,feedback text,suppress boolean,created_at timestamp,modified_at timestamp);''')
    db.commit()
    raws={int(k):v for k,v in fixture['raws'].items()}
    show=m.normalize_metadata(10,raws[10])
    for key in [1,10,20,30]:
        accepted(db,m.normalize_metadata(key,raws[key],show=show if key in [20,30] else None))
    assert m.json_value({str(key):snap(db,key) for key in raws})==fixture['expected_snapshots']
    assert source_signature(db)==fixture['expected_source_signature']


def test_actual_importer_subprocess_history_and_dry_run(db,tmp_path):
    with db.cursor() as q:
        q.execute('''CREATE EXTENSION vector;
            CREATE TABLE watch_history(rating_key integer,watched_at timestamp,played_duration integer,
             percent_complete double precision,watch_id integer PRIMARY KEY,media_type text,username text,title text,
             episode_title text,season_number integer,episode_number integer,friendly_name text,show_rating_key integer);''')
    db.commit()
    # Real CLI/controller/history writer, only the remote source is synthetic.
    script='''import sys,json
import fetch_tautulli_data as f
source=json.loads(sys.argv[1])
f.get_library_media_info=lambda section_id,limit=None: [{'rating_key':1,'media_type':'movie'}] if section_id==1 else []
f.get_children_metadata=lambda key: []
f.fetch_tautulli_data=lambda endpoint,params=None: source
def users(conn,cur): cur.execute("INSERT INTO operational_probe VALUES('users')")
f.sync_users_from_tautulli=users
f.fetch_watch_history_pages=lambda **kwargs: {'ok':True,'rows':[{'id':900,'rating_key':1,'user':'FixtureViewer','title':'Fixture 1','media_type':'movie','date':1700000010,'play_duration':3000,'percent_complete':80,'group_ids':'900','group_count':1}]}
raise SystemExit(f.cli(['--mode','full']+(['--dry-run'] if sys.argv[2]=='preview' else [])))
'''
    env={**os.environ,'DATABASE_URL':db.dsn}
    def run(value,mode):
        return subprocess.run([sys.executable,'-c',script,json.dumps(value),mode],cwd=ROOT,env=env,text=True,capture_output=True)
    preview=run(raw(),'preview');assert preview.returncode==0,preview.stderr+preview.stdout
    assert scalar(db,'SELECT count(*) FROM library')==0
    assert scalar(db,'SELECT count(*) FROM watch_history')==0
    applied=run(raw(),'apply');assert applied.returncode==0,applied.stderr+applied.stdout
    db.rollback();assert scalar(db,'SELECT count(*) FROM watch_history')==1
    before=snap(db);changed=raw();changed['summary']='Upstream changed'
    again=run(changed,'apply');assert again.returncode==0,again.stderr+again.stdout
    db.rollback();assert snap(db)==before
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='applied'")==1
    # A new invalid key has nonzero status while independent history still commits.
    with db.cursor() as q:q.execute('DELETE FROM watch_history; DELETE FROM media_actors; DELETE FROM media_directors; DELETE FROM media_genres; DELETE FROM library')
    db.commit();bad=raw();bad['guid']=None
    failed=run(bad,'apply');assert failed.returncode==1
    assert '"history": "committed"' in failed.stdout
    assert scalar(db,'SELECT count(*) FROM watch_history')==1
    assert snap(db) is None
