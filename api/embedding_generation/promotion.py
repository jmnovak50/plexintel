"""All database-visible populations switch in ONE transaction, with verified undo.

Legacy xgb_model.pkl is never replaced. V2 classifiers live in the generation
artifact table. Existing authenticated readers retain their tables/views; complete
validated generation values are materialized together at commit.
"""
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from functools import wraps

from psycopg2 import sql
from psycopg2.extras import Json

from .contracts import ContractError, fingerprint
from .model import load_bundle
from .runtime import ROOT, code_hash, publication_barrier
from .source import read_snapshot

TABLES=('media_embeddings','watch_embeddings','user_embeddings','training_data','recommendations',
        'shap_impact','shap_dimension_stats_current','shap_prediction_context','embedding_labels',
        'embedding_label_history','embedding_feature_config','app_settings')


def block_writers(function):
    @wraps(function)
    def invoke(*args,**kwargs):
        if not kwargs.get('approved'):
            raise ContractError('Explicit publication/rollback approval required')
        if kwargs.get('live_schema','public')=='pg_temp':return function(*args,**kwargs)
        with publication_barrier():return function(*args,**kwargs)
    return invoke


def live_table(name,schema):return sql.Identifier(schema,name)


def table_filter(name):
    return sql.SQL(" WHERE key IN ('ollama.embedding_model','training.engagement_threshold')") if name=='app_settings' else sql.SQL('')


def digest_rows(store,table,live_schema='public',promotion=None):
    if promotion:
        query=sql.SQL('SELECT row_data::text AS value FROM {} WHERE promotion_id=%s AND table_name=%s')
        args=(promotion,table);query=query.format(store.table('rollback_rows'))
    else:
        query=sql.SQL('SELECT to_jsonb(t)::text AS value FROM {} t{}').format(live_table(table,live_schema),table_filter(table));args=()
    hashes=[]
    with store.conn.cursor() as cur:
        cur.execute(query,args)
        while True:
            rows=cur.fetchmany(256)
            if not rows:break
            hashes.extend(hashlib.sha256(row[0].encode()).hexdigest() for row in rows)
    return len(hashes),hashlib.sha256('\n'.join(sorted(hashes)).encode()).hexdigest()


def archive(store,promotion,live_schema):
    counts={};hashes={}
    for table in TABLES:
        store.query(sql.SQL('INSERT INTO {}(promotion_id,table_name,row_data) SELECT %s,%s,to_jsonb(t) FROM {} t{}')
            .format(store.table('rollback_rows'),live_table(table,live_schema),table_filter(table)),(promotion,table))
        before=digest_rows(store,table,live_schema)
        saved=digest_rows(store,table,live_schema,promotion)
        if before!=saved:raise ContractError('Rollback archive verification failed')
        counts[table],hashes[table]=saved
    return counts,hashes


