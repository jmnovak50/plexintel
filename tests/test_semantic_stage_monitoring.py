"""Stage ownership/lifecycle using retained records and mocked labelers only."""
import json
from copy import deepcopy
from unittest.mock import MagicMock
from contextlib import nullcontext
import pytest

from api.predictive.progress import Reporter,EVENT,ITEM_EVENT,labeling_metrics,labeling_status
from api.services.pipeline_logs import get_stage_logs
from api.services.pipeline_visibility import enrich_runs
from tests.test_pipeline_log_view import fixture,event
from tests.test_pipeline_labeling import setup


def test_labeling_has_its_own_complete_streams_not_publication_or_worker(tmp_path,monkeypatch):
    records=[];r=Reporter(records.append)
    with r.span('semantic_labels'):
        r.log('semantic_labels','labeling',data=dict(dimension=12,outcome='inserted_missing_label',assessed=1,
            selected=2,successes=1,reviews=0,abstentions=0,usage=dict(requests=2,estimated_cost_usd=.001234),
            cumulative_usage=dict(requests=9,estimated_cost_usd=.012345),limits=dict(request_limit=100,budget_usd=1.)))
        r.progress('semantic_labels',**labeling_metrics(dict(assessed=1,selected=2,usage=dict(requests=2,estimated_cost_usd=.001234))))
    r.emit('semantic_labels','success')
    raw=event('publication','success')+event('verification','success')+''.join(json.dumps(v)+'\n' for v in records)
    stderr=json.dumps(dict(stage_key='semantic_labels',error='Fictional labeling stderr'))+'\n'
    run=fixture(tmp_path,monkeypatch,raw,stderr)
    label=get_stage_logs(run,'semantic_labels')
    assert 'Dimension 12' in label['stdout']['text'] and 'Accepted labels: 1' in label['stdout']['text']
    assert 'Cloud requests / attempts: 2' in label['stdout']['text']
    assert '$0.001234' in label['stdout']['text'] and '$0.012345 / $1.000000' in label['stdout']['text']
    assert 'Cumulative requests: 9 / 100' in label['stdout']['text']
    assert 'Fictional labeling stderr' in label['stderr']['text']
    for key in ('publication','predictive_daily'):
        text=json.dumps(get_stage_logs(run,key))
        assert 'Dimension 12' not in text and 'Fictional labeling stderr' not in text
    stage_events=[v for v in records if v['event']==EVENT]
    assert stage_events[0]['status']=='started' and stage_events[-1]['status']=='success'
    assert stage_events[-1]['elapsed_seconds']>=0 and stage_events[-1]['timing_known']
    assert stage_events[-1]['metrics']['completed']==1


def test_live_labeling_lines_append_in_their_own_card(tmp_path,monkeypatch):
    run=fixture(tmp_path,monkeypatch,event('semantic_labels')+'Label evidence first\n')
    before=get_stage_logs(run,'semantic_labels')['stdout']['text']
    with (tmp_path/'pipeline-run-999-predictive_daily-fixture.stdout.log').open('a') as f:
        f.write(json.dumps(dict(event=ITEM_EVENT,stage_key='semantic_labels',operation='labeling',
            data=dict(dimension=24,outcome='abstained',assessed=2,abstentions=1)))+'\n')
    after=get_stage_logs(run,'semantic_labels')['stdout']['text']
    assert after.startswith(before) and 'Dimension 24: abstained' in after
    assert 'Dimension 24' not in get_stage_logs(run,'publication')['stdout']['text']


def test_historical_untagged_batch_output_and_skip_are_label_owned(tmp_path,monkeypatch):
    values=[dict(batch_id='fictional',status='completed',selected=2,assessed=2,successes=1,abstentions=1),
            dict(status='skipped',reason='Standing cloud authorization absent')]
    run=fixture(tmp_path,monkeypatch,'\n'.join(json.dumps(v) for v in values)+'\n')
    text=get_stage_logs(run,'semantic_labels')['stdout']['text']
    assert 'Accepted labels: 1' in text and 'Standing cloud authorization absent' in text
    assert 'Standing cloud authorization absent' not in get_stage_logs(run,'publication')['stdout']['text']
    assert 'Accepted labels' not in get_stage_logs(run,'predictive_daily')['stdout']['text']


def test_missing_labeling_event_keeps_an_honest_stage_and_receipt_outcome(monkeypatch):
    import api.services.pipeline_visibility as visibility
    report=dict(verified=True,semantic_labeling=dict(status='skipped',reason='Automatic labeling disabled'))
    monkeypatch.setattr(visibility,'retained_report',lambda *a:report)
    run=dict(run_id=999,status='success',stages=[dict(stage_key='predictive_daily',status='success')])
    enrich_runs(MagicMock(),[run]);stage=next(s for s in run['stage_details'] if s['stage_key']=='semantic_labels')
    assert stage['status']=='skipped' and stage['message']=='Automatic labeling disabled'
    assert stage['duration_seconds'] is None and not stage['timing_known']
    assert not stage['metrics']


