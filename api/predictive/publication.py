"""Connection-private preparation followed by one public-table transaction.

No permanent staging populations or activation records. Readers keep seeing the
last committed recommendations throughout fitting and staging.
"""
from contextlib import contextmanager
import hashlib,json,os,subprocess,tempfile,tarfile,shutil
from psycopg2.extensions import parse_dsn,make_dsn
from pathlib import Path
from uuid import uuid4
from itertools import islice
import numpy as np
from pgvector import Vector
from psycopg2 import sql,OperationalError,InterfaceError
from psycopg2.extras import Json,execute_values
from .artifacts import current_config,load_model
from .contracts import ContractError,fingerprint
from .prepare import TABLES
from .source import read_snapshot
from .recovery import iter_associations

PUBLISHED=('media_embeddings','watch_embeddings','user_embeddings','training_data','recommendations',
           'shap_impact','shap_dimension_stats_current','shap_prediction_context','embedding_feature_config')
SOURCE=('library','watch_history','user_feedback','media_genres','genres','media_actors','actors','media_directors','directors')
LOCK=(184726,72)


@contextmanager
def writer_lock(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(%s,%s)',LOCK)
        if not cur.fetchone()[0]:raise ContractError('A predictive writer already owns the execution lock')
    conn.commit()
    try:yield
    finally:
        if not conn.closed:
            try:
                conn.rollback()
                with conn.cursor() as cur:cur.execute('SELECT pg_advisory_unlock(%s,%s)',LOCK)
                conn.commit()
            except (OperationalError,InterfaceError):pass  # Session loss releases its locks.


def source_signature(conn, *, snapshot=None):
    snapshot=read_snapshot(conn) if snapshot is None else snapshot
    # All association values still participate in drift detection. Never retain
    # the full million-row cast population or its serialized JSON in memory.
    digest=hashlib.sha256(b'public-source-signature/2\n')
    digest.update(fingerprint({k:snapshot[k] for k in ('media','events','feedback','legacy_watch_ids')}).encode())
    for key,row in iter_associations(conn,[str(r['rating_key']) for r in snapshot['media']]):
        digest.update(fingerprint([key,row]).encode())
    return digest.hexdigest()


def install_staging(conn):
    with conn.cursor() as cur:
        for table in PUBLISHED:
            if table=='embedding_feature_config':continue
            cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier('pg_temp','prepared_'+table)))
            cur.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE public.{}) ON COMMIT PRESERVE ROWS').format(
                sql.Identifier('prepared_'+table),sql.Identifier(table)))
    conn.commit()


def insert(conn,table,columns,values):
    if not values:return
    if table not in PUBLISHED:raise ContractError('Unknown published table')
    statement=sql.SQL('INSERT INTO {} ({}) VALUES %s').format(sql.Identifier('prepared_'+table),
        sql.SQL(',').join(map(sql.Identifier,columns))).as_string(conn)
    with conn.cursor() as cur:execute_values(cur,statement,values,page_size=128)


def stage_vectors(conn,media,watches,users):
    for kind,rows in [('media_text',media),('watch',watches),('user',users)]:
        table,key=TABLES[kind]
        items=iter(rows.items())
        while batch:=list(islice(items,128)):
            values=[]
            for item,row in batch:
                provenance={k:v for k,v in row.items() if k not in ('embedding','_cached_vector','_cached_input_hash')}
                values.append((item if kind=='user' else int(item),Vector(row['embedding']),Json(provenance)))
            insert(conn,table,(key,'embedding','provenance'),values)
            conn.commit()  # Only temporary rows; no public data changed.


def stage_training(conn,rows):
    columns=('id','username','rating_key','label','embedding','genre_tags','actor_tags','director_tags','release_year',
        'played_duration','media_duration','engagement_ratio','season_number','episode_number',
        'watch_sim','sample_weight','label_source','feedback_value','diagnostics')
    for start in range(0,len(rows),128):
        values=[]
        for index,r in enumerate(rows[start:start+128],start+1):
            diagnostics={key:r[key] for key in ('canonical_identity','identity_policy','supervision_policy','prediction_at',
                'label_available_at','observation_kind','feedback_provenance','auxiliary_feedback_count','auxiliary_feedback_conflicts')}
            diagnostics['dependency_hash']=r['dependency_hash'] if 'dependency_hash' in r else fingerprint(r['dependencies'])
            diagnostics['feature_sha256']=hashlib.sha256(np.asarray(r['embedding'],dtype='<f4').tobytes()).hexdigest()
            values.append((index,r['owner'],int(r['media_key']),r['label'],Vector(r['embedding']),','.join(r['genres']),
                '',','.join(r['directors']),r['year'],r['played_duration'],r['media_duration'],r['engagement_ratio'],
                r['season_number'],r['episode_number'],r['watch_sim'],r['sample_weight'],r['label_source'],r['feedback_value'],Json(diagnostics)))
        insert(conn,'training_data',columns,values);conn.commit()


