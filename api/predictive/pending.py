"""Only completed media/watch inference, never execution or publication state.

The daily worker owns the existing session writer lock. Each lookup finishes its
read transaction, and each new vector commits before preparation continues.
Cleanup belongs to the existing publication transaction after source checks.
"""
import hashlib
import json
import time

import numpy as np
from pgvector import Vector
from psycopg2 import sql

from .contracts import ContractError, vector

TABLE = 'pending_embedding_inference'
KINDS = {'media_text': ('media_embeddings', 'rating_key'),
         'watch': ('watch_embeddings', 'watch_id')}


def checked(values, provenance, input_hash, contract_hash, encoder_digest):
    """Return a validated candidate or a safe diagnostic; never weaken reuse."""
    if provenance is None:
        return None, 'missing'
    if (provenance.get('input_hash') != input_hash
            or provenance.get('modality_contract_hash') != contract_hash
            or provenance.get('encoder_digest') != encoder_digest):
        return None, 'incompatible'
    try:
        values = vector(values, unit=True)
        digest = hashlib.sha256(np.asarray(values, dtype='<f4').tobytes()).hexdigest()
        if provenance.get('vector_sha256') != digest:
            return None, 'invalid'
    except (ContractError, TypeError, ValueError, OverflowError):
        return None, 'invalid'
    return values, None


class PendingVectors:
    def __init__(self, conn):
        self.conn = conn
        self.lookup_seconds = 0.
        self.persistence_seconds = 0.
        self.persisted = 0

    def require_schema(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT to_regclass(%s)', ('public.' + TABLE,))
            if cur.fetchone()[0] is None:
                raise ContractError('Pending inference migration required: optional/simple_predictor/002_pending_inference.sql')
            cur.execute('SELECT modality,source_key,input_hash,modality_contract_hash,encoder_digest,embedding,vector_sha256 '
                        'FROM public.pending_embedding_inference LIMIT 0')
        self.conn.commit()

    def get(self, kind, key, input_hash, contract_hash, encoder_digest):
        if kind not in KINDS:
            raise ContractError('Only media/watch encoder results may be pending')
        start = time.perf_counter()
        try:
            with self.conn.cursor() as cur:
                cur.execute('''SELECT embedding::text,input_hash,modality_contract_hash,encoder_digest,vector_sha256
                    FROM public.pending_embedding_inference WHERE modality=%s AND source_key=%s''', (kind, int(key)))
                row = cur.fetchone()
            self.conn.commit()  # No read transaction may span the next encoder request.
            if row is None:
                return None, 'missing'
            provenance = dict(zip(('input_hash','modality_contract_hash','encoder_digest','vector_sha256'), row[1:]))
            return checked(json.loads(row[0]), provenance, input_hash, contract_hash, encoder_digest)
        finally:
            self.lookup_seconds += time.perf_counter() - start

    def save(self, kind, key, record):
        if kind not in KINDS:
            raise ContractError('Only media/watch encoder results may be pending')
        values, reason = checked(record['embedding'], record, record['input_hash'],
                                 record['modality_contract_hash'], record['encoder_digest'])
        if reason:
            raise ContractError('Invalid completed inference cannot be persisted')
        start = time.perf_counter()
        try:
            with self.conn.cursor() as cur:
                cur.execute('''INSERT INTO public.pending_embedding_inference
                    (modality,source_key,input_hash,modality_contract_hash,encoder_digest,embedding,vector_sha256)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(modality,source_key) DO UPDATE SET input_hash=EXCLUDED.input_hash,
                    modality_contract_hash=EXCLUDED.modality_contract_hash,encoder_digest=EXCLUDED.encoder_digest,
                    embedding=EXCLUDED.embedding,vector_sha256=EXCLUDED.vector_sha256''',
                    (kind,int(key),record['input_hash'],record['modality_contract_hash'],record['encoder_digest'],
                     Vector(values),record['vector_sha256']))
            self.conn.commit()
            self.persisted += 1
        finally:
            self.persistence_seconds += time.perf_counter() - start

    def population(self, kind):
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM public.pending_embedding_inference WHERE modality=%s', (kind,))
            count = cur.fetchone()[0]
        self.conn.commit()
        return count


def reconcile(conn, *, backup_verified):
    """Caller holds publication locks and has verified the complete prepared set.

    Never commit here: a failed publication rolls back *all* cleanup. Matching
    current vectors may be removed only after that population's backup passed
    verification. New candidates survive promotion until such backup coverage.
    """
    start = time.perf_counter()
    covered = obsolete = invalid = 0
    with conn.cursor() as cur:
        for kind, (table, key) in KINDS.items():
            if backup_verified:
                cur.execute(sql.SQL('''DELETE FROM public.pending_embedding_inference p USING public.{} v
                    WHERE p.modality=%s AND p.source_key=v.{}
                    AND p.input_hash=v.provenance->>'input_hash'
                    AND p.modality_contract_hash=v.provenance->>'modality_contract_hash'
                    AND p.encoder_digest=v.provenance->>'encoder_digest'
                    AND p.vector_sha256=v.provenance->>'vector_sha256' AND p.embedding=v.embedding''').format(
                        sql.Identifier(table), sql.Identifier(key)), (kind,))
                covered += cur.rowcount
            cur.execute(sql.SQL('''DELETE FROM public.pending_embedding_inference p WHERE p.modality=%s
                AND NOT EXISTS (SELECT 1 FROM pg_temp.{} v WHERE v.{}=p.source_key
                    AND p.input_hash=v.provenance->>'input_hash'
                    AND p.modality_contract_hash=v.provenance->>'modality_contract_hash'
                    AND p.encoder_digest=v.provenance->>'encoder_digest')''').format(
                        sql.Identifier('prepared_' + table), sql.Identifier(key)), (kind,))
            obsolete += cur.rowcount
        # A healthy published candidate can hide a corrupt pending duplicate
        # from lookup. Validate remaining cache records too, only at this safe
        # complete-publication boundary. This never inspects/removes public rows.
        with conn.cursor(name='pending_inference_cleanup') as stream:
            stream.execute('''SELECT modality,source_key,embedding::text,input_hash,modality_contract_hash,encoder_digest,vector_sha256
                FROM public.pending_embedding_inference''')
            while batch := stream.fetchmany(128):
                for kind, key, raw, input_hash, contract_hash, encoder_digest, checksum in batch:
                    provenance = dict(input_hash=input_hash,modality_contract_hash=contract_hash,
                                      encoder_digest=encoder_digest,vector_sha256=checksum)
                    _, reason = checked(json.loads(raw),provenance,input_hash,contract_hash,encoder_digest)
                    if reason:
                        cur.execute('DELETE FROM public.pending_embedding_inference WHERE modality=%s AND source_key=%s', (kind,key))
                        invalid += cur.rowcount
        cur.execute('SELECT count(*) FROM public.pending_embedding_inference')
        retained = cur.fetchone()[0]
    return dict(pending_backup_covered=covered, pending_obsolete=obsolete, pending_invalid_removed=invalid,
                pending_retained=retained, pending_cleanup_seconds=time.perf_counter()-start)
