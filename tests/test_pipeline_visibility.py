"""Operational observation uses synthetic subprocesses and optional private SQL only."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json
import os
import sys
import tempfile
from unittest.mock import Mock

import pytest
from api.predictive.progress import EVENT,STAGES,Reporter,EventReader,event_details
from api.predictive.contracts import ContractError
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
    assert len([s for s,_ in conn.executed if 'INSERT INTO' in s])==len(STAGES)
    assert (tmp_path/'pipeline.log').read_text().count('verification')>0


def test_live_logs_arrive_before_exit_and_survive_worker_completion(monkeypatch,tmp_path):
    observe_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(service,'_read_pipeline_cancel_requested',lambda _:False)
    outputs=[];monkeypatch.setattr(service,'_save_live_output',lambda run,stage,out,err:outputs.append((out,err)))
    code='import time;print("Embedded: Fictional Beacon — 東京",flush=True);time.sleep(.15);print("worker finished",flush=True)'
    result=service._run_stage_process(run_id=998,stage_key='embeddinggemma2_generation',
        argv=[sys.executable,'-u','-c',code],env=dict(os.environ),poll_seconds=.01)
    assert result.returncode==0
    assert any('Fictional Beacon' in out and 'worker finished' not in out for out,_ in outputs)
    assert 'worker finished' in outputs[-1][0]
    files=list(tmp_path.glob('pipeline-run-998-*.log'))
    assert len(files)==2 and all(p.stat().st_mode & 0o777 == 0o600 for p in files)
    assert any('Fictional Beacon' in p.read_text() for p in files)


def test_live_tail_preserves_writer_offset_and_redacts_credentials():
    with tempfile.TemporaryFile('w+b') as handle:
        handle.write('Fictional Beacon — 東京\nkey=fictional-secret token=hidden\nAuthorization: Bearer hidden2'.encode())
        handle.flush()
        before=handle.tell()
        text=service._live_output_tail(handle,{'OLLAMA_API_KEY':'fictional-secret'})
        assert handle.tell()==before
        assert 'Fictional Beacon' in text and 'fictional-secret' not in text and 'hidden' not in text
        os.write(handle.fileno(),b'\nlast line')
        assert service._live_output_tail(handle,{}).endswith('last line')


@pytest.mark.parametrize('alive,fresh,discovery,advanced,expected',[
    (False,False,False,False,1),(True,False,False,False,0),
    (False,True,False,False,0),(False,False,True,False,0),(False,False,False,True,0),
])
def test_dead_worker_reconciliation_is_guarded_and_changes_only_run_metadata(monkeypatch,alive,fresh,discovery,advanced,expected):
    row=dict(run_id=999,status='started',current_pid=123,current_stage_key='training_data',
        delivery_type='content_discovery_fixture' if discovery else 'manual',
        last_heartbeat_at=datetime.now(timezone.utc)-timedelta(seconds=0 if fresh else 300))
    conn=FakeConnection([None if advanced else {'run_id':999}],[[row]])
    monkeypatch.setattr(service,'_process_exists',lambda _:alive)
    monkeypatch.setattr(service,'_pipeline_execution_locked',lambda:False)
    monkeypatch.setattr(service,'_log_run_event',lambda *args:None)
    assert service._reconcile_cancel_requested_runs(conn)==expected
    updates=[s for s,_ in conn.executed if s.lstrip().startswith('UPDATE')]
    assert bool(updates)==(expected==1 or advanced)
    assert not any('embedding_v2' in s or 'recommendations' in s or 'shap_' in s for s in updates)
    assert any(s.lstrip().startswith('UPDATE public.pipeline_run_stages') for s in updates)==bool(expected)


def test_dead_child_with_controller_still_holding_lock_is_not_reconciled(monkeypatch):
    row=dict(run_id=999,status='started',current_pid=123,last_heartbeat_at=datetime.now(timezone.utc)-timedelta(minutes=5))
    conn=FakeConnection([],[[row]])
    monkeypatch.setattr(service,'_process_exists',lambda _:False)
    monkeypatch.setattr(service,'_pipeline_execution_locked',lambda:True)
    assert service._reconcile_cancel_requested_runs(conn)==0
    assert not any(s.lstrip().startswith('UPDATE') for s,_ in conn.executed)


def test_interrupted_structured_stage_stops_its_clock_but_keeps_evidence():
    payload=dict(event('training_data'),timing_active=True,elapsed_seconds=50,metrics=dict(rows=10))
    result=event_details(dict(stage_key='training_data',status='failed',stdout_tail=json.dumps(payload),stderr_tail='Worker interrupted'))
    assert not result['timing_active'] and result['duration_seconds']==50
    assert result['metrics']=={'rows':10} and result['message']=='Worker interrupted'


def test_live_stage_details_use_existing_public_logs_without_migration_queries():
    child=dict(stage_key='media_text',status='success',stdout_tail=json.dumps(event('media_text','success')))
    run=dict(run_id=999,status='success',stages=[dict(stage_key='predictive_daily',stdout_tail=None),child])
    conn=FakeConnection([]);enrich_runs(conn.cursor(),[run])
    assert run['stage_details'][0]['stage_key']=='media_text'
    assert conn.executed==[]


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


def test_historical_logs_remain_visible_without_querying_retired_journals():
    run=dict(stages=[dict(stage_key='embeddinggemma2_generation',stdout_tail='original log')])
    before=deepcopy(run['stages']);conn=FakeConnection([])
    enrich_runs(conn.cursor(),[run])
    assert run['stages']==before and 'not queried' in run['stage_detail_note']
    assert conn.executed==[]


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
    assert len(rows)==len(STAGES)
    watch=event_details(next(r for r in rows if r['stage_key']=='watch'))
    assert watch['status']=='success' and watch['duration_seconds']==1
    assert next(r for r in rows if r['stage_key']=='verification')['status']=='skipped'


def test_real_private_sql_interruption_and_checkpoint_title_recovery(store,monkeypatch):
    from psycopg2.extras import RealDictCursor,Json
    store.query('''CREATE TEMP TABLE observed_runs(run_id integer,status text,delivery_type text,
        current_pid integer,current_stage_key text,last_heartbeat_at timestamptz,cancel_requested_at timestamptz,
        notes text,completed_at timestamptz);
        CREATE TEMP TABLE observed_stages(run_id integer,stage_key text,status text,completed_at timestamptz,
        stderr_tail text);
        INSERT INTO observed_runs VALUES(999,'started','manual',123,'training_data',now()-interval '5 minutes',NULL,NULL,NULL);
        INSERT INTO observed_stages(run_id,stage_key,status) VALUES
        (999,'media_text','success'),(999,'training_data','started'),(999,'train_model','pending')''')
    class Cursor:
        def __enter__(self):self.cur=store.conn.cursor(cursor_factory=RealDictCursor);return self
        def __exit__(self,*args):self.cur.close()
        def execute(self,statement,args=None):
            statement=statement.replace('public.pipeline_runs','pg_temp.observed_runs').replace(
                'public.pipeline_run_stages','pg_temp.observed_stages').replace('embedding_v2.','pg_temp.')
            self.cur.execute(statement,args)
        def fetchall(self):return self.cur.fetchall()
        def fetchone(self):return self.cur.fetchone()
    class Connection:
        def cursor(self,**kwargs):return Cursor()
    monkeypatch.setattr(service,'_process_exists',lambda _:False)
    monkeypatch.setattr(service,'_pipeline_execution_locked',lambda:False)
    monkeypatch.setattr(service,'_log_run_event',lambda *args:None)
    assert service._reconcile_cancel_requested_runs(Connection())==1
    assert store.query('SELECT status FROM observed_runs')['status']=='failed'
    statuses={r['stage_key']:r['status'] for r in store.query('SELECT * FROM observed_stages',many=True)}
    assert statuses==dict(media_text='success',training_data='failed',train_model='skipped')
    store.query("INSERT INTO pg_temp.production_runs(run_id,generation_id,base_model_sha256,status,stages,summary) VALUES(%s,'fictional','fictional','running','{}','{}')",(RID,))
    source=dict(title='Fictional Beacon',media_type='episode',metadata=dict(episode_title='Fictional Beacon',show_context=dict(title='Fictional Series')))
    store.query('INSERT INTO pg_temp.production_run_items(run_id,kind,item_key,record) VALUES(%s,\'media_text\',\'42\',%s)',(RID,Json(dict(source=source))))
    for key,kind in [('42','media_text'),('private-watch','watch')]:
        store.query('INSERT INTO pg_temp.production_run_requests(request_id,run_id,kind,item_key,status,stats) VALUES(%s,%s,%s,%s,\'succeeded\',\'{}\')',(key,RID,kind,key))
    run=dict(stages=[dict(stage_key='embeddinggemma2_generation',stdout_tail=None),
        dict(stage_key='media_text',status='success',stdout_tail=json.dumps(event('media_text','success')))])
    with Cursor() as cur:enrich_runs(cur,[run])
    # Retired journals are deliberately not a serving dependency. Public events
    # survive, but private title checkpoints are no longer recoverable here.
    assert run['stage_details'][0]['stage_key']=='media_text'
    assert 'embedded_media' not in run
