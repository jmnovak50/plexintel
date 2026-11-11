"""Anonymized versions of the two retired-key episode patterns; no real I/O."""
import io
from unittest.mock import Mock

import joblib
import numpy as np
import pytest

from api.predictive.contracts import (
    ContractError, specification, fingerprint, metadata, modality_contract,
)
from api.predictive.features import (
    ProfileContext, chronological_split, feature_row, training_rows,
    unseen_candidate_keys, training_plan, show_heldout_plan, SUPERVISION_POLICY, Vocabulary,
)
from api.predictive.io import SourceError
from api.predictive.recovery import (
    CanonicalTitles, IdentityError, IDENTITY_POLICY, POLICY, Resolver, stable_identity,
)
def unit(n=0):
    result=[0.0]*768;result[n]=1.0
    return result


@pytest.fixture(params=[(36296, 36298, 2, 13), (38257, 38259, 3, 4)])
def example(request):
    old, live, season, episode = request.param
    guid = f'plex://episode/anonymous-{season}-{episode}'
    show = dict(ratingKey='100', type='show', title='Anonymous series', guid='plex://show/example')
    parent = dict(ratingKey='101', type='season', title='Anonymous season',
                  guid=f'plex://season/example-{season}', parentRatingKey='100', index=season)
    raw = dict(ratingKey=str(live), type='episode', title='Anonymous episode', guid=guid,
               parentRatingKey='101', grandparentRatingKey='100', parentIndex=season,
               index=episode, duration=6000000, year=2020)
    sources = {
        '100': dict(rating_key=100, media_type='show', plex_guid=show['guid']),
        '101': dict(rating_key=101, media_type='season', plex_guid=parent['guid'],
                    show_rating_key=100, parent_rating_key=100, season_number=season),
    }
    for key in (old, live):
        sources[str(key)] = dict(rating_key=key, media_type='episode', plex_guid=guid,
                                parent_rating_key=101, show_rating_key=100,
                                season_number=season, episode_number=episode, duration=6000000)
    plex = Mock()
    def read(key):
        if int(key) == old:
            raise SourceError('HTTP_404')
        return {'100': show, '101': parent, str(live): raw}[str(key)]
    plex.metadata.side_effect = read
    plex.catalog.return_value = iter([show, parent, raw])
    value, _, origin = Resolver(plex, sources, {}).payload(sources[str(old)])
    sources[str(old)].update(metadata=value, metadata_origin=origin,
        _metadata_recovery=dict(policy=POLICY, reason='Fixture verified replacement',
                                approved_at='2020-02-01T00:00:00+00:00'))
    sources[str(live)]['metadata'] = metadata(raw, show, parent)
    sources['100']['metadata'] = metadata(show)
    sources['101']['metadata'] = metadata(parent, show)
    sources['1'] = dict(rating_key=1, media_type='movie', plex_guid='plex://movie/independent',
                       duration=6000000, metadata=metadata(dict(type='movie', title='Other title', duration=6000000)))
    other = dict(raw, ratingKey='2', guid='plex://episode/different', index=episode+1, title='Different episode')
    sources['2'] = dict(sources[str(live)], rating_key=2, plex_guid=other['guid'],
                        episode_number=episode+1, metadata=metadata(other, show, parent))
    spec = specification(dict(name='embeddinggemma-2:latest',digest='a'*64))
    generation = dict(feature_space_id='fixture', contract=spec, contract_hash=fingerprint(spec))
    media = {key: dict(feature_space_id='fixture', kind='media_text', status='succeeded',
                       modality_contract_hash=fingerprint(modality_contract(spec, 'media_text')),
                       input_hash=key, embedding=unit(0 if key in (str(old), str(live)) else 1), source=source)
             for key, source in sources.items()}
    def event(ident, key, day, played=4800):
        stamp=f'2020-01-{day:02}T00:00:00+00:00'
        return dict(watch_id=ident, rating_key=key, username='viewer', watched_at=stamp,
                    verified_started_at=stamp, available_at=f'2020-01-{day:02}T01:00:00+00:00',
                    played_seconds=played, percent_complete=80 if played==4800 else 10)
    events=[event(1,1,1),event(2,live,3),event(3,old,5)]
    watches={str(e['watch_id']): dict(feature_space_id='fixture', kind='watch', status='succeeded',
                modality_contract_hash=fingerprint(modality_contract(spec,'watch')), input_hash=str(e['watch_id']),
                embedding=unit(1 if e['rating_key']==1 else 0)) for e in events}
    feedback=[dict(username='viewer',rating_key=old,feedback='watched_like',suppress=True,
                   created_at='2020-01-06T00:00:00+00:00',modified_at='2020-01-06T00:00:00+00:00')]
    generation['snapshot']=dict(events=events,feedback=feedback,as_of='2020-03-01T00:00:00+00:00')
    return generation,media,watches,old,live,event


