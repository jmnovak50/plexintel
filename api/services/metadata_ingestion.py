"""Normalized metadata acceptance and explicit repairs. No import-time IO.

All writes use caller-owned transactions; remote retrieval belongs to adapters.
Predictive metadata/serializers and their independent lifecycle are untouched.
"""
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from uuid import uuid4, UUID

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
from api.predictive.recovery import stable_identity, IdentityError

CONTRACT = 'plexintel.metadata-ingestion/1'
LOCK = (184727, 73)
KINDS = {'movie', 'show', 'season', 'episode'}
FIELDS = ('title','year','duration','media_type','summary','rating','added_at',
          'season_number','episode_number','parent_rating_key','show_rating_key',
          'show_title','episode_title','episode_summary','thumb_path',
          'parent_thumb_path','grandparent_thumb_path','plex_guid')
RELATIONS = {'actors': ('media_actors','actors','actor_id'),
             'directors': ('media_directors','directors','director_id'),
             'genres': ('media_genres','genres','genre_id')}


class MetadataError(ValueError):
    pass


class IncompleteMetadata(MetadataError):
    """A requested title lacks source data; never an accepted metadata record."""
    def __init__(self, reason, *, rating_key, field):
        super().__init__(reason)
        self.rating_key, self.field = rating_key, field


class Conflict(MetadataError):
    pass


class Busy(MetadataError):
    pass


class CommitUncertain(MetadataError):
    def __init__(self, key, operation_id, resolved):
        super().__init__('commit_connection_lost')
        self.rating_key, self.operation_id, self.resolved = key, str(operation_id), resolved


def commit_metadata(conn, key, operation_id):
    """A lost acknowledgement is not evidence of rollback. Never retry writes."""
    try:
        conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        resolved='unknown'
        try:
            check=psycopg2.connect(conn.dsn)
            try:
                check.set_session(readonly=True)
                with check.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='5s'")
                    # Same lock as the original write; if acquired, its commit
                    # has completed. A busy lock cannot prove absence.
                    writer_lock(cur)
                    cur.execute("SELECT 1 FROM public.metadata_ingestion_events WHERE operation_id=%s AND rating_key=%s AND outcome='applied'", (str(operation_id),key))
                    resolved='applied' if cur.fetchone() else 'not_applied'
            finally: check.rollback(); check.close()
        except Exception:
            pass
        print(json.dumps(dict(event='metadata_commit_resolution',rating_key=key,
                              operation_id=str(operation_id),status=resolved)),flush=True)
        raise CommitUncertain(key,operation_id,resolved) from None


def error_code(exc):
    value = str(exc) if isinstance(exc, MetadataError) else type(exc).__name__
    return value[:100] if value.replace('_','').isalnum() else type(exc).__name__


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             default=lambda x: x.isoformat() if isinstance(x, datetime) else str(x),
                             allow_nan=False).encode()).hexdigest()


def json_value(value):
    return json.loads(json.dumps(value,default=lambda x:x.isoformat() if isinstance(x,datetime) else str(x),allow_nan=False))


def integer(value, *, required=False):
    if value is None or value == '':
        if required: raise MetadataError('missing_integer')
        return None
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if math.isfinite(value) and int(value)==value: return int(value)
        raise MetadataError('invalid_integer')
    if isinstance(value, bool) or not str(value).lstrip('-').isdigit():
        raise MetadataError('invalid_integer')
    return int(value)


def identity(kind, guid):
    try: return stable_identity(kind, guid)
    except (IdentityError, TypeError) as exc: raise MetadataError('unresolved_identity') from exc


def _collection(raw, name):
    # Tautulli's optional descriptive collections can be omitted/unavailable.
    # Preserve that limitation instead of silently claiming an observed empty set.
    value = raw.get(name)
    if value is None: return [], 'unavailable'
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise MetadataError('malformed_' + name)
    return value, 'present' if value else 'empty'


