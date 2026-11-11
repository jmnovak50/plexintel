"""Demonstrated restoration defects, no production DB or real provider required."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,MagicMock
import numpy as np
import pytest
from tests.test_predictive_identity import example
from api.predictive import source
from api.predictive.contracts import specification,fingerprint,ContractError
from api.predictive.features import (feature_row,training_rows,compact_row,Vocabulary,label_for,profile_inputs)
from api.predictive.recovery import CanonicalTitles
from api.services import dimension_label_batch as batch,pipeline_labeling as labeling
from api.services.labeling_costs import BudgetExceeded,Pricing


def test_single_label_admin_script_unconditionally_delegates_to_guarded_engine(monkeypatch):
    import label_embeddings as single
    current=Mock();monkeypatch.setattr(batch,'main',current)
    single.main(['--help']);current.assert_called_once_with(['--help'])
    current.reset_mock()
    single.label_single_dimension(12,generate_label=True,save_label=True)
    assert current.call_args.args[0]==['--dimension','12','--top-n','10','--label','--save-label']
    assert not hasattr(single,'_label_single_dimension')
    assert not hasattr(single,'call_llm_for_label_result')


@pytest.mark.parametrize('error',['unavailable','revoked','insufficient'])
def test_manual_execution_cannot_bypass_standing_cloud_policy(monkeypatch,error):
    provider=Mock();import gpt_utils as gpt
    monkeypatch.setattr(gpt,'call_llm_for_label_result',provider)
    monkeypatch.setattr(labeling,'limits',Mock(side_effect=BudgetExceeded(error)))
    conn=MagicMock();args=batch.parser().parse_args(['--label'])
    with pytest.raises(BudgetExceeded):batch.execute(conn,Mock(context={}),[],[],Pricing(),args,{})
    conn.cursor.assert_not_called();provider.assert_not_called()


def test_nondefault_profile_and_maturity_policy_changes_only_supported_fields(example):
    g,m,w,*_=example
    policy={'user_embeddings.engagement_threshold':.9,'training.movie_revisit_pending_days':30,'training.tv_revisit_pending_days':28}
    configured=specification(g['contract']['encoder'],policy=policy)
    assert configured['profile_threshold']==.9
    assert configured['movie_revisit_days']==30 and configured['tv_revisit_days']==28
    assert configured['watch_threshold']==g['contract']['watch_threshold']==.5
    inputs=dict(g,contract=configured)
    _,keys=profile_inputs(inputs,m,g['snapshot']['events'],'viewer',g['snapshot']['as_of'],identity=CanonicalTitles(m))
    assert keys==[]  # 80% viewed titles no longer qualify at 90%.
    event=dict(watched_at='2020-01-01T00:00:00+00:00',played_seconds=300)
    args=([event],None,3600,'movie','2020-01-23T00:00:00+00:00')
    assert label_for(*args,movie_days=21)[0]==0
    assert label_for(*args,movie_days=configured['movie_revisit_days']) is None


def test_numeric_transform_and_compact_dependency_digest_are_exact(example):
    g,m,w,*_=example
    for event in g['snapshot']['events']:w[str(event['watch_id'])]['source']=event
    detailed,_=training_rows(g,m,w)
    compact,_=training_rows(g,m,w,compact=True)
    vocabulary=Vocabulary.fit(detailed)
    np.testing.assert_array_equal(vocabulary.transform(detailed),vocabulary.transform(compact))
    assert all('dependencies' not in r for r in compact)
    for before,after in zip(detailed,compact):
        assert fingerprint(before['dependencies'])==after['dependency_hash']
        for key in ('label','sample_weight','watch_sim','prediction_at','label_available_at'):
            assert before[key]==after[key]
    # Explicitly compare the old transformation arithmetic, not a second call.
    old=[]
    for row in detailed:
        decade=int(row['year'])//10*10 if row['year'] is not None else None
        old.append(list(np.asarray(row['embedding'],dtype=np.float32))+
            [int(x in row['genres']) for x in vocabulary.genres]+
            [int(x in row['directors']) for x in vocabulary.directors]+
            [int(x==decade) for x in vocabulary.decades]+[row['watch_sim']])
    np.testing.assert_array_equal(vocabulary.transform(detailed),np.asarray(old,dtype=np.float32))
    bad=deepcopy(detailed[0]);bad['dependencies']['profile_keys'].append(bad['media_key'])
    with pytest.raises(ContractError,match='target leaked'):compact_row(bad,m,w,CanonicalTitles(m))


def test_ranking_feature_mode_omits_only_diagnostic_graph(example):
    g,m,w,old,live,_=example
    args=(g,m,w,g['snapshot']['events'],'viewer',str(live),g['snapshot']['as_of'])
    detailed=feature_row(*args);bounded=feature_row(*args,dependencies=False)
    np.testing.assert_array_equal(detailed['embedding'],bounded['embedding'])
    assert detailed['watch_sim']==bounded['watch_sim'] and bounded['dependencies'] is None


def test_absent_stop_receipts_are_unknown_not_invented(monkeypatch):
    event=dict(watch_id=1,rating_key=2,username='viewer',watched_at='2020-01-01T00:00:00+00:00',played_seconds=300)
    data=dict(recordsFiltered=1,data=[dict(id=1,rating_key=2,user='viewer',date=1577836800)])
    monkeypatch.setattr(source,'tautulli',lambda *a,**kw:data)
    snapshot=dict(events=[event]);result=source.event_availability({},snapshot)
    assert result['unknown_end_times']==1
    assert event['available_at'] is None and event['verified_started_at'] is None
    assert 'observed_at' not in event


def test_configured_explanation_allocations_and_cumulative_dimensions():
    from api.predictive.scoring import shap_targets,raw_shap
    media={str(i):dict(source=dict(metadata=dict(media_type='episode' if i<5 else 'movie'),
        show_rating_key=10 if i<3 else 20)) for i in range(1,7)}
    predictions=[(str(i),1-i/10,0.) for i in range(1,7)]
    policy={'scoring.shap_targeting_strategy':'per_media_type','scoring.shap_max_items_movie':1,
        'scoring.shap_max_items_tv':1,'scoring.shap_max_items_overall':1,'scoring.shap_max_items':4,
        'scoring.shap_raw_min_dims':1,'scoring.shap_raw_max_dims':3,'scoring.shap_raw_cumabs_target':.95}
    assert shap_targets(predictions,media,policy)=={'1','2','5'}
    policy['scoring.shap_targeting_strategy']='global'
    assert shap_targets(predictions,media,policy)=={'1','2','3','4'}
    assert raw_shap(np.array([.8,-.15,.05,0]),policy)==[(0,.8),(1,-.15)]
    policy['scoring.shap_raw_cumabs_target']=.9
    assert raw_shap(np.array([.95,.03,.02]),policy)==[(0,.95)]
    policy['scoring.shap_raw_max_dims']=0
    assert raw_shap(np.array([1.,2.]),policy)==[]


def test_policy_database_read_is_strict_and_incompatible_labels_fail_explicitly(monkeypatch):
    from api.services.app_settings import get_setting_definition
    resolver=Mock(side_effect=lambda **kw:{k:SimpleNamespace(value=(.6 if k=='training.engagement_threshold' else get_setting_definition(k).default)) for k in kw['keys']})
    monkeypatch.setattr(source,'resolve_settings',resolver)
    values=source.settings()
    assert resolver.call_args.kwargs['require_database'] is True
    assert values['training.engagement_threshold']==.6
    values['training.engagement_threshold']=.7
    resolver.side_effect=lambda **kw:{k:SimpleNamespace(value=values[k]) for k in kw['keys']}
    with pytest.raises(ContractError,match='0.60 label contract'):source.settings()


def test_explanation_settings_preserve_all_prediction_values_and_ranks(example):
    from api.predictive.scoring import score
    g,m,w,*_=example
    vocab=Vocabulary.fit(training_rows(g,m,w)[0])
    classifier=Mock()
    classifier.predict_proba.side_effect=lambda matrix:np.tile([.25,.75],(len(matrix),1))
    classifier.get_booster.return_value.predict.side_effect=lambda matrix,**kw:np.zeros((matrix.num_row(),len(vocab.names)+1))
    policy={'scoring.shap_targeting_strategy':'global','scoring.shap_max_items':750,
        'scoring.shap_raw_min_dims':5,'scoring.shap_raw_max_dims':40,'scoring.shap_raw_cumabs_target':.95}
    first=list(score(g,m,w,{'viewer':{}},{'model':classifier},vocab,policy=policy))
    second=list(score(g,m,w,{'viewer':{}},{'model':classifier},vocab,policy=dict(policy,**{'scoring.shap_max_items':0})))
    assert first and all(row['shap'] for row in first) and not any(row['shap'] for row in second)
    assert [{k:v for k,v in r.items() if k!='shap'} for r in first]==[{k:v for k,v in r.items() if k!='shap'} for r in second]
