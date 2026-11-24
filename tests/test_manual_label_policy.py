"""Explicit labeling shares financial policy, independently of daily enablement."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock,Mock

import pytest
from psycopg2.extras import Json

from api.services import dimension_label_batch as batch,pipeline_labeling as policy,app_settings
from api.services.labeling_costs import BudgetExceeded,Pricing,UsageLedger,cumulative_usage
from tests.test_pipeline_labeling import ledger_db
from tests.test_semantic_labeling import context_fixture,response

DIMENSIONS=[136,219,239,375,555,678]


@pytest.fixture
def manual_policy(monkeypatch):
    values={'pipeline.labeling_enabled':False,'pipeline.labeling_cloud_authorized':True,
            'pipeline.labeling_budget_usd':10.}
    resolver=Mock(side_effect=lambda **kw:{k:SimpleNamespace(value=values[k]) for k in kw['keys']})
    monkeypatch.setattr(policy,'resolve_settings',resolver)
    return values,resolver


def test_explicit_policy_skips_only_automatic_enablement(manual_policy):
    values,resolver=manual_policy
    assert policy.limits(automatic=False)==dict(budget_usd=10.)
    assert resolver.call_args.kwargs['keys']==('pipeline.labeling_cloud_authorized','pipeline.labeling_budget_usd')
    assert resolver.call_args.kwargs['require_database'] is True
    with pytest.raises(BudgetExceeded,match='Automatic labeling disabled'):policy.limits()
    # Malformed/missing automatic configuration cannot disable explicit actions.
    values['pipeline.labeling_enabled']='invalid'
    assert policy.limits(automatic=False)==dict(budget_usd=10.)
    del values['pipeline.labeling_enabled']
    assert policy.limits(automatic=False)==dict(budget_usd=10.)


@pytest.mark.parametrize('key,value,message',[
    ('pipeline.labeling_cloud_authorized',False,'Standing cloud authorization absent'),
    ('pipeline.labeling_budget_usd',0.,'Positive cumulative budget'),
    ('pipeline.labeling_budget_usd',float('nan'),'Positive cumulative budget'),
])
def test_manual_policy_preserves_cloud_and_financial_denials(manual_policy,key,value,message):
    manual_policy[0][key]=value
    with pytest.raises(BudgetExceeded,match=message):policy.limits(automatic=False)


def test_explicit_policy_database_outage_fails_closed(manual_policy):
    manual_policy[1].side_effect=app_settings.SettingsUnavailableError('synthetic outage')
    with pytest.raises(BudgetExceeded,match='Authoritative labeling policy unavailable'):
        policy.limits(automatic=False)


@pytest.fixture
def cli(monkeypatch,manual_policy):
    import gpt_utils as gpt
    config,_,context=context_fixture();conn=MagicMock();evidence=Mock(context=context)
    rows=[dict(dimension=d,side='media',completed=True,abstained=False,
               prompt=dict(prompt_text='synthetic contrast '+str(d))) for d in DIMENSIONS]
    monkeypatch.setattr(batch,'connect_db',lambda:conn)
    lock=Mock(return_value=nullcontext());monkeypatch.setattr(batch,'batch_lock',lock)
    monkeypatch.setattr(batch,'get_active_config',lambda cur:config)
    monkeypatch.setattr(batch,'current_context',lambda c:context)
    monkeypatch.setattr(batch,'Evidence',Mock(return_value=evidence))
    monkeypatch.setattr(batch,'candidates',lambda *a,**kw:(rows,{}))
    monkeypatch.setattr(policy,'_attempt_counts',lambda *a:{})
    monkeypatch.setattr(policy,'cumulative_usage',lambda *a:dict(requests=50,estimated_cost_usd=.1))
    monkeypatch.setattr(UsageLedger,'observations',lambda *a:{})
    monkeypatch.setattr(gpt,'resolve_label_backend',lambda *a:('ollama','gemma4:31b-cloud'))
    monkeypatch.setattr(gpt,'label_output_limit',lambda *a:1024)
    cloud=Mock(side_effect=AssertionError('No actual cloud inference allowed'))
    monkeypatch.setattr(gpt,'call_llm_for_label_result',cloud)
    execute=Mock(return_value=dict(status='completed'));monkeypatch.setattr(batch,'execute',execute)
    return conn,lock,execute,cloud


@pytest.mark.parametrize('review',[False,True])
def test_actual_cli_and_admin_review_cli_reach_execution_while_automatic_disabled(cli,review):
    conn,lock,execute,cloud=cli
    args=(['--dimension','136','--dim_type','media','--selection_mode','review','--label','--save_label'] if review
          else ['--label','--dim-type','media','--regenerate','--dimensions',*map(str,DIMENSIONS)])
    assert batch.main(args)['status']=='completed'
    selected=execute.call_args.args[3]
    assert [r['dimension'] for r in selected]==([136] if review else DIMENSIONS)
    assert execute.call_args.args[5].save_label is review
    lock.assert_called_once();cloud.assert_not_called()


@pytest.mark.parametrize('fault',['unauthorized','spent'])
def test_manual_cli_denial_precedes_evidence_and_execution(cli,manual_policy,monkeypatch,fault):
    if fault=='unauthorized':manual_policy[0]['pipeline.labeling_cloud_authorized']=False
    else:monkeypatch.setattr(policy,'cumulative_usage',lambda *a:dict(estimated_cost_usd=10.))
    with pytest.raises(BudgetExceeded):batch.main(['--label','--dim-type','media','--regenerate','--dimensions','136'])
    batch.Evidence.assert_not_called();cli[2].assert_not_called();cli[3].assert_not_called()


def test_dry_run_still_bypasses_execution_authorization(cli,manual_policy):
    manual_policy[0]['pipeline.labeling_cloud_authorized']=False
    batch.main(['--dry-run','--label','--dim-type','media','--regenerate','--dimensions','136'])
    manual_policy[1].assert_not_called();cli[2].assert_not_called();cli[3].assert_not_called()


def test_manual_mode_does_not_bypass_media_scope(cli):
    with pytest.raises(SystemExit):batch.main(['--label','--dim-type','media','--dimension','768'])
    batch.Evidence.assert_not_called();cli[2].assert_not_called();cli[3].assert_not_called()


@pytest.fixture
def sql_manual_policy(ledger_db,monkeypatch):
    db=ledger_db
    db.query('''CREATE TEMP TABLE app_settings(key text PRIMARY KEY,raw_value text,source text,
        updated_at timestamptz,updated_by text,description text)''')
    for key,value in [('pipeline.labeling_enabled','false'),('pipeline.labeling_cloud_authorized','true'),('pipeline.labeling_budget_usd','1')]:
        db.query('INSERT INTO pg_temp.app_settings(key,raw_value,source) VALUES(%s,%s,\'fixture\')',(key,value))
    db.conn.commit()
    monkeypatch.setattr(app_settings,'SETTINGS_TABLE','pg_temp.app_settings')
    return db


@pytest.mark.parametrize('change',['none','authorization','cumulative_budget','batch_budget','retry'])
def test_sql_manual_execution_and_each_reservation_use_shared_limits(sql_manual_policy,monkeypatch,change):
    import gpt_utils as gpt
    db=sql_manual_policy;ctx=context_fixture()[2]
    rows=[dict(dimension=d,side='media',completed=True,abstained=False,
               prompt=dict(prompt_text='synthetic '+str(d),positive_items=[{}]*6,negative_items=[{}]*4)) for d in (136,219)]
    args=batch.parser().parse_args(['--label','--regenerate','--dimensions','136','219'])
    args.label_model='gemma4:31b-cloud';args.label_provider='ollama';args.max_output_tokens=1024
    args.budget_usd=1.
    if change=='retry':
        # Exhaust only the second prompt, preserving a first admissible request.
        from tests.test_pipeline_labeling import new_auto_ledger
        for _ in range(3):
            ledger=new_auto_ledger(db,prompt=batch.prompt_hash(rows[1]['prompt']))
            # Use the actual context/prompt association and the same existing scope.
            ledger.automation['feature_space_id']=ctx['feature_space_id']
            ledger.automation['prompts']={'219':batch.prompt_hash(rows[1]['prompt'])}
            db.query('UPDATE pg_temp.embedding_label_batches SET feature_space_id=%s,forecast=%s WHERE batch_id=%s',
                (ctx['feature_space_id'],Json(dict(automation_scope=policy.SCOPE,automation_prompts=ledger.automation['prompts'])),ledger.batch_id))
            db.conn.commit();ledger.start(219,'media',1,'synthetic 219','system',1024)
    monkeypatch.setattr(batch,'current_context',lambda conn:ctx)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    monkeypatch.setattr(batch,'record_assessment',Mock())
    monkeypatch.setattr(batch,'workload_forecast',lambda *a:dict(all_remaining={}))
    calls=[]
    def provider(*a,**kw):
        calls.append(kw['dimension_mode'])
        kw['on_usage'](dict(prompt_eval_count=100,eval_count=50))
        if len(calls)==1 and change in ('authorization','cumulative_budget'):
            key='pipeline.labeling_cloud_authorized' if change=='authorization' else 'pipeline.labeling_budget_usd'
            value='false' if change=='authorization' else '0.000001'
            db.query('UPDATE pg_temp.app_settings SET raw_value=%s WHERE key=%s',(value,key));db.conn.commit()
        return response()
    cloud=Mock(side_effect=provider);monkeypatch.setattr(gpt,'_call_ollama_for_label_result',cloud)
    forecast=dict(selected_batch=dict(combined=dict(expected=dict(cost_usd=.001))))
    # Lower the batch allowance after its first real reservation, avoiding a
    # dependence on estimated prompt size in the batch-budget assertion.
    if change=='batch_budget':
        original_start=UsageLedger.start
        def start(ledger,*a,**kw):
            result=original_start(ledger,*a,**kw)
            ledger.budget=ledger.total_cost()
            return result
        monkeypatch.setattr(UsageLedger,'start',start)
    result=batch.execute(db.conn,Mock(context=ctx),rows,rows,Pricing(),args,forecast,output=lambda value:None)
    assert result['status']==('completed' if change=='none' else 'budget_stopped')
    assert cloud.call_count==(2 if change=='none' else 1)
    assert result['usage']['requests']==cloud.call_count
    assert args.automation['scope']==policy.SCOPE
    db.conn.rollback()
    if change!='authorization':assert policy.limits(db.conn,automatic=False)['budget_usd']>0
    with pytest.raises(BudgetExceeded,match='Automatic labeling disabled'):policy.limits(db.conn)
    db.conn.rollback()
    assert db.query("SELECT raw_value FROM pg_temp.app_settings WHERE key='pipeline.labeling_enabled'")['raw_value']=='false'