@block_writers
def promote(store,gid,*,approved=False,deployed_code=None,live_schema='public',source_check=None,legacy_model=None,failpoint=None):
    if live_schema not in ('public','pg_temp'):raise ContractError('Unexpected publication schema')
    generation=store.generation(gid)
    if not approved or generation['scope']!='full' or generation['status']!='validated':
        raise ContractError('Explicit GO/approval and a fully validated FULL generation are required')
    if deployed_code!=code_hash():raise ContractError('Approved deployed code hash differs from implementation')
    bundle,vocab=load_bundle(store,gid)
    legacy_model=Path(legacy_model or ROOT/'xgb_model.pkl')
    legacy_sha=hashlib.sha256(legacy_model.read_bytes()).hexdigest()
    publication=str(uuid4())
    store.conn.rollback()
    try:
        with store.conn.cursor() as cur:
            cur.execute("SET LOCAL TIME ZONE 'UTC'")
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute('SELECT pg_advisory_xact_lock(184725,42)')
            # Blocks source mutations and legacy materialization for the short
            # publication transaction; readers keep their prior MVCC snapshot.
            for table in TABLES:
                cur.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(live_table(table,live_schema)))
            control=store.query(sql.SQL('SELECT * FROM {} WHERE singleton FOR UPDATE').format(store.table('control')))
            if control['active_generation']!=generation['base_generation']:
                raise ContractError('Active generation changed since staging; rebase the shadow generation')
            if source_check is None:
                if live_schema!='public':raise ContractError('Test source check required')
                for table in ('library','watch_history','user_feedback'):
                    cur.execute(sql.SQL('LOCK TABLE {} IN SHARE MODE').format(live_table(table,'public')))
                current=fingerprint(read_snapshot(store.conn))
            else:current=source_check()
            if current!=generation['source_hash']:
                raise ContractError('Source inventory/history/feedback drifted; refresh and revalidate before cutover')
            counts,hashes=archive(store,publication,live_schema)
            store.query(sql.SQL('INSERT INTO {}(promotion_id,generation_id,previous_generation,archive_counts,archive_hashes,legacy_model_sha256) VALUES(%s,%s,%s,%s,%s,%s)')
                .format(store.table('promotions')),(publication,gid,control['active_generation'],Json(counts),Json(hashes),legacy_sha))
            for kind,table,key in [('media','media_embeddings','rating_key'),('watch','watch_embeddings','watch_id'),('user','user_embeddings','username')]:
                cur.execute(sql.SQL('INSERT INTO {} SELECT %s,%s,{}::text,embedding FROM {}')
                    .format(store.table('retained_vectors'),sql.Identifier(key),live_table(table,live_schema)),(publication,kind))
                retained=store.query(sql.SQL('SELECT count(*) AS n FROM {} WHERE promotion_id=%s AND kind=%s')
                    .format(store.table('retained_vectors')),(publication,kind))['n']
                if retained!=counts[table]:raise ContractError('Typed legacy vector retention count mismatch')
            if failpoint:failpoint('archived')
            for kind,table,key in [('media_text','media_embeddings','rating_key'),('watch','watch_embeddings','watch_id'),('user','user_embeddings','username')]:
                cur.execute(sql.SQL('DELETE FROM {}').format(live_table(table,live_schema)))
                cast=sql.SQL('item_key') if kind=='user' else sql.SQL('item_key::integer')
                cur.execute(sql.SQL('INSERT INTO {}({},embedding) SELECT {},embedding FROM {} WHERE generation_id=%s AND kind=%s AND status=\'succeeded\'')
                    .format(live_table(table,live_schema),sql.Identifier(key),cast,store.table('items')),(gid,kind))
            cur.execute(sql.SQL('DELETE FROM {}').format(live_table('training_data',live_schema)))
            cur.execute(sql.SQL('''INSERT INTO {}(username,rating_key,label,embedding,genre_tags,actor_tags,director_tags,
                release_year,played_duration,media_duration,engagement_ratio,season_number,episode_number,
                watch_sim,sample_weight,label_source,feedback_value)
                SELECT t.owner,t.media_key::integer,t.label,t.media_text || t.user_embedding,
                (SELECT string_agg(value,',') FROM jsonb_array_elements_text(t.features->'genres')),'',
                (SELECT string_agg(value,',') FROM jsonb_array_elements_text(t.features->'directors')),
                (t.features->>'year')::integer,(t.features->>'played_duration')::integer,
                (t.features->>'media_duration')::integer,(t.features->>'engagement_ratio')::double precision,
                (t.features->>'season_number')::integer,(t.features->>'episode_number')::integer,
                (t.features->>'watch_sim')::double precision,(t.features->>'sample_weight')::double precision,
                t.features->>'label_source',t.features->>'feedback_value' FROM {} t WHERE generation_id=%s''')
                .format(live_table('training_data',live_schema),store.table('modality_training_rows')),(gid,))
            cur.execute(sql.SQL('DELETE FROM {}').format(live_table('recommendations',live_schema)))
            cur.execute(sql.SQL('''INSERT INTO {}(username,rating_key,predicted_probability,model_name,scored_at,rank,cosine_similarity,explanation)
                SELECT owner,media_key::integer,probability,%s,%s::timestamptz,rank,cosine,''
                FROM {} WHERE generation_id=%s''').format(live_table('recommendations',live_schema),store.table('predictions')),
                ('embeddinggemma2:'+gid,generation['snapshot']['as_of'],gid))
            from api.services.dimension_config import build_independent_metadata
            config=build_independent_metadata(vocab.names,generation['validation']['model_sha256'],
                generation_id=gid,contract_hash=generation['contract_hash'],encoder_digest=generation['contract']['encoder']['digest'],serializer=generation['contract']['media_serializer'])
            if json.loads(bytes(store.artifact(gid,'dimensions.json')['data']))!=config:
                raise ContractError('Reviewed shadow dimension configuration differs from publication')
            config_id=config['config_id']
            active=store.query(sql.SQL('SELECT config_id FROM {} WHERE active').format(live_table('embedding_feature_config',live_schema)))
            if not active or active['config_id']!=config_id:
                # Exact historical labels remain in the verified archive. Never
                # expose their same-numbered interpretations as the new space.
                for table in ('embedding_labels','embedding_label_history'):
                    cur.execute(sql.SQL('DELETE FROM {}').format(live_table(table,live_schema)))
            cur.execute(sql.SQL('UPDATE {} SET active=false WHERE active').format(live_table('embedding_feature_config',live_schema)))
            cur.execute(sql.SQL('''INSERT INTO {}(config_id,metadata,active) VALUES(%s,%s,true)
                ON CONFLICT(config_id) DO UPDATE SET metadata=EXCLUDED.metadata,active=true''')
                .format(live_table('embedding_feature_config',live_schema)),(config_id,Json(config)))
            for table in ('shap_impact','shap_dimension_stats_current','shap_prediction_context'):
                cur.execute(sql.SQL('DELETE FROM {}').format(live_table(table,live_schema)))
            cur.execute(sql.SQL('''INSERT INTO {}(user_id,rating_key,dimension,shap_value,created_at,modified_at)
                SELECT owner,media_key::integer,(part->>0)::integer,(part->>1)::double precision,now(),now()
                FROM {} CROSS JOIN LATERAL jsonb_array_elements(shap) part WHERE generation_id=%s''')
                .format(live_table('shap_impact',live_schema),store.table('predictions')),(gid,))
            cur.execute(sql.SQL('''INSERT INTO {}(dimension,usage_count,sum_abs_shap,avg_abs_shap,combined_score,user_count,modified_at)
                SELECT dimension,count(*),sum(abs(shap_value)),avg(abs(shap_value)),
                sum(abs(shap_value))*ln(1+count(*)),count(DISTINCT user_id),now() FROM {} GROUP BY dimension''')
                .format(live_table('shap_dimension_stats_current',live_schema),live_table('shap_impact',live_schema)))
            cur.execute(sql.SQL('''INSERT INTO {}(username,rating_key,config_id,model_version,scored_at)
                SELECT owner,media_key::integer,%s,%s,%s::timestamptz FROM {} WHERE generation_id=%s AND shap<>'[]'::jsonb''')
                .format(live_table('shap_prediction_context',live_schema),store.table('predictions')),
                (config_id,generation['validation']['model_sha256'],generation['snapshot']['as_of'],gid))
            for key,value in [('ollama.embedding_model','embeddinggemma-2'),('training.engagement_threshold','0.60')]:
                cur.execute(sql.SQL('''INSERT INTO {}(key,raw_value,source) VALUES(%s,%s,'admin_ui')
                    ON CONFLICT(key) DO UPDATE SET raw_value=EXCLUDED.raw_value,source=EXCLUDED.source''')
                    .format(live_table('app_settings',live_schema)),(key,value))
            if failpoint:failpoint('materialized')
            store.query(sql.SQL("UPDATE {} SET status='retired' WHERE status='active'").format(store.table('generations')))
            store.query(sql.SQL("UPDATE {} SET status='active' WHERE generation_id=%s").format(store.table('generations')),(gid,))
            store.query(sql.SQL('UPDATE {} SET previous_generation=active_generation,active_generation=%s,legacy_model_sha256=%s,deployed_code_sha256=%s,updated_at=now() WHERE singleton')
                .format(store.table('control')),(gid,legacy_sha,deployed_code))
            # Recheck materialized vector counts before making any state visible.
            for kind,table in [('media_text','media_embeddings'),('watch','watch_embeddings'),('user','user_embeddings')]:
                count=store.query(sql.SQL('SELECT count(*) AS n FROM {}').format(live_table(table,live_schema)))['n']
                if count!=generation['expected'][kind]:raise ContractError('Materialized vector count mismatch')
        store.conn.commit()
        return dict(promotion_id=publication,generation_id=gid,rollback_archive_counts=counts)
    except Exception:
        store.conn.rollback();raise


