"""Real PostgreSQL, public-only predictor with synthetic local encoder/source replay."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json,os,re
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
import numpy as np
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
import pytest
from api.predictive import source
from api.predictive.artifacts import current_config,load_model
from api.predictive.contracts import ContractError
from api.predictive.runner import run
from api.predictive.publication import PUBLISHED,writer_lock,verify,install_staging,stage_predictions


@pytest.fixture
def db():
    """A distinct disposable database, only on an explicitly private Unix socket."""
    dsn=os.getenv('PLEXINTEL_RESTORATION_TEST_DSN')
    if not dsn:pytest.skip('Set PLEXINTEL_RESTORATION_TEST_DSN to a disposable private socket cluster')
    admin=psycopg2.connect(dsn);params=admin.get_dsn_parameters()
    if not params['host'].startswith('/tmp/plexintel-restoration-pg-'):
        admin.close();pytest.fail('Refusing non-disposable PostgreSQL host')
    admin.autocommit=True;name='restoration_'+uuid4().hex
    with admin.cursor() as cur:cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    args=dict(host=params['host'],port=params['port'],user=params['user'],dbname=name)
    conn=psycopg2.connect(**args)
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE EXTENSION vector')
            baseline=Path('create.sql').read_text()
            tables=set(PUBLISHED)-{'embedding_feature_config','shap_prediction_context'}
            tables|={'library','watch_history','genres','media_genres','actors','media_actors','directors','media_directors'}
            for table in sorted(tables):
                match=re.search(r'CREATE TABLE IF NOT EXISTS public\.'+table+r' \([\s\S]*?\n\);',baseline)
                assert match,table
                cur.execute(match.group())
            cur.execute('''ALTER TABLE library ADD COLUMN plex_guid text;
                CREATE TABLE user_feedback(id serial,username text,rating_key integer,feedback text,suppress boolean,
                    created_at timestamptz,modified_at timestamptz);
                CREATE TABLE embedding_feature_config(config_id text PRIMARY KEY,metadata jsonb,active boolean);
                CREATE UNIQUE INDEX config_active ON embedding_feature_config(active) WHERE active;
                CREATE TABLE embedding_labels(dimension integer,config_id text,generation_id text,contract_hash text,encoder_digest text);
                CREATE TABLE embedding_label_batches(batch_id text,generation_id text NOT NULL);''')
            context_migration=Path('api/db/migrations/001_dimension_explorer.sql').read_text()
            context_ddl=re.search(r'CREATE TABLE IF NOT EXISTS public\.shap_prediction_context \([\s\S]*?\n\);',context_migration)
            assert context_ddl
            cur.execute(context_ddl.group())
            cur.execute(Path('api/db/migrations/optional/simple_predictor/001_public_provenance.sql').read_text())
            cur.execute('SELECT to_regnamespace(%s)',('embedding_v2',));assert cur.fetchone()[0] is None
        conn.commit();yield conn
    finally:
        conn.close()
        with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


class Encoder:
    identity=dict(name='embeddinggemma-2:latest',digest='a'*64,dimensions=768,
        normalization='ollama-l2-unit/1.0',num_ctx=8192,num_batch=2048)
    def __init__(self):self.calls=0;self.fail=False
    def embed(self,text):
        if self.fail:raise RuntimeError('mock local encoder unavailable')
        self.calls+=1
        values=np.zeros(768);values[1 if 'Negative' in text else 0]=1.
        return values


def populate(conn):
    base=datetime(2020,1,1,tzinfo=timezone.utc);raw={}
    with conn.cursor() as cur:
        for key in range(1,174):
            title=('Negative' if key%2 else 'Positive')+f' movie {key}'
            row=dict(ratingKey=str(key),type='movie',title=title,guid='plex://movie/title-'+str(key),duration=6000000,
                year=2020,summary='Synthetic synopsis',updatedAt=1,Genre=[dict(tag='Drama')],
                Role=[dict(tag='Synthetic actor',order=1)],Director=[dict(tag='Synthetic director')])
            raw[str(key)]=row
            cur.execute('INSERT INTO library(rating_key,title,media_type,plex_guid,duration,year,summary) VALUES(%s,%s,\'movie\',%s,6000000,2020,%s)',
                (key,title,row['guid'],row['summary']))
        ident=0
        for owner in ('viewer-one','viewer-two'):
            ident+=1
            cur.execute('INSERT INTO watch_history(watch_id,username,rating_key,watched_at,played_duration,percent_complete) VALUES(%s,%s,2,%s,4800,80)',
                (ident,owner,base))
            for key in range(3,164):
                at=base+timedelta(days=key)
                if key%3==0:
                    ident+=1;played=600 if key%2 else 4800
                    cur.execute('INSERT INTO watch_history(watch_id,username,rating_key,watched_at,played_duration,percent_complete) VALUES(%s,%s,%s,%s,%s,%s)',
                        (ident,owner,key,at,played,played/60))
                else:
                    value=('never_watch' if key%2 else 'interested') if key%5==0 else ('watched_dislike' if key%2 else 'watched_like')
                    cur.execute('INSERT INTO user_feedback(username,rating_key,feedback,suppress,created_at,modified_at) VALUES(%s,%s,%s,true,%s,%s)',
                        (owner,key,value,at,at+timedelta(hours=1)))
    conn.commit()
    snapshot=source.read_snapshot(conn);conn.rollback()
    snapshot['as_of']='2021-01-01T00:00:00+00:00'
    from api.services.app_settings import get_setting_definition
    snapshot['_fixture_policy']={k:get_setting_definition(k).default for k in (
        'scoring.shap_targeting_strategy','scoring.shap_max_items','scoring.shap_max_items_overall',
        'scoring.shap_max_items_movie','scoring.shap_max_items_tv','scoring.shap_raw_min_dims',
        'scoring.shap_raw_max_dims','scoring.shap_raw_cumabs_target')}
    for event in snapshot['events']:
        event['verified_started_at']=event['watched_at']
        # Explicit synthetic upstream stop receipt, separate from public storage.
        event['available_at']=(datetime.fromisoformat(event['watched_at'])+timedelta(hours=1)).isoformat()
    plex=Mock();plex.catalog.return_value=list(raw.values());plex.metadata.side_effect=lambda key:raw[str(key)]
    return snapshot,plex,Encoder()


def digest(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT md5(COALESCE(jsonb_agg(to_jsonb(r) ORDER BY username,rating_key)::text,\'\')) FROM recommendations r')
        return cur.fetchone()[0]


@pytest.mark.parametrize('explain',[True,False])
def test_prediction_staging_sets_generation_time_without_changing_snapshot_or_public_rows(db,explain):
    install_staging(db)
    snapshot='2021-01-01T00:00:00+00:00'
    config=dict(config_id='fixture',model_sha256='a'*64)
    with db.cursor() as cur:
        cur.execute('''SELECT a.attnotnull,d.adbin IS NULL
            FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE a.attrelid='pg_temp.prepared_shap_prediction_context'::regclass AND a.attname='generated_at' ''')
        assert cur.fetchone()==(True,True)  # Production constraint, intentionally no copied default.
    db.commit()
    before=datetime.now(timezone.utc)
    predictions=(dict(owner='fixture-viewer',key=i,probability=.75,rank=i,cosine=.5,
                      shap=[(7,.25)] if explain else []) for i in range(1,130))
    assert stage_predictions(db,predictions,config,snapshot)==129  # Cross the first 128-row flush.
    after=datetime.now(timezone.utc)
    with db.cursor() as cur:
        cur.execute('SELECT scored_at,generated_at,config_id,model_version FROM prepared_shap_prediction_context')
        contexts=cur.fetchall()
        assert len(contexts)==(129 if explain else 0)
        for scored_at,generated_at,config_id,model_version in contexts:
            assert scored_at==datetime(2021,1,1)
            assert before<=generated_at<=after
            assert (config_id,model_version)==('fixture','a'*64)
        cur.execute('SELECT count(*),min(predicted_probability),max(predicted_probability) FROM prepared_recommendations')
        assert cur.fetchone()==(129,.75,.75)
        cur.execute('SELECT count(*),sum(shap_value) FROM prepared_shap_impact')
        assert cur.fetchone()==((129,129*.25) if explain else (0,None))
        for table in ('recommendations','shap_impact','shap_prediction_context'):
            cur.execute('SELECT count(*) FROM public.'+table)
            assert cur.fetchone()[0]==0


def test_public_only_complete_repeat_partial_failure_and_last_good(db,tmp_path,monkeypatch):
    import api.predictive.runner as runner
    snapshot,plex,encoder=populate(db)
    before_generation=datetime.now(timezone.utc)
    result=run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    after_generation=datetime.now(timezone.utc)
    config=current_config(db);db.commit()
    assert result['verified'] and result['counts']['training_data']>128
    assert result['summary']['observations']['retrospective_explicit_feedback']>0
    assert result['evaluation']['chronological']['negative_recall'] is not None
    assert result['evaluation']['show_heldout']['negative']>0
    assert all(result['evaluation']['gates'].values())
    assert result['counts']['recommendations']>0 and result['counts']['shap_impact']>0
    with db.cursor() as cur:
        cur.execute('SELECT count(*),min(scored_at),max(scored_at),min(generated_at),max(generated_at) FROM public.shap_prediction_context')
        count,first_score,last_score,first_generated,last_generated=cur.fetchone()
        assert count==result['counts']['shap_prediction_context']>0
        assert first_score==last_score==datetime(2021,1,1)
        assert before_generation<=first_generated<=last_generated<=after_generation
    before=digest(db);db.commit();calls=encoder.calls
    with db.cursor() as cur:
        cur.execute('SELECT ctid::text FROM media_embeddings WHERE rating_key=4');physical=cur.fetchone()[0]
    db.commit()
    # Repeat reads exactly the same saved vector/provenance inputs; no inference.
    result2=run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    assert encoder.calls==calls
    with db.cursor() as cur:
        cur.execute('SELECT ctid::text FROM media_embeddings WHERE rating_key=4');assert cur.fetchone()[0]==physical
    assert digest(db)==before;db.commit()
    assert (tmp_path/'last-good.tar').is_file()
    # Inject a failure after >128 rows have been staged and a public table replaced.
    real_publish=runner.publish
    def interrupted(*args,**kwargs):
        def failure(stage):
            if stage=='training_data':raise RuntimeError('simulated interruption after replacement')
        return real_publish(*args,**kwargs,failpoint=failure)
    monkeypatch.setattr(runner,'publish',interrupted)
    with pytest.raises(RuntimeError,match='interruption'):
        run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    assert digest(db)==before;db.commit()
    assert verify(db,current_config(db))==result2['counts'];db.commit()
    with db.cursor() as cur:
        cur.execute('SELECT to_regnamespace(%s)',('embedding_v2',));assert cur.fetchone()[0] is None
    db.commit()
    # A corrupted model file is rejected before any new daily work.
    active=current_config(db);db.commit();Path(active['model_path']).write_bytes(b'corrupt')
    with pytest.raises(ContractError,match='checksum'):
        run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    assert digest(db)==before;db.commit()
    from api.predictive.publication import restore_last_good
    restored=restore_last_good(db,tmp_path)
    assert restored['verified'] and restored['verification_only']
    assert digest(db)==before


def test_writer_conflicts_fail_before_work(db):
    other=psycopg2.connect(db.dsn)
    try:
        with writer_lock(db):
            with pytest.raises(ContractError,match='writer'):
                with writer_lock(other):pytest.fail('Concurrent writer admitted')
    finally:other.close()


@pytest.mark.parametrize('drift',['source','incumbent'])
def test_revision_or_source_drift_after_staging_fails_before_publication(db,tmp_path,monkeypatch,drift):
    import api.predictive.runner as runner
    snapshot,plex,encoder=populate(db)
    # Seed a tiny pre-existing publication and retain its exact contents.
    with db.cursor() as cur:
        cur.execute("INSERT INTO recommendations(id,username,rating_key,predicted_probability,rank) VALUES(1,'saved',1,.42,1)")
    db.commit();before=digest(db);db.commit()
    real_publish=runner.publish
    def changed(conn,config,incumbent,source_hash,**kwargs):
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM prepared_training_data');assert cur.fetchone()[0]>128
            if drift=='source':cur.execute("UPDATE library SET summary='changed during fit' WHERE rating_key=3")
            else:cur.execute("INSERT INTO embedding_feature_config VALUES('unexpected','{}',true)")
        conn.commit()
        return real_publish(conn,config,incumbent,source_hash,**kwargs)
    monkeypatch.setattr(runner,'publish',changed)
    with pytest.raises(ContractError,match='changed during preparation'):
        run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    assert digest(db)==before


def test_encoder_failure_preserves_published_recommendations(db,tmp_path):
    snapshot,plex,encoder=populate(db);encoder.fail=True
    with db.cursor() as cur:cur.execute("INSERT INTO recommendations(id,username,rating_key,predicted_probability,rank) VALUES(1,'saved',1,.42,1)")
    db.commit();before=digest(db);db.commit()
    with pytest.raises(RuntimeError,match='encoder unavailable'):
        run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    assert digest(db)==before


@pytest.mark.parametrize('when',['commit','after_commit'])
def test_real_connection_loss_does_not_automatically_replay_a_possible_publication(db,tmp_path,monkeypatch,when):
    import api.predictive.runner as runner
    from api.predictive.failures import classify_failure
    from api.services import pipeline_labeling
    snapshot,plex,encoder=populate(db)
    with db.cursor() as cur:cur.execute("INSERT INTO recommendations(id,username,rating_key,predicted_probability,rank) VALUES(1,'saved',1,.42,1)")
    db.commit();before=digest(db);db.commit()
    other=psycopg2.connect(db.dsn);real_publish=runner.publish
    cloud=Mock();monkeypatch.setattr(pipeline_labeling,'run_after_publication',cloud)
    def terminate():
        with other.cursor() as cur:cur.execute('SELECT pg_terminate_backend(%s)',(db.get_backend_pid(),))
        other.commit()
    def lost(*args,**kwargs):
        with db.cursor() as cur:
            cur.execute('SELECT count(*) FROM prepared_training_data');assert cur.fetchone()[0]>128
        if when=='commit':
            def interrupt(stage):
                if stage=='verified':terminate()
            return real_publish(*args,**kwargs,failpoint=interrupt)
        result=real_publish(*args,**kwargs);terminate();return result
    monkeypatch.setattr(runner,'publish',lost)
    try:
        with pytest.raises(ContractError) as error:
            run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,output=lambda _:None)
        assert not classify_failure(error.value)['retryable']
        cloud.assert_not_called()
        if when=='commit':assert digest(other)==before
        else:
            assert digest(other)!=before,str(error.value)
            assert verify(other,current_config(other))['training_data']>128
    finally:other.close()


def test_training_vector_mismatch_after_first_staging_batch_fails_closed(db,tmp_path,monkeypatch):
    import api.predictive.runner as runner
    snapshot,plex,encoder=populate(db);real_publish=runner.publish
    def corrupt(conn,*args,**kwargs):
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM prepared_training_data');assert cur.fetchone()[0]>128
            cur.execute("UPDATE prepared_training_data SET embedding='[1,0]'::vector WHERE id=129")
        conn.commit();return real_publish(conn,*args,**kwargs)
    monkeypatch.setattr(runner,'publish',corrupt)
    with pytest.raises(ContractError,match='materialization'):
        run(db,tmp_path,frozen_source=snapshot,policy=snapshot['_fixture_policy'],plex=plex,encoder=encoder,collect=False,label=False,output=lambda _:None)
    with db.cursor() as cur:
        cur.execute('SELECT count(*) FROM recommendations');assert cur.fetchone()[0]==0


def test_log_retention_keeps_recent_active_and_last_thirty_terminal_records(db):
    from api.predictive.history import prune
    with db.cursor() as cur:
        cur.execute('CREATE TABLE pipeline_runs(run_id integer PRIMARY KEY,status text,started_at timestamptz)')
        cur.execute("INSERT INTO pipeline_runs SELECT i,'success',now()-interval '40 days'-i*interval '1 minute' FROM generate_series(1,50) i")
        cur.execute("INSERT INTO pipeline_runs SELECT i,'success',now() FROM generate_series(51,55) i")
        cur.execute("INSERT INTO pipeline_runs VALUES(56,'started',now()-interval '45 days')")
    db.commit()
    assert prune(db)==25;db.commit()
    with db.cursor() as cur:
        cur.execute("SELECT count(*),count(*) FILTER(WHERE status='started') FROM pipeline_runs")
        assert cur.fetchone()==(31,1)


def test_additive_migration_preserves_existing_vector_values(db):
    with db.cursor() as cur:
        cur.execute('ALTER TABLE training_data ALTER COLUMN embedding TYPE vector(768)')
        cur.execute("INSERT INTO training_data(id,embedding) VALUES(99,%s::vector)",(str([1.]+[0.]*767),))
        cur.execute('SELECT embedding::text FROM training_data WHERE id=99');before=cur.fetchone()[0]
        cur.execute(Path('api/db/migrations/optional/simple_predictor/001_public_provenance.sql').read_text())
        cur.execute('SELECT embedding::text FROM training_data WHERE id=99');assert cur.fetchone()[0]==before
        cur.execute('SELECT to_regnamespace(%s)',('embedding_v2',));assert cur.fetchone()[0] is None


def test_actual_public_projection_has_no_observation_column_and_does_not_invent_times(db):
    snapshot,_,_=populate(db)
    raw=source.read_snapshot(db)
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='watch_history' AND column_name='observed_at'")
        assert cur.fetchone()[0]==0
    assert all('observed_at' not in e and 'available_at' not in e for e in raw['events'])
    from api.predictive.features import available
    assert all(available(e) is None for e in raw['events'])
    assert all(available(e) is not None for e in snapshot['events'])


def test_association_projection_preserves_serialized_inputs_and_full_source_drift_detection(db):
    from api.predictive.recovery import load_associations,iter_associations,historical_raw
    from api.predictive.contracts import metadata,media_text
    from api.predictive.publication import source_signature
    snapshot,_,_=populate(db)
    with db.cursor() as cur:
        for i in range(30):
            cur.execute('INSERT INTO actors(id,name) VALUES(%s,%s)',(i+1,'Fixture actor '+str(i)))
            cur.execute('INSERT INTO media_actors(media_id,actor_id,cast_order) VALUES(2,%s,%s)',(i+1,i))
    db.commit()
    # Normalization aliases before the serializer cap must not lose actor 21.
    with db.cursor() as cur:cur.execute("UPDATE actors SET name='  Fixture actor 0  ' WHERE id=2")
    db.commit()
    full=dict(iter_associations(db,['2']));bounded=load_associations(db,['2'])
    assert len(full['2']['cast'])==30 and len(bounded['2']['cast'])==20
    row=next(r for r in snapshot['media'] if r['rating_key']==2)
    assert media_text(metadata(historical_raw(row,full['2'])))==media_text(metadata(historical_raw(row,bounded['2'])))
    before=source_signature(db)
    with db.cursor() as cur:cur.execute("UPDATE actors SET name='Changed beyond serializer limit' WHERE id=30")
    assert source_signature(db)!=before
    assert media_text(metadata(historical_raw(row,load_associations(db,['2'])['2'])))==media_text(metadata(historical_raw(row,bounded['2'])))
