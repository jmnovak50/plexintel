"""B3 captured B1/B2 regressions. Only the existing guarded disposable DB fixture.

The copied production provenance is rebound to a fictional fixture origin; the
original captures remain untouched. No HTTP, production DSN or production writes.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json

from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor
import pytest
import requests

from api.db.seerr_discovery import JSON_COLUMNS, DiscoveryRepository
from api.services.seerr_discovery import DiscoveryScope, sync_discovery
from tests.test_seerr_discovery import CFG, ROOT, database, database_v1

ARTIFACTS = ROOT / 'artifacts/seerr-exploration'
CONFIG = replace(CFG, url='https://b3-capture.invalid', source_id='b3-isolated-fixture',
                 media_types=('movie', 'tv'), max_pages=1, metadata_ttl_hours=24)
MOVIE = DiscoveryScope('all', date(2026, 10, 28), date(2026, 10, 28))
TV = DiscoveryScope('all', date(2026, 10, 31), date(2026, 10, 31),
                    'all', 'first_air_date.asc', 'tv')
WHEN = datetime(2026, 10, 29, 3, 10, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def forbid_http(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('B3 capture tests forbid HTTP')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)


@pytest.fixture
def seeded(database):
    b2 = json.loads((ARTIFACTS / '2026-10-28-gate-b2/after.json').read_text())
    copies = deepcopy(b2)
    for run in copies['discovery_runs']:
        run['source_key'] = CONFIG.source_key
        run['parameters'].update(source_key=CONFIG.source_key, source_id=CONFIG.source_id)
    for title in copies['canonical_titles']:
        title['metadata_source_key'] = CONFIG.source_key
    json_columns = JSON_COLUMNS | {'parameters', 'pagination', 'counts', 'errors', 'warnings',
        'query_parameters', 'discovery_metadata', 'detail_metadata', 'eligibility'}
    with database:
        with database.cursor() as cur:
            for table, key in [('seerr_discovery_runs', 'discovery_runs'),
                               ('seerr_discovered_titles', 'canonical_titles'),
                               ('seerr_discovery_observations', 'observations')]:
                for row in copies[key]:
                    keys = list(row)
                    cur.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(
                        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, keys)),
                        sql.SQL(',').join(sql.Placeholder() for _ in keys)),
                        [Json(row[k]) if k in json_columns and row[k] is not None else row[k] for k in keys])
            cur.execute("SELECT setval('public.seerr_discovery_observations_observation_id_seq',20,true)")
    return database, b2


def query(conn, statement, args=()):
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(statement, args)
            return [dict(row) for row in cur.fetchall()]


def titles(conn):
    return query(conn, 'SELECT * FROM public.seerr_discovered_titles ORDER BY media_type,tmdb_id')


class CaptureClient:
    """Synthetic adapter: counters count fixture calls, never actual HTTP attempts."""
    def __init__(self, b2, extra_page=False):
        captures = json.loads((ARTIFACTS / '2026-10-28-gate-b1/candidates.json').read_text())
        self.movie_rows = [deepcopy(o['discovery_metadata']) for o in b2['observations']]
        self.details = {('movie', o['tmdb_id']): deepcopy(o['detail_metadata']) for o in b2['observations']}
        self.tv_rows = []
        self.extra = []
        old = {r['tmdb_id'] for r in b2['canonical_titles']}
        for candidate in captures:
            summary = candidate['discovery'][0]['metadata']
            key = candidate['media_type'], candidate['tmdb_id']
            if key[0] == 'tv' and summary.get('firstAirDate') == '2026-10-31':
                self.tv_rows.append(deepcopy(summary))
                self.details[key] = deepcopy(candidate['detail'])
            if (extra_page and key[0] == 'movie' and key[1] not in old
                    and summary.get('releaseDate') == '2026-10-28' and candidate['detail']):
                self.extra.append(deepcopy(summary))
                self.details[key] = deepcopy(candidate['detail'])
        self.extra = self.extra[:20]
        self.requests = self.retry_count = 0
        self.detail_calls = []

    def discover(self, params):
        self.requests += 1
        return dict(page=params['page'], totalPages=6, totalResults=111,
                    results=self.movie_rows if params['page'] == 1 else self.extra)

    def discover_tv(self, params):
        self.requests += 1
        return dict(page=1, totalPages=1, totalResults=len(self.tv_rows), results=self.tv_rows)

    def _detail(self, kind, ident):
        self.requests += 1
        self.detail_calls.append((kind, ident))
        return deepcopy(self.details[kind, ident])

    def movie(self, ident):
        return self._detail('movie', ident)

    def tv(self, ident):
        return self._detail('tv', ident)


def run(conn, client, scope=MOVIE, when=WHEN, config=CONFIG, **kwargs):
    return sync_discovery(client, config, [scope], repository=DiscoveryRepository(conn),
                          dry_run=False, clock=lambda: when, **kwargs)


def test_captured_b2_repeat_preserves_history_and_unknowns(seeded):
    conn, b2 = seeded
    before = titles(conn)
    old_run = query(conn, 'SELECT * FROM public.seerr_discovery_runs')[0]
    client = CaptureClient(b2)
    result = run(conn, client)
    assert result['status'] == 'partial' and not result['discovery_complete']
    assert result['counts']['new_titles'] == result['counts']['updated_titles'] == 0
    assert result['counts']['existing_titles'] == result['counts']['enrichment_cached'] == 20
    assert client.requests == 1 and client.detail_calls == []
    assert len(query(conn, 'SELECT * FROM public.seerr_discovery_observations')) == 40
    assert query(conn, 'SELECT * FROM public.seerr_discovery_runs WHERE run_id=%s', (old_run['run_id'],)) == [old_run]
    for old, new in zip(before, titles(conn)):
        assert new['last_observed_at'] == WHEN
        for key in ('tmdb_id', 'first_discovery_run_id', 'first_discovered_at', 'last_enriched_at',
                    'last_enrichment_attempt_at', 'metadata_updated_at', 'metadata_fingerprint',
                    'premiere_date', 'runtime', 'media_status', 'media_status_4k', 'media_state'):
            assert new[key] == old[key]
    assert sum(r['premiere_date'] is None for r in titles(conn)) == 8
    assert sum(r['runtime'] is None for r in titles(conn)) == 10
    assert all(r['media_status'] is None and r['media_state']['request_count'] is None for r in titles(conn))


def test_captured_b2_identical_refresh_advances_fetch_age_only(seeded):
    conn, b2 = seeded
    before = titles(conn)
    client = CaptureClient(b2)
    result = run(conn, client, refresh=True)
    assert len(client.detail_calls) == 20 and result['counts']['updated_titles'] == 0
    for old, new in zip(before, titles(conn)):
        assert new['last_enriched_at'] == WHEN
        assert new['metadata_updated_at'] == old['metadata_updated_at']
        assert new['metadata_fingerprint'] == old['metadata_fingerprint']


def test_captured_metadata_delta_is_one_update_with_new_observation(seeded):
    conn, b2 = seeded
    before = titles(conn)
    client = CaptureClient(b2)
    ident = before[0]['tmdb_id']
    client.details['movie', ident]['overview'] = 'Isolated synthetic metadata delta'
    result = run(conn, client, refresh=True)
    assert result['counts']['new_titles'] == 0 and result['counts']['updated_titles'] == 1
    changed = [new for old, new in zip(before, titles(conn)) if new['metadata_fingerprint'] != old['metadata_fingerprint']]
    assert len(changed) == 1 and changed[0]['tmdb_id'] == ident
    assert changed[0]['metadata_updated_at'] == WHEN
    observation = query(conn, 'SELECT * FROM public.seerr_discovery_observations WHERE run_id=%s AND tmdb_id=%s',
                        (result['run_id'], ident))[0]
    assert 'synopsis' in observation['changed_fields'] and not observation['is_new']


def test_captured_oct31_tv_insert_and_repeat_leave_movies_untouched(seeded):
    conn, b2 = seeded
    movies = titles(conn)
    first = run(conn, CaptureClient(b2), TV)
    assert first['status'] == 'success' and first['counts']['new_titles'] == 8
    assert first['counts']['eligible'] == 7 and first['counts']['provisional'] == 1
    tv_before = [r for r in titles(conn) if r['media_type'] == 'tv']
    client = CaptureClient(b2)
    second = run(conn, client, TV, WHEN + timedelta(minutes=1))
    assert second['counts']['new_titles'] == second['counts']['updated_titles'] == 0
    assert second['counts']['enrichment_cached'] == 8 and client.detail_calls == []
    assert [r for r in titles(conn) if r['media_type'] == 'movie'] == movies
    assert len(query(conn, 'SELECT * FROM public.seerr_discovery_observations')) == 36
    conflict = query(conn, "SELECT eligibility FROM public.seerr_discovery_observations WHERE media_type='tv' AND tmdb_id=338525")
    assert len(conflict) == 2 and all(r['eligibility']['state'] == 'provisional' for r in conflict)
    for old, new in zip(tv_before, [r for r in titles(conn) if r['media_type'] == 'tv']):
        assert new['metadata_fingerprint'] == old['metadata_fingerprint']
        assert new['first_discovery_run_id'] == old['first_discovery_run_id']


def test_captured_page_expansion_adds_new_prefix_without_recovering_terminal_b2(seeded):
    conn, b2 = seeded
    old_run = query(conn, 'SELECT * FROM public.seerr_discovery_runs')[0]
    client = CaptureClient(b2, extra_page=True)
    assert len(client.extra) == 20
    result = run(conn, client, config=replace(CONFIG, max_pages=2))
    assert result['status'] == 'partial' and len(result['pagination'][0]['pages']) == 2
    assert result['counts']['titles'] == 40 and result['counts']['new_titles'] == 20
    assert result['counts']['enrichment_cached'] == 20 and len(client.detail_calls) == 20
    assert client.requests == 22 and len(titles(conn)) == 40
    assert len(query(conn, 'SELECT * FROM public.seerr_discovery_observations')) == 60
    assert query(conn, 'SELECT * FROM public.seerr_discovery_runs WHERE run_id=%s', (old_run['run_id'],)) == [old_run]
