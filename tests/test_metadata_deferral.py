"""Missing new-title data defers acceptance; operational/integrity errors stay fatal."""
from copy import deepcopy
from uuid import uuid4
import os
import sys
import subprocess
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from api.services import metadata_ingestion as m, metadata_collection as c
from tests.test_metadata_ingestion import db, raw, item, accepted, scalar, snap, adapter


def source_adapter(db, sources):
    a=adapter(db)
    a.get_library_media_info=lambda section_id:[{'rating_key':key,'media_type':'movie'} for key in sources] if section_id==1 else []
    a.get_metadata=lambda key,**kwargs:m.normalize_metadata(key,sources[key])
    return a


@pytest.mark.parametrize('change,field',[
    ({'guid':None},'guid'),({'guid':''},'guid'),({'guid':'   '},'guid'),({'guid':'local://1'},'guid'),
    ({'duration':None},'duration'),({'duration':''},'duration'),({'duration':'0'},'duration'),
    ({'title':None},'title'),({'title':''},'title'),
])
def test_missing_source_fields_are_explicit_incomplete_errors(change,field):
    value=raw();value.update(change)
    with pytest.raises(m.IncompleteMetadata) as caught:m.normalize_metadata(1,value)
    assert caught.value.field==field and caught.value.rating_key==1


@pytest.mark.parametrize('change',[
    {'guid':'plex://show/wrong-kind'},{'guid':'local://2'},{'guid':'unsupported://1'},
    {'rating_key':'2'},{'media_type':'other'},{'duration':-1},{'duration':False},
    {'duration':'bad'},{'actors':{'name':'bad'}},{'title':123},
])
def test_conflicting_or_malformed_source_is_not_a_deferral(db,change):
    value=raw();value.update(change)
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert snap(db) is None
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==0
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='failed'")==1


def test_partial_acceptance_retry_and_one_time_contract(db,capsys):
    values={1:raw(),2:raw(2)}
    values[1]['guid']='local://1';a=source_adapter(db,values)
    result=c.run(a,mode='full')
    assert result['ok'] and result['status']=='completed_with_deferrals'
    assert result['coverage']=='complete' and result['metadata_coverage']=='partial'
    assert result['metadata']==dict(accepted=1,skipped_existing=0,previewed=0,deferred=1,failed=0,receipt_failed=0)
    assert result['history']==result['users']=='committed' and snap(db,1) is None
    saved=snap(db,2)
    with db.cursor() as q:
        assert m.ingestion_status(q,1)['status']=='deferred_initial'
        q.execute("SELECT reason,evidence FROM metadata_ingestion_events WHERE rating_key=1")
        reason,evidence=q.fetchone()
    assert reason=='unresolved_identity' and evidence['disposition']=='deferred' and evidence['field']=='guid'
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='applied'")==1
    assert 'new title(s) deferred' in capsys.readouterr().out
    # Only the absent title is fetched on retry; a formerly deferred record is
    # certified only after its first complete acceptance.
    values[1]=raw();values[2]['summary']='Upstream changed after acceptance'
    fetched=[]
    def fetch(key,**kw):fetched.append(key);return m.normalize_metadata(key,values[key])
    a.get_metadata=fetch
    retry=c.run(a,mode='full')
    assert fetched==[1] and retry['metadata']['accepted']==1 and retry['metadata']['deferred']==0
    assert snap(db,2)==saved
    with db.cursor() as q:assert m.ingestion_status(q,1)['status']=='accepted'
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='applied'")==2


@pytest.mark.parametrize('column',['parent_media_index','media_index','grandparent_rating_key','parent_rating_key'])
def test_missing_episode_coordinates_and_parents_are_incomplete(column):
    value=raw(30,'episode');value.update(parent_rating_key='20',grandparent_rating_key='10',parent_media_index=1,media_index=2)
    value[column]=''
    with pytest.raises(m.IncompleteMetadata):m.normalize_metadata(30,value)