def normalize_metadata(requested_key, raw, *, show=None):
    """Tautulli adapter; presence evidence is retained before legacy fallback."""
    if not isinstance(raw, dict): raise MetadataError('invalid_metadata_envelope')
    key = integer(requested_key, required=True)
    if key <= 0 or integer(raw.get('rating_key'), required=True) != key:
        raise MetadataError('requested_key_mismatch')
    kind = raw.get('media_type')
    if kind not in KINDS: raise MetadataError('unsupported_media_kind')
    missing = []
    if raw.get('title') is None or isinstance(raw.get('title'), str) and not raw['title'].strip():
        missing.append(('missing_title','title'))
    elif not isinstance(raw.get('title'), str): raise MetadataError('missing_title')
    try:
        identity(kind, raw.get('guid'))
    except MetadataError:
        guid = raw.get('guid')
        if guid is None or isinstance(guid, str) and (not guid.strip() or guid == f'local://{key}'):
            missing.append(('unresolved_identity','guid'))
        else: raise
    def required_number(field):
        if raw.get(field) in (None, ''):
            missing.append(('missing_integer',field)); return None
        return integer(raw[field], required=True)
    item = dict(rating_key=key, title=raw.get('title'), media_type=kind,
                plex_guid=raw.get('guid'), summary=raw.get('summary'), rating=raw.get('rating'),
                year=integer(raw.get('year')) if raw.get('year') else None,
                duration=integer(raw.get('duration')) or None,
                added_at=integer(raw.get('added_at')), parent_rating_key=integer(raw.get('parent_rating_key')),
                grandparent_title=raw.get('grandparent_title'), parent_title=raw.get('parent_title'),
                thumb_path=raw.get('thumb'), parent_thumb_path=raw.get('parent_thumb'),
                grandparent_thumb_path=raw.get('grandparent_thumb'),
                season_number=None, episode_number=None, show_rating_key=None)
    for field in ('summary','thumb_path','parent_thumb_path','grandparent_thumb_path'):
        if item[field] is not None and not isinstance(item[field], str):
            raise MetadataError('invalid_' + field)
    if kind in ('movie','episode') and item['duration'] in (None, 0):
        missing.append(('missing_runtime','duration'))
    elif kind in ('movie','episode') and item['duration'] < 0:
        raise MetadataError('missing_runtime')
    if kind == 'episode':
        item.update(season_number=required_number('parent_media_index'),
                    episode_number=required_number('media_index'),
                    show_rating_key=required_number('grandparent_rating_key'))
    elif kind == 'season':
        item.update(season_number=required_number('media_index'),
                    show_rating_key=item['parent_rating_key'])
    elif kind == 'show': item['show_rating_key'] = key
    if kind in ('season','episode'):
        for field in ('parent_rating_key', 'show_rating_key'):
            if item[field] is None:
                missing.append(('missing_parent',field))
            elif item[field] <= 0: raise MetadataError('missing_parent')
            elif item[field] == key: raise MetadataError('cyclic_parent')
        if (item['season_number'] is not None and item['season_number'] < 0) or (kind == 'episode' and item['episode_number'] is not None and item['episode_number'] < 0):
            raise MetadataError('invalid_episode_number')
    evidence = dict(adapter_contract=CONTRACT, requested_key=key, media_type=kind, plex_guid=raw.get('guid'),
                    observed_at=datetime.now(timezone.utc).isoformat(), presence={}, scopes={})
    for field in ('summary','year','duration','rating','added_at','thumb'):
        v = raw.get(field)
        if field in ('year','duration') and item[field] is None: v=None
        evidence['presence'][field] = 'unavailable' if v is None else ('empty' if v == '' else 'present')
    for name in RELATIONS:
        values, presence = _collection(raw, name)
        evidence['presence'][name] = presence
        evidence['scopes'][name] = dict(scope='direct', source_key=key)
        if name in ('actors','genres') and not values and kind in ('season','episode') and show:
            if show.get('media_type') != 'show' or int(show['rating_key']) != item['show_rating_key']:
                raise MetadataError('series_identity_mismatch')
            values = show.get(name) or []
            evidence['scopes'][name] = dict(scope='series', source_key=item['show_rating_key'])
        item[name] = values
    if show: evidence['show_guid'] = show.get('plex_guid')
    if missing:
        # Missing data must never hide a conflicting/malformed supplied field.
        reason,field = missing[0]
        raise IncompleteMetadata(reason,rating_key=key,field=field)
    item['_ingestion_evidence'] = evidence
    return item


