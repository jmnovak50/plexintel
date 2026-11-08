"""Text adoption and real SQL atomic publication use private temporary tables only."""
import hashlib
import io
import json
from copy import deepcopy
from unittest.mock import Mock
import joblib
import numpy as np
import pytest
from psycopg2.extras import Json
from api.embedding_generation.contracts import ContractError,fingerprint,text_contract,text_only
from api.embedding_generation.features import feature_row,Vocabulary
from api.embedding_generation.backfill import prepare_posters,run_media_poster,run_media_text,run_watches,run_users
from api.embedding_generation.model import score,load_bundle
from api.embedding_generation.operator import approve_review
from api.embedding_generation.promotion import promote,rollback,TABLES,digest_rows
from api.embedding_generation.runtime import code_hash
from api.embedding_generation.text_production import adopt,load_production,physical_verification,seed_from_production
from api.services.dimension_config import feature_groups,identity
from tests.test_embedding_generation_database import store,encoder,synthetic_ready,clone_legacy_tables_privately,FakeOllama
from tests.test_embedding_generation_features import fixture_data


def test_text_feature_contract_preserves_native_dimensions_and_leakage(encoder):
    g,media,watches,events=fixture_data(encoder)
    old=feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00',posters=g['_test_posters'])
    g['contract']=text_contract(g['contract']);g['contract_hash']=fingerprint(g['contract'])
    g.pop('_modality_hash_cache',None)
    new=feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')
    vocab=Vocabulary.fit([old],include_poster=False)
    np.testing.assert_array_equal(vocab.transform([new]),vocab.transform([old]))
    assert len(new['embedding'])==1536 and 'media_poster_hash' not in new['dependencies']
    assert new['dependencies']['profile_keys']==['1'] and new['watch_sim']==old['watch_sim']
    assert feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00',excluded_keys=['1']) is None
    watches['1']['generation_id']='legacy'
    with pytest.raises(ContractError):feature_row(g,media,watches,events,'u','2','2020-01-20T00:00:00+00:00')


