"""Restored labeling: fictional evidence and mocked cloud responses only."""
import copy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import Json
import pytest

import gpt_utils as gpt
from api.embedding_generation.contracts import fingerprint
from api.services.dimension_labeling import Evidence, checked_vectors, validate_context
from api.services.dimension_label_batch import choose, parser, persist_result, workload_forecast, validate_sample_counts
from api.services.labeling_costs import (Pricing, UsageLedger, BudgetExceeded, LabelingError, failure_diagnostic,
                                       forecast, token_usage, usage_report, pricing_for_model)


def context_fixture():
    contract = dict(ordering='media_text,user',encoder=dict(name='embeddinggemma-2:latest',digest='a'*64),
                    media_serializer='fictional/1',profile='fictional-mean/1')
    from api.predictive.features import SUPERVISION_POLICY
    from api.predictive.recovery import IDENTITY_POLICY
    state=dict(feature_space_id=fingerprint(contract),contract=contract)
    config=dict(architecture='public-text-predictor/1.0',contract=contract,
        config_id='fictional-config',feature_space_id=state['feature_space_id'],contract_hash=fingerprint(contract),
        identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
        encoder_digest='a'*64,model_sha256='b'*64,embedding_model='embeddinggemma-2',ordering='media_text,user',
        media_dimensions=768,user_dimensions=768,feature_groups=[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)],
        feature_names=[f'{side}_{i}' for side in ('media_text','user') for i in range(768)])
    return config,state,validate_context(config)


def response():
    return dict(label='workplace rivalries',label_confidence='high',proposed_label_type='semantic',
        coverage_high_count=6,coverage_high_total=6,coverage_high_percent=100,
        coverage_low_overlap_count=0,coverage_low_total=4,coverage_low_overlap_percent=0,
        explanation='Repeated workplace rivals separate the fictional HIGH examples.',
        evidence=['HIGH fictional titles show work rivals.','LOW fictional titles concern sailing.','Repeated career competition separates them.'])


@pytest.mark.parametrize('label',[
    'episodic drama series', 'standalone movies and series', 'episodic sitcoms',
    'episodic television series', 'serialized crime series', 'limited television series',
    'runtime over 45 minutes', 'episodes under 42 minutes', 'runtime below 90 minutes',
    'movies about 90 minutes',
    'movies released 1990-1999', 'feature films',
])
def test_format_and_release_labels_are_never_semantic_explanations(label):
    import batch_label_embeddings as labels
    result=gpt.validate_label_result(dict(response(),label=label))
    governance=labels.classify_validated_label_governance(result)
    assert governance['label_type'] in {'hard_structural','metadata'}
    assert not labels.is_saved_label_usable_for_explanation(governance)


@pytest.mark.parametrize('label',[
    'workplace rivalries', 'character-driven comedy and drama', 'historical and family dramas',
    'drama about estranged siblings', 'series about police corruption',
    'an episode exploring parental sacrifice', 'films centered on family reconciliation',
])
def test_narrative_content_is_not_rejected_for_format_or_genre_words(label):
    import batch_label_embeddings as labels
    governance=labels.classify_validated_label_governance(gpt.validate_label_result(dict(response(),label=label)))
    assert governance['label_type']=='semantic_candidate'
    assert labels.is_saved_label_usable_for_explanation(governance)


@pytest.mark.parametrize('changes',[
    dict(coverage_high_percent=66), dict(coverage_low_overlap_percent=45),
    dict(coverage_high_percent=None), dict(coverage_low_overlap_percent=None),
    dict(label_confidence='unclear'),
])
def test_incomplete_or_downgraded_evidence_cannot_explain(changes):
    import batch_label_embeddings as labels
    result=gpt.validate_label_result(dict(response(),**changes))
    before=copy.deepcopy(result)
    assert not labels.classify_validated_label_governance(result)['explainable']
    assert result==before  # Classification never rewrites confidence or evidence.