def stage_predictions(conn,predictions,config,as_of):
    count=0;recommendations=[];shap=[];contexts=[]
    def flush():
        insert(conn,'recommendations',('id','username','rating_key','predicted_probability','rank','model_name','scored_at','cosine_similarity','explanation'),recommendations)
        insert(conn,'shap_impact',('user_id','rating_key','dimension','shap_value'),shap)
        insert(conn,'shap_prediction_context',('username','rating_key','config_id','model_version','scored_at'),contexts)
        conn.commit();recommendations.clear();shap.clear();contexts.clear()
    for row in predictions:
        count+=1
        recommendations.append((count,row['owner'],row['key'],row['probability'],row['rank'],
            'text-engagement:'+config['model_sha256'],as_of,row['cosine'],''))
        if row['shap']:
            contexts.append((row['owner'],row['key'],config['config_id'],config['model_sha256'],as_of))
            shap.extend((row['owner'],row['key'],i,v) for i,v in row['shap'])
        if len(recommendations)>=128:flush()
    flush()
    with conn.cursor() as cur:
        cur.execute('''INSERT INTO prepared_shap_dimension_stats_current
            (dimension,usage_count,sum_abs_shap,avg_abs_shap,combined_score,user_count,modified_at)
            SELECT dimension,count(*),sum(abs(shap_value)),avg(abs(shap_value)),sum(abs(shap_value))*ln(1+count(*)),
            count(DISTINCT user_id),now() FROM prepared_shap_impact GROUP BY dimension''')
    conn.commit()
    return count


def verify(conn,config,*,prepared=False):
    """Verify model checksum/layout and each vector's physical provenance."""
    load_model(config)
    prefix='pg_temp.prepared_' if prepared else 'public.'
    counts={}
    with conn.cursor() as cur:
        for kind,(table,key) in TABLES.items():
            with conn.cursor(name='predictor_verify_'+uuid4().hex) as stream:
                stream.execute(sql.SQL('SELECT embedding::text,provenance FROM {}').format(sql.Identifier('pg_temp' if prepared else 'public',
                    'prepared_'+table if prepared else table)))
                count=0
                while True:
                    batch=stream.fetchmany(128)
                    if not batch:break
                    for raw,p in batch:
                        values=np.asarray(json.loads(raw),dtype='<f4')
                        if (values.shape!=(768,) or not np.isfinite(values).all() or not p
                            or p.get('feature_space_id')!=config['feature_space_id']
                            or hashlib.sha256(values.tobytes()).hexdigest()!=p.get('vector_sha256')):
                            raise ContractError('Published vector provenance/shape mismatch')
                        count+=1
            counts[table]=count
        for table in ('training_data','recommendations','shap_impact','shap_prediction_context'):
            cur.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier('pg_temp' if prepared else 'public',
                'prepared_'+table if prepared else table)));counts[table]=cur.fetchone()[0]
        with conn.cursor(name='predictor_verify_training_'+uuid4().hex) as stream:
            stream.execute(f'SELECT embedding::text,diagnostics FROM {prefix}training_data')
            while True:
                batch=stream.fetchmany(128)
                if not batch:break
                for raw,diagnostics in batch:
                    values=np.asarray(json.loads(raw),dtype='<f4')
                    if values.shape!=(1536,) or not np.isfinite(values).all() or not diagnostics or hashlib.sha256(values.tobytes()).hexdigest()!=diagnostics.get('feature_sha256'):
                        raise ContractError('Training feature materialization differs from prepared vector')
        cur.execute(f'''SELECT count(*) FROM {prefix}recommendations WHERE predicted_probability NOT BETWEEN 0 AND 1''')
        if cur.fetchone()[0]:raise ContractError('Invalid prediction probabilities')
        cur.execute(f'''SELECT username,diagnostics->>'canonical_identity',count(*) FROM {prefix}training_data
            GROUP BY 1,2 HAVING count(*)>1 OR diagnostics->>'canonical_identity' IS NULL LIMIT 1''')
        if cur.fetchone():raise ContractError('Duplicate/missing canonical training identities')
        cur.execute(f'''SELECT 1 FROM {prefix}shap_prediction_context WHERE config_id<>%s OR model_version<>%s LIMIT 1''',
            (config['config_id'],config['model_sha256']))
        if cur.fetchone():raise ContractError('SHAP/model context mismatch')
    return counts


