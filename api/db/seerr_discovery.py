"""Explicit discovery-only persistence. No schema bootstrap or library/model writes."""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json

from psycopg2.extras import Json, RealDictCursor
from psycopg2 import sql

from api.services.seerr_client import SeerrError, parse_iso_date, tv_eligibility, validate_media_type


LOCK = (184725, 30)


def database_error_code(error):
    return {'42P01': 'seerr_schema_not_installed', '42501': 'seerr_database_permission_denied',
            '23503': 'seerr_foreign_key_failure', '23514': 'seerr_check_constraint_failure',
            '23505': 'seerr_unique_constraint_failure'}.get(getattr(error, 'pgcode', None), 'database_or_internal_failure')


JSON_COLUMNS = {'genres', 'cast_members', 'crew_members', 'production_countries', 'production_companies',
                'release_events', 'media_state', 'field_states', 'source_metadata', 'tv_metadata'}
META_COLUMNS = ('title', 'original_title', 'synopsis', 'original_language', 'premiere_date', 'runtime',
                'genres', 'directors', 'cast_members', 'crew_members', 'production_countries',
                'production_companies', 'popularity', 'vote_count', 'vote_average', 'release_events',
                'media_status', 'media_status_4k', 'media_state', 'field_states', 'tv_metadata')
TITLE_COLUMNS = ('media_type', 'tmdb_id', *META_COLUMNS, 'discovery_premiere_date', 'first_discovered_at',
    'first_discovery_run_id', 'last_observed_at', 'last_enriched_at', 'last_enrichment_attempt_at',
    'metadata_updated_at', 'enrichment_status', 'enrichment_error', 'metadata_source_key',
    'metadata_fingerprint', 'source_metadata')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, default=lambda v: v.isoformat()).encode()).hexdigest()


parse_date = parse_iso_date


def release_collection(payload):
    """Only a fully specified response collection can replace canonical events.

    Seerr detail results is a complete country collection, not a paginated/patch
    response. Missing, null or malformed nested lists convey no deletion authority.
    Conservatively preserve the whole prior collection if any country is unknown.
    """
    root = payload.get('releases')
    if not isinstance(root, dict):
        return None, payload.get('_fields', {}).get('releases',
            'omitted' if 'releases' not in payload else 'null' if root is None else 'invalid')
    state = root.get('_fields', {}).get('results',
        'omitted' if 'results' not in root else 'null' if root['results'] is None else
        'value' if isinstance(root['results'], list) else 'invalid')
    if state != 'value':
        return None, 'results_' + state
    events = []
    for group in root['results']:
        if not isinstance(group, dict):
            return None, 'release_dates_invalid'
        state = group.get('_fields', {}).get('release_dates',
            'omitted' if 'release_dates' not in group else 'null' if group['release_dates'] is None else
            'value' if isinstance(group['release_dates'], list) else 'invalid')
        if state != 'value':
            return None, 'release_dates_' + state
        if not all(isinstance(e, dict) for e in group['release_dates']):
            return None, 'release_dates_invalid'
        events.extend(dict(country=group.get('iso_3166_1'), **event) for event in group['release_dates'])
    return events, 'value' if events else 'empty'