def test_governance_uses_applicable_thresholds_and_complete_validation_status():
    import batch_label_embeddings as labels
    result=gpt.validate_label_result(dict(response(),coverage_high_percent=66),minimum_label_coverage_percent=60)
    assert labels.classify_validated_label_governance(result,minimum_label_coverage_percent=60)['explainable']
    assert not labels.classify_validated_label_governance(result)['explainable']
    for status in ('downgraded','needs_review','invalid'):
        assert not labels.classify_validated_label_governance(dict(result,validation_status=status),minimum_label_coverage_percent=60)['explainable']
    assert labels.classify_validated_label_governance(gpt.validate_label_result(dict(response(),label_confidence='low')))['explainable']


def test_current_context_rejects_wrong_layout_generation_encoder_and_classifier():
    config,state,context = context_fixture()
    assert context['feature_space_id']==fingerprint(config['contract'])
    for key,value in [('feature_space_id','other'),('encoder_digest','c'*64),('model_sha256','wrong'),('ordering','media_text,media_poster,user')]:
        bad=copy.deepcopy(config);bad[key]=value
        with pytest.raises(ValueError):validate_context(bad,state,state['feature_space_id'])
    bad=copy.deepcopy(config);bad['feature_names'][768]='media_text_768'
    with pytest.raises(ValueError):validate_context(bad,state,state['feature_space_id'])


@pytest.mark.parametrize('fault',['width','nan','hash','generation','encoder'])
def test_vector_lineage_is_checked_before_sample_selection(fault):
    _,_,context = context_fixture()
    vector=np.arange(768,dtype='<f4')
    record=dict(feature_space_id=context['feature_space_id'],vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest(),
                encoder_digest=context['encoder_digest'])
    if fault=='width':vector=vector[:-1]
    if fault=='nan':vector[0]=np.nan
    if fault=='hash':record['vector_sha256']='bad'
    if fault=='generation':record['feature_space_id']='other'
    if fault=='encoder':record['encoder_digest']='other'
    with pytest.raises(ValueError):checked_vectors([dict(id='fictional',embedding=vector,record=record)],context)


def test_checked_vectors_retain_unnormalized_user_coordinate_values():
    _,_,context=context_fixture();values=np.full(768,.01,dtype='<f4')
    record=dict(feature_space_id=context['feature_space_id'],vector_sha256=hashlib.sha256(values.tobytes()).hexdigest(),encoder_digest=context['encoder_digest'])
    ids,matrix=checked_vectors([dict(id='fictional',embedding=json.dumps(values.tolist()),record=record)],context)
    assert ids==['fictional'] and np.array_equal(matrix[0],values)


@pytest.mark.parametrize('dimension,side,index',[(0,'media',0),(767,'media',767),(768,'user',0),(1535,'user',767)])
def test_high_low_coordinate_mapping_and_disjoint_populations(dimension,side,index):
    evidence=Evidence.__new__(Evidence)
    ids=[f'fictional-{i}' for i in range(31)]
    matrix=np.zeros((31,768),dtype='<f4');matrix[:,index]=np.arange(31)
    evidence.vectors={side:(ids,matrix)}
    high=evidence.ranked(side,index,10);low=evidence.ranked(side,index,10,True)
    assert high==ids[::-1][:10] and low==ids[:10]
    assert not set(high)&set(low)
    matrix[:,index]=0;matrix[30,index]=1
    assert not set(evidence.ranked(side,index,10))&set(evidence.ranked(side,index,10,True))


def test_forecast_uses_full_prompts_and_separate_media_user_counts():
    prompts=[dict(side='media',prompt=dict(prompt_text='HIGH fictional media LOW contrast')),
             dict(side='user',prompt=dict(prompt_text='HIGH fictional user engagement LOW contrast '*20))]
    f=forecast(prompts,Pricing(),system='full fictional system',output_limit=420,attempts=3)
    assert f['user']['expected']['input_tokens']>f['media']['expected']['input_tokens']
    assert f['combined']['high']['cloud_requests']==6
    assert f['combined']['high']['cost_usd']>=f['combined']['expected']['cost_usd']
    assert f['cached_input_assumed']==0
    calibrated=forecast(prompts,Pricing(),system='full fictional system',observations={'media':dict(output_mean=25,input_ratio=.8,retry_factor=1)})
    assert calibrated['media']['expected']['output_tokens']==25


