from copy import deepcopy
from unittest.mock import Mock
import pytest
from api.embedding_generation.contracts import ContractError,fingerprint
from api.embedding_generation.io import SourceError
from api.embedding_generation.recovery import Resolver,prepare,POLICY,historical_raw
from api.embedding_generation import recovery
from api.embedding_generation.backfill import prepare_metadata
from tests.test_embedding_generation_database import store,encoder,prepared_fixture


def sources():
    return {'1':dict(rating_key=1,media_type='show',title='Series',plex_guid='plex://show/series',summary='Recorded show synopsis',year=2020),
        '2':dict(rating_key=2,media_type='season',title='Season 2',show_rating_key=1,parent_rating_key=1,season_number=2),
        '3':dict(rating_key=3,media_type='episode',title='Chapter',plex_guid='plex://episode/chapter',show_rating_key=1,
            parent_rating_key=2,season_number=2,episode_number=3,summary='Recorded story',duration=100000,year=2021)}


def plex_fixture(catalog=()):
    plex=Mock();plex.catalog.return_value=iter(catalog)
    current={'11':dict(type='show',ratingKey='11',title='Series',guid='plex://show/series',summary='Live show synopsis',thumb='/library/metadata/11/thumb/1'),
        '12':dict(type='season',ratingKey='12',title='Season Two',parentRatingKey='11',index=2,summary='Live season synopsis')}
    def get(key):
        if str(key) not in current:raise SourceError('HTTP_404')
        return current[str(key)]
    plex.metadata.side_effect=get
    return plex,current


def test_guid_recovery_and_historical_episode_preserve_parent_context():
    plex,current=plex_fixture([dict(type='show',ratingKey='11',guid='plex://show/series'),
        dict(type='season',ratingKey='12',parentRatingKey='11',index=2)])
    resolver=Resolver(plex,sources(),{'3':dict(genres=['Drama'],cast=[dict(tag='A',order=1)],directors=['D'])})
    value,poster,origin=resolver.payload(sources()['3'])
    assert value['synopsis']=='Recorded story' and value['show_context']['synopsis']=='Live show synopsis'
    assert value['season_context']['synopsis']=='Live season synopsis' and value['episode_number']==3
    assert value['cast']==['A'] and value['directors']==['D'] and value['original_title'] is None
    assert origin['components']['media']['source']=='stored-library'
    assert origin['components']['show']['resolved_key']=='11'
    assert origin['components']['season']['identity_rule']=='verified-show-guid-and-season-index'
    assert poster['_poster_sources'][0]['ratingKey']=='11'
    assert origin['raw_inputs_hash']==fingerprint(origin['raw_inputs'])


def test_no_title_only_replacement_or_fabricated_missing_fields():
    src={'1':dict(rating_key=1,media_type='movie',title='Same title',summary='Stored',plex_guid='plex://movie/old')}
    plex,current=plex_fixture([dict(type='movie',ratingKey='21',guid='plex://movie/different',title='Same title')])
    result,_,origin=Resolver(plex,src,{}).payload(src['1'])
    assert origin['components']['media']['source']=='stored-library' and result['synopsis']=='Stored'
    assert result['cast']==[] and result['original_language'] is None
    assert all(str(c.args[0])!='21' for c in plex.metadata.call_args_list)


def test_ambiguous_replacement_and_transient_errors_fail_closed():
    src={'1':dict(rating_key=1,media_type='show',title='Series',plex_guid='plex://show/series')}
    plex,_=plex_fixture([dict(type='show',ratingKey=k,guid='plex://show/series') for k in ('11','99')])
    with pytest.raises(ContractError,match='Ambiguous'):Resolver(plex,src,{}).payload(src['1'])
    plex.metadata.side_effect=SourceError('network_failure')
    with pytest.raises(SourceError,match='network_failure'):Resolver(plex,src,{}).payload(src['1'])


def test_same_key_guid_mismatch_is_not_silently_accepted():
    src={'11':dict(rating_key=11,media_type='show',title='Series',plex_guid='plex://show/other')}
    plex,_=plex_fixture()
    with pytest.raises(ContractError,match='different entity'):Resolver(plex,src,{}).payload(src['11'])


