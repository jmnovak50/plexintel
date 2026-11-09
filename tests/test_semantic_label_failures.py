"""Fictional responses only; no cloud or private viewing evidence in tests."""
from contextlib import nullcontext
import json
from unittest.mock import Mock

import pytest
import requests

import gpt_utils as gpt
from api.services import dimension_label_batch as batch
from api.services.labeling_costs import LabelingError, Pricing, failure_diagnostic, forecast, usage_report
from tests.test_semantic_labeling import context_fixture, response, sql_db


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setattr(gpt,'_resolve_ollama_model_name',lambda model:model)
    monkeypatch.setattr(gpt,'label_ollama_endpoint',lambda:('https://example.invalid',{}))
    mock=Mock(status_code=200)
    post=Mock(return_value=mock);monkeypatch.setattr(gpt.requests,'post',post)
    def reply(value,**metadata):
        prompt=metadata.pop('_prompt','fictional HIGH LOW')
        raw=dict(model='gemma4:31b-cloud',done=True,done_reason='stop',response=value,
                 prompt_eval_count=1000,eval_count=250)
        raw.update(metadata);mock.json.return_value=raw
        return gpt._call_ollama_for_label_result(prompt,'gemma4:31b-cloud',strict_json=True,on_usage=lambda data:None)
    return reply,post,mock


@pytest.mark.parametrize('fenced',[False,True])
def test_valid_contract_accepts_one_json_markdown_envelope(cloud,fenced):
    reply,_,_=cloud;raw=json.dumps(response())
    result=reply('```json\n'+raw+'\n```' if fenced else raw)
    assert result['label']=='workplace rivalries' and result['validation_status']=='valid'
    assert result['response_diagnostics']['response_envelope']==('markdown_json_fence' if fenced else 'plain_json')


def test_legacy_aliases_and_lossless_numbers_keep_canonical_contract(cloud):
    reply,_,_=cloud;payload=response()
    payload['confidence']=payload.pop('label_confidence').upper()
    payload['label_type']=payload.pop('proposed_label_type')
    payload['coverage_high_count']=6.0
    result=reply(json.dumps(payload))
    assert result['label_confidence']=='high' and type(result['coverage_high_count']) is int
    assert set(result['response_diagnostics']['normalized_fields'])>={'label_confidence','proposed_label_type','coverage_high_count'}


@pytest.mark.parametrize('field,value',[('coverage_high_count','6'),('coverage_high_count',5.5),('coverage_high_count',True),
    ('coverage_high_percent',False),('coverage_high_percent',101),('coverage_high_total',-1),('evidence',{}),
    ('label_confidence','unsupported'),('label',[])])
def test_wrong_types_and_ranges_remain_errors(cloud,field,value):
    reply,_,_=cloud;payload=response();payload[field]=value
    with pytest.raises(LabelingError) as caught:reply(json.dumps(payload))
    detail=failure_diagnostic(caught.value)
    assert detail['code']=='INVALID_JSON_TYPES' and field in detail['details']['invalid_fields']


def test_missing_fields_are_not_filled_or_misreported_as_provider_errors(cloud):
    reply,_,_=cloud;payload=response();del payload['coverage_high_total']
    with pytest.raises(LabelingError) as caught:reply(json.dumps(payload))
    error=failure_diagnostic(caught.value)
    assert error['code']=='MISSING_JSON_FIELDS' and error['category']=='json_schema'
    assert error['details']['missing_fields']==['coverage_high_total']


@pytest.mark.parametrize('raw',['private viewing details','```json\n{"label":\n```','{} {}','[{}]'])
def test_invalid_json_diagnostics_never_contain_response_text(cloud,raw):
    reply,_,_=cloud
    with pytest.raises(LabelingError) as caught:reply(raw)
    diagnostic=failure_diagnostic(caught.value)
    assert raw not in json.dumps(diagnostic)
    assert diagnostic['code'] in ('INVALID_JSON_SYNTAX','INVALID_JSON_TYPES')


def test_complete_json_with_length_stop_is_still_truncation(cloud):
    reply,_,_=cloud
    with pytest.raises(LabelingError) as caught:reply(json.dumps(response()),done_reason='length',eval_count=1024)
    error=failure_diagnostic(caught.value)
    assert error['code']=='OUTPUT_TRUNCATED' and error['details']['output_token_limit']==1024


