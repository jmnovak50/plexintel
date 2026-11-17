"""Item logging observes fake encoders/classifiers; never executes a pipeline."""
from collections import Counter
from copy import deepcopy
import json
import tempfile
from unittest.mock import Mock

import numpy as np
import pytest
from api.predictive.contracts import specification
from api.predictive.prepare import refresh_vector
from api.predictive.progress import Reporter,EventReader,EVENT,ITEM_EVENT,media_log_fields
from api.services import pipeline_logs as logs
from tests.test_predictive_identity import example,unit
from tests.test_pipeline_log_view import fixture,event


def test_embedding_logs_start_before_actual_request_and_distinguish_cache_reuse():
    spec=specification(dict(name='fictional-encoder',digest='x',dimensions=768))
    events=[];encoder=Mock()
    def embed(text):
        assert events[-1][0]=='embedding'
        assert text=='exact serialized input'
        return unit()
    encoder.embed.side_effect=embed
    callback=lambda operation,**fields:events.append((operation,fields))
    stats=Counter();result=refresh_vector(spec,'media_text','7',{},'exact serialized input',{},encoder,stats,log=callback)
    assert [op for op,_ in events]==['embedding','embedded']
    encoder.embed.assert_called_once_with('exact serialized input')
    plain_encoder=Mock();plain_encoder.embed.return_value=unit()
    assert refresh_vector(spec,'media_text','7',{},'exact serialized input',{},plain_encoder,Counter())==result
    old={'7':dict(embedding=result['embedding'],provenance={k:v for k,v in result.items() if k!='embedding'})}
    events.clear();encoder.reset_mock()
    cached=refresh_vector(spec,'media_text','7',{},'exact serialized input',deepcopy(old),encoder,stats,log=callback)
    assert cached==result and events==[('reused',{})]
    encoder.embed.assert_not_called()
    events.clear();encoder.embed.side_effect=embed
    # A cached input mismatch still follows the original one-request path.
    old['7']['provenance']['input_hash']='changed'
    refresh_vector(spec,'media_text','7',{},'exact serialized input',old,encoder,stats,log=callback)
    assert [op for op,_ in events]==['embedding','embedded']
    assert stats==dict(inferred=2,reused=1)


def test_embedding_failure_identifies_operation_without_logging_request_or_secret():
    spec=specification(dict(name='fake',digest='x',dimensions=768))
    encoder=Mock();encoder.embed.side_effect=RuntimeError('private request URL token=must-not-log')
    messages=[];callback=lambda operation,**fields:messages.append(dict(operation=operation,**fields))
    with pytest.raises(RuntimeError,match='private request'):
        refresh_vector(spec,'media_text','7',{},'private synopsis',{},encoder,Counter(),log=callback)
    assert messages[-1]==dict(operation='embedding_failed',error_type='RuntimeError')
    assert not any(v['operation']=='embedded' for v in messages)
    assert 'must-not-log' not in json.dumps(messages) and 'private synopsis' not in json.dumps(messages)


def test_item_events_do_not_replace_stage_state_or_create_observer_events():
    events=[];r=Reporter(events.append)
    r.emit('media_text','started',completed=0,expected=2)
    saved=deepcopy(r.details)
    for i in range(30):r.log('media_text','embedded',rating_key=str(i),title='Fictional film')
    assert r.details==saved and len(events)==31  # Item output is not throttled away.
    with tempfile.TemporaryFile('w+b') as f:
        f.write(''.join(json.dumps(e)+'\n' for e in events).encode());f.flush()
        observed,_=EventReader(f).read()
    assert len(observed)==1 and observed[0]['event']==EVENT
    r=Reporter(events.append,log_titles=False)
    r.log('media_text','embedded',rating_key='7',title='Private title',show_title='Private show')
    assert events[-1]['rating_key']=='7' and 'title' not in events[-1] and 'show_title' not in events[-1]


def test_title_logging_does_not_change_embedding_contract_or_cache_identity():
    encoder=dict(name='fictional-encoder',digest='x',dimensions=768)
    assert specification(encoder,policy={'embeddings.log_titles':True})==specification(
        encoder,policy={'embeddings.log_titles':False})


