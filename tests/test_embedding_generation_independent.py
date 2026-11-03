from copy import deepcopy
from contextlib import nullcontext
from io import BytesIO
from unittest.mock import Mock
import numpy as np
from PIL import Image
import pytest
from psycopg2 import sql

from api.embedding_generation.contracts import contract,modality_contract,embedding_input_hash,ContractError,KINDS,metadata
from api.embedding_generation.backfill import prepare_metadata,prepare_posters,run_media_text,run_media_poster,run_watches,run_users
from api.embedding_generation.features import feature_row,Vocabulary
from api.embedding_generation.operator import approve_review,require_review,StageProgress
from tests.test_embedding_generation_database import store,encoder,prepared_fixture
from tests.test_embedding_generation_features import fixture_data


def test_documented_manual_runbook_matches_actual_cli():
    from scripts.validate_embeddinggemma2_runbook import check
    result=check()
    assert result['valid'] and result['commands_checked']>=40
    assert result['review_gates']==['poster','profiles','quality','text']


def test_create_reports_source_progress_without_starting_inference(monkeypatch,encoder):
    from scripts import embeddinggemma2_migration as cli
    client=Mock();client.resolve.return_value=encoder
    monkeypatch.setattr(cli,'Ollama',Mock(return_value=client))
    def collect(config,**kwargs):
        kwargs['progress'](dict(expected=10,completed=5,failed=0,phase='history availability'))
        return dict(events=[])
    monkeypatch.setattr(cli,'collect',collect)
    config={'ollama.host':'http://fixture.invalid','ollama.timeout_s':1,'ollama.threads':16,
        'user_embeddings.engagement_threshold':.5,'training.movie_revisit_pending_days':21,'training.tv_revisit_pending_days':14}
    store=Mock();store.create.side_effect=lambda *args,**kwargs:kwargs['gid']
    progress=[];gid,_=cli.create(store,config,progress=progress.append)
    assert progress==[dict(expected=10,completed=5,failed=0,phase='history availability',generation_id=gid)]
    assert store.create.call_args.kwargs['gid']==gid
    client.embed.assert_not_called()


def test_modality_contracts_invalidate_only_the_affected_inputs(encoder):
    base=contract(encoder)
    for field,value,affected in [('image','next-image-policy',{'media_poster'}),
        ('media_serializer','next-semantic-format',{'media_text','watch','user'}),
        ('watch_serializer','next-behavior-format',{'watch'}),('features','next-features',set())]:
        changed={**base,field:value}
        assert {kind for kind in KINDS if modality_contract(base,kind)!=modality_contract(changed,kind)}==affected
    changed=deepcopy(base);changed['encoder']['digest']='c'*64
    assert all(modality_contract(base,k)!=modality_contract(changed,k) for k in KINDS)


def test_missing_poster_is_null_and_indicator_not_a_fabricated_vector(encoder):
    g,media,watches,events=fixture_data(encoder);posters=g['_test_posters']
    posters['2'].update(status='missing',embedding=None)
    row=feature_row(g,media,watches,events,'u','2','2021-01-01T00:00:00+00:00',posters=posters)
    assert row['poster_missing'] and np.isnan(row['embedding'][768:1536]).all()
    assert np.isfinite(row['embedding'][:768]).all() and np.isfinite(row['embedding'][1536:]).all()
    full=Vocabulary.fit([row]);text=Vocabulary.fit([row],include_poster=False)
    assert full.transform([row])[0,-1]==1 and not np.isnan(text.transform([row])).any()
    assert full.names[:2304]==[f'{group}_{i}' for group in ('media_text','media_poster','user') for i in range(768)]
    assert not any(n.startswith('media_poster_') for n in text.names)
    posters['2']['generation_id']='different'
    with pytest.raises(ContractError,match='Mixed/incomplete media_poster'):feature_row(g,media,watches,events,'u','2','2021-01-01T00:00:00+00:00',posters=posters)


def test_episode_preserves_verified_season_context():
    result=metadata(dict(type='episode',title='Chapter',summary='Episode story',parentIndex=2,index=3),
        dict(type='show',title='Series',summary='Show story'),dict(type='season',title='Season Two',summary='Season story',index=2))
    assert result['show_context']['synopsis']=='Show story'
    assert result['season_context']['synopsis']=='Season story'
    assert result['episode_title']=='Chapter' and result['episode_number']==3