def test_cloud_self_correction_can_only_recover_consistent_abstention(cloud):
    reply,_,_=cloud;first=response();first.update(coverage_low_overlap_count=3,coverage_low_overlap_percent=75)
    second=response();second.update(label=gpt.UNCLEAR_LABEL,label_confidence='unclear',proposed_label_type='unclear',
        coverage_high_count=0,coverage_high_total=0,coverage_high_percent=0,coverage_low_overlap_count=0,coverage_low_total=0,coverage_low_overlap_percent=0)
    raw='```json\n'+json.dumps(first)+'\n```\nWait: use the required quality threshold.\n```json\n'+json.dumps(second)+'\n```'
    result=reply(raw,_prompt='HIGH examples in this prompt = 6; LOW examples in this prompt = 4.')
    assert result['label']==gpt.UNCLEAR_LABEL and result['coverage_low_overlap_percent']==75
    assert result['response_diagnostics']['usable_label_recovered'] is False
    checked=batch.validate_sample_counts(result,dict(positive_items=[{}]*6,negative_items=[{}]*4))
    assert not checked.get('sample_count_mismatch')


def test_multiple_answers_never_recover_positive_or_conflicting_labels(cloud):
    reply,_,_=cloud;first=response();second=response();second['label']='fictional alternative'
    raw='```json\n'+json.dumps(first)+'\n```\nAnother answer:\n```json\n'+json.dumps(second)+'\n```'
    with pytest.raises(LabelingError) as caught:reply(raw,_prompt='HIGH examples in this prompt = 6; LOW examples in this prompt = 4.')
    assert caught.value.code=='MULTIPLE_JSON_OBJECTS'
    # Two reports with matching totals cannot silently select differing counts,
    # even when the quality gate would turn both proposed labels into abstentions.
    first.update(coverage_low_overlap_count=3,coverage_low_overlap_percent=75)
    second.update(coverage_low_overlap_count=4,coverage_low_overlap_percent=100)
    raw='```json\n'+json.dumps(first)+'\n```\n```json\n'+json.dumps(second)+'\n```'
    with pytest.raises(LabelingError):reply(raw,_prompt='HIGH examples in this prompt = 6; LOW examples in this prompt = 4.')


def test_http_and_incomplete_errors_are_distinct(cloud):
    reply,_,mock=cloud
    with pytest.raises(LabelingError) as caught:reply(json.dumps(response()),done=False)
    assert caught.value.code=='INCOMPLETE_RESPONSE'
    mock.status_code=401
    with pytest.raises(LabelingError) as caught:reply('{}')
    assert caught.value.code=='HTTP_401' and caught.value.transient is False


def test_wrapping_preserves_structural_failure_and_avoids_retries(monkeypatch):
    error=LabelingError('MISSING_JSON_FIELDS','json_schema','Model response omitted required label fields.',details={'missing_fields':['evidence']})
    cloud=Mock(side_effect=error);monkeypatch.setattr(gpt,'_call_ollama_for_label_result',cloud)
    with pytest.raises(LabelingError) as caught:
        gpt.call_llm_for_label_result('fictional',provider='ollama',model='gemma4:31b-cloud',max_output_tokens=1024)
    assert caught.value is error and cloud.call_count==1
    private=requests.ConnectionError('https://private.invalid/?api_key=never-log-this')
    assert 'never-log-this' not in json.dumps(failure_diagnostic(private))


def test_setup_limit_override_and_conservative_forecast_agree(monkeypatch,cloud):
    monkeypatch.setattr(gpt,'get_setting_value',lambda key,**kw:2048 if key=='labeling.max_output_tokens' else kw.get('default'))
    reply,post,_=cloud;reply(json.dumps(response()))
    assert post.call_args.kwargs['json']['options']['num_predict']==2048
    assert gpt.label_output_limit(1536)==1536
    with pytest.raises(ValueError):gpt.label_output_limit(0)
    rows=[dict(side='media',prompt=dict(prompt_text='fictional HIGH LOW'))]
    low=forecast(rows,Pricing(),system='fictional',output_limit=420)
    high=forecast(rows,Pricing(),system='fictional',output_limit=2048)
    assert high['combined']['high']['output_tokens']==3*2048
    assert high['combined']['high']['cost_usd']>low['combined']['high']['cost_usd']