def test_scoring_logs_are_real_named_item_results_without_changing_any_predictions(example):
    from api.predictive.scoring import score
    from api.predictive.features import training_rows,Vocabulary
    g,m,w,*_=example;vocabulary=Vocabulary.fit(training_rows(g,m,w)[0]);classifier=Mock()
    classifier.predict_proba.side_effect=lambda matrix:np.tile([.25,.75],(len(matrix),1))
    def contribute(matrix,**kwargs):
        values=np.zeros((matrix.num_row(),len(vocabulary.names)+1))
        values[:,0]=.2;values[:,1]=-.3;values[:,-2]=.4;values[:,-1]=99  # Bias must not be ranked.
        return values
    classifier.get_booster.return_value.predict.side_effect=contribute
    policy={'scoring.shap_targeting_strategy':'global','scoring.shap_max_items':2,
        'scoring.shap_raw_min_dims':5,'scoring.shap_raw_max_dims':40,'scoring.shap_raw_cumabs_target':.95}
    args=(g,m,w,{'viewer':{}},{'model':classifier},vocabulary)
    expected=list(score(*args,policy=policy));calls=classifier.predict_proba.call_count
    explanation_calls=classifier.get_booster.return_value.predict.call_count
    classifier.reset_mock();messages=[]
    actual=list(score(*args,policy=policy,log=lambda operation,**fields:messages.append(dict(operation=operation,**fields))))
    assert actual==expected and classifier.predict_proba.call_count==calls
    assert classifier.get_booster.return_value.predict.call_count==explanation_calls
    assert messages[0]['operation']=='scoring_user' and messages[0]['user']=='viewer'
    ranked=[e for e in messages if e['operation']=='ranked_shap']
    assert len(ranked)==min(2,len(actual))
    for record in ranked:
        prediction=next(p for p in actual if str(p['key'])==record['rating_key'])
        assert record['rank']==prediction['rank'] and record['probability']==prediction['probability']
        assert record['title']==m[record['rating_key']]['source']['metadata']['title']
        assert record['contributions'][0]==dict(feature=vocabulary.names[-1],value=.4)
        assert len(record['contributions'])==3 and all(v['value']!=99 for v in record['contributions'])
    assert messages[-1]['operation']=='scoring_complete'
    classifier.reset_mock();messages.clear()
    no_targets=list(score(*args,policy=dict(policy,**{'scoring.shap_max_items':0}),
                          log=lambda operation,**fields:messages.append(dict(operation=operation,**fields))))
    assert [{k:v for k,v in row.items() if k!='shap'} for row in no_targets]==[
        {k:v for k,v in row.items() if k!='shap'} for row in expected]
    assert not any(row['shap'] for row in no_targets)
    assert not any(message['operation']=='ranked_shap' for message in messages)
    classifier.get_booster.return_value.predict.assert_not_called()


def test_embedding_and_ranked_output_are_readable_grouped_and_never_duplicated(monkeypatch,tmp_path):
    values=[];r=Reporter(values.append)
    r.log('media_text','embedding',**media_log_fields('7',dict(metadata=dict(media_type='episode',title='Episode Ω',
        show_context=dict(title='Fictional series'),season_number=1,episode_number=2))))
    r.log('media_text','embedded',rating_key='7',title='Episode Ω')
    r.log('score_model','ranked_shap',user='Fictional viewer',rank=3,rating_key='7',title='Episode Ω',
          probability=.8,contributions=[dict(feature='genre_Drama',value=-.25)])
    raw=event('source_sync')+'Collector output\n'+event('source_sync','success')+'\n'.join(json.dumps(v) for v in values)+'\n'
    run=fixture(tmp_path,monkeypatch,raw)
    source=logs.get_stage_logs(run,'source_sync')['stdout'];media=logs.get_stage_logs(run,'media_text')['stdout']
    score=logs.get_stage_logs(run,'score_model')['stdout']
    assert 'Collector output' in source['text'] and '🎬 Embedding' in source['text']
    assert 'Fictional series — S01E02' in source['text']
    assert 'Collector output' not in media['text'] and 'Episode Ω' in media['text']
    assert 'Rank 3: 7 —' in score['text'] and 'Probability: 0.800' in score['text']
    assert 'genre_Drama (-0.25)' in score['text']
    assert source['has_item_details'] and score['has_item_details']
    worker=logs.get_stage_logs(run,'predictive_daily')['stdout']['text']
    assert 'Episode Ω' not in worker


def test_pre_item_history_explicitly_explains_missing_title_and_rank_details(monkeypatch,tmp_path):
    run=fixture(tmp_path,monkeypatch,event('media_text')+event('media_text','success')+event('score_model'))
    assert 'Per-title embedding decisions were not retained' in logs.get_stage_logs(run,'source_sync')['stdout']['note']
    assert 'ranked SHAP log lines were not retained' in logs.get_stage_logs(run,'score_model')['stdout']['note']
    assert not logs.get_stage_logs(run,'source_sync')['stdout']['has_item_details']
    legacy=dict(run_id=998,stages=[dict(stage_key='tautulli_incremental',stdout_tail='Original real title list')])
    assert logs.get_stage_logs(legacy,'tautulli_incremental')['stdout']['text']=='Original real title list'
    assert not logs.get_stage_logs(legacy,'tautulli_incremental')['stdout']['note'] or 'Per-title' not in logs.get_stage_logs(legacy,'tautulli_incremental')['stdout']['note']