def row_dict(cur, row):
    if row is None: return None
    return dict(row) if isinstance(row, Mapping) else dict(zip((x.name for x in cur.description), row))


def validate_core(item):
    key = integer(item.get('rating_key'), required=True)
    if key <= 0 or not isinstance(item.get('title'), str) or not item['title'].strip():
        raise MetadataError('missing_title')
    identity(item.get('media_type'), item.get('plex_guid'))
    if item['media_type'] in ('movie','episode') and (integer(item.get('duration')) or 0) <= 0:
        raise MetadataError('missing_runtime')
    if item['media_type'] in ('season','episode'):
        for field in ('parent_rating_key','show_rating_key'):
            if integer(item.get(field), required=True) <= 0: raise MetadataError('missing_parent')
        if integer(item.get('season_number'), required=True) < 0: raise MetadataError('invalid_episode_number')
        if item['media_type']=='episode' and integer(item.get('episode_number'), required=True) < 0:
            raise MetadataError('invalid_episode_number')


def validate_candidate(item):
    validate_core(item)
    key=integer(item['rating_key'],required=True)
    evidence = item.get('_ingestion_evidence') or {}
    if evidence.get('adapter_contract') != CONTRACT or evidence.get('requested_key') != key or evidence.get('media_type') != item['media_type'] or evidence.get('plex_guid') != item['plex_guid']:
        raise MetadataError('unvalidated_candidate')
    if not set(RELATIONS) <= set(evidence.get('presence', {})) or not set(RELATIONS) <= set(evidence.get('scopes', {})):
        raise MetadataError('missing_source_presence')
    for name in RELATIONS: _collection(item, name)


def require_schema(cur):
    cur.execute("SELECT to_regclass('public.metadata_ingestion_events') AS relation")
    if row_dict(cur, cur.fetchone())['relation'] is None:
        raise MetadataError('metadata_contract_migration_required')


def writer_lock(cur):
    # Bound waits on non-cooperating row/dictionary writers without relaxing a
    # caller's stricter limit. This is a transaction-local lock guard, not an SLO.
    cur.execute("""SELECT set_config('lock_timeout',
        CASE WHEN current_setting('lock_timeout')::interval=interval '0'
               OR current_setting('lock_timeout')::interval>interval '5 seconds'
        THEN '5s' ELSE current_setting('lock_timeout') END,true)""")
    cur.execute('SELECT pg_try_advisory_xact_lock(%s,%s) AS acquired', LOCK)
    if not row_dict(cur, cur.fetchone())['acquired']: raise Busy('metadata_writer_busy')


def snapshot(cur, rating_key, *, lock=False):
    cur.execute('SELECT * FROM public.library WHERE rating_key=%s' + (' FOR UPDATE' if lock else ''), (rating_key,))
    result = row_dict(cur, cur.fetchone())
    if result is None: return None
    for name, (links, dictionary, fk) in RELATIONS.items():
        order = ',m.cast_order' if name == 'actors' else ''
        cur.execute(sql.SQL('SELECT d.id,d.name{} FROM public.{} m JOIN public.{} d ON d.id=m.{} WHERE m.media_id=%s ORDER BY d.id').format(
            sql.SQL(order), sql.Identifier(links), sql.Identifier(dictionary), sql.Identifier(fk)), (rating_key,))
        result[name] = [row_dict(cur, x) for x in cur.fetchall()]
    return result


def parent_metadata(cur, rating_key):
    item = snapshot(cur, rating_key)
    if item:
        for name in RELATIONS: item[name] = [x['name'] for x in item[name]]
    return item


