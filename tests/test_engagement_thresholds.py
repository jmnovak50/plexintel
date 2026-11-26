"""Configurable passive labels; synthetic evidence and isolated settings only."""
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock

import pytest

from api.predictive.contracts import (ContractError,engagement_thresholds,configured_engagement_thresholds,
    specification,modality_contract,fingerprint)
from api.predictive.features import label_for,training_rows,Vocabulary,SUPERVISION_POLICY
from api.predictive.recovery import IDENTITY_POLICY
from api.predictive import artifacts,source
from api.services import app_settings
from tests.test_app_settings import FakeConnection
from tests.test_predictive_identity import example

NOW=datetime(2020,3,1,tzinfo=timezone.utc)

def events(ratio,age=30,runtime=6000):
    return [dict(played_seconds=runtime*ratio,watched_at=(NOW-timedelta(days=age)).isoformat())]


def previous_label(rows,feedback,runtime,kind,now):
    # Independent frozen pre-change behavior, including precedence and weights.
    explicit={'interested':(1,.75,'explicit_interest'),'never_watch':(0,5.,'explicit_reject'),
        'watched_like':(1,3.,'explicit_watched_like'),'watched_dislike':(0,5.,'explicit_watched_dislike')}
    if rows and (not runtime or runtime<=0):return None
    if feedback and feedback['feedback'] in explicit:return explicit[feedback['feedback']]
    played=[e['played_seconds'] for e in rows if e.get('played_seconds') is not None]
    if not played:return None
    ratio=sum(played)/runtime;maximum=max(played);weight=min(1+.5*len(played),5.)
    if ratio>=.60:return (1,weight,'watch_history')
    if maximum>=120 and ratio<=.35 and (maximum>=600 or maximum/runtime>=.05):
        last=max(datetime.fromisoformat(e['watched_at']) for e in rows)
        if (now-last).days >= (14 if kind=='episode' else 21):return (0,weight,'watch_history')
    return None


@pytest.mark.parametrize('ratio',[0,.01,.02,.049,.05,.1,.3499,.35,.3501,.5999,.6,.6001,.9,1,1.5])
@pytest.mark.parametrize('kind,age',[('movie',20),('movie',21),('episode',13),('episode',14)])
def test_defaults_reproduce_frozen_prechange_labels(ratio,kind,age):
    rows=events(ratio,age)
    assert label_for(rows,None,6000,kind,NOW)==previous_label(rows,None,6000,kind,NOW)


@pytest.mark.parametrize('positive,negative,ratio,expected',[
    (.6,.35,.6,1),(.6,.35,.35,0),(.6,.35,.35001,None),(.6,.35,.59999,None),
    (.7,.35,.65,None),(.65,.35,.65,1),(.6,.45,.4,0),(.6,.4,.4,0),(.6,.35,.4,None),
    (.7,.4,.55,None),(1.,0.,1.,1),(1.,0.,.5,None),
])
def test_configured_boundaries_and_exact_equality(positive,negative,ratio,expected):
    value=label_for(events(ratio),None,6000,'movie',NOW,positive_minimum=positive,negative_maximum=negative)
    assert (None if value is None else value[0])==expected


def test_cumulative_viewing_and_sample_weight_are_preserved():
    rows=events(.2)+events(.25)
    assert label_for(rows,None,6000,'movie',NOW,positive_minimum=.45)==(1,2.,'watch_history')
    assert label_for(rows,None,6000,'movie',NOW,positive_minimum=.6,negative_maximum=.45)==(0,2.,'watch_history')


@pytest.mark.parametrize('kind,age,allowed',[('movie',20,False),('movie',21,True),('episode',13,False),('episode',14,True)])
def test_configured_negative_boundary_keeps_revisit_window(kind,age,allowed):
    result=label_for(events(.4,age),None,6000,kind,NOW,negative_maximum=.45)
    assert (result is not None)==allowed