def test_cached_user_preprocessing_preserves_exact_original_prompts_and_gates():
    evidence=Evidence.__new__(Evidence)
    usernames=['fictional-'+str(i) for i in range(10)]
    rows=[]
    for user in usernames:
        for i in range(20):
            rows.append(dict(username=user,rating_key=i,title='Fictional story '+str(i),media_type='movie',year=2000+i,
                summary='A fictional workplace conflict.',duration=6_000_000,engagement_ratio=1-i/100,training_label=1))
    evidence.user=gpt._ensure_metadata_columns(pd.DataFrame(rows))
    evidence.aliases={u:'Viewer '+str(i) for i,u in enumerate(usernames)}
    evidence.fetch_count=4;evidence.prompt_cache={}
    matrix=np.repeat(np.arange(10,dtype='<f4')[:,None],768,axis=1)
    evidence.vectors={'user':(usernames,matrix)}
    evidence.prepare_user_cache()
    side,high,low=evidence.samples(768,4)
    original=gpt.build_dimension_prompt(768,high,low,dimension_mode=side)
    optimized=evidence.prompt(768)
    for key in ('prompt_text','summary','valid_positive_count','valid_negative_count','flagged_item_count','skipped_reason'):
        assert optimized[key]==original[key],key
    pd.testing.assert_frame_equal(optimized['positive_items'],original['positive_items'])
    pd.testing.assert_frame_equal(optimized['negative_items'],original['negative_items'])


def test_pricing_cache_discount_and_missing_metering_are_explicit():
    pricing=Pricing()
    assert pricing.cost(1_000_000,1_000_000)==.54
    assert pricing.cost(1_000_000,1_000_000,1_000_000)==.45
    assert token_usage({})==dict(input_tokens=None,cached_input_tokens=None,output_tokens=None)
    assert token_usage(dict(prompt_eval_count=10,prompt_eval_cached_count=20,eval_count=3))['cached_input_tokens'] is None
    for bad in (-1,float('inf'),float('nan')):
        with pytest.raises(ValueError):Pricing(bad)


def test_model_is_resolved_from_current_setup_with_explicit_override(monkeypatch):
    settings={'labeling.provider':'ollama','labeling.ollama_model':'gpt-oss:120b-cloud'}
    monkeypatch.setattr(gpt,'get_setting_value',lambda key,**kwargs:settings.get(key,kwargs.get('default')))
    assert gpt.resolve_label_backend()==('ollama','gpt-oss:120b-cloud')
    settings['labeling.ollama_model']='gemma4:31b-cloud'
    assert gpt.resolve_label_backend()==('ollama','gemma4:31b-cloud')
    assert gpt.resolve_label_backend(model='gpt-oss:20b-cloud')==('ollama','gpt-oss:20b-cloud')


def test_pricing_follows_configured_model_and_unknown_prices_are_not_guessed():
    assert pricing_for_model('gpt-oss:120b-cloud').input_per_million==.15
    assert pricing_for_model('gemma4:31b-cloud').input_per_million==.14
    assert pricing_for_model('gpt-oss:20b-cloud').output_per_million==.30
    with pytest.raises(ValueError,match='verified default pricing'):
        pricing_for_model('unknown-configured-model')
    supplied=pricing_for_model('unknown-configured-model',1.0,.2,3.0)
    assert supplied.output_per_million==3.0 and supplied.source=='operator CLI pricing override'


def test_resume_skip_and_explicit_regeneration():
    args=parser().parse_args(['--limit','25','--dim_type','all'])
    rows=[dict(dimension=i,side='media' if i<768 else 'user',completed=i==0,abstained=i==1) for i in (0,1,2,768)]
    assert [r['dimension'] for r in choose(rows,args)]==[2,768]
    args=parser().parse_args(['--regenerate','--dimensions','0','1'])
    assert [r['dimension'] for r in choose(rows,args)]==[0,1]
    args=parser().parse_args(['--dim_type','user','--all'])
    assert [r['dimension'] for r in choose(rows,args)]==[768]
    args=parser().parse_args(['--dimension','1536'])
    with pytest.raises(ValueError):choose(rows,args)


