"""Operational hardening with fictional data and mocked I/O only."""
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock
import hashlib

import numpy as np
import psycopg2
import pytest
from psycopg2 import sql

from api.embedding_generation import runtime,features
from api.embedding_generation.contracts import Encoder,ContractError,text_contract,fingerprint
from api.embedding_generation.features import SUPERVISION_POLICY,Vocabulary
from api.embedding_generation.recovery import IDENTITY_POLICY
from api.embedding_generation.run_safety import assert_preflight,RunFailure,classify_failure,failure_message
from api.embedding_generation.training_integrity import serialized_row,record_for_row,row_digest
from api.services import pipeline_service
from tests.test_embedding_generation_features import fixture_data
from tests.test_pipeline_service import FakeConnection


def text_fixture():
    enc=Encoder('embeddinggemma-2:latest','a'*64,'740m-q8_0','Q8_0','b'*64)
    g,m,w,events=fixture_data(enc)
    g['contract']=text_contract(g['contract']);g['contract_hash']=fingerprint(g['contract'])
    g['snapshot']=dict(events=events,feedback=[],as_of='2020-03-01T00:00:00+00:00')
    return g,m,w


def test_shared_stream_preserves_committed_dataset_hash_and_predictor_matrix():
    # Golden captured from the committed 3ffaa68 builder, before this refactor.
    g,m,w=text_fixture();rows,skips=features.training_rows(g,m,w,{})
    digest=hashlib.sha256(b''.join(serialized_row(r) for r in rows)).hexdigest()
    assert digest=='64fc3103e8ee1edc55f75e9702ace5e3c4ab711f70f0bee401120d13b5e36f2d'
    identity=features.CanonicalTitles(m);plan,_=features.training_plan(g,m,identity)
    streamed=list(features.planned_text_rows(g,m,w,plan,identity))
    vocab=Vocabulary.fit(rows,include_poster=False)
    np.testing.assert_array_equal(vocab.transform(rows),vocab.transform(streamed))
    assert [r['sample_weight'] for r in rows]==[r['sample_weight'] for r in streamed]


def test_materialization_hash_handles_float32_roundtrip_without_changing_fit_hash():
    g,m,w=text_fixture();row=features.training_rows(g,m,w,{})[0][-1]
    record=record_for_row(g['generation_id'],row,True)
    db_record=dict(record,embedding=np.asarray(record['embedding'],dtype=np.float32),
                   prediction_at=datetime.fromisoformat(record['prediction_at']))
    assert row_digest(record,True)==row_digest(db_record,True)
    db_record['features']=dict(record['features'],sample_weight=123.)
    assert row_digest(record,True)!=row_digest(db_record,True)


@pytest.fixture
def preflight(monkeypatch,tmp_path):
    marker=tmp_path/'installed.json';marker.write_text('{}')
    monkeypatch.setattr(runtime,'MARKER',marker);monkeypatch.setattr(runtime,'TRANSITION',tmp_path/'transition.json')
    monkeypatch.setattr(runtime,'code_hash',lambda:'approved')
    control=dict(active_generation='fixture',deployed_code_sha256='approved')
    store=Mock();store.query.return_value=control;store.table.side_effect=lambda name:sql.Identifier('pg_temp',name)
    state=dict(generation_id='fixture');bundle=dict(identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY)
    return store,state,bundle,control


@pytest.mark.parametrize('fault',['receipt','identity','supervision','generation','marker','transition','control'])
def test_preflight_fails_closed_without_registering_receipt(preflight,fault):
    store,state,bundle,control=preflight
    if fault=='receipt':control['deployed_code_sha256']='unapproved'
    elif fault=='identity':bundle['identity_policy']=None
    elif fault=='supervision':bundle['supervision_policy']=None
    elif fault=='generation':control['active_generation']='different'
    elif fault=='marker':runtime.MARKER.unlink()
    elif fault=='transition':runtime.TRANSITION.write_text('{}')
    elif fault=='control':store.query.return_value=None
    with pytest.raises(RunFailure) as error:assert_preflight(store,state,bundle)
    assert not error.value.retryable
    assert all('UPDATE' not in str(call.args[0]) for call in store.query.call_args_list)