@pytest.mark.parametrize('seconds,runtime',[(119,6000),(200,6000),(None,6000),(600,0)])
def test_negative_boundary_does_not_bypass_meaningful_play_or_runtime(seconds,runtime):
    rows=events(.1);rows[0]['played_seconds']=seconds
    assert label_for(rows,None,runtime,'movie',NOW,negative_maximum=.55) is None


@pytest.mark.parametrize('feedback,expected',[
    ('interested',(1,.75,'explicit_interest')),('never_watch',(0,5.,'explicit_reject')),
    ('watched_like',(1,3.,'explicit_watched_like')),('watched_dislike',(0,5.,'explicit_watched_dislike')),
])
@pytest.mark.parametrize('ratio',[.1,.5,.95])
def test_explicit_feedback_precedence_and_weights_are_unchanged(feedback,expected,ratio):
    assert label_for(events(ratio),dict(feedback=feedback),6000,'movie',NOW,
        positive_minimum=.75,negative_maximum=.45)==expected


@pytest.mark.parametrize('positive,negative',[(0,0),(.6,.6),(.6,.7),(-.1,0),(1.1,.35),(.6,-.1),
    (.6,1.1),(float('nan'),.35),(.6,float('nan')),(float('inf'),.35),(.6,float('-inf')),
    (True,.35),(.6,False),('garbage',.35),(.6,None)])
def test_invalid_pairs_fail_with_actionable_errors(positive,negative):
    with pytest.raises(ContractError,match='Engagement'):
        engagement_thresholds(positive,negative)


@pytest.mark.parametrize('key',app_settings.ENGAGEMENT_SETTING_KEYS)
@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity',-0.001,1.001])
def test_individual_settings_reject_nonfinite_and_out_of_range_values(key,value):
    with pytest.raises(app_settings.SettingsValidationError):
        app_settings.parse_value(app_settings.get_setting_definition(key),value)


@pytest.fixture
def settings_store(monkeypatch):
    def make(positive=.6,negative=.35):
        data=[dict(key=key,raw_value=str(value),source='admin_ui')
            for key,value in zip(app_settings.ENGAGEMENT_SETTING_KEYS,(positive,negative))]
        conn=FakeConnection(data)
        monkeypatch.setattr(app_settings,'connect_db',lambda:conn)
        monkeypatch.setattr(app_settings,'ensure_settings_schema',lambda _:None)
        return conn
    return make


@pytest.mark.parametrize('updates,clears,stored,valid',[
    ({'training.engagement_threshold':.3},[],(.6,.35),False),
    ({'training.negative_engagement_threshold':.7},[],(.6,.35),False),
    ({'training.negative_engagement_threshold':.7,'training.engagement_threshold':.8},[],(.6,.35),True),
    ({'training.engagement_threshold':.6,'training.negative_engagement_threshold':.6},[],(.6,.35),False),
    ({},['training.engagement_threshold'],(.8,.7),False),
    ({},['training.engagement_threshold','training.negative_engagement_threshold'],(.8,.7),True),
    ({'training.engagement_threshold':None},[],(.8,.7),False),
    ({'training.engagement_threshold':.8},['training.engagement_threshold'],(.6,.35),True),
])
def test_settings_save_validates_final_pair_before_any_write(settings_store,updates,clears,stored,valid):
    conn=settings_store(*stored)
    if valid:
        app_settings.save_settings(updates=updates,clear_keys=clears,updated_by='fixture')
        assert conn.commit_count==1
    else:
        with pytest.raises(app_settings.SettingsValidationError,match='strictly below'):
            app_settings.save_settings(updates=updates,clear_keys=clears,updated_by='fixture')
        assert conn.commit_count==0
        assert not any('INSERT INTO' in query for query,args in conn.cursor_obj.executed)
    assert any('SHARE ROW EXCLUSIVE' in query for query,args in conn.cursor_obj.executed)