def ingestion_status(cur, rating_key):
    cur.execute('SELECT EXISTS(SELECT 1 FROM public.library WHERE rating_key=%s) AS present', (rating_key,))
    present=row_dict(cur,cur.fetchone())['present']
    cur.execute("SELECT to_regclass('public.metadata_ingestion_events') AS relation")
    if row_dict(cur,cur.fetchone())['relation'] is None:
        return {'status':'historical_unknown' if present else 'absent','accepted':False,'last_change':None}
    cur.execute("""SELECT bool_or(operation='ingest' AND outcome='applied') AS accepted,
        max(event_id) FILTER(WHERE operation IN('complete','correct') AND outcome='applied') AS last_change,
        bool_or(operation='ingest' AND outcome='failed') AS failed
        FROM public.metadata_ingestion_events WHERE rating_key=%s""", (rating_key,))
    row=row_dict(cur,cur.fetchone())
    status=('corrected' if row['last_change'] else 'accepted') if present and row['accepted'] else 'historical_unknown' if present else 'failed_initial' if row['failed'] else 'absent'
    if status == 'failed_initial':
        cur.execute("""SELECT evidence->>'disposition' AS disposition FROM public.metadata_ingestion_events
            WHERE rating_key=%s AND operation='ingest' AND outcome='failed' ORDER BY event_id DESC LIMIT 1""", (rating_key,))
        latest = row_dict(cur, cur.fetchone())
        if latest and latest['disposition'] == 'deferred': status = 'deferred_initial'
    return {'status':status,'accepted':bool(row['accepted'] and present),'last_change':row['last_change']}


def _check_parents(cur, item):
    kind = item['media_type']
    if kind not in ('season','episode'): return
    parent_key=integer(item.get('parent_rating_key'), required=True)
    show_key=integer(item.get('show_rating_key'), required=True)
    cur.execute('SELECT rating_key,media_type,plex_guid,parent_rating_key,show_rating_key FROM public.library WHERE rating_key=ANY(%s) ORDER BY rating_key FOR SHARE',
                ([parent_key, show_key],))
    parents = {x['rating_key']: x for x in (row_dict(cur, r) for r in cur.fetchall())}
    parent, show = parents.get(parent_key), parents.get(show_key)
    if not parent or not show or show['media_type'] != 'show' or parent['media_type'] != ('season' if kind == 'episode' else 'show'):
        raise MetadataError('unaccepted_parent')
    identity('show', show['plex_guid'])
    if kind == 'episode' and parent['show_rating_key'] != show_key:
        raise MetadataError('wrong_series_parent')
    expected = item.get('_ingestion_evidence', {}).get('show_guid')
    if expected and expected != show['plex_guid']: raise Conflict('series_changed')


def _event(cur, key, operation_id, operation, outcome, *, operator, reason,
           evidence=None, before=None, after=None, changes=None):
    evidence = evidence or {}
    cur.execute('''INSERT INTO public.metadata_ingestion_events
        (operation_id,rating_key,operation,outcome,contract_version,source_observed_at,
         operator,reason,before_hash,after_hash,evidence,changes)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING event_id''',
        (str(operation_id), key, operation, outcome, CONTRACT, evidence.get('observed_at'),
         operator, reason, fingerprint(before) if before else None,
         fingerprint(after) if after else None, Json(evidence),
         Json(json.loads(json.dumps(changes or {},default=lambda x: x.isoformat() if isinstance(x,datetime) else str(x))))))
    return row_dict(cur, cur.fetchone())['event_id']


def _replay(cur, key, plan):
    cur.execute("SELECT evidence FROM public.metadata_ingestion_events WHERE operation_id=%s AND rating_key=%s AND outcome='applied'", (str(plan['operation_id']), key))
    row=row_dict(cur,cur.fetchone())
    if row and row['evidence'].get('plan_hash') != fingerprint(plan):
        raise Conflict('operation_id_reused')
    return row is not None


def _write_relationships(cur, key, name, values, *, overwrite_order=False):
    links, dictionary, fk = RELATIONS[name]
    for n, value in enumerate(values):
        if isinstance(value, str): value = dict(name=value, cast_order=n)
        person = value['name'].strip() if name == 'actors' else value['name']
        cur.execute(sql.SQL('INSERT INTO public.{}(name) VALUES(%s) ON CONFLICT(name) DO NOTHING').format(sql.Identifier(dictionary)), (person,))
        columns = ('media_id', fk, 'cast_order') if name == 'actors' else ('media_id', fk)
        placeholders = '%s,id,%s' if name == 'actors' else '%s,id'
        params = (key, value.get('cast_order', n), person) if name == 'actors' else (key, person)
        conflict = 'ON CONFLICT(media_id,actor_id) DO UPDATE SET cast_order=EXCLUDED.cast_order' if name=='actors' and overwrite_order else 'ON CONFLICT DO NOTHING'
        cur.execute(sql.SQL('INSERT INTO public.{}({}) SELECT {} FROM public.{} WHERE name=%s {}').format(
            sql.Identifier(links), sql.SQL(',').join(map(sql.Identifier, columns)),
            sql.SQL(placeholders), sql.Identifier(dictionary),sql.SQL(conflict)), params)