def metadata_values(payload, previous=None, media_type='movie'):
    """Omitted general fields preserve last-known values; explicit null clears them.

    Status omission is separately observable and clears *current observed* status codes.
    Failed GETs never call this function and cannot overwrite last successful metadata.
    """
    validate_media_type(media_type)
    if 'mediaType' in payload and payload['mediaType'] != media_type:
        raise SeerrError('media_type_mismatch')
    values = {k: (previous or {}).get(k) for k in META_COLUMNS}
    states = {}
    mapping = dict(title='title', original_title='originalTitle', synopsis='overview',
        original_language='originalLanguage', premiere_date='releaseDate', runtime='runtime',
        genres='genres', production_countries='productionCountries', production_companies='productionCompanies',
        popularity='popularity', vote_count='voteCount', vote_average='voteAverage')
    if media_type == 'tv':
        mapping.update(title='name', original_title='originalName', premiere_date='firstAirDate')
        mapping.pop('runtime')
        values['runtime'] = None
        states['runtime'] = 'not_applicable'
    for column, key in mapping.items():
        state = payload.get('_fields', {}).get(key, 'value' if key in payload and payload[key] is not None else 'null' if key in payload else 'omitted')
        state_column = 'release_date' if column == 'premiere_date' and media_type == 'movie' else column
        states[state_column] = state
        if key not in payload:
            continue
        value = payload[key]
        if column == 'premiere_date':
            value = parse_date(value)
        elif column == 'runtime':
            if type(value) is not int or not 0 < value <= 2147483647:
                value = None
                if payload[key] == 0:
                    states[column] = 'zero_unknown'
        elif column == 'vote_count':
            value = value if type(value) is int and 0 <= value <= 9223372036854775807 else None
        elif column in ('popularity', 'vote_average') and value is not None:
            # Match PostgreSQL double precision before hashing: 0 and 0.0 must
            # not alternate fingerprints on otherwise identical refreshes.
            value = float(value)
        values[column] = value
    if 'genres' not in payload and isinstance(payload.get('genreIds'), list):
        known = {g.get('id'): g.get('name') for g in (previous or {}).get('genres') or [] if isinstance(g, dict)}
        values['genres'] = [{'id': ident, **({'name': known[ident]} if known.get(ident) else {})} for ident in payload['genreIds']]
        states['genres'] = 'ids_only'
    credits = payload.get('credits')
    for column, key in [('cast_members', 'cast'), ('crew_members', 'crew'), ('directors', 'crew')]:
        state = 'omitted' if 'credits' not in payload or isinstance(credits, dict) and key not in credits else 'null' if credits is None or credits.get(key) is None else 'value'
        state = credits.get('_fields', {}).get(key, state) if isinstance(credits, dict) else state
        states[column] = state
        if state == 'null':
            values[column] = None
        elif state == 'value':
            values[column] = [p['name'] for p in credits[key] if p.get('job') == 'Director' and isinstance(p.get('name'), str)] if column == 'directors' else credits[key]
    if media_type == 'movie':
        events, states['release_events'] = release_collection(payload)
        if events is not None:
            values['release_events'] = events
        values['tv_metadata'] = None
    else:
        values['release_events'] = None
        states['release_events'] = 'not_applicable'
        tv = dict((previous or {}).get('tv_metadata') or {})
        for column, key in [('series_type', 'type'), ('episode_run_times', 'episodeRunTime'),
                            ('created_by', 'createdBy'), ('season_numbers', 'seasons'),
                            ('number_of_seasons', 'numberOfSeasons'), ('number_of_episodes', 'numberOfEpisodes'),
                            ('in_production', 'inProduction'), ('series_status', 'status')]:
            state = payload.get('_fields', {}).get(key, 'omitted')
            states['tv_' + column] = state
            if key == 'seasons':
                states['tv_season_premieres'] = state
            collection = key in ('episodeRunTime', 'createdBy', 'seasons')
            if state == 'value':
                value = payload[key]
                if key == 'seasons':
                    value = [s['seasonNumber'] for s in value]
                if key in ('numberOfSeasons', 'numberOfEpisodes') and (type(value) is not int or value < 0):
                    states['tv_' + column] = 'invalid'
                    continue
                tv[column] = value
                if key == 'seasons':
                    tv['season_premieres'] = payload[key]
            elif state == 'null' and not collection:
                tv[column] = None
        values['tv_metadata'] = tv
    media = payload.get('mediaInfo') or {}
    state = payload.get('_fields', {}).get('mediaInfo', 'omitted')
    for column, key in [('media_status', 'status'), ('media_status_4k', 'status4k')]:
        code = media.get(key)
        values[column] = code if type(code) is int and 0 < code <= 2147483647 else None
    request_state = media.get('_fields', {}).get('requests', 'omitted')
    requests = media.get('requests')
    values['media_state'] = dict(media_info=state,
        status=media.get('_fields', {}).get('status', 'omitted'),
        status4k=media.get('_fields', {}).get('status4k', 'omitted'),
        requests=request_state, request_count=len(requests) if isinstance(requests, list) else None,
        request_states=requests, **{k: media[k] for k in ('externalServiceLinked', 'externalService4kLinked',
            'libraryIdentifierPresent', 'monitored', 'monitored4k') if k in media})
    values['field_states'] = states
    return values


def _fingerprint(movie):
    if movie['media_type'] == 'movie':
        # Preserve the reviewed v1 movie projection and hashes across column rename.
        data = {('release_date' if k == 'premiere_date' else k): movie.get(k)
                for k in META_COLUMNS if k != 'tv_metadata'}
    else:
        data = {'media_type': 'tv', **{k: movie.get(k) for k in META_COLUMNS}}
    return digest(data | {'detail': movie.get('source_metadata', {}).get('detail')})


def source_fingerprint(payload, media_type):
    return digest(payload if media_type == 'movie' else {'media_type': media_type, 'payload': payload})


