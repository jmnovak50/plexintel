"""Durability and recovery using only disposable PostgreSQL and synthetic inputs."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from unittest.mock import Mock

import numpy as np
import psycopg2
from psycopg2.extras import Json
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
from pgvector.psycopg2 import register_vector
import pytest

from api.predictive import prepare as preparation
from api.predictive.artifacts import current_config
from api.predictive.contracts import ContractError,fingerprint,specification,modality_contract
from api.predictive.pending import PendingVectors,checked
from api.predictive.prepare import refresh_vector,record
from api.predictive.publication import PUBLISHED,restore_last_good,source_signature,verify
from api.predictive.runner import run
from api.services.pipeline_log_format import item_line
from tests.test_predictive_publication import db,populate,Encoder


def refresh(conn,encoder,kind='media_text',key='1',text='synthetic text',old=None,output=None):
    register_vector(conn)
    stats=Counter();events=[]
    value=refresh_vector(specification(encoder.identity),kind,key,{'fresh':'source'},text,old or {},encoder,stats,
        pending=PendingVectors(conn),log=lambda op,**fields:events.append(dict(operation=op,**fields)))
    if output is not None:output.extend(events)
    return value,stats


def population(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT modality,source_key,input_hash,modality_contract_hash,encoder_digest,embedding::text,vector_sha256 '
                    'FROM pending_embedding_inference ORDER BY modality,source_key')
        result=cur.fetchall()
    conn.commit();return result


def published(conn):
    """Compare every public bundle record, not only the recommendation count."""
    result={}
    with conn.cursor() as cur:
        for table in PUBLISHED:
            cur.execute('SELECT md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,\'\')) FROM public.'+table+' t')
            result[table]=cur.fetchone()[0]
    conn.commit();return result


def execute(conn,path,fixture,events=None):
    snapshot,plex,encoder=fixture
    return run(conn,path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,
               collect=False,label=False,output=events.append if events is not None else lambda _:None)


@pytest.mark.parametrize('kind',['media_text','watch'])
def test_success_commits_before_next_request_and_retry_prefers_pending(db,kind):
    encoder=Encoder();embed=encoder.embed
    def idle(text):
        assert db.get_transaction_status()==TRANSACTION_STATUS_IDLE
        return embed(text)
    encoder.embed=idle;events=[]
    first,stats=refresh(db,encoder,kind=kind,output=events)
    assert stats['inferred']==stats['durably_persisted']==1 and encoder.calls==1
    assert events[-2]['operation']=='inference_completed' and events[-1]['durably_persisted'] is True
    other=psycopg2.connect(db.dsn)
    try:
        second,stats=refresh(other,encoder,kind=kind)
        assert stats['pending_reused']==stats['reused']==1 and stats['inferred']==0
        assert second==first and encoder.calls==1
    finally:other.close()
    with db.cursor() as cur:
        for table in ('media_embeddings','watch_embeddings','user_embeddings','recommendations'):
            cur.execute('SELECT count(*) FROM '+table);assert cur.fetchone()[0]==0


def test_published_preference_and_corrupt_published_fallback(db):
    encoder=Encoder();first,_=refresh(db,encoder)
    old={'1':dict(embedding=first['embedding'],provenance={k:v for k,v in first.items() if k!='embedding'})}
    second,stats=refresh(db,encoder,old=deepcopy(old))
    assert second==first and stats['published_reused']==1 and stats['pending_reused']==0
    broken=deepcopy(old);broken['1']['provenance']['vector_sha256']='b'*64
    third,stats=refresh(db,encoder,old=broken)
    assert third==first and stats['published_invalid']==1 and stats['pending_reused']==1 and encoder.calls==1


@pytest.mark.parametrize('change',['input','contract','encoder','checksum','nonunit'])
def test_changed_or_invalid_candidates_require_inference(db,change):
    encoder=Encoder();refresh(db,encoder)
    column={'input':'input_hash','contract':'modality_contract_hash','encoder':'encoder_digest','checksum':'vector_sha256'}.get(change)
    with db.cursor() as cur:
        if change=='nonunit':cur.execute('UPDATE pending_embedding_inference SET embedding=%s::vector',(str([2.]+[0.]*767),))
        else:cur.execute('UPDATE pending_embedding_inference SET '+column+'=%s',('b'*64,))
    db.commit();_,stats=refresh(db,encoder)
    assert encoder.calls==2 and stats['durably_persisted']==1
    assert stats['pending_'+('invalid' if change in ('checksum','nonunit') else 'incompatible')]==1
    assert len(population(db))==1  # Replace only this source's obsolete candidate.


def test_real_input_and_encoder_changes_and_model_only_contract_changes(db):
    encoder=Encoder();refresh(db,encoder)
    refresh(db,encoder,text='changed serialized text');assert encoder.calls==2
    encoder.identity=dict(encoder.identity,digest='b'*64)
    refresh(db,encoder,text='changed serialized text');assert encoder.calls==3
    spec=specification(encoder.identity);spec['profile_threshold']=.7
    stats=Counter()
    row=refresh_vector(spec,'media_text','1',{},'changed serialized text',{},encoder,stats,pending=PendingVectors(db))
    assert stats['pending_reused']==1 and encoder.calls==3
    assert row['feature_space_id']==fingerprint(spec)


@pytest.mark.parametrize('values',[[0.]*768,[1.]*768,[float('nan')]+[0.]*767,[1.,0.]])
def test_invalid_vectors_are_never_accepted(values):
    p=dict(input_hash='a',modality_contract_hash='b',encoder_digest='c',vector_sha256='d')
    assert checked(values,p,'a','b','c')==(None,'invalid')


def test_no_schema_creation_or_inference_when_migration_is_missing(db,tmp_path):
    fixture=populate(db)
    with db.cursor() as cur:cur.execute('DROP TABLE pending_embedding_inference')
    db.commit()
    with pytest.raises(ContractError,match='migration required'):execute(db,tmp_path,fixture)
    assert fixture[2].calls==0


def test_completed_vector_survives_real_process_kill(db):
    encoder=Encoder();spec=specification(encoder.identity)
    digest=fingerprint(dict(contract=modality_contract(spec,'media_text'),text='synthetic text'))
    value=record(spec,'media_text','1',{},[1.]+[0.]*767,digest)
    code='''import json,sys,os,signal
import psycopg2
from pgvector.psycopg2 import register_vector
from api.predictive.pending import PendingVectors
x=json.load(sys.stdin);c=psycopg2.connect(x['dsn']);register_vector(c)
PendingVectors(c).save('media_text','1',x['record'])
os.kill(os.getpid(),signal.SIGKILL)
'''
    child=subprocess.run([sys.executable,'-c',code],input=json.dumps(dict(dsn=db.dsn,record=value)),text=True,capture_output=True,timeout=15)
    assert child.returncode==-signal.SIGKILL,child.stderr
    _,stats=refresh(db,encoder)
    assert stats['pending_reused']==1 and encoder.calls==0


def test_completed_vector_survives_database_connection_termination(db):
    encoder=Encoder();refresh(db,encoder)
    other=psycopg2.connect(db.dsn)
    try:
        with other.cursor() as cur:cur.execute('SELECT pg_terminate_backend(%s)',(db.get_backend_pid(),))
        other.commit()
        _,stats=refresh(other,encoder)
        assert stats['pending_reused']==1 and encoder.calls==1
    finally:other.close()


def test_interrupted_preparation_has_no_public_effect_and_reuses_completed_work(db):
    from api.predictive.prepare import prepare
    snapshot,plex,encoder=populate(db);register_vector(db)
    before=published(db);signature=source_signature(db);db.commit();embed=encoder.embed
    def interrupted(text):
        if encoder.calls==3:raise RuntimeError('interrupted preparation')
        return embed(text)
    encoder.embed=interrupted
    with pytest.raises(RuntimeError,match='interrupted preparation'):
        prepare(db,snapshot,plex,encoder,{},policy=snapshot['_fixture_policy'])
    db.rollback()
    assert len(population(db))==3 and published(db)==before
    assert source_signature(db)==signature;db.commit()
    encoder.embed=embed;events=[]
    prepare(db,snapshot,plex,encoder,{},policy=snapshot['_fixture_policy'],progress=lambda key,**m:events.append((key,m)))
    assert encoder.calls==len(snapshot['media'])+len(snapshot['events'])
    assert max(m.get('pending_reused',0) for k,m in events if k=='media_text')==3
    assert published(db)==before


@pytest.mark.parametrize('stage',['training','scoring','shap','publication'])
def test_downstream_failure_preserves_incumbent_and_retry_uses_pending(db,tmp_path,monkeypatch,stage):
    import api.predictive.runner as runner
    import api.predictive.scoring as scoring
    fixture=populate(db);execute(db,tmp_path,fixture)
    before=published(db);snapshot,plex,encoder=fixture
    plex.metadata('2').update(summary='Legitimate changed synthetic description',updatedAt=2)
    calls=encoder.calls
    with monkeypatch.context() as m:
        if stage=='training':m.setattr(runner,'train',Mock(side_effect=RuntimeError('injected training failure')))
        elif stage=='scoring':m.setattr(runner,'score',Mock(side_effect=RuntimeError('injected scoring failure')))
        elif stage=='shap':m.setattr(scoring,'raw_shap',Mock(side_effect=RuntimeError('injected shap failure')))
        else:
            real=runner.publish
            def fail(*args,**kwargs):
                def stop(point):
                    if point=='recommendations':raise RuntimeError('injected publication failure')
                return real(*args,**kwargs,failpoint=stop)
            m.setattr(runner,'publish',fail)
        with pytest.raises(RuntimeError,match='injected'):execute(db,tmp_path,fixture)
    db.rollback()
    assert published(db)==before
    assert encoder.calls==calls+3  # One media input and two associated watch inputs.
    retained=population(db)
    assert len(retained)==len(snapshot['media'])+len(snapshot['events'])  # Cleanup rolled back too.
    events=[];result=execute(db,tmp_path,fixture,events)
    assert result['verified'] and encoder.calls==calls+3
    assert result['pending_inference']['durably_persisted']==0
    assert len([e for e in events if e.get('operation')=='pending_reused'])==3
    assert len(population(db))==3  # Newly promoted results still lack last-good coverage.
    assert verify(db,current_config(db))==result['counts']


def test_last_good_restore_preserves_pending_and_cleanup_waits_for_backup(db,tmp_path):
    fixture=populate(db);execute(db,tmp_path,fixture)
    original=current_config(db);db.commit();encoder=fixture[2]
    fixture[1].metadata('2').update(summary='New accepted synthetic input',updatedAt=2)
    result=execute(db,tmp_path,fixture);calls=encoder.calls
    assert len(population(db))==3
    saved=population(db)
    restore_last_good(db,tmp_path)
    assert current_config(db)==original;db.commit()
    assert population(db)==saved
    result2=execute(db,tmp_path,fixture)
    assert result2['verified'] and encoder.calls==calls and population(db)==saved
    # A subsequent verified backup now covers the promoted candidate population.
    result3=execute(db,tmp_path,fixture)
    assert result3['pending_inference']['pending_backup_covered']==3
    assert population(db)==[] and encoder.calls==calls


def test_cleanup_only_after_complete_publication_and_only_new_store_rows(db,tmp_path,monkeypatch):
    import api.predictive.runner as runner
    fixture=populate(db);execute(db,tmp_path,fixture);encoder=fixture[2]
    refresh(db,encoder,key='999999')  # Unreferenced work; no source identity is established.
    with db.cursor() as cur:
        cur.execute("UPDATE pending_embedding_inference SET encoder_digest=%s WHERE modality='media_text' AND source_key=3",('b'*64,))
        cur.execute("UPDATE pending_embedding_inference SET vector_sha256=%s WHERE modality='media_text' AND source_key=4",('c'*64,))
    db.commit();before=published(db);retained=population(db)
    with monkeypatch.context() as m:
        m.setattr(runner,'train',Mock(side_effect=RuntimeError('no full publication')))
        with pytest.raises(RuntimeError):execute(db,tmp_path,fixture)
    assert population(db)==retained and published(db)==before
    result=execute(db,tmp_path,fixture)
    assert result['pending_inference']['pending_obsolete']==2
    assert result['pending_inference']['pending_invalid_removed']==1
    assert population(db)==[]


def test_pending_does_not_admit_unlinked_history_or_bypass_identity(db):
    from api.predictive.source import read_snapshot
    from api.predictive.history_scope import partition_history
    from api.predictive.prepare import prepare
    fixture=populate(db);encoder=fixture[2]
    refresh(db,encoder,kind='watch',key='999999')
    with db.cursor() as cur:
        cur.execute("INSERT INTO watch_history(watch_id,username,rating_key,watched_at,played_duration) VALUES(999999,'fixture',999999,'2020-01-01',300)")
    db.commit();snapshot=read_snapshot(db);db.commit()
    assert 999999 not in snapshot['legacy_watch_ids']
    scoped=partition_history(snapshot)
    assert not any(e['watch_id']==999999 for e in scoped['events'])
    pending=PendingVectors(db);pending.get=Mock(side_effect=AssertionError('Identity must resolve first'))
    # The cached result is never consulted when the supplied key now identifies another title.
    fixture[1].metadata('1')['guid']='plex://movie/different-identity'
    with pytest.raises(ContractError,match='different entity'):
        prepare(db,fixture[0],fixture[1],encoder,{},policy=fixture[0]['_fixture_policy'],pending=pending)
    pending.get.assert_not_called()


def test_pending_and_published_reuse_produce_identical_model_features_ranks_and_shap(db,tmp_path,monkeypatch):
    import api.predictive.runner as runner
    fixture=populate(db)
    with monkeypatch.context() as m:
        m.setattr(runner,'train',Mock(side_effect=RuntimeError('retain prepared inference')))
        with pytest.raises(RuntimeError):execute(db,tmp_path,fixture)
    calls=fixture[2].calls;events=[]
    first=execute(db,tmp_path,fixture,events)
    assert first['pending_inference']['durably_persisted']==0 and fixture[2].calls==calls
    def numerical(conn):
        result={}
        with conn.cursor() as cur:
            for table,columns,order in (
                ('training_data','username,rating_key,embedding::text,watch_sim,sample_weight,diagnostics','username,rating_key'),
                ('recommendations','username,rating_key,predicted_probability,rank,cosine_similarity','username,rating_key'),
                ('shap_impact','user_id,rating_key,dimension,shap_value','user_id,rating_key,dimension')):
                cur.execute(f'SELECT {columns} FROM {table} ORDER BY {order}');result[table]=cur.fetchall()
        conn.commit();return result
    before=numerical(db)
    second=execute(db,tmp_path,fixture)
    assert numerical(db)==before and first['counts']==second['counts']
    assert fixture[2].calls==calls and first['evaluation']['statistical_checks_blocking'] is False
    assert not any(e.get('stage_key')=='semantic_labels' and e.get('status')=='failed' for e in events)
    logs=[item_line(e) for e in events if e.get('event')=='plexintel.pipeline-log/1']
    assert any('durable pending embedding reused' in text for text in logs)
    assert any('Pending inference reconciled after publication' in text for text in logs)


def test_persistence_failure_does_not_claim_durability(db):
    encoder=Encoder();register_vector(db);pending=PendingVectors(db)
    pending.save=Mock(side_effect=psycopg2.OperationalError('synthetic connection loss'))
    events=[];stats=Counter()
    with pytest.raises(psycopg2.OperationalError):
        refresh_vector(specification(encoder.identity),'media_text','1',{},'synthetic',{},encoder,stats,pending=pending,
                       log=lambda op,**fields:events.append(dict(operation=op,**fields)))
    assert stats['inferred']==1 and stats['durably_persisted']==0 and population(db)==[]
    assert events[-1]['operation']=='persistence_failed' and not any(e['operation']=='embedded' for e in events)
    assert 'durable persistence failed' in item_line(events[-1])


def test_lost_commit_acknowledgement_is_not_replayed_and_next_attempt_reuses_actual_commit(db):
    register_vector(db);db.commit();encoder=Encoder()
    class LostAcknowledgement:
        lose=False
        def cursor(self,*args,**kwargs):return db.cursor(*args,**kwargs)
        def commit(self):
            db.commit()
            if self.lose:raise psycopg2.OperationalError('synthetic lost commit acknowledgement')
    connection=LostAcknowledgement();pending=PendingVectors(connection);embed=encoder.embed
    def completed(text):
        connection.lose=True
        return embed(text)
    encoder.embed=completed;stats=Counter()
    with pytest.raises(psycopg2.OperationalError,match='acknowledgement'):
        refresh_vector(specification(encoder.identity),'media_text','1',{},'synthetic text',{},encoder,stats,pending=pending)
    assert stats['inferred']==1 and stats['durably_persisted']==0 and len(population(db))==1
    encoder.embed=embed
    _,stats=refresh(db,encoder)
    assert stats['pending_reused']==1 and encoder.calls==1


def test_store_is_minimal_has_only_primary_lookup_index_and_no_user_profiles(db):
    with db.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pending_embedding_inference' ORDER BY ordinal_position")
        assert [x[0] for x in cur.fetchall()]==['modality','source_key','input_hash','modality_contract_hash','encoder_digest','embedding','vector_sha256']
        cur.execute("SELECT count(*) FROM pg_indexes WHERE tablename='pending_embedding_inference'");assert cur.fetchone()[0]==1
    db.commit()
    with pytest.raises(ContractError,match='Only media/watch'):PendingVectors(db).get('user','fixture','a','b','c')
