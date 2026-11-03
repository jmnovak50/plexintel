from datetime import datetime,timedelta,timezone
import numpy as np
import pytest

from api.embedding_generation.contracts import contract,fingerprint,metadata,ContractError,modality_contract
from api.embedding_generation.features import feature_row as build_feature_row,history_before,label_for,Vocabulary,chronological_split,training_rows,ProfileContext
from tests.test_embedding_generation import unit


def feature_row(g,*args,**kwargs):
    return build_feature_row(g,*args,posters=g['_test_posters'],**kwargs)


def fixture_data(encoder):
    g=dict(generation_id='new',contract=contract(encoder),snapshot={})
    g['contract_hash']=fingerprint(g['contract'])
    media={}
    for key,index in [('1',0),('2',1),('3',2)]:
        media[key]=dict(generation_id='new',status='succeeded',embedding=unit(index),input_hash=key,
            source=dict(duration=100000,metadata=metadata(dict(type='movie',title=key,year=2000,duration=100000))))
    watches={k:dict(generation_id='new',status='succeeded',embedding=unit(int(k)-1),input_hash=k) for k in ('1','2','3')}
    def event(k,day,played=80):
        stamp=f'2020-01-{day:02}T00:00:00+00:00'
        return dict(watch_id=int(k),rating_key=int(k),username='u',watched_at=stamp,available_at=stamp,played_seconds=played)
    posters={k:dict(generation_id='new',status='succeeded',embedding=unit(10+int(k)),input_hash='poster-'+k) for k in media}
    g['_test_posters']=posters
    for kind,rows in [('media_text',media),('media_poster',posters),('watch',watches)]:
        for row in rows.values():row.update(kind=kind,modality_contract_hash=fingerprint(modality_contract(g['contract'],kind)))
    return g,media,watches,[event('1',1),event('2',2),event('3',30)]


@pytest.fixture
def encoder():
    from api.embedding_generation.contracts import Encoder
    return Encoder('embeddinggemma-2:latest','a'*64,'740m-q8_0','Q8_0','b'*64)


def test_target_future_and_exact_cutoff_excluded(encoder):
    g,media,watches,events=fixture_data(encoder)
    result=feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')
    assert result['dependencies']['profile_keys']==['1']
    assert result['dependencies']['watch_events']==[['1','1','2020-01-01T00:00:00+00:00']]
    np.testing.assert_array_equal(result['embedding'][:768],unit(1))
    np.testing.assert_array_equal(result['embedding'][1536:],unit(0))
    assert result['watch_sim']==0
    assert feature_row(g,media,watches,events,'u','1','2020-01-02T00:00:00+00:00') is None


def test_unknown_end_time_requires_observation_before_prediction(encoder):
    g,media,watches,events=fixture_data(encoder)
    events[0]['available_at']=None;events[0]['observed_at']='2026-01-01T00:00:00+00:00'
    assert feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00') is None


def test_show_group_exclusion_and_mixed_generation(encoder):
    g,media,watches,events=fixture_data(encoder)
    assert feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00',excluded_keys=['1']) is None
    media['1']['generation_id']='legacy'
    with pytest.raises(ContractError):feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')


def test_watch_generation_cannot_differ(encoder):
    g,media,watches,events=fixture_data(encoder)
    watches['1']['generation_id']='legacy'
    with pytest.raises(ContractError):feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')


def test_label_threshold_and_revisit_rule_preserved():
    events=[dict(played_seconds=60,watched_at='2020-01-01T00:00:00+00:00')]
    assert label_for(events,None,100,'movie','2020-02-01T00:00:00+00:00')==(1,1.5,'watch_history')
    events=[dict(played_seconds=600,watched_at='2020-01-01T00:00:00+00:00')]
    assert label_for(events,None,6000,'movie','2020-01-10T00:00:00+00:00') is None
    assert label_for(events,None,6000,'movie','2020-02-01T00:00:00+00:00')==(0,1.5,'watch_history')
    assert label_for([],dict(feedback='never_watch'),None,'movie','2020-02-01T00:00:00+00:00')==(0,5.,'explicit_reject')


def test_train_fold_vocabulary_and_order():
    train=[dict(genres=['known'],directors=['director'],year=2000,poster_missing=False,embedding=[0.]*2304,watch_sim=.3)]
    heldout=[dict(genres=['new'],directors=['new'],year=2030,poster_missing=False,embedding=[0.]*2304,watch_sim=.2)]
    vocab=Vocabulary.fit(train)
    assert vocab.names[:2304]==[f'{group}_{i}' for group in ('media_text','media_poster','user') for i in range(768)]
    assert 'genre_new' not in vocab.names and 'decade_2030' not in vocab.names
    values=vocab.transform(heldout)
    assert values[0,2304:-2].sum()==0 and values[0,-2]==pytest.approx(.2)


def test_chronological_labels_must_be_available_before_train_boundary():
    base=datetime(2020,1,1,tzinfo=timezone.utc)
    rows=[dict(prediction_at=(base+timedelta(days=i)).isoformat(),
        label_available_at=(base+timedelta(days=i+1)).isoformat(),label=i%2) for i in range(30)]
    rows[2]['label_available_at']='2025-01-01T00:00:00+00:00'
    train,test,boundary=chronological_split(rows)
    assert rows[2] not in train
    assert all(datetime.fromisoformat(r['label_available_at'])<boundary for r in train)
    assert all(datetime.fromisoformat(r['prediction_at'])>=boundary for r in test)


def test_training_serving_same_builder_at_same_snapshot(encoder):
    g,media,watches,events=fixture_data(encoder)
    first=feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')
    second=feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')
    np.testing.assert_array_equal(first['embedding'],second['embedding'])
    assert first['dependencies']==second['dependencies']


def test_cached_context_matches_direct_target_excluded_arithmetic(encoder):
    g,media,watches,events=fixture_data(encoder)
    cutoff='2021-01-01T00:00:00+00:00'
    context=ProfileContext(g,media,watches,events,'u',cutoff)
    for key in media:
        result=feature_row(g,media,watches,events,'u',key,cutoff,context=context)
        expected=np.mean([unit(int(k)-1) for k in media if k!=key],axis=0)
        np.testing.assert_allclose(result['embedding'][1536:],expected)
        assert result['watch_sim']==pytest.approx(0.)
        assert len(result['dependencies']['watch_events'])==2
    with pytest.raises(ContractError):feature_row(g,media,watches,events,'u','2',cutoff,context=context,excluded_keys=['1'])