def test_sql_fail_fast_retains_metering_and_leaves_all_failed_dimensions_retryable(sql_db,monkeypatch):
    conn,_=sql_db;_,_,context=context_fixture()
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    args=batch.parser().parse_args(['--label','--save-label','--label-model','gemma4:31b-cloud'])
    rows=[dict(dimension=i,side='media',completed=False,abstained=False,prompt=dict(prompt_text='fictional HIGH LOW')) for i in range(25)]
    def fail(prompt,model,**kw):
        kw['on_usage'](dict(prompt_eval_count=1000,eval_count=200))
        raise LabelingError('MISSING_JSON_FIELDS','json_schema','Model response omitted required label fields.',details={'missing_fields':['evidence']})
    cloud=Mock(side_effect=fail);monkeypatch.setattr(gpt,'_call_ollama_for_label_result',cloud)
    prediction=batch.workload_forecast(rows,rows,Pricing(),args,{})
    summary=batch.execute(conn,Mock(context=context),rows,rows,Pricing(),args,prediction)
    assert summary['failures']==3 and cloud.call_count==3 and summary['unprocessed_dimensions']==list(range(3,25))
    with conn.cursor() as cur:
        cur.execute('SELECT status FROM embedding_label_batches');assert cur.fetchone()[0]=='systemic_failure_stopped'
        cur.execute('SELECT COUNT(*) FROM embedding_labels');assert cur.fetchone()[0]==0
        cur.execute('SELECT result FROM embedding_dimension_assessments')
        assert all(r[0]['error_diagnostics']['details']['missing_fields']==['evidence'] for r in cur.fetchall())
    usage=usage_report(conn,summary['batch_id'])
    assert usage['combined']['output_tokens']==600 and usage['failure_codes']=={'MISSING_JSON_FIELDS':3}
    assert len(batch.choose(rows,args))==25


def test_sql_fail_fast_resets_after_valid_response(sql_db,monkeypatch):
    conn,_=sql_db;_,_,context=context_fixture()
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    args=batch.parser().parse_args(['--label','--save-label','--label-model','gemma4:31b-cloud'])
    rows=[dict(dimension=i,side='media',completed=False,abstained=False,prompt=dict(prompt_text='fictional HIGH LOW')) for i in range(5)]
    calls=[]
    def sometimes(prompt,model,**kw):
        calls.append(True);kw['on_usage'](dict(prompt_eval_count=1000,eval_count=200))
        if len(calls)!=3:raise LabelingError('INVALID_JSON_SYNTAX','json_syntax','Model response is not one complete JSON value.')
        return gpt._extract_label_result_from_response(json.dumps(response()))
    monkeypatch.setattr(gpt,'_call_ollama_for_label_result',sometimes)
    prediction=batch.workload_forecast(rows,rows,Pricing(),args,{})
    summary=batch.execute(conn,Mock(context=context),rows,rows,Pricing(),args,prediction)
    assert summary['successes']==1 and summary['failures']==4 and len(calls)==5
    with conn.cursor() as cur:
        cur.execute('SELECT status FROM embedding_label_batches');assert cur.fetchone()[0]=='completed_with_errors'


def test_sql_sample_count_failure_is_classified_after_metering(sql_db,monkeypatch):
    conn,_=sql_db;_,_,context=context_fixture()
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    args=batch.parser().parse_args(['--label','--save-label','--label-model','gemma4:31b-cloud','--fail-fast-threshold','1'])
    rows=[dict(dimension=0,side='media',completed=False,abstained=False,prompt=dict(prompt_text='fictional HIGH LOW',positive_items=[{}]*6,negative_items=[{}]*4))]
    def wrong_counts(prompt,model,**kw):
        kw['on_usage'](dict(prompt_eval_count=1000,eval_count=200))
        payload=response();payload.update(coverage_high_total=8,coverage_high_percent=75)
        return gpt._extract_label_result_from_response(json.dumps(payload))
    monkeypatch.setattr(gpt,'_call_ollama_for_label_result',wrong_counts)
    prediction=batch.workload_forecast(rows,rows,Pricing(),args,{})
    summary=batch.execute(conn,Mock(context=context),rows,rows,Pricing(),args,prediction)
    assert summary['failures']==1 and summary['abstentions']==0
    usage=usage_report(conn,summary['batch_id'])
    assert usage['failure_codes']=={'LABEL_COVERAGE_MISMATCH':1} and usage['combined']['output_tokens']==200
    assert len(batch.choose(rows,args))==1