def test_missing_negative_setting_keeps_existing_positive_and_uses_default(monkeypatch):
    monkeypatch.setattr(app_settings,'_fetch_setting_rows',lambda keys:{'training.engagement_threshold':
        dict(key='training.engagement_threshold',raw_value='.6',source='admin_ui')})
    result=app_settings.resolve_settings(keys=app_settings.ENGAGEMENT_SETTING_KEYS)
    assert configured_engagement_thresholds({k:v.value for k,v in result.items()})==engagement_thresholds()
    positive,negative=(app_settings.get_setting_definition(k) for k in app_settings.ENGAGEMENT_SETTING_KEYS)
    assert (positive.label,positive.default)==('Positive Engagement Minimum',.6)
    assert (negative.label,negative.default)==('Negative Engagement Maximum',.35)


@pytest.mark.parametrize('ratio,thresholds,expected',[
    (.65,engagement_thresholds(.7,.35),None),(.65,engagement_thresholds(.65,.35),1),
    (.4,engagement_thresholds(.6,.4),0),(.4,engagement_thresholds(.6,.35),None),
])
def test_active_training_plan_consumes_thresholds_and_preserves_isolation(example,ratio,thresholds,expected):
    inputs,media,watches,old,live,event=example
    inputs['label_thresholds']=thresholds
    inputs['snapshot']['events']=inputs['snapshot']['events'][:1]+[event(2,live,3,played=ratio*6000)]
    inputs['snapshot']['feedback']=[]
    rows,_=training_rows(inputs,media,watches)
    targets=[r for r in rows if r['media_key']==str(live)]
    if expected is None:assert targets==[]
    else:
        assert len(targets)==1 and targets[0]['label']==expected
        row=targets[0]
        assert row['label_thresholds']==row['dependencies']['label_thresholds']==thresholds
        assert row['dependencies']['profile_keys']==['1']
        assert row['prediction_at']=='2020-01-03T00:00:00+00:00'
        assert row['sample_weight']==1.5


def test_preparation_propagates_policy_without_changing_feature_contract(monkeypatch,example):
    import importlib
    prepare=importlib.import_module('api.predictive.prepare')
    inputs,media,watches,*_=example
    for event in inputs['snapshot']['events']:watches[str(event['watch_id'])]['source']=event
    rows,_=training_rows(inputs,media,watches,compact=True)
    monkeypatch.setattr(prepare,'cache',lambda *a:{})
    received=[]
    def training(actual,*args,**kwargs):received.append(actual);return rows,{}
    monkeypatch.setattr(prepare,'training_rows',training)
    encoder=Mock(identity=inputs['contract']['encoder']);plex=Mock();plex.catalog.return_value=[]
    policy={'training.engagement_threshold':.7,'training.negative_engagement_threshold':.4}
    pending=Mock();pending.population.return_value=0
    result=prepare.prepare(Mock(),dict(media=[],events=[],feedback=[],as_of=NOW.isoformat()),plex,encoder,{},policy=policy,pending=pending)
    assert received[0]['label_thresholds']==result[-1]['label_thresholds']==engagement_thresholds(.7,.4)
    baseline=specification(encoder.identity)
    baseline.update(identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY)
    assert result[0]['contract']==baseline
    assert result[0]['feature_space_id']==fingerprint(baseline)
    for kind in ('media_text','watch','user'):
        assert modality_contract(result[0]['contract'],kind)==modality_contract(baseline,kind)
    encoder.embed.assert_not_called()


