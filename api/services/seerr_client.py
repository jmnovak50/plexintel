"""Instance-configured, GET-only Seerr transport and privacy-preserving metadata.

Independent of exploratory scripts, application startup, and model pipelines.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from io import StringIO
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import quote, urlencode, urlsplit

from dotenv import dotenv_values
import requests

from api.services.private_config import read_private_file


class SeerrError(RuntimeError):
    """Only fixed error categories may cross this boundary; no response bodies/URLs."""
    def __init__(self, code, *, stop=False):
        super().__init__(code)
        self.code, self.stop = code, stop


@dataclass(frozen=True)
class SeerrConfig:
    url: str = field(repr=False)
    api_key: str = field(repr=False)
    enabled: bool = False
    source_id: str | None = None
    media_types: tuple[str, ...] = ('movie',)
    languages: tuple[str, ...] = ('all',)
    lookback_days: int = 14
    lookahead_days: int = 90
    window_days: int = 14
    sort_by: str = 'primary_release_date.asc'
    max_pages: int = 500
    retries: int = 2
    timeout: float = 25
    interval: float = .3
    max_retry_after: float = 60
    metadata_ttl_hours: float = 24
    failed_retry_hours: float = 1
    cache_enabled: bool = True
    refresh_batch_size: int = 1000
    max_requests: int = 10000

    def __post_init__(self):
        try:
            parts = urlsplit(self.url)
            parts.port
        except ValueError:
            raise SeerrError('invalid_base_url') from None
        if (parts.scheme not in ('https', 'http') or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment
                or any(s in ('.', '..') for s in parts.path.split('/'))):
            raise SeerrError('invalid_base_url')
        if not self.api_key or not self.api_key.isascii() or any(c.isspace() for c in self.api_key):
            raise SeerrError('invalid_api_credential')
        if self.source_id is not None and (not isinstance(self.source_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', self.source_id)):
            raise SeerrError('invalid_discovery_source_id')
        if (not self.media_types or len(set(self.media_types)) != len(self.media_types)
                or any(t not in ('movie', 'tv') for t in self.media_types)):
            raise SeerrError('invalid_discovery_media_types')
        if not self.languages or len(self.languages) > 20 or len(set(self.languages)) != len(self.languages):
            raise SeerrError('invalid_language_scopes')
        if any(not re.fullmatch(r'(all|configured|[a-z]{2,3}(?:\|[a-z]{2,3})*)', s) for s in self.languages):
            raise SeerrError('invalid_language_scopes')
        if self.sort_by not in ('primary_release_date.asc', 'primary_release_date.desc', 'first_air_date.asc', 'first_air_date.desc', 'popularity.desc', 'vote_count.desc'):
            raise SeerrError('invalid_sort_order')
        for name, lo, hi in [('lookback_days', 0, 3650), ('lookahead_days', 0, 3650),
                             ('window_days', 1, 366), ('max_pages', 1, 500), ('retries', 0, 5),
                             ('refresh_batch_size', 1, 10000), ('max_requests', 1, 100000)]:
            v = getattr(self, name)
            if type(v) is not int or not lo <= v <= hi:
                raise SeerrError('invalid_' + name)
        for name, lo, hi in [('timeout', .1, 300), ('interval', 0, 60), ('max_retry_after', 0, 60),
                             ('metadata_ttl_hours', 0, 8760), ('failed_retry_hours', 0, 720)]:
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
                raise SeerrError('invalid_' + name)

    @property
    def base_url(self):
        return self.url.rstrip('/').removesuffix('/api/v1')

    @property
    def source_key(self):
        return hashlib.sha256(self.base_url.encode()).hexdigest()

    def require_source_identity(self):
        if self.source_id is None:
            raise SeerrError('discovery_source_id_required', stop=True)


def load_seerr_config(credentials_file=None, **overrides):
    """Environment/dotenv bootstrap belongs to the CLI; private-file reads have no side effects."""
    values = {}
    configured = credentials_file or os.getenv('SEERR_DISCOVERY_CREDENTIALS_FILE')
    default = Path.home() / '.config/plexintel/seerr-discovery.env'
    if configured or default.exists():
        values.update(dotenv_values(stream=StringIO(read_private_file(configured or default)), interpolate=False))
        if any(v is None or '\n' in v or '\r' in v for v in values.values()):
            raise SeerrError('invalid_private_configuration')
    values.update(os.environ)
    def get(name, default=None):
        return values.get(name, default)
    def boolean(name, default):
        value = str(get(name, str(default))).lower()
        if value not in ('true', 'false', '1', '0'):
            raise SeerrError('invalid_boolean_configuration')
        return value in ('true', '1')
    key = get('SEERR_API_KEY') or get('SEER_API_KEY')
    if get('SEERR_API_KEY_FILE'):
        key = read_private_file(get('SEERR_API_KEY_FILE')).strip()
    try:
        cfg = SeerrConfig(
            url=get('SEERR_URL') or get('SEER_URL') or '', api_key=key or '',
            enabled=boolean('SEERR_DISCOVERY_ENABLED', False),
            source_id=get('SEERR_DISCOVERY_SOURCE_ID'),
            media_types=tuple(s.strip() for s in get('SEERR_DISCOVERY_MEDIA_TYPES', 'movie').split(',')),
            languages=tuple(s.strip() for s in get('SEERR_DISCOVERY_LANGUAGES', 'all').split(',')),
            sort_by=get('SEERR_DISCOVERY_SORT', 'primary_release_date.asc'),
            cache_enabled=boolean('SEERR_DISCOVERY_CACHE_ENABLED', True),
            **{name: int(get('SEERR_DISCOVERY_' + name.upper(), default)) for name, default in
               [('lookback_days', 14), ('lookahead_days', 90), ('window_days', 14), ('max_pages', 500), ('retries', 2), ('refresh_batch_size', 1000), ('max_requests', 10000)]},
            **{name: float(get('SEERR_DISCOVERY_' + name.upper(), default)) for name, default in
               [('timeout', 25), ('interval', .3), ('max_retry_after', 60), ('metadata_ttl_hours', 24), ('failed_retry_hours', 1)]})
        return replace(cfg, **{k: v for k, v in overrides.items() if v is not None})
    except (TypeError, ValueError):
        raise SeerrError('invalid_configuration_value') from None


def valid_tmdb_id(value):
    return type(value) is int and 0 < value <= 9223372036854775807


def validate_media_type(value):
    if value not in ('movie', 'tv'):
        raise SeerrError('unsupported_media_type')
    return value


def parse_iso_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def _state(source, key, valid):
    return 'omitted' if key not in source else 'null' if source[key] is None else 'value' if valid(source[key]) else 'invalid'


def _scalar(value):
    return value is None or isinstance(value, (str, bool, int)) or isinstance(value, float) and math.isfinite(value)


def _objects(value, keys):
    return [{k: row[k] for k in keys if k in row and _scalar(row[k])} for row in value if isinstance(row, dict)]


TEXT_FIELDS = ('title', 'originalTitle', 'overview', 'originalLanguage', 'releaseDate', 'status',
               'imdbId', 'posterPath', 'backdropPath')
NUMBER_FIELDS = ('popularity', 'voteCount', 'voteAverage', 'runtime')


def sanitize_movie(raw):
    return _sanitize_title(raw, 'movie')


def sanitize_tv(raw):
    return _sanitize_title(raw, 'tv')


def _sanitize_title(raw, media_type):
    """Allowlisted source fields; never store requester identities or internal service/library IDs."""
    if not isinstance(raw, dict) or not valid_tmdb_id(raw.get('id')):
        raise SeerrError('invalid_movie_identity')
    validate_media_type(media_type)
    # An endpoint supplies authoritative context when detail responses omit mediaType.
    if 'mediaType' in raw and raw['mediaType'] != media_type:
        raise SeerrError('media_type_mismatch')
    result = {'id': raw['id']}
    if media_type == 'tv':
        result['mediaType'] = 'tv'
    states = {}
    text_fields = TEXT_FIELDS if media_type == 'movie' else ('name', 'originalName', 'firstAirDate', 'type',
        'overview', 'originalLanguage', 'status', 'posterPath', 'backdropPath')
    number_fields = NUMBER_FIELDS if media_type == 'movie' else ('popularity', 'voteCount', 'voteAverage', 'numberOfEpisodes', 'numberOfSeasons')
    validators = {k: lambda v: isinstance(v, str) for k in text_fields}
    validators.update({k: lambda v: type(v) in (int, float) and math.isfinite(v) for k in number_fields})
    validators.update({k: lambda v: type(v) is bool for k in (('adult', 'video') if media_type == 'movie' else ('inProduction',))})
    for key, valid in validators.items():
        states[key] = _state(raw, key, valid)
        if states[key] in ('value', 'null'):
            result[key] = raw[key]
    for key, keys in [('genres', ('id', 'name')), ('productionCountries', ('iso_3166_1', 'name')),
                      ('productionCompanies', ('id', 'name', 'originCountry'))]:
        # Preserve the legacy movie projection/fingerprint. TV collections must not
        # turn malformed members into authoritative emptiness by filtering them.
        required = 'iso_3166_1' if key == 'productionCountries' else 'id'
        def valid_objects(value):
            return isinstance(value, list) and (media_type == 'movie' or all(
                isinstance(row, dict) and
                (isinstance(row.get(required), str) and bool(row[required]) if required == 'iso_3166_1'
                 else valid_tmdb_id(row.get(required))) and
                all(_scalar(row[k]) for k in keys if k in row) for row in value))
        states[key] = _state(raw, key, valid_objects)
        if states[key] == 'value':
            result[key] = _objects(raw[key], keys)
        elif states[key] == 'null':
            result[key] = None
    states['genreIds'] = _state(raw, 'genreIds', lambda v: isinstance(v, list) and
        (media_type == 'movie' or all(valid_tmdb_id(ident) for ident in v)))
    if states['genreIds'] == 'value':
        result['genreIds'] = [v for v in raw['genreIds'] if valid_tmdb_id(v)]
    elif states['genreIds'] == 'null':
        result['genreIds'] = None
    for key in (('credits', 'releases', 'mediaInfo') if media_type == 'movie' else ('credits', 'mediaInfo')):
        states[key] = _state(raw, key, lambda v: isinstance(v, dict))
        if states[key] == 'null':
            result[key] = None
    if states['credits'] == 'value':
        credit = raw['credits']
        result['credits'] = {}
        for key, keys in [('cast', ('id', 'name', 'character', 'order')), ('crew', ('id', 'name', 'job', 'department'))]:
            if isinstance(credit.get(key), list) and all(isinstance(p, dict) for p in credit[key]):
                result['credits'][key] = _objects(credit[key], keys)
            elif key in credit and credit[key] is None:
                result['credits'][key] = None
            elif key in credit:
                result['credits'].setdefault('_fields', {})[key] = 'invalid'
    if media_type == 'movie' and states['releases'] == 'value':
        releases = raw['releases']
        clean = {'_fields': {'results': _state(releases, 'results', lambda v: isinstance(v, list))}}
        if clean['_fields']['results'] == 'null':
            clean['results'] = None
        elif clean['_fields']['results'] == 'value':
            clean['results'] = []
            for group in releases['results']:
                if not isinstance(group, dict):
                    clean['results'].append({'_fields': {'release_dates': 'invalid'}})
                    continue
                state = _state(group, 'release_dates', lambda v: isinstance(v, list) and all(isinstance(e, dict) for e in v))
                item = {'iso_3166_1': group.get('iso_3166_1') if isinstance(group.get('iso_3166_1'), str) else None,
                        '_fields': {'release_dates': state}}
                if state == 'value':
                    item['release_dates'] = _objects(group['release_dates'], ('type', 'release_date', 'certification', 'iso_639_1'))
                elif state == 'null':
                    item['release_dates'] = None
                clean['results'].append(item)
        result['releases'] = clean
    if states['mediaInfo'] == 'value':
        media = raw['mediaInfo']
        clean = {}
        media_states = {k: _state(media, k, lambda v: type(v) is int) for k in ('status', 'status4k')}
        for k in ('status', 'status4k'):
            if media_states[k] in ('value', 'null'):
                clean[k] = media[k]
        media_states['requests'] = _state(media, 'requests', lambda v: isinstance(v, list) and all(isinstance(r, dict) for r in v))
        if media_states['requests'] == 'value':
            clean['requests'] = _objects(media['requests'], ('status', 'is4k'))
            if media_type == 'tv':
                for source, request in zip(media['requests'], clean['requests']):
                    state = _state(source, 'seasons', lambda v: isinstance(v, list) and all(isinstance(s, dict) for s in v))
                    request['_fields'] = {'seasons': state}
                    if state == 'value':
                        request['seasons'] = _objects(source['seasons'], ('seasonNumber', 'status'))
                    elif state == 'null':
                        request['seasons'] = None
        elif media_states['requests'] == 'null':
            clean['requests'] = None
        for output, keys in [('externalServiceLinked', ('externalServiceId',)),
                             ('externalService4kLinked', ('externalServiceId4k',)),
                             ('libraryIdentifierPresent', ('ratingKey', 'jellyfinMediaId'))]:
            if any(k in media for k in keys):
                clean[output] = any(media.get(k) is not None for k in keys)
        for k in ('monitored', 'monitored4k'):
            if type(media.get(k)) is bool:
                clean[k] = media[k]
        clean['_fields'] = media_states
        result['mediaInfo'] = clean
    if media_type == 'tv':
        for key, valid in [('episodeRunTime', lambda v: isinstance(v, list) and all(type(n) is int and n >= 0 for n in v)),
                           ('createdBy', lambda v: isinstance(v, list) and all(isinstance(p, dict) for p in v)),
                           ('seasons', lambda v: isinstance(v, list) and all(isinstance(p, dict) and type(p.get('seasonNumber')) is int and p['seasonNumber'] >= 0 for p in v))]:
            states[key] = _state(raw, key, valid)
            if states[key] == 'value':
                result[key] = (list(raw[key]) if key == 'episodeRunTime' else
                    _objects(raw[key], ('id', 'name')) if key == 'createdBy' else [dict(
                        seasonNumber=season['seasonNumber'],
                        **({'airDate': season['airDate']} if 'airDate' in season and
                           (season['airDate'] is None or isinstance(season['airDate'], str)) else {}),
                        _fields={'airDate': _state(season, 'airDate', lambda v: parse_iso_date(v) is not None)})
                        for season in raw[key]])
            elif states[key] == 'null':
                result[key] = None
    result['_fields'] = states
    return result


def tv_eligibility(payload, query, *, detail=False, discovery=None):
    """New-series coverage assessment only; never engagement/acquisition scoring.

    Excluded detail evidence remains in the inventory/history and is not a candidate.
    Unknown classification stays provisional, rather than pretending it is absent.
    """
    kind = payload.get('type')
    if isinstance(kind, str) and kind.casefold().replace('_', ' ').strip() in ('special', 'tv special', 'tv movie'):
        return {'state': 'excluded', 'reason': 'explicit_tv_special'}
    seasons = payload.get('seasons')
    if isinstance(seasons, list) and seasons and all(s.get('seasonNumber') == 0 for s in seasons):
        return {'state': 'excluded', 'reason': 'specials_only'}
    premiere = parse_iso_date(payload.get('firstAirDate'))
    if premiere is None:
        return {'state': 'provisional', 'reason': 'original_premiere_unknown'}
    start, end = (parse_iso_date(query.get(k)) for k in ('firstAirDateGte', 'firstAirDateLte'))
    if start is None or end is None:
        return {'state': 'provisional', 'reason': 'refresh_not_new_series_discovery'}
    summary_premiere = parse_iso_date((discovery or {}).get('firstAirDate'))
    if detail and summary_premiere is not None and summary_premiere != premiere:
        return {'state': 'provisional', 'reason': 'summary_detail_premiere_conflict'}
    if isinstance(seasons, list):
        numbers = [s['seasonNumber'] for s in seasons]
        if len(numbers) != len(set(numbers)):
            return {'state': 'provisional', 'reason': 'season_metadata_conflict'}
        for season in seasons:
            if season['seasonNumber'] == 0:
                continue
            season_date = parse_iso_date(season.get('airDate'))
            if (season_date is not None and (season_date < premiere or
                    season['seasonNumber'] == 1 and season_date != premiere)):
                return {'state': 'provisional', 'reason': 'season_premiere_conflict'}
        dated = sorted((s['seasonNumber'], parse_iso_date(s.get('airDate'))) for s in seasons
                       if s['seasonNumber'] > 0 and parse_iso_date(s.get('airDate')) is not None)
        if any(later[1] < earlier[1] for earlier, later in zip(dated, dated[1:])):
            return {'state': 'provisional', 'reason': 'season_premiere_conflict'}
    if not start <= premiere <= end:
        return {'state': 'excluded', 'reason': 'original_premiere_outside_window'}
    if not detail:
        return {'state': 'provisional', 'reason': 'awaiting_series_detail'}
    if payload.get('_fields', {}).get('seasons') == 'invalid':
        return {'state': 'provisional', 'reason': 'season_metadata_invalid'}
    if not isinstance(seasons, list) or not seasons:
        return {'state': 'provisional', 'reason': 'season_metadata_incomplete'}
    if any(s.get('_fields', {}).get('airDate') == 'invalid' for s in seasons if s['seasonNumber'] > 0):
        return {'state': 'provisional', 'reason': 'season_dates_invalid'}
    first_season = next((s for s in seasons if s['seasonNumber'] == 1), None)
    if first_season is None:
        return {'state': 'provisional', 'reason': 'season_one_missing'}
    if parse_iso_date(first_season.get('airDate')) is None:
        return {'state': 'provisional', 'reason': 'season_one_premiere_unknown'}
    return {'state': 'eligible', 'reason': 'original_series_premiere_in_window'}


class SeerrClient:
    """No disk cache or write methods. Discovery is always fetched; DB metadata caching is separate."""
    def __init__(self, config, *, session=None, sleep=time.sleep, monotonic=time.monotonic):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({'X-Api-Key': config.api_key, 'Accept': 'application/json'})
        self.sleep, self.monotonic, self.last = sleep, monotonic, None
        self.requests = self.retry_count = 0

    def _get(self, path, params):
        if path not in ('/discover/movies', '/discover/tv') and not re.fullmatch(r'/(movie|tv)/[1-9]\d*', path):
            raise SeerrError('endpoint_not_allowlisted', stop=True)
        for attempt in range(self.config.retries + 1):
            if self.requests >= self.config.max_requests:
                raise SeerrError('request_budget_exhausted', stop=True)
            if self.last is not None:
                self.sleep(max(0, self.config.interval - (self.monotonic() - self.last)))
            self.last = self.monotonic()
            self.requests += 1
            try:
                r = self.session.get(self.config.base_url + '/api/v1' + path,
                    params=urlencode(params or {}, quote_via=quote), timeout=self.config.timeout, allow_redirects=False)
            except requests.RequestException:
                if attempt == self.config.retries:
                    raise SeerrError('network_retries_exhausted') from None
                self.retry_count += 1
                self.sleep(min(2 ** attempt, self.config.max_retry_after))
                continue
            status = r.status_code
            if status == 429 or 500 <= status < 600:
                if attempt == self.config.retries:
                    raise SeerrError('rate_limit_exhausted' if status == 429 else 'server_retries_exhausted', stop=status == 429)
                retry = r.headers.get('Retry-After')
                try:
                    wait = float(retry) if retry else 2 ** attempt
                except ValueError:
                    try:
                        wait = parsedate_to_datetime(retry).timestamp() - datetime.now(timezone.utc).timestamp()
                    except (ValueError, TypeError, OverflowError):
                        wait = 2 ** attempt
                if not math.isfinite(wait) or wait > self.config.max_retry_after:
                    raise SeerrError('retry_after_exceeds_budget', stop=True)
                self.retry_count += 1
                self.sleep(max(0, wait))
                continue
            if status != 200:
                raise SeerrError(f'http_{status}', stop=status in (401, 403) or 300 <= status < 400)
            try:
                payload = r.json()
                if not isinstance(payload, dict):
                    raise ValueError
                return payload
            except ValueError:
                raise SeerrError('invalid_json_response') from None

    def discover(self, params):
        return self._get('/discover/movies', params)

    def discover_tv(self, params):
        return self._get('/discover/tv', params)

    def movie(self, tmdb_id):
        if not valid_tmdb_id(tmdb_id):
            raise SeerrError('invalid_movie_identity')
        raw = self._get(f'/movie/{tmdb_id}', {})
        if raw.get('id') != tmdb_id or type(raw.get('id')) is not int:
            raise SeerrError('detail_identity_mismatch')
        return sanitize_movie(raw)

    def tv(self, tmdb_id):
        if not valid_tmdb_id(tmdb_id):
            raise SeerrError('invalid_movie_identity')
        raw = self._get(f'/tv/{tmdb_id}', {})
        if raw.get('id') != tmdb_id or not valid_tmdb_id(raw.get('id')):
            raise SeerrError('detail_identity_mismatch')
        return sanitize_tv(raw)