def test_recovery_requires_reason_only_retries_failed_and_survives_refresh(store,encoder,tmp_path,monkeypatch):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    row=store.items(gid,'media_text')[0]
    captured={**row['source'],'title':'Recorded title','summary':'Recorded synopsis','year':2000}
    captured.pop('metadata',None)
    store.upsert_source(gid,'media_text','1',captured,semantic_hash=row['semantic_hash'])
    # One failed 404; the other successful checkpoint must not be rewritten.
    store.preparation(gid,'1','metadata',status='failed',provenance={'error':'SourceError:HTTP_404'});store.conn.commit()
    before=store.preparation(gid,'2','metadata')['prepared_at']
    plex.metadata=lambda key: (_ for _ in ()).throw(SourceError('HTTP_404'))
    plex.catalog=lambda:iter([])
    monkeypatch.setattr(recovery,'load_associations',lambda conn,keys:{'1':dict(genres=['Recorded Genre'],directors=['Recorded Director'],cast=[dict(tag='Recorded Actor',order=0)])})
    with pytest.raises(ContractError,match='requires --reason'):prepare(store,gid,plex,reason=None)
    prepare(store,gid,plex,reason='Approved archived metadata for absent Plex records')
    result=store.items(gid,'media_text')[0]
    assert result['status']=='pending' and result['embedding'] is None and not client.calls
    assert result['source']['metadata']['genres']==['Recorded Genre']
    assert result['source']['_metadata_recovery']['policy']==POLICY
    assert result['source']['metadata_origin']['components']['media']['source']=='stored-library'
    assert store.preparation(gid,'2','metadata')['prepared_at']==before
    assert store.preparation(gid,'1','metadata')['status']=='succeeded'
    checkpoint=store.preparation(gid,'1','metadata')['prepared_at']
    prepare(store,gid,plex,reason='Resume')
    assert store.preparation(gid,'1','metadata')['prepared_at']==checkpoint
    # Future explicit refresh retains the approved source policy, without inference.
    plex.revisions=lambda:{}
    prepare_metadata(store,gid,plex,refresh=True)
    assert store.preparation(gid,'1','metadata')['status']=='succeeded' and not client.calls
    assert store.preparation(gid,'2','metadata')['status']=='failed'


def test_cli_recovery_stage_does_not_start_other_producers(monkeypatch,encoder):
    from contextlib import nullcontext
    from scripts import embeddinggemma2_migration as cli
    recovered=Mock();monkeypatch.setattr(recovery,'prepare',recovered)
    producers=[Mock() for _ in range(6)]
    for name,method in zip(('prepare_metadata','prepare_posters','run_media_text','run_media_poster','run_watches','run_users'),producers):
        monkeypatch.setattr(cli.backfill,name,method)
    monkeypatch.setattr(cli.source,'plex',lambda *a:Mock())
    monkeypatch.setattr(cli,'report',lambda *a:{})
    monkeypatch.setattr(cli,'StageProgress',lambda *a,**kw:nullcontext(lambda value:None))
    fake=Mock();fake.generation.return_value=dict(contract={})
    args=cli.argument_parser().parse_args(['recover-metadata','--generation','fixture','--reason','Operator accepted source policy','--approved-production-change'])
    cli.dispatch_stage(fake,'fixture',args,{})
    recovered.assert_called_once()
    assert not any(method.called for method in producers)
    args.reason=None
    with pytest.raises(ContractError,match='requires --reason'):cli.dispatch_stage(fake,'fixture',args,{})


def test_recovered_source_provenance_is_reproducible_and_tamper_checked():
    from api.embedding_generation.recovery import validate_origin
    from datetime import datetime,timezone
    plex,_=plex_fixture([dict(type='show',ratingKey='11',guid='plex://show/series'),
        dict(type='season',ratingKey='12',parentRatingKey='11',index=2)])
    value,poster,origin=Resolver(plex,sources(),{}).payload(sources()['3'])
    row={**sources()['3'],'metadata':value,'metadata_origin':origin,'_metadata_recovery':dict(
        policy=POLICY,reason='Explicit source acceptance',approved_at=datetime.now(timezone.utc).isoformat())}
    validate_origin(row,'3')
    changed=deepcopy(row);changed['metadata_origin']['raw_inputs']['media']['summary']='unattributed replacement'
    with pytest.raises(ContractError,match='attributed input snapshot'):validate_origin(changed,'3')
    changed=deepcopy(row);changed['metadata_origin']['components']['show']['verified_guid']='plex://show/wrong'
    with pytest.raises(ContractError,match='stable GUID mismatch'):validate_origin(changed,'3')


def test_historical_fallback_preserves_previously_captured_rich_fields():
    from api.embedding_generation.contracts import metadata
    captured=metadata(dict(type='movie',title='Recorded title',summary='Stored plot',originalTitle='Original',duration=90000,
        Writer=[dict(tag='Writer')],Role=[dict(tag='Actor')],originalLanguage='en',Genre=[dict(tag='Drama')]))
    src=dict(rating_key=1,media_type='movie',metadata=captured)
    result=metadata(historical_raw(src,{}))
    assert result==captured