def test_ollama_contract_bounded_output_and_usage_before_json_parse(monkeypatch):
    monkeypatch.setattr(gpt,'_resolve_ollama_model_name',lambda model:model)
    monkeypatch.setattr(gpt,'label_ollama_endpoint',lambda:('https://example.invalid',{'Authorization':'Bearer fictional-test-key'}))
    raw=dict(model='gemma4:31b-cloud',done=True,response=json.dumps(response()),prompt_eval_count=1200,prompt_eval_cached_count=900,eval_count=99)
    mock=Mock(status_code=200);mock.json.return_value=raw
    with patch.object(gpt.requests,'post',return_value=mock) as post:
        meter=Mock();result=gpt._call_ollama_for_label_result('fictional prompt','gemma4:31b-cloud',max_output_tokens=256,on_usage=meter)
    request=post.call_args.kwargs
    assert request['json']['options']['num_predict']==256 and request['json']['think'] is False
    assert request['json']['format']=='json' and request['allow_redirects'] is False
    assert request['json']['system']==gpt.SYSTEM_PROMPT
    assert result['label_confidence']=='high' and meter.call_args.args[0]['eval_count']==99
    raw.update(done_reason='length',response='{')
    with patch.object(gpt.requests,'post',return_value=mock),pytest.raises(LabelingError,match='output-token limit'):
        gpt._call_ollama_for_label_result('fictional','gemma4:31b-cloud',on_usage=meter)
    assert meter.call_count==2


def test_transient_retry_records_each_attempt_and_permanent_error_stops(monkeypatch):
    transient=RuntimeError('HTTP 503');transient.transient=True
    permanent=RuntimeError('HTTP 401');permanent.transient=False
    monkeypatch.setattr(gpt.time,'sleep',lambda _:None)
    for errors,expected in [([transient,response()],2),([permanent],1)]:
        before,after=Mock(),Mock()
        with patch.object(gpt,'_call_ollama_for_label_result',side_effect=errors) as cloud:
            try:gpt.call_llm_for_label_result('fictional',provider='ollama',model='gemma4:31b-cloud',before_attempt=before,attempt_callback=after)
            except RuntimeError:pass
        assert cloud.call_count==expected and before.call_count==expected and after.call_count==expected


def test_budget_hook_stops_retry_before_cloud(monkeypatch):
    def stop(_):raise BudgetExceeded('fictional budget')
    with patch.object(gpt,'_call_ollama_for_label_result') as cloud,pytest.raises(BudgetExceeded):
        gpt.call_llm_for_label_result('fictional',provider='ollama',model='gemma4:31b-cloud',before_attempt=stop)
    cloud.assert_not_called()


def test_coverage_must_match_actual_prompt_examples_and_counts():
    result=gpt._extract_label_result_from_response(json.dumps(response()))
    bundle=dict(positive_items=[{}]*6,negative_items=[{}]*4)
    assert validate_sample_counts(result,bundle)==result
    assert validate_sample_counts(dict(result,coverage_high_total=100),bundle)['validation_status']=='invalid'
    assert validate_sample_counts(dict(result,coverage_high_count=0),bundle)['label']==gpt.UNCLEAR_LABEL


@pytest.fixture
def sql_db():
    """Opt-in, isolated schema only. No test can change production label tables."""
    dsn=os.getenv('PLEXINTEL_LABELING_TEST_DATABASE_URL')
    if not dsn:pytest.skip('Set PLEXINTEL_LABELING_TEST_DATABASE_URL for isolated PostgreSQL labeling checks')
    conn=psycopg2.connect(dsn);schema='test_labeling_'+uuid4().hex
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE SCHEMA '+schema)
            cur.execute('SET search_path TO '+schema)
            cur.execute('''CREATE TABLE embedding_labels(dimension integer PRIMARY KEY,label text,display_label text,explainable boolean,needs_review boolean,
                label_type text,created_at timestamp,updated_at timestamp,last_reviewed_at timestamp,review_attempt_count integer DEFAULT 0,next_review_at timestamp);
                CREATE TABLE embedding_feature_config(config_id text PRIMARY KEY,metadata jsonb,active boolean);
                CREATE TABLE shap_impact(user_id text,rating_key integer,dimension integer,shap_value double precision);
                CREATE TABLE recommendations(username text,rating_key integer,scored_at timestamp);
                CREATE TABLE shap_prediction_context(username text,rating_key integer,scored_at timestamp,config_id text,model_version text);
                CREATE TABLE embedding_dimension_admin(config_id text,dimension integer,suppressed boolean);
                CREATE TABLE embedding_label_history(history_id serial,dimension integer,old_label text,old_label_type text,old_explainable boolean,
                    old_display_label text,old_needs_review boolean,old_last_reviewed_at timestamp,old_review_attempt_count integer,old_next_review_at timestamp,
                    new_label text,change_reason text,changed_at timestamp);
                CREATE TABLE embedding_dimension_assessments(assessment_id serial,dimension integer,config_id text,source text,provider text,model text,
                    prompt jsonb,result jsonb,saved boolean,outcome text,before_state jsonb,after_state jsonb,review_id integer,created_at timestamptz DEFAULT now());''')
            migration=Path('api/db/migrations/005_semantic_dimension_labeling.sql').read_text().replace('public.',schema+'.')
            cur.execute(migration)
            config,_,_=context_fixture()
            cur.execute('INSERT INTO embedding_feature_config VALUES(%s,%s,true)',(config['config_id'],Json(config)))
        conn.commit()
        yield conn,schema
    finally:
        conn.rollback()
        with conn.cursor() as cur:cur.execute('DROP SCHEMA '+schema+' CASCADE')
        conn.commit();conn.close()


