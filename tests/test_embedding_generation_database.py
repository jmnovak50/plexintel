"""Real PostgreSQL tests use ONLY connection-private temporary relations.

Opt in with PLEXINTEL_TEST_TEMP_DB=1. No production DDL, sequence advancement,
model fit on production rows, or production table mutation is performed.
"""
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from PIL import Image
from psycopg2 import sql
from psycopg2.extras import Json
import pytest

from api.embedding_generation.contracts import Encoder,ContractError,contract,fingerprint,metadata,media_text,watch_text,IMAGE_VERSION,embedding_input_hash
from api.embedding_generation.store import Store
from api.embedding_generation.io import Plex
from api.embedding_generation.backfill import prepare_metadata,prepare_posters,run_media_text,run_media_poster,run_watches,run_users
from api.embedding_generation.model import train,score,load_bundle
from api.embedding_generation.promotion import TABLES,promote,rollback,digest_rows
from api.embedding_generation.runtime import code_hash
from tests.test_embedding_generation import unit,image_bytes


@pytest.fixture
def store():
    if os.getenv('PLEXINTEL_TEST_TEMP_DB')!='1':pytest.skip('Opt-in private PostgreSQL temporary fixture')
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    from api.db.connection import connect_db
    conn=connect_db();conn.set_session(readonly=False)
    for path in sorted((Path(__file__).resolve().parents[1]/'api/db/migrations/optional/embedding_generation').glob('*.sql')):
        text='\n'.join(line for line in path.read_text().splitlines() if not line.startswith(('CREATE SCHEMA','REVOKE')))
        with conn.cursor() as cur:cur.execute(text.replace('embedding_v2.','pg_temp.'))
    conn.commit()
    try:yield Store(conn,'pg_temp')
    finally:conn.close()  # All temporary tables and their private sequences vanish.


@pytest.fixture
def encoder():return Encoder('embeddinggemma-2:latest','a'*64,'740m-q8_0','Q8_0','b'*64)


class FakeOllama:
    def __init__(self,encoder):self.encoder=encoder;self.calls=[];self.fail=False
    def embed(self,text=None,poster=None):
        self.calls.append((text,poster))
        if self.fail:raise RuntimeError('injected interruption')
        return unit(int(hashlib.sha256(text.encode() if text is not None else poster).hexdigest()[:4],16)%768),dict(
            model=self.encoder.reference,client_seconds=.01,server_nonload_seconds=.009)


def run_both(store,gid,cache,client):
    run_media_text(store,gid,client)
    run_media_poster(store,gid,cache,client)


def prepared_fixture(store,encoder,tmp_path):
    raw={str(k):dict(ratingKey=str(k),type='movie',title=f'Title {k}',summary='Plot',duration=100000,year=2000,
             Genre=[{'tag':'Drama'}],thumb=f'/library/metadata/{k}/thumb/1',updatedAt=1) for k in (1,2)}
    now='2026-01-01T00:00:00+00:00'
    snapshot=dict(as_of=now,legacy_watch_ids=[],media=[dict(rating_key=k,duration=100000,media_type='movie') for k in (1,2)],
        events=[dict(watch_id=k,rating_key=k,username='fixture',watched_at=f'2020-01-0{k}T00:00:00+00:00',
            available_at=f'2020-01-0{k}T01:00:00+00:00',observed_at=now,played_seconds=80,percent_complete=80) for k in (1,2)],feedback=[])
    gid=store.create(contract(encoder),snapshot,scope='full')
    plex=Plex('http://fixture.invalid','private',tmp_path)
    plex.metadata=lambda k:raw[str(k)]
    plex.revisions=lambda:{k:fingerprint(v) for k,v in raw.items()}
    response=Mock(status_code=200,headers={'Content-Type':'image/jpeg','ETag':'"one"'},iter_content=lambda n:[image_bytes()])
    plex.session.request=Mock(return_value=response)
    client=FakeOllama(encoder)
    prepare_metadata(store,gid,plex);prepare_posters(store,gid,plex)
    return gid,raw,plex,client


