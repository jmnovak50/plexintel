"""Fictional CSV fixtures only; PostgreSQL uses the isolated labeling fixture."""
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from psycopg2.extras import Json

import gpt_utils as gpt
from api.services import dimension_label_export as export
from tests.test_semantic_labeling import sql_db, context_fixture, response


@pytest.mark.parametrize('value', ['=1+1', '+cmd', '-1+2', '@SUM(A1)', ' \t=cmd', '\ufeff=cmd',
    '\n=cmd', '\tplain', '\rplain', '＝1+1', '  \ufeff @cmd'])
def test_excel_formula_text_is_escaped(value):
    assert export.excel_cell(value)=="'"+value


def test_excel_round_trip_unicode_quotes_multiline_private_permissions_and_atomicity(tmp_path):
    target=tmp_path/'results.csv';target.write_text('old');target.chmod(0o644)
    text='HIGH, "fictional" stories\nRésumé, 東京'
    export.write_csv(target,[dict(dimension=0,label='=1+1',label_explanation=text,input_tokens=0)])
    assert target.read_bytes().startswith(b'\xef\xbb\xbf')
    assert b'\r\n' in target.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o600
    with target.open(encoding='utf-8-sig',newline='') as handle:
        row=next(csv.DictReader(handle))
    assert row['label']=="'=1+1" and row['label_explanation']==text and row['input_tokens']=='0'
    assert 'prompt_text' not in row and 'summary' not in row
    original=target.read_bytes()
    with pytest.raises(ValueError):export.write_csv(target,[dict(unexpected_column='bad')])
    assert target.read_bytes()==original
    assert not list(tmp_path.glob('*.tmp'))
    link=tmp_path/'linked.csv';link.symlink_to(target)
    with pytest.raises(ValueError,match='symlink'):export.write_csv(link,[])
    assert target.read_bytes()==original


def records():
    _,_,context=context_fixture()
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    first,second=str(uuid4()),str(uuid4())
    batches={}
    for bid,start,dimensions in ((first,now,[0]),(second,now+timedelta(minutes=5),[0,1,2,3,768])):
        batches[bid]=dict(batch_id=bid,config_id=context['config_id'],generation_id=context['generation_id'],
            model='gemma4:31b-cloud',dimensions=dimensions,status='completed_with_errors',created_at=start,completed_at=start+timedelta(minutes=1))
    saved=dict(label='workplace rivalries',label_type='semantic_candidate',display_label='workplace rivalries',explainable=True,needs_review=False)
    good=dict(response(),validation_status='valid',provenance=context)
    bad=dict(label=gpt.UNCLEAR_LABEL,validation_status='invalid',processing_error=True,error_code='OUTPUT_TRUNCATED',
        error_diagnostics=dict(category='truncation',message='Authorization: Bearer secret-error'),provenance=context,
        error='secret-error')
    abstain=dict(response(),label=gpt.UNCLEAR_LABEL,label_confidence='unclear',validation_status='invalid',provenance=context)
    metadata=dict(minimum_label_coverage_percent=70,maximum_low_overlap_percent=40,valid_positive_count=6,valid_negative_count=4)
    assessments=[]
    for aid,bid,dimension,result,outcome,after in ((1,first,0,good,'inserted_missing_label',saved),
            (2,second,0,bad,'response_error',None),(3,second,768,abstain,'abstained',None)):
        assessments.append(dict(assessment_id=aid,dimension=dimension,source='manual-batch',provider='ollama',
            model='gemma4:31b-cloud',result=result,saved=bool(after),outcome=outcome,before_state=None,after_state=after,
            prompt_metadata=metadata,created_at=batches[bid]['created_at']+timedelta(seconds=45)))
    requests=[]
    for rid,bid,dimension,status,error,input_count,output_count,attempt in (
        (1,first,0,'succeeded',None,100,0,1),(2,second,0,'failed','INVALID_JSON_SYNTAX',100,10,1),
        (3,second,0,'failed','OUTPUT_TRUNCATED',100,10,2),(4,second,768,'succeeded',None,100,10,1),
        (5,second,2,'pending',None,None,None,1)):
        requests.append(dict(request_id=rid,batch_id=bid,dimension=dimension,side='media' if dimension<768 else 'user',
            attempt=attempt,status=status,error_code=error,input_tokens=input_count,output_tokens=output_count,cached_input_tokens=None,
            estimated_cost_usd=Decimal('.001'),created_at=batches[bid]['created_at']+timedelta(seconds=attempt),
            completed_at=batches[bid]['created_at']+timedelta(seconds=30) if status!='pending' else None))
    labels={0:dict(saved,dimension=0,**{k:context[k] for k in ('config_id','generation_id','contract_hash','encoder_digest')}),
            1:dict(saved,dimension=1,label='feature films',label_type='hard_structural',display_label=None,explainable=False)}
    return context,labels,assessments,batches,requests,first,second