def test_reuses_exact_recovery_mapping_and_keeps_episode_granularity(example):
    g,m,w,old,live,_=example
    identities=CanonicalTitles(m)
    assert identities.aliases(old)=={str(old),str(live)}
    assert identities.representative(old)==str(live)
    assert identities.identity(old)!=identities.identity('2')
    assert identities.group(old)==identities.group('2')==identities.identity('100')
    assert stable_identity('movie','tmdb://123')!=stable_identity('episode','tmdb://123')
    with pytest.raises(IdentityError):stable_identity('episode','plex://show/example')


def test_first_exposure_consolidates_multiple_watches_and_ignores_retired_key_feedback(example):
    g,m,w,old,live,_=example
    rows,skips=training_rows(g,m,w)
    targets=[r for r in rows if r['media_key']==str(live)]
    assert len(targets)==1
    row=targets[0]
    assert row['label_source']=='watch_history' and row['feedback_value'] is None
    assert row['prediction_at']=='2020-01-03T00:00:00+00:00'
    assert row['label_available_at']=='2020-01-05T01:00:00+00:00'
    assert row['dependencies']['target_aliases']==sorted([str(old),str(live)])
    assert row['identity_policy']==row['dependencies']['identity_policy']==IDENTITY_POLICY
    assert row['dependencies']['profile_keys']==['1']
    assert row['dependencies']['watch_events']==[['1','1','2020-01-01T01:00:00+00:00']]
    assert skips['recorded_watch_feedback_auxiliary']==1
    assert row['observation_kind']=='first_recorded_watch'


def test_no_cross_alias_media_or_watch_contribution_in_reused_context(example):
    g,m,w,old,live,_=example
    cutoff='2020-02-01T00:00:00+00:00'
    context=ProfileContext(g,m,w,g['snapshot']['events'],'viewer',cutoff)
    a=feature_row(g,m,w,g['snapshot']['events'],'viewer',old,cutoff,context=context)
    b=feature_row(g,m,w,g['snapshot']['events'],'viewer',live,cutoff,context=context)
    for row in (a,b):
        np.testing.assert_array_equal(row['embedding'][768:],unit(1))
        assert row['watch_sim']==pytest.approx(0.)
        assert row['history_titles']==1
        assert len(row['dependencies']['watch_events'])==1
    # Qualifying media aggregates use one vector per canonical title, not per alias.
    assert len(context.keys)==2 and context.watch_count==3
    w['2'].update(embedding=unit(4),input_hash='changed')
    w['3'].update(embedding=unit(5),input_hash='changed-again')
    c=feature_row(g,m,w,g['snapshot']['events'],'viewer',old,cutoff)
    np.testing.assert_array_equal(a['embedding'],c['embedding'])
    assert a['watch_sim']==c['watch_sim']
    assert feature_row(g,m,w,g['snapshot']['events'],'viewer',live,cutoff,excluded_keys=['1']) is None


def test_alias_watched_and_suppressed_candidates_are_removed_without_suppressing_siblings(example):
    g,m,w,old,live,_=example
    keys=unseen_candidate_keys(m,g['snapshot']['events'],[],'viewer')
    assert str(old) not in keys and str(live) not in keys and '2' in keys
    # The same rule works when the only watch is on the retired key.
    assert str(live) not in unseen_candidate_keys(m,[g['snapshot']['events'][2]],[],'viewer')
    # Preserve partial-watch behavior (< 0.5); suppress feedback crosses aliases.
    partial=dict(g['snapshot']['events'][1],played_seconds=600,percent_complete=10)
    assert str(live) in unseen_candidate_keys(m,[partial],[],'viewer')
    assert str(live) not in unseen_candidate_keys(m,[partial],g['snapshot']['feedback'],'viewer')