@pytest.mark.parametrize('preview',[False,True])
@pytest.mark.parametrize('missing_parent',[10,20])
def test_deferred_parent_defers_only_its_new_descendants(db,monkeypatch,preview,missing_parent):
    import fetch_tautulli_data as f
    values={1:raw(),10:raw(10,'show'),20:raw(20,'season'),30:raw(30,'episode')}
    values[missing_parent]['guid']=None;values[20].update(parent_rating_key='10',media_index=1)
    values[30].update(parent_rating_key='20',grandparent_rating_key='10',media_index=1,parent_media_index=1)
    calls=[]
    def fetch(endpoint,params):calls.append(params['rating_key']);return deepcopy(values[params['rating_key']])
    monkeypatch.setattr(f,'fetch_tautulli_data',fetch);monkeypatch.setattr(f,'_METADATA_CACHE',{})
    a=adapter(db);a.get_metadata=f.get_metadata;a._METADATA_CACHE=f._METADATA_CACHE
    a.get_library_media_info=lambda section_id:[{'rating_key':1,'media_type':'movie'}] if section_id==1 else [{'rating_key':10,'media_type':'show'}]
    a.get_children_metadata=lambda key:[{'rating_key':20,'media_type':'season'}] if int(key)==10 else [{'rating_key':30,'media_type':'episode'}]
    result=c.run(a,mode='full',dry_run=preview)
    deferred=3 if missing_parent==10 else 2
    complete=4-deferred
    assert result['ok'] and result['metadata']['deferred']==deferred and result['metadata']['failed']==0
    assert result['metadata']['previewed' if preview else 'accepted']==complete
    assert sorted(calls)==[1,10,20,30]  # No repeated fetch of a known deferred parent.
    assert scalar(db,'SELECT count(*) FROM library')==(0 if preview else complete)
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==(0 if preview else deferred)


def test_readonly_deferral_without_receipt_schema_does_not_advance_sequences(db):
    with db.cursor() as q:q.execute('DROP TABLE metadata_ingestion_events')
    db.commit();value=raw();value['guid']=None
    result=c.run(source_adapter(db,{1:value}),mode='full',dry_run=True)
    assert result['metadata']['deferred']==1 and result['ok']
    assert scalar(db,'SELECT count(*) FROM library')==0
    assert scalar(db,'SELECT count(*) FROM operational_probe')==0
    assert scalar(db,'SELECT is_called FROM actors_id_seq') is False


@pytest.mark.parametrize('table',['media_embeddings','recommendations','training_data','user_feedback'])
def test_existing_predictive_or_feedback_dependency_blocks_deferral(db,table):
    with db.cursor() as q:
        q.execute(f'CREATE TABLE {table}(rating_key integer, marker text)')
        q.execute(f"INSERT INTO {table} VALUES(1,'preserve')")
    db.commit();value=raw();value['guid']=None
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert scalar(db,f'SELECT count(*) FROM {table} WHERE marker=\'preserve\'')==1
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE reason='unsafe_deferral_existing_dependency'")==1
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==0


def test_existing_descendant_and_previous_acceptance_cannot_be_deferred(db):
    with db.cursor() as q:q.execute("INSERT INTO library(rating_key,media_type,parent_rating_key,show_rating_key) VALUES(2,'episode',1,3)")
    db.commit();value=raw();value['guid']=None
    stats=c.ingest_keys(source_adapter(db,{1:value}),db,[(1,'movie')])
    assert stats['failed']==1 and stats['deferred']==0
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE reason='unsafe_deferral_existing_descendants'")==1
    with db.cursor() as q:
        q.execute('DELETE FROM library')
        m._event(q,1,uuid4(),'ingest','applied',operator='fixture',reason='prior_acceptance')
    db.commit()
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE reason='unsafe_deferral_existing_dependency'")==1


def history_tables(db):
    with db.cursor() as q:
        q.execute('''CREATE TABLE media_embeddings(rating_key integer);
            CREATE TABLE watch_history(watch_id integer,username text,rating_key integer,watched_at timestamp,
                played_duration integer,percent_complete double precision);
            CREATE TABLE watch_embeddings(watch_id integer);
            CREATE TABLE user_feedback(id integer,username text,rating_key integer,feedback text,suppress boolean,
                created_at timestamp,modified_at timestamp);
            INSERT INTO watch_history VALUES(900,'fixture',1,'2026-11-01',3000,80);''')
    db.commit()


def test_unembedded_history_is_retained_and_explicitly_quarantined(db):
    from api.predictive.source import read_snapshot
    from api.predictive.history_scope import partition_history
    history_tables(db);value=raw();value['guid']=None
    result=c.run(source_adapter(db,{1:value}),mode='full')
    assert result['ok'] and result['metadata']['deferred']==1
    with db.cursor() as q:q.execute('SELECT * FROM watch_history');before=q.fetchall()
    snapshot=read_snapshot(db);scoped=partition_history(snapshot)
    assert scoped['events']==[] and len(scoped['quarantined_events'])==1
    assert scoped['watch_coverage']['quarantined_watch_events']==1
    assert scoped['watch_coverage']['existing_watch_embeddings_covered']==0
    with db.cursor() as q:q.execute('SELECT * FROM watch_history');assert q.fetchall()==before
    # The existing history policy re-admits the retained event after acceptance.
    accepted(db,item());restored=read_snapshot(db)
    rescoped=partition_history({**scoped,'media':restored['media']})
    assert len(rescoped['events'])==1 and rescoped['quarantined_events']==[]


