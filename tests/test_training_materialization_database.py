"""Opt-in real SQL tests: fictional rows and connection-private tables only."""
import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from psycopg2 import sql
from psycopg2.extras import Json

from api.embedding_generation.contracts import ContractError
from api.embedding_generation import model,backfill
from api.embedding_generation.training_integrity import ARTIFACT,restore_text_rows,verify_materialization
from api.embedding_generation.production_run import ProductionRun,WORK
from api.embedding_generation.promotion import promote,TABLES,digest_rows
from api.embedding_generation.runtime import code_hash
from api.embedding_generation.text_production import load_production,train_text
from tests.test_embedding_generation_database import store,encoder,synthetic_ready,clone_legacy_tables_privately


def test_lost_private_context_restores_rows_without_fit_encoder_or_receipt_replacement(store,encoder,tmp_path,monkeypatch):
    gid,_,_=synthetic_ready(store,encoder,text_mode=True)
    store.validate(gid,quality_go=True);clone_legacy_tables_privately(store)
    legacy=tmp_path/'legacy.pkl';legacy.write_bytes(b'fixture legacy bytes')
    promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',legacy_model=legacy,
            source_check=lambda:store.generation(gid)['source_hash'])
    state,_,_=load_production(store);snapshot=deepcopy(state['snapshot']);snapshot['_db_hash']=state['source_hash']
    run='fictional-crash'
    store.query('INSERT INTO pg_temp.production_runs(run_id,generation_id,base_model_sha256,status) VALUES(%s,%s,%s,\'running\')',(run,gid,state['model_sha256']));store.conn.commit()
    first=ProductionRun(store,run,live_schema='pg_temp');first.install_work();first.hydrate(state,snapshot)
    train_text(first,gid);model.score(first,gid)
    names=('dataset.json','model.pkl','evaluation.json','dimensions.json','scoring.json')
    originals={n:bytes(first.artifact(gid,n)['data']) for n in names}
    count=json.loads(originals['dataset.json'])['rows']
    # Losing a worker's private tables must not lose its durable journal/artifacts.
    for name in WORK:
        first.query(sql.SQL('DROP TABLE IF EXISTS {} CASCADE').format(first.table(name)))
    store.conn.commit()
    restored=ProductionRun(store,run,live_schema='pg_temp');restored.install_work();restored.hydrate(state,snapshot)
    assert restored.query(sql.SQL('SELECT count(*) AS n FROM {}').format(restored.table('text_training_rows')))['n']==0
    # Also cover old saved runs which predate the new sidecar artifact.
    restored.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s AND name=%s').format(restored.table('artifacts')),(gid,ARTIFACT));store.conn.commit()
    forbidden=Mock(side_effect=AssertionError('Resume must not fit or infer'))
    monkeypatch.setattr(model,'fit',forbidden);monkeypatch.setattr(backfill,'run_media_text',forbidden)
    monkeypatch.setattr(backfill,'run_watches',forbidden);monkeypatch.setattr(backfill,'run_users',forbidden)
    receipt=restore_text_rows(restored,gid)
    assert receipt['rows']==count
    assert all(bytes(restored.artifact(gid,n)['data'])==originals[n] for n in names)
    forbidden.assert_not_called()
    validated=restored.validate(gid,quality_go=True)
    assert validated['training']==receipt
    assert max(restored.context_resources['max_own_locks'],1)<100