def test_preflight_accepts_only_existing_approved_receipt(preflight):
    store,state,bundle,control=preflight
    assert_preflight(store,state,bundle)
    assert store.query.call_count==1
    assert control['deployed_code_sha256']=='approved'


@pytest.mark.parametrize('installed,active,allowed',[(False,None,True),(True,None,True),(True,'active',False)])
def test_missing_marker_cannot_downgrade_active_installation(monkeypatch,tmp_path,installed,active,allowed):
    monkeypatch.setattr(runtime,'MARKER',tmp_path/'absent');monkeypatch.setattr(runtime,'TRANSITION',tmp_path/'transition')
    # MagicMock is needed only for the cursor context protocol.
    from unittest.mock import MagicMock
    conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect=[('embedding_v2.control',),(active,)] if installed else [(None,)]
    monkeypatch.setattr('api.db.connection.connect_db',lambda:conn)
    if allowed:assert runtime.active_generation() is None
    else:
        with pytest.raises(RuntimeError,match='refusing legacy fallback'):runtime.active_generation()
    conn.set_session.assert_called_once_with(readonly=True)
    conn.rollback.assert_called_once();conn.close.assert_called_once()


def test_transition_and_control_lookup_failure_never_choose_legacy(monkeypatch,tmp_path):
    monkeypatch.setattr(runtime,'MARKER',tmp_path/'absent');monkeypatch.setattr(runtime,'TRANSITION',tmp_path/'transition')
    lookup=Mock(side_effect=psycopg2.OperationalError('private connection URL'))
    monkeypatch.setattr('api.db.connection.connect_db',lookup)
    with pytest.raises(psycopg2.OperationalError):runtime.active_generation()
    runtime.TRANSITION.write_text('{}')
    with pytest.raises(RuntimeError,match='in progress'):runtime.active_generation()
    assert lookup.call_count==1


@pytest.mark.parametrize('code',['53200','55P03','40001','40P01','08006','57014'])
def test_known_transient_database_errors_are_retryable_without_leaking_details(code):
    error=type('DatabaseFailure',(Exception,),{'pgcode':code})('private SQL/account/token')
    assert classify_failure(error)==dict(code='DATABASE_'+code,retryable=True)
    assert 'SQL/account/token' not in failure_message(error)


def test_unknown_and_contract_errors_require_operator():
    assert not classify_failure(ContractError('quality gates'))['retryable']
    assert not classify_failure(ValueError('private'))['retryable']
    assert not classify_failure(psycopg2.OperationalError('private'))['retryable']
    assert classify_failure(psycopg2.OperationalError('server closed the connection unexpectedly'))['retryable']


@pytest.mark.parametrize('code',['28P01','42501','42703','23505'])
def test_known_permanent_sqlstates_are_not_generic_connection_retries(code):
    error=type('PermanentDatabaseFailure',(psycopg2.OperationalError,),{'pgcode':code})('fixture')
    assert not classify_failure(error)['retryable']


def test_context_reconstruction_commits_bounded_batches_only():
    from types import SimpleNamespace
    from api.embedding_generation.production_run import ProductionRun
    worker=SimpleNamespace(observe_resources=Mock(),conn=Mock())
    for index in range(1,258):ProductionRun.context_batch(worker,'fixture',index)
    assert worker.conn.commit.call_count==2
    assert [c.args for c in worker.observe_resources.call_args_list]==[('fixture',128),('fixture',256)]


def retry_conn(failures=1,code=75,completed=None):
    return FakeConnection([dict(failures=failures,exit_code=code,completed_at=completed)])


@pytest.mark.parametrize('code',[1,78,None,137])
def test_scheduler_never_retries_unclassified_or_permanent_failures(monkeypatch,code):
    conn=retry_conn(code=code)
    assert pipeline_service._scheduled_retry_state(conn,'slot')['status']=='requires_operator'