def test_existing_watch_vector_cannot_disappear_behind_deferral(db):
    history_tables(db)
    with db.cursor() as q:q.execute('INSERT INTO watch_embeddings VALUES(900)')
    db.commit();value=raw();value['guid']=None
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert scalar(db,'SELECT count(*) FROM watch_embeddings')==1
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE reason='unsafe_deferral_existing_watch_vector'")==1


@pytest.mark.parametrize('all_receipts',[False,True])
def test_audit_write_failure_is_fatal(db,monkeypatch,all_receipts):
    original=m._event
    def fail(q,*args,**kw):
        if all_receipts or (kw.get('evidence') or {}).get('disposition')=='deferred':q.execute('SELECT 1/0')
        return original(q,*args,**kw)
    monkeypatch.setattr(m,'_event',fail);value=raw();value['guid']=None
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert snap(db) is None
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==0


@pytest.mark.parametrize('applied',[False,True])
def test_uncertain_deferral_receipt_commit_stops_without_retry(db,monkeypatch,applied):
    class LostAcknowledgement:
        commits=0
        def cursor(self):return db.cursor()
        def rollback(self):db.rollback()
        def commit(self):
            self.commits+=1
            db.commit() if applied else db.rollback()
            raise psycopg2.OperationalError('Synthetic acknowledgement loss')
    conn=LostAcknowledgement();stats=c._stats()
    monkeypatch.setattr(c,'_failure',lambda *a:pytest.fail('Uncertain writes must never be followed by another receipt attempt'))
    with pytest.raises(m.CommitUncertain):
        c._incomplete(conn,1,uuid4(),m.IncompleteMetadata('unresolved_identity',rating_key=1,field='guid'),stats)
    assert conn.commits==1 and stats['deferred']==0
    assert scalar(db,'SELECT count(*) FROM metadata_ingestion_events')==int(applied)
    assert snap(db) is None


def test_concurrent_valid_acceptance_is_preserved_without_false_deferral(db):
    a=adapter(db)
    def get(key,**kwargs):
        accepted(db)
        value=raw();value['guid']=None
        return m.normalize_metadata(key,value)
    a.get_metadata=get
    result=c.run(a,mode='full')
    assert result['ok'] and result['metadata']['skipped_existing']==1 and result['metadata']['deferred']==0
    assert scalar(db,'SELECT count(*) FROM metadata_ingestion_events')==1
    assert snap(db)['plex_guid']=='plex://movie/fixture-1'


def test_deferral_guard_supports_mapping_cursors(db):
    with db.cursor(cursor_factory=RealDictCursor) as q:
        assert m.record_deferral(q,1,uuid4(),m.IncompleteMetadata('missing_runtime',rating_key=1,field='duration'))=='deferred'
    db.commit()
    with db.cursor(cursor_factory=RealDictCursor) as q:assert m.ingestion_status(q,1)['status']=='deferred_initial'


def test_incomplete_discovery_and_remote_errors_stay_fatal(db):
    a=adapter(db)
    def discovery(**kwargs):raise c.DiscoveryError('truncated_discovery')
    a.get_library_media_info=discovery
    with pytest.raises(m.MetadataError):c.run(a,mode='full')
    a=adapter(db)
    def remote(*args,**kwargs):raise RuntimeError('Synthetic remote failure')
    a.get_metadata=remote
    with pytest.raises(m.MetadataError):c.run(a,mode='full')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==0


