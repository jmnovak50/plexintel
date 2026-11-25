"""One explicit action retains one budget; no network, encoders or production DB."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock
import numpy as np
import pytest
from api.predictive.contracts import ContractError
from api.predictive.supervision import (allocate, fit_weights, support, atomic_split, unit_key,
    decision_for, POLICY, PROVENANCE, BASE_WEIGHTS, EXPLICIT, AttributionRequired)
from api.predictive.evaluation import probability_metrics
from api.predictive.features import training_plan, chronological_split, show_heldout_plan
from api.predictive.recovery import CanonicalTitles
from tests.test_predictive_identity import example


def outcome(key, *, decision=None, source='watch_history', label=0, day=1, weight=1.):
    stamp=(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=day)).isoformat()
    row=dict(owner='viewer',media_key=str(key),canonical_identity=f'episode:{key}',show_key='show:one',
        label=label,label_source=source,sample_weight=weight,prediction_at=stamp,label_available_at=stamp,
        supervision_weighting=POLICY)
    if decision:row['feedback_decision']=decision
    return row


@pytest.mark.parametrize('source,action',EXPLICIT.items())
@pytest.mark.parametrize('count',[1,10,113,200])
def test_equal_aggregate_base_and_evaluation_support(source,action,count):
    d=dict(id=str(uuid4()),target_scope='show')
    rows=allocate([outcome(i,decision=d,source=source,label=int(action in ('interested','watched_like')),weight=BASE_WEIGHTS[action]) for i in range(count)])
    assert sum(r['sample_weight'] for r in rows)==pytest.approx(BASE_WEIGHTS[action])
    assert support(rows)['decision_equivalent']==pytest.approx(1.)
    # Reallocation after eligibility/filtering still preserves the original budget.
    assert sum(r['sample_weight'] for r in allocate(rows[:max(1,count//2)]))==pytest.approx(BASE_WEIGHTS[action])


def test_class_multiplier_independent_of_expansion_and_type_weight():
    positive=[outcome('p'+str(i),label=1,weight=2.) for i in range(8)]
    for n in (1,10,113):
        rejected=[outcome(i,decision={'id':'decision'},source='explicit_reject',weight=5.) for i in range(n)]
        rows=positive+[outcome('negative',weight=3.)]+rejected
        w=fit_weights(rows)
        assert w[8]==pytest.approx(3.*4.)
        assert w[9:].sum()==pytest.approx(5.*4.)
        assert w[:8].tolist()==[2.]*8


def test_evaluation_uses_support_not_training_significance_and_keeps_raw():
    rows=[outcome(1001,label=1),outcome(1002)]+[outcome(i,decision={'id':'reject'},source='explicit_reject',weight=5.) for i in range(113)]
    result=probability_metrics(rows,[.9,.1]+[.9]*113)
    assert result['decision_equivalent_support']==pytest.approx(3.)
    np.testing.assert_allclose(result['confusion_matrix'],[[1.,1.],[0.,1.]])
    assert result['raw_episode_metrics']['confusion_matrix']==[[1.,113.],[0.,1.]]
    assert result['balanced_accuracy']==pytest.approx(.75)
    assert result['negative_support']==pytest.approx(2.)


def test_decision_spanning_chronological_boundary_is_purged():
    rows=[outcome(i,label=i%2,day=i) for i in range(20)]
    rows += [outcome('a',decision={'id':'shared'},source='explicit_reject',weight=5.,day=1),
             outcome('b',decision={'id':'shared'},source='explicit_reject',weight=5.,day=19)]
    train,test,boundary=chronological_split(rows)
    assert not {unit_key(r) for r in train}&{unit_key(r) for r in test}
    assert not any(r.get('feedback_decision') for r in train+test)
    assert all(r['prediction_at']<boundary.isoformat() for r in train)
    assert all(r['prediction_at']>=boundary.isoformat() for r in test)


def test_no_duplicate_canonical_or_contradictory_decision():
    r=outcome('a',decision={'id':'one'},source='explicit_reject',weight=5.)
    with pytest.raises(ContractError,match='Duplicate canonical'):allocate([r,dict(r,media_key='alias')])
    with pytest.raises(ContractError,match='contradictory'):allocate([r,dict(r,media_key='b',canonical_identity='b',label=1)])


def origin(example,scope='show',action='never_watch'):
    g,m,w,old,live,event=example
    key={'show':'100','season':'101','episode':str(live),'movie':'1'}[scope]
    return dict(version=PROVENANCE,id=str(uuid4()),kind='captured',username='viewer',target_scope=scope,
        target_identity=CanonicalTitles(m).identity(key),action=action,occurred_at='2020-01-02T00:00:00+00:00')


@pytest.mark.parametrize('scope',['show','season','episode'])
def test_provenance_checks_real_hierarchy_and_aliases(example,scope):
    g,m,w,old,live,_=example;d=origin(example,scope)
    f=dict(username='viewer',feedback='never_watch',created_at='2020-01-02T00:00:00+00:00',decision_provenance=d)
    assert decision_for(f,'viewer',str(old),m,CanonicalTitles(m))['id']==d['id']
    f['decision_provenance']=dict(d,target_identity='show:wrong')
    with pytest.raises(ContractError,match='target_mismatch'):decision_for(f,'viewer',str(live),m,CanonicalTitles(m))


def test_ambiguous_episodes_fail_closed_but_recorded_watches_remain_independent(example):
    g,m,w,old,live,event=example;g['supervision_weighting']=POLICY
    # Existing example is watched, therefore explicit retrospective feedback is auxiliary.
    rows,_=training_plan(g,m)
    assert rows and all(r['label_source']=='watch_history' for r in rows)
    g['snapshot']['events']=[event(1,1,1)]
    with pytest.raises(AttributionRequired) as caught:training_plan(g,m)
    assert caught.value.supervision_audit['ambiguous_outcomes']==1
    assert 'viewer' not in str(caught.value)


def test_overlap_partial_eligibility_watched_precedence_and_undo(example):
    g,m,w,old,live,event=example;g['supervision_weighting']=POLICY
    g['snapshot']['events']=[event(1,1,1)]
    shared=origin(example)
    def f(key,d=shared,action='never_watch'):
        return dict(id=int(key),username='viewer',rating_key=key,feedback=action,suppress=True,
            created_at=d['occurred_at'],modified_at=d['occurred_at'],decision_provenance=d)
    # Canonical aliases are collapsed before budget allocation.
    g['snapshot']['feedback']=[f(old),f(live),f(2)]
    rows,_=training_plan(g,m)
    assert len(rows)==2 and sum(r['sample_weight'] for r in rows)==pytest.approx(5.)
    individual=origin(example,'episode','watched_like');individual['occurred_at']='2020-01-03T00:00:00+00:00'
    g['snapshot']['feedback']=[f(old),f(live,individual,'watched_like'),f(2)]
    rows,_=training_plan(g,m)
    assert sorted(r['sample_weight'] for r in rows)==[3.,5.]
    # Undo removes the effective leaf; it does not resurrect overwritten history.
    g['snapshot']['feedback']=[f(2)]
    rows,_=training_plan(g,m)
    assert len(rows)==1 and rows[0]['sample_weight']==5.
    # A real watch controls supervision instead of redistributing it as feedback.
    later=dict(shared,occurred_at='2020-01-05T00:00:00+00:00')
    g['snapshot']['feedback']=[f(old,later),f(live,later),f(2)]
    g['snapshot']['events'].append(event(2,live,4,6000))
    rows,_=training_plan(g,m)
    assert sum(r['sample_weight'] for r in rows if r['label_source']=='explicit_reject')==5.
    assert any(r['label_source']=='watch_history' and r['decision_support']==1 for r in rows)


def test_old_raw_ap_cannot_qualify_new_normalized_model():
    from api.predictive.train import train
    with pytest.raises(ContractError,match='not a comparable'):
        train({'supervision_weighting':POLICY},{},{},[],{},incumbent_ap=.9)


# Real SQL coverage uses the project's existing disposable-database fixture.
from tests.test_predictive_publication import db


def test_feedback_writer_persists_shared_origin_and_replacement_undo(db,monkeypatch):
    from psycopg2.extras import RealDictCursor
    from pathlib import Path
    from api.services import feedback_service as service
    with db.cursor() as cur:
        cur.execute('''ALTER TABLE user_feedback ALTER COLUMN created_at TYPE timestamp without time zone,
            ALTER COLUMN modified_at TYPE timestamp without time zone;
            ALTER TABLE user_feedback ADD COLUMN reason_code text, ADD COLUMN source text,
            ADD COLUMN plex_watchlist_status text, ADD COLUMN plex_watchlist_synced_at timestamp;
            CREATE UNIQUE INDEX feedback_test_pair ON user_feedback(username,rating_key)''')
        cur.execute(Path('api/db/migrations/optional/feedback_decisions/001_decision_provenance.sql').read_text())
        for key,kind,parent in [(100,'show',None),(101,'season',100),(1,'episode',101),(2,'episode',101),(3,'episode',101)]:
            cur.execute('INSERT INTO library(rating_key,title,media_type,plex_guid,parent_rating_key,show_rating_key) VALUES(%s,%s,%s,%s,%s,100)',
                (key,'Anonymous '+kind,kind,f'plex://{kind}/{key}',parent))
    monkeypatch.setattr(service,'seed_feedback_reasons',lambda cur:None)
    def load(cur,key):
        cur.execute('SELECT * FROM library WHERE rating_key=%s',(key,));return cur.fetchone()
    monkeypatch.setattr(service,'ensure_library_guid',load)
    monkeypatch.setattr(service,'load_library_item',load)
    monkeypatch.setattr(service,'remove_from_plex_watchlist',lambda *a:dict(status='fixture'))
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        a=service.record_bulk_feedback(cur,'viewer',100,'never_watch');assert a['updated_count']==3
        cur.execute('SELECT * FROM user_feedback ORDER BY rating_key');initial=cur.fetchall()
        ids={r['decision_provenance']['id'] for r in initial};assert len(ids)==1
        assert len({r['created_at'] for r in initial})==1
        assert initial[0]['created_at']==datetime.fromisoformat(initial[0]['decision_provenance']['occurred_at']).replace(tzinfo=None)
        assert all(r['suppress'] and r['decision_provenance']['target_scope']=='show' for r in initial)
        assert service.record_bulk_feedback(cur,'viewer',101,'never_watch')['updated_count']==0
        cur.execute('SELECT decision_provenance FROM user_feedback');assert {r['decision_provenance']['id'] for r in cur.fetchall()}==ids
        service.record_feedback(cur,'viewer',1,'watched_like')
        a=service.record_bulk_feedback(cur,'viewer',101,'interested')
        assert a['updated_count']==2 and a['skipped_watched_count']==1
        cur.execute('SELECT * FROM user_feedback ORDER BY rating_key');changed=cur.fetchall()
        assert changed[0]['feedback']=='watched_like' and changed[0]['suppress']
        assert changed[0]['decision_provenance']['target_scope']=='episode'
        assert changed[1]['decision_provenance']==changed[2]['decision_provenance']
        assert changed[1]['decision_provenance']['target_scope']=='season' and not changed[1]['suppress']
        assert changed[1]['decision_provenance']['id'] not in ids
        assert service.delete_feedback_row(cur,'viewer',1)['deleted']
        cur.execute('SELECT count(*) AS n FROM user_feedback WHERE rating_key=1');assert cur.fetchone()['n']==0
        cur.execute('SELECT count(*) AS n FROM user_feedback');assert cur.fetchone()['n']==2
    db.rollback()


def test_recovered_origin_retains_unknown_original_time(example):
    g,m,w,old,live,_=example;d=origin(example)
    d.update(kind='operator-confirmed',occurred_at=None,evidence_sha256='a'*64,
        derived_interval=dict(first='2020-01-02T00:00:00+00:00',last='2020-01-03T00:00:00+00:00'))
    f=dict(feedback='never_watch',created_at='2020-01-02T00:00:00+00:00',decision_provenance=d)
    value=decision_for(f,'viewer',str(live),m,CanonicalTitles(m))
    assert value['time_basis']=='latest_retained_derived_time_not_original_action_time'
    assert value['time']=='2020-01-03T00:00:00+00:00'
    d.pop('evidence_sha256')
    with pytest.raises(ContractError,match='explicit_evidence'):decision_for(f,'viewer',str(live),m,CanonicalTitles(m))


def test_independent_episode_and_movie_keep_the_same_base(example):
    g,m,w,old,live,_=example;identity=CanonicalTitles(m)
    for scope,key in [('movie','1'),('episode',str(live)),('season',str(live)),('show',str(live))]:
        d=origin(example,scope)
        feedback=dict(feedback='never_watch',created_at=d['occurred_at'],decision_provenance=d)
        decision=decision_for(feedback,'viewer',key,m,identity)
        assert allocate([outcome(key,decision=decision,source='explicit_reject',weight=5.)])[0]['sample_weight']==5.


def test_duplicate_canonical_across_different_origins_cannot_overwrite_effective_supervision():
    r=outcome(1,decision={'id':'first'},source='explicit_reject',weight=5.)
    with pytest.raises(ContractError,match='Duplicate canonical'):
        allocate([r,dict(r,feedback_decision={'id':'second'})])


def test_comparable_reference_excludes_whole_heldout_decision(monkeypatch):
    import api.predictive.reference as module
    from api.predictive.contracts import utc
    identity=Mock()
    identity.identity.side_effect=lambda key:'episode:'+key
    identity.group.side_effect=lambda key:'show:'+key
    identity.aliases.side_effect=lambda key:{key}
    def feature(*args,**kwargs):
        return dict(embedding=np.zeros(1536),genres=[],directors=[],year=2020,watch_sim=0.,
            dependencies=dict(profile_keys=[],watch_events=[]))
    monkeypatch.setattr(module,'feature_row',feature)
    stamp='2020-01-02T00:00:00+00:00'
    current=[outcome(i,label=i%2,day=1) for i in (1,2)]
    current.append(outcome(3,label=0,day=1,decision={'id':'shared'},source='explicit_reject',weight=5.))
    heldout=[outcome(4,label=0,day=20,decision={'id':'shared'},source='explicit_reject',weight=5.)]
    raw=[dict(username=r['owner'],rating_key=int(r['media_key']),label=r['label'],sample_weight=r['sample_weight'],
        label_source=r['label_source'],feedback_value=None,diagnostics=dict(canonical_identity=r['canonical_identity'],prediction_at=r['prediction_at'],label_available_at=r['label_available_at'],
        feedback_decision=r.get('feedback_decision'),feedback_base_weight=5.)) for r in current]
    # Replacement feedback must not let the reference train on a current held-out
    # canonical user/title outcome under a different historical decision ID.
    raw.append(dict(username='viewer',rating_key=5,label=0,sample_weight=5.,label_source='explicit_reject',feedback_value='never_watch',
        diagnostics=dict(canonical_identity='episode:5',prediction_at=stamp,label_available_at=stamp,
        feedback_decision={'id':'old-action'},feedback_base_weight=5.)))
    heldout.append(outcome(5,day=20,decision={'id':'new-action'},source='explicit_reject',weight=5.))
    reference=dict(config=dict(model_sha256='a'*64,feature_space_id='space',contract_hash='contract',
        fit_settings=dict(seed=42,threshold=.5,n_estimators=100,max_depth=6,learning_rate=.1,subsample=.8,n_jobs=2)),rows=raw)
    fitted,legacy,manifest=module.reference_fit(reference,dict(feature_space_id='space',contract_hash='contract',snapshot={'events':[]}),
        {str(i):{} for i in (1,2,3,5)}, {}, current,utc('2020-01-10T00:00:00+00:00'),set(),identity,heldout)
    assert {r['media_key'] for r in fitted}=={'1','2'}
    assert legacy and manifest['decision_overlap']==0
    assert module.feature_row is feature
    reference['config']['fit_settings']['max_depth']=3
    with pytest.raises(ContractError,match='fit settings'):
        module.reference_fit(reference,dict(feature_space_id='space',contract_hash='contract',snapshot={'events':[]}),
            {str(i):{} for i in (1,2,3)},{},current,utc('2020-01-10T00:00:00+00:00'),set(),identity,heldout)



def test_normalized_rows_cannot_use_an_unversioned_training_gate():
    from api.predictive.train import train
    with pytest.raises(ContractError,match='Mixed supervision'):
        train({}, {}, {}, [outcome(1)], {}, incumbent_ap=.9)


def test_reference_applies_existing_limited_history_eligibility_and_reports_coverage(monkeypatch):
    import api.predictive.reference as module
    from api.predictive.contracts import utc
    identity=Mock()
    identity.identity.side_effect=lambda key:'episode:'+key
    identity.group.side_effect=lambda key:'show:'+key
    identity.aliases.side_effect=lambda key:{key}
    current=[outcome(i,label=i%2) for i in (1,2,3)]
    raw=[dict(username=r['owner'],rating_key=int(r['media_key']),label=r['label'],sample_weight=r['sample_weight'],
        label_source=r['label_source'],feedback_value=None,diagnostics=dict(canonical_identity=r['canonical_identity'],
        prediction_at=r['prediction_at'],label_available_at=r['label_available_at'])) for r in current]
    def feature(inputs,media,watches,events,owner,key,*args,**kwargs):
        if key=='3':return None
        return dict(embedding=np.zeros(1536),genres=[],directors=[],year=2020,watch_sim=0.,dependencies=dict(profile_keys=[],watch_events=[]))
    monkeypatch.setattr(module,'feature_row',feature)
    config=dict(model_sha256='a'*64,feature_space_id='s',contract_hash='c',
        fit_settings=dict(seed=42,threshold=.5,n_estimators=100,max_depth=6,learning_rate=.1,subsample=.8,n_jobs=2))
    rr,legacy,manifest=module.reference_fit(dict(config=config,rows=raw),dict(feature_space_id='s',contract_hash='c',snapshot={'events':[]}),
        {str(i):{} for i in (1,2,3)},{},current,utc('2020-01-10T00:00:00+00:00'),set(),identity,[])
    assert {r['media_key'] for r in rr}=={'1','2'}
    assert manifest['limited_history_skips']==1 and manifest['fit_rows']==2
    # Losing a complete class is still a hard failure, never a bypass.
    monkeypatch.setattr(module,'feature_row',lambda *a,**kw:None)
    with pytest.raises(ContractError,match='lacks both classes'):
        module.reference_fit(dict(config=config,rows=raw),dict(feature_space_id='s',contract_hash='c',snapshot={'events':[]}),
            {str(i):{} for i in (1,2,3)},{},current,utc('2020-01-10T00:00:00+00:00'),set(),identity,[])


@pytest.mark.parametrize('reference_ap,accepted',[(.84,True),(.86,False)])
def test_quality_gate_uses_shared_normalized_reference_with_unchanged_tolerance(monkeypatch,reference_ap,accepted):
    import importlib
    module=importlib.import_module('api.predictive.train')
    fit_rows=[outcome(1,label=0),outcome(2,label=1)]
    heldout=[outcome(3,label=0,day=20),outcome(4,label=1,day=20)]
    from api.predictive.contracts import utc
    boundary=utc('2020-01-10T00:00:00+00:00')
    monkeypatch.setattr(module,'chronological_split',lambda rows:(fit_rows,heldout,boundary))
    monkeypatch.setattr(module,'CanonicalTitles',lambda media:Mock())
    monkeypatch.setattr(module,'show_heldout_plan',lambda *a,**kw:(fit_rows,heldout,set(),{}))
    monkeypatch.setattr(module,'feature_row',lambda *a,**kw:dict(embedding=np.zeros(1536),dependencies={}))
    monkeypatch.setattr(module,'compact_row',lambda value,*args:value)
    monkeypatch.setattr(module,'reference_fit',lambda *a,**kw:(fit_rows,True,{'protocol':'fixture'}))
    measured=Mock(side_effect=[dict(balanced_accuracy=.7,average_precision=.8),dict(balanced_accuracy=.7,average_precision=.8),
        dict(balanced_accuracy=.7,average_precision=reference_ap),dict(balanced_accuracy=.7,average_precision=reference_ap)])
    monkeypatch.setattr(module,'fit_compare',measured)
    vocabulary=Mock(names=[]);vocabulary.specification.return_value={}
    monkeypatch.setattr(module.Vocabulary,'fit',lambda *a,**kw:vocabulary)
    final_fit=Mock();monkeypatch.setattr(module,'fit',final_fit)
    args=(dict(supervision_weighting=POLICY,feature_space_id='s',contract_hash='c',snapshot={'events':[]}),{}, {}, fit_rows+heldout,dict(dataset_hash='d'))
    if accepted:
        bundle,_,evaluation=module.train(*args,reference={'fixture':True},incumbent_ap=.99)
        assert all(evaluation['gates'].values()) and final_fit.call_count==1
        assert bundle['supervision_weighting']==POLICY
    else:
        with pytest.raises(ContractError,match='quality gate') as caught:
            module.train(*args,reference={'fixture':True},incumbent_ap=.99)
        evaluation=caught.value.evaluation
        assert evaluation['gates']['average_precision'] is False
        final_fit.assert_not_called()
    assert evaluation['incumbent_average_precision']==reference_ap
    assert evaluation['historical_incumbent_average_precision_diagnostic']==.99


def test_legacy_reference_movie_remains_attributable_after_feedback_undo(monkeypatch):
    import api.predictive.reference as module
    from api.predictive.contracts import utc
    identity=Mock()
    identity.identity.side_effect=lambda key:('movie:' if key=='3' else 'episode:')+key
    identity.group.side_effect=lambda key:'group:'+key
    identity.aliases.side_effect=lambda key:{key}
    current=[outcome(i,label=i%2) for i in (1,2)]
    raw=[dict(username=r['owner'],rating_key=int(r['media_key']),label=r['label'],sample_weight=r['sample_weight'],
        label_source=r['label_source'],feedback_value=None,diagnostics=dict(canonical_identity=r['canonical_identity'],
        prediction_at=r['prediction_at'],label_available_at=r['label_available_at'])) for r in current]
    raw.append(dict(username='viewer',rating_key=3,label=1,sample_weight=3.,label_source='explicit_watched_like',
        feedback_value='watched_like',diagnostics=dict(canonical_identity='movie:3',prediction_at=current[0]['prediction_at'],label_available_at=current[0]['label_available_at'])))
    monkeypatch.setattr(module,'feature_row',lambda *a,**kw:dict(embedding=np.zeros(1536),genres=[],directors=[],year=2020,watch_sim=0.,dependencies=dict(profile_keys=[],watch_events=[])))
    config=dict(model_sha256='a'*64,feature_space_id='s',contract_hash='c',fit_settings=dict(seed=42,threshold=.5,n_estimators=100,max_depth=6,learning_rate=.1,subsample=.8,n_jobs=2))
    media={str(i):{} for i in (1,2,3)};media['3']={'source':{'metadata':{'media_type':'movie'}}}
    rr,legacy,manifest=module.reference_fit(dict(config=config,rows=raw),dict(feature_space_id='s',contract_hash='c',snapshot={'events':[]}),
        media,{},current,utc('2020-01-10T00:00:00+00:00'),set(),identity,[])
    restored=next(r for r in rr if r['media_key']=='3')
    assert restored['feedback_decision']['kind']=='legacy-published-single-movie'
    assert restored['sample_weight']==3. and restored['decision_support']==1.
    # The same retained row provides no original scope for an episode.
    media['3']['source']['metadata']['media_type']='episode'
    with pytest.raises(ContractError,match='requires reliable decision attribution'):
        module.reference_fit(dict(config=config,rows=raw),dict(feature_space_id='s',contract_hash='c',snapshot={'events':[]}),
            media,{},current,utc('2020-01-10T00:00:00+00:00'),set(),identity,[])