def accept(cur, item, *, operation_id, operator='ingestion'):
    require_schema(cur); writer_lock(cur)
    key = integer(item.get('rating_key'), required=True)
    if snapshot(cur, key, lock=True): return 'skipped_existing'
    evidence = item.get('_ingestion_evidence') or {}
    if evidence.get('requested_key') != key or evidence.get('plex_guid') != item.get('plex_guid') or evidence.get('media_type') != item.get('media_type'):
        raise MetadataError('unvalidated_candidate')
    validate_candidate(item)
    identity(item['media_type'], item['plex_guid'])
    _check_parents(cur, item)
    kind = item['media_type']
    values = dict(item)
    values.update(show_title=item.get('grandparent_title') if kind == 'episode' else
                  (item.get('parent_title') or item.get('grandparent_title')) if kind == 'season' else
                  item['title'] if kind == 'show' else None,
                  episode_title=item['title'] if kind == 'episode' else None,
                  episode_summary=item.get('summary') if kind == 'episode' else None)
    columns = ('rating_key',) + FIELDS
    expressions = [sql.SQL('TO_TIMESTAMP(%s)') if x == 'added_at' else sql.SQL('%s') for x in columns]
    cur.execute(sql.SQL('INSERT INTO public.library({}) VALUES({}) ON CONFLICT(rating_key) DO NOTHING RETURNING rating_key').format(
        sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(expressions)), tuple(values.get(x) for x in columns))
    if cur.fetchone() is None: return 'skipped_existing'
    for name in RELATIONS: _write_relationships(cur, key, name, item[name],overwrite_order=True)
    _event(cur, key, operation_id, 'ingest', 'applied', operator=operator, reason='initial_acceptance',
           evidence=evidence, after=snapshot(cur, key))
    return 'accepted'


def record_failure(cur, key, operation_id, exc, *, operation='ingest', operator='ingestion'):
    require_schema(cur)
    # Never persist arbitrary exception strings (URLs, parameters or credentials).
    diag=getattr(exc,'diag',None)
    evidence={k:v for k,v in {
        'sqlstate':getattr(exc,'pgcode',None),
        'column':getattr(diag,'column_name',None),
        'constraint':getattr(diag,'constraint_name',None),
    }.items() if v}
    _event(cur, key, operation_id, operation, 'failed', operator=operator,
           reason=error_code(exc), evidence=evidence)


def guard_deferral(cur, key):
    """Only a new, safely omitted target may be deferred; reads also support preview."""
    cur.execute('SELECT 1 FROM public.library WHERE rating_key=%s', (key,))
    if cur.fetchone(): return False  # An ordinary concurrent acceptance owns this key.
    cur.execute('SELECT 1 FROM public.library WHERE parent_rating_key=%s OR show_rating_key=%s LIMIT 1', (key,key))
    if cur.fetchone(): raise MetadataError('unsafe_deferral_existing_descendants')
    # Fresh installs/tests need not have optional predictive tables. If a table
    # exists, its errors propagate: unknown dependency coverage is never safe.
    for table in ('metadata_ingestion_events','media_embeddings','recommendations','training_data','user_feedback'):
        cur.execute('SELECT to_regclass(%s) AS relation', ('public.'+table,))
        if row_dict(cur,cur.fetchone())['relation'] is None: continue
        condition = " AND outcome='applied'" if table == 'metadata_ingestion_events' else ''
        cur.execute(sql.SQL('SELECT 1 FROM public.{} WHERE rating_key=%s'+condition+' LIMIT 1').format(sql.Identifier(table)), (key,))
        if cur.fetchone(): raise MetadataError('unsafe_deferral_existing_dependency')
    cur.execute("SELECT to_regclass('public.watch_embeddings') AS vectors,to_regclass('public.watch_history') AS history")
    relations = row_dict(cur,cur.fetchone())
    if relations['vectors'] and not relations['history']:
        raise MetadataError('unsafe_deferral_unknown_watch_coverage')
    if all(relations.values()):
        cur.execute('''SELECT 1 FROM public.watch_embeddings v JOIN public.watch_history h USING(watch_id)
            WHERE h.rating_key=%s LIMIT 1''', (key,))
        if cur.fetchone(): raise MetadataError('unsafe_deferral_existing_watch_vector')
    return True


