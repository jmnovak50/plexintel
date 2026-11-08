"""Operational observation uses synthetic subprocesses and optional private SQL only."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
import json
import os
import sys
import tempfile
from unittest.mock import Mock

import pytest
from api.embedding_generation.progress import EVENT,STAGES,Reporter,EventReader,event_details
from api.embedding_generation.contracts import ContractError
from api.services import pipeline_service as service
from api.services.pipeline_visibility import enrich_runs,historical_details
from tests.test_pipeline_service import FakeConnection
from tests.test_embedding_generation_database import store

RID='45143c11-afbc-4edf-ac3e-e1a72fd67b30'

def event(key='source_sync',status='started',**kwargs):
    return dict(event=EVENT,stage_key=key,status=status,at=datetime.now(timezone.utc).isoformat(),
                elapsed_seconds=1.,metrics={},generation_run_id=RID,**kwargs)


def test_reader_handles_partial_utf8_oversize_noise_and_preserves_shared_offset():
    with tempfile.TemporaryFile('w+b') as handle:
        reader=EventReader(handle)
        data=json.dumps(event(message='✓'),ensure_ascii=False).encode()+b'\n'
        cut=data.index('✓'.encode())+1
        handle.write(data[:cut]);handle.flush();offset=handle.tell()
        assert reader.read()[0]==[] and handle.tell()==offset
        handle.write(data[cut:]+b'x'*300000+b'\n'+data);handle.flush();offset=handle.tell()
        found=[]
        while True:
            rows,more=reader.read();found+=rows
            if not more:break
        assert len(found)==2 and found[0]['message']=='✓'
        assert handle.tell()==offset


def test_reporter_measures_interleaved_spans_and_excludes_private_metric_fields():
    now=[0.];events=[];report=Reporter(events.append,clock=lambda:now[0]);report.bind(RID)
    with report.span('score_model'):
        now[0]+=2
    with report.span('shap'):
        now[0]+=4
    with report.span('score_model'):
        now[0]+=3
        report(dict(completed=3,expected=5,owner='private',api_key='secret'))
    report.done('score_model',predictions=5);report.done('shap',contexts=2)
    assert report.details['score_model']['elapsed_seconds']==5
    assert report.details['shap']['elapsed_seconds']==4
    assert report.details['score_model']['status']=='success'
    assert all('private' not in json.dumps(v) and 'secret' not in json.dumps(v) for v in events if v.get('event')==EVENT)
    report.skip('watch',previous_seconds=100);report.done('watch',reused=10)
    assert report.details['watch']['status']=='skipped'
    with pytest.raises(ContractError):
        with report.span('train_model'):raise ContractError('Quality gate failed')
    assert report.details['train_model']['status']=='failed'
    assert 'Quality gate failed' in report.details['train_model']['message']


def observe_fixture(monkeypatch,tmp_path):
    conn=FakeConnection([])
    @contextmanager
    def connection(**kwargs):yield conn
    monkeypatch.setattr(service,'_pipeline_connection',connection)
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    heartbeats=[]
    monkeypatch.setattr(service,'_update_run_heartbeat_short',lambda **kwargs:heartbeats.append(kwargs))
    observers=[];cls=service.PipelineStageObserver
    def make(run_id):
        value=cls(run_id);observers.append(value);return value
    monkeypatch.setattr(service,'PipelineStageObserver',make)
    return conn,heartbeats,observers


def test_actual_subprocess_emits_ten_stages_without_launching_any_pipeline(monkeypatch,tmp_path):
    conn,beats,observers=observe_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(service,'_read_pipeline_cancel_requested',lambda _:False)
    sequence=[event(key,status) for key,_ in STAGES for status in ('started','success')]
    code='import json,time\nfor value in '+repr(sequence)+':\n print(json.dumps(value),flush=True)\n time.sleep(.002)\n'
    result=service._run_stage_process(run_id=999,stage_key='embeddinggemma2_generation',
        argv=[sys.executable,'-u','-c',code],env=dict(os.environ),poll_seconds=.01)
    assert result.returncode==0 and not result.cancelled
    assert set(observers[0].events)==dict(STAGES).keys()
    assert all(v['status']=='success' for v in observers[0].events.values())
    assert any(b['stage_key']!='embeddinggemma2_generation' for b in beats)
    assert len([s for s,_ in conn.executed if 'INSERT INTO' in s])==10
    assert (tmp_path/'pipeline.log').read_text().count('verification')>0


def test_cancellation_closes_active_stage_and_marks_unreached_work_skipped(monkeypatch,tmp_path):
    _,_,observers=observe_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(service,'_read_pipeline_cancel_requested',lambda _:bool(observers and observers[0].initialized))
    code='import json,time;print(json.dumps('+repr(event())+'),flush=True);time.sleep(30)'
    result=service._run_stage_process(run_id=999,stage_key='embeddinggemma2_generation',
        argv=[sys.executable,'-u','-c',code],env=dict(os.environ),poll_seconds=.01,grace_seconds=.1)
    assert result.cancelled and result.returncode!=0
    assert observers[0].events['source_sync']['status']=='cancelled'
    assert observers[0].events['verification']['status']=='skipped'


def test_success_without_complete_events_is_not_falsely_reported_as_ten_successes(monkeypatch,tmp_path):
    _,_,observers=observe_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(service,'_read_pipeline_cancel_requested',lambda _:False)
    result=service._run_stage_process(run_id=999,stage_key='embeddinggemma2_generation',
        argv=[sys.executable,'-c','import json;print(json.dumps('+repr(event(status='success'))+'))'],
        env=dict(os.environ),poll_seconds=.01)
    assert result.returncode==0
    assert observers[0].events['verification']['status']=='not_recorded'


def test_observation_failure_does_not_strand_child_or_disable_its_cancellation(monkeypatch,tmp_path):
    _,_,_=observe_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(service,'_read_pipeline_cancel_requested',lambda _:False)
    monkeypatch.setattr(service,'PipelineStageObserver',lambda _:Mock(accept=Mock(side_effect=RuntimeError('monitor unavailable'))))
    result=service._run_stage_process(run_id=999,stage_key='embeddinggemma2_generation',
        argv=[sys.executable,'-c','import json;print(json.dumps('+repr(event())+'))'],env=dict(os.environ),poll_seconds=.01)
    assert result.returncode==0
    assert 'Stage observation unavailable' in (tmp_path/'pipeline.log').read_text()


def historical_journal():
    return dict(run_id=RID,status='succeeded',promotion_id='committed',
        stages=dict(source_sync=131.,context=119.,metadata=122.,media_text=113.,watch=139.,users=8.,training=501.,scoring=883.,validation=19.),
        counts=dict(media_text=dict(expected=8414,succeeded=8414),watch=dict(succeeded=9626),user=dict(succeeded=31)),
        reconciliation=dict(new_media_identities=4,new_watch_history_events=19,media_embeddings_reused=8186,watch_embeddings_reused=9357,new_media_embeddings=4,existing_media_regenerated=224),
        scoring=dict(predictions=224330,users=31,limited_history_skips=0),inference=dict(media_text=dict(succeeded=228)),
        users_rebuilt=18,dataset=dict(rows=9303,skips=dict(label_policy=533,limited_history=42),watch_coverage=dict(quarantined_watch_events=277)))


def test_historical_run_expansion_is_read_only_correlated_and_honest_about_missing_data():
    carrier=dict(stage_key='embeddinggemma2_generation',stdout_tail='truncated line\n'+json.dumps(dict(run_id=RID,promotion_id='committed')))
    run=dict(run_id=326,status='success',stages=[carrier]);original=deepcopy(run['stages'])
    conn=FakeConnection([{'installed':'embedding_v2.production_runs'}],[[historical_journal()]])
    enrich_runs(conn.cursor(),[run])
    details={s['stage_key']:s for s in run['stage_details']}
    assert len(details)==10 and run['stages']==original
    assert details['media_text']['metrics']['inferred']==228
    assert details['media_text']['duration_seconds']==354
    assert details['training_data']['duration_seconds'] is None
    assert details['shap']['duration_seconds'] is None
    assert details['publication']['status']=='success'
    assert details['verification']['status']=='not_recorded'
    assert run['semantic_labeling']['status']=='disabled'
    assert all(s.lstrip().startswith('SELECT') for s,_ in conn.executed)
    assert conn.executed[-1][1]==((RID,),)
    legacy=dict(stages=[dict(stage_key='batch_label',stdout_tail='legacy log')]);before=deepcopy(legacy)
    enrich_runs(conn.cursor(),[legacy]);assert legacy==before


def test_uncorrelated_history_preserves_original_log_instead_of_guessing_by_time():
    run=dict(stages=[dict(stage_key='embeddinggemma2_generation',stdout_tail='no receipt')])
    conn=FakeConnection([]);enrich_runs(conn.cursor(),[run])
    assert not conn.executed and 'stage_details' not in run and 'stage_detail_note' in run


def test_failed_historical_quality_gate_is_not_presented_as_a_success():
    journal=historical_journal();journal['status']='failed';journal['promotion_id']=None
    journal['stages'].pop('scoring')
    details={s['stage_key']:s for s in historical_details(journal)}
    assert details['train_model']['status']=='not_recorded'
    assert details['publication']['status']=='not_recorded'
    assert 'quality_passed' not in details['train_model']['metrics']


def test_api_serializes_optional_details_without_changing_legacy_rows():
    from api.routes.pipeline_admin_routes import _serialize_run
    at=datetime.now(timezone.utc)
    original=dict(stages=[dict(stage_key='train_model',started_at=at)],stage_details=[dict(stage_key='shap',started_at=at)])
    result=_serialize_run(original)
    assert result['stages'][0]['started_at']==at.isoformat()
    assert result['stage_details'][0]['started_at']==at.isoformat()
    assert original['stages'][0]['started_at']==at


def test_real_private_sql_observer_and_stage_payloads(store,monkeypatch):
    # Temp identity sequence is private; public pipeline rows are never inserted/updated.
    store.query('''CREATE TEMP TABLE observed_stages(stage_id integer GENERATED ALWAYS AS IDENTITY,
        run_id integer,stage_key text,status text,stdout_tail text,started_at timestamptz NOT NULL DEFAULT now(),completed_at timestamptz)''')
    class Cursor:
        def __enter__(self):self.cur=store.conn.cursor();return self
        def __exit__(self,*a):self.cur.close()
        def execute(self,statement,args):
            assert 'public.pipeline_run_stages' in statement
            self.cur.execute(statement.replace('public.pipeline_run_stages','pg_temp.observed_stages'),args)
    class Connection:
        def cursor(self):return Cursor()
    @contextmanager
    def connection(**kwargs):
        yield Connection();store.conn.commit()
    monkeypatch.setattr(service,'_pipeline_connection',connection)
    observer=service.PipelineStageObserver(999)
    observer.accept(event('watch'));observer.accept(event('watch','success',message='text only'))
    observer.finish(cancelled=False,returncode=1)
    rows=store.query('SELECT * FROM pg_temp.observed_stages ORDER BY stage_id',many=True)
    assert len(rows)==10
    watch=event_details(next(r for r in rows if r['stage_key']=='watch'))
    assert watch['status']=='success' and watch['duration_seconds']==1
    assert next(r for r in rows if r['stage_key']=='verification')['status']=='skipped'