@pytest.mark.parametrize('feedback,label,weight,source', [
    ('interested',1,.75,'explicit_interest'),('never_watch',0,5.,'explicit_reject'),
    ('watched_like',1,3.,'explicit_watched_like'),('watched_dislike',0,5.,'explicit_watched_dislike')])
def test_feedback_without_history_policy(example,feedback,label,weight,source):
    g,m,w,old,live,_=example
    g['snapshot']['events']=g['snapshot']['events'][:1]
    g['snapshot']['feedback'][0].update(feedback=feedback)
    rows,skips=training_rows(g,m,w)
    targets=[r for r in rows if r['media_key']==str(live)]
    assert len(targets)==1
    row=targets[0]
    assert row['prediction_at']=='2020-01-06T00:00:00+00:00'
    assert (row['label'],row['sample_weight'],row['label_source'])==(label,weight,source)
    assert row['observation_kind']==('retrospective_explicit_feedback' if feedback.startswith('watched') else 'pre_viewing_intent')
    assert row['supervision_policy']==SUPERVISION_POLICY
    assert row['feedback_provenance']=='predates_four_state_source'


def test_pre_watch_feedback_and_negative_maturity_preserved(example):
    g,m,w,old,live,_=example
    g['snapshot']['feedback'][0].update(feedback='interested',created_at='2020-01-02T00:00:00+00:00',
                                       modified_at='2020-01-02T00:00:00+00:00')
    rows,_=training_rows(g,m,w)
    row=next(r for r in rows if r['media_key']==str(live))
    assert row['label_source']=='explicit_interest' and row['prediction_at']=='2020-01-02T00:00:00+00:00'
    g['snapshot']['feedback']=[]
    for e in g['snapshot']['events'][1:]:e['played_seconds']=600
    g['snapshot']['as_of']='2020-01-10T00:00:00+00:00'
    assert not any(r['media_key']==str(live) for r in training_rows(g,m,w)[0])
    g['snapshot']['as_of']='2020-03-01T00:00:00+00:00'
    row=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    assert row['label']==0 and row['label_available_at']=='2020-01-19T00:00:00+00:00'


@pytest.mark.parametrize('failure',['missing_guid','wrong_kind','conflicting_number','missing_destination','tampered_origin'])
def test_uncertain_identity_quarantines_alias_group_and_fails_closed(example,failure):
    g,m,w,old,live,_=example
    if failure=='missing_guid':m[str(live)]['source']['plex_guid']=None
    elif failure=='wrong_kind':m[str(live)]['source']['plex_guid']='plex://show/example'
    elif failure=='conflicting_number':m[str(live)]['source']['metadata']['episode_number']+=1
    elif failure=='missing_destination':del m[str(live)]
    else:m[str(old)]['source']['metadata_origin']['raw_inputs']['media']['guid']='plex://episode/tampered'
    identities=CanonicalTitles(m)
    with pytest.raises(IdentityError):identities.identity(old)
    with pytest.raises(IdentityError):unseen_candidate_keys(m,g['snapshot']['events'],[],'viewer',identities)
    with pytest.raises(IdentityError):feature_row(g,m,w,g['snapshot']['events'],'viewer',old,'2020-02-01T00:00:00+00:00')
    rows,skips=training_rows(g,m,w)
    assert not any(r['media_key'] in (str(old),str(live)) for r in rows)
    assert skips['unresolved_identity']>=1


def test_unknown_other_history_cannot_be_silently_dropped(example):
    g,m,w,old,live,event=example
    g['snapshot']['events'].append(event(99,999,2))
    rows,skips=training_rows(g,m,w)
    assert not any(r['media_key']==str(live) for r in rows)
    assert skips['unresolved_history_identity']>=1