def test_forced_shared_tv_artwork_is_revalidated_once_per_preparation_run(tmp_path):
    from api.embedding_generation.io import Plex
    from tests.test_embedding_generation import image_bytes
    plex=Plex('http://fixture.invalid','private',tmp_path)
    plex.session.request=Mock(return_value=Mock(status_code=200,headers={'Content-Type':'image/jpeg'},iter_content=lambda _: [image_bytes()]))
    cache={};checked=set();show=dict(type='show',ratingKey='3',thumb='/library/metadata/3/thumb/1')
    for key in ('1','2'):
        result=plex.poster(dict(type='episode',ratingKey=key,_poster_sources=[show]),cache.get,
            lambda k,v:cache.update({k:v}),force=True,force_checked=checked)
        assert result.provenance['source_key']==3
    assert plex.session.request.call_count==1


def finish(store,gid,cache,client):
    run_media_text(store,gid,client);run_media_poster(store,gid,cache,client)
    run_watches(store,gid,client);run_users(store,gid)


def test_metadata_only_change_never_runs_image_inference(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path);finish(store,gid,tmp_path,client)
    images=sum(image is not None for _,image in client.calls)
    raw['1']['summary']='Changed descriptive synopsis';raw['1']['updatedAt']=2
    prepare_metadata(store,gid,plex,refresh=True)
    assert store.counts(gid)['media_text']['pending']==1
    assert store.counts(gid)['media_poster']['succeeded']==2
    run_media_text(store,gid,client);run_media_poster(store,gid,tmp_path,client)
    assert len(client.calls)==7 and sum(image is not None for _,image in client.calls)==images


def test_completed_semantic_user_checkpoint_is_not_rebuilt_on_resume(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path);finish(store,gid,tmp_path,client)
    previous=store.items(gid,'user')[0]
    run_users(store,gid)
    current=store.items(gid,'user')[0]
    assert current['generated_at']==previous['generated_at'] and current['attempts']==previous['attempts']


def test_new_poster_reference_with_identical_pixels_reuses_native_image_vector(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path);finish(store,gid,tmp_path,client)
    raw['1']['thumb']='/library/metadata/1/thumb/2';raw['1']['updatedAt']=2
    prepare_metadata(store,gid,plex,refresh=True)
    assert store.preparation(gid,'1','poster') is None
    prepare_posters(store,gid,plex);run_media_poster(store,gid,tmp_path,client)
    assert len(client.calls)==6
    assert store.items(gid,'media_poster')[0]['poster']['source'].endswith('/2')