@block_writers
def rollback(store,promotion_id,*,approved=False,live_schema='public',legacy_model=None,failpoint=None):
    if not approved:raise ContractError('Explicit rollback approval required')
    if live_schema not in ('public','pg_temp'):raise ContractError('Unexpected rollback schema')
    model=Path(legacy_model or ROOT/'xgb_model.pkl')
    try:
        with store.conn.cursor() as cur:
            cur.execute("SET LOCAL TIME ZONE 'UTC'")
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute('SELECT pg_advisory_xact_lock(184725,42)')
            record=store.query(sql.SQL('SELECT * FROM {} WHERE promotion_id=%s FOR UPDATE').format(store.table('promotions')),(promotion_id,))
            control=store.query(sql.SQL('SELECT * FROM {} WHERE singleton FOR UPDATE').format(store.table('control')))
            if not record or record['rolled_back_at'] or control['active_generation']!=record['generation_id']:
                raise ContractError('Rollback is not the active publication')
            if hashlib.sha256(model.read_bytes()).hexdigest()!=record['legacy_model_sha256']:
                raise ContractError('Legacy model artifact changed; rollback refused')
            for table in TABLES:
                saved=digest_rows(store,table,live_schema,promotion_id)
                if saved!=(record['archive_counts'][table],record['archive_hashes'][table]):
                    raise ContractError('Rollback archive is corrupt')
                cur.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(live_table(table,live_schema)))
            for table in TABLES:
                if table=='embedding_feature_config':
                    cur.execute(sql.SQL('UPDATE {} SET active=false WHERE active').format(live_table(table,live_schema)))
                    cur.execute(sql.SQL('''INSERT INTO {} SELECT (jsonb_populate_record(NULL::{},row_data)).* FROM {}
                        WHERE promotion_id=%s AND table_name=%s ON CONFLICT(config_id) DO UPDATE
                        SET metadata=EXCLUDED.metadata,active=EXCLUDED.active''').format(live_table(table,live_schema),live_table(table,live_schema),store.table('rollback_rows')),(promotion_id,table))
                    continue
                cur.execute(sql.SQL('DELETE FROM {}{}').format(live_table(table,live_schema),table_filter(table)))
                cur.execute(sql.SQL('''INSERT INTO {} OVERRIDING SYSTEM VALUE SELECT (jsonb_populate_record(NULL::{},row_data)).*
                    FROM {} WHERE promotion_id=%s AND table_name=%s ORDER BY ordinal''')
                    .format(live_table(table,live_schema),live_table(table,live_schema),store.table('rollback_rows')),(promotion_id,table))
                if digest_rows(store,table,live_schema)!=(record['archive_counts'][table],record['archive_hashes'][table]):
                    raise ContractError('Restored table differs from verified legacy archive')
            if failpoint:failpoint('restored')
            store.query(sql.SQL("UPDATE {} SET status='retired' WHERE generation_id=%s").format(store.table('generations')),(record['generation_id'],))
            if record['previous_generation']:
                store.query(sql.SQL("UPDATE {} SET status='active' WHERE generation_id=%s").format(store.table('generations')),(record['previous_generation'],))
            store.query(sql.SQL('UPDATE {} SET active_generation=%s,previous_generation=NULL,updated_at=now() WHERE singleton')
                .format(store.table('control')),(record['previous_generation'],))
            store.query(sql.SQL('UPDATE {} SET rolled_back_at=now() WHERE promotion_id=%s').format(store.table('promotions')),(promotion_id,))
        store.conn.commit()
    except Exception:
        store.conn.rollback();raise
