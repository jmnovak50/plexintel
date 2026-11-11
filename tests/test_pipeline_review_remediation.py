"""Adversarial regression cases with synthetic data and mocked I/O."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
from unittest.mock import Mock

import psycopg2
import pytest

from api.embedding_generation import production_run,runtime,run_safety,text_production
from api.embedding_generation.contracts import ContractError
from api.services import pipeline_service as pipeline
from tests.test_pipeline_hardening import pending_run
from tests.test_pipeline_service import FakeConnection,FakePipelineLock


def load_cli():
    spec=importlib.util.spec_from_file_location('review_remediation_cli',Path('scripts/embeddinggemma2_migration.py'))
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    return cli


def test_incumbent_is_loaded_only_after_execution_lock(pending_run,monkeypatch):
    p=pending_run;held=[]
    @contextmanager
    def lock(*args):
        held.append(True)
        p.state.update(publication_id='new',model_sha256='new-model')
        p.run.update(promotion_id='new');p.run['summary']['model_after']='new-model'
        p.verify.return_value.update(publication_id='new',model_sha256='new-model')
        yield
        held.pop()
    def load(store):
        assert held,'Baseline loaded before execution lock'
        return dict(p.state),{},None
    monkeypatch.setattr(text_production,'load_production',load)
    result=production_run.execute(p.store,{},collect=p.forbidden,plex_factory=p.forbidden,cache=Path('/tmp'),publication_lock=lock)
    assert result['promotion_id']=='new';p.forbidden.assert_not_called()


def test_revision_change_during_baseline_verification_stops_before_any_write(pending_run):
    p=pending_run;p.verify.return_value['publication_id']='another'
    with pytest.raises(run_safety.RunFailure,match='baseline verification'):p.execute()
    p.store.query.assert_not_called();p.forbidden.assert_not_called()


@pytest.mark.parametrize('pin',[None,dict(generation_id='fixture',publication_id='old',model_sha256='after')])
def test_unpublished_resume_requires_exact_saved_revision(pending_run,pin):
    p=pending_run;p.run.update(promotion_id=None,base_model_sha256='after',status='running')
    p.run['summary']['incumbent_revision']=pin
    with pytest.raises(run_safety.RunFailure,match='exact incumbent revision'):p.execute()
    p.forbidden.assert_not_called()


@pytest.mark.parametrize('step',['connect','settings','store','close'])
@pytest.mark.parametrize('kind',['transport','contract','unknown'])
def test_all_daily_bootstrap_and_cleanup_failures_are_classified(monkeypatch,capsys,step,kind):
    cli=load_cli();conn=Mock()
    operations=dict(connect=Mock(return_value=conn),settings=Mock(return_value={}),store=Mock(return_value=Mock()),close=conn.close)
    error=(psycopg2.OperationalError('server closed the connection unexpectedly: fixture-secret') if kind=='transport'
           else ContractError('Fixture policy mismatch') if kind=='contract' else psycopg2.OperationalError('fixture-secret unknown failure'))
    operations[step].side_effect=error
    monkeypatch.setattr(cli,'connect_db',operations['connect']);monkeypatch.setattr(cli.source,'settings',operations['settings'])
    monkeypatch.setattr(cli,'Store',operations['store']);daily=Mock(return_value=None);monkeypatch.setattr(cli,'daily',daily)
    with pytest.raises(SystemExit) as result:cli.main(['daily'])
    assert result.value.code==(75 if kind=='transport' else 78)
    assert 'fixture-secret' not in capsys.readouterr().out
    if step!='close':daily.assert_not_called()
    assert conn.close.call_count==int(step!='connect')


def test_cleanup_loss_cannot_mask_permanent_primary_failure(monkeypatch):
    cli=load_cli();conn=Mock();conn.close.side_effect=psycopg2.InterfaceError('connection already closed')
    monkeypatch.setattr(cli,'connect_db',lambda:conn)
    monkeypatch.setattr(cli.source,'settings',Mock(side_effect=ContractError('Permanent configuration failure')))
    with pytest.raises(SystemExit) as result:cli.main(['daily'])
    assert result.value.code==78


def test_cleanup_after_recorded_completion_cannot_automatically_repeat_work(monkeypatch):
    cli=load_cli();conn=Mock();conn.close.side_effect=psycopg2.InterfaceError('connection already closed')
    monkeypatch.setattr(cli,'connect_db',lambda:conn);monkeypatch.setattr(cli.source,'settings',lambda:{})
    monkeypatch.setattr(cli,'Store',lambda c:Mock());monkeypatch.setattr(cli,'daily',lambda *a,**k:dict(promotion_id='recorded'))
    with pytest.raises(SystemExit) as result:cli.main(['daily'])
    assert result.value.code==78


@pytest.mark.parametrize('persist',[True,False])
def test_failed_activation_never_launches_child_and_finalizes_when_possible(monkeypatch,persist):
    conn=FakeConnection([{'run_id':123},{'run_id':123}]);lock=FakePipelineLock();calls=[]
    @contextmanager
    def connection():
        calls.append(1)
        if len(calls)>1 and not persist:raise psycopg2.InterfaceError('connection already closed')
        yield conn
    monkeypatch.setattr(pipeline,'_pipeline_connection',connection)
    monkeypatch.setattr(pipeline,'build_pipeline_environment',lambda:{})
    monkeypatch.setattr(pipeline,'_log_run_event',Mock());monkeypatch.setattr(pipeline,'_launch_environment_summary',lambda **kw:'fixture')
    monkeypatch.setattr(pipeline,'build_pipeline_stages',Mock(side_effect=RuntimeError('Activation uncertain')))
    child=Mock();monkeypatch.setattr(pipeline,'_run_stage_process',child)
    result=pipeline.run_pipeline(delivery_type='manual',triggered_by='fixture',schedule_key=None,acquired_lock=lock)
    assert result['status']=='failed' and result['failure_persisted']==persist
    child.assert_not_called();assert lock.released
    if persist:
        assert any("status='failed'" in str(q) for q,a in conn.executed)
        assert any('controller_dispatch' in str(q) and a[1]==78 for q,a in conn.executed)


@pytest.mark.parametrize('old,locked,advanced,expected',[(True,False,False,1),(False,False,False,0),(True,True,False,0),(True,False,True,0)])
def test_abandoned_null_pid_reconciliation_requires_old_unlocked_unchanged_owner(monkeypatch,old,locked,advanced,expected):
    row=dict(run_id=123,status='started',delivery_type='scheduled',current_pid=None,current_stage_key=None,
             last_heartbeat_at=datetime.now(timezone.utc)-timedelta(seconds=60 if old else 1))
    conn=FakeConnection([None if advanced else {'run_id':123}],fetchall_results=[[row]])
    monkeypatch.setattr(pipeline,'_pipeline_execution_locked',lambda:locked)
    monkeypatch.setattr(pipeline,'_log_run_event',Mock())
    child_check=Mock();monkeypatch.setattr(pipeline,'_process_exists',child_check)
    assert pipeline._reconcile_cancel_requested_runs(conn)==expected
    child_check.assert_not_called()
    if old and not locked:assert any('current_pid IS NOT DISTINCT FROM' in str(q) for q,a in conn.executed)


@pytest.mark.parametrize('field,value',[('has_stages',True),('current_stage_key','embeddinggemma2_generation')])
def test_null_pid_with_dispatch_evidence_is_an_ambiguous_hold(monkeypatch,field,value):
    row=dict(run_id=123,status='started',delivery_type='scheduled',current_pid=None,current_stage_key=None,
             last_heartbeat_at=datetime.now(timezone.utc)-timedelta(seconds=60))
    row[field]=value
    conn=FakeConnection([],fetchall_results=[[row]])
    monkeypatch.setattr(pipeline,'_pipeline_execution_locked',lambda:False)
    assert pipeline._reconcile_cancel_requested_runs(conn)==0
    assert not any('UPDATE' in str(q) for q,a in conn.executed)


def test_hard_kill_transition_marker_is_never_automatically_bypassed(pending_run,monkeypatch):
    p=pending_run;runtime.MARKER.write_text('{}')
    marker='{"pid":999999999,"code_sha256":"dead-worker-fixture"}'
    runtime.TRANSITION.write_text(marker)
    monkeypatch.setattr(production_run,'assert_preflight',run_safety.assert_preflight)
    for _ in range(2):
        with pytest.raises(run_safety.RunFailure,match='operator review'):p.execute()
    assert runtime.TRANSITION.read_text()==marker
    p.verify.assert_not_called();p.forbidden.assert_not_called()
    assert not any('UPDATE' in str(c.args[0]) for c in p.store.query.call_args_list)


def test_actual_killed_barrier_child_leaves_a_fail_closed_marker(pending_run,monkeypatch):
    p=pending_run;runtime.MARKER.write_text('{}')
    code="""import sys