def test_full_b_adoption_physical_publication_failure_rollback_and_incremental_reuse(store,encoder,tmp_path,monkeypatch):
    source,_,_=synthetic_ready(store,encoder)
    store.validate(source,quality_go=True)
    clone_legacy_tables_privately(store)
    legacy=tmp_path/'legacy.pkl';legacy.write_bytes(b'untouched legacy model')
    # Model C is already active in the observed deployment; exercise that transition.
    original=promote(store,source,approved=True,deployed_code=code_hash(),live_schema='pg_temp',
        source_check=lambda:store.generation(source)['source_hash'],legacy_model=legacy)
    before={t:digest_rows(store,t,'pg_temp') for t in TABLES}
    result=adopt(store,source,reason='Select evaluated B; retain complete metadata and disable poster costs')
    gid=result['generation_id']
    assert result['embedding_inference_requests']==0 and result['model_refits']==0
    assert store.items(gid,'media_poster')==[]
    assert store.counts(gid)['media_poster']['expected']==0
    assert store.query('SELECT count(*) AS n FROM pg_temp.inference_requests WHERE generation_id=%s',(gid,))['n']==0
    for kind in ('media_text','watch','user'):
        a={r['item_key']:r for r in store.items(source,kind)}
        for row in store.items(gid,kind):
            old=a[row['item_key']]
            np.testing.assert_array_equal(row['embedding'].to_numpy(),old['embedding'].to_numpy())
            assert row['input_hash']==old['input_hash'] and row['provenance']==old['provenance']
    with pytest.raises(ContractError,match='disabled'):prepare_posters(store,gid,Mock())
    with pytest.raises(ContractError,match='disabled'):run_media_poster(store,gid,tmp_path,FakeOllama(encoder))
    bundle,vocab=load_bundle(store,gid)
    assert len(vocab.names)>=1536 and not vocab.include_poster
    assert not any(n.startswith('media_poster_') or n=='poster_missing' for n in vocab.names)
    assert store.query('SELECT count(*) AS n FROM pg_temp.text_training_rows WHERE generation_id=%s',(gid,))['n']>0
    approve_review(store,gid,'text','Complete rich text coverage')
    approve_review(store,gid,'profiles','Compatible watch/user coverage')
    approve_review(store,gid,'quality','Selected B with independent quality review',quality_go=True)
    scoring=score(store,gid);assert scoring['predictions']>0
    from psycopg2 import sql
    from api.embedding_generation.progress import Reporter
    prediction_query=sql.SQL('SELECT owner,media_key,probability,rank,shap FROM {} WHERE generation_id=%s ORDER BY owner,media_key').format(store.table('predictions'))
    unobserved=store.query(prediction_query,(gid,),many=True)
    monitor=Reporter(lambda event:None)
    observed=score(store,gid,monitor=monitor)
    assert store.query(prediction_query,(gid,),many=True)==unobserved
    assert monitor.details['score_model']['status']=='success'
    assert monitor.details['shap']['status']=='success'
    assert observed['shap_contexts']>0 and observed['shap_contributions']>0
    store.validate(gid,quality_go=True)
    assert {t:digest_rows(store,t,'pg_temp') for t in TABLES}==before
    def failure(point):
        if point=='materialized':raise RuntimeError('Injected failure before atomic commit')
    with pytest.raises(RuntimeError):promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',
        source_check=lambda:store.generation(gid)['source_hash'],legacy_model=legacy,failpoint=failure)
    assert {t:digest_rows(store,t,'pg_temp') for t in TABLES}==before
    assert load_production(store) is None
    promoted=promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',
        source_check=lambda:store.generation(gid)['source_hash'],legacy_model=legacy)
    assert all(r['all_vectors_exact'] for r in physical_verification(store,gid,'pg_temp').values())
    canonical,active,active_vocab=load_production(store)
    assert active['ordering']=='media_text,user' and active['dimensions']==[768,768]
    assert canonical['model_sha256']==promoted.get('model_sha256',canonical['model_sha256'])
    config=store.query('SELECT metadata FROM pg_temp.embedding_feature_config WHERE active')['metadata']
    assert feature_groups(config)==[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)]
    assert identity(config,768)['side']=='user'
    assert store.query('SELECT max(dimension) AS n FROM pg_temp.shap_impact')['n']<1536
    # Canonical loading does not redirect to a shadow model artifact.
    with monkeypatch.context() as patch:
        patch.setattr(store,'artifact',Mock(side_effect=AssertionError('Shadow artifact access forbidden')))
        assert load_production(store)[1]['ordering']=='media_text,user'
        scratch=seed_from_production(store,deepcopy(canonical['snapshot']),live_schema='pg_temp')
    client=FakeOllama(encoder)
    run_media_text(store,scratch,client);run_watches(store,scratch,client);run_users(store,scratch)
    assert client.calls==[] and store.items(scratch,'media_poster')==[]
    from api.embedding_generation.text_production import train_text
    future_evaluation=train_text(store,scratch)
    assert future_evaluation['chronological']['rows']>0
    score(store,scratch);store.validate(scratch,quality_go=True)
    assert load_bundle(store,scratch)[0]['dimensions']==[768,768]
    assert load_production(store)[0]['generation_id']==gid
    # Retire initial B's redundant staging rows: production must remain independent.
    for name in ('dependencies','preparations','predictions','text_training_rows','items'):
        store.query(__import__('psycopg2').sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(store.table(name)),(gid,))
    store.conn.commit()
    from api.embedding_generation.text_production import verify_current_production
    assert verify_current_production(store,live_schema='pg_temp')['verified']
    from api.embedding_generation.production_run import ProductionRun
    run_id='fixture-production-run'
    store.query("INSERT INTO pg_temp.production_runs(run_id,generation_id,base_model_sha256,status) VALUES(%s,%s,%s,'running')",(run_id,gid,canonical['model_sha256']))
    store.conn.commit()
    journal=ProductionRun(store,run_id,live_schema='pg_temp');journal.install_work()
    generation_count=store.query('SELECT count(*) AS n FROM pg_temp.generations')['n']
    working_snapshot=deepcopy(canonical['snapshot']);working_snapshot['_db_hash']=canonical['source_hash']
    journal.hydrate(canonical,working_snapshot)
    assert journal.generation(gid)['status']=='building'
    unchanged=FakeOllama(encoder)
    run_media_text(journal,gid,unchanged);run_watches(journal,gid,unchanged);run_users(journal,gid)
    assert unchanged.calls==[]
    assert store.query('SELECT count(*) AS n FROM pg_temp.generations')['n']==generation_count
    # A corrected watch event checkpoints only its own inference and dependent profile.
    event=journal.items(gid,'watch')[0];corrected=dict(event['source'],played_seconds=900)
    journal.upsert_source(gid,'watch',event['item_key'],corrected,owner=event['owner'],media_key=event['media_key'],semantic_hash=fingerprint({k:v for k,v in corrected.items() if k!='observed_at'}))
    journal.conn.commit();run_watches(journal,gid,unchanged)
    assert len(unchanged.calls)==1 and unchanged.calls[0][1] is None
    assert store.query('SELECT count(*) AS n FROM pg_temp.production_run_requests WHERE run_id=%s',(run_id,))['n']==1
    assert store.query('SELECT count(*) AS n FROM pg_temp.production_run_items WHERE run_id=%s',(run_id,))['n']==1
    # Restore the checkpoint into working state and skip its completed inference.
    checkpoint=store.query('SELECT record,embedding FROM pg_temp.production_run_items WHERE run_id=%s',(run_id,))
    journal.restore_item(checkpoint['record'],checkpoint['embedding']);journal.conn.commit()
    run_watches(journal,gid,unchanged);assert len(unchanged.calls)==1
    for target in working_snapshot['events']:
        if str(target['watch_id'])==event['item_key']:target.update(corrected)
    journal.query(__import__('psycopg2').sql.SQL('UPDATE {} SET snapshot=%s WHERE generation_id=%s').format(journal.table('generations')),(Json(working_snapshot),gid))
    journal.conn.commit();run_users(journal,gid)
    train_text(journal,gid);score(journal,gid);journal.validate(gid,quality_go=True)
    revision=promote(journal,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',
        source_check=lambda:journal.generation(gid)['source_hash'],legacy_model=legacy)
    assert store.query('SELECT count(*) AS n FROM pg_temp.generations')['n']==generation_count
    assert store.query('SELECT status FROM pg_temp.production_runs WHERE run_id=%s',(run_id,))['status']=='succeeded'
    assert load_production(store)[0]['publication_id']==revision['promotion_id']
    with pytest.raises(ContractError,match='current production revision'):rollback(store,promoted['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=legacy)
    rollback(store,revision['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=legacy)
    assert load_production(store)[0]['publication_id']==promoted['promotion_id']
    # Removing a production identity is detected even though joined rows match.
    store.query('DELETE FROM pg_temp.watch_embeddings WHERE watch_id=1')
    with pytest.raises(ContractError,match='physical production'):verify_current_production(store,live_schema='pg_temp')
    store.conn.rollback()
    # A corrupt runtime archive cannot leave a partial database restoration.
    saved=store.query('SELECT model_bundle FROM pg_temp.production_rollback WHERE promotion_id=%s',(promoted['promotion_id'],))['model_bundle']
    store.query('UPDATE pg_temp.production_rollback SET model_bundle=%s WHERE promotion_id=%s',(b'corrupt',promoted['promotion_id']));store.conn.commit()
    with pytest.raises(ContractError,match='checksum'):rollback(store,promoted['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=legacy)
    assert load_production(store)[0]['generation_id']==gid
    store.query('UPDATE pg_temp.production_rollback SET model_bundle=%s WHERE promotion_id=%s',(bytes(saved),promoted['promotion_id']));store.conn.commit()
    rollback(store,promoted['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=legacy)
    assert {t:digest_rows(store,t,'pg_temp') for t in TABLES if t!='embedding_feature_config'}=={t:v for t,v in before.items() if t!='embedding_feature_config'}
    restored_config=store.query('SELECT metadata FROM pg_temp.embedding_feature_config WHERE active')['metadata']
    assert restored_config['ordering']=='media_text,media_poster,user'
    assert store.query('SELECT active_generation FROM pg_temp.control')['active_generation']==source
    assert load_production(store) is None
    # Original legacy rollback remains available after returning to C.
    rollback(store,original['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=legacy)
    assert store.query('SELECT active_generation FROM pg_temp.control')['active_generation'] is None
    assert legacy.read_bytes()==b'untouched legacy model'


def test_new_title_and_metadata_edits_never_require_artwork(store,encoder,tmp_path):
    from tests.test_embedding_generation_database import prepared_fixture
    from api.embedding_generation.backfill import prepare_metadata
    source,raw,plex,_=prepared_fixture(store,encoder,tmp_path)
    snapshot=store.generation(source)['snapshot']
    gid=store.create(text_contract(store.generation(source)['contract']),snapshot,scope='full')
    plex.revisions=lambda **kwargs:{k:fingerprint(v) for k,v in raw.items()}
    plex.poster=Mock(side_effect=AssertionError('Poster access forbidden'))
    client=FakeOllama(encoder)
    prepare_metadata(store,gid,plex);run_media_text(store,gid,client);run_watches(store,gid,client);run_users(store,gid)
    assert len(client.calls)==4 and all(text is not None and image is None for text,image in client.calls)
    assert store.counts(gid)['media_poster']['expected']==0
    # A different thumb does not change either text vector or require artwork.
    raw['1']['thumb']='/library/metadata/1/thumb/2'
    prepare_metadata(store,gid,plex,refresh=True)
    run_media_text(store,gid,client);run_watches(store,gid,client);run_users(store,gid)
    assert len(client.calls)==4
    raw['1']['summary']='Revised complete synopsis'
    prepare_metadata(store,gid,plex,refresh=True);run_media_text(store,gid,client);run_watches(store,gid,client);run_users(store,gid)
    assert len(client.calls)==6 and all(image is None for _,image in client.calls)
    plex.poster.assert_not_called()
    # Input/model contract edits fail even when dimensions remain identical.
    client.encoder=deepcopy(encoder)
    from dataclasses import replace
    client.encoder=replace(encoder,digest='f'*64)
    with pytest.raises(ContractError,match='differs'):run_media_text(store,gid,client)


def test_daily_orchestrator_explicitly_omits_poster_work(encoder,tmp_path,monkeypatch):
    from api.embedding_generation import text_production,production_run
    implementation=Mock(return_value={'production_run':'one'})
    monkeypatch.setattr(production_run,'execute',implementation)
    store=Mock();config={};collect=Mock();plex=Mock();lock=Mock()
    result=text_production.daily(store,config,collect=collect,plex_factory=plex,cache=tmp_path,publication_lock=lock)
    assert result=={'production_run':'one'}
    assert implementation.call_args.kwargs['collect'] is collect
    assert not any('poster' in key for key in implementation.call_args.kwargs)


def test_active_pipeline_dispatch_and_legacy_write_protection(monkeypatch):
    from api.embedding_generation import runtime
    from api.services.pipeline_service import build_pipeline_stages
    monkeypatch.setattr(runtime,'active_generation',lambda:'text-production')
    stages=build_pipeline_stages()
    assert len(stages)==1 and 'daily' in stages[0][1]
    assert not any('poster' in part for _,command in stages for part in command)
    with pytest.raises(RuntimeError,match='Legacy embedding/model writers are disabled'):runtime.assert_legacy_allowed()


def test_admin_receipt_reports_canonical_text_classifier(monkeypatch):
    from unittest.mock import MagicMock
    from api.routes import admin_routes
    from api.embedding_generation import runtime,text_production
    runtime.MARKER.write_text('{}')
    monkeypatch.setattr(runtime,'active_generation',lambda:'text')
    conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect=[(True,),('text',),(True,)]
    monkeypatch.setattr(admin_routes,'connect_db',lambda:conn)
    state=dict(generation_id='text',model_sha256='a'*64)
    bundle=dict(variant='text_only',encoder=dict(digest='b'*64),feature_version='semantic-text-user-prospective/1.0',
                ordering='media_text,user',dimensions=[768,768],feature_names=['feature']*1605)
    monkeypatch.setattr(text_production,'load_production',lambda store:(state,bundle,None))
    monkeypatch.setattr(__import__('api.embedding_generation.store',fromlist=['Store']),'Store',lambda connection:Mock())
    result=admin_routes.embedding_generation_deployment_status(admin_user={'is_admin':True})
    assert result['model_variant']=='text_only' and result['embedding_dimensions']==1536
    assert result['classifier_feature_count']==1605 and result['poster_inference']=='disabled/1.0'
    assert result['model_storage']=='canonical production state'
    conn.set_session.assert_called_once_with(readonly=True,isolation_level='REPEATABLE READ')
    conn.rollback.assert_called_once();conn.close.assert_called_once()


def test_text_source_refresh_does_not_create_poster_work(store,encoder,tmp_path,monkeypatch):
    import importlib.util
    from pathlib import Path
    from tests.test_embedding_generation_database import prepared_fixture
    source,raw,plex,_=prepared_fixture(store,encoder,tmp_path)
    snapshot=deepcopy(store.generation(source)['snapshot'])
    gid=store.create(text_contract(store.generation(source)['contract']),snapshot,scope='full')
    spec=importlib.util.spec_from_file_location('text_refresh_cli',Path('scripts/embeddinggemma2_migration.py'))
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    before=cli.report(store,gid)
    assert before['preparation_counts']['poster']['expected']==0
    assert before['preparation_counts']['poster']['pending']==0
    snapshot['media'].append(dict(rating_key=3,duration=100000,media_type='movie'))
    snapshot['_db_hash']=fingerprint(snapshot)
    monkeypatch.setattr(cli,'collect',lambda *a,**k:snapshot)
    cli.refresh_source(store,gid,{})
    assert len(store.items(gid,'media_text'))==3 and store.items(gid,'media_poster')==[]
    assert store.counts(gid)['media_poster']['expected']==0
    assert cli.report(store,gid)['preparation_counts']['poster']['pending']==0


@pytest.mark.parametrize('resumed',[False,True])
@pytest.mark.parametrize('bad_quality',[False,True])
def test_canonical_run_orchestration_resumes_without_new_shadow_or_duplicate_sync(encoder,tmp_path,monkeypatch,resumed,bad_quality):
    from contextlib import nullcontext
    from dataclasses import asdict
    from unittest.mock import MagicMock
    from psycopg2 import sql
    from api.embedding_generation import production_run as module,text_production,backfill,operator,model,promotion,io,runtime
    contract=text_contract(__import__('api.embedding_generation.contracts',fromlist=['contract']).contract(encoder))
    state=dict(generation_id='existing',model_sha256='before',contract=contract,evaluation=dict(chronological=dict(average_precision=.9)))
    monkeypatch.setattr(text_production,'load_production',lambda store:(state,{},None))
    monkeypatch.setattr(text_production,'verify_current_production',lambda store:{'verified':True,'counts':{'media_text':{'succeeded':1}},'generation_id':'existing','publication_id':'published','model_sha256':'after'})
    base=dict(library_counts={'movie':1},media_keys=['1'],watch_ids=['1'],media_embedding_keys=['1'],watch_embedding_keys=['1'])
    snapshot=dict(_db_hash='source',media=[{'rating_key':1}],events=[],watch_coverage={})
    completed={k:1 for k in ('source_sync','metadata','media_text','watch','users','training','scoring')} if resumed else {}
    run=dict(run_id='resume',base_model_sha256='before',stages=completed,summary={'before':base},snapshot=snapshot)
    def query(statement,*args,**kwargs):
        text=str(statement)
        if 'production_runs' in text and 'status IN' in text:return run if resumed else None
        if 'SELECT *' in text and 'production_runs' in text:return run
        if 'production_run_requests' in text:return []
        if 'deployed_code_sha256' in text:return {'deployed_code_sha256':'code'}
        return None
    store=MagicMock();store.query.side_effect=query;store.table.side_effect=lambda name:sql.Identifier('pg_temp',name)
    monkeypatch.setattr(module,'baseline',lambda store:base)
    worker=MagicMock();worker.hydrate.return_value='existing'
    worker.counts.return_value={k:dict(expected=1,succeeded=1,failed=0,pending=0) for k in ('media_text','watch','user')}
    worker.items.return_value=[{'timing':{'rebuilt':True}}]
    good=dict(chronological=dict(balanced_accuracy=.4 if bad_quality else .6,average_precision=.9),show_grouped=dict(metrics=dict(balanced_accuracy=.6)))
    def artifact(gid,name):return dict(sha256='after',data=json.dumps(good if name=='evaluation.json' else {'predictions':1}).encode())
    worker.artifact.side_effect=artifact
    monkeypatch.setattr(module,'ProductionRun',lambda *a,**k:worker)
    stages=[]
    for name in ('prepare_metadata','run_media_text','run_watches','run_users'):
        monkeypatch.setattr(backfill,name,lambda *a,_name=name,**k:stages.append(_name))
    monkeypatch.setattr(backfill,'prepare_posters',Mock(side_effect=AssertionError('No posters')))
    monkeypatch.setattr(backfill,'run_media_poster',Mock(side_effect=AssertionError('No posters')))
    monkeypatch.setattr(operator,'require_preparation',Mock());monkeypatch.setattr(operator,'approve_review',Mock())
    monkeypatch.setattr(text_production,'train_text',Mock());monkeypatch.setattr(model,'score',Mock())
    monkeypatch.setattr(promotion,'promote',Mock(return_value=dict(promotion_id='published',generation_id='existing')))
    monkeypatch.setattr(io,'Ollama',Mock())
    import subprocess
    process=Mock(return_value=Mock(returncode=0,stdout='',stderr=''));monkeypatch.setattr(subprocess,'run',process)
    (tmp_path/'logs').mkdir();monkeypatch.setattr(runtime,'ROOT',tmp_path)
    def execute():return module.execute(store,{'ollama.host':'http://fixture','ollama.timeout_s':1},collect=Mock(),
        plex_factory=lambda *a:Mock(),cache=tmp_path,publication_lock=lambda *a:nullcontext())
    if bad_quality:
        with pytest.raises(ContractError,match='quality gates'):execute()
        promotion.promote.assert_not_called();return
    result=execute()
    assert result['generation_id']=='existing' and result['summary']['no_new_shadow_generation']
    assert result['summary']['poster_inference_requests']==0
    assert process.call_count==(0 if resumed else 1)
    assert stages==([] if resumed else ['prepare_metadata','run_media_text','run_watches','run_users'])
    assert '--no-embeddings' in process.call_args.args[0] if not resumed else True
