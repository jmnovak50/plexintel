"""Statistical diagnostics never override technical success or failure."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock
import importlib

import pytest
from api.predictive.contracts import ContractError
from api.predictive.progress import Reporter
from api.services.pipeline_log_format import item_line, completion_summary
from api.services.pipeline_visibility import supplement


@pytest.fixture
def trainer(monkeypatch):
    module=importlib.import_module('api.predictive.train')
    rows=[dict(owner='fixture',media_key=str(i),canonical_identity='movie:'+str(i),label=i%2,
        prediction_at='2020-01-01T00:00:00+00:00') for i in range(4)]
    boundary=datetime(2020,1,2,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'chronological_split',lambda values:(rows[:2],rows[2:],boundary))
    monkeypatch.setattr(module,'CanonicalTitles',lambda media:object())
    monkeypatch.setattr(module,'show_heldout_plan',lambda *a,**kw:(rows[:2],rows[2:],set(),{}))
    monkeypatch.setattr(module,'feature_row',lambda *a,**kw:{})
    monkeypatch.setattr(module,'compact_row',lambda row,*a:row)
    vocabulary=Mock(names=['unchanged_feature']);vocabulary.specification.return_value={'unchanged':'vocabulary'}
    monkeypatch.setattr(module.Vocabulary,'fit',Mock(return_value=vocabulary))
    final=Mock(return_value=object());monkeypatch.setattr(module,'fit',final)
    return module,rows,final


@pytest.mark.parametrize('chronological_ba,show_ba,ap,expected',[
    (.5,.5,.85,[]),(.49,.7,.9,['chronological_balanced_accuracy']),
    (.7,.49,.9,['show_balanced_accuracy']),(.7,.7,.849,['average_precision']),
    (.4,.3,.2,['chronological_balanced_accuracy','show_balanced_accuracy','average_precision']),
    (.7,None,None,['show_balanced_accuracy','average_precision']),
])
def test_thresholds_are_retained_as_warnings_and_final_fit_always_proceeds(trainer,monkeypatch,chronological_ba,show_ba,ap,expected):
    module,rows,final=trainer
    chronological=dict(balanced_accuracy=chronological_ba,average_precision=ap,training_seconds=1.23,confusion_matrix=[[1,2],[3,4]])
    show=dict(balanced_accuracy=show_ba,average_precision=.8,training_seconds=2.34)
    before=deepcopy((chronological,show))
    compare=Mock(side_effect=[chronological,show]);monkeypatch.setattr(module,'fit_compare',compare)
    output=[];reporter=Reporter(output.append)
    with reporter.span('train_model'):
        bundle,_,evaluation=module.train(dict(feature_space_id='same-space',contract_hash='same-contract',snapshot={'events':[]}),
            {},{},rows,dict(dataset_hash='same-data'),incumbent_ap=.9,
            warning=lambda value:reporter.log('train_model','quality_warning',**value))
    reporter.done('train_model',quality_passed=all(evaluation['gates'].values()),quality_warning_count=len(evaluation['statistical_warnings']))
    final.assert_called_once();assert final.call_args.args[0] is rows
    assert bundle['model'] is final.return_value and bundle['feature_space_id']=='same-space'
    assert compare.call_count==2  # Existing validation fits only; no reference refits.
    assert evaluation['statistical_checks_blocking'] is False
    assert [w['check'] for w in evaluation['statistical_warnings']]==expected
    for key in before[0]:assert evaluation['chronological'][key]==before[0][key]
    for key in before[1]:assert evaluation['show_heldout'][key]==before[1][key]
    messages=[item_line(v) for v in output if v.get('operation')=='quality_warning']
    assert len(messages)==len(expected) and all('Non-blocking statistical warning:' in m for m in messages)
    assert output[-1]['status']=='success' and output[-1]['metrics']['quality_warning_count']==len(expected)
    assert not any(v.get('status')=='failed' for v in output)
    for warning in evaluation['statistical_warnings']:
        assert warning['blocking'] is False and warning['comparison']=='>='
        expected_min=.85 if warning['check']=='average_precision' else .5
        assert warning['minimum']==pytest.approx(expected_min)
    text=completion_summary('train_model',dict(evaluation=evaluation))
    assert 'Diagnostic statistical checks (non-blocking)' in text
    assert 'Recorded quality gates:' not in text


def test_true_training_failure_is_still_a_failure_after_statistical_warnings(trainer,monkeypatch):
    module,rows,final=trainer
    monkeypatch.setattr(module,'fit_compare',Mock(side_effect=[dict(balanced_accuracy=.4,average_precision=.1),dict(balanced_accuracy=.3)]))
    final.side_effect=RuntimeError('genuine final classifier fit failure')
    output=[];reporter=Reporter(output.append)
    with pytest.raises(RuntimeError,match='genuine final classifier'):
        with reporter.span('train_model'):
            module.train(dict(snapshot={'events':[]}),{},{},rows,{},incumbent_ap=.9,
                warning=lambda value:reporter.log('train_model','quality_warning',**value))
    assert len([e for e in output if e.get('operation')=='quality_warning'])==3
    assert output[-1]['status']=='failed'


def test_evaluation_execution_error_is_not_treated_as_a_statistical_warning(trainer,monkeypatch):
    module,rows,final=trainer
    monkeypatch.setattr(module,'fit_compare',Mock(side_effect=ContractError('invalid inference dimensions')))
    with pytest.raises(ContractError,match='invalid inference dimensions'):
        module.train({}, {}, {}, rows, {})
    final.assert_not_called()


def test_historical_evaluations_keep_their_original_gate_meaning_and_warning_availability():
    original={'gates':{'average_precision':False},'chronological':{'average_precision':.7}}
    before=deepcopy(original)
    assert 'Recorded quality gates: average precision: failed' in completion_summary('train_model',dict(evaluation=original))
    details=[{'stage_key':'train_model','status':'failed','metrics':{}}]
    supplement(details,{'evaluation':original})
    assert details[0]['metrics']['quality_passed'] is False
    assert 'quality_warning_count' not in details[0]['metrics']
    assert original==before
    new=dict(original,statistical_checks_blocking=False,statistical_warnings=[{'check':'average_precision'}])
    supplement(details,{'evaluation':new})
    assert details[0]['metrics']['quality_warning_count']==1


from tests.test_predictive_publication import db


@pytest.mark.parametrize('technical_failure',[False,True])
def test_real_publication_allows_statistical_warnings_but_not_fit_failures(db,tmp_path,monkeypatch,technical_failure):
    import json
    from tests.test_predictive_publication import populate,digest
    from tests.test_pipeline_log_view import fixture
    from api.predictive.runner import run
    from api.predictive.artifacts import current_config
    from api.predictive.publication import verify
    from api.services.pipeline_logs import get_stage_logs
    module=importlib.import_module('api.predictive.train')
    snapshot,plex,encoder=populate(db)
    first=run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,
        collect=False,label=False,output=lambda value:None)
    incumbent=current_config(db);db.commit();before=digest(db);db.commit()
    real_compare=module.fit_compare
    def unfavorable(*args,**kwargs):
        result=real_compare(*args,**kwargs)
        return dict(result,balanced_accuracy=.4,average_precision=.01)
    monkeypatch.setattr(module,'fit_compare',unfavorable)
    if technical_failure:
        monkeypatch.setattr(module,'fit',Mock(side_effect=RuntimeError('genuine final fit failure')))
    events=[]
    kwargs=dict(frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,
        collect=False,label=False,output=events.append)
    if technical_failure:
        with pytest.raises(RuntimeError,match='genuine final fit failure'):run(db,tmp_path,**kwargs)
        assert current_config(db)==incumbent and digest(db)==before
        db.commit()
        assert any(e.get('stage_key')=='train_model' and e.get('status')=='failed' for e in events)
        assert not any(e.get('stage_key')=='publication' for e in events)
    else:
        result=run(db,tmp_path,**kwargs)
        assert result['verified'] and result['counts']['recommendations']>0
        assert not any(result['evaluation']['gates'].values())
        assert len(result['evaluation']['statistical_warnings'])==3
        config=current_config(db);db.commit()
        assert config['evaluation']==result['evaluation']
        assert verify(db,config)==result['counts'];db.commit()
        final={e['stage_key']:e for e in events if 'status' in e and 'stage_key' in e}
        for key in ('train_model','score_model','publication','verification'):assert final[key]['status']=='success'
        assert final['train_model']['metrics']['quality_passed'] is False
        assert final['train_model']['metrics']['quality_warning_count']==3
        assert final['semantic_labels']['status']=='skipped'
        raw=''.join(json.dumps(e)+'\n' for e in events)+json.dumps(result)+'\n'
        monitor=fixture(tmp_path,monkeypatch,raw)
        text=get_stage_logs(monitor,'train_model')['stdout']['text']
        assert '⚠️ Non-blocking statistical warning:' in text
        assert 'Diagnostic statistical checks (non-blocking)' in text
        assert '0.010000' in text and 'minimum=0.500000' in text
    assert len([e for e in events if e.get('operation')=='quality_warning'])==3
    assert all(first['evaluation']['gates'].values())  # Original result was not rewritten.