def test_retry_limit_and_backoff_survive_new_scheduler_instance(monkeypatch):
    settings={'pipeline.max_attempts':3,'pipeline.retry_backoff_seconds':300}
    monkeypatch.setattr(pipeline_service,'get_setting_value',lambda k,default=None:settings.get(k,default))
    now=datetime(2026,11,10,12,tzinfo=timezone.utc)
    assert pipeline_service._scheduled_retry_state(retry_conn(failures=3),'slot',now_utc=now)['status']=='retry_exhausted'
    row=lambda:retry_conn(completed=now-timedelta(seconds=30))
    for _ in range(2):
        assert pipeline_service._scheduled_retry_state(row(),'slot',now_utc=now)['status']=='retry_backoff'
    assert pipeline_service._scheduled_retry_state(retry_conn(completed=now-timedelta(seconds=301)),'slot',now_utc=now) is None
    assert pipeline_service._scheduled_retry_state(FakeConnection([None]),'slot',now_utc=now) is None


def test_schedule_catchup_is_explicit_and_once_per_local_slot(monkeypatch):
    settings={'pipeline.frequency':'daily','pipeline.run_time':'07:03','pipeline.timezone':'America/Chicago'}
    monkeypatch.setattr(pipeline_service,'get_setting_value',lambda k,default=None:settings.get(k,default))
    from zoneinfo import ZoneInfo
    for day in (datetime(2026,3,8,17,tzinfo=ZoneInfo('America/Chicago')),datetime(2026,11,1,17,tzinfo=ZoneInfo('America/Chicago'))):
        slot=pipeline_service.get_pipeline_schedule_slot(day)
        assert slot['slot_dt'].hour==7 and slot['slot_dt'].minute==3 and slot['slot_dt'].date()==day.date()
        assert slot['slot_dt']<day  # Activation can catch up; no scheduling is invoked here.


def test_missing_control_singleton_cannot_choose_legacy(monkeypatch,tmp_path):
    from unittest.mock import MagicMock
    monkeypatch.setattr(runtime,'MARKER',tmp_path/'absent')
    conn=MagicMock();conn.cursor.return_value.__enter__.return_value.fetchone.side_effect=[('control',),None]
    monkeypatch.setattr('api.db.connection.connect_db',lambda:conn)
    with pytest.raises(RuntimeError,match='control is missing'):runtime.active_generation()


@pytest.fixture
def pending_run(monkeypatch,tmp_path):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from api.embedding_generation import production_run,text_production
    state=dict(generation_id='fixture',publication_id='published',model_sha256='after')
    run=dict(run_id='interrupted',promotion_id='published',base_model_sha256='before',
             summary=dict(model_after='after'),status='failed')
    store=MagicMock();store.table.side_effect=lambda name:sql.Identifier('pg_temp',name)
    store.query.return_value=run
    monkeypatch.setattr(text_production,'load_production',lambda store:(state,{},None))
    verify=Mock(return_value=dict(generation_id='fixture',publication_id='published',model_sha256='after',counts={'media_text':{'succeeded':1}}))
    monkeypatch.setattr(text_production,'verify_current_production',verify)
    preflight=Mock();monkeypatch.setattr(production_run,'assert_preflight',preflight)
    forbidden=Mock(side_effect=AssertionError('Recovery must not start pipeline work'))
    monkeypatch.setattr(production_run,'ProductionRun',forbidden)
    execute=lambda:production_run.execute(store,{},collect=forbidden,plex_factory=forbidden,cache=tmp_path,
                                         publication_lock=lambda *a:nullcontext())
    return SimpleNamespace(state=state,run=run,store=store,verify=verify,preflight=preflight,
                           forbidden=forbidden,execute=execute)


@pytest.mark.parametrize('status',['failed','succeeded','running'])
def test_committed_publication_recovery_only_verifies_receipts(pending_run,status):
    p=pending_run;p.run['status']=status
    result=p.execute()
    assert result['verification_only'] and result['summary']['verification_only_recovery']
    p.forbidden.assert_not_called()
    updates=[c for c in p.store.query.call_args_list if 'UPDATE' in str(c.args[0])]
    assert len(updates)==1 and "status='succeeded'" in str(updates[0].args[0])
    query=p.store.query.call_args_list[0].args[0]
    assert "status='succeeded'" in str(query) and "final_verification" in str(query)