def test_snapshot_uses_latest_result_and_keeps_current_label_separate():
    context,labels,assessments,batches,requests,first,second=records()
    events,groups=export.collect_events(labels,assessments,batches,requests)
    assert [e['dimension'] for e in events]==[0,1,2,768]
    event=events[0];assert event['assessment_id']==2 and event['batch_id']==second
    row=export.format_row(event,labels[0],batches[second],groups[second,0],{},context)
    assert row['processing_outcome']=='response_error' and row['explanation_eligible'] is False
    assert row['final_saved_label']=='workplace rivalries' and row['final_explanation_eligible'] is True
    assert (row['input_tokens'],row['output_tokens'],row['failed_attempt_count'])==(200,20,2)
    assert row['error_category']=='truncation' and row['token_totals_are_complete'] is True
    assert row['estimated_cost_usd']==Decimal('.002')
    assert 'secret-error' not in str(row)
    pending=export.format_row(events[2],None,batches[second],groups[second,2],{},context)
    assert pending['input_tokens'] is None and pending['output_tokens'] is None
    assert pending['token_totals_are_complete'] is False and pending['cost_basis']=='includes reserved estimates'
    pending_with_label=export.format_row(events[2],labels[0],batches[second],groups[second,2],{},context)
    assert pending_with_label['label']=='' and pending_with_label['explainable'] is None
    assert not pending_with_label['explanation_eligible'] and pending_with_label['final_explanation_eligible']


def test_batch_export_preserves_its_outcomes_and_unprocessed_dimensions():
    context,labels,assessments,batches,requests,first,second=records()
    events,groups=export.collect_events(labels,assessments,batches,requests,first)
    assert len(events)==1 and events[0]['assessment_id']==1
    row=export.format_row(events[0],labels[0],batches[first],groups[first,0],{},context,historical=True)
    assert row['processing_outcome']=='inserted_missing_label' and row['final_state_scope']=='assessment_time'
    assert row['output_tokens']==0 and row['attempt_count']==1
    events,_=export.collect_events(labels,assessments,batches,requests,second)
    assert [e['dimension'] for e in events]==[0,1,2,3,768]
    assert events[-1]['outcome']=='abstained' and events[1]['outcome']=='not_processed'
    with pytest.raises(ValueError,match='not found'):export.collect_events(labels,assessments,batches,requests,str(uuid4()))


def test_ambiguous_legacy_links_remain_unknown_but_explicit_uuid_is_used():
    _,labels,assessments,batches,requests,first,second=records()
    batches[second].update(created_at=batches[first]['created_at'],completed_at=batches[first]['completed_at'])
    requests[1]['created_at']=requests[0]['created_at']
    requests[1]['completed_at']=requests[0]['completed_at']
    events,_=export.collect_events(labels,assessments[:1],batches,requests[:2])
    assessment=next(e for e in events if e.get('assessment_id')==1)
    assert assessment['batch_id'] is None and assessment['batch_link_source']=='unresolved_batch_link'
    assessments[0]['result']['batch_id']=first
    events,_=export.collect_events(labels,assessments[:1],batches,requests[:2],first)
    assert events[0]['assessment_id']==1 and events[0]['batch_link_source']=='explicit'


@pytest.mark.parametrize('flag',['--export-csv','--export_csv'])
def test_cli_export_bypasses_cloud_forecast_locks_and_model_configuration(monkeypatch,tmp_path,flag):
    from api.services import dimension_label_batch as batch
    conn=Mock();monkeypatch.setattr(batch,'connect_db',lambda:conn)
    exporter=Mock(return_value=dict(rows=0,cloud_requests_started=0));monkeypatch.setattr(export,'export_csv',exporter)
    for module,name in ((batch,'Evidence'),(batch,'batch_lock'),(batch,'candidates'),(batch,'execute'),
                        (gpt,'resolve_label_backend'),(gpt,'call_llm_for_label_result')):
        monkeypatch.setattr(module,name,Mock(side_effect=AssertionError('Export must not invoke '+name)))
    target=tmp_path/'results.csv'
    batch.main([flag,str(target)])
    conn.set_session.assert_called_once_with(readonly=True,isolation_level='REPEATABLE READ')
    conn.commit.assert_not_called()
    exporter.assert_called_once_with(conn,str(target),batch_id=None,dim_type='all',dimensions=None)


@pytest.mark.parametrize('flags',[['--label'],['--save-label'],['--regenerate'],['--usage'],
    ['--batch-id','not-a-uuid'],['--batch-id',''],['--export-csv','']])
def test_export_rejects_mutating_or_invalid_flags_before_connecting(monkeypatch,flags):
    from api.services import dimension_label_batch as batch
    connect=Mock();monkeypatch.setattr(batch,'connect_db',connect)
    with pytest.raises(SystemExit):batch.main(['--export-csv','fictional.csv']+flags)
    connect.assert_not_called()