# Exact integrity contract of optional migrations 001 + 002. Catalog rendering
# is validated on PostgreSQL 18; extra ordinary indexes are allowed, integrity drift is not.
SCHEMA_COLUMNS = {'seerr_discovered_titles': {'tmdb_id': ('bigint', True, '', None),
                             'title': ('text', False, '', None),
                             'original_title': ('text', False, '', None),
                             'synopsis': ('text', False, '', None),
                             'original_language': ('text', False, '', None),
                             'premiere_date': ('date', False, '', None),
                             'discovery_premiere_date': ('date', False, '', None),
                             'runtime': ('integer', False, '', None),
                             'genres': ('jsonb', False, '', None),
                             'directors': ('text[]', False, '', None),
                             'cast_members': ('jsonb', False, '', None),
                             'crew_members': ('jsonb', False, '', None),
                             'production_countries': ('jsonb', False, '', None),
                             'production_companies': ('jsonb', False, '', None),
                             'popularity': ('double precision', False, '', None),
                             'vote_count': ('bigint', False, '', None),
                             'vote_average': ('double precision', False, '', None),
                             'release_events': ('jsonb', False, '', None),
                             'media_status': ('integer', False, '', None),
                             'media_status_4k': ('integer', False, '', None),
                             'media_state': ('jsonb', True, '', "'{}'::jsonb"),
                             'first_discovered_at': ('timestamp with time zone', True, '', None),
                             'first_discovery_run_id': ('uuid', True, '', None),
                             'last_observed_at': ('timestamp with time zone', True, '', None),
                             'last_enriched_at': ('timestamp with time zone', False, '', None),
                             'last_enrichment_attempt_at': ('timestamp with time zone', False, '', None),
                             'metadata_updated_at': ('timestamp with time zone', True, '', None),
                             'enrichment_status': ('text', True, '', "'pending'::text"),
                             'enrichment_error': ('text', False, '', None),
                             'metadata_source_key': ('text', False, '', None),
                             'metadata_fingerprint': ('text', True, '', None),
                             'field_states': ('jsonb', True, '', "'{}'::jsonb"),
                             'source_metadata': ('jsonb', True, '', "'{}'::jsonb"),
                             'media_type': ('text', True, '', None),
                             'tv_metadata': ('jsonb', False, '', None)},
 'seerr_discovery_observations': {'observation_id': ('bigint', True, 'd', None),
                                  'run_id': ('uuid', True, '', None),
                                  'tmdb_id': ('bigint', True, '', None),
                                  'scope_key': ('text', True, '', None),
                                  'scope_name': ('text', True, '', None),
                                  'observation_kind': ('text', True, '', None),
                                  'query_parameters': ('jsonb', True, '', None),
                                  'observed_at': ('timestamp with time zone', True, '', None),
                                  'discovery_metadata': ('jsonb', True, '', None),
                                  'detail_metadata': ('jsonb', False, '', None),
                                  'detail_observed_at': ('timestamp with time zone', False, '', None),
                                  'enrichment_outcome': ('text', True, '', "'pending'::text"),
                                  'enrichment_error': ('text', False, '', None),
                                  'source_fingerprint': ('text', True, '', None),
                                  'prior_metadata_fingerprint': ('text', False, '', None),
                                  'metadata_fingerprint': ('text', True, '', None),
                                  'changed_fields': ('text[]', True, '', "'{}'::text[]"),
                                  'is_new': ('boolean', True, '', None),
                                  'media_type': ('text', True, '', None),
                                  'eligibility': ('jsonb', False, '', None)},
 'seerr_discovery_runs': {'run_id': ('uuid', True, '', None),
                          'started_at': ('timestamp with time zone', True, '', None),
                          'completed_at': ('timestamp with time zone', False, '', None),
                          'status': ('text', True, '', None),
                          'operation': ('text', True, '', None),
                          'source_key': ('text', True, '', None),
                          'parameters': ('jsonb', True, '', None),
                          'pagination': ('jsonb', True, '', "'[]'::jsonb"),
                          'counts': ('jsonb', True, '', "'{}'::jsonb"),
                          'discovery_complete': ('boolean', True, '', 'false'),
                          'enrichment_complete': ('boolean', True, '', 'false'),
                          'errors': ('jsonb', True, '', "'[]'::jsonb"),
                          'warnings': ('jsonb', True, '', "'[]'::jsonb")}}