@pytest.mark.parametrize('mutation',['empty','delete_one','weight','label','dependency'])
def test_post_validation_training_corruption_cannot_touch_published_tables(store,encoder,tmp_path,mutation):
    gid,_,_=synthetic_ready(store,encoder,text_mode=True)
    store.validate(gid,quality_go=True);clone_legacy_tables_privately(store)
    before={t:digest_rows(store,t,'pg_temp') for t in TABLES}
    key=store.query('SELECT media_key FROM pg_temp.text_training_rows LIMIT 1')['media_key']
    if mutation=='empty':store.query('DELETE FROM pg_temp.text_training_rows')
    elif mutation=='delete_one':store.query('DELETE FROM pg_temp.text_training_rows WHERE media_key=%s',(key,))
    elif mutation=='weight':store.query("UPDATE pg_temp.text_training_rows SET features=jsonb_set(features,'{sample_weight}','999') WHERE media_key=%s",(key,))
    elif mutation=='label':store.query('UPDATE pg_temp.text_training_rows SET label=1-label WHERE media_key=%s',(key,))
    else:store.query("UPDATE pg_temp.text_training_rows SET dependencies=jsonb_set(dependencies,'{target_aliases}','[]') WHERE media_key=%s",(key,))
    store.conn.commit()
    legacy=tmp_path/'legacy.pkl';legacy.write_bytes(b'fixture')
    with pytest.raises(ContractError):
        promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',legacy_model=legacy,
                source_check=lambda:store.generation(gid)['source_hash'])
    assert {t:digest_rows(store,t,'pg_temp') for t in TABLES}==before
    assert store.query('SELECT count(*) AS n FROM pg_temp.promotions')['n']==0


def test_empty_training_rows_cannot_be_validated_even_with_good_artifacts(store,encoder):
    gid,_,_=synthetic_ready(store,encoder,text_mode=True)
    store.query('DELETE FROM pg_temp.text_training_rows');store.conn.commit()
    with pytest.raises(ContractError,match='materialization'):store.validate(gid,quality_go=True)
    assert store.generation(gid)['status']=='building'


def test_reconstruction_hash_mismatch_preserves_original_model_and_dataset_receipts(store,encoder):
    gid,_,_=synthetic_ready(store,encoder,text_mode=True)
    names=('dataset.json','model.pkl',ARTIFACT)
    original={n:bytes(store.artifact(gid,n)['data']) for n in names}
    snapshot=store.generation(gid)['snapshot'];snapshot['events'][10]['played_seconds']=600
    store.query('UPDATE pg_temp.generations SET snapshot=%s WHERE generation_id=%s',(Json(snapshot),gid));store.conn.commit()
    with pytest.raises(ContractError,match='differs from saved fit'):restore_text_rows(store,gid)
    assert all(bytes(store.artifact(gid,n)['data'])==original[n] for n in names)


def test_atomic_publisher_rechecks_rows_after_taking_publication_locks(store,encoder,tmp_path,monkeypatch):
    from api.embedding_generation import training_integrity
    gid,_,_=synthetic_ready(store,encoder,text_mode=True);store.validate(gid,quality_go=True)
    clone_legacy_tables_privately(store);before={t:digest_rows(store,t,'pg_temp') for t in TABLES}
    real=training_integrity.verify_materialization;calls=[]
    def changed_after_first(*args):
        calls.append(1)
        if len(calls)==2:store.query('DELETE FROM pg_temp.text_training_rows')
        return real(*args)
    monkeypatch.setattr(training_integrity,'verify_materialization',changed_after_first)
    legacy=tmp_path/'legacy.pkl';legacy.write_bytes(b'fixture')
    with pytest.raises(ContractError,match='materialization'):
        promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',legacy_model=legacy,
                source_check=lambda:store.generation(gid)['source_hash'])
    assert len(calls)==2
    assert {t:digest_rows(store,t,'pg_temp') for t in TABLES}==before