def record_deferral(cur, key, operation_id, exc):
    require_schema(cur); writer_lock(cur)
    if not isinstance(exc, IncompleteMetadata): raise MetadataError('invalid_deferral')
    if not guard_deferral(cur,key): return 'skipped_existing'
    _event(cur, key, operation_id, 'ingest', 'failed', operator='ingestion', reason=error_code(exc),
           evidence=dict(disposition='deferred', field=exc.field, source_rating_key=exc.rating_key,
                         observed_at=datetime.now(timezone.utc).isoformat()))
    return 'deferred'


def make_plan(cur, key, *, fields=None, relationships=None, operator, reason, mode='correct', operation_id=None):
    if not operator.strip() or not reason.strip() or mode not in ('complete','correct'):
        raise MetadataError('correction_identity_and_reason_required')
    before = snapshot(cur, key)
    if before is None: raise MetadataError('title_not_found')
    fields, relationships = fields or {}, relationships or {}
    if set(fields) - set(FIELDS) or set(relationships) - set(RELATIONS):
        raise MetadataError('unauthorized_field')
    plan = dict(plan_version=CONTRACT, operation_id=str(operation_id or uuid4()), rating_key=key,
                mode=mode, operator=operator, reason=reason, before_hash=fingerprint(before),
                expected_identity={x: before.get(x) for x in ('rating_key','media_type','plex_guid','parent_rating_key','show_rating_key')},
                fields=fields, relationships=relationships,
                preview_before=json_value({x:before.get(x) for x in (*fields,*relationships)}))
    _validate_plan(plan, before)
    if ingestion_status(cur,key)['accepted']:
        validate_core({**before,**fields})
    return plan


def _validate_plan(plan, before):
    UUID(plan['operation_id'])
    if plan.get('plan_version') != CONTRACT or plan.get('mode') not in ('complete','correct'):
        raise MetadataError('invalid_plan')
    if not isinstance(plan.get('operator'), str) or not plan['operator'].strip() or not isinstance(plan.get('reason'), str) or not plan['reason'].strip():
        raise MetadataError('correction_identity_and_reason_required')
    fields, relationships = plan['fields'], plan['relationships']
    if not isinstance(fields, dict) or not isinstance(relationships, dict) or set(fields)-set(FIELDS) or set(relationships)-set(RELATIONS):
        raise MetadataError('unauthorized_field')
    for field, value in fields.items():
        if plan['mode'] == 'complete' and before.get(field) not in (None, '') and before[field] != value:
            raise Conflict('completion_would_overwrite')
        if field in ('year','duration','season_number','episode_number','parent_rating_key','show_rating_key'):
            integer(value)
            if field in ('season_number','episode_number') and value is not None and int(value) < 0:
                raise MetadataError('invalid_episode_number')
            if field in ('parent_rating_key','show_rating_key') and value is not None and int(value) <= 0:
                raise MetadataError('invalid_parent')
        elif field not in ('rating','added_at') and value is not None and not isinstance(value, str):
            raise MetadataError('invalid_field_type')
    after = {**before, **fields}
    if set(fields) & {'plex_guid','media_type'}:
        if after['plex_guid'] or 'media_type' in fields:
            identity(after['media_type'], after['plex_guid'])
    if 'duration' in fields and after['media_type'] in ('movie','episode') and (after['duration'] is None or int(after['duration']) <= 0):
        raise MetadataError('missing_runtime')
    if 'title' in fields and (not isinstance(after['title'], str) or not after['title'].strip()):
        raise MetadataError('missing_title')
    for name, spec in relationships.items():
        if not isinstance(spec,dict) or set(spec) != {'action','values'}:
            raise MetadataError('invalid_relationship_operation')
        action, values = spec.get('action'), spec.get('values')
        if action not in ('add','remove','replace','orders') or not isinstance(values, list):
            raise MetadataError('invalid_relationship_operation')
        if action == 'orders':
            if name != 'actors': raise MetadataError('invalid_order_scope')
            existing = {x['id']: x for x in before['actors']}
            seen = set()
            for v in values:
                if not isinstance(v, dict) or set(v) != {'id','cast_order'}: raise MetadataError('invalid_order')
                ident = integer(v['id'], required=True); order = integer(v['cast_order'],required=plan['mode']=='complete')
                if ident not in existing or ident in seen or (order is not None and order < 0): raise Conflict('order_membership_mismatch')
                if plan['mode'] == 'complete' and existing[ident]['cast_order'] is not None and existing[ident]['cast_order'] != order:
                    raise Conflict('completion_would_reorder')
                seen.add(ident)
        else:
            if plan['mode'] == 'complete': raise MetadataError('membership_requires_correction')
            for v in values:
                if action == 'remove':
                    ident=integer(v, required=True)
                    if ident not in {x['id'] for x in before[name]}: raise Conflict('removal_membership_mismatch')
                elif isinstance(v, str):
                    if not v.strip(): raise MetadataError('blank_credit')
                elif not isinstance(v, dict) or not isinstance(v.get('name'), str) or not v['name'].strip() or set(v)-{'name','cast_order'}:
                    raise MetadataError('invalid_credit')
                elif name == 'actors' and v.get('cast_order') is not None and integer(v['cast_order'], required=True) < 0:
                    raise MetadataError('invalid_order')