def new_ledger(conn,budget=None):
    batch_id=str(uuid4())
    with conn.cursor() as cur:
        cur.execute("INSERT INTO embedding_label_batches(batch_id,config_id,feature_space_id,model,dimensions,forecast,pricing) VALUES(%s,'fictional-config','fictional-generation','gemma4:31b-cloud','[]','{}',%s)",(batch_id,Json(vars(Pricing()))))
    conn.commit()
    return UsageLedger(conn,batch_id,Pricing(),budget)


def test_sql_usage_per_attempt_retries_cache_and_budget(sql_db):
    conn,_=sql_db;ledger=new_ledger(conn,budget=.01)
    rid=ledger.start(0,'media',1,'fictional high low','system',420)
    ledger.finish(rid,dict(prompt_eval_count=100,prompt_eval_cached_count=50,eval_count=20),RuntimeError('fictional parse failure'))
    rid=ledger.start(0,'media',2,'fictional high low','system',420)
    ledger.finish(rid,dict(prompt_eval_count=100,prompt_eval_cached_count=80,eval_count=20),None)
    result=usage_report(conn,ledger.batch_id)
    assert result['combined']['input_tokens']==200 and result['combined']['cached_input_tokens']==130
    assert result['combined']['retry_input_tokens']==100 and result['combined']['retries']==1
    assert result['combined']['token_totals_are_complete'] and len(result['request_details'])==2
    ledger.budget=ledger.total_cost()
    with pytest.raises(BudgetExceeded):ledger.start(1,'media',1,'fictional','system',420)
    assert usage_report(conn,ledger.batch_id)['requests']==2


def test_sql_unknown_and_interrupted_requests_are_not_reported_as_zero_actual(sql_db):
    conn,_=sql_db;ledger=new_ledger(conn)
    rid=ledger.start(768,'user',1,'fictional','system',420)
    ledger.finish(rid,{},RuntimeError('fictional timeout'))
    ledger.start(768,'user',2,'fictional','system',420)  # interruption after reservation
    result=usage_report(conn,ledger.batch_id)['user']
    assert result['missing_input_counts']==2 and result['missing_output_counts']==2
    assert not result['token_totals_are_complete'] and result['pending']==1
    assert result['estimated_cost_usd']>0


def test_sql_forecast_refines_only_after_ten_successful_measurements(sql_db):
    conn,_=sql_db;ledger=new_ledger(conn)
    for i in range(10):
        rid=ledger.start(i,'media',1,'fictional','system',420)
        ledger.finish(rid,dict(prompt_eval_count=100,eval_count=30),None)
        if i<9:assert ledger.observations('fictional-config','gemma4:31b-cloud')=={}
    observed=ledger.observations('fictional-config','gemma4:31b-cloud')
    assert observed['media']['successful_requests']==10 and observed['media']['output_mean']==30
    assert 'pooled' in observed['user']['source']


