"""Read model parity for CLI/daily label batches, including unsaved assessments."""
from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
import json
from unittest.mock import Mock
import pytest
from psycopg2.extras import RealDictCursor,Json
from api.services import dimension_explorer as explorer
from tests.test_pipeline_labeling import ledger_db


def test_no_ledger_or_stages_is_explicitly_empty():
    cur=Mock();cur.fetchone.return_value=dict(batches=None,requests=None,stages=None)
    assert explorer.recent_labeling_runs(cur,dict(config_id='fixture'))==[]
    assert cur.execute.call_count==1


def test_stage_only_outcomes_are_not_fabricated_as_batch_counts():
    now=datetime.now(timezone.utc);cur=Mock()
    cur.fetchone.return_value=dict(batches=None,requests=None,stages=True)
    cur.fetchall.return_value=[dict(run_id=9,stage_key='semantic_labels',status='skipped',exit_code=0,
        started_at=now,completed_at=now,stdout_tail=json.dumps(dict(generation_run_id='unmatched')))]
    rows=explorer.recent_labeling_runs(cur,dict(config_id='fixture'))
    assert rows[0]['run_id']==9 and rows[0]['batch_id'] is None and rows[0]['status']=='skipped'
    assert 'assessed' not in rows[0] and 'saved' not in rows[0]


def test_sql_recent_batches_reconcile_requests_unsaved_results_and_exact_stage_link(ledger_db):
    conn=ledger_db.conn;q=ledger_db.query
    q('''CREATE TEMP TABLE embedding_dimension_assessments(assessment_id bigint,config_id text,
        dimension integer,source text,result jsonb,saved boolean,outcome text);
        CREATE TEMP TABLE pipeline_run_stages(run_id integer,stage_key text,status text,exit_code integer,
        started_at timestamptz,completed_at timestamptz,stdout_tail text)''')
    now=datetime(2026,11,20,21,tzinfo=timezone.utc)
    for bid,cid,space,status,start,forecast,summary in [
        ('cli','fixture','space','completed',now,{},dict(assessed=2,successes=1,abstentions=1,failures=0,reviews=0)),
        ('daily','fixture','space','running',now-timedelta(minutes=1),dict(automation_run_id='exact-workload'),{}),
        ('incompatible','fixture','other-space','completed',now+timedelta(minutes=1),{},{}),
        ('other-config','other','space','completed',now+timedelta(minutes=1),{},{})]:
        q('''INSERT INTO pg_temp.embedding_label_batches(batch_id,config_id,feature_space_id,model,dimensions,forecast,pricing,status,created_at,summary)
            VALUES(%s,%s,%s,'fictional','[1,2]',%s,'{}',%s,%s,%s)''',(bid,cid,space,Json(forecast),status,start,Json(summary)))
    for aid,bid,dim,saved,outcome,source in [(1,'cli',1,True,'inserted_missing_label','manual-batch'),
            (2,'cli',2,False,'abstained','manual-batch'),(3,'cli',1,True,'native_media_provenance_reconciled','provenance-reconciliation'),
            (4,'daily',3,False,'response_error','daily-pipeline')]:
        q('INSERT INTO pg_temp.embedding_dimension_assessments VALUES(%s,\'fixture\',%s,%s,%s,%s,%s)',
            (aid,dim,source,Json(dict(batch_id=bid,processing_error=outcome=='response_error')),saved,outcome))
    for bid in ('cli','daily'):
        q('''INSERT INTO pg_temp.embedding_label_requests(batch_id,dimension,side,attempt,
            estimated_input_tokens,reserved_input_tokens,reserved_output_tokens,estimated_cost_usd,input_tokens,output_tokens)
            VALUES(%s,1,'media',1,100,120,100,.001,100,20)''',(bid,))
    for rid,key,workload in [(1,'semantic_labels','exact-workload'),(2,'semantic_labels','not-the-workload'),(3,'batch_label',None)]:
        q('INSERT INTO pg_temp.pipeline_run_stages VALUES(%s,%s,\'skipped\',0,%s,%s,%s)',
            (rid,key,now-timedelta(minutes=2),now,json.dumps(dict(generation_run_id=workload))))
    conn.commit()
    with conn.cursor(cursor_factory=RealDictCursor) as real:
        class Cursor:
            def execute(self,sql,args=()):real.execute(sql.replace("to_regclass('public.","to_regclass('pg_temp."),args)
            def fetchone(self):return real.fetchone()
            def fetchall(self):return real.fetchall()
        rows=explorer.recent_labeling_runs(Cursor(),dict(config_id='fixture',feature_space_id='space'))
    cli=next(r for r in rows if r['batch_id']=='cli');daily=next(r for r in rows if r['batch_id']=='daily')
    assert cli['source']=='cli' and cli['assessed']==2 and cli['saved']==1 and cli['abstentions']==1
    assert cli['requests']==1 and cli['input_tokens']==100 and cli['estimated_cost_usd']==.001
    assert daily['source']=='daily' and daily['run_id']==1 and daily['status']=='running'
    assert daily['assessed']==1 and daily['failures']==1 and daily['saved']==0
    assert len([r for r in rows if r['run_id']==1])==1
    assert not any(r['batch_id'] in ('incompatible','other-config') for r in rows)
    assert {r['run_id'] for r in rows if r['batch_id'] is None}=={2,3}
