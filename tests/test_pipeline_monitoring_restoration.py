"""Monitoring contract fixtures: no production connection, fit or pipeline run."""
from copy import deepcopy
from datetime import datetime, timezone
import json

from api.predictive.progress import EVENT, Reporter, event_details
from api.routes.pipeline_admin_routes import _serialize_run
from api.services import pipeline_service as service
from api.services.pipeline_visibility import enrich_runs
from tests.test_pipeline_service import FakeConnection


def stage(key, status='success', **event):
    payload=dict(event=EVENT,stage_key=key,status=status,elapsed_seconds=12.,metrics={})
    payload.update(event)
    return dict(stage_id=key,stage_key=key,status=status,started_at=datetime.now(timezone.utc),
        completed_at=None,stderr_tail=None,stdout_tail=json.dumps(payload))


def test_legacy_shared_stage_names_do_not_hide_original_stages():
    keys=['tautulli_incremental','library_embeddings','watch_embeddings','user_embeddings',
          'training_data','train_model','score_model','batch_label']
    run=dict(stages=[dict(stage_key=k,stdout_tail='original log') for k in keys])
    original=deepcopy(run)
    conn=FakeConnection([]);enrich_runs(conn.cursor(),[run])
    assert run==original and conn.executed==[]


def test_restored_receipt_recovers_metrics_without_mutating_history_or_querying_journals(monkeypatch,tmp_path):
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    report=dict(run_id='a'*64,promotion_id='a'*64,verified=True,
        counts=dict(shap_prediction_context=12,shap_impact=480),
        summary=dict(rows=20,skips=dict(label_policy=3,limited_history=1)),
        evaluation=dict(chronological=dict(balanced_accuracy=.6,average_precision=.9),
                        show_heldout=dict(balanced_accuracy=.7),gates=dict(ap=True,balanced=True)),
        semantic_labeling=dict(status='skipped',reason='Automatic labeling disabled'))
    # Larger than DB stdout_tail; exact per-run retained file is the evidence.
    report['private_ignored']='x'*6000
    (tmp_path/'pipeline-run-999-predictive_daily-fixture.stdout.log').write_text(json.dumps(report)+'\n')
    run=dict(run_id=999,status='success',stages=[dict(stage_key='predictive_daily',stdout_tail='truncated receipt'),
        stage('train_model'),stage('training_data'),
        stage('shap',message='Measured within scoring; raw-margin embedding contributions retained'),
        stage('semantic_labels','not_recorded')])
    original=deepcopy(run['stages']);conn=FakeConnection([])
    enrich_runs(conn.cursor(),[run]);details={s['stage_key']:s for s in run['stage_details']}
    assert details['train_model']['metrics']['chronological_average_precision']==.9
    assert details['training_data']['metrics']['label_policy_skips']==3
    assert details['shap']['metrics']==dict(contexts=12,contributions=480)
    assert details['shap']['duration_seconds'] is None and not details['shap']['timing_known']
    assert details['semantic_labels']['status']=='skipped'
    assert run['publication_id']=='a'*64
    assert run['stages']==original and not conn.executed
    assert 'private_ignored' not in json.dumps(run['stage_details'],default=str)
    serialized=_serialize_run(run)
    assert isinstance(serialized['stage_details'][0]['started_at'],str)


def test_archived_final_stdout_receipt_recovers_available_stages_without_journals():
    report=dict(run_id='fictional-archived-receipt',promotion_id='committed',
        stages=dict(source_sync=10,media_text=20,training=30,scoring=40),counts={},
        scoring=dict(predictions=100,users=2))
    run=dict(status='success',stages=[dict(stage_key='embeddinggemma2_generation',stdout_tail=json.dumps(report))])
    conn=FakeConnection([]);enrich_runs(conn.cursor(),[run])
    details={s['stage_key']:s for s in run['stage_details']}
    assert len(details)==10
    assert details['source_sync']['duration_seconds']==10
    assert details['score_model']['metrics']['predictions']==100
    assert details['shap']['duration_seconds'] is None
    assert details['verification']['status']=='not_recorded'
    assert conn.executed==[]


def test_missing_or_ambiguous_retained_logs_do_not_guess_from_another_run(monkeypatch,tmp_path):
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    report=json.dumps(dict(run_id='other-run',verified=True,counts={},summary=dict(rows=123)))
    (tmp_path/'pipeline-run-998-predictive_daily-other.stdout.log').write_text(report)
    for suffix in ('one','two'):
        (tmp_path/f'pipeline-run-999-predictive_daily-{suffix}.stdout.log').write_text(report)
    run=dict(run_id=999,stages=[dict(stage_key='predictive_daily',stdout_tail='truncated'),stage('training_data')])
    enrich_runs(None,[run])
    assert run['stage_details'][0]['metrics']=={}


def test_preparation_callbacks_finish_each_phase_and_tick_only_active_work():
    now=[0.];events=[];reporter=Reporter(events.append,clock=lambda:now[0])
    reporter.progress('media_text',completed=1,expected=4,reused=1)
    now[0]=2.
    reporter.progress('media_text',completed=4,expected=4,reused=4)
    reporter.progress('media_text',seconds=2.)
    now[0]=3.
    reporter.progress('watch',completed=1,expected=3,inferred=1)
    assert reporter.details['media_text']['status']=='success'
    assert not reporter.details['media_text']['timing_active']
    assert reporter.details['watch']['timing_active']
    snapshot=event_details(stage('watch','started',**{
        k:v for k,v in reporter.details['watch'].items() if k not in ('event','stage_key','status')}))
    assert snapshot['timing_active'] and snapshot['metrics']['completed']==1
    reporter.progress('watch',seconds=5.)
    assert reporter.details['watch']['elapsed_seconds']==5.
    assert reporter.details['media_text']['elapsed_seconds']==2.


def test_training_phase_survives_allowlist_and_progress_updates_are_bounded():
    now=[0.];events=[];reporter=Reporter(events.append,clock=lambda:now[0])
    with reporter.span('train_model'):
        reporter.progress('train_model',phase='boosting round 11/100; examples=1000',owner='private')
        assert events[-1]['message'].startswith('boosting round 11/100')
        assert 'owner' not in events[-1]['metrics']
    reporter.progress('media_text',completed=0,expected=10000)
    before=len(events)
    for n in range(10000):reporter.progress('media_text',completed=n)
    assert len(events)==before
    reporter.progress('media_text',seconds=1)
    assert events[-1]['metrics']['completed']==9999


def test_predictive_worker_observer_accepts_active_and_completed_events(monkeypatch,tmp_path):
    # Exercise actual subprocess retention/heartbeat with fictional stdout only.
    import os,sys
    from tests.test_pipeline_visibility import observe_fixture, event
    conn,beats,observers=observe_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(service,'_read_pipeline_cancel_requested',lambda _:False)
    sequence=[event('media_text','started'),event('media_text','success')]
    result=service._run_stage_process(run_id=999,stage_key='predictive_daily',
        argv=[sys.executable,'-c','import json,time;\nfor v in '+repr(sequence)+':\n print(json.dumps(v),flush=True)\n time.sleep(.05)'],
        env=dict(os.environ),poll_seconds=.01)
    assert result.returncode==0 and observers[0].events['media_text']['status']=='success'
    assert observers[0].events['verification']['status']=='not_recorded'
    assert any(b['stage_key']=='media_text' for b in beats)