def test_sql_read_only_export_provenance_history_failures_and_token_totals(sql_db,monkeypatch,tmp_path):
    conn,_=sql_db;context,labels,assessments,batches,requests,first,second=records()
    monkeypatch.setattr(export,'current_context',lambda conn:context)
    with conn.cursor() as cur:
        for bid,b in batches.items():
            cur.execute('''INSERT INTO embedding_label_batches(batch_id,config_id,generation_id,model,dimensions,forecast,pricing,status,created_at,completed_at)
                VALUES(%s,%s,%s,%s,%s,'{}','{}',%s,%s,%s)''',
                (bid,context['config_id'],context['generation_id'],b['model'],Json(b['dimensions']),b['status'],b['created_at'],b['completed_at']))
        for r in requests:
            cur.execute('''INSERT INTO embedding_label_requests(batch_id,dimension,side,attempt,status,input_tokens,output_tokens,
                estimated_input_tokens,reserved_input_tokens,reserved_output_tokens,estimated_cost_usd,error_code,created_at,completed_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,100,100,100,%s,%s,%s,%s)''',
                tuple(r[k] for k in ('batch_id','dimension','side','attempt','status','input_tokens','output_tokens','estimated_cost_usd','error_code','created_at','completed_at')))
        for dimension,l in labels.items():
            cur.execute('''INSERT INTO embedding_labels(dimension,label,display_label,label_type,explainable,needs_review,config_id,generation_id,contract_hash,encoder_digest)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (dimension,l['label'],l['display_label'],l['label_type'],l['explainable'],False,
                 context['config_id'],context['generation_id'],context['contract_hash'],context['encoder_digest']))
        for a in assessments:
            prompt=dict(a['prompt_metadata'],prompt_text='PRIVATE_RAW_PROMPT',positive_items=['PRIVATE_EXAMPLE'],provenance=context)
            cur.execute('''INSERT INTO embedding_dimension_assessments(dimension,config_id,source,provider,model,prompt,result,saved,outcome,before_state,after_state,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (a['dimension'],context['config_id'],a['source'],a['provider'],a['model'],Json(prompt),Json(a['result']),a['saved'],a['outcome'],Json(a['before_state']),Json(a['after_state']),a['created_at']))
        cur.execute("INSERT INTO embedding_dimension_assessments(dimension,config_id,source,model,prompt,result,saved,outcome) VALUES(99,%s,'manual-batch','fictional','{}',%s,false,'retired')",
                    (context['config_id'],Json(dict(provenance=dict(context,generation_id='retired')))))
    conn.commit()
    tables=('embedding_labels','embedding_dimension_assessments','embedding_label_batches','embedding_label_requests')
    def snapshot():
        with conn.cursor() as cur:
            values=[]
            for table in tables:
                cur.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text');values.append(cur.fetchall())
            return values
    original=snapshot();conn.commit()
    conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
    try:
        target=tmp_path/'snapshot.csv';report=export.export_csv(conn,target)
        assert report['rows']==4 and report['cloud_requests_started']==0
        def read(path):
            with path.open(encoding='utf-8-sig',newline='') as handle:return list(csv.DictReader(handle))
        rows=read(target);assert [int(r['dimension']) for r in rows]==[0,1,2,768]
        assert rows[0]['batch_id']==second and rows[0]['batch_link_source']=='legacy_time_window'
        assert rows[0]['label']==gpt.UNCLEAR_LABEL and rows[0]['final_saved_label']=='workplace rivalries'
        assert rows[0]['input_tokens']=='200' and rows[0]['error_category']=='truncation'
        assert 'PRIVATE_RAW_PROMPT' not in target.read_text() and 'PRIVATE_EXAMPLE' not in target.read_text()
        assert 'secret-error' not in target.read_text()
        export.export_csv(conn,tmp_path/'first.csv',batch_id=first)
        first_rows=read(tmp_path/'first.csv');assert len(first_rows)==1 and first_rows[0]['processing_outcome']=='inserted_missing_label'
        export.export_csv(conn,tmp_path/'second.csv',batch_id=second)
        second_rows=read(tmp_path/'second.csv');assert len(second_rows)==5
        assert sum(Decimal(r['estimated_cost_usd']) for r in second_rows if r['estimated_cost_usd'])==Decimal('.004')
        export.export_csv(conn,tmp_path/'user.csv',dim_type='user')
        assert [r['dimension'] for r in read(tmp_path/'user.csv')]==['768']
        assert snapshot()==original
    finally:
        conn.rollback();conn.set_session(readonly=False,isolation_level='READ COMMITTED')


def test_export_function_refuses_a_writable_transaction():
    conn=Mock();conn.cursor.return_value.__enter__=Mock(return_value=Mock(fetchone=lambda:('off',)))
    conn.cursor.return_value.__exit__=Mock(return_value=False)
    with pytest.raises(ValueError,match='read-only'):export.export_csv(conn,'unused.csv')
