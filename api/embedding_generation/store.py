"""Generation-isolated PostgreSQL persistence; caller owns the connection."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
from uuid import uuid4

from pgvector import Vector
from pgvector.psycopg2 import register_vector
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from .contracts import (ContractError, canonical, fingerprint, vector, KINDS,
                        REPRESENTATION, modality_contract, embedding_input_hash)


class Store:
    def __init__(self, conn, schema='embedding_v2'):
        if schema not in ('embedding_v2','pg_temp'):
            raise ContractError('Unexpected embedding schema')
        self.conn, self.schema = conn, schema
        register_vector(conn)

    def table(self, name):
        return sql.Identifier(self.schema,name)

    def query(self, statement, args=(), *, many=False):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(statement,args)
            if cur.description:
                return cur.fetchall() if many else cur.fetchone()

    @contextmanager
    def writer(self, generation_id):
        # Session lock spans checkpoint commits, released even on interruption.
        with self.conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))',('embedding-v2:'+generation_id,))
            if not cur.fetchone()[0]:
                raise ContractError('Generation already has a worker')
        try:
            yield
        finally:
            self.conn.rollback()
            with self.conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))',('embedding-v2:'+generation_id,))
            self.conn.commit()

    def generation(self, gid, *, include_snapshot=True):
        columns=sql.SQL('*') if include_snapshot else sql.SQL('generation_id,contract,contract_hash,scope,status,parent_id,base_generation,source_hash,expected,validation,created_at')
        value=self.query(sql.SQL('SELECT {} FROM {} WHERE generation_id=%s').format(columns,self.table('generations')),(gid,))
        if not value:
            raise ContractError('Unknown embedding generation')
        if fingerprint(value['contract']) != value['contract_hash']:
            raise ContractError('Generation contract checksum mismatch')
        return value

    def mutable(self, gid):
        generation=self.generation(gid)
        if generation['status'] not in ('building',):
            raise ContractError('Published/validated generation is immutable; fork a child')
        return generation

    def assert_mutable(self,gid):
        if self.generation(gid,include_snapshot=False)['status']!='building':
            raise ContractError('Published/validated generation is immutable; fork a child')

    def create(self, specification, snapshot, *, scope, parent=None, gid=None,progress=lambda value:None):
        from .history_scope import partition_history
        from .contracts import WATCH_SCOPE_VERSION
        if specification.get('watch_scope')!=WATCH_SCOPE_VERSION:
            raise ContractError('Unsupported historical watch-scope contract')
        if specification.get('representation')!=REPRESENTATION:
            raise ContractError('Independent media representation is required')
        source_hash=snapshot.get('_db_hash') or fingerprint(snapshot)
        snapshot=partition_history(snapshot)
        if scope=='full' and not snapshot['watch_coverage']['existing_vector_coverage_verified']:
            raise ContractError('Full generation requires verified existing-vector membership')
        if parent:
            previous=self.generation(parent,include_snapshot=False)
            if previous['scope']!='full' or previous['status'] not in ('active','validated','retired') or previous['contract'].get('representation')!=REPRESENTATION:
                raise ContractError('Reuse requires a fully validated independent EmbeddingGemma 2 parent')
        gid=gid or str(uuid4())
        profiles=self.profile_sources(snapshot,specification['profile_threshold'])
        expected=dict(media_text=len(snapshot['media']),media_poster=len(snapshot['media']),watch=len(snapshot['events']),user=len(profiles))
        base=self.query(sql.SQL('SELECT active_generation FROM {} WHERE singleton').format(self.table('control')))
        self.query(sql.SQL('''INSERT INTO {}(generation_id,contract,contract_hash,scope,parent_id,base_generation,source_hash,snapshot,expected)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''').format(self.table('generations')),
            (gid,Json(specification),fingerprint(specification),scope,parent,base['active_generation'],source_hash,Json(snapshot),Json(expected)))
        total=2*len(snapshot['media'])+len(snapshot['events'])+len(profiles);completed=0
        progress(dict(generation_id=gid,expected=total,completed=0,failed=0))
        for row in snapshot['media']:
            self.upsert_source(gid,'media_text',str(row['rating_key']),row)
            self.upsert_source(gid,'media_poster',str(row['rating_key']),dict(rating_key=row['rating_key']))
            completed+=2
            if completed%32==0:progress(dict(generation_id=gid,expected=total,completed=completed,failed=0))
        for row in snapshot['events']:
            self.upsert_source(gid,'watch',str(row['watch_id']),row,owner=row['username'],media_key=str(row['rating_key']),
                semantic_hash=fingerprint({k:v for k,v in row.items() if k!='observed_at'}))
            completed+=1
            if completed%32==0:progress(dict(generation_id=gid,expected=total,completed=completed,failed=0))
        for owner,source in profiles.items():
            self.upsert_source(gid,'user',owner,source,owner=owner);completed+=1
        self.conn.commit()
        progress(dict(generation_id=gid,expected=total,completed=completed,failed=0))
        return gid

    @staticmethod
    def profile_sources(snapshot,threshold):
        from .backfill import qualifying_profiles
        media={str(row['rating_key']):dict(source=row) for row in snapshot['media']}
        profiles=qualifying_profiles(snapshot['events'],media,threshold)
        return {owner:dict(qualifying_keys=keys,history_hash=fingerprint([e for e in snapshot['events'] if e['username']==owner]))
                for owner,keys in profiles.items()}

    def items(self, gid, kind, *, pending=False):
        clause=sql.SQL(" AND status NOT IN ('succeeded','missing')") if pending else sql.SQL('')
        return self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND kind=%s{} ORDER BY item_key')
            .format(self.table('items'),clause),(gid,kind),many=True)

    def batches(self,gid,kind,*,size=16,pending=False):
        if not 1<=size<=128:raise ContractError('Batch size outside 1..128')
        key=''
        clause=sql.SQL(" AND status NOT IN ('succeeded','missing')") if pending else sql.SQL('')
        while True:
            rows=self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND kind=%s AND item_key>%s{} ORDER BY item_key LIMIT %s')
                .format(self.table('items'),clause),(gid,kind,key,size),many=True)
            if not rows:return
            yield rows
            key=rows[-1]['item_key']

    def upsert_source(self, gid, kind, key, source, *, owner=None, media_key=None, semantic_hash=None):
        self.assert_mutable(gid)
        digest=semantic_hash or fingerprint(source)
        old=self.query(sql.SQL('SELECT semantic_hash FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s')
            .format(self.table('items')),(gid,kind,key))
        self.query(sql.SQL('''INSERT INTO {}(generation_id,kind,item_key,owner,media_key,source,semantic_hash)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(generation_id,kind,item_key) DO UPDATE SET
            source=EXCLUDED.source,semantic_hash=EXCLUDED.semantic_hash,owner=EXCLUDED.owner,media_key=EXCLUDED.media_key,
            status=CASE WHEN {}.semantic_hash=EXCLUDED.semantic_hash THEN {}.status ELSE 'pending' END,
            embedding=CASE WHEN {}.semantic_hash=EXCLUDED.semantic_hash THEN {}.embedding ELSE NULL END''')
            .format(self.table('items'),*[sql.Identifier('items')]*4),
            (gid,kind,key,owner,media_key,Json(source),digest))
        if old and old['semantic_hash']!=digest:
            self.invalidate_children(gid,kind,key)
        return not old or old['semantic_hash']!=digest

    def invalidate_children(self, gid, kind, key, *, poster_only=False):
        # Only text rows have watch/profile descendants. Poster changes still
        # invalidate downstream artifacts, never text-derived user/watch vectors.
        clause=sql.SQL(" AND child_kind<>'watch'") if poster_only else sql.SQL('')
        rows=self.query(sql.SQL('SELECT child_kind,child_key FROM {} WHERE generation_id=%s AND parent_kind=%s AND parent_key=%s{}')
            .format(self.table('dependencies'),clause),(gid,kind,key),many=True)
        for row in rows:
            self.query(sql.SQL("UPDATE {} SET status='pending',embedding=NULL WHERE generation_id=%s AND kind=%s AND item_key=%s")
                .format(self.table('items')),(gid,row['child_kind'],row['child_key']))
            self.invalidate_children(gid,row['child_kind'],row['child_key'])
        for name in ('artifacts','modality_training_rows','predictions'):
            self.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(self.table(name)),(gid,))

    def complete(self, gid, kind, key, values, input_hash, *, poster=None, timing=None, dependencies=(), origin=None):
        self.assert_mutable(gid)
        if kind not in KINDS or kind.startswith('media_') and dependencies or any(k!='media_text' for k,_,_ in dependencies):
            raise ContractError('Unsupported/cyclic dependency kind')
        values=vector(values,unit=kind!='user')
        specification=modality_contract(self.generation(gid,include_snapshot=False)['contract'],kind)
        old=self.query(sql.SQL('SELECT input_hash FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s')
            .format(self.table('items')),(gid,kind,key))
        if not old:
            raise ContractError('Completion lacks expected source record')
        if old['input_hash'] and old['input_hash']!=input_hash:
            self.invalidate_children(gid,kind,key)
        self.query(sql.SQL('''UPDATE {} SET status='succeeded',embedding=%s,input_hash=%s,poster=%s,
            timing=%s,generated_at=now(),attempts=attempts+1,error=NULL,origin_generation=%s,
            modality_contract_hash=%s,provenance=%s
            WHERE generation_id=%s AND kind=%s AND item_key=%s''').format(self.table('items')),
            (Vector(values),input_hash,Json(poster),Json(timing),origin or gid,fingerprint(specification),
             Json(dict(**specification,output_dimensions=768,normalization_state=specification['normalization'])),gid,kind,key))
        self.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s AND child_kind=%s AND child_key=%s')
            .format(self.table('dependencies')),(gid,kind,key))
        for parent_kind,parent_key,parent_hash in dependencies:
            parent=self.query(sql.SQL('SELECT status,input_hash,semantic_hash FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s')
                .format(self.table('items')),(gid,parent_kind,parent_key))
            expected=parent['semantic_hash'] if kind=='watch' else parent['input_hash']
            if parent['status']!='succeeded' or expected!=parent_hash:
                raise ContractError('Dependency generation/hash is incomplete or incompatible')
            self.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s)').format(self.table('dependencies')),
                (gid,kind,key,parent_kind,parent_key,parent_hash))

    def complete_missing_poster(self,gid,key,input_hash,poster,*,origin=None):
        self.assert_mutable(gid)
        specification=modality_contract(self.generation(gid,include_snapshot=False)['contract'],'media_poster')
        self.invalidate_children(gid,'media_poster',key)
        self.query(sql.SQL("""UPDATE {} SET status='missing',embedding=NULL,input_hash=%s,poster=%s,
            timing=%s,generated_at=now(),attempts=attempts+1,error=NULL,origin_generation=%s,
            modality_contract_hash=%s,provenance=%s WHERE generation_id=%s AND kind='media_poster' AND item_key=%s""")
            .format(self.table('items')),(input_hash,Json(poster),Json(dict(inherited=bool(origin),inference_skipped='missing_art')),
                origin or gid,fingerprint(specification),Json(dict(**specification,output_dimensions=None,normalization_state='missing')),
                gid,key))

    def fail(self, gid, kind, key, code):
        self.assert_mutable(gid)
        self.query(sql.SQL("UPDATE {} SET status='failed',embedding=NULL,error=%s,attempts=attempts+1 WHERE generation_id=%s AND kind=%s AND item_key=%s")
            .format(self.table('items')),(code,gid,kind,key))

    def log_inference(self,gid,kind,key,input_hash,status,stats):
        self.query(sql.SQL('INSERT INTO {}(request_id,generation_id,kind,item_key,input_hash,status,stats) VALUES(%s,%s,%s,%s,%s,%s,%s)')
            .format(self.table('inference_requests')),(str(uuid4()),gid,kind,key,input_hash,status,Json(stats)))

    def preparation(self,gid,key,stage,*,status=None,content_hash=None,provenance=None,timing=None):
        if status is None:
            return self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND item_key=%s AND stage=%s')
                .format(self.table('preparations')),(gid,key,stage))
        self.assert_mutable(gid)
        self.query(sql.SQL('''INSERT INTO {}(generation_id,item_key,stage,status,content_hash,provenance,timing)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(generation_id,item_key,stage) DO UPDATE SET
            status=EXCLUDED.status,content_hash=EXCLUDED.content_hash,provenance=EXCLUDED.provenance,
            timing=EXCLUDED.timing,prepared_at=now()''').format(self.table('preparations')),
            (gid,key,stage,status,content_hash,Json(provenance or {}),Json(timing or {})))
        self.query(sql.SQL('INSERT INTO {}(attempt_id,generation_id,item_key,stage,status,content_hash,timing) VALUES(%s,%s,%s,%s,%s,%s,%s)')
            .format(self.table('preparation_attempts')),(str(uuid4()),gid,key,stage,status,content_hash,Json(timing or {})))

    def cache(self,key,value=None):
        if value is None:
            row=self.query(sql.SQL('SELECT provenance FROM {} WHERE source_id=%s').format(self.table('poster_cache')),(key,))
            return row['provenance'] if row else None
        self.query(sql.SQL('INSERT INTO {} VALUES(%s,%s) ON CONFLICT(source_id) DO UPDATE SET provenance=EXCLUDED.provenance')
            .format(self.table('poster_cache')),(key,Json(value)))

    def inherited(self,gid,kind,key,input_hash):
        generation=self.generation(gid,include_snapshot=False)
        if not generation['parent_id']:return None
        parent=self.generation(generation['parent_id'],include_snapshot=False)
        specification=modality_contract(generation['contract'],kind)
        if modality_contract(parent['contract'],kind)!=specification:return None
        return self.query(sql.SQL("SELECT * FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s AND status IN ('succeeded','missing') AND input_hash=%s AND modality_contract_hash=%s")
            .format(self.table('items')),(generation['parent_id'],kind,key,input_hash,fingerprint(specification)))

    def counts(self, gid):
        groups=self.query(sql.SQL('SELECT kind,status,count(*) AS n FROM {} WHERE generation_id=%s GROUP BY kind,status')
            .format(self.table('items')),(gid,),many=True)
        expected=self.generation(gid,include_snapshot=False)['expected']
        result={kind:dict(expected=expected[kind],processed=0,succeeded=0,missing=0,failed=0,pending=0) for kind in expected}
        for row in groups:
            result[row['kind']][row['status']]=row['n']
            if row['status']!='pending':result[row['kind']]['processed']+=row['n']
        return result

    def artifact(self,gid,name,data=None,metadata=None):
        if data is None:
            row=self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND name=%s').format(self.table('artifacts')),(gid,name))
            if not row or hashlib.sha256(bytes(row['data'])).hexdigest()!=row['sha256']:
                raise ContractError('Missing/corrupt generation artifact: '+name)
            return row
        self.assert_mutable(gid)
        digest=hashlib.sha256(data).hexdigest()
        self.query(sql.SQL('''INSERT INTO {} VALUES(%s,%s,%s,%s,%s) ON CONFLICT(generation_id,name)
            DO UPDATE SET sha256=EXCLUDED.sha256,metadata=EXCLUDED.metadata,data=EXCLUDED.data''').format(self.table('artifacts')),
            (gid,name,digest,Json(metadata or {}),data))
        return digest

    def validate(self,gid, *, quality_go=False, missing_art_limit=0,progress=lambda value:None):
        with self.writer(gid):
            return self._validate(gid,quality_go=quality_go,missing_art_limit=missing_art_limit,progress=progress)

    def _validate(self,gid, *, quality_go=False, missing_art_limit=0,progress=lambda value:None):
        from .validation import validate_generation
        return validate_generation(self,gid,quality_go=quality_go,missing_art_limit=missing_art_limit,progress=progress)