def test_group_exclusions_expand_aliases_and_chronology_rejects_duplicate_outcomes(example):
    g,m,w,old,live,_=example
    identities=CanonicalTitles(m)
    assert identities.expand([old])=={str(old),str(live)}
    context=ProfileContext(g,m,w,g['snapshot']['events'],'viewer','2020-02-01T00:00:00+00:00',excluded_keys=[old])
    assert context.keys==['1'] and context.watch_count==1
    with pytest.raises(ContractError,match='Duplicate canonical'):
        chronological_split([dict(owner='viewer',canonical_identity=identities.identity(old))]*10)






def test_retrospective_submission_cutoff_and_modified_label_availability(example):
    g,m,w,old,live,event=example
    g['snapshot']['events']=g['snapshot']['events'][:1]+[event(4,2,10)]
    w['4']=dict(w['1'],input_hash='future',embedding=unit(7))
    g['snapshot']['feedback'][0]['modified_at']='2020-02-05T00:00:00+00:00'
    plan,skips=training_plan(g,m)
    fields=next(r for r in plan if r['media_key']==str(live))
    row=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    assert all(row[key]==value for key,value in fields.items())
    assert row['prediction_at']=='2020-01-06T00:00:00+00:00'
    assert row['label_available_at']=='2020-02-05T00:00:00+00:00'
    assert row['dependencies']['profile_keys']==['1']
    assert row['dependencies']['watch_events']==[['1','1','2020-01-01T01:00:00+00:00']]
    assert row['watch_sim']==0.
    # Do not train on a label whose current state became available after boundary.
    others=[dict(owner='other',canonical_identity=str(n),prediction_at=f'2020-01-{10+n:02}T00:00:00+00:00',
                 label_available_at=f'2020-01-{10+n:02}T01:00:00+00:00',label=n%2) for n in range(10)]
    train,test,boundary=chronological_split([fields]+others)
    assert fields not in train and fields not in test


def test_feedback_updates_choose_latest_canonical_state_without_duplicate_outcomes(example):
    g,m,w,old,live,_=example
    g['snapshot']['events']=g['snapshot']['events'][:1]
    old_state=g['snapshot']['feedback'][0]
    latest=dict(old_state,rating_key=live,feedback='watched_dislike',
                created_at='2020-01-10T00:00:00+00:00',modified_at='2020-01-12T00:00:00+00:00')
    g['snapshot']['feedback'].append(latest)
    rows,_=training_rows(g,m,w)
    targets=[r for r in rows if r['media_key']==str(live)]
    assert len(targets)==1
    assert targets[0]['label']==0 and targets[0]['sample_weight']==5.
    assert targets[0]['prediction_at']==latest['created_at']
    assert targets[0]['label_available_at']==latest['modified_at']
    latest.update(feedback='watched_like',created_at='2020-01-15T00:00:00+00:00',modified_at='2020-01-15T00:00:00+00:00')
    target=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    assert target['label']==1 and target['prediction_at']==latest['created_at']
    # Equal availability with contradictory alias states cannot be tie-broken by key.
    old_state.update(feedback='watched_dislike',modified_at=latest['modified_at'])
    rows,skips=training_rows(g,m,w)
    assert not any(r['media_key']==str(live) for r in rows)
    assert skips['conflicting_latest_feedback']==1


@pytest.mark.parametrize('change',[
    {'created_at':None},{'created_at':'invalid'},{'created_at':'2020-01-06'},
    {'modified_at':'2020-01-05T00:00:00+00:00'},
    {'modified_at':'2021-01-01T00:00:00+00:00'},
])
def test_invalid_or_unavailable_feedback_time_quarantines_pair(example,change):
    g,m,w,old,live,_=example
    g['snapshot']['events']=g['snapshot']['events'][:1]
    g['snapshot']['feedback'][0].update(change)
    rows,skips=training_rows(g,m,w)
    assert not any(r['media_key']==str(live) for r in rows)
    assert skips['invalid_feedback_time']==1