SCHEMA_CONSTRAINTS = (('seerr_discovered_titles',
  'c',
  "CHECK (((cast_members IS NULL) OR (jsonb_typeof(cast_members) = 'array'::text)))"),
 ('seerr_discovered_titles', 'c', "CHECK (((genres IS NULL) OR (jsonb_typeof(genres) = 'array'::text)))"),
 ('seerr_discovered_titles', 'c', "CHECK (((media_type = 'movie'::text) OR (release_events IS NULL)))"),
 ('seerr_discovered_titles',
  'c',
  "CHECK (((tv_metadata IS NULL) OR ((media_type = 'tv'::text) AND (jsonb_typeof(tv_metadata) = "
  "'object'::text))))"),
 ('seerr_discovered_titles',
  'c',
  "CHECK ((enrichment_status = ANY (ARRAY['pending'::text, 'success'::text, 'failed'::text])))"),
 ('seerr_discovered_titles', 'c', 'CHECK ((last_observed_at >= first_discovered_at))'),
 ('seerr_discovered_titles', 'c', "CHECK ((media_type = ANY (ARRAY['movie'::text, 'tv'::text])))"),
 ('seerr_discovered_titles', 'c', 'CHECK ((runtime > 0))'),
 ('seerr_discovered_titles', 'c', 'CHECK ((tmdb_id > 0))'),
 ('seerr_discovered_titles', 'f', 'FOREIGN KEY (first_discovery_run_id) REFERENCES seerr_discovery_runs(run_id)'),
 ('seerr_discovered_titles', 'p', 'PRIMARY KEY (media_type, tmdb_id)'),
 ('seerr_discovery_observations',
  'c',
  "CHECK (((eligibility IS NULL) OR ((media_type = 'tv'::text) AND (jsonb_typeof(eligibility) = 'object'::text) "
  "AND (eligibility ? 'state'::text) AND (jsonb_typeof((eligibility -> 'state'::text)) = 'string'::text) AND "
  "((eligibility ->> 'state'::text) = ANY (ARRAY['eligible'::text, 'provisional'::text, 'excluded'::text])))))"),
 ('seerr_discovery_observations',
  'c',
  "CHECK ((enrichment_outcome = ANY (ARRAY['pending'::text, 'success'::text, 'cached'::text, 'failed'::text, "
  "'deferred'::text])))"),
 ('seerr_discovery_observations', 'c', "CHECK ((media_type = ANY (ARRAY['movie'::text, 'tv'::text])))"),
 ('seerr_discovery_observations',
  'c',
  "CHECK ((observation_kind = ANY (ARRAY['discovery'::text, 'refresh'::text])))"),
 ('seerr_discovery_observations',
  'f',
  'FOREIGN KEY (media_type, tmdb_id) REFERENCES seerr_discovered_titles(media_type, tmdb_id)'),
 ('seerr_discovery_observations', 'f', 'FOREIGN KEY (run_id) REFERENCES seerr_discovery_runs(run_id)'),
 ('seerr_discovery_observations', 'p', 'PRIMARY KEY (observation_id)'),
 ('seerr_discovery_observations', 'u', 'UNIQUE (run_id, media_type, tmdb_id, scope_key)'),
 ('seerr_discovery_runs',
  'c',
  "CHECK (((status <> 'success'::text) OR (discovery_complete AND enrichment_complete)))"),
 ('seerr_discovery_runs', 'c', "CHECK (((status = 'running'::text) = (completed_at IS NULL)))"),
 ('seerr_discovery_runs', 'c', "CHECK ((operation = ANY (ARRAY['discover'::text, 'enrich'::text])))"),
 ('seerr_discovery_runs',
  'c',
  "CHECK ((status = ANY (ARRAY['running'::text, 'success'::text, 'partial'::text, 'failed'::text])))"),
 ('seerr_discovery_runs', 'p', 'PRIMARY KEY (run_id)'))


