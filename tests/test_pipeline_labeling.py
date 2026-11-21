"""Automatic labeling reuses the existing batch engine; all provider calls mocked."""
from contextlib import nullcontext
from copy import deepcopy
from unittest.mock import MagicMock,Mock
import json
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg2 import sql
from psycopg2.extras import Json

from api.services import pipeline_labeling as auto,dimension_label_batch as batch
from api.services.labeling_costs import UsageLedger,Pricing,BudgetExceeded,usage_report
from tests.test_semantic_labeling import response


@pytest.fixture
def setup(monkeypatch):
    import gpt_utils as gpt
    settings={'pipeline.labeling_enabled':True,'pipeline.labeling_cloud_authorized':True,
              'pipeline.labeling_budget_usd':1.}
    monkeypatch.setattr(auto,'get_setting_value',lambda key,default=None:settings.get(key,default))
    monkeypatch.setattr(auto,'resolve_settings',lambda **kw:{key:SimpleNamespace(value=settings[key]) for key in kw['keys']})
    ctx=dict(feature_space_id='generation',publication_id='publication',model_sha256='model',config_id='config')
    summary=dict(outcome='daily_completed',model_after='model',final_verification=dict(ctx,verified=True))
    result=dict(verified=True,model_sha256='model',run_id='daily-run',feature_space_id='generation',promotion_id='publication',summary=deepcopy(summary))
    conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value=None
    from api.predictive import artifacts
    monkeypatch.setattr(artifacts,'current_config',lambda c:dict(workload_id=result['promotion_id'],model_sha256='model'))
    cur.fetchall.return_value=[]
    connect=Mock(return_value=conn);monkeypatch.setattr(auto,'connect_db',connect)
    monkeypatch.setattr(auto,'current_context',lambda c:ctx)
    evidence=Mock(context=ctx);factory=Mock(return_value=evidence);monkeypatch.setattr(auto,'Evidence',factory)
    monkeypatch.setattr(gpt,'resolve_label_backend',lambda:('ollama','gemma4:31b-cloud'))
    monkeypatch.setattr(gpt,'label_output_limit',lambda v:1024)
    rows=[dict(dimension=i,side='media',completed=i==0,abstained=i==1,
               prompt=dict(prompt_text='fictional '+str(i))) for i in range(3)]
    monkeypatch.setattr(batch,'candidates',lambda c,e,**kw:([r for r in rows if r['dimension'] not in kw.get('exclude_dimensions',())],{}))
    monkeypatch.setattr(auto,'_attempt_counts',lambda *a:{})
    monkeypatch.setattr(auto,'cumulative_usage',lambda *a:dict(requests=1000,estimated_cost_usd=0.,input_tokens=200,output_tokens=100,total_tokens=300))
    monkeypatch.setattr(auto,'_eligible_attempts',lambda c,r,ctx,n:r)
    monkeypatch.setattr(UsageLedger,'observations',lambda *a:{})
    monkeypatch.setattr(batch,'workload_forecast',lambda *a:dict(selected_batch=dict(combined=dict(expected=dict(cost_usd=0.01)))))
    execute=Mock(return_value=dict(status='completed',successes=1,failures=0,abstentions=0,selected=1,usage=dict(requests=1,input_tokens=100,output_tokens=30,total_tokens=130,estimated_cost_usd=.01)))
    monkeypatch.setattr(batch,'execute',execute)
    model_store=Mock();model_store.table.side_effect=lambda n:sql.Identifier('fixture',n)
    events=[]
    def run():return auto.run_after_publication(result,output=events.append)
    return settings,result,summary,conn,cur,connect,factory,execute,model_store,events,run


@pytest.mark.parametrize('key,value',[('pipeline.labeling_enabled',False),('pipeline.labeling_cloud_authorized',False),
    ('pipeline.labeling_budget_usd',0.),('pipeline.labeling_budget_usd',float('nan'))])
def test_disabled_unauthorized_or_unbudgeted_never_opens_label_connection(setup,key,value):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    settings[key]=value
    assert run()['status']=='skipped'
    connect.assert_not_called();evidence.assert_not_called();execute.assert_not_called()
    assert 'final_verification' in result['summary'] and result['summary']['model_after']=='model'


def test_authorized_stage_uses_existing_selection_only_after_exact_verification(setup):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    outcome=run();assert outcome['status']=='completed'
    args=execute.call_args.args[5];selected=execute.call_args.args[3]
    assert [r['dimension'] for r in selected]==[2]  # Saved label and same-prompt abstention retained.
    assert args.label_model=='gemma4:31b-cloud' and args.max_output_tokens==1024
    assert args.automation['scope']==auto.SCOPE and args.automation['max_attempts']==3
    assert execute.call_args.args[6]['automation_publication_id']=='publication'
    assert events[-1]['status']=='completed'
    assert all('production_runs' in str(c.args[0]) for c in store.query.call_args_list)