@pytest.mark.parametrize('labeling',['Legacy labeling disabled for this feature space',None,['older unsupported shape']])
def test_archived_nonobject_labeling_receipt_does_not_break_recent_runs(monkeypatch,labeling):
    import api.services.pipeline_visibility as visibility
    report=dict(run_id='old-receipt',promotion_id='archived-pub',verified=True,stages={},semantic_labeling=labeling)
    monkeypatch.setattr(visibility,'retained_report',lambda *a:report)
    run=dict(run_id=999,status='success',stages=[dict(stage_key='embeddinggemma2_generation',status='success')])
    original=deepcopy(run['stages'])
    enrich_runs(MagicMock(),[run])
    stage=next(s for s in run['stage_details'] if s['stage_key']=='semantic_labels')
    assert stage['status']=='not_recorded' and stage['duration_seconds'] is None
    assert run['stages']==original


def test_denied_policy_reports_actual_snapshot_and_duration_without_provider(setup):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    settings['pipeline.labeling_cloud_authorized']=False
    outcome=run()
    assert outcome['status']=='skipped' and outcome['seconds']>=0
    assert events[0]['policy']['pipeline.labeling_cloud_authorized'] is False
    assert events[-1]['reason']=='Standing cloud authorization absent'
    execute.assert_not_called();connect.assert_not_called();evidence.assert_not_called()
    assert summary==result['summary']


def test_batch_progress_observes_actual_attempts_acceptances_reviews_and_abstentions(monkeypatch):
    import gpt_utils as gpt
    from api.services import dimension_label_batch as batch
    from api.services.labeling_costs import Pricing
    ctx=dict(media_dimensions=768,user_dimensions=768,config_id='fictional-config',feature_space_id='fictional-space')
    requests=[];events=[];review_calls=[]
    class Ledger:
        def __init__(self,*a,**kw):pass
        def observations(self,*a):return {}
        def start(self,dimension,*a):requests.append(dimension);return len(requests)
        def finish(self,*a):pass
        def total_cost(self):return len(requests)*.01
    def usage(*args):
        total=dict(requests=len(requests),input_tokens=len(requests)*100,output_tokens=len(requests)*10,
            total_tokens=len(requests)*110,estimated_cost_usd=len(requests)*.01,token_totals_are_complete=True)
        return dict(combined=total,media=total,user=total)
    def label(prompt,**kw):
        kw['before_attempt'](1);kw['attempt_callback'](1,{},None)
        return dict(label=gpt.UNCLEAR_LABEL if prompt=='abstain' else 'Fictional reviewed label')
    monkeypatch.setattr(batch,'UsageLedger',Ledger)
    monkeypatch.setattr(batch,'usage_report',usage)
    monkeypatch.setattr(batch,'current_context',lambda c:ctx)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    monkeypatch.setattr(batch,'validate_sample_counts',lambda value,prompt:value)
    def persist(c,ctx,row,*a,**kw):
        review_calls.append(kw['regenerate'])
        return row['dimension']==12,'updated_review_label' if row['dimension']==12 else 'abstained'
    monkeypatch.setattr(batch,'persist_result',persist)
    monkeypatch.setattr(batch,'workload_forecast',lambda *a:dict(all_remaining={}))
    monkeypatch.setattr(gpt,'call_llm_for_label_result',label)
    args=batch.parser().parse_args(['--label','--save-label']);args.automation={'scope':'fictional'}
    args.label_model='fictional';args.max_output_tokens=1024
    rows=[dict(dimension=12,side='media',completed=True,review_due=True,prompt=dict(prompt_text='review')),
          dict(dimension=24,side='media',completed=False,prompt=dict(prompt_text='abstain'))]
    evidence=MagicMock(context=ctx)
    result=batch.execute(MagicMock(),evidence,rows,rows,Pricing(),args,
        dict(selected_batch=dict(combined=dict(expected=dict(cost_usd=.02)))),output=events.append)
    assert requests==[12,24]
    assert review_calls==[True,False]
    assert result['assessed']==2 and result['reviews']==1 and result['successes']==1 and result['abstentions']==1
    started=[e for e in events if e.get('event')=='request_started']
    assert [e['usage']['requests'] for e in started]==[1,2]
    assert started[-1]['usage']['estimated_cost_usd']==.02
    updates=[e for e in events if 'progress' in e]
    assert [e['assessed'] for e in updates]==[1,2]
    assert updates[-1]['reviews']==1 and updates[-1]['abstentions']==1


@pytest.mark.parametrize('outcome,status',[('completed','success'),('empty','success'),('budget_stopped','skipped'),
    ('completed_with_errors','failed'),('systemic_failure_stopped','failed'),('interrupted','failed'),('skipped','skipped')])
def test_labeling_terminal_states_are_explicit_and_clock_owned_by_stage(outcome,status):
    assert labeling_status(outcome)==status
    assert 'seconds' not in labeling_metrics(dict(seconds=8,assessed=2))