def test_watched_declaration_before_recorded_watch_retains_watch_and_conflict_diagnostic(example):
    g,m,w,old,live,_=example
    g['snapshot']['feedback'][0].update(feedback='watched_dislike',created_at='2020-01-02T00:00:00+00:00',
                                       modified_at='2020-01-02T00:00:00+00:00')
    row=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    assert (row['label'],row['sample_weight'],row['label_source'])==(1,2.,'watch_history')
    assert row['prediction_at']=='2020-01-03T00:00:00+00:00'
    assert row['auxiliary_feedback_conflicts']==1 and row['auxiliary_feedback_count']==1
    for event in g['snapshot']['events'][1:]:event['played_seconds']=1200
    assert not any(r['media_key']==str(live) for r in training_rows(g,m,w)[0])


def test_retrospective_diagnostics_never_enter_predictors_and_plan_needs_no_vectors(example):
    g,m,w,old,live,_=example
    g['snapshot']['events']=g['snapshot']['events'][:1]
    row=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    vocab=Vocabulary.fit([row],include_poster=False)
    original=vocab.transform([row])
    changed=dict(row,observation_kind='anything',feedback_provenance='anything',
                 auxiliary_feedback_conflicts=999,supervision_policy='anything',label_source='anything')
    np.testing.assert_array_equal(original,vocab.transform([changed]))
    for item in m.values():item.pop('embedding')
    assert any(r['media_key']==str(live) for r in training_plan(g,m)[0])




def quarantine_example(example,coordinates=(4,24),key='14808'):
    from copy import deepcopy
    from api.predictive.eligibility_quarantine import FRIENDS_IDENTITY
    g,m,w,old,live,event=example
    m['100']['source']['plex_guid']=FRIENDS_IDENTITY[len('show:'):]
    uncertain=deepcopy(m[str(live)])
    uncertain['source'].update(rating_key=int(key),plex_guid='local://'+key,
                               season_number=coordinates[0],episode_number=coordinates[1])
    uncertain['source']['metadata'].update(season_number=coordinates[0],episode_number=coordinates[1])
    m[key]=uncertain
    outside=deepcopy(m['1']);outside.update(input_hash='outside',embedding=unit(4))
    outside['source'].update(rating_key=3,plex_guid='plex://movie/outside')
    m['3']=outside
    f=dict(g['snapshot']['feedback'][0],rating_key=int(key))
    g['snapshot']['feedback']=[f]
    return g,m,w,old,live,event


@pytest.mark.parametrize('key,coordinates',[
    ('14808',(4,24)),('14833',(5,24)),('14858',(6,24)),('14859',(6,25)),
    ('14884',(7,24)),('14909',(8,24)),('14934',(9,24)),('14953',(10,18)),
])
def test_audited_series_quarantine_contains_candidates_and_profiles_without_resolving_episode(example,key,coordinates):
    from api.predictive.eligibility_quarantine import FRIENDS_IDENTITY,profile_exclusions
    g,m,w,old,live,_=quarantine_example(example,coordinates,key)
    identities=CanonicalTitles(m);scopes=set()
    with pytest.raises(IdentityError):identities.identity(key)
    assert unseen_candidate_keys(m,g['snapshot']['events'],g['snapshot']['feedback'],'viewer',identities,
                                 quarantined_groups=scopes)==['3']
    assert scopes=={FRIENDS_IDENTITY}
    assert identities.identity(old)!=identities.identity('2')
    excluded=profile_exclusions(identities,scopes)
    context=ProfileContext(g,m,w,g['snapshot']['events'],'viewer','2020-02-01T00:00:00+00:00',
                           excluded_keys=excluded,identity=identities)
    assert context.keys==['1'] and context.watch_count==1
    rows,skips=training_rows(g,m,w)
    assert not any(r['media_key']==key for r in rows) and skips['unresolved_identity']==1