def require_unified_schema(connection):
    """Read-only compatibility guard, before recovery/run writes or HTTP.

    This is validation only: never bootstrap/repair schema or adopt partial upgrades.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('public.seerr_discovered_titles'),to_regclass('public.seerr_discovered_movies')")
        titles, legacy = cur.fetchone()
        if legacy is not None and titles is not None:
            raise SeerrError('seerr_unified_schema_ambiguous', stop=True)
        if titles is None:
            raise SeerrError('seerr_unified_schema_required', stop=True)
        tables = list(SCHEMA_COLUMNS)
        cur.execute("""SELECT c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=ANY(%s)""", (tables,))
        if sorted(cur.fetchall()) != sorted((t, 'r', False, False) for t in tables):
            raise SeerrError('seerr_unified_schema_incompatible', stop=True)
        cur.execute("""SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),
            a.attnotnull,a.attidentity::text,pg_get_expr(d.adbin,d.adrelid),a.attgenerated::text
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
            WHERE n.nspname='public' AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped""", (tables,))
        actual = {}
        for table, name, *definition, generated in cur.fetchall():
            if generated:
                raise SeerrError('seerr_unified_schema_incompatible', stop=True)
            actual.setdefault(table, {})[name] = tuple(definition)
        if actual != SCHEMA_COLUMNS:
            raise SeerrError('seerr_unified_schema_incompatible', stop=True)
        # A controlled search path makes FK definitions unambiguous and restores
        # the caller's value after comparison; no persistent/session config change.
        cur.execute("SELECT current_setting('search_path')")
        search_path = cur.fetchone()[0]
        cur.execute("SELECT set_config('search_path','pg_catalog,public,pg_temp',true)")
        try:
            cur.execute("""SELECT c.relname,k.contype::text,pg_get_constraintdef(k.oid),
                k.convalidated,k.condeferrable,k.condeferred,
                COALESCE(i.indisvalid,true),COALESCE(i.indisready,true)
                FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                LEFT JOIN pg_index i ON i.indexrelid=k.conindid
                WHERE n.nspname='public' AND c.relname=ANY(%s) AND k.contype<>'n'""", (tables,))
            constraints = cur.fetchall()
        finally:
            cur.execute("SELECT set_config('search_path',%s,true)", (search_path,))
        if (sorted(row[:3] for row in constraints) != sorted(SCHEMA_CONSTRAINTS)
                or any(tuple(row[3:]) != (True, False, False, True, True) for row in constraints)):
            raise SeerrError('seerr_unified_schema_incompatible', stop=True)
        cur.execute("""SELECT EXISTS(SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=ANY(%s)
              AND (NOT t.tgisinternal OR t.tgenabled NOT IN ('O','A'))),
            EXISTS(SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
              JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname='public' AND c.relname=ANY(%s) AND i.indisunique
                AND NOT EXISTS(SELECT 1 FROM pg_constraint k WHERE k.conindid=i.indexrelid
                  AND k.conrelid=i.indrelid AND k.contype IN ('p','u','x'))),
            pg_get_serial_sequence('public.seerr_discovery_observations','observation_id'),
            current_setting('session_replication_role')""", (tables, tables))
        triggers, extra_unique, sequence, replication_role = cur.fetchone()
        if (triggers or extra_unique or replication_role != 'origin'
                or sequence != 'public.seerr_discovery_observations_observation_id_seq'):
            raise SeerrError('seerr_unified_schema_incompatible', stop=True)
        cur.execute("""SELECT c.relkind,format_type(s.seqtypid,NULL),s.seqstart,s.seqincrement,
            s.seqmin,s.seqmax,s.seqcache,s.seqcycle,
            EXISTS(SELECT 1 FROM pg_depend d JOIN pg_attribute a
              ON a.attrelid=d.refobjid AND a.attnum=d.refobjsubid
              WHERE d.objid=c.oid AND d.classid='pg_class'::regclass AND d.refclassid='pg_class'::regclass
                AND d.refobjid='public.seerr_discovery_observations'::regclass
                AND a.attname='observation_id' AND d.deptype='i')
            FROM pg_class c JOIN pg_sequence s ON s.seqrelid=c.oid
            WHERE c.oid=%s::regclass""", (sequence,))
        if cur.fetchone() != ('S', 'bigint', 1, 1, 1, 9223372036854775807, 1, False, True):
            raise SeerrError('seerr_unified_schema_incompatible', stop=True)


class DiscoveryRepository:
    def __init__(self, connection):
        self.conn = connection

    def acquire(self):
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_lock(%s, %s)', LOCK)
                return cur.fetchone()[0]

    def release(self):
        self.conn.rollback()
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s, %s)', LOCK)

    def start(self, run_id, now, operation, source_key, parameters):
        with self.conn:
            require_unified_schema(self.conn)
        self.validate_source(source_key, parameters.get('source_id'))
        # Recovery is durable even if creating the next run fails. Session lock is held.
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("SELECT run_id FROM public.seerr_discovery_runs WHERE status='running'")
                interrupted = [row[0] for row in cur.fetchall()]
        for previous in interrupted:
            counts = self.counts(previous)
            with self.conn:
                with self.conn.cursor() as cur:
                    cur.execute("""UPDATE public.seerr_discovery_runs SET status=%s,completed_at=%s,counts=%s,
                        discovery_complete=false,enrichment_complete=false,
                        errors=errors || '[{"code":"interrupted_previous_execution"}]'::jsonb,
                        warnings=warnings || '["recovered_after_exclusive_lock"]'::jsonb
                        WHERE run_id=%s AND status='running'""",
                        ('partial' if counts['titles'] else 'failed', now, Json(counts), str(previous)))
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""INSERT INTO public.seerr_discovery_runs
                    (run_id,started_at,status,operation,source_key,parameters)
                    VALUES (%s,%s,'running',%s,%s,%s)""", (str(run_id), now, operation, source_key, Json(parameters)))

    def validate_source(self, source_key, source_id):
        """Validate the single-inventory binding under the writer's session lock.

        Existing run columns/JSON carry the durable binding, including empty runs.
        Never adopt legacy/ambiguous data or recover other-instance runs implicitly.
        """
        if not isinstance(source_id, str) or not source_id:
            raise SeerrError('discovery_source_id_required', stop=True)
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""SELECT
                    EXISTS (SELECT 1 FROM public.seerr_discovery_runs
                        WHERE jsonb_typeof(parameters->'source_id') IS DISTINCT FROM 'string'
                           OR parameters->>'source_id' = ''),
                    EXISTS (SELECT 1 FROM public.seerr_discovered_titles
                        WHERE last_enriched_at IS NOT NULL AND metadata_source_key IS NULL),
                    NOT EXISTS (SELECT 1 FROM public.seerr_discovery_runs)
                        AND EXISTS (SELECT 1 FROM public.seerr_discovered_titles)""")
                if any(cur.fetchone()):
                    raise SeerrError('discovery_source_identity_ambiguous', stop=True)
                cur.execute("""SELECT
                    EXISTS (SELECT 1 FROM public.seerr_discovery_runs
                        WHERE source_key IS DISTINCT FROM %s OR parameters->>'source_id' IS DISTINCT FROM %s),
                    EXISTS (SELECT 1 FROM public.seerr_discovered_titles
                        WHERE metadata_source_key IS NOT NULL AND metadata_source_key IS DISTINCT FROM %s)""",
                    (source_key, source_id, source_key))
                if any(cur.fetchone()):
                    raise SeerrError('discovery_source_identity_mismatch', stop=True)

    def get(self, tmdb_id, media_type='movie'):
        validate_media_type(media_type)
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT * FROM public.seerr_discovered_titles WHERE media_type=%s AND tmdb_id=%s', (media_type, tmdb_id))
                row = cur.fetchone()
                return dict(row) if row else None

    def _save(self, cur, movie):
        columns = sql.SQL(',').join(map(sql.Identifier, TITLE_COLUMNS))
        updates = sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(k), sql.Identifier(k))
                                  for k in TITLE_COLUMNS if k not in ('media_type', 'tmdb_id', 'first_discovered_at', 'first_discovery_run_id'))
        cur.execute(sql.SQL('INSERT INTO public.seerr_discovered_titles ({}) VALUES ({}) ON CONFLICT(media_type,tmdb_id) DO UPDATE SET {}').format(
            columns, sql.SQL(',').join(sql.Placeholder() for _ in TITLE_COLUMNS), updates),
            [Json(movie[k]) if k in JSON_COLUMNS and movie.get(k) is not None else movie.get(k) for k in TITLE_COLUMNS])

    def discover_page(self, run_id, scope_key, scope_name, query, rows, now, *, kind='discovery', media_type='movie'):
        validate_media_type(media_type)
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                for payload in rows:
                    tmdb_id = payload['id']
                    cur.execute('SELECT * FROM public.seerr_discovered_titles WHERE media_type=%s AND tmdb_id=%s FOR UPDATE', (media_type, tmdb_id))
                    old = cur.fetchone()
                    if 'mediaType' in payload and payload['mediaType'] != media_type:
                        raise SeerrError('media_type_mismatch')
                    movie = dict(old) if old else dict(media_type=media_type, tmdb_id=tmdb_id, first_discovered_at=now,
                        first_discovery_run_id=str(run_id), last_observed_at=now, last_enriched_at=None,
                        last_enrichment_attempt_at=None, enrichment_status='pending', enrichment_error=None,
                        metadata_source_key=None, source_metadata={})
                    before = old['metadata_fingerprint'] if old else None
                    if not old or not old['last_enriched_at']:
                        movie.update(metadata_values(payload, movie, media_type))
                    if kind == 'discovery':
                        movie['last_observed_at'] = max(movie['last_observed_at'], now)
                        date_key = 'releaseDate' if media_type == 'movie' else 'firstAirDate'
                        if date_key in payload:
                            movie['discovery_premiere_date'] = parse_date(payload[date_key])
                        movie['source_metadata'] = {**movie['source_metadata'], 'discovery': payload}
                    movie['metadata_fingerprint'] = _fingerprint(movie)
                    changed = [k for k in META_COLUMNS if old and movie.get(k) != old.get(k)]
                    movie['metadata_updated_at'] = now if before != movie['metadata_fingerprint'] else old['metadata_updated_at']
                    self._save(cur, movie)
                    cur.execute("""INSERT INTO public.seerr_discovery_observations
                        (run_id,media_type,tmdb_id,scope_key,scope_name,observation_kind,query_parameters,observed_at,
                         discovery_metadata,source_fingerprint,prior_metadata_fingerprint,metadata_fingerprint,changed_fields,is_new,eligibility)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(run_id,media_type,tmdb_id,scope_key) DO NOTHING""",
                        (str(run_id), media_type, tmdb_id, scope_key, scope_name, kind, Json(query), now, Json(payload),
                         source_fingerprint(payload, media_type), before, movie['metadata_fingerprint'], changed, old is None,
                         Json(tv_eligibility(payload, query)) if media_type == 'tv' else None))

    def enriched(self, run_id, tmdb_id, payload, now, source_key, media_type='movie'):
        validate_media_type(media_type)
        if payload.get('id') != tmdb_id:
            raise SeerrError('detail_identity_mismatch')
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT * FROM public.seerr_discovered_titles WHERE media_type=%s AND tmdb_id=%s FOR UPDATE', (media_type, tmdb_id))
                old = dict(cur.fetchone())
                movie = {**old, **metadata_values(payload, old, media_type)}
                movie['source_metadata'] = {**old['source_metadata'], 'detail': payload}
                movie['metadata_fingerprint'] = _fingerprint(movie)
                changed = [k for k in META_COLUMNS if old.get(k) != movie.get(k)]
                if old['source_metadata'].get('detail') != payload:
                    changed.append('source_metadata')
                movie.update(last_enriched_at=now, last_enrichment_attempt_at=now, metadata_source_key=source_key,
                    enrichment_status='success', enrichment_error=None,
                    metadata_updated_at=now if movie['metadata_fingerprint'] != old['metadata_fingerprint'] else old['metadata_updated_at'])
                self._save(cur, movie)
                cur.execute("""UPDATE public.seerr_discovery_observations SET detail_metadata=%s,detail_observed_at=%s,
                    enrichment_outcome='success',enrichment_error=NULL,metadata_fingerprint=%s,
                    changed_fields=ARRAY(SELECT DISTINCT unnest(changed_fields || %s::text[]))
                    WHERE run_id=%s AND media_type=%s AND tmdb_id=%s""",
                    (Json(payload), now, movie['metadata_fingerprint'], changed, str(run_id), media_type, tmdb_id)
                )
                self._eligibility(cur, run_id, media_type, tmdb_id, payload)

    def enrichment_failed(self, run_id, tmdb_id, now, code, media_type='movie'):
        validate_media_type(media_type)
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""UPDATE public.seerr_discovered_titles SET enrichment_status='failed',
                    enrichment_error=%s,last_enrichment_attempt_at=%s WHERE media_type=%s AND tmdb_id=%s""", (code, now, media_type, tmdb_id))
                cur.execute("""UPDATE public.seerr_discovery_observations SET enrichment_outcome='failed',enrichment_error=%s
                    WHERE run_id=%s AND media_type=%s AND tmdb_id=%s""", (code, str(run_id), media_type, tmdb_id))

    def reuse(self, run_id, movie, *, deferred=False):
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""UPDATE public.seerr_discovery_observations SET enrichment_outcome=%s,
                    detail_metadata=%s,detail_observed_at=%s,metadata_fingerprint=%s WHERE run_id=%s AND media_type=%s AND tmdb_id=%s""",
                    ('deferred' if deferred else 'cached', Json(movie['source_metadata'].get('detail')),
                     movie['last_enriched_at'], movie['metadata_fingerprint'], str(run_id), movie['media_type'], movie['tmdb_id']))
                self._eligibility(cur, run_id, movie['media_type'], movie['tmdb_id'], movie['source_metadata'].get('detail'))

    def defer(self, run_id, tmdb_id, code, media_type='movie'):
        validate_media_type(media_type)
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""UPDATE public.seerr_discovery_observations SET enrichment_outcome='deferred',enrichment_error=%s
                    WHERE run_id=%s AND media_type=%s AND tmdb_id=%s""", (code, str(run_id), media_type, tmdb_id))

    def due(self, config, now, *, force=False):
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""SELECT * FROM public.seerr_discovered_titles WHERE media_type=ANY(%s) AND (
                    %s OR
                    (enrichment_status='failed' AND (last_enrichment_attempt_at IS NULL OR last_enrichment_attempt_at<=%s)) OR
                    (enrichment_status<>'failed' AND (metadata_source_key IS DISTINCT FROM %s OR last_enriched_at IS NULL OR last_enriched_at<=%s)))
                    ORDER BY last_enrichment_attempt_at NULLS FIRST,media_type,tmdb_id LIMIT %s""",
                    (list(config.media_types), force or not config.cache_enabled, now - timedelta(hours=config.failed_retry_hours),
                     config.source_key, now - timedelta(hours=config.metadata_ttl_hours), config.refresh_batch_size))
                return [dict(row) for row in cur.fetchall()]

    def _eligibility(self, cur, run_id, media_type, tmdb_id, payload):
        if media_type != 'tv':
            return
        cur.execute("""SELECT observation_id,query_parameters,discovery_metadata FROM public.seerr_discovery_observations
            WHERE run_id=%s AND media_type=%s AND tmdb_id=%s""", (str(run_id), media_type, tmdb_id))
        for row in cur.fetchall():
            if isinstance(row, dict):
                ident, query, discovery = row['observation_id'], row['query_parameters'], row['discovery_metadata']
            else:
                ident, query, discovery = row
            assessment = tv_eligibility(payload or {}, query, detail=payload is not None, discovery=discovery)
            cur.execute('UPDATE public.seerr_discovery_observations SET eligibility=%s WHERE observation_id=%s',
                        (Json(assessment), ident))

    def counts(self, run_id):
        with self.conn:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""WITH titles AS (
                    SELECT media_type,tmdb_id,bool_or(is_new) AS is_new,
                        bool_or(cardinality(changed_fields)>0) AS changed,
                        bool_or(enrichment_outcome='success') AS success,
                        bool_or(enrichment_outcome='cached') AS cached,
                        bool_or(enrichment_outcome='failed') AS failed,
                        bool_or(enrichment_outcome='deferred') AS deferred,
                        bool_or(enrichment_outcome='pending') AS pending,
                        bool_or(eligibility->>'state'='eligible') AS eligible,
                        bool_or(eligibility->>'state'='provisional') AS provisional,
                        bool_or(eligibility->>'state'='excluded') AS excluded
                    FROM public.seerr_discovery_observations WHERE run_id=%s GROUP BY media_type,tmdb_id)
                    SELECT media_type,COUNT(*)::int AS titles,
                        COUNT(*) FILTER(WHERE is_new)::int AS new_titles,
                        COUNT(*) FILTER(WHERE NOT is_new)::int AS existing_titles,
                        COUNT(*) FILTER(WHERE NOT is_new AND changed)::int AS updated_titles,
                        COUNT(*) FILTER(WHERE success)::int AS enrichment_success,
                        COUNT(*) FILTER(WHERE cached)::int AS enrichment_cached,
                        COUNT(*) FILTER(WHERE failed)::int AS enrichment_failed,
                        COUNT(*) FILTER(WHERE deferred)::int AS enrichment_deferred,
                        COUNT(*) FILTER(WHERE pending)::int AS enrichment_pending,
                        COUNT(*) FILTER(WHERE eligible)::int AS eligible,
                        COUNT(*) FILTER(WHERE NOT coalesce(eligible,false) AND provisional)::int AS provisional,
                        COUNT(*) FILTER(WHERE NOT coalesce(eligible,false) AND NOT coalesce(provisional,false) AND excluded)::int AS excluded
                    FROM titles GROUP BY media_type""", (str(run_id),))
                return combine_counts([dict(r) for r in cur.fetchall()])

    def finish(self, run_id, now, status, pagination, counts, discovery_complete, enrichment_complete, errors, warnings):
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("""UPDATE public.seerr_discovery_runs SET completed_at=%s,status=%s,pagination=%s,counts=%s,
                    discovery_complete=%s,enrichment_complete=%s,errors=%s,warnings=%s WHERE run_id=%s AND status='running'""",
                    (now, status, Json(pagination), Json(counts), discovery_complete, enrichment_complete,
                     Json(errors), Json(warnings), str(run_id)))


