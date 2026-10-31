"""Transactional eligibility history, independent of discovery and ML jobs.

No startup bootstrap. The optional migration must be separately approved.
Policy and run records are append-only through this API; evaluations commit atomically.
"""
from contextlib import contextmanager
import os
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor, execute_values

from api.db.connection import connect_db
from api.db.seerr_discovery import require_unified_schema
from api.services.global_eligibility import ENGINE_VERSION, Policy, digest, evaluate_all, summarize

TABLES = ('eligibility_policies', 'eligibility_runs', 'eligibility_results')
SCHEMA_FIELDS = {
    'eligibility_policies': dict(version='bigint', created_at='timestamp with time zone',
                                created_by='text', policy_hash='text', policy='jsonb'),
    'eligibility_runs': dict(run_id='uuid', evaluated_at='timestamp with time zone', evaluated_by='text',
                             policy_version='bigint', engine_version='text', inventory_hash='text',
                             summary='jsonb', previous_run_id='uuid', changes='jsonb'),
    'eligibility_results': dict(run_id='uuid', media_type='text', tmdb_id='bigint', title='text',
                                outcome='text', reasons='jsonb', uncertainties='jsonb',
                                rule_outcomes='jsonb', input_snapshot='jsonb'),
}
SCHEMA_CONSTRAINTS = {
    ('eligibility_policies', 'p', 'PRIMARY KEY (version)'),
    ('eligibility_policies', 'c', "CHECK ((jsonb_typeof(policy) = 'object'::text))"),
    ('eligibility_runs', 'p', 'PRIMARY KEY (run_id)'),
    ('eligibility_runs', 'f', 'FOREIGN KEY (policy_version) REFERENCES eligibility_policies(version)'),
    ('eligibility_runs', 'f', 'FOREIGN KEY (previous_run_id) REFERENCES eligibility_runs(run_id)'),
    ('eligibility_results', 'p', 'PRIMARY KEY (run_id, media_type, tmdb_id)'),
    ('eligibility_results', 'f', 'FOREIGN KEY (run_id) REFERENCES eligibility_runs(run_id)'),
    ('eligibility_results', 'f', 'FOREIGN KEY (media_type, tmdb_id) REFERENCES seerr_discovered_titles(media_type, tmdb_id)'),
    ('eligibility_results', 'c', "CHECK ((media_type = ANY (ARRAY['movie'::text, 'tv'::text])))"),
    ('eligibility_results', 'c', "CHECK ((outcome = ANY (ARRAY['retained'::text, 'excluded'::text])))"),
    ('eligibility_results', 'c', 'CHECK ((tmdb_id > 0))'),
    *(('eligibility_results', 'c', f"CHECK ((jsonb_typeof({name}) = '{kind}'::text))")
      for name, kind in [('reasons', 'array'), ('uncertainties', 'array'),
                         ('rule_outcomes', 'array'), ('input_snapshot', 'object')]),
}
INPUT_SQL = """SELECT t.media_type,t.tmdb_id,t.title,t.runtime,t.original_language,t.genres,
t.metadata_fingerprint,t.metadata_source_key,t.first_discovered_at,t.last_enriched_at,
t.enrichment_status,t.field_states,t.first_discovery_run_id,
r.source_key AS discovery_source_key,r.parameters->>'source_id' AS discovery_source_id
FROM public.seerr_discovered_titles t JOIN public.seerr_discovery_runs r
ON r.run_id=t.first_discovery_run_id ORDER BY t.media_type,t.tmdb_id"""


class EligibilityError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def writes_enabled():
    return os.getenv('GLOBAL_ELIGIBILITY_WRITES_ENABLED', 'false').lower() == 'true'


