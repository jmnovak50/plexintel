from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from PIL import Image
import pytest

from api.embedding_generation.contracts import (
    ContractError, Encoder, MEDIA_VERSION, WATCH_VERSION, canonical, contract,
    fingerprint, media_text, metadata, same_generation, vector, watch_text,
)
from api.embedding_generation.io import Ollama, Plex, SourceError, preprocess
from api.embedding_generation.backfill import qualifying_profiles


def unit(n=0):
    result=[0.0]*768;result[n]=1.0
    return result


@pytest.fixture
def encoder():
    return Encoder('embeddinggemma-2:latest','a'*64,'embeddinggemma-2:740m-q8_0','Q8_0','b'*64)


@pytest.fixture
def movie():
    return dict(ratingKey='1',type='movie',title=' A  Film ',originalTitle='Original',year=2000,
        duration=90000,summary='Plot',Genre=[{'tag':'Drama'},{'tag':'Comedy'}],
        Role=[{'tag':'Second','order':2},{'tag':'First','order':1}],Director=[{'tag':'Director'}],
        Writer=[{'tag':'Writer'}],Creator=[{'tag':'Creator'}],studio='Studio',
        ProductionCompany=[{'tag':'Company'}],tagline='Tagline',contentRating='PG',Country=[{'tag':'US'}],
        originalLanguage='en',Collection=[{'tag':'Franchise'}],rating=9.8,audienceRating=9.9,
        Media=[{'Part':[{'Stream':[{'streamType':2,'languageCode':'fr'}]}]}],thumb='/library/metadata/1/thumb/1')


@pytest.mark.parametrize('kind',['movie','show','season','episode'])
def test_explicit_type_and_tv_context(movie,kind):
    show={**movie,'type':'show','title':'Series'}
    raw={**movie,'type':kind,'parentIndex':3,'index':4}
    result=metadata(raw,show)
    assert result['media_type']==kind
    assert result['title']=='A Film'
    if kind in ('episode','season'):assert result['show_context']['title']=='Series'
    if kind=='episode':
        assert result['season_number']==3 and result['episode_number']==4
        assert result['episode_title']=='A Film' and result['episode_synopsis']=='Plot'


def test_full_fields_and_stable_text(movie):
    value=metadata(movie)
    assert value['cast']==['First','Second']
    assert value['runtime_minutes']==1.5
    assert value['genres']==['Comedy','Drama']
    for field in ('original_title','synopsis','writers','creators','studio','production_companies',
                  'tagline','content_rating','countries','original_language','collections','audio_languages'):
        assert value[field]
    assert 'rating' not in value and 'audienceRating' not in value
    assert media_text(value).startswith(MEDIA_VERSION+'\n')
    assert media_text(metadata(dict(reversed(list(movie.items())))))==media_text(value)


def test_cast_limit_and_missing_metadata(movie):
    movie['Role']=[{'tag':f'Actor {i}','order':i} for i in range(25)]
    assert len(metadata(movie)['cast'])==20
    value=metadata(dict(type='movie',title='No plot'))
    assert value['synopsis'] is None and value['year'] is None and value['cast']==[]
    assert value['original_language'] is None
    with pytest.raises(ContractError):metadata(dict(type='episode',title='Episode'))
    with pytest.raises(ContractError):metadata(dict(type='movie'))


def test_partial_missing_credit_order_preserves_returned_order(movie):
    movie['Role']=[{'tag':'Unknown first','order':None},{'tag':'Unknown second'},
                   {'tag':'Credited','order':'1'}]
    assert metadata(movie)['cast']==['Credited','Unknown first','Unknown second']


def test_watch_text_omits_identity_and_poster(movie):
    event=dict(username='PRIVATE_PERSON',played_seconds=300,percent_complete=50,watch_id=123,
               ip_address='PRIVATE_IP',session_id='PRIVATE_SESSION')
    text=watch_text(event,metadata(movie))
    assert text.startswith(WATCH_VERSION+'\n') and '300' in text and '50' in text
    for banned in ('PRIVATE','watch_id','poster','rating'):assert banned not in text.replace('content_rating','contentCertification')


@pytest.mark.parametrize('bad',[[1.0]*767,[float('nan')]*768,[float('inf')]*768,[0.0]*768])
def test_invalid_vectors_rejected(bad):
    with pytest.raises(ContractError):vector(bad)


def test_generation_and_digest_guards(encoder):
    assert encoder.reference=='sha256:'+'a'*64
    with pytest.raises(ContractError):replace(encoder,name='embeddinggemma')
    with pytest.raises(ContractError):replace(encoder,digest='latest')
    with pytest.raises(ContractError):same_generation(
        dict(generation_id='a',contract_hash='same',status='succeeded'),
        dict(generation_id='b',contract_hash='same',status='succeeded'))
    with pytest.raises(ContractError):same_generation(
        dict(generation_id='a',contract_hash='same',status='pending'))


def image_bytes(fmt='JPEG'):
    out=BytesIO();Image.new('RGB',(100,200),'blue').save(out,format=fmt);return out.getvalue()


def test_image_preprocessing_deterministic():
    a,size=preprocess(image_bytes(),'image/jpeg')
    assert size==(100,200) and a==preprocess(image_bytes(),'image/jpeg')[0]
    assert Image.open(BytesIO(a)).format=='PNG'
    with pytest.raises(SourceError):preprocess(image_bytes(),'text/html')
    with pytest.raises(SourceError):preprocess(image_bytes(),'image/png')
    with pytest.raises(SourceError):preprocess(b'broken','image/jpeg')