def test_sql_explanation_path_rejects_old_generation_and_stale_shap(sql_db):
    conn,schema=sql_db;config,_,context=context_fixture()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO recommendations VALUES('fictional-viewer',1,'2000-01-01'); INSERT INTO shap_prediction_context VALUES('fictional-viewer',1,'2000-01-01','fictional-config',%s); INSERT INTO shap_impact VALUES('fictional-viewer',1,0,1)",(context['model_sha256'],))
        cur.execute("INSERT INTO embedding_labels(dimension,label,display_label,explainable,needs_review) VALUES(0,'fictional label','fictional label',true,false)")
        def selected():
            cur.execute('SELECT * FROM '+schema+".selected_embedding_labels('fictional-viewer',1)")
            return cur.fetchall()
        assert selected()==[]  # Historical dimension number is insufficient.
        cur.execute('UPDATE embedding_labels SET config_id=%s,feature_space_id=%s,contract_hash=%s,encoder_digest=%s',
                    (context['config_id'],context['feature_space_id'],context['contract_hash'],context['encoder_digest']))
        assert len(selected())==1  # No human approval required for an eligible candidate.
        cur.execute("UPDATE shap_prediction_context SET model_version='wrong'")
        assert selected()==[]
        cur.execute('UPDATE shap_prediction_context SET model_version=%s',(context['model_sha256'],))
        cur.execute("UPDATE embedding_labels SET feature_space_id='retired'")
        assert selected()==[]
        cur.execute('UPDATE embedding_labels SET feature_space_id=%s',(context['feature_space_id'],))
        cur.execute("INSERT INTO embedding_dimension_admin VALUES('fictional-config',0,true)")
        assert selected()==[]


def test_sql_persistence_reuses_original_governance_and_records_provenance(sql_db,monkeypatch):
    conn,_=sql_db;_,_,context=context_fixture()
    import api.services.dimension_label_batch as batch
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    assessment=Mock();monkeypatch.setattr(batch,'record_assessment',assessment)
    result=gpt._extract_label_result_from_response(json.dumps(response()))
    row=dict(dimension=0,side='media',prompt=dict(prompt_text='fictional HIGH LOW'))
    saved,outcome=persist_result(conn,context,row,result,'gemma4:31b-cloud')
    assert saved and outcome=='inserted_missing_label'
    with conn.cursor() as cur:
        cur.execute('SELECT config_id,feature_space_id,encoder_digest,interpretation_model,needs_review FROM embedding_labels')
        assert cur.fetchone()==(context['config_id'],context['feature_space_id'],context['encoder_digest'],'gemma4:31b-cloud',False)
    assert assessment.call_args.kwargs['prompt']['provenance']==context
    result['validation_status']='needs_review'
    persist_result(conn,context,row,result,'gemma4:31b-cloud',regenerate=True)
    # Original review replacement rules preserve a valid saved candidate when a
    # replacement itself requires review, instead of silently replacing it.
    with conn.cursor() as cur:
        cur.execute('SELECT label FROM embedding_labels');assert cur.fetchone()[0]=='workplace rivalries'


@pytest.mark.parametrize('label,high,minimum,eligible',[
    ('episodic drama series',100,70,False),('standalone movies and series',100,70,False),
    ('medical and birth events',66,70,False),('workplace rivalries',100,70,True),
    ('workplace rivalries',66,60,True),
])
def test_sql_validated_governance_controls_current_explanations(sql_db,monkeypatch,label,high,minimum,eligible):
    conn,schema=sql_db;_,_,context=context_fixture()
    import api.services.dimension_label_batch as batch
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    monkeypatch.setattr(batch,'record_assessment',Mock())
    result=gpt.validate_label_result(dict(response(),label=label,coverage_high_percent=high),minimum_label_coverage_percent=minimum)
    original=copy.deepcopy(result)
    row=dict(dimension=0,side='media',prompt=dict(prompt_text='fictional HIGH LOW',
        minimum_label_coverage_percent=minimum,maximum_low_overlap_percent=40))
    assert persist_result(conn,context,row,result,'gemma4:31b-cloud')[0]
    assert result==original
    with conn.cursor() as cur:
        cur.execute('SELECT label,explainable,interpretation_model,feature_space_id FROM embedding_labels WHERE dimension=0')
        assert cur.fetchone()==(label,eligible,'gemma4:31b-cloud',context['feature_space_id'])
        cur.execute("INSERT INTO recommendations VALUES('fictional-viewer',1,'2000-01-01'); INSERT INTO shap_prediction_context VALUES('fictional-viewer',1,'2000-01-01','fictional-config',%s); INSERT INTO shap_impact VALUES('fictional-viewer',1,0,1)",(context['model_sha256'],))
        cur.execute('SELECT * FROM '+schema+".selected_embedding_labels('fictional-viewer',1)")
        assert bool(cur.fetchall())==eligible
        cur.execute("UPDATE embedding_labels SET feature_space_id='retired'")
        cur.execute('SELECT * FROM '+schema+".selected_embedding_labels('fictional-viewer',1)")
        assert cur.fetchall()==[]