def test_retry_classification_uses_worker_exit_not_logical_observer_rows(store,monkeypatch):
    from contextlib import contextmanager
    from datetime import datetime,timedelta,timezone
    from api.services import pipeline_service
    # Execute the real SQL against only these private, synthetic log tables.
    store.query('CREATE TEMP TABLE pipeline_runs(run_id integer,status text,schedule_key text,completed_at timestamptz)')
    store.query('CREATE TEMP TABLE pipeline_run_stages(stage_id integer,run_id integer,stage_key text,status text,exit_code integer)')
    completed=datetime.now(timezone.utc)-timedelta(seconds=600)
    store.query("INSERT INTO pg_temp.pipeline_runs VALUES(1,'failed','slot',%s)",(completed,))
    store.query("INSERT INTO pg_temp.pipeline_run_stages VALUES(1,1,'embeddinggemma2_generation','failed',75),(10,1,'verification','failed',NULL)")
    class PrivateLogs:
        @contextmanager
        def cursor(self):
            with store.conn.cursor() as cur:
                class Cursor:
                    def execute(self,query,args):cur.execute(query.replace('public.pipeline_run','pg_temp.pipeline_run'),args)
                    def fetchone(self):return cur.fetchone()
                yield Cursor()
    settings={'pipeline.max_attempts':3,'pipeline.retry_backoff_seconds':300}
    monkeypatch.setattr(pipeline_service,'get_setting_value',lambda k,default=None:settings.get(k,default))
    assert pipeline_service._scheduled_retry_state(PrivateLogs(),'slot') is None
    store.query('UPDATE pg_temp.pipeline_run_stages SET exit_code=78 WHERE stage_id=1')
    assert pipeline_service._scheduled_retry_state(PrivateLogs(),'slot')['status']=='requires_operator'


@pytest.mark.parametrize('status',['succeeded','failed'])
def test_real_journal_query_recovers_committed_run_without_new_pipeline_work(store,monkeypatch,tmp_path,status):
    from contextlib import nullcontext
    from api.embedding_generation import production_run,text_production
    from api.embedding_generation.run_safety import SAFETY_VERSION
    state=dict(generation_id='fixture',publication_id='committed',model_sha256='after')
    saved=dict(run_safety=SAFETY_VERSION,model_after='after')
    store.query("INSERT INTO pg_temp.production_runs(run_id,generation_id,base_model_sha256,status,promotion_id,summary,created_at) VALUES('old','fixture','old','succeeded','old',%s,'2020-01-01')",(Json({}),))
    store.query("INSERT INTO pg_temp.production_runs(run_id,generation_id,base_model_sha256,status,promotion_id,summary) VALUES('recover','fixture','before',%s,'committed',%s)",(status,Json(saved)))
    store.conn.commit()
    monkeypatch.setattr(production_run,'assert_preflight',Mock())
    monkeypatch.setattr(text_production,'load_production',lambda store:(state,{},None))
    verified=dict(generation_id='fixture',publication_id='committed',model_sha256='after',counts={'media_text':{'succeeded':1}})
    monkeypatch.setattr(text_production,'verify_current_production',Mock(return_value=verified))
    forbidden=Mock(side_effect=AssertionError('Committed recovery must only verify'))
    monkeypatch.setattr(production_run,'ProductionRun',forbidden)
    result=production_run.execute(store,{},collect=forbidden,plex_factory=forbidden,cache=tmp_path,
                                  publication_lock=lambda *a:nullcontext())
    assert result['verification_only'];forbidden.assert_not_called()
    rows=store.query('SELECT run_id,status,summary FROM pg_temp.production_runs ORDER BY run_id',many=True)
    assert rows[0]['run_id']=='old' and rows[0]['summary']=={}
    assert rows[1]['status']=='succeeded' and rows[1]['summary']['final_verification']==verified