@pytest.mark.parametrize('fault',['unverified','stale'])
def test_unverified_stale_or_failed_publication_cannot_label(setup,monkeypatch,fault):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    if fault=='unverified':result['verified']=False
    else:
        from api.predictive import artifacts
        monkeypatch.setattr(artifacts,'current_config',lambda c:dict(workload_id='stale',model_sha256='model'))
    assert run()['status'] in ('failed','skipped')
    evidence.assert_not_called();execute.assert_not_called()


@pytest.mark.parametrize('error',[RuntimeError('sensitive provider URL'),KeyboardInterrupt()])
def test_label_failure_or_interrupt_does_not_invalidate_publication(setup,error):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    execute.side_effect=error
    original=deepcopy(result['summary']['final_verification'])
    assert run()['status'] in ('failed','interrupted')
    assert result['summary']['final_verification']==original and result['summary']['outcome']=='daily_completed'
    assert not any("status='failed'" in str(c.args[0]) for c in store.query.call_args_list)
    assert 'sensitive provider URL' not in json.dumps(events)


def test_recovery_only_does_not_touch_unrelated_run_or_cloud(setup):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    result['verification_only']=True
    assert run()['status']=='skipped'
    connect.assert_not_called();store.query.assert_not_called();execute.assert_not_called()


def test_terminal_label_work_is_not_repeated_after_restart(setup):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    done=dict(status='completed',successes=1,abstentions=2,usage=dict(requests=3))
    cur.fetchone.return_value=('old-batch','completed',done)
    outcome=run();assert outcome['status']=='completed' and outcome['reused']
    assert outcome['usage']['requests']==3
    evidence.assert_not_called();execute.assert_not_called()


def test_budget_and_authorization_can_be_revoked_between_attempts(setup):
    settings,*_=setup
    assert auto.limits()==dict(budget_usd=1.)
    settings['pipeline.labeling_cloud_authorized']=False
    with pytest.raises(BudgetExceeded):auto.limits()


def test_explicit_refresh_does_not_repeat_saved_or_abstained_work_in_same_publication(setup):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    settings['pipeline.refresh_existing_labels']=True
    cur.fetchall.return_value=[(0,),(1,)]
    assert run()['status']=='completed'
    assert [r['dimension'] for r in execute.call_args.args[3]]==[2]
    assert execute.call_args.args[5].dimensions==[2]


def test_unsupported_legacy_selection_is_not_silently_reinterpreted(setup):
    settings,result,summary,conn,cur,connect,evidence,execute,store,events,run=setup
    settings['pipeline.label_selection_mode']='coverage'
    assert run()['status']=='failed'
    evidence.assert_not_called();execute.assert_not_called()


@pytest.fixture
def ledger_db():
    import os
    from api.db.connection import connect_db
    from psycopg2.extras import RealDictCursor
    if os.getenv('PLEXINTEL_TEST_TEMP_DB')!='1':pytest.skip('Opt-in connection-private labeling SQL fixture')
    conn=connect_db()
    def query(statement,args=(),*,many=False):
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(statement,args)
            if cur.description:return cur.fetchall() if many else cur.fetchone()
    text=Path('api/db/migrations/005_semantic_dimension_labeling.sql').read_text()
    for match in re.finditer(r'CREATE TABLE IF NOT EXISTS public.embedding_label_(?:batches|requests) \([\s\S]*?\n\);',text):
        query(match[0].replace('public.','pg_temp.').replace('generation_id text NOT NULL,','generation_id text,feature_space_id text,'))
    conn.commit()
    try:yield SimpleNamespace(conn=conn,query=query)
    finally:conn.close()


def new_auto_ledger(db,*,cap=1.,prompt='same-prompt',max_attempts=3):
    batch_id=str(uuid4());pricing=Pricing()
    forecast=dict(automation_scope=auto.SCOPE,automation_prompts={'0':prompt})
    db.query('''INSERT INTO pg_temp.embedding_label_batches(batch_id,config_id,feature_space_id,model,dimensions,forecast,pricing)
        VALUES(%s,'config','generation','gemma4:31b-cloud','[0]',%s,%s)''',(batch_id,Json(forecast),Json(vars(pricing))))
    db.conn.commit()
    limits=dict(scope=auto.SCOPE,feature_space_id='generation',prompts={'0':prompt},max_attempts=max_attempts,
                limits=lambda conn:dict(budget_usd=cap))
    return UsageLedger(db.conn,batch_id,pricing,automation=limits)