def test_sql_persistence_refuses_production_context_change(sql_db,monkeypatch):
    conn,_=sql_db;_,_,context=context_fixture()
    import api.services.dimension_label_batch as batch
    monkeypatch.setattr(batch,'current_context',lambda conn:dict(context,feature_space_id='changed'))
    with pytest.raises(ValueError,match='provenance changed'):
        persist_result(conn,context,dict(dimension=0,side='media',prompt={}),gpt.validate_label_result(response()),'gemma4:31b-cloud')
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM embedding_labels');assert cur.fetchone()[0]==0


def test_dry_run_reads_forecasts_without_cloud_or_label_writes(monkeypatch):
    from contextlib import nullcontext
    import api.services.dimension_label_batch as batch
    _,_,context=context_fixture()
    conn=Mock();evidence=Mock(context=context)
    row=dict(dimension=0,side='media',completed=False,abstained=False,prompt=dict(prompt_text='fictional full prompt'))
    monkeypatch.setattr(batch,'connect_db',lambda:conn)
    monkeypatch.setattr(batch,'batch_lock',lambda:nullcontext())
    monkeypatch.setattr(batch,'Evidence',lambda *a:evidence)
    monkeypatch.setattr(batch,'candidates',lambda *a:([row],{}))
    monkeypatch.setattr(batch.UsageLedger,'observations',lambda *a:{})
    monkeypatch.setattr(gpt,'get_setting_value',lambda key,**kwargs:{'labeling.provider':'ollama','labeling.ollama_model':'gemma4:31b-cloud'}.get(key,kwargs.get('default')))
    cloud=Mock();monkeypatch.setattr(gpt,'call_llm_for_label_result',cloud)
    persist=Mock();monkeypatch.setattr(batch,'execute',persist)
    batch.main(['--dry-run','--label','--save-label'])
    cloud.assert_not_called();persist.assert_not_called()
    conn.set_session.assert_called_once_with(readonly=True,isolation_level='REPEATABLE READ')
    conn.commit.assert_not_called()


def test_review_invocation_uses_setup_model_and_matching_price_in_forecast(monkeypatch):
    from contextlib import nullcontext
    import api.services.dimension_label_batch as batch
    _,_,context=context_fixture()
    conn=Mock();row=dict(dimension=0,side='media',completed=True,abstained=False,prompt=dict(prompt_text='fictional full prompt'))
    monkeypatch.setattr(batch,'connect_db',lambda:conn)
    monkeypatch.setattr(batch,'batch_lock',lambda:nullcontext())
    monkeypatch.setattr(batch,'Evidence',lambda *a:Mock(context=context))
    monkeypatch.setattr(batch,'candidates',lambda *a:([row],{}))
    monkeypatch.setattr(batch.UsageLedger,'observations',lambda *a:{})
    monkeypatch.setattr(gpt,'get_setting_value',lambda key,**kwargs:{'labeling.provider':'ollama','labeling.ollama_model':'gpt-oss:120b-cloud'}.get(key,kwargs.get('default')))
    cloud=Mock();monkeypatch.setattr(gpt,'call_llm_for_label_result',cloud)
    result=batch.main(['--dimension','0','--selection_mode','review','--dry_run'])
    assert result['interpretation_model']=='gpt-oss:120b-cloud'
    assert result['selected_batch']['pricing']['input_per_million']==.15
    assert result['model_source']=='Setup: labeling.ollama_model'
    cloud.assert_not_called()