def test_fit_metadata_propagation_and_row_policy_mismatch_fail_before_fit(monkeypatch,example):
    import importlib
    train=importlib.import_module('api.predictive.train')
    inputs,media,watches,*_=example
    inputs['label_thresholds']=engagement_thresholds(.7,.4)
    for event in inputs['snapshot']['events']:watches[str(event['watch_id'])]['source']=event
    rows,_=training_rows(inputs,media,watches,compact=True)
    fit=Mock();monkeypatch.setattr(train,'fit',fit)
    metrics=dict(balanced_accuracy=.6,average_precision=.9)
    monkeypatch.setattr(train,'fit_compare',lambda *a,**kw:dict(metrics))
    monkeypatch.setattr(train,'chronological_split',lambda rows:(rows,rows,NOW))
    monkeypatch.setattr(train,'show_heldout_plan',lambda *a,**kw:(rows,rows,set(),{}))
    monkeypatch.setattr(train,'feature_row',lambda *a,**kw:dict(rows[0],dependencies={'profile_keys':[], 'watch_events':[]}))
    bundle,vocab,evaluation=train.train(inputs,media,watches,rows,dict(dataset_hash='fixture'))
    assert bundle['label_thresholds']==evaluation['label_thresholds']==inputs['label_thresholds']
    assert fit.call_count==1
    rows[0]['label_thresholds']=engagement_thresholds()
    fit.reset_mock()
    with pytest.raises(ContractError,match='thresholds differ'):
        train.train(inputs,media,watches,rows,dict(dataset_hash='fixture'))
    fit.assert_not_called()


def artifact_fixture(tmp_path,thresholds=None):
    vocab=Vocabulary([],[],[])
    spec=specification(dict(name='embeddinggemma-2:latest',digest='a'*64))
    config=dict(architecture='public-text-predictor/1.0',source_sha256='source',feature_space_id=fingerprint(spec),
        contract=spec,contract_hash=fingerprint(spec),feature_names=vocab.names)
    bundle=dict(source_sha256='source',feature_space_id=config['feature_space_id'],contract_hash=config['contract_hash'],
        feature_names=vocab.names,vocabulary=vocab.specification(),identity_policy=IDENTITY_POLICY,
        supervision_policy=SUPERVISION_POLICY,model='not a trained fixture',dataset_hash='fixture')
    if thresholds is not None:config['label_thresholds']=dict(thresholds);bundle['label_thresholds']=dict(thresholds)
    path,sha=artifacts.save_model(tmp_path,bundle);config.update(model_path=path,model_sha256=sha)
    return config,bundle


@pytest.mark.parametrize('thresholds',[None,engagement_thresholds(),engagement_thresholds(.7,.4)])
def test_existing_and_new_artifacts_remain_loadable_with_unchanged_checks(tmp_path,thresholds):
    config,bundle=artifact_fixture(tmp_path,thresholds)
    actual,_=artifacts.load_model(config)
    assert actual==bundle
    bad=dict(config,source_sha256='tampered')
    with pytest.raises(ContractError,match='policy mismatch'):artifacts.load_model(bad)
    bad=dict(config,contract=dict(config['contract'],features='tampered'))
    with pytest.raises(ContractError,match='policy mismatch'):artifacts.load_model(bad)
    bad=dict(config,model_sha256='0'*64)
    with pytest.raises(ContractError,match='checksum mismatch'):artifacts.load_model(bad)


@pytest.mark.parametrize('change',['different','missing','invalid','extra'])
def test_new_model_threshold_provenance_cannot_be_changed_or_dropped(tmp_path,change):
    config,bundle=artifact_fixture(tmp_path,engagement_thresholds(.7,.4))
    if change=='different':config['label_thresholds']=engagement_thresholds()
    if change=='missing':config.pop('label_thresholds')
    if change=='invalid':config['label_thresholds']['negative_maximum']=.75
    if change=='extra':config['label_thresholds']['unknown']=1
    with pytest.raises(ContractError,match='threshold|Engagement'):artifacts.load_model(config)


def test_historical_metadata_cannot_be_silently_retagged(tmp_path):
    config,_=artifact_fixture(tmp_path)
    config['label_thresholds']=engagement_thresholds(.7,.4)
    with pytest.raises(ContractError,match='metadata mismatch'):artifacts.load_model(config)