def test_sql_budget_survives_new_uuid_pending_requests_and_ledger_restart(ledger_db):
    first=new_auto_ledger(ledger_db)
    first.start(0,'media',1,'fictional','system',1024)
    cost=first.total_cost();assert cost>0
    second=new_auto_ledger(ledger_db,cap=cost)  # New batch UUID must not reset spending.
    with pytest.raises(BudgetExceeded):second.start(0,'media',1,'fictional','system',1024)
    ledger_db.conn.rollback()
    assert ledger_db.query('SELECT COUNT(*) AS n FROM pg_temp.embedding_label_requests')['n']==1
    assert usage_report(ledger_db.conn)['automatic']['pending']==1


def test_sql_attempt_limits_survive_restarts_without_a_cumulative_request_cap(ledger_db):
    for attempt in range(1,4):
        ledger=new_auto_ledger(ledger_db)
        request=ledger.start(0,'media',1,'fictional','system',1024)
        assert ledger_db.query('SELECT attempt FROM pg_temp.embedding_label_requests WHERE request_id=%s',(request,))['attempt']==attempt
    restarted=new_auto_ledger(ledger_db)
    with pytest.raises(BudgetExceeded,match='per-prompt'):restarted.start(0,'media',1,'fictional','system',1024)
    ledger_db.conn.rollback()
    other_prompt=new_auto_ledger(ledger_db,prompt='new-prompt')
    other_prompt.start(0,'media',1,'fictional','system',1024)
    assert usage_report(ledger_db.conn)['automatic']['requests']==4


def test_sql_metered_success_cannot_release_automatic_reservation(ledger_db):
    ledger=new_auto_ledger(ledger_db);request=ledger.start(0,'media',1,'fictional','system',1024)
    reserved=ledger.total_cost()
    ledger.finish(request,dict(prompt_eval_count=1,eval_count=1),None)
    assert ledger.total_cost()>=reserved


def test_sql_more_than_one_hundred_requests_are_monitoring_only(ledger_db):
    from api.services.labeling_costs import cumulative_usage
    ledger=new_auto_ledger(ledger_db)
    ledger_db.query('''INSERT INTO pg_temp.embedding_label_requests
        (batch_id,dimension,side,attempt,estimated_input_tokens,reserved_input_tokens,reserved_output_tokens,estimated_cost_usd)
        SELECT %s,0,'media',1,100,100,100,.001 FROM generate_series(1,100)''',(ledger.batch_id,))
    ledger_db.conn.commit()
    next_batch=new_auto_ledger(ledger_db,prompt='different-evidence')
    request=next_batch.start(0,'media',1,'fictional','system',1024)
    totals=cumulative_usage(ledger_db.conn,auto.SCOPE)
    assert totals['requests']==101 and totals['pending']==101
    assert not totals['token_totals_are_complete'] and totals['missing_input_counts']==101
    next_batch.finish(request,dict(prompt_eval_count=100,eval_count=50),None)
    totals=cumulative_usage(ledger_db.conn,auto.SCOPE)
    assert totals['input_tokens']==100 and totals['output_tokens']==50
    assert totals['requests']==101 and totals['estimated_cost_usd']>=.1


def test_sql_real_policy_ignores_retired_setting_but_rechecks_finances_and_authorization(ledger_db,monkeypatch):
    from api.services import app_settings
    ledger_db.query('''CREATE TEMP TABLE app_settings(key text PRIMARY KEY,raw_value text,source text,
        updated_at timestamptz,updated_by text,description text)''')
    for key,value in [('pipeline.labeling_enabled','true'),('pipeline.labeling_cloud_authorized','true'),
            ('pipeline.labeling_budget_usd','1'),('pipeline.labeling_request_limit','not-a-valid-limit')]:
        ledger_db.query('INSERT INTO pg_temp.app_settings(key,raw_value,source) VALUES(%s,%s,\'fixture\')',(key,value))
    ledger_db.conn.commit()
    monkeypatch.setattr(app_settings,'SETTINGS_TABLE','pg_temp.app_settings')
    ledger=new_auto_ledger(ledger_db)
    ledger.automation['limits']=auto.limits
    assert auto.limits(ledger_db.conn)==dict(budget_usd=1.)
    ledger.start(0,'media',1,'fictional','system',1024)
    spent=ledger.total_cost()
    ledger_db.query("UPDATE pg_temp.app_settings SET raw_value=%s WHERE key='pipeline.labeling_budget_usd'",(str(spent),))
    ledger_db.conn.commit()
    with pytest.raises(BudgetExceeded,match='financial allowance'):ledger.start(0,'media',1,'fictional','system',1024)
    ledger_db.conn.rollback()
    ledger_db.query("UPDATE pg_temp.app_settings SET raw_value='1' WHERE key='pipeline.labeling_budget_usd'")
    ledger_db.query("UPDATE pg_temp.app_settings SET raw_value='false' WHERE key='pipeline.labeling_cloud_authorized'")
    ledger_db.conn.commit()
    with pytest.raises(BudgetExceeded,match='authorization'):ledger.start(0,'media',1,'fictional','system',1024)
    ledger_db.conn.rollback()
    assert usage_report(ledger_db.conn)['automatic']['requests']==1


