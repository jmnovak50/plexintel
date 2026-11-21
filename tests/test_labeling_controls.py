"""Budget-only admission, bounded exact evidence, and one-owner operational logs."""
from contextlib import nullcontext
import json
from unittest.mock import Mock,MagicMock
import pytest
from api.services import dimension_label_batch as batch,pipeline_labeling as auto,app_settings
from api.services.labeling_costs import BudgetExceeded,Pricing
from api.predictive.progress import Reporter,EVENT,ITEM_EVENT,labeling_metrics,labeling_status
from api.services.pipeline_logs import get_stage_logs
from tests.test_pipeline_log_view import fixture,event
from tests.test_pipeline_labeling import setup


@pytest.mark.parametrize('obsolete',[0,-1,'invalid',None])
def test_obsolete_request_limit_is_not_a_policy_input_or_configuration(setup,obsolete):
    settings,*_=setup
    settings['pipeline.labeling_request_limit']=obsolete
    assert auto.limits()==dict(budget_usd=1.)
    assert setup[-1]()['status']=='completed'
    with pytest.raises(app_settings.SettingsValidationError):
        app_settings.get_setting_definition('pipeline.labeling_request_limit')


def test_exhausted_finances_skip_evidence_and_batch_creation(setup,monkeypatch):
    monkeypatch.setattr(auto,'cumulative_usage',lambda *a:dict(requests=99999,estimated_cost_usd=1.))
    outcome=setup[-1]()
    assert outcome['status']=='skipped' and 'financial allowance exhausted' in outcome['reason']
    setup[6].assert_not_called();setup[7].assert_not_called()
    assert len([v for v in setup[9] if v.get('status')])==1


@pytest.mark.parametrize('reason',['authorization','exhausted'])
def test_manual_generation_checks_policy_before_evidence(monkeypatch,reason):
    import gpt_utils as gpt
    monkeypatch.setattr(batch,'connect_db',Mock(return_value=MagicMock()))
    monkeypatch.setattr(batch,'batch_lock',lambda:nullcontext())
    monkeypatch.setattr(gpt,'resolve_label_backend',lambda *a:('ollama','gemma4:31b-cloud'))
    monkeypatch.setattr(gpt,'label_output_limit',lambda *a:1024)
    if reason=='authorization':monkeypatch.setattr(auto,'limits',Mock(side_effect=BudgetExceeded('Standing cloud authorization absent')))
    else:
        monkeypatch.setattr(auto,'limits',lambda **kw:dict(budget_usd=10.))
        monkeypatch.setattr(auto,'cumulative_usage',lambda *a:dict(estimated_cost_usd=10.))
    evidence=Mock();execute=Mock();monkeypatch.setattr(batch,'Evidence',evidence);monkeypatch.setattr(batch,'execute',execute)
    with pytest.raises(BudgetExceeded):batch.main(['--label','--save-label','--selection-mode','eligible'])
    evidence.assert_not_called();execute.assert_not_called()


def candidate_fixture():
    dims=[12,24,36,48,60,72,84,800]
    def prompt(d):return dict(prompt_text='exact fixture '+str(d),skipped_reason='No LOW contrast' if d==60 else None)
    def conn():
        c=MagicMock();c.cursor.return_value.__enter__.return_value.fetchall.side_effect=[
            [(d,1.) for d in dims],[],[(12,True),(24,False)],[(36,batch.prompt_hash(prompt(36)))]]
        return c
    attempts={(48,batch.prompt_hash(prompt(48))):3}
    return conn,Mock(context=dict(config_id='c',model_sha256='m',feature_space_id='f'),prompt=Mock(side_effect=prompt)),attempts


@pytest.mark.parametrize('mode',['eligible','importance','review'])
@pytest.mark.parametrize('side',['all','media','user'])
def test_bounded_selection_matches_full_evidence_semantics(mode,side):
    make,evidence,attempts=candidate_fixture()
    args=batch.parser().parse_args(['--selection-mode',mode,'--dim-type',side,'--limit','2'])
    full,_=batch.candidates(make(),evidence,output=lambda v:None)
    admitted=[r for r in full if attempts.get((r['dimension'],batch.prompt_hash(r['prompt'])),0)<args.max_attempts]
    expected=batch.choose(admitted,args)
    evidence.prompt.reset_mock()
    bounded,_=batch.candidates(make(),evidence,args=args,attempt_counts=attempts,output=lambda v:None)
    actual=batch.choose(bounded,args)
    assert actual==expected
    assert len(actual)<=2
    assert args.evidence_scope=='selected_batch'
    if mode=='eligible' and side=='all':
        assert [r['dimension'] for r in actual]==[72,84]
        assert [c.args[0] for c in evidence.prompt.call_args_list]==[36,48,60,72,84]
    args.label_model='gemma4:31b-cloud';args.label_provider='ollama'
    forecast=batch.workload_forecast(bounded,actual,Pricing(),args,{})
    assert forecast['evidence_scope']=='selected_batch' and forecast['all_remaining'] is None


def test_one_terminal_summary_and_announcement_with_live_state_and_receipt(setup,monkeypatch,tmp_path):
    summary=dict(status='completed',selected=1,assessed=1,successes=1,reviews=0,abstentions=0,failures=0,
        usage=dict(requests=1,input_tokens=80,output_tokens=20,total_tokens=100,estimated_cost_usd=.01))
    def execute(*args,output,**kw):
        output(dict(preparing_prompts=1,ranked_dimensions=1000))
        output(dict(event='request_started',dimension=2,usage=dict(requests=1)))
        output(dict(dimension=2,outcome='inserted_missing_label',assessed=1,successes=1))
        output(dict(final_status='completed',**summary))
        return dict(summary)
    monkeypatch.setattr(batch,'execute',execute)
    records=[];reporter=Reporter(records.append)
    def notify(value):
        reporter.log('semantic_labels','labeling',data=dict(value))
        reporter.progress('semantic_labels',**labeling_metrics(value))
    with reporter.span('semantic_labels'):
        result=auto.run_after_publication(setup[1],output=notify)
    reporter.emit('semantic_labels',labeling_status(result['status']),**labeling_metrics(result))
    records.append(dict(verified=True,run_id='fixture',counts={},evaluation={},summary={},semantic_labeling=result))
    terminal=[v['data'] for v in records if v.get('event')==ITEM_EVENT and v.get('data',{}).get('status')]
    assert len(terminal)==1 and terminal[0]['assessed']==1
    states=[v for v in records if v.get('event')==EVENT]
    assert states[-1]['status']=='success' and states[-1]['metrics']['completed']==1
    run=fixture(tmp_path,monkeypatch,''.join(json.dumps(v)+'\n' for v in records))
    text=get_stage_logs(run,'semantic_labels')['stdout']['text']
    assert text.count('🔄 Semantic dimension labeling...')==1
    assert text.count('Labeling outcome: completed.')==1
    assert 'Dimension 2: inserted missing label' in text
    assert 'Cumulative requests: 1,000' in text and 'Cumulative known input tokens: 200' in text
    assert 'cumulative request limit' not in text and 'Cumulative requests: 1,000 /' not in text