def test_real_cli_exits_success_with_audited_deferral_and_later_accepts(db):
    with db.cursor() as q:q.execute('CREATE EXTENSION vector')
    db.commit()
    script="""import sys,json
import fetch_tautulli_data as f
source=json.loads(sys.argv[1])
f.get_library_media_info=lambda section_id,limit=None:[{'rating_key':1,'media_type':'movie'}] if section_id==1 else []
f.get_children_metadata=lambda key:[]
f.fetch_tautulli_data=lambda *args,**kwargs:source
f.sync_users_from_tautulli=lambda conn,cur:cur.execute("INSERT INTO operational_probe VALUES('users')")
f.get_watch_history=lambda:[]
f.store_watch_history=lambda conn,cur,rows,**kw:cur.execute("INSERT INTO operational_probe VALUES('history')")
raise SystemExit(f.cli(['--mode','full']))
"""
    value=raw();value['guid']='local://1'
    def run(source):
        return subprocess.run([sys.executable,'-c',script,json.dumps(source)],cwd=Path(__file__).resolve().parents[1],
            env={**os.environ,'DATABASE_URL':db.dsn},capture_output=True,text=True)
    deferred=run(value)
    assert deferred.returncode==0,deferred.stdout+deferred.stderr
    assert 'completed_with_deferrals' in deferred.stdout and 'new title(s) deferred' in deferred.stdout
    assert snap(db) is None
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==1
    applied=run(raw());assert applied.returncode==0,applied.stdout+applied.stderr
    db.rollback();assert snap(db) is not None
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE outcome='applied'")==1


@pytest.mark.parametrize('change',[
    {'guid':'local://1','actors':{}}, {'guid':None,'duration':'bad'},
    {'guid':None,'year':'bad'}, {'title':'','guid':'plex://show/wrong-kind'},
    {'duration':None,'directors':False},
])
def test_missing_fields_do_not_hide_malformed_or_conflicting_fields(db,change):
    value=raw();value.update(change)
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==0


def test_existing_watch_table_without_history_has_unknown_dependency_coverage(db):
    with db.cursor() as q:q.execute('CREATE TABLE watch_embeddings(watch_id integer)')
    db.commit();value=raw();value['guid']=None
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE reason='unsafe_deferral_unknown_watch_coverage'")==1


def test_deferred_parent_does_not_mask_wrong_discovered_child_kind(db):
    a=adapter(db)
    a.get_library_media_info=lambda section_id:[] if section_id==1 else [{'rating_key':10,'media_type':'show'}]
    a.get_children_metadata=lambda key:[{'rating_key':20,'media_type':'season'}] if key==10 else []
    def fetch(key,**kwargs):
        value=raw(key,'show' if key==10 else 'movie')
        if key==10:value['guid']=None
        else:value['parent_rating_key']='10'
        return m.normalize_metadata(key,value)
    a.get_metadata=fetch
    with pytest.raises(m.MetadataError):c.run(a,mode='full')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE reason='discovered_kind_mismatch'")==1
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==1


@pytest.mark.parametrize('field',['guid','title','duration'])
def test_absent_required_fields_are_deferred_like_empty_values(db,field):
    value=raw();del value[field]
    result=c.run(source_adapter(db,{1:value}),mode='full')
    assert result['ok'] and result['metadata']['deferred']==1 and snap(db) is None


def test_dependency_query_errors_are_fatal(db):
    with db.cursor() as q:q.execute('CREATE TABLE media_embeddings(unexpected_column integer)')
    db.commit();value=raw();value['guid']=None
    with pytest.raises(m.MetadataError):c.run(source_adapter(db,{1:value}),mode='full')
    assert scalar(db,"SELECT count(*) FROM metadata_ingestion_events WHERE evidence->>'disposition'='deferred'")==0
    assert scalar(db,"SELECT evidence->>'sqlstate' FROM metadata_ingestion_events")=='42703'


@pytest.mark.parametrize('change',[
    {'guid':'plex://movie/wrong-kind'}, {'directors':False}, {'media_index':-1},
])
def test_real_adapter_checks_child_conflicts_before_a_deferred_parent(monkeypatch,change):
    import fetch_tautulli_data as f
    value=raw(30,'episode');value.update(parent_rating_key=20,grandparent_rating_key=10,media_index=1,parent_media_index=1)
    value.update(change)
    monkeypatch.setattr(f,'_METADATA_CACHE',{})
    monkeypatch.setattr(f,'fetch_tautulli_data',lambda *a,**k:value)
    def parent(key):pytest.fail('Conflicting child fields must be checked before parent lookup')
    with pytest.raises(m.MetadataError) as caught:f.get_metadata(30,parent_lookup=parent,expected_type='episode')
    assert not isinstance(caught.value,m.IncompleteMetadata)
    assert 30 not in f._METADATA_CACHE


def test_missing_guid_does_not_hide_a_cyclic_parent():
    value=raw(30,'episode');value.update(guid=None,parent_rating_key=30,grandparent_rating_key=10,media_index=1,parent_media_index=1)
    with pytest.raises(m.MetadataError,match='cyclic_parent') as caught:m.normalize_metadata(30,value)
    assert not isinstance(caught.value,m.IncompleteMetadata)