@pytest.mark.parametrize('fault',['publication','model','verification'])
def test_committed_recovery_refuses_superseded_or_unverified_receipts(pending_run,fault):
    p=pending_run
    if fault=='publication':p.state['publication_id']='another'
    elif fault=='model':p.run['summary']['model_after']='another'
    else:p.verify.return_value['model_sha256']='another'
    with pytest.raises(RunFailure):p.execute()
    p.forbidden.assert_not_called()
    assert not any('UPDATE' in str(c.args[0]) for c in p.store.query.call_args_list)


def test_preflight_failure_stops_before_sync_checkpoint_or_verification(pending_run):
    p=pending_run;p.preflight.side_effect=RunFailure('DEPLOYMENT_RECEIPT','Unapproved code receipt')
    with pytest.raises(RunFailure):p.execute()
    p.verify.assert_not_called();p.forbidden.assert_not_called();p.store.query.assert_not_called()


@pytest.mark.parametrize('reason',['stale','exhausted','permanent','unknown'])
def test_unpublished_recovery_refuses_unsafe_automatic_resume(pending_run,reason):
    p=pending_run;p.run['promotion_id']=None;p.run['base_model_sha256']='after'
    if reason=='stale':p.run['base_model_sha256']='old'
    elif reason!='unknown':p.run['summary']['recovery']=dict(attempts=3 if reason=='exhausted' else 1,requires_operator=reason=='permanent')
    with pytest.raises(RunFailure):p.execute()
    p.forbidden.assert_not_called()
    assert not any('UPDATE' in str(c.args[0]) for c in p.store.query.call_args_list)


@pytest.mark.parametrize('under_lock',[False,True])
def test_schedule_retry_guard_prevents_child_launch_and_new_run(monkeypatch,under_lock):
    from contextlib import contextmanager
    from tests.test_pipeline_service import FakePipelineLock
    conn=FakeConnection([]);lock=FakePipelineLock()
    @contextmanager
    def connection():yield conn
    monkeypatch.setattr(pipeline_service,'connect_db',lambda:conn)
    monkeypatch.setattr(pipeline_service,'_pipeline_connection',connection)
    monkeypatch.setattr(pipeline_service,'get_setting_value',lambda *a,**k:True)
    monkeypatch.setattr(pipeline_service,'get_pipeline_schedule_slot',lambda:dict(schedule_key='slot'))
    monkeypatch.setattr(pipeline_service,'_reconcile_cancel_requested_runs',Mock())
    monkeypatch.setattr(pipeline_service,'_has_terminal_scheduled_run_for_schedule_key',lambda *a:False)
    monkeypatch.setattr(pipeline_service,'_has_active_run_for_schedule_key',lambda *a:False)
    monkeypatch.setattr(pipeline_service,'_scheduled_retry_state',lambda *a:dict(status='retry_exhausted'))
    child=Mock(side_effect=AssertionError('Blocked slot must not start a child'))
    monkeypatch.setattr(pipeline_service,'build_pipeline_stages',child)
    if under_lock:
        result=pipeline_service.run_pipeline(delivery_type='scheduled',triggered_by='fixture',schedule_key='slot',acquired_lock=lock)
        assert lock.released
    else:
        result=pipeline_service.run_scheduled_pipeline()
    assert result['status']=='retry_exhausted'
    child.assert_not_called();assert not conn.executed


@pytest.mark.parametrize('retryable',[False,True])
def test_daily_cli_reports_classified_exit_without_work_or_sensitive_errors(monkeypatch,capsys,retryable):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('hardening_daily_cli',Path('scripts/embeddinggemma2_migration.py'))
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    conn=Mock();monkeypatch.setattr(cli,'connect_db',lambda:conn)
    monkeypatch.setattr(cli.source,'settings',lambda:{})
    monkeypatch.setattr(cli,'Store',lambda conn:Mock())
    error=psycopg2.OperationalError('server closed the connection unexpectedly: sensitive-connection-string') if retryable else ContractError('Policy mismatch')
    operation=Mock(side_effect=error);monkeypatch.setattr(cli,'daily',operation)
    with pytest.raises(SystemExit) as result:cli.main(['daily'])
    assert result.value.code==(75 if retryable else 78)
    assert 'sensitive-connection-string' not in capsys.readouterr().out
    operation.assert_called_once();conn.close.assert_called_once()