def test_threshold_provenance_is_in_existing_training_diagnostics(monkeypatch,example):
    from api.predictive import publication
    inputs,media,watches,*_=example;inputs['label_thresholds']=engagement_thresholds(.7,.4)
    for event in inputs['snapshot']['events']:watches[str(event['watch_id'])]['source']=event
    rows,_=training_rows(inputs,media,watches,compact=True)
    insert=Mock();monkeypatch.setattr(publication,'insert',insert)
    publication.stage_training(Mock(),rows)
    args=insert.call_args.args;columns=args[2];values=args[3]
    assert values[0][columns.index('diagnostics')].adapted['label_thresholds']==inputs['label_thresholds']


def test_publication_model_metadata_carries_exact_fit_thresholds(tmp_path):
    config,bundle=artifact_fixture(tmp_path,engagement_thresholds(.7,.4))
    inputs=dict(feature_space_id=config['feature_space_id'],contract=config['contract'],contract_hash=config['contract_hash'])
    result=artifacts.model_config(inputs,bundle,config['model_path'],config['model_sha256'],{})
    assert result['label_thresholds']==bundle['label_thresholds']
    assert result['contract_hash']==config['contract_hash']
    assert result['feature_space_id']==config['feature_space_id']


@pytest.fixture
def temporary_settings_database(monkeypatch):
    """Opt-in connection-private table; no public settings or schema writes."""
    import os
    from types import SimpleNamespace
    from api.db.connection import connect_db
    if os.getenv('PLEXINTEL_TEST_TEMP_DB')!='1':pytest.skip('Opt-in connection-private SQL settings fixture')
    conn=connect_db()
    with conn.cursor() as cur:
        cur.execute('''CREATE TEMP TABLE app_settings(key text PRIMARY KEY,raw_value text,source text NOT NULL,
            updated_at timestamptz DEFAULT now(),updated_by text,description text)''')
        cur.execute("INSERT INTO pg_temp.app_settings(key,raw_value,source) VALUES('training.engagement_threshold','.6','fixture')")
    conn.commit()
    monkeypatch.setattr(app_settings,'SETTINGS_TABLE','pg_temp.app_settings')
    # save_settings owns its normal connections; retain this temporary-table
    # session solely for fixture assertions, and close it at fixture teardown.
    proxy=SimpleNamespace(cursor=conn.cursor,commit=conn.commit,close=lambda:None)
    monkeypatch.setattr(app_settings,'connect_db',lambda:proxy)
    try:yield conn
    finally:conn.close()


def test_sql_pair_save_and_reset_use_defaults_without_new_stored_values(temporary_settings_database):
    conn=temporary_settings_database
    app_settings.save_settings(updates=dict(zip(app_settings.ENGAGEMENT_SETTING_KEYS,(.75,.45))),clear_keys=[],updated_by='fixture')
    values=app_settings.resolve_settings(keys=app_settings.ENGAGEMENT_SETTING_KEYS,require_database=True,conn=conn)
    assert configured_engagement_thresholds({k:v.value for k,v in values.items()})==engagement_thresholds(.75,.45)
    app_settings.save_settings(updates={},clear_keys=app_settings.ENGAGEMENT_SETTING_KEYS,updated_by='fixture')
    values=app_settings.resolve_settings(keys=app_settings.ENGAGEMENT_SETTING_KEYS,require_database=True,conn=conn)
    assert configured_engagement_thresholds({k:v.value for k,v in values.items()})==engagement_thresholds()


@pytest.mark.parametrize('key,value',[('training.engagement_threshold',.3),('training.negative_engagement_threshold',.7)])
def test_sql_invalid_partial_edit_preserves_existing_pair(temporary_settings_database,key,value):
    conn=temporary_settings_database
    with pytest.raises(app_settings.SettingsValidationError,match='strictly below'):
        app_settings.save_settings(updates={key:value},clear_keys=[],updated_by='fixture')
    with conn.cursor() as cur:
        cur.execute('SELECT key,raw_value FROM pg_temp.app_settings ORDER BY key')
        assert cur.fetchall()==[('training.engagement_threshold','.6')]
    conn.rollback()
