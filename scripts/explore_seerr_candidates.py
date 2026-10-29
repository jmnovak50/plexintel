#!/usr/bin/env python3
"""Read-only Seerr candidate snapshots and curation experiments. No app startup imports."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import sys
import tempfile
import time
import unicodedata
from urllib.parse import quote, urlencode, urlsplit

import requests
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MEDIA = {1: 'unknown', 2: 'pending', 3: 'processing', 4: 'partially_available',
         5: 'available', 6: 'blocklisted', 7: 'deleted'}
REQUEST = {1: 'pending', 2: 'approved', 3: 'declined', 4: 'failed', 5: 'completed'}
RELEASE = {1: 'premiere', 2: 'limited_theatrical', 3: 'theatrical',
           4: 'digital', 5: 'physical', 6: 'tv'}
PUBLIC_FIELDS = ('id', 'title', 'originalTitle', 'mediaType', 'adult', 'video',
                 'overview', 'popularity', 'voteCount', 'voteAverage', 'genreIds',
                 'genres', 'originalLanguage', 'runtime', 'releaseDate', 'releases',
                 'posterPath', 'credits', 'status', 'imdbId', 'collection')
DEFAULT_RULES = dict(popularity_min=5.0, votes_min=20, rating_min=6.0,
                     runtime_min=40, completeness_min=5, niche_genres=['Documentary', 'Animation'],
                     person_ids=[], niche_tmdb_ids=[])
APPROACHES = ('broad', 'popularity', 'metadata', 'multi_path', 'soft_priority')


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def private_dir(path):
    if path.is_symlink():
        raise ValueError('Output/cache directory must not be a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def write_text(path, value):
    """Atomic owner-only output, including cache files; never follow a target symlink."""
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.snapshot-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(value)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, rows):
    if not rows:
        write_text(path, '')
        return
    buf = io.StringIO(newline='')
    fields = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        values = {}
        for k, value in row.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            # Spreadsheet formula protection; the JSON remains lossless.
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                value = "'" + value
            values[k] = value
        writer.writerow(values)
    write_text(path, buf.getvalue())


class ApiError(RuntimeError):
    def __init__(self, code, stop=False):
        super().__init__(code)
        self.stop = stop


def sanitize_movie(value):
    """Do not cache/export Seerr user objects, request IDs, server URLs or paths."""
    result = {k: value[k] for k in PUBLIC_FIELDS if k in value}
    result['mediaInfoFieldState'] = value.get('mediaInfoFieldState') or (
        'missing' if 'mediaInfo' not in value else 'null' if value['mediaInfo'] is None
        else 'object' if isinstance(value['mediaInfo'], dict) else 'invalid')
    if isinstance(value.get('mediaInfo'), dict):
        media = value['mediaInfo']
        result['mediaInfo'] = {k: media[k] for k in ('status', 'status4k') if k in media}
        safe = result['mediaInfo']
        safe['requestsFieldState'] = media.get('requestsFieldState') or (
            'missing' if 'requests' not in media else 'null' if media['requests'] is None
            else 'list' if isinstance(media['requests'], list) else 'invalid')
        # Preserve only presence/count observations, never service IDs, library IDs or paths.
        for output, sources in {
            'externalServiceLinked': ('externalServiceId',),
            'externalService4kLinked': ('externalServiceId4k',),
            'libraryIdentifierPresent': ('ratingKey', 'jellyfinMediaId'),
            'libraryIdentifier4kPresent': ('ratingKey4k', 'jellyfinMediaId4k'),
        }.items():
            if output in media:
                safe[output] = media[output]
            elif any(k in media for k in sources):
                safe[output] = any(media.get(k) is not None for k in sources)
        for source, output in [('downloadStatus', 'downloadCount'), ('downloadStatus4k', 'downloadCount4k')]:
            if output in media:
                safe[output] = media[output]
            elif isinstance(media.get(source), list):
                safe[output] = len(media[source])
        for k in ('monitored', 'monitored4k'):
            if isinstance(media.get(k), bool):
                safe[k] = media[k]
        if isinstance(media.get('requests'), list):
            result['mediaInfo']['requests'] = [
                {k: r[k] for k in ('status', 'is4k') if k in r}
                for r in media['requests'] if isinstance(r, dict)]
    elif 'mediaInfo' in value:
        result['mediaInfo'] = None
    return result


def media_observation(value, error=None):
    """Evidence about returned fields; absence never asserts that no prior request exists."""
    field = value.get('mediaInfoFieldState') or (
        'missing' if 'mediaInfo' not in value else 'null' if value['mediaInfo'] is None
        else 'object' if isinstance(value['mediaInfo'], dict) else 'invalid')
    media = value.get('mediaInfo') if isinstance(value.get('mediaInfo'), dict) else {}
    requests_ = media.get('requests')
    request_field = media.get('requestsFieldState') or (
        'missing' if 'requests' not in media else 'null' if requests_ is None
        else 'list' if isinstance(requests_, list) else 'invalid')
    status = media.get('status')
    request_observations = [{k: r[k] for k in ('status', 'is4k') if k in r}
                            for r in requests_ if isinstance(r, dict)] if isinstance(requests_, list) else None
    return dict(media_info_field_state=field, media_record_state=(
        'extraction_failed' if error else 'record_returned' if field == 'object'
        else 'no_associated_record_returned' if field == 'null' else 'unavailable'),
        media_status_field_present='status' in media, request_list_state=(
            'extraction_failed' if error else 'empty_list' if request_field == 'list' and requests_ == []
            else 'requests_returned' if request_field == 'list' else request_field),
        request_observations=request_observations,
        standard_request_statuses=[label(r.get('status'), REQUEST) for r in request_observations if r.get('is4k') is False]
            if request_observations is not None else None,
        request_statuses_4k=[label(r.get('status'), REQUEST) for r in request_observations if r.get('is4k') is True]
            if request_observations is not None else None,
        external_service_link_present=media.get('externalServiceLinked'),
        external_service_4k_link_present=media.get('externalService4kLinked'),
        library_identifier_present=media.get('libraryIdentifierPresent'),
        library_identifier_4k_present=media.get('libraryIdentifier4kPresent'),
        radarr_monitored=media.get('monitored'),
        download_count=media.get('downloadCount'), download_count_4k=media.get('downloadCount4k'),
        standard_library_availability=(
            'seerr_reported_available' if status == 5 else 'seerr_reported_partially_available' if status == 4
            else 'not_reported_available' if status in (2, 3, 6, 7) else 'unknown'))


class Client:
    """Allowlisted GET endpoints only; no redirects, writes, or automatic stale fallback."""
    def __init__(self, base, key, cache, *, offline=False, ttl=86400, interval=.3,
                 retries=3, timeout=25, max_wait=60):
        u = urlsplit(base)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError('SEERR_URL must be an HTTP(S) base URL without credentials/query/fragment')
        self.base = base.rstrip('/').removesuffix('/api/v1')
        self.key, self.cache, self.offline = key, cache, offline
        self.ttl, self.interval, self.retries = ttl, interval, retries
        self.timeout, self.max_wait = timeout, max_wait
        self.session = requests.Session()
        self.session.headers.update({'X-Api-Key': key, 'Accept': 'application/json'})
        self.last = 0.0
        self.audit = []
        # Separate origins and credential scopes without persisting credentials.
        self.scope = hashlib.sha256((self.base + '\0' + key).encode()).hexdigest()
        private_dir(cache)

    def get(self, path, params=None):
        if not (path in ('/discover/movies', '/search') or re.fullmatch(r'/movie/[1-9]\d*', path)):
            raise ValueError('Endpoint is not on the exploratory GET allowlist')
        params = params or {}
        digest = hashlib.sha256(json.dumps([self.scope, path, params], sort_keys=True).encode()).hexdigest()
        file = self.cache / (digest + '.json')
        entry = None
        if file.exists() and not file.is_symlink():
            try:
                entry = json.loads(file.read_text())
                age = time.time() - entry['epoch']
                if entry['schema'] != 1 or not isinstance(entry['data'], dict) or age < 0:
                    entry = None
                elif path.startswith('/movie/') and entry['data'].get('id') != int(path.rsplit('/', 1)[1]):
                    entry = None
                elif not path.startswith('/movie/') and not isinstance(entry['data'].get('results'), list):
                    entry = None
            except (ValueError, KeyError, TypeError, OSError):
                entry = None
        if entry and (self.offline or age <= self.ttl):
            self.audit.append(dict(path=path, params=params, source='cache',
                                   fetched_at=entry['fetched_at'], stale=age > self.ttl))
            return entry['data']
        if self.offline:
            raise ApiError('offline_cache_miss')
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            try:
                # Seerr's OpenAPI validation rejects '+' for spaces in search queries.
                encoded = urlencode(params, quote_via=quote)
                response = self.session.get(self.base + '/api/v1' + path, params=encoded,
                                            timeout=self.timeout, allow_redirects=False)
            except requests.RequestException:
                if attempt == self.retries:
                    raise ApiError('network_failure') from None
                time.sleep(min(self.max_wait, 2 ** attempt + random.random()))
                continue
            status = response.status_code
            self.audit.append(dict(path=path, params=params, source='network',
                                   fetched_at=utcnow(), http_status=status, attempt=attempt))
            if status == 429 or 500 <= status <= 599:
                if attempt == self.retries:
                    raise ApiError('rate_limit_exhausted' if status == 429 else 'server_error', stop=status == 429)
                retry = response.headers.get('Retry-After')
                try:
                    delay = float(retry) if retry else 2 ** attempt + random.random()
                except ValueError:
                    try:
                        delay = parsedate_to_datetime(retry).timestamp() - time.time()
                    except (TypeError, ValueError, OverflowError):
                        delay = 2 ** attempt + random.random()
                if not math.isfinite(delay) or delay > self.max_wait:
                    raise ApiError('retry_after_exceeds_wait_budget', stop=True)
                time.sleep(max(0, delay))
                continue
            if status != 200:
                raise ApiError(f'http_{status}', stop=status in (401, 403) or 300 <= status < 400)
            try:
                raw = response.json()
                if not isinstance(raw, dict):
                    raise ValueError
                if path.startswith('/movie/'):
                    if raw.get('id') != int(path.rsplit('/', 1)[1]):
                        raise ValueError
                    data = sanitize_movie(raw)
                else:
                    if not isinstance(raw.get('results'), list):
                        raise ValueError
                    data = {k: raw[k] for k in ('page', 'totalPages', 'totalResults') if k in raw}
                    data['results'] = [sanitize_movie(r) for r in raw['results'] if isinstance(r, dict)]
            except (ValueError, TypeError):
                raise ApiError('invalid_json_or_schema') from None
            write_json(file, dict(schema=1, epoch=time.time(), fetched_at=utcnow(), data=data))
            return data
        raise ApiError('retry_exhausted')


def valid_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def discover(client, start, end, language, sort_by='popularity.desc'):
    rows, failures, seen_pages = {}, [], []
    page, pages, total, raw_count, invalid = 1, 1, None, 0, 0
    while page <= pages:
        try:
            params = dict(page=page, primaryReleaseDateGte=start,
                          primaryReleaseDateLte=end, sortBy=sort_by)
            if language is not None:
                params['language'] = language
            data = client.get('/discover/movies', params)
            reported_pages, reported_total = data.get('totalPages'), data.get('totalResults')
            if (data.get('page') != page or not isinstance(reported_pages, int)
                    or not 0 <= reported_pages <= 500 or not isinstance(reported_total, int)
                    or reported_total < 0 or (reported_pages == 0 and reported_total != 0)):
                raise ApiError('invalid_pagination')
            if page == 1:
                pages, total = max(1, reported_pages), reported_total
            elif max(1, reported_pages) != pages or reported_total != total:
                failures.append(dict(page=page, error='pagination_totals_changed'))
            seen_pages.append(page)
            raw_count += len(data['results'])
            for row in data['results']:
                if not valid_id(row.get('id')):
                    invalid += 1
                    continue
                rows.setdefault(row['id'], row)
        except ApiError as e:
            failures.append(dict(page=page, error=str(e)))
            if page == 1 or e.stop:
                break
        page += 1
    complete = not failures and invalid == 0 and len(seen_pages) == pages and len(rows) == total
    return list(rows.values()), dict(complete=complete, reported_total=total, expected_pages=pages,
        retrieved_pages=seen_pages, raw_rows=raw_count, unique_ids=len(rows), invalid_ids=invalid,
        duplicate_rows=raw_count - len(rows) - invalid, failures=failures)


def num(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def label(value, mapping):
    return mapping.get(value, 'unknown' if value is None else f'unrecognized:{value}')


def normalize(summary, detail=None, error=None):
    detail = detail or {}
    merged = {**summary, **detail}
    credits = detail.get('credits') or {}
    cast = credits.get('cast') if isinstance(credits.get('cast'), list) else None
    crew = credits.get('crew') if isinstance(credits.get('crew'), list) else None
    genres = [g['name'] for g in detail.get('genres', []) if g.get('name')]
    events = []
    for group in (detail.get('releases') or {}).get('results', []):
        for event in group.get('release_dates', []):
            events.append(dict(country=group.get('iso_3166_1'), type=event.get('type'),
                type_name=label(event.get('type'), RELEASE), date=event.get('release_date'),
                certification=event.get('certification') or None))
    media = merged.get('mediaInfo') if isinstance(merged.get('mediaInfo'), dict) else {}
    requests_ = media.get('requests')
    statuses = [label(r.get('status'), REQUEST) for r in requests_] if isinstance(requests_, list) else None
    runtime = num(detail.get('runtime'))
    runtime = runtime if runtime and runtime > 0 else None
    components = dict(overview=bool((merged.get('overview') or '').strip()), poster=bool(merged.get('posterPath')),
        genres=bool(genres or summary.get('genreIds')), language=bool(merged.get('originalLanguage')),
        runtime=runtime is not None, cast=bool(cast), director=any(p.get('job') == 'Director' for p in crew or []))
    summary_date, detail_date = summary.get('releaseDate') or None, detail.get('releaseDate') or None
    result = dict(tmdb_id=summary['id'], title=merged.get('title') or merged.get('originalTitle') or '(untitled)',
        original_title=merged.get('originalTitle'), primary_release_date=detail_date or summary_date,
        discovery_primary_release_date=summary_date, detail_primary_release_date=detail_date,
        release_date_disagrees=bool(summary_date and detail_date and summary_date != detail_date),
        adult=merged.get('adult'), video=merged.get('video'), popularity=num(merged.get('popularity')),
        vote_count=num(merged.get('voteCount')), vote_average=num(merged.get('voteAverage')),
        genre_ids=summary.get('genreIds'), genres=genres, original_language=merged.get('originalLanguage') or None,
        runtime=runtime, overview=merged.get('overview') or None, poster_present=components['poster'],
        cast=cast, crew=crew, cast_count=len(cast) if cast is not None else None,
        crew_count=len(crew) if crew is not None else None,
        directors=[p.get('name') for p in crew or [] if p.get('job') == 'Director'],
        person_ids=sorted({p['id'] for p in (cast or []) + (crew or []) if valid_id(p.get('id'))}),
        completeness=sum(components.values()), completeness_components=components,
        release_events=events, release_types=sorted({e['type_name'] for e in events}),
        digital_event_count=sum(e['type'] == 4 for e in events),
        production_status=detail.get('status'), media_status=label(media.get('status'), MEDIA),
        media_status_raw=media.get('status'), media_status_4k=label(media.get('status4k'), MEDIA),
        media_status_4k_raw=media.get('status4k'),
        request_statuses=statuses, request_count=len(requests_) if isinstance(requests_, list) else None,
        detail_ok=bool(detail), detail_error=error)
    result['rated_vote_average'] = result['vote_average'] if (result['vote_count'] or 0) > 0 else None
    result.update(media_observation(merged, error))
    return result


def enrich(client, summaries):
    result, stopped = [], None
    for i, row in enumerate(summaries):
        detail, error = None, stopped
        if not stopped:
            try:
                detail = client.get(f"/movie/{row['id']}")
            except ApiError as e:
                error = str(e)
                if e.stop:
                    stopped = 'deferred_after_' + error
        result.append(normalize(row, detail, error))
        if (i + 1) % 50 == 0:
            print(f'Enriched {i + 1}/{len(summaries)} candidates', flush=True)
    return result


def simulate(row, cfg):
    hard = []
    if row['adult'] is True:
        hard.append('explicit_adult')
    if row['media_status'] == 'blocklisted':
        hard.append('seerr_blocklisted')
    if row['media_status'] in ('available', 'partially_available', 'pending', 'processing'):
        hard.append('existing_standard_media_or_workflow')
    if any(s in ('pending', 'approved', 'completed') for s in row['request_statuses'] or []):
        hard.append('existing_request_workflow')
    popular = row['popularity'] is not None and row['popularity'] >= cfg['popularity_min']
    metadata = row['completeness'] >= cfg['completeness_min'] and row['runtime'] is not None and row['runtime'] >= cfg['runtime_min']
    rated = (row['vote_count'] or 0) >= cfg['votes_min'] and (row['vote_average'] or 0) >= cfg['rating_min']
    niche = bool(set(row['genres']) & set(cfg['niche_genres'])) and row['completeness'] >= cfg['completeness_min']
    curated = row['tmdb_id'] in cfg['niche_tmdb_ids'] or bool(set(row['person_ids']) & set(cfg['person_ids']))
    paths = [name for name, ok in [('popular', popular), ('metadata', metadata), ('rated', rated),
                                  ('niche_metadata', niche), ('curated_title_or_person', curated)] if ok]
    # Do not treat failed enrichment or unreleased sparse metadata as a firm negative.
    sparse_upcoming = not row['detail_ok'] or (row['production_status'] in
                       ('Rumored', 'Planned', 'In Production', 'Post Production'))
    if sparse_upcoming:
        paths.append('defer_sparse_or_failed_detail')
    score = round(math.log1p(max(0, row['popularity'] or 0)) + row['completeness'] / 7 + int(rated) + int(niche) + 2 * int(curated), 4)
    passes = dict(broad=True, popularity=popular, metadata=metadata,
                  multi_path=bool(paths), soft_priority=True)
    return [dict(tmdb_id=row['tmdb_id'], title=row['title'], approach=a,
        included=not hard and passes[a], hard_exclusions=hard,
        soft_exclusion=[] if passes[a] else [dict(popularity='below_or_unknown_popularity',
            metadata='insufficient_metadata_or_runtime', multi_path='no_qualifying_path')[a]],
        qualifying_paths=paths, priority=score,
        disposition='excluded' if hard or not passes[a] else
                    'defer' if sparse_upcoming and not (popular or metadata or rated or niche or curated) else 'retain')
        for a in APPROACHES]


def norm_title(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def read_history():
    """Existing connector only; DB-enforced read-only repeatable snapshot; no DDL/bootstrap."""
    from api.db.connection import connect_db
    from psycopg2.extras import RealDictCursor
    conn = connect_db()
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ', autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute("SET LOCAL lock_timeout = '3s'")
            cur.execute("""
                WITH viewer AS (
                    SELECT rating_key, username, COUNT(*) AS plays,
                        SUM(GREATEST(played_duration, 0)) AS played_seconds,
                        MAX(percent_complete) AS max_percent,
                        MIN(watched_at) AS first_watch, MAX(watched_at) AS last_watch
                    FROM public.watch_history WHERE media_type = 'movie'
                    GROUP BY rating_key, username
                ), agg AS (
                    SELECT v.rating_key, SUM(plays) AS plays,
                        COUNT(username) AS viewers,
                        COUNT(*) FILTER (WHERE username IS NOT NULL AND
                          (max_percent >= 50 OR played_seconds >= l.duration / 2000.0)) AS engaged_viewers,
                        SUM(played_seconds) AS played_seconds,
                        MIN(first_watch) AS first_watch, MAX(last_watch) AS last_watch
                    FROM viewer v JOIN public.library l ON l.rating_key = v.rating_key
                    GROUP BY v.rating_key
                )
                SELECT l.rating_key, l.title, l.year, l.added_at,
                    COALESCE(a.plays, 0)::int AS plays, COALESCE(a.viewers, 0)::int AS viewers,
                    COALESCE(a.engaged_viewers, 0)::int AS engaged_viewers,
                    COALESCE(a.played_seconds, 0)::bigint AS played_seconds,
                    a.first_watch, a.last_watch
                FROM public.library l LEFT JOIN agg a ON a.rating_key = l.rating_key
                WHERE l.media_type = 'movie' ORDER BY l.rating_key
            """)
            rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
        return rows, dict(available=True, movie_count=len(rows), snapshot_at=utcnow(),
            definition='Engaged viewer: >=50% maximum session completion OR cumulative played seconds >=50% current library runtime. Replays can inflate cumulative engagement. This is an exploratory proxy, not a training label.')
    finally:
        conn.rollback()
        conn.close()


def historical_sample(history, count):
    ordered = sorted(history, key=lambda r: (-r['engaged_viewers'], -r['viewers'], r['rating_key']))
    if count >= len(ordered):
        return ordered
    n_top = (count + 2) // 3
    top = ordered[:n_top]
    remaining = ordered[n_top:]
    zero = [r for r in remaining if r['viewers'] == 0]
    rng = random.Random(20261028)
    low = rng.sample(zero, min(count // 3, len(zero)))
    used = {r['rating_key'] for r in top + low}
    pool = [r for r in remaining if r['rating_key'] not in used]
    return top + low + rng.sample(pool, min(count - len(top) - len(low), len(pool)))


def match_history(client, history, count):
    matches, mapping = [], []
    for source in historical_sample(history, count):
        record = dict(rating_key=source['rating_key'], title=source['title'], year=source['year'])
        try:
            if not source['title'] or not source['year']:
                raise ApiError('missing_title_or_year')
            data = client.get('/search', dict(query=source['title'], page=1, language='en'))
            options = {r['id']: r for r in data['results'] if valid_id(r.get('id'))
                and r.get('mediaType') == 'movie' and str(r.get('releaseDate', ''))[:4] == str(source['year'])
                and norm_title(source['title']) in (norm_title(r.get('title')), norm_title(r.get('originalTitle')))}
            if len(options) != 1:
                raise ApiError('ambiguous_match' if options else 'no_exact_title_year_match_on_search_page_1')
            summary = next(iter(options.values()))
            detail = client.get(f"/movie/{summary['id']}")
            # Revalidate identity against the enriched response too.
            if str(detail.get('releaseDate', ''))[:4] != str(source['year']) or norm_title(source['title']) not in (
                    norm_title(detail.get('title')), norm_title(detail.get('originalTitle'))):
                raise ApiError('detail_identity_mismatch')
            row = normalize(summary, detail)
            # Curation signal comparison must not exclude historical titles because they are now owned.
            row['observed_media_status'] = row['media_status']
            row['observed_request_statuses'] = row['request_statuses']
            row['media_status'] = 'unknown'
            row['request_statuses'] = None
            row['historical_engagement'] = source
            matches.append(row)
            record.update(tmdb_id=row['tmdb_id'], result='exact_title_year_heuristic')
        except ApiError as e:
            record['result'] = str(e)
            if e.stop:
                mapping.append(record)
                break
        mapping.append(record)
    counts = Counter(r['tmdb_id'] for r in matches)
    # Multiple library editions can map to the same TMDB ID: avoid double-weighting titles.
    ambiguous = {k for k, v in counts.items() if v > 1}
    for record in mapping:
        if record.get('tmdb_id') in ambiguous:
            record['result'] = 'duplicate_library_editions_excluded'
    return [r for r in matches if r['tmdb_id'] not in ambiguous], mapping


def distributions(rows):
    result = {}
    for field in ('popularity', 'vote_count', 'vote_average', 'rated_vote_average', 'runtime',
                  'completeness', 'cast_count', 'crew_count', 'digital_event_count', 'request_count'):
        values = sorted(r[field] for r in rows if num(r[field]) is not None)
        def quantile(q):
            if not values:
                return None
            pos = (len(values) - 1) * q
            lo, hi = math.floor(pos), math.ceil(pos)
            return round(values[lo] + (values[hi] - values[lo]) * (pos - lo), 3)
        result[field] = dict(known=len(values), unknown=len(rows) - len(values), zero=sum(v == 0 for v in values),
            min=min(values) if values else None, p25=quantile(.25), median=quantile(.5), p75=quantile(.75),
            p90=quantile(.9), p95=quantile(.95), max=max(values) if values else None)
    for field in ('original_language', 'media_status', 'media_status_4k', 'production_status', 'detail_error'):
        result[field] = dict(Counter(r[field] if r[field] is not None else 'unknown' for r in rows).most_common())
    for field in ('genres', 'release_types', 'request_statuses'):
        result[field] = dict(Counter(v for r in rows for v in (r[field] or ['unknown_or_empty'])).most_common())
    result['availability'] = {k: sum(bool(r['completeness_components'][k]) for r in rows)
                              for k in ('overview', 'poster', 'genres', 'language', 'runtime', 'cast', 'director')}
    result['crew_jobs'] = dict(Counter(p.get('job') or 'unknown' for r in rows for p in r['crew'] or []).most_common())
    result['cast_names_top20'] = dict(Counter(p.get('name') or 'unknown' for r in rows for p in r['cast'] or []).most_common(20))
    result['detail_successes'] = sum(r['detail_ok'] for r in rows)
    result['release_events_present'] = sum(bool(r['release_events']) for r in rows)
    result['primary_release_date_unknown'] = sum(not r['primary_release_date'] for r in rows)
    result['detail_primary_release_date_unknown'] = sum(not r['detail_primary_release_date'] for r in rows)
    result['discovery_detail_release_date_disagreements'] = sum(r['release_date_disagrees'] for r in rows)
    result['future_digital_events'] = sum(any(e['type'] == 4 and (e['date'] or '')[:10] > date.today().isoformat()
                                             for e in r['release_events']) for r in rows)
    return result


def compare_history(rows, cfg):
    result = []
    total_engagement = sum(r['historical_engagement']['engaged_viewers'] for r in rows)
    for approach in APPROACHES:
        kept = [r for r in rows if next(d for d in simulate(r, cfg) if d['approach'] == approach)['included']]
        captured = sum(r['historical_engagement']['engaged_viewers'] for r in kept)
        result.append(dict(approach=approach, matched_titles=len(rows), retained=len(kept),
            engaged_title_viewer_pairs_retained=captured, engaged_title_viewer_pairs_total=total_engagement,
            engagement_retention=captured / total_engagement if total_engagement else None,
            engaged_titles_retained=sum(r['historical_engagement']['engaged_viewers'] > 0 for r in kept),
            zero_viewer_titles_retained=sum(r['historical_engagement']['viewers'] == 0 for r in kept)))
    return result


def md_table(headers, rows):
    def cell(v):
        return str(v).replace('|', '\\|').replace('\n', ' ')
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'] + [
        '| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]


def render_report(manifest, rows, decisions, stats, history_meta, history_rows, comparisons, cfg):
    coverage = manifest['discovery']
    lines = ['# Seerr candidate curation exploration', '',
        f"Snapshot: {manifest['started_at']}. Inclusive primary release dates {manifest['start']} through {manifest['end']}.", '',
        f"Discovery complete: **{coverage['complete']}**. {len(rows)} unique titles; {coverage['raw_rows']} raw rows; "
        f"{len(coverage['retrieved_pages'])}/{coverage['expected_pages']} pages; upstream total {coverage['reported_total']}; "
        f"{coverage['duplicate_rows']} duplicate rows. Details succeeded for {stats['detail_successes']}/{len(rows)} titles.", '',
        'This is a live, paginated observation, not an atomic upstream snapshot. All simulations are exploratory; no request or model scoring ran. '
        'Incomplete coverage and failed enrichment are unknown data, never proof of no interest.', '',
        '## Field availability and distributions', '']
    lines += md_table(['Field', 'Known', 'Unknown', 'Zero', 'Min', 'P25', 'Median', 'P75', 'P90', 'P95', 'Max'],
        [[k] + [v[x] for x in ('known', 'unknown', 'zero', 'min', 'p25', 'median', 'p75', 'p90', 'p95', 'max')]
         for k, v in stats.items() if isinstance(v, dict) and 'median' in v])
    lines += ['', 'Completeness is a 0–7 descriptive count: overview, poster, genres, language, positive runtime, cast, director. '
        'Zero-vote ratings are not supported ratings; `rated_vote_average` excludes them. Missing/zero runtime is unknown.', '']
    for field in ('availability', 'genres', 'original_language', 'media_status', 'media_status_4k',
                  'request_statuses', 'production_status', 'release_types', 'cast_names_top20'):
        lines += [f'### {field}', ''] + md_table(['Value', 'Titles / occurrences'], stats[field].items()) + ['']
    lines += [f"Titles with release events: {stats['release_events_present']}/{len(rows)}. "
        f"Titles with future digital events at execution: {stats['future_digital_events']}.", '',
        f"Missing detail primary date: {stats['detail_primary_release_date_unknown']}; "
        f"missing both detail and discovery primary date: {stats['primary_release_date_unknown']}; "
        f"discovery/detail primary-date disagreements: {stats['discovery_detail_release_date_disagreements']}. "
        'Both date observations are retained. The effective primary date falls back to discovery when detail is empty; '
        'a changed detail date does not silently remove a discovered title.', '',
        'Release types: 1 premiere, 2 limited theatrical, 3 theatrical, 4 digital, 5 physical, 6 TV. '
        'Events retain country, date and type. Primary release date does not establish digital availability, and a dated digital event is not a verified downloadable source. '
        'Null/missing mediaInfo, status 1 and unrecognized status codes remain unknown; unknown is not confirmed unrequested. '
        'An omitted request list is unknown; an empty list is observed empty. Standard and 4K media statuses remain separate.', '',
        '## Simulated rules', '', 'All approaches share proposed hard exclusions: explicit adult content; Seerr blocklist; '
        'standard media already available/partially available or pending/processing; explicit pending/approved/completed request. '
        'These are policy/workflow exclusions, not low-engagement predictions. Adult policy is provisional. '
        'Unknown status, language, genre, release date, zero votes, and short/missing runtime are not common hard exclusions.', '',
        f"Parameters: `{json.dumps(cfg, sort_keys=True)}`", '',
        '- broad: retain every title passing common hard exclusions.',
        '- popularity: additionally require popularity_min; this is an intentionally restrictive comparison.',
        '- metadata: additionally require completeness_min and runtime_min; this tests metadata readiness, not appeal.',
        '- multi_path: popularity OR metadata OR supported rating OR niche genre plus completeness OR curated title/person; defer failed/sparse in-production details.',
        '- soft_priority: retain the broad pool; order by log1p(popularity) + completeness/7 + supported-rating + niche + 2*curated. No top-N limit.', '',
        'Niche genres are provisional examples, not asserted community preferences. Configurable TMDB/person allowlists supply explicit exceptions. '
        'A future release with sparse metadata may need deferral; future release dates never cause exclusion.', '']
    counts = []
    for a in APPROACHES:
        ds = [d for d in decisions if d['approach'] == a]
        counts.append([a, sum(d['included'] for d in ds), sum(bool(d['hard_exclusions']) for d in ds),
                       sum(not d['included'] and not d['hard_exclusions'] for d in ds), sum(d['disposition'] == 'defer' for d in ds)])
    lines += md_table(['Approach', 'Survivors (incl. defer)', 'Hard excluded', 'Soft excluded', 'Deferred'], counts) + ['']
    lookup = {r['tmdb_id']: r for r in rows}
    for a in APPROACHES:
        lines += [f'### {a} examples', '']
        samples = []
        for included in (True, False):
            options = sorted([d for d in decisions if d['approach'] == a and d['included'] == included],
                             key=lambda d: (-d['priority'], d['tmdb_id']))
            # Three high-priority and two low-priority examples expose the distribution tails.
            selected = options[:3] + [d for d in options[-2:] if d not in options[:3]]
            for d in selected:
                r = lookup[d['tmdb_id']]
                reason = d['hard_exclusions'] + d['soft_exclusion'] if not included else d['qualifying_paths'] or ['broad_eligible']
                samples.append([d['disposition'], f"{d['title']} ({d['tmdb_id']})", r['popularity'],
                                r['vote_count'], r['runtime'], r['completeness'], ', '.join(reason)])
            if not options:
                samples.append(['included' if included else 'excluded', '(none)', '', '', '', '', ''])
        lines += md_table(['Decision', 'Title (TMDB)', 'Popularity', 'Votes', 'Runtime', 'Completeness', 'Reason'], samples) + ['']
    lines += ['Every title/approach decision, all hard and soft exclusion reasons, qualifying paths, and priority are in `decisions.json` and `decisions.csv`.', '',
        '## Historical engagement comparison', '', f"History coverage: `{json.dumps(history_meta, sort_keys=True)}`", '']
    if comparisons:
        lines += md_table(['Approach', 'Matched sample', 'Retained', 'Engaged pairs retained/total', 'Retention'],
            [[c['approach'], c['matched_titles'], c['retained'],
              f"{c['engaged_title_viewer_pairs_retained']}/{c['engaged_title_viewer_pairs_total']}",
              f"{c['engagement_retention']:.1%}" if c['engagement_retention'] is not None else 'unknown'] for c in comparisons]) + ['']
    lines += [f'Historical matched/enriched titles: {len(history_rows)}. Matching uses unique exact normalized title/year on Seerr search page 1, '
        'then validates details; this is a heuristic, not verified identity. Ambiguous matches and duplicate library editions are excluded from comparisons. '
        'All selected titles and failures are in `history_matches.json`.', '',
        'Historical sampling uses one third highest-engagement titles, up to one third seeded zero-viewer library titles, and seeded remaining titles. '
        'It is deliberately selected and is not a population estimate. Current ownership/request state is neutralized only in the historical signal comparison. '
        'Current popularity, votes, runtime, credits, release status and completeness may have increased after past discovery: severe temporal leakage prevents treating this as a prospective backtest. '
        'No historical discovery snapshots, rejected-title outcomes, availability exposure, removal history, or equal follow-up window are available. '
        'Library titles were already selected by operators/requesters; zero observed plays does not prove no demand. '
        'Counts are title-viewer pairs, not distinct community users across all films. History is limited to retained watch_history and current library rows.', '',
        '## Recommendation and next evidence', '',
        'Prefer broad retention with soft priority while collecting prospective snapshots and outcomes. If a preliminary candidate gate is necessary, '
        'test the multi-path rule with a defer/revisit lane; compare each path and false exclusions before activating anything. '
        'Keep minimum votes paired with ratings; do not require votes for unreleased films. Avoid hard language, genre, runtime, metadata-completeness or popularity cutoffs. '
        'Tune popularity_min, votes_min, rating_min, completeness_min, runtime_min, niche_genres, niche_tmdb_ids and person_ids in a separate JSON file. '
        'Thresholds here are illustrative, not calibrated or enabled.', '',
        'Before automation: validate Seerr visibility and region/language scope, preserve timestamped candidates and rule exclusions, '
        'measure community engagement after comparable availability windows, and evaluate niche/upcoming recall. '
        'Separate candidate eligibility from regional release readiness and request deduplication. Unknown state must be rechecked before any eventual request.', '',
        '## Provenance and limitations', '',
        'The manifest records parameter values, completeness, sanitized failures, timestamps, cache/network provenance and output hashes. '
        'Cache entries are keyed by origin, credential scope, endpoint and query; online TTL defaults to 24 hours, with no stale fallback. '
        'Offline mode explicitly permits cached stale entries and records them. Media/request status can become stale sooner than metadata. '
        'The initial 329/17 count is a supplied reference, not a forced target. Seerr server/user discovery settings can limit scope; '
        '`--language all` asks upstream for all original languages, while region remains server/user-configured. '
        'Snapshot collection can drift while pages load; deduplication/count reconciliation flags observed discrepancies but cannot prove atomicity. '
        'By default discovery uses the server/user language scope. The manifest records an explicit override when supplied.', '',
        'Upstream references (develop branch, not an assertion of the installed server version): '
        '[discovery route](https://github.com/seerr-team/seerr/blob/develop/server/routes/discover.ts), '
        '[movie mapping](https://github.com/seerr-team/seerr/blob/develop/server/models/Movie.ts), '
        '[status enums](https://github.com/seerr-team/seerr/blob/develop/server/constants/media.ts).', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True, type=date.fromisoformat)
    parser.add_argument('--end', required=True, type=date.fromisoformat)
    parser.add_argument('--credentials-file', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cache-dir', type=Path, default=ROOT / 'artifacts/seerr-exploration/cache')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--cache-ttl-hours', type=float, default=24)
    parser.add_argument('--interval', type=float, default=.3)
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument('--language', help='Original-language override; omit to preserve Seerr configured scope; all broadens scope')
    parser.add_argument('--sort-by', choices=['popularity.desc', 'primary_release_date.asc', 'vote_count.desc'], default='popularity.desc')
    parser.add_argument('--rules', type=Path)
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--history-sample', type=int, default=60)
    args = parser.parse_args(argv)
    if args.start > args.end or args.interval < 0 or args.cache_ttl_hours < 0 or not 0 <= args.retries <= 5 or not 0 <= args.history_sample <= 300:
        parser.error('Invalid dates, timing, retries or history sample size')
    load_dotenv(ROOT / '.env', override=False)
    values = dotenv_values(args.credentials_file, interpolate=False) if args.credentials_file else {}
    base = os.getenv('SEERR_URL') or values.get('SEERR_URL') or values.get('SEER_URL')
    key = os.getenv('SEERR_API_KEY') or values.get('SEERR_API_KEY') or values.get('SEER_API_KEY')
    if not base or not key:
        parser.error('Configure SEERR_URL/SEERR_API_KEY or a dotenv credential file (SEER aliases supported)')
    cfg = dict(DEFAULT_RULES)
    if args.rules:
        provided = json.loads(args.rules.read_text())
        if not isinstance(provided, dict) or set(provided) - set(cfg):
            parser.error('Rule configuration contains unsupported keys')
        cfg.update(provided)
    for k in ('popularity_min', 'votes_min', 'rating_min', 'runtime_min', 'completeness_min'):
        if num(cfg[k]) is None or cfg[k] < 0:
            parser.error('Rule thresholds must be finite nonnegative numbers')
    for k in ('person_ids', 'niche_tmdb_ids'):
        if not isinstance(cfg[k], list) or not all(valid_id(v) for v in cfg[k]):
            parser.error('Rule ID allowlists must be lists of positive integers')
    if not isinstance(cfg['niche_genres'], list) or not all(isinstance(v, str) for v in cfg['niche_genres']):
        parser.error('niche_genres must be a list of genre names')
    private_dir(args.output)
    client = Client(base, key, args.cache_dir, offline=args.offline, ttl=args.cache_ttl_hours * 3600,
                    interval=args.interval, retries=args.retries)
    manifest = dict(schema_version=1, started_at=utcnow(), start=args.start.isoformat(), end=args.end.isoformat(),
        language=args.language, sort_by=args.sort_by, rules=cfg, offline=args.offline, cache_ttl_hours=args.cache_ttl_hours,
        interval=args.interval, retries=args.retries, history_sample_requested=args.history_sample,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    summaries, coverage = discover(client, str(args.start), str(args.end), args.language, args.sort_by)
    manifest['discovery'] = coverage
    rows = enrich(client, summaries)
    decisions = [d for r in rows for d in simulate(r, cfg)]
    history, history_rows, matches = [], [], []
    history_meta = dict(available=False, reason='not_requested')
    if args.history:
        if args.offline:
            history_file = args.output / 'history_library.json'
            if history_file.exists():
                saved = json.loads(history_file.read_text())
                history, history_meta = saved['rows'], saved['metadata']
                history_meta = {**history_meta, 'reused_snapshot_offline': True}
            else:
                history_meta = dict(available=False, reason='offline_history_snapshot_missing')
        else:
            try:
                history, history_meta = read_history()
            except Exception as e:
                history_meta = dict(available=False, reason=type(e).__name__)
        if history:
            history_rows, matches = match_history(client, history, args.history_sample)
    comparisons = compare_history(history_rows, cfg)
    # Same-week overlap is descriptive only; preserve ambiguous title/year collisions.
    history_index = defaultdict(list)
    for h in history:
        history_index[(norm_title(h['title']), str(h['year']))].append(h)
    overlap = []
    for row in rows:
        found = {h['rating_key']: h for title in (row['title'], row['original_title'])
                 for h in history_index.get((norm_title(title), (row['primary_release_date'] or '')[:4]), [])}
        if found:
            overlap.append(dict(tmdb_id=row['tmdb_id'], title=row['title'],
                result='exact_title_year_heuristic' if len(found) == 1 else 'ambiguous', library_matches=list(found.values())))
    stats = distributions(rows)
    write_json(args.output / 'candidates.json', rows)
    write_csv(args.output / 'candidates.csv', rows)
    write_json(args.output / 'decisions.json', decisions)
    write_csv(args.output / 'decisions.csv', decisions)
    write_json(args.output / 'distributions.json', stats)
    write_json(args.output / 'history_library.json', dict(metadata=history_meta, rows=history))
    write_json(args.output / 'history_matches.json', matches)
    write_json(args.output / 'history_candidates.json', history_rows)
    historical_decisions = [dict(**d, historical_engagement=r['historical_engagement'])
                            for r in history_rows for d in simulate(r, cfg)]
    write_json(args.output / 'history_decisions.json', historical_decisions)
    write_csv(args.output / 'history_decisions.csv', historical_decisions)
    write_json(args.output / 'history_comparison.json', comparisons)
    write_json(args.output / 'history_candidate_overlap.json', overlap)
    manifest['history'] = dict(**history_meta, sampled=len(matches), matched=len(history_rows), candidate_overlap=len(overlap))
    manifest['requests'] = client.audit
    manifest['finished_at'] = utcnow()
    manifest['enrichment_complete'] = all(r['detail_ok'] for r in rows)
    write_text(args.output / 'analysis.md', render_report(manifest, rows, decisions, stats, history_meta, history_rows, comparisons, cfg))
    manifest['outputs_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(args.output.iterdir()) if p.is_file() and p.name != 'manifest.json'}
    write_json(args.output / 'manifest.json', manifest)
    print(json.dumps(dict(output=str(args.output), candidates=len(rows), discovery_complete=coverage['complete'],
        details_ok=stats['detail_successes'], historical_matches=len(history_rows),
        survivors={a: sum(d['included'] for d in decisions if d['approach'] == a) for a in APPROACHES})))
    return 0 if coverage['complete'] and manifest['enrichment_complete'] else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, requests.RequestException):
        # Never echo arbitrary exception text that might contain credentials or private URLs.
        print('Exploration failed: verify configuration, filesystem access and input formats.', file=sys.stderr)
        sys.exit(1)