def test_poster_fallback_and_tv_hierarchy(tmp_path,movie):
    client=Plex('http://plex.test','private',tmp_path)
    movie={**movie,'type':'episode','grandparentRatingKey':'3','parentRatingKey':'2'}
    show={**movie,'ratingKey':'3','type':'show','thumb':'/library/metadata/3/thumb/1'}
    season={**movie,'ratingKey':'2','type':'season','thumb':'/library/metadata/2/thumb/1'}
    client.metadata=Mock(side_effect=lambda k:{'3':show,'2':season}[str(k)])
    response=Mock(status_code=200,headers={'Content-Type':'image/jpeg'},iter_content=lambda n:[image_bytes()])
    client.session.request=Mock(return_value=response)
    poster=client.poster(movie)
    assert poster.provenance['state']=='available' and poster.provenance['source_key']==3
    assert len(list(tmp_path.glob('*.png')))==1
    client.poster(movie)
    assert len(list(tmp_path.glob('*.png')))==1
    show.pop('thumb');season.pop('thumb');movie.pop('thumb')
    assert client.poster(movie).provenance['state']=='missing_art'


def test_no_credential_redirect_or_untrusted_poster(tmp_path,movie):
    client=Plex('http://plex.test','private',tmp_path)
    movie['thumb']='https://other.test/image'
    with pytest.raises(SourceError):client.poster(movie)


def test_ollama_independent_payloads_and_output_identity(encoder):
    session=Mock()
    session.request.return_value=Mock(status_code=200,json=lambda:dict(
        model=encoder.reference,embeddings=[unit()],total_duration=100,load_duration=10,prompt_eval_count=15))
    client=Ollama('http://ollama.test',encoder,session)
    result,timing=client.embed('Canonical metadata')
    payload=session.request.call_args.kwargs['json']
    assert payload['model']==encoder.reference and payload['truncate'] is False
    assert payload['options']['num_thread']==16 and 'num_thread' not in {k:v for k,v in payload.items() if k!='options'}
    assert set(payload['input'])=={'text'}
    client.embed(poster=b'actual-image')
    assert set(session.request.call_args.kwargs['json']['input'])=={'image'}
    with pytest.raises(ContractError):client.embed('no joint inference',b'actual-image')
    assert len(result)==768 and timing['prompt_eval_count']==15
    session.request.return_value.json=lambda:dict(model='alias',embeddings=[unit()])
    with pytest.raises(ContractError):client.embed('x')


def test_original_profile_qualification_and_equal_title_weight(movie):
    m={'1':dict(source=dict(metadata=metadata(movie))),'2':dict(source=dict(metadata=metadata(movie)))}
    events=[dict(username='u',rating_key=1,played_seconds=60) for _ in range(5)]
    events += [dict(username='u',rating_key=2,played_seconds=70)]
    assert qualifying_profiles(events,m,.5)=={'u':['1','2']}
    assert qualifying_profiles([dict(username='u',rating_key=1,played_seconds=45)],m,.5)=={}


def test_missing_poster_negative_cache_is_persistent(tmp_path,movie):
    client=Plex('http://plex.test','private',tmp_path)
    client.session.request=Mock(return_value=Mock(status_code=404))
    cache={}
    for _ in range(2):
        poster=client.poster(movie,cache.get,lambda k,v:cache.update({k:v}))
        assert poster.provenance['state']=='missing_art'
        assert poster.data is None and poster.provenance['content_sha256'] is None
    assert client.session.request.call_count==1


def test_publication_barrier_blocks_legacy_and_cleans_failure(tmp_path,monkeypatch):
    from api.embedding_generation import runtime
    from unittest.mock import MagicMock
    conn=MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value=(None,)
    monkeypatch.setattr('api.db.connection.connect_db',lambda:conn)
    monkeypatch.setattr(runtime,'TRANSITION',tmp_path/'transition.json')
    monkeypatch.setattr(runtime,'MARKER',tmp_path/'absent.json')
    monkeypatch.setattr(runtime,'legacy_writer_pids',lambda:[])
    with pytest.raises(ValueError):
        with runtime.publication_barrier():
            with pytest.raises(RuntimeError):runtime.assert_legacy_allowed()
            raise ValueError('injected publication error')
    assert not runtime.TRANSITION.exists()
    runtime.assert_legacy_allowed()
    monkeypatch.setattr(runtime,'legacy_writer_pids',lambda:[123])
    with pytest.raises(RuntimeError):
        with runtime.publication_barrier():pytest.fail('Existing legacy writer must prevent publication')
    assert not runtime.TRANSITION.exists()


def test_deployment_receipt_requires_existing_admin_auth(monkeypatch):
    from api.routes import admin_routes
    from api.embedding_generation import runtime
    route=next(r for r in admin_routes.router.routes if r.path=='/admin/embedding-generation/status')
    assert any(dep.call is admin_routes.require_admin for dep in route.dependant.dependencies)
    monkeypatch.setattr(runtime,'active_generation',lambda:None)
    result=admin_routes.embedding_generation_deployment_status(admin_user={'is_admin':True})
    assert result['generation_api']==1 and result['active_generation'] is None
    assert len(result['deployed_code_sha256'])==64


def test_api_only_distribution_can_hash_without_offline_scripts(tmp_path,monkeypatch):
    from api.embedding_generation import runtime
    full_hash=runtime.code_hash()
    monkeypatch.setattr(runtime,'ROOT',tmp_path)
    assert len(runtime.code_hash())==64 and runtime.code_hash()!=full_hash