@pytest.mark.parametrize('failure',['other_key','wrong_coordinates','wrong_show','unknown_show','wrong_guid','unknown_watch','bad_origin'])
def test_series_containment_does_not_allow_other_uncertainty(example,failure):
    g,m,w,old,live,event=quarantine_example(example)
    source=m['14808']['source']
    if failure=='other_key':
        source.update(rating_key=999,plex_guid='local://999');m['999']=m.pop('14808')
        g['snapshot']['feedback'][0]['rating_key']=999
    elif failure=='wrong_coordinates':source['metadata']['episode_number']=23
    elif failure=='wrong_show':m['100']['source']['plex_guid']='plex://show/other'
    elif failure=='unknown_show':source['show_rating_key']=999
    elif failure=='wrong_guid':source['plex_guid']='local://elsewhere'
    elif failure=='unknown_watch':g['snapshot']['events'].append(event(99,14808,2))
    else:source['metadata_origin']={'invalid':True}
    with pytest.raises(IdentityError):unseen_candidate_keys(m,g['snapshot']['events'],g['snapshot']['feedback'],'viewer')




def test_show_plan_excludes_every_held_group_alias_and_preserves_supervision_diagnostics(example):
    from copy import deepcopy
    from api.predictive.contracts import utc
    g,m,w,old,live,event=example
    for key in ('3','4'):
        m[key]=deepcopy(m['1'])
        m[key]['source'].update(rating_key=int(key),plex_guid='plex://movie/held-alias')
    identities=CanonicalTitles(m)
    rows=[];g['snapshot']['events']=[]
    for n in range(20):
        owner='viewer'+str(n);key=str(live) if n%2 else '3'
        g['snapshot']['events'].append(dict(event(n+10,1,1),username=owner))
        rows.append(dict(owner=owner,media_key=key,canonical_identity=identities.identity(key),
            show_key=identities.group(key),label=(n//2)%2,label_source='explicit_watched_like',
            observation_kind='retrospective_explicit_feedback',feedback_provenance='predates_four_state_source',
            prediction_at=f'2020-01-{n+3:02}T00:00:00+00:00',label_available_at=f'2020-01-{n+3:02}T01:00:00+00:00'))
    fit,validation,excluded,skips=show_heldout_plan(g,m,rows,identity=identities)
    held={identities.group(k) for k in excluded}
    assert fit and validation and skips=={}
    assert all(r['show_key'] not in held for r in fit)
    assert all(r['show_key'] in held for r in validation)
    assert all(identities.aliases(k)<=excluded for k in excluded)
    assert all(r['observation_kind']=='retrospective_explicit_feedback' for r in fit+validation)


def test_evaluation_reports_supervision_segments_without_real_classifier(example):
    from api.predictive.evaluation import evaluate
    g,m,w,old,live,_=example
    g['snapshot']['events']=g['snapshot']['events'][:1]
    row=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    rows=[row,dict(row,owner='other',label=0,label_source='watch_history',
                   observation_kind='first_recorded_watch',feedback_provenance='none')]
    vocab=Vocabulary.fit(rows,include_poster=False)
    classifier=Mock();classifier.predict_proba.return_value=np.asarray([[.2,.8],[.8,.2]])
    booster=classifier.get_booster.return_value
    booster.predict.return_value=np.zeros((len(rows),len(vocab.names)+1));booster.get_score.return_value={}
    result=evaluate(classifier,vocab,rows)
    assert result['supervision_segments']['observation_kind']['retrospective_explicit_feedback']['rows']==1
    assert result['supervision_segments']['label_source']['watch_history']['negative']==1
    assert result['supervision_segments']['feedback_provenance']['predates_four_state_source']['positive']==1






def test_alias_feedback_changed_after_viewing_cannot_be_backdated(example):
    g,m,w,old,live,_=example
    g['snapshot']['feedback'][0].update(feedback='never_watch',created_at='2020-01-02T00:00:00+00:00')
    row=next(r for r in training_rows(g,m,w)[0] if r['media_key']==str(live))
    assert row['label_source']=='watch_history' and row['prediction_at']=='2020-01-03T00:00:00+00:00'


def test_future_alias_watch_never_enters_earlier_history(example):
    g,m,w,old,live,_=example
    cutoff='2020-01-04T00:00:00+00:00'
    row=feature_row(g,m,w,g['snapshot']['events'],'viewer','2',cutoff)
    assert [event[0] for event in row['dependencies']['watch_events']]==['1','2']
    assert '3' not in [event[0] for event in row['dependencies']['watch_events']]