def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def pg_connection(conn):
    # Never put a database password in a subprocess argument or command log.
    values=parse_dsn(conn.dsn);environment=dict(os.environ)
    secret=values.pop('password',None)
    if secret is not None:environment['PGPASSWORD']=secret
    return make_dsn(**values),environment


def backup(conn,directory):
    """Keep exactly one ordinary backup of derived tables and the previous model."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    previous=current_config(conn)
    with tempfile.TemporaryDirectory(dir=directory,prefix='.backup-') as work:
        work=Path(work);dump=work/'published.dump'
        dsn,environment=pg_connection(conn)
        with dump.open('wb') as target:
            command=['pg_dump','--dbname',dsn,'--format=custom','--data-only','--no-owner','--no-privileges']
            for table in PUBLISHED:
                if table!='embedding_feature_config':command+=['--table','public.'+table]
            process=subprocess.run(command,stdout=target,stderr=subprocess.PIPE,timeout=300,env=environment)
            if process.returncode:raise ContractError('Last-good database backup failed; publication cancelled')
        manifest=dict(config=previous,dump_sha256=file_sha256(dump),
            counts=verify(conn,previous) if previous.get('architecture')=='public-text-predictor/1.0' else None)
        if previous.get('architecture')=='public-text-predictor/1.0':
            model=Path(previous['model_path']).read_bytes()
            if hashlib.sha256(model).hexdigest()!=previous['model_sha256']:raise ContractError('Last-good model file mismatch')
            (work/'model.joblib').write_bytes(model)
        (work/'manifest.json').write_text(json.dumps(manifest,sort_keys=True))
        archive=work/'backup.tar'
        with tarfile.open(archive,'w') as target:
            for name in ('published.dump','manifest.json','model.joblib'):
                if (work/name).exists():target.add(work/name,arcname=name)
        with archive.open('rb') as handle:os.fsync(handle.fileno())
        archive.chmod(0o600);os.replace(archive,directory/'last-good.tar')
        fd=os.open(directory,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)


def restore_last_good(conn,directory):
    """Explicit operator recovery only; no inference, source writes or labeling."""
    directory=Path(directory)
    with writer_lock(conn),tempfile.TemporaryDirectory(dir=directory,prefix='.restore-') as work:
        work=Path(work)
        with tarfile.open(directory/'last-good.tar','r') as archive:
            if set(archive.getnames())!={'published.dump','manifest.json','model.joblib'}:
                raise ContractError('Restoring a pre-cutover backup requires its original code and ordinary database restore procedure')
            for name in archive.getnames():
                member=archive.getmember(name)
                if not member.isfile():raise ContractError('Unexpected recovery archive member')
                with archive.extractfile(member) as source,(work/name).open('wb') as target:
                    shutil.copyfileobj(source,target,length=1024*1024)
        manifest=json.loads((work/'manifest.json').read_text());config=manifest['config']
        if file_sha256(work/'published.dump')!=manifest['dump_sha256']:
            raise ContractError('Recovery dump checksum mismatch')
        model=(work/'model.joblib').read_bytes()
        if hashlib.sha256(model).hexdigest()!=config['model_sha256']:raise ContractError('Recovery model checksum mismatch')
        # Restore the checksum-addressed file before its pointer can become active.
        fd,temp=tempfile.mkstemp(dir=Path(config['model_path']).parent,prefix='.restore-model-')
        with os.fdopen(fd,'wb') as handle:handle.write(model);handle.flush();os.fsync(handle.fileno())
        os.replace(temp,config['model_path']);load_model(config)
        dsn,environment=pg_connection(conn)
        restored=work/'restored.sql'
        with restored.open('wb') as output:
            process=subprocess.run(['pg_restore','--data-only','--file=-',str(work/'published.dump')],stdout=output,stderr=subprocess.PIPE,timeout=300,env=environment)
        if process.returncode:raise ContractError('Recovery dump cannot be decoded')
        before=work/'before.sql';after=work/'after.sql'
        with conn.cursor() as cur:
            locks=[sql.SQL('LOCK TABLE public.{} IN SHARE ROW EXCLUSIVE MODE;').format(sql.Identifier(t)).as_string(conn) for t in PUBLISHED]
            deletes=[sql.SQL('DELETE FROM public.{};').format(sql.Identifier(t)).as_string(conn) for t in PUBLISHED if t!='embedding_feature_config']
            before.write_text("SET LOCAL lock_timeout='8s';\n"+'\n'.join(locks+deletes))
            update=cur.mogrify("UPDATE public.embedding_feature_config SET active=false WHERE active; INSERT INTO public.embedding_feature_config(config_id,metadata,active) VALUES(%s,%s,true) ON CONFLICT(config_id) DO UPDATE SET metadata=EXCLUDED.metadata,active=true;",(config['config_id'],Json(config))).decode()
            checks=[]
            for table,count in manifest['counts'].items():
                checks.append(f"IF (SELECT count(*) FROM public.{table})<>{int(count)} THEN RAISE EXCEPTION 'Recovery population mismatch'; END IF;")
            after.write_text(update+'\nDO $$ BEGIN '+' '.join(checks)+' END $$;')
        conn.commit()  # Keep only the session writer lock while psql owns the restore transaction.
        process=subprocess.run(['psql','--dbname',dsn,'--no-psqlrc','--single-transaction','--set','ON_ERROR_STOP=1',
            '--file',str(before),'--file',str(restored),'--file',str(after)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=300,env=environment)
        if process.returncode:raise ContractError('Recovery transaction failed; prior publication remains committed')
        counts=verify(conn,config);conn.commit()
        if counts!=manifest['counts']:raise ContractError('Recovery verification differs from backup')
        return dict(verified=True,verification_only=True,counts=counts,model_sha256=config['model_sha256'])


def publish(conn,config,expected_config,expected_source,*,backup_directory,failpoint=lambda stage:None):
    expected=verify(conn,config,prepared=True)
    conn.commit()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='8s'")
            for table in SOURCE:
                cur.execute(sql.SQL('LOCK TABLE public.{} IN SHARE MODE').format(sql.Identifier(table)))
            for table in PUBLISHED:
                cur.execute(sql.SQL('LOCK TABLE public.{} IN SHARE ROW EXCLUSIVE MODE').format(sql.Identifier(table)))
            if current_config(conn)!=expected_config:raise ContractError('Incumbent changed during preparation')
            if source_signature(conn)!=expected_source:raise ContractError('Source data changed during preparation')
            if expected_config:backup(conn,backup_directory)
            failpoint('backed_up')
            for table in PUBLISHED:
                if table=='embedding_feature_config':continue
                if table in {value[0] for value in TABLES.values()}:
                    key=next(value[1] for value in TABLES.values() if value[0]==table)
                    live=sql.Identifier('public',table);staged=sql.Identifier('pg_temp','prepared_'+table);column=sql.Identifier(key)
                    cur.execute(sql.SQL('DELETE FROM {} live WHERE NOT EXISTS(SELECT 1 FROM {} staged WHERE staged.{}=live.{})').format(live,staged,column,column))
                    cur.execute(sql.SQL('UPDATE {} live SET embedding=staged.embedding,provenance=staged.provenance FROM {} staged WHERE live.{}=staged.{} AND (live.embedding IS DISTINCT FROM staged.embedding OR live.provenance IS DISTINCT FROM staged.provenance)').format(live,staged,column,column))
                    cur.execute(sql.SQL('INSERT INTO {} SELECT staged.* FROM {} staged WHERE NOT EXISTS(SELECT 1 FROM {} live WHERE live.{}=staged.{})').format(live,staged,live,column,column))
                else:
                    cur.execute(sql.SQL('DELETE FROM public.{}').format(sql.Identifier(table)))
                    cur.execute(sql.SQL('INSERT INTO public.{} SELECT * FROM {}').format(sql.Identifier(table),sql.Identifier('prepared_'+table)))
                failpoint(table)
            cur.execute('UPDATE public.embedding_feature_config SET active=false WHERE active')
            cur.execute('''INSERT INTO public.embedding_feature_config(config_id,metadata,active) VALUES(%s,%s,true)
                ON CONFLICT(config_id) DO UPDATE SET metadata=EXCLUDED.metadata,active=true''',(config['config_id'],Json(config)))
            if verify(conn,config)!=expected:raise ContractError('Public materialization differs from prepared counts')
            failpoint('verified')
        try:conn.commit()
        except (OperationalError,InterfaceError):
            raise ContractError('Publication commit outcome is uncertain; run read-only verify before retrying') from None
    except BaseException:
        try:conn.rollback()
        except (OperationalError,InterfaceError):pass
        raise
    return expected