@pytest.mark.parametrize('field,value',[('publication_id','same-generation-new-publication'),('model_sha256','f'*64)])
def test_atomic_publication_rejects_exact_incumbent_mismatch_before_protected_writes(store,encoder,tmp_path,monkeypatch,field,value):
    gid,_,_=synthetic_ready(store,encoder,text_mode=True)
    store.validate(gid,quality_go=True);clone_legacy_tables_privately(store)
    legacy=tmp_path/'legacy.pkl';legacy.write_bytes(b'fixture')
    promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',legacy_model=legacy,
            source_check=lambda:store.generation(gid)['source_hash'])
    state,_,_=load_production(store);snapshot=deepcopy(state['snapshot']);snapshot['_db_hash']=state['source_hash']
    store.query("INSERT INTO pg_temp.production_runs(run_id,generation_id,base_model_sha256,status) VALUES('revision-race',%s,%s,'running')",(gid,state['model_sha256']));store.conn.commit()
    work=ProductionRun(store,'revision-race',live_schema='pg_temp');work.install_work();work.hydrate(state,snapshot)
    train_text(work,gid);model.score(work,gid);work.validate(gid,quality_go=True)
    before={t:digest_rows(store,t,'pg_temp') for t in TABLES}
    store.query(sql.SQL('UPDATE pg_temp.production_state SET {}=%s').format(sql.Identifier(field)),(value,));store.conn.commit()
    forbidden=Mock(side_effect=AssertionError('Mismatch must precede source/archival work'))
    from api.embedding_generation import promotion
    monkeypatch.setattr(promotion,'archive',forbidden)
    with pytest.raises(ContractError,match='Incumbent publication/model revision'):
        promote(work,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',legacy_model=legacy,source_check=forbidden)
    forbidden.assert_not_called()
    assert {t:digest_rows(store,t,'pg_temp') for t in TABLES}==before
    assert store.query('SELECT count(*) AS n FROM pg_temp.promotions')['n']==1
    assert store.query(sql.SQL('SELECT {} AS value FROM pg_temp.production_state').format(sql.Identifier(field)))['value']==value


@pytest.mark.parametrize('fault',['interrupt','mismatch','connection_loss'])
def test_restoration_failure_after_a_committed_128_row_batch(store,encoder,monkeypatch,fault):
    import psycopg2
    from api.embedding_generation import training_integrity,run_safety,features
    gid,_,_=synthetic_ready(store,encoder,text_mode=True,example_count=160)
    names=('dataset.json','model.pkl','evaluation.json','dimensions.json','scoring.json',ARTIFACT)
    original={name:bytes(store.artifact(gid,name)['data']) for name in names}
    assert json.loads(original['dataset.json'])['rows']>128
    real=features.planned_text_rows
    completed=[]
    def broken(*args,**kwargs):
        for index,row in enumerate(real(*args,**kwargs),1):
            if index==129:
                # The helper has committed row 128 before requesting this row.
                count=store.query('SELECT count(*) AS n FROM pg_temp.text_training_rows')['n']
                completed.append(count);assert count==128
                if fault=='interrupt':raise RuntimeError('Interrupted after committed batch')
                if fault=='connection_loss':
                    # Terminate only THIS test's own private-table backend. No
                    # other session/PID is addressed, and no permanent data exists.
                    with store.conn.cursor() as cur:cur.execute('SELECT pg_terminate_backend(pg_backend_pid())')
                row=dict(row,sample_weight=row['sample_weight']+1.)
            yield row
    forbidden=Mock(side_effect=AssertionError('Restoration must never fit/infer'))
    monkeypatch.setattr(model,'fit',forbidden);monkeypatch.setattr(backfill,'run_media_text',forbidden)
    with monkeypatch.context() as patch:
        patch.setattr(features,'planned_text_rows',broken)
        if fault=='connection_loss':
            with pytest.raises((psycopg2.OperationalError,psycopg2.InterfaceError)) as error:restore_text_rows(store,gid)
            assert store.conn.closed
            assert run_safety.classify_failure(error.value)['retryable']
        else:
            with pytest.raises(RuntimeError if fault=='interrupt' else ContractError):restore_text_rows(store,gid)
            store.conn.rollback()
    assert completed==[128];forbidden.assert_not_called()
    if fault!='connection_loss':
        assert store.query('SELECT count(*) AS n FROM pg_temp.text_training_rows')['n']==128
        assert all(bytes(store.artifact(gid,n)['data'])==original[n] for n in names)
        result=restore_text_rows(store,gid)
        assert result['rows']==json.loads(original['dataset.json'])['rows']
        assert all(bytes(store.artifact(gid,n)['data'])==original[n] for n in names)


@pytest.fixture
def private_pipeline_logs(store):
    from contextlib import contextmanager
    store.query('''CREATE TEMP TABLE pipeline_runs(run_id integer GENERATED ALWAYS AS IDENTITY,
        status text,delivery_type text,schedule_key text,notes text,completed_at timestamptz,
        last_heartbeat_at timestamptz,current_pid integer,current_stage_key text,cancel_requested_at timestamptz)''')
    store.query('''CREATE TEMP TABLE pipeline_run_stages(stage_id integer GENERATED ALWAYS AS IDENTITY,
        run_id integer,stage_key text,status text,exit_code integer,completed_at timestamptz,stderr_tail text)''')
    class PrivateLogs:
        @contextmanager
        def cursor(self,**kwargs):
            with store.conn.cursor(**kwargs) as cur:
                class Cursor:
                    def execute(self,query,args=()):cur.execute(query.replace('public.pipeline_run','pg_temp.pipeline_run'),args)
                    def fetchone(self):return cur.fetchone()
                    def fetchall(self):return cur.fetchall()
                yield Cursor()
    return PrivateLogs()


def test_predispatch_failure_and_orphan_reconciliation_use_atomic_real_sql(store,private_pipeline_logs,monkeypatch):
    from contextlib import contextmanager
    from api.services import pipeline_service as pipeline
    store.query("INSERT INTO pg_temp.pipeline_runs(status,delivery_type,last_heartbeat_at) VALUES('started','scheduled',now()-interval '5 minutes')")
    monkeypatch.setattr(pipeline,'_pipeline_execution_locked',lambda:False)
    monkeypatch.setattr(pipeline,'_log_run_event',Mock())
    assert pipeline._reconcile_cancel_requested_runs(private_pipeline_logs)==1
    assert store.query('SELECT status FROM pg_temp.pipeline_runs WHERE run_id=1')['status']=='failed'
    store.query("INSERT INTO pg_temp.pipeline_runs(status,delivery_type) VALUES('started','scheduled')")
    @contextmanager
    def connection():
        yield private_pipeline_logs
        store.conn.commit()
    monkeypatch.setattr(pipeline,'_pipeline_connection',connection)
    assert pipeline._finalize_controller_failure(2,RuntimeError('Uncertain activation'))
    assert store.query('SELECT status FROM pg_temp.pipeline_runs WHERE run_id=2')['status']=='failed'
    assert store.query('SELECT exit_code FROM pg_temp.pipeline_run_stages WHERE run_id=2')['exit_code']==78
    assert not pipeline._finalize_controller_failure(2,RuntimeError('Must not overwrite terminal state'))


def test_recovery_outcome_is_not_a_consumed_slot_or_retry_failure_in_real_sql(store,private_pipeline_logs,monkeypatch):
    from api.services import pipeline_service as pipeline
    store.query("INSERT INTO pg_temp.pipeline_runs(status,delivery_type,schedule_key,completed_at) VALUES('verification_only','scheduled','today',now())")
    store.query("INSERT INTO pg_temp.pipeline_run_stages(run_id,stage_key,status,exit_code) VALUES(1,'embeddinggemma2_generation','verification_only',76)")
    assert not pipeline._has_terminal_scheduled_run_for_schedule_key(private_pipeline_logs,'today')
    assert not pipeline._has_active_run_for_schedule_key(private_pipeline_logs,'today')
    assert pipeline._scheduled_retry_state(private_pipeline_logs,'today') is None
    store.query("INSERT INTO pg_temp.pipeline_runs(status,delivery_type,schedule_key,completed_at) VALUES('failed','scheduled','failed-slot',now())")
    store.query("INSERT INTO pg_temp.pipeline_run_stages(run_id,stage_key,status,exit_code) VALUES(2,'embeddinggemma2_generation','failed',75),(2,'controller_dispatch','failed',78)")
    assert pipeline._scheduled_retry_state(private_pipeline_logs,'failed-slot')['status']=='requires_operator'