from pathlib import Path
from api.embedding_generation import runtime
runtime.TRANSITION=Path(sys.argv[1])
runtime.legacy_writer_pids=lambda:[]
runtime.code_hash=lambda:'fixture-source'
with runtime.publication_barrier():
    print('barrier-ready',flush=True)
    sys.stdin.read()
"""
    child=subprocess.Popen([sys.executable,'-c',code,str(runtime.TRANSITION)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},close_fds=True)
    try:
        assert select.select([child.stdout],[],[],10)[0],'Test child did not establish its private marker'
        assert child.stdout.readline().strip()==b'barrier-ready'
        child.kill();child.wait(timeout=5)  # Only this disposable test process.
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)
        child.stdin.close();child.stdout.close()
    assert json.loads(runtime.TRANSITION.read_text())['pid']==child.pid
    monkeypatch.setattr(production_run,'assert_preflight',run_safety.assert_preflight)
    with pytest.raises(run_safety.RunFailure,match='operator review'):p.execute()
    assert runtime.TRANSITION.exists();p.verify.assert_not_called();p.forbidden.assert_not_called()


def test_old_committed_recovery_is_durable_and_exposed_by_cli(pending_run,monkeypatch,capsys):
    p=pending_run;p.run['created_at']='2026-11-09T00:00:00+00:00'
    p.run['summary'].update(counts={},inference={},scoring={},stages={},model_before='before',elapsed_seconds=100.)
    result=p.execute();p.forbidden.assert_not_called()
    update=[c for c in p.store.query.call_args_list if 'UPDATE' in str(c.args[0])][0]
    assert update.args[1][0].adapted['outcome']=='verification_only'
    cli=load_cli();conn=Mock();monkeypatch.setattr(cli,'connect_db',lambda:conn)
    monkeypatch.setattr(cli.source,'settings',lambda:{});monkeypatch.setattr(cli,'Store',lambda c:Mock())
    monkeypatch.setattr(text_production,'daily',Mock(return_value=result))
    with pytest.raises(SystemExit) as outcome:cli.main(['daily'])
    assert outcome.value.code==run_safety.VERIFICATION_ONLY_EXIT
    receipt=json.loads(capsys.readouterr().out)
    assert receipt['verification_only'] and receipt['outcome']=='verification_only'


def test_recovery_only_parent_does_not_consume_fresh_slot(monkeypatch):
    conn=FakeConnection([{'run_id':123},{'stage_id':456},{'status':'verification_only'}]);lock=FakePipelineLock()
    @contextmanager
    def connection():yield conn
    monkeypatch.setattr(pipeline,'_pipeline_connection',connection)
    monkeypatch.setattr(pipeline,'build_pipeline_environment',lambda:{})
    for name in ('_log_run_event','_log_stage_output'):monkeypatch.setattr(pipeline,name,Mock())
    monkeypatch.setattr(pipeline,'_launch_environment_summary',lambda **kw:'fixture')
    monkeypatch.setattr(pipeline,'_read_pipeline_cancel_requested',lambda rid:False)
    monkeypatch.setattr(pipeline,'build_pipeline_stages',lambda:[('embeddinggemma2_generation',['fixture'])])
    monkeypatch.setattr(pipeline,'_run_stage_process',lambda **kw:pipeline.StageProcessResult(returncode=76,stdout='',stderr='',cancelled=False))
    result=pipeline.run_pipeline(delivery_type='manual',triggered_by='fixture',schedule_key='later-slot',acquired_lock=lock)
    assert result['status']=='verification_only' and not result['fresh_workload_completed']
    assert any("status='verification_only'" in str(q) for q,a in conn.executed)
    assert not any("SET status = 'success'" in str(q) for q,a in conn.executed)
    assert 'verification_only' not in pipeline.SCHEDULE_TERMINAL_STATUSES
    # A new poll sees no successful/cancelled run, active worker or failed retry.
    slot=FakeConnection([None,None,None])
    assert not pipeline._has_terminal_scheduled_run_for_schedule_key(slot,'later-slot')
    assert not pipeline._has_active_run_for_schedule_key(slot,'later-slot')
    assert pipeline._scheduled_retry_state(slot,'later-slot') is None