def validate_preview(cur, plan, *, before=None):
    key=integer(plan['rating_key'],required=True)
    before=snapshot(cur,key) if before is None else before
    if before is None or fingerprint(before) != plan['before_hash']:
        raise Conflict('stale_preview')
    if plan.get('expected_identity') != {x: before.get(x) for x in ('rating_key','media_type','plex_guid','parent_rating_key','show_rating_key')}:
        raise Conflict('identity_changed')
    if plan.get('preview_before') != json_value({x:before.get(x) for x in (*plan['fields'],*plan['relationships'])}):
        raise Conflict('preview_values_changed')
    _validate_plan(plan, before)
    if ingestion_status(cur,key)['accepted']:
        validate_core({**before,**plan['fields']})
    return before


def apply_plan(cur, plan):
    require_schema(cur); writer_lock(cur)
    key = integer(plan['rating_key'], required=True)
    if _replay(cur, key, plan): return 'replayed'
    before = validate_preview(cur,plan,before=snapshot(cur,key,lock=True))
    fields=plan['fields']
    if set(fields) & {'parent_rating_key','show_rating_key','media_type','plex_guid'}:
        _check_parents(cur, {**before, **fields})
    if fields:
        cur.execute(sql.SQL('UPDATE public.library SET {} WHERE rating_key=%s').format(sql.SQL(',').join(
            sql.SQL('{}=%s').format(sql.Identifier(x)) for x in fields)), (*fields.values(), key))
    for name, spec in plan['relationships'].items():
        links, _, fk = RELATIONS[name]; action, values = spec['action'], spec['values']
        if action == 'orders':
            for v in values:
                cur.execute('UPDATE public.media_actors SET cast_order=%s WHERE media_id=%s AND actor_id=%s', (v['cast_order'], key, v['id']))
        else:
            if action == 'replace': cur.execute(sql.SQL('DELETE FROM public.{} WHERE media_id=%s').format(sql.Identifier(links)), (key,))
            elif action == 'remove':
                cur.execute(sql.SQL('DELETE FROM public.{} WHERE media_id=%s AND {}=ANY(%s)').format(sql.Identifier(links), sql.Identifier(fk)), (key, values))
            if action in ('add','replace'): _write_relationships(cur, key, name, values,overwrite_order=action=='replace')
    after = snapshot(cur, key)
    if before == after: return 'unchanged'
    _event(cur, key, plan['operation_id'], plan['mode'], 'applied', operator=plan['operator'], reason=plan['reason'],
           evidence={**plan.get('evidence', {}),'plan_hash':fingerprint(plan)}, before=before, after=after,
           changes=dict(before={x: before.get(x) for x in (*fields, *plan['relationships'])},
                        after={x: after.get(x) for x in (*fields, *plan['relationships'])}))
    return 'applied'