@pytest.mark.parametrize('stop_at_budget',[False,True])
def test_sql_complete_batch_accounting_persistence_and_budget_stop(sql_db,monkeypatch,stop_at_budget):
    from contextlib import nullcontext
    import api.services.dimension_label_batch as batch
    conn,_=sql_db;_,_,context=context_fixture()
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    from api.services import pipeline_labeling as auto
    from types import SimpleNamespace
    caps=dict(zip(auto.POLICY_KEYS,(True,True,1.,100)))
    monkeypatch.setattr(auto,'resolve_settings',lambda **kw:{k:SimpleNamespace(value=caps[k]) for k in kw['keys']})
    args=parser().parse_args(['--label','--save-label','--label-model','gemma4:31b-cloud']+(['--budget-usd','0'] if stop_at_budget else []))
    row=dict(dimension=0,side='media',completed=False,abstained=False,prompt=dict(prompt_text='Fictional HIGH/LOW batch evidence'))
    eligible=[row];prediction=workload_forecast(eligible,eligible,Pricing(),args,{})
    def mocked_cloud(prompt,model,**kwargs):
        kwargs['on_usage'](dict(prompt_eval_count=1000,prompt_eval_cached_count=500,eval_count=100))
        return gpt._extract_label_result_from_response(json.dumps(response()))
    cloud=Mock(side_effect=mocked_cloud);monkeypatch.setattr(gpt,'_call_ollama_for_label_result',cloud)
    summary=batch.execute(conn,Mock(context=context),eligible,eligible,Pricing(),args,prediction)
    usage=usage_report(conn,summary['batch_id'])
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM embedding_labels');labels=cur.fetchone()[0]
        cur.execute('SELECT status FROM embedding_label_batches');status=cur.fetchone()[0]
        cur.execute("SELECT result->>'batch_id' FROM embedding_dimension_assessments")
        assessment_batches=cur.fetchall()
    if stop_at_budget:
        assert labels==0 and status=='budget_stopped' and usage['requests']==0
        assert assessment_batches==[]
        cloud.assert_not_called()
    else:
        assert assessment_batches==[(summary['batch_id'],)]
        assert labels==1 and status=='completed' and usage['requests']==1
        assert usage['combined']['input_tokens']==1000 and usage['combined']['cached_input_tokens']==500
        assert summary['successes']==1 and choose(eligible,args)==[]


def test_sql_interruption_keeps_completed_label_and_unknown_request_reservation(sql_db,monkeypatch):
    from contextlib import nullcontext
    import api.services.dimension_label_batch as batch
    conn,_=sql_db;_,_,context=context_fixture()
    monkeypatch.setattr(batch,'current_context',lambda conn:context)
    monkeypatch.setattr(batch,'dimension_review_guard',lambda *a:nullcontext(True))
    from api.services import pipeline_labeling as auto
    from types import SimpleNamespace
    caps=dict(zip(auto.POLICY_KEYS,(True,True,1.,100)))
    monkeypatch.setattr(auto,'resolve_settings',lambda **kw:{k:SimpleNamespace(value=caps[k]) for k in kw['keys']})
    args=parser().parse_args(['--label','--save-label','--label-model','gemma4:31b-cloud'])
    rows=[dict(dimension=i,side='media',completed=False,abstained=False,prompt=dict(prompt_text='Fictional HIGH LOW')) for i in (0,1)]
    calls=[]
    def mocked_cloud(prompt,model,**kwargs):
        calls.append(True)
        if len(calls)>1:raise KeyboardInterrupt()
        kwargs['on_usage'](dict(prompt_eval_count=1000,eval_count=100))
        return gpt._extract_label_result_from_response(json.dumps(response()))
    monkeypatch.setattr(gpt,'_call_ollama_for_label_result',mocked_cloud)
    prediction=workload_forecast(rows,rows,Pricing(),args,{})
    with pytest.raises(KeyboardInterrupt):batch.execute(conn,Mock(context=context),rows,rows,Pricing(),args,prediction)
    with conn.cursor() as cur:
        cur.execute('SELECT dimension FROM embedding_labels');assert cur.fetchall()==[(0,)]
        cur.execute('SELECT status FROM embedding_label_batches');assert cur.fetchone()[0]=='interrupted'
    usage=usage_report(conn)['combined']
    assert usage['pending']==1 and usage['missing_input_counts']==1
    assert [r['dimension'] for r in choose(rows,args)]==[1]