def test_inference_audit_retains_superseded_requests_and_failure_reporting(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    client.fail=True
    lines=[]
    with pytest.raises(ContractError,match='incomplete'):
        with StageProgress(store,gid,'media-text',kind='media_text',printer=lambda *a,**kw:lines.append(a[0])) as progress:
            run_media_text(store,gid,client,progress=progress)
    assert 'failed=2' in lines[-1] and 'last_error=RuntimeError' in lines[-1]
    client.fail=False;run_media_text(store,gid,client)
    raw['1']['summary']='New description';raw['1']['updatedAt']=2
    prepare_metadata(store,gid,plex,refresh=True);run_media_text(store,gid,client)
    rows=store.query('SELECT status,count(*) AS n FROM pg_temp.inference_requests GROUP BY status',many=True)
    assert {r['status']:r['n'] for r in rows}=={'failed':2,'succeeded':3}


def test_calibration_ranking_and_classification_metrics_have_known_values():
    from api.embedding_generation.evaluation import probability_metrics
    rows=[dict(owner='u',media_key=str(i),label=y) for i,y in enumerate((1,0,1),1)]
    result=probability_metrics(rows,[.9,.8,.1])
    assert result['balanced_accuracy']==pytest.approx(.25)
    assert result['precision']==pytest.approx(.5) and result['recall']==pytest.approx(.5)
    assert result['roc_auc']==pytest.approx(.5) and result['average_precision']==pytest.approx(5/6)
    assert result['brier_score']==pytest.approx((.01+.64+.81)/3)
    assert result['calibration']['ece_10_bins']==pytest.approx(.6)
    assert result['ranking']['ndcg_at_10']==pytest.approx(1.5/(1+1/np.log2(3)))
    assert result['ranking']['recall_at_25']==1 and result['ranking']['users_with_at_most_25_candidates']==1
    assert probability_metrics([],[])['status']=='no_examples'


def test_dimension_inventory_exposes_three_complete_native_groups():
    from api.services.dimension_config import build_independent_metadata,identity
    names=[f'{group}_{i}' for group in ('media_text','media_poster','user') for i in range(768)]
    config=build_independent_metadata(names+['watch_sim','poster_missing'],'model-sha',generation_id='new',
        contract_hash='contract',encoder_digest='digest',serializer='semantic-format')
    assert identity(config,0)['feature_name']=='media_text_0'
    assert identity(config,768)==dict(dimension=768,feature_name='media_poster_0',side='media_poster',local_index=0)
    assert identity(config,1536)['feature_name']=='user_0' and identity(config,2303)['local_index']==767
    with pytest.raises(ValueError):identity(config,2304)
    with pytest.raises(ValueError):build_independent_metadata(names[:-1],'model',generation_id='g',contract_hash='c',encoder_digest='d',serializer='s')


def test_failed_metadata_prevents_downstream_cli_from_starting(store,encoder,tmp_path,monkeypatch):
    from scripts import embeddinggemma2_migration as cli
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    store.preparation(gid,'1','metadata',status='failed',provenance={'error':'controlled error'});store.conn.commit()
    make_plex=Mock();monkeypatch.setattr(cli.source,'plex',make_plex)
    for operation in ('posters','media-text'):
        args=cli.argument_parser().parse_args([operation,'--generation',gid,'--approved-production-change'])
        with pytest.raises(ContractError,match='preparation is incomplete'):cli.dispatch_stage(store,gid,args,{})
    make_plex.assert_not_called();assert client.calls==[]


def test_poster_only_change_keeps_text_watch_and_user_checkpoints(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path);finish(store,gid,tmp_path,client)
    store.artifact(gid,'old-model-probe',b'old');store.conn.commit()
    previous={kind:[r['input_hash'] for r in store.items(gid,kind)] for kind in ('media_text','watch','user')}
    output=BytesIO();Image.new('RGB',(80,160),'red').save(output,format='JPEG')
    plex.session.request.return_value=Mock(status_code=200,headers={'Content-Type':'image/jpeg'},iter_content=lambda _: [output.getvalue()])
    prepare_posters(store,gid,plex,refresh=True,force=True)
    assert all(store.counts(gid)[kind]['succeeded']==len(values) for kind,values in previous.items())
    run_media_poster(store,gid,tmp_path,client);run_media_text(store,gid,client);run_watches(store,gid,client)
    assert len(client.calls)==8 and all(text is None for text,_ in client.calls[-2:])
    assert previous=={kind:[r['input_hash'] for r in store.items(gid,kind)] for kind in previous}
    with pytest.raises(ContractError):store.artifact(gid,'old-model-probe')


def test_interrupted_text_stage_resumes_without_repeating_committed_requests(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    embed=client.embed;attempts=0;lines=[]
    def interrupted(*args,**kwargs):
        nonlocal attempts
        attempts+=1
        if attempts==2:raise KeyboardInterrupt()
        return embed(*args,**kwargs)
    client.embed=interrupted
    with pytest.raises(KeyboardInterrupt):
        with StageProgress(store,gid,'media-text',kind='media_text',printer=lambda *a,**kw:lines.append(a[0])) as progress:
            run_media_text(store,gid,client,progress=progress)
    assert store.counts(gid)['media_text']['succeeded']==1 and len(client.calls)==1
    run_media_text(store,gid,client)
    assert len(client.calls)==2 and store.counts(gid)['media_poster']['pending']==2
    assert store.query("SELECT status FROM pg_temp.stage_runs ORDER BY started_at DESC LIMIT 1")['status']=='interrupted'
    assert 'resumed/skipped=' in lines[-1] and 'last_error=KeyboardInterrupt' in lines[-1]


def test_manual_reviews_are_explicit_and_become_stale_on_changes(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    with pytest.raises(ContractError):approve_review(store,gid,'text','not ready')
    run_media_text(store,gid,client);approve_review(store,gid,'text','Operator inspected metadata/text')
    require_review(store,gid,'text')
    raw['1']['summary']='Changed';raw['1']['updatedAt']=2;prepare_metadata(store,gid,plex,refresh=True)
    with pytest.raises(ContractError,match='missing or stale'):require_review(store,gid,'text')
    run_media_text(store,gid,client)
    with pytest.raises(ContractError,match='missing or stale'):require_review(store,gid,'text')
    approve_review(store,gid,'text','Operator reviewed changed input');require_review(store,gid,'text')


def test_missing_art_needs_review_allowance_and_no_image_inference(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    for value in raw.values():value.pop('thumb')
    prepare_metadata(store,gid,plex,refresh=True);prepare_posters(store,gid,plex,refresh=True)
    run_media_text(store,gid,client);run_media_poster(store,gid,tmp_path,client)
    assert len(client.calls)==2 and store.counts(gid)['media_poster']['missing']==2
    assert all(row['embedding'] is None for row in store.items(gid,'media_poster'))
    with pytest.raises(ContractError,match='missing-art allowance'):approve_review(store,gid,'poster','missing image review')
    approve_review(store,gid,'poster','Explicitly accepted two missing images',missing_art_limit=2)
    assert require_review(store,gid,'poster')['missing_art_limit']==2


def test_global_feature_change_reuses_independent_vectors_with_identical_modality_contracts(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path);finish(store,gid,tmp_path,client)
    store.query("UPDATE pg_temp.generations SET status='validated' WHERE generation_id=%s",(gid,));store.conn.commit()
    previous=store.generation(gid);spec={**previous['contract'],'features':'future-independent-feature-schema'}
    child=store.create(spec,previous['snapshot'],scope='full',parent=gid)
    prepare_metadata(store,child,plex);prepare_posters(store,child,plex);finish(store,child,tmp_path,client)
    assert len(client.calls)==6
    assert all(r['timing']['inherited'] for kind in ('media_text','media_poster','watch') for r in store.items(child,kind))


def test_cli_has_no_combined_media_stage_and_requires_explicit_authorization(monkeypatch):
    from scripts import embeddinggemma2_migration as cli
    with pytest.raises(SystemExit):cli.argument_parser().parse_args(['media'])
    connect=Mock();monkeypatch.setattr(cli,'connect_db',connect)
    for stage in ('install','create','metadata','posters','media-text','media-poster','watch','users','train','score','validate','promote','rollback'):
        with pytest.raises(SystemExit):cli.main([stage,'--generation','fixture'])
    connect.assert_not_called()


@pytest.mark.parametrize('operation,expected', [('metadata','prepare_metadata'),('posters','prepare_posters'),
    ('media-text','run_media_text'),('media-poster','run_media_poster'),('watch','run_watches'),('users','run_users'),('train','train'),('score','score')])
def test_manual_cli_dispatch_invokes_only_the_requested_stage(operation,expected,monkeypatch,encoder):
    from scripts import embeddinggemma2_migration as cli
    methods={name:Mock() for name in ('prepare_metadata','prepare_posters','run_media_text','run_media_poster','run_watches','run_users','train','score')}
    for name,method in methods.items():monkeypatch.setattr(cli.backfill if hasattr(cli.backfill,name) else cli,name,method)
    monkeypatch.setattr(cli,'require_review',Mock());monkeypatch.setattr(cli,'require_preparation',Mock())
    monkeypatch.setattr(cli,'legacy_vectors',Mock(return_value={}))
    monkeypatch.setattr(cli,'report',lambda *a:{})
    monkeypatch.setattr(cli,'StageProgress',lambda *a,**kw:nullcontext(lambda value:None))
    monkeypatch.setattr(cli.source,'plex',lambda *a:Mock())
    fake=Mock();fake.generation.return_value=dict(contract=contract(encoder),base_generation=None)
    fake.counts.return_value={'watch':dict(succeeded=1,expected=1,failed=0)}
    args=cli.argument_parser().parse_args([operation,'--generation','fixture','--approved-production-change'])
    cli.dispatch_stage(fake,'fixture',args,{'ollama.host':'http://fixture.invalid','ollama.timeout_s':1})
    assert [name for name,method in methods.items() if method.called]==[expected]