def guid_plan(cur, key, raw, *, operator='ingestion'):
    before = snapshot(cur, key)
    if before is None: raise MetadataError('title_not_found')
    if not isinstance(raw, dict) or integer(raw.get('rating_key'), required=True) != key or raw.get('media_type') != before['media_type']:
        raise Conflict('guid_identity_mismatch')
    identity(before['media_type'], raw.get('guid'))
    if raw.get('title') != before['title'] or (before.get('year') and integer(raw.get('year')) != before['year']):
        raise Conflict('ambiguous_key_reuse')
    for source, field in [('parent_rating_key','parent_rating_key'),('grandparent_rating_key','show_rating_key')]:
        if before['media_type'] in ('season','episode') and (source != 'grandparent_rating_key' or before['media_type']=='episode'):
            if integer(raw.get(source)) != before.get(field): raise Conflict('guid_parent_mismatch')
    if before.get('plex_guid'):
        if before['plex_guid'] != raw['guid']: raise Conflict('existing_guid_conflict')
        return None
    # Use an existing retained identity anchor if available; never read vectors
    # or change the independently owned predictive source/provenance.
    cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='media_embeddings' AND column_name='provenance') AS available")
    if row_dict(cur,cur.fetchone())['available']:
        cur.execute("SELECT provenance->'source'->>'plex_guid' AS guid FROM public.media_embeddings WHERE rating_key=%s", (key,))
        anchor=row_dict(cur,cur.fetchone())
        if anchor and anchor['guid'] and anchor['guid'] != raw['guid']:
            raise Conflict('retained_identity_conflict')
    return make_plan(cur, key, fields={'plex_guid':raw['guid']}, operator=operator,
                     reason='missing_guid', mode='complete')


def cast_order_plan(cur, key, raw, *, operator, reason, reorder=False):
    before = snapshot(cur, key)
    if before is None: raise MetadataError('title_not_found')
    if not isinstance(raw, dict) or integer(raw.get('rating_key'), required=True) != key or raw.get('media_type') != before['media_type'] or raw.get('guid') != before['plex_guid']:
        raise Conflict('cast_identity_mismatch')
    names, _ = _collection(raw, 'actors')
    by_name = {x['name']: x for x in before['actors']}; values=[]; seen=set()
    for n, name in enumerate(names):
        name=name.strip()
        if name in seen: raise Conflict('ambiguous_duplicate_source_actor')
        seen.add(name); row=by_name.get(name)
        if row and (reorder or row['cast_order'] is None): values.append({'id':row['id'],'cast_order':n})
    known = {x['cast_order']:x['id'] for x in before['actors'] if x['cast_order'] is not None}
    if not reorder and any(v['cast_order'] in known and known[v['cast_order']] != v['id'] for v in values):
        raise Conflict('order_collision_requires_explicit_reorder')
    return make_plan(cur, key, relationships={'actors':{'action':'orders','values':values}},
                     operator=operator, reason=reason, mode='correct' if reorder else 'complete')


def inverse_plan(cur, event_id, *, operator, reason):
    """Prepare, never apply, a scoped reversal of an existing-title edit."""
    require_schema(cur)
    cur.execute("SELECT * FROM public.metadata_ingestion_events WHERE event_id=%s AND outcome='applied'", (event_id,))
    event=row_dict(cur,cur.fetchone())
    if event is None or event['operation']=='ingest':
        raise MetadataError('only_existing_title_changes_are_reversible')
    current=snapshot(cur,event['rating_key'])
    if current is None or fingerprint(current)!=event['after_hash']:
        raise Conflict('title_changed_since_correction')
    before=event['changes']['before'];fields={k:v for k,v in before.items() if k in FIELDS};relations={}
    for name in set(before)&set(RELATIONS):
        old,now=before[name],current[name]
        if name=='actors' and {x['id'] for x in old}=={x['id'] for x in now}:
            # Restoring a NULL order is an explicit correction, not completion.
            relations[name]={'action':'orders','values':[{'id':x['id'],'cast_order':x['cast_order']} for x in old]}
        else:
            values=[{k:x[k] for k in ('name','cast_order') if k in x} for x in old]
            relations[name]={'action':'replace','values':values}
    plan=make_plan(cur,event['rating_key'],fields=fields,relationships=relations,
                   operator=operator,reason=reason,mode='correct')
    return plan