@contextmanager
def transaction(write=False):
    if write and not writes_enabled():
        raise EligibilityError('eligibility_writes_disabled', 403)
    conn = connect_db()
    try:
        # Reads need a consistent multi-query view. Writers serialize on the
        # advisory lock, then capture the full inventory with ONE SELECT. Using
        # READ COMMITTED here ensures a just-committed policy is visible after
        # obtaining the lock, rather than retaining a pre-lock RR snapshot.
        conn.set_session(readonly=not write, isolation_level='READ COMMITTED' if write else 'REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='30s'")
            cur.execute("SET LOCAL lock_timeout='2s'")
            # Serialize policy/evaluation writes without affecting discovery locks.
            # A busy writer is an explicit conflict, never queued/retried.
            if write:
                cur.execute('SELECT pg_try_advisory_xact_lock(184725,41) AS acquired')
                if not cur.fetchone()['acquired']:
                    raise EligibilityError('eligibility_writer_busy')
            require_unified_schema(conn)
            yield cur
        if write:
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def installed(cur):
    cur.execute('''SELECT c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(%s)''', (list(TABLES),))
    relations = cur.fetchall()
    if not relations:
        return False
    def incompatible():
        raise EligibilityError('eligibility_schema_incompatible', 503)
    if sorted(tuple(r.values()) for r in relations) != sorted((t, 'r', False, False) for t in TABLES):
        incompatible()
    cur.execute('''SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,
        a.attidentity::text,a.attgenerated::text,pg_get_expr(d.adbin,d.adrelid)
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped''', (list(TABLES),))
    expected = {(table, name, kind, name not in ('title', 'previous_run_id'),
                 'a' if name == 'version' else '', '',
                 'now()' if name in ('created_at', 'evaluated_at') else None)
                for table, fields in SCHEMA_FIELDS.items() for name, kind in fields.items()}
    if {tuple(r.values()) for r in cur.fetchall()} != expected:
        incompatible()
    cur.execute("SELECT current_setting('search_path') AS path")
    path = cur.fetchone()['path']
    cur.execute("SELECT set_config('search_path','pg_catalog,public,pg_temp',true)")
    try:
        cur.execute('''SELECT c.relname,k.contype::text,pg_get_constraintdef(k.oid),k.convalidated,
            k.condeferrable,k.condeferred,COALESCE(i.indisvalid,true) AS index_valid,COALESCE(i.indisready,true) AS index_ready
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_index i ON i.indexrelid=k.conindid
            WHERE n.nspname='public' AND c.relname=ANY(%s) AND k.contype<>'n' ''', (list(TABLES),))
        constraints = [tuple(r.values()) for r in cur.fetchall()]
    finally:
        cur.execute("SELECT set_config('search_path',%s,true)", (path,))
    if ({r[:3] for r in constraints} != SCHEMA_CONSTRAINTS or
            any(r[3:] != (True, False, False, True, True) for r in constraints)):
        incompatible()
    cur.execute('''SELECT EXISTS(SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(%s)
        AND (NOT t.tgisinternal OR t.tgenabled NOT IN ('O','A'))) AS unexpected_triggers''', (list(TABLES),))
    if cur.fetchone()['unexpected_triggers']:
        incompatible()
    return True


def require_installed(cur):
    if not installed(cur):
        raise EligibilityError('eligibility_migration_required', 503)


def current_policy(cur):
    cur.execute('SELECT * FROM public.eligibility_policies ORDER BY version DESC LIMIT 1')
    row = cur.fetchone()
    if row:
        try:
            Policy.model_validate(row['policy'])
        except ValueError:
            raise EligibilityError('eligibility_policy_incompatible', 503) from None
        if digest(row['policy']) != row['policy_hash']:
            raise EligibilityError('eligibility_policy_incompatible', 503)
    return dict(row) if row else dict(version=0, policy=Policy().model_dump(), created_by=None,
                                     created_at=None, policy_hash=digest(Policy().model_dump()))


def inputs(cur):
    cur.execute(INPUT_SQL)
    # JSON-normalize dates before hashing AND persistence to make replay identical.
    import json
    return json.loads(json.dumps([dict(r) for r in cur.fetchall()], default=str))


def policy_payload():
    with transaction() as cur:
        ready = installed(cur)
        policy = current_policy(cur) if ready else dict(version=0, policy=Policy().model_dump())
        return dict(**policy, schema_installed=ready, writes_enabled=ready and writes_enabled(),
                    precedence='Any enabled exclusion wins. Retain and unknown never override exclusions.',
                    engine_version=ENGINE_VERSION)


def save_policy(policy: Policy, expected_version: int, actor: str):
    with transaction(write=True) as cur:
        require_installed(cur)
        current = current_policy(cur)
        if current['version'] != expected_version:
            raise EligibilityError('policy_version_conflict')
        payload = policy.model_dump()
        if current['version'] and current['policy_hash'] == digest(payload):
            return current
        cur.execute('INSERT INTO public.eligibility_policies(created_by,policy_hash,policy) VALUES(%s,%s,%s) RETURNING *',
                    (actor, digest(payload), Json(payload)))
        return dict(cur.fetchone())


def preview(policy: Policy):
    with transaction() as cur:
        inventory = inputs(cur)
    results = evaluate_all(inventory, policy)
    return dict(**summarize(results), inventory_hash=digest(inventory), policy_hash=digest(policy.model_dump()),
                persisted=False, examples=[dict(title=t['title'], **r) for t, r in zip(inventory, results) if r['outcome']=='excluded'][:20])


def compare(previous, results):
    old = {(r['media_type'], r['tmdb_id']): r for r in previous}
    new = {(r['media_type'], r['tmdb_id']): r for r in results}
    common = old.keys() & new.keys()
    return dict(added=len(new.keys()-old.keys()), no_longer_in_inventory=len(old.keys()-new.keys()),
                retained_to_excluded=sum(old[k]['outcome']=='retained' and new[k]['outcome']=='excluded' for k in common),
                excluded_to_retained=sum(old[k]['outcome']=='excluded' and new[k]['outcome']=='retained' for k in common),
                explanation_changed=sum(digest([old[k]['reasons'], old[k]['uncertainties']]) !=
                                        digest([new[k]['reasons'], new[k]['uncertainties']]) for k in common))


def run_evaluation(expected_version: int, actor: str):
    with transaction(write=True) as cur:
        require_installed(cur)
        current = current_policy(cur)
        if expected_version != current['version']:
            raise EligibilityError('policy_version_conflict')
        if current['version'] == 0:
            cur.execute('INSERT INTO public.eligibility_policies(created_by,policy_hash,policy) VALUES(%s,%s,%s) RETURNING *',
                        (actor, digest(current['policy']), Json(current['policy'])))
            current = dict(cur.fetchone())
        policy = Policy.model_validate(current['policy'])
        inventory = inputs(cur)
        results = [dict(title=t['title'], input_snapshot=t, **r)
                   for t, r in zip(inventory, evaluate_all(inventory, policy))]
        cur.execute('SELECT run_id FROM public.eligibility_runs ORDER BY evaluated_at DESC,run_id DESC LIMIT 1')
        previous = cur.fetchone()
        previous_id = previous['run_id'] if previous else None
        cur.execute('SELECT media_type,tmdb_id,outcome,reasons,uncertainties FROM public.eligibility_results WHERE run_id=%s', (previous_id,))
        changes = compare(cur.fetchall(), results)
        run_id = str(uuid4())
        summary = summarize(results)
        cur.execute('''INSERT INTO public.eligibility_runs(run_id,evaluated_by,policy_version,engine_version,inventory_hash,summary,previous_run_id,changes)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (run_id, actor, current['version'], ENGINE_VERSION, digest(inventory), Json(summary), previous_id, Json(changes)))
        run = dict(cur.fetchone())
        execute_values(cur, '''INSERT INTO public.eligibility_results
            (run_id,media_type,tmdb_id,title,outcome,reasons,uncertainties,rule_outcomes,input_snapshot) VALUES %s''',
                       [(run_id, r['media_type'], r['tmdb_id'], r['title'], r['outcome'],
                         Json(r['reasons']), Json(r['uncertainties']), Json(r['rule_outcomes']), Json(r['input_snapshot']))
                        for r in results], page_size=500)
        return run


def overview():
    with transaction() as cur:
        cur.execute("SELECT count(*) AS total,count(*) FILTER(WHERE media_type='movie') AS movies,count(*) FILTER(WHERE media_type='tv') AS tv FROM public.seerr_discovered_titles")
        inventory = dict(cur.fetchone())
        if not installed(cur):
            return dict(inventory=inventory, latest_run=None, schema_installed=False, unevaluated=inventory['total'])
        policy = current_policy(cur)
        cur.execute('SELECT * FROM public.eligibility_runs ORDER BY evaluated_at DESC,run_id DESC LIMIT 1')
        row = cur.fetchone()
        run = dict(row) if row else None
        cur.execute('''SELECT count(*) FILTER(WHERE e.tmdb_id IS NULL) AS unevaluated,
        count(*) FILTER(WHERE e.tmdb_id IS NOT NULL AND (e.input_snapshot->>'metadata_fingerprint' IS DISTINCT FROM t.metadata_fingerprint
          OR e.input_snapshot->>'metadata_source_key' IS DISTINCT FROM t.metadata_source_key)) AS changed_since_evaluation
        FROM public.seerr_discovered_titles t LEFT JOIN public.eligibility_results e
        ON e.media_type=t.media_type AND e.tmdb_id=t.tmdb_id AND e.run_id=%s''', (run['run_id'] if run else None,))
        return dict(inventory=inventory, latest_run=run, schema_installed=True, **dict(cur.fetchone()),
                    policy_changed=bool(run and run['policy_version'] != policy['version']))


def history(page=1, limit=25):
    with transaction() as cur:
        require_installed(cur)
        cur.execute('SELECT count(*) AS n FROM public.eligibility_runs')
        total = cur.fetchone()['n']
        cur.execute('''SELECT r.*,p.policy,p.policy_hash FROM public.eligibility_runs r
        JOIN public.eligibility_policies p ON p.version=r.policy_version
        ORDER BY r.evaluated_at DESC,r.run_id DESC LIMIT %s OFFSET %s''', (limit, (page-1)*limit))
        return dict(items=[dict(r) for r in cur.fetchall()], total=total, page=page, limit=limit)


def results(run_id=None, *, page=1, limit=25, search='', outcome=None, media_type=None,
            incomplete=False, sort='title', direction='asc'):
    if sort not in ('title', 'tmdb_id', 'outcome', 'media_type') or direction not in ('asc', 'desc'):
        raise ValueError('Invalid result sort')
    with transaction() as cur:
        require_installed(cur)
        if run_id is None:
            cur.execute('SELECT run_id FROM public.eligibility_runs ORDER BY evaluated_at DESC,run_id DESC LIMIT 1')
            row = cur.fetchone()
            run_id = row['run_id'] if row else None
        clauses, args = ['run_id=%s'], [str(run_id) if run_id else None]
        for col, value in [('outcome', outcome), ('media_type', media_type)]:
            if value:
                clauses.append(col+'=%s'); args.append(value)
        if search:
            clauses.append('title ILIKE %s')
            args.append('%'+search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')+'%')
        if incomplete:
            clauses.append("uncertainties<>'[]'::jsonb")
        where = ' AND '.join(clauses)
        cur.execute('SELECT count(*) AS n FROM public.eligibility_results WHERE '+where, args)
        total = cur.fetchone()['n']
        cur.execute(f'''SELECT * FROM public.eligibility_results WHERE {where}
            ORDER BY {sort} {direction} NULLS LAST,media_type,tmdb_id LIMIT %s OFFSET %s''', [*args, limit, (page-1)*limit])
        return dict(items=[dict(r) for r in cur.fetchall()], total=total, page=page, limit=limit, run_id=run_id)