def test_sql_revoked_authorization_never_reserves_or_requests(ledger_db):
    ledger=new_auto_ledger(ledger_db)
    ledger.automation['limits']=Mock(side_effect=BudgetExceeded('Authorization revoked'))
    with pytest.raises(BudgetExceeded):ledger.start(0,'media',1,'fictional','system',1024)
    assert ledger_db.query('SELECT COUNT(*) AS n FROM pg_temp.embedding_label_requests')['n']==0


def test_sql_exhausted_prompts_are_skipped_in_favor_of_other_dimensions(ledger_db):
    row=dict(dimension=0,prompt=dict(prompt_text='fictional'),side='media')
    for _ in range(3):
        ledger=new_auto_ledger(ledger_db,prompt=batch.prompt_hash(row['prompt']))
        ledger.start(0,'media',1,'fictional','system',1024)
    other=dict(row,dimension=1)
    assert auto._eligible_attempts(ledger_db.conn,[row,other],dict(feature_space_id='generation'),3)==[other]


@pytest.mark.parametrize('kind',['label','abstain','error','interrupt'])
def test_existing_batch_engine_with_mock_cloud_keeps_publication_independent(ledger_db,monkeypatch,kind):
    import gpt_utils as gpt
    from api.embedding_generation import model,backfill
    from api.services.labeling_costs import LabelingError
    context=dict(config_id='config',feature_space_id='generation')
    row=dict(dimension=1,side='media',completed=False,abstained=False,
             prompt=dict(prompt_text='fictional high low',positive_items=[{}]*6,negative_items=[{}]*4))
    existing=dict(dimension=0,side='media',completed=True,abstained=False,prompt=dict(prompt_text='existing'))
    args=batch.parser().parse_args([]);args.label_model='gemma4:31b-cloud';args.label_provider='ollama'
    args.max_output_tokens=1024;args.save_label=True;args.budget_usd=1.
    args.automation=dict(scope=auto.SCOPE,feature_space_id='generation',prompts={'1':batch.prompt_hash(row['prompt'])},
                         max_attempts=3,limits=lambda conn:dict(budget_usd=1.))
    prediction=dict(automation_scope=auto.SCOPE,automation_prompts=args.automation['prompts'],
                    selected_batch=dict(combined=dict(expected=dict(cost_usd=.001))))
    monkeypatch.setattr(batch,'current_context',lambda c:context)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    monkeypatch.setattr(batch,'record_assessment',Mock())
    monkeypatch.setattr(batch,'persist_result',Mock(return_value=(kind=='label','saved' if kind=='label' else 'abstained')))
    monkeypatch.setattr(batch,'workload_forecast',lambda *a:dict(all_remaining={}))
    monkeypatch.setattr(gpt,'resolve_label_backend',lambda *a:('ollama','gemma4:31b-cloud'))
    def provider(*a,**kw):
        if kind=='interrupt':raise KeyboardInterrupt()
        if kind=='error':raise LabelingError('HTTP_401','provider','Fictional provider failure',transient=False)
        kw['on_usage'](dict(prompt_eval_count=100,eval_count=50))
        return dict(response(),label=gpt.UNCLEAR_LABEL) if kind=='abstain' else response()
    cloud=Mock(side_effect=provider);monkeypatch.setattr(gpt,'_call_ollama_for_label_result',cloud)
    forbidden=Mock(side_effect=AssertionError('Labeling cannot fit/score/embed'))
    monkeypatch.setattr(model,'fit',forbidden);monkeypatch.setattr(model,'score',forbidden)
    monkeypatch.setattr(backfill,'run_media_text',forbidden)
    selected=batch.choose([existing,row],args);assert selected==[row]
    if kind=='interrupt':
        with pytest.raises(KeyboardInterrupt) as error:batch.execute(ledger_db.conn,Mock(context=context),[existing,row],selected,Pricing(),args,prediction)
        assert error.value.labeling_summary['usage']['requests']==1
    else:
        summary=batch.execute(ledger_db.conn,Mock(context=context),[existing,row],selected,Pricing(),args,prediction)
        assert summary['successes']==int(kind=='label') and summary['abstentions']==int(kind=='abstain')
        assert summary['failures']==int(kind=='error')
    cloud.assert_called_once();forbidden.assert_not_called()
    assert ledger_db.query('SELECT count(*) AS n FROM pg_temp.embedding_label_requests')['n']==1
    if kind=='interrupt':assert ledger_db.query('SELECT status FROM pg_temp.embedding_label_batches')['status']=='interrupted'
    assert existing['completed']  # The existing selection/label state was preserved.