def test_checkpoint_resume_and_separate_input_stages(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    assert len(client.calls)==0
    assert store.counts(gid)['user']['expected']==1 and store.counts(gid)['user']['pending']==1
    assert plex.session.request.call_count==2
    run_both(store,gid,tmp_path,client);run_watches(store,gid,client);run_users(store,gid)
    assert len(client.calls)==6
    run_both(store,gid,tmp_path,client);run_watches(store,gid,client);run_users(store,gid)
    prepare_posters(store,gid,plex,refresh=True)
    assert len(client.calls)==6 and plex.session.request.call_count==2
    assert store.counts(gid)['user']['succeeded']==1
    values=store.items(gid,'user')[0]['embedding'].to_numpy()
    expected=np.mean([r['embedding'].to_numpy() for r in store.items(gid,'media_text')],axis=0)
    np.testing.assert_allclose(values,expected)


def test_partial_failure_resumes_only_failed_items(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    client.fail=True;run_both(store,gid,tmp_path,client)
    assert store.counts(gid)['media_text']['failed']==2
    client.fail=False;run_both(store,gid,tmp_path,client)
    assert store.counts(gid)['media_text']['succeeded']==2
    calls=len(client.calls);run_both(store,gid,tmp_path,client)
    assert len(client.calls)==calls
    with pytest.raises(ContractError):store.validate(gid,quality_go=True)


def test_poster_only_change_does_not_regenerate_watch_vectors(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    run_both(store,gid,tmp_path,client);run_watches(store,gid,client);run_users(store,gid)
    previous=[r['input_hash'] for r in store.items(gid,'watch')]
    out=BytesIO();Image.new('RGB',(100,200),'red').save(out,format='JPEG')
    plex.session.request.return_value=Mock(status_code=200,headers={'Content-Type':'image/jpeg','ETag':'"two"'},iter_content=lambda n:[out.getvalue()])
    prepare_posters(store,gid,plex,refresh=True,force=True)
    assert store.counts(gid)['media_poster']['pending']==2
    assert store.counts(gid)['media_text']['succeeded']==2
    assert store.counts(gid)['watch']['succeeded']==2
    run_both(store,gid,tmp_path,client);run_watches(store,gid,client)
    assert len(client.calls)==8
    assert previous==[r['input_hash'] for r in store.items(gid,'watch')]


def test_metadata_and_history_changes_invalidate_their_dependencies(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    run_both(store,gid,tmp_path,client);run_watches(store,gid,client);run_users(store,gid)
    raw['1']['summary']='New synopsis';raw['1']['updatedAt']=2
    prepare_metadata(store,gid,plex,refresh=True)
    assert store.counts(gid)['media_text']['pending']==1 and store.counts(gid)['watch']['pending']==1
    prepare_posters(store,gid,plex);run_both(store,gid,tmp_path,client);run_watches(store,gid,client)
    event=store.items(gid,'watch')[1]['source'];event['played_seconds']=10
    store.upsert_source(gid,'watch','2',event,owner='fixture',media_key='2')
    store.conn.commit()
    assert store.counts(gid)['watch']['pending']==1


def test_model_identity_and_scope_guards(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    client.encoder=Encoder('embeddinggemma-2:latest','c'*64,'740m-q8_0','Q8_0','b'*64)
    with pytest.raises(ContractError):run_both(store,gid,tmp_path,client)
    with pytest.raises(ContractError):promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp')


def test_304_and_persistent_cache_reuse(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    cached=store.query(sql.SQL('SELECT source_id,provenance FROM {}').format(store.table('poster_cache')),many=True)
    for row in cached:
        row['provenance']['checked_at']='2000-01-01T00:00:00+00:00';store.cache(row['source_id'],row['provenance'])
    store.conn.commit()
    plex.session.request.return_value=Mock(status_code=304,headers={})
    prepare_posters(store,gid,plex,refresh=True)
    assert plex.session.request.call_args.kwargs['headers']['If-None-Match']=='"one"'
    assert all(r['poster']['state']=='available' for r in store.items(gid,'media_poster'))


def synthetic_ready(store,encoder,*,missing_keys=()):
    base=datetime(2020,1,1,tzinfo=timezone.utc)
    media=[];events=[]
    for index in range(1,121):
        raw=dict(type='movie',title=f'Fixture {index}',duration=6000000,year=2000+index%20,
                 Genre=[{'tag':'Comedy' if index%2 else 'Drama'}])
        media.append(dict(rating_key=index,media_type='movie',plex_guid=f'plex://movie/fixture-{index}',
                          duration=6000000,metadata=metadata(raw)))
        day=base+timedelta(days=index*3)
        events.append(dict(watch_id=index,rating_key=index,username='fixture',watched_at=day.isoformat(),
            available_at=(day+timedelta(hours=2)).isoformat(),observed_at='2026-01-01T00:00:00+00:00',
            played_seconds=4800 if index%2 else 600,percent_complete=80 if index%2 else 10))
    snapshot=dict(media=media,events=events,legacy_watch_ids=[],feedback=[],as_of='2026-01-01T00:00:00+00:00')
    gid=store.create(contract(encoder),snapshot,scope='full')
    poster=dict(state='available',content_sha256='c'*64,preprocessing=IMAGE_VERSION)
    specification=store.generation(gid)['contract']
    for row in media:
        key=str(row['rating_key']);digest=fingerprint(row['metadata'])
        poster=dict(state='missing_art' if row['rating_key'] in missing_keys else 'available',
            content_sha256=None if row['rating_key'] in missing_keys else 'c'*64,preprocessing=IMAGE_VERSION)
        store.upsert_source(gid,'media_text',key,row,semantic_hash=digest)
        store.preparation(gid,key,'metadata',status='succeeded',content_hash=digest)
        poster_hash=fingerprint({k:poster[k] for k in ('state','content_sha256','preprocessing')})
        store.preparation(gid,key,'poster',status='succeeded',content_hash=poster_hash)
        store.complete(gid,'media_text',key,unit(row['rating_key']%20),embedding_input_hash(specification,'media_text',metadata=row['metadata']),timing=dict(model=encoder.reference))
        image_hash=embedding_input_hash(specification,'media_poster',poster_hash=poster_hash)
        if row['rating_key'] in missing_keys:store.complete_missing_poster(gid,key,image_hash,poster)
        else:store.complete(gid,'media_poster',key,unit((row['rating_key']+5)%20),image_hash,poster=poster,timing=dict(model=encoder.reference))
    for row in events:
        parent=media[row['rating_key']-1]
        input_hash=embedding_input_hash(specification,'watch',text=watch_text(row,parent['metadata']),
            event_hash=fingerprint({k:v for k,v in row.items() if k!='observed_at'}),media_hash=fingerprint(parent['metadata']))
        store.complete(gid,'watch',str(row['watch_id']),unit(row['rating_key']%20),input_hash,
            timing=dict(model=encoder.reference),dependencies=[('media_text',str(row['rating_key']),fingerprint(parent['metadata']))])
    store.conn.commit();run_users(store,gid)
    legacy=dict(media={str(r['rating_key']):unit((r['rating_key']+10)%20) for r in media},
                watch={str(e['watch_id']):unit((e['rating_key']+10)%20) for e in events})
    evaluation=train(store,gid,legacy_populations=legacy)
    scoring=score(store,gid)
    return gid,evaluation,scoring


def clone_legacy_tables_privately(store):
    """Copy schema + at most one legacy row. Defaults use ONLY temp sequences."""
    with store.conn.cursor() as cur:
        for index,table in enumerate(TABLES):
            cur.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE {} INCLUDING CONSTRAINTS INCLUDING INDEXES)')
                .format(sql.Identifier(table),sql.Identifier('public',table)))
            cur.execute('''SELECT a.attname,a.attidentity,pg_get_expr(d.adbin,d.adrelid)
                FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped''',('public.'+table,))
            for column,identity,default in cur.fetchall():
                if identity or default and default.startswith('nextval('):
                    name=f'fixture_seq_{index}_{column}'
                    cur.execute(sql.SQL('CREATE TEMP SEQUENCE {}').format(sql.Identifier(name)))
                    expression=sql.SQL("nextval({}::regclass)").format(sql.Literal('pg_temp.'+name))
                elif default:expression=sql.SQL(default)
                else:continue
                cur.execute(sql.SQL('ALTER TABLE {} ALTER COLUMN {} SET DEFAULT {}').format(sql.Identifier('pg_temp',table),sql.Identifier(column),expression))
            condition=sql.SQL(" WHERE key IN ('ollama.embedding_model','training.engagement_threshold')") if table=='app_settings' else sql.SQL(' LIMIT 1')
            cur.execute(sql.SQL('INSERT INTO {} SELECT * FROM {}{}').format(sql.Identifier('pg_temp',table),sql.Identifier('public',table),condition))
    store.conn.commit()


def test_full_shadow_classifier_parity_and_quality_gate(store,encoder):
    gid,evaluation,scoring=synthetic_ready(store,encoder)
    assert evaluation['chronological']['rows']>0 and evaluation['show_grouped']['metrics']['rows']>0
    assert 'paired_controls' in evaluation and scoring['predictions']>0
    bundle,vocab=load_bundle(store,gid)
    assert bundle['feature_names']==vocab.names and bundle['dimensions']==[768,768,768]
    with pytest.raises(ContractError):store.validate(gid,quality_go=False)
    result=store.validate(gid,quality_go=True)
    assert result['counts']['media_text']['succeeded']==120 and result['counts']['watch']['succeeded']==120
    with pytest.raises(ContractError):store.upsert_source(gid,'media_text','1',{})


def test_atomic_promotion_and_verified_rollback(store,encoder,tmp_path):
    gid,evaluation,scoring=synthetic_ready(store,encoder)
    store.validate(gid,quality_go=True)
    clone_legacy_tables_privately(store)
    before={t:digest_rows(store,t,'pg_temp') for t in TABLES}
    model=tmp_path/'legacy.pkl';model.write_bytes(b'private fixture legacy artifact')
    outcome=promote(store,gid,approved=True,deployed_code=code_hash(),live_schema='pg_temp',
                    source_check=lambda:store.generation(gid)['source_hash'],legacy_model=model)
    assert store.query('SELECT count(*) AS n FROM pg_temp.media_embeddings')['n']==120
    assert store.query('SELECT active_generation FROM pg_temp.control')['active_generation']==gid
    assert digest_rows(store,'embedding_labels','pg_temp')[0]==0
    from api.services.dimension_explorer import register_cte
    config=store.query('SELECT metadata FROM pg_temp.embedding_feature_config WHERE active')['metadata']
    statement,params=register_cte(dict(model_version='legacy'),config)
    identities=store.query(statement+' SELECT dimension,side,local_index,feature_name FROM register WHERE dimension IN (0,768,1536,2303) ORDER BY dimension',params,many=True)
    assert [(r['side'],r['local_index']) for r in identities]==[('media_text',0),('media_poster',0),('user',0),('user',767)]
    from scripts.embeddinggemma2_migration import verify
    assert verify(store,gid,live_schema='pg_temp')['embedding_dimensions']==2304
    model.write_bytes(b'changed artifact')
    with pytest.raises(ContractError):rollback(store,outcome['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=model)
    assert store.query('SELECT active_generation FROM pg_temp.control')['active_generation']==gid
    model.write_bytes(b'private fixture legacy artifact')
    rollback(store,outcome['promotion_id'],approved=True,live_schema='pg_temp',legacy_model=model)
    for table in TABLES:
        if table!='embedding_feature_config':assert digest_rows(store,table,'pg_temp')==before[table]
    assert store.query('SELECT active_generation FROM pg_temp.control')['active_generation'] is None


def test_promotion_failure_is_all_or_nothing(store,encoder,tmp_path):
    gid,evaluation,scoring=synthetic_ready(store,encoder)
    store.validate(gid,quality_go=True);clone_legacy_tables_privately(store)
    before={t:digest_rows(store,t,'pg_temp') for t in TABLES}
    model=tmp_path/'legacy.pkl';model.write_bytes(b'fixture')
    def fail(stage):
        if stage=='materialized':raise RuntimeError('injected publication failure')
    with pytest.raises(RuntimeError):promote(store,gid,approved=True,deployed_code=code_hash(),
        live_schema='pg_temp',source_check=lambda:store.generation(gid)['source_hash'],legacy_model=model,failpoint=fail)
    assert all(digest_rows(store,t,'pg_temp')==before[t] for t in TABLES)


def test_unchanged_compatible_parent_reuses_joint_and_watch_vectors(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    run_both(store,gid,tmp_path,client);run_watches(store,gid,client);run_users(store,gid)
    # Isolate reuse mechanics; quality/promotion validation has separate real tests.
    store.query("UPDATE pg_temp.generations SET status='validated' WHERE generation_id=%s",(gid,));store.conn.commit()
    generation=store.generation(gid)
    child=store.create(generation['contract'],generation['snapshot'],scope='full',parent=gid)
    prepare_metadata(store,child,plex);prepare_posters(store,child,plex)
    calls=len(client.calls)
    run_both(store,child,tmp_path,client);run_watches(store,child,client);run_users(store,child)
    assert len(client.calls)==calls
    assert all(r['origin_generation']==gid and r['timing']['inherited'] for kind in ('media_text','media_poster','watch') for r in store.items(child,kind))
    assert store.counts(child)['user']['succeeded']==1


def test_control_cohort_handles_missing_legacy_vectors(store,encoder):
    gid,evaluation,scoring=synthetic_ready(store,encoder)
    from api.embedding_generation.model import paired_controls
    media={r['item_key']:r for r in store.items(gid,'media_text')}
    watches={r['item_key']:r for r in store.items(gid,'watch')}
    legacy=dict(media={k:unit((int(k)+10)%20) for k in media},watch={k:unit((int(k)+10)%20) for k in watches if int(k)%17})
    posters={r['item_key']:r for r in store.items(gid,'media_poster')}
    controls=paired_controls(store.generation(gid),media,watches,posters,legacy,evaluation['boundary'])
    assert controls['coverage']['missing_legacy_events']>0
    assert controls['new_vectors_corrected_same_cohort']['rows']==controls['legacy_vectors_corrected_features']['rows']


def test_unlinked_history_requires_verified_legacy_membership(store,encoder):
    snapshot=dict(media=[],events=[dict(watch_id=1,rating_key=999,username='fixture')],feedback=[])
    with pytest.raises(ContractError,match='coverage must be verified'):
        store.create(contract(encoder),snapshot,scope='full')
    assert store.query('SELECT count(*) AS n FROM pg_temp.generations')['n']==0
    assert store.query('SELECT active_generation FROM pg_temp.control')['active_generation'] is None


def test_quarantine_is_durable_and_excluded_from_every_embedding_population(store,encoder,tmp_path):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path)
    snapshot=store.generation(gid)['snapshot']
    snapshot['events'].append(dict(watch_id=99,rating_key=999,username='unlinked-only-owner',played_seconds=100000))
    snapshot['legacy_watch_ids']=[1]
    snapshot['_db_hash']='untouched-entire-source-hash'
    child=store.create(contract(encoder),snapshot,scope='full')
    prepare_metadata(store,child,plex);prepare_posters(store,child,plex)
    run_both(store,child,tmp_path,client);run_watches(store,child,client);run_users(store,child)
    generation=store.generation(child)
    assert generation['source_hash']=='untouched-entire-source-hash'
    assert generation['snapshot']['quarantined_events'][0]['event']['watch_id']==99
    assert generation['snapshot']['watch_coverage']['source_watch_events']==3
    assert generation['snapshot']['watch_coverage']['existing_watch_embeddings_covered']==1
    assert store.counts(child)['watch']['expected']==2 and store.counts(child)['watch']['succeeded']==2
    assert {r['item_key'] for r in store.items(child,'user')}=={'fixture'}
    assert len(client.calls)==6 and not any('unlinked-only-owner' in (text or '') for text,_ in client.calls)
    before=len(client.calls)
    run_both(store,child,tmp_path,client);run_watches(store,child,client)
    assert len(client.calls)==before


def test_existing_vector_cannot_be_quarantined(store,encoder):
    snapshot=dict(media=[],events=[dict(watch_id=1,rating_key=999,username='fixture')],feedback=[],legacy_watch_ids=[1])
    with pytest.raises(ContractError,match='Existing watch vector has unlinked media'):
        store.create(contract(encoder),snapshot,scope='full')
    assert store.query('SELECT count(*) AS n FROM pg_temp.generations')['n']==0


def test_missing_image_training_storage_ablations_and_explicit_acceptance(store,encoder):
    gid,evaluation,scoring=synthetic_ready(store,encoder,missing_keys={105,106,109,110,115,116})
    assert store.query('SELECT count(*) AS n FROM pg_temp.modality_training_rows WHERE media_poster IS NULL')['n']==6
    for split in ('chronological','show_grouped'):
        b=evaluation['ablations']['B_text_only'][split];c=evaluation['ablations']['C_text_poster'][split]
        assert b['cohort_hash']==c['cohort_hash'] and b['rows']==c['rows']
    assert evaluation['chronological']['segments']['missing_art']['rows']==6
    with pytest.raises(ContractError,match='missing-art allowance'):store.validate(gid,quality_go=True)
    assert store.validate(gid,quality_go=True,missing_art_limit=6)['missing_art']==6