COUNT_FIELDS = ('titles', 'new_titles', 'existing_titles', 'updated_titles',
                'enrichment_success', 'enrichment_cached', 'enrichment_failed', 'enrichment_deferred',
                'enrichment_pending', 'eligible', 'provisional', 'excluded')


def combine_counts(rows):
    by_type = {t: dict.fromkeys(COUNT_FIELDS, 0) for t in ('movie', 'tv')}
    for row in rows:
        by_type[row['media_type']].update({k: row[k] for k in COUNT_FIELDS})
    result = {k: sum(r[k] for r in by_type.values()) for k in COUNT_FIELDS}
    # Legacy movie-only fields continue to count movies, never television.
    result.update({old: by_type['movie'][new] for old, new in
        [('movies','titles'), ('new_movies','new_titles'), ('existing_movies','existing_titles'), ('updated_movies','updated_titles')]})
    return result | {'by_media_type': by_type}


def inventory_summary(connection, config, now):
    """Caller establishes read-only mode. No implicit migration or Seerr requests."""
    require_unified_schema(connection)
    with connection.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM public.seerr_discovery_runs ORDER BY started_at DESC,run_id DESC LIMIT 1')
        row = cur.fetchone()
        latest = dict(row) if row else None
        cur.execute("""SELECT media_type,COUNT(*)::int AS titles,COUNT(*) FILTER(WHERE media_type=ANY(%s) AND (%s
            OR (enrichment_status='failed' AND (last_enrichment_attempt_at IS NULL OR last_enrichment_attempt_at<=%s))
            OR (enrichment_status<>'failed' AND (last_enriched_at IS NULL OR metadata_source_key IS DISTINCT FROM %s OR last_enriched_at<=%s))))::int AS refresh_due
            FROM public.seerr_discovered_titles GROUP BY media_type""", (list(config.media_types), not config.cache_enabled,
                now-timedelta(hours=config.failed_retry_hours), config.source_key, now-timedelta(hours=config.metadata_ttl_hours)))
        grouped = {r['media_type']: dict(r) for r in cur.fetchall()}
        return dict(total_titles=sum(r['titles'] for r in grouped.values()),
                    total_movies=grouped.get('movie', {}).get('titles', 0),
                    total_tv=grouped.get('tv', {}).get('titles', 0),
                    refresh_due=sum(r['refresh_due'] for r in grouped.values()),
                    by_media_type=grouped, latest_run=latest)
