"""Production-capable discovery contracts: GET fixtures and isolated PostgreSQL only."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import Mock

import psycopg2
from psycopg2.extensions import parse_dsn
import pytest
import requests

from api.db.seerr_discovery import DiscoveryRepository, inventory_summary, metadata_values
from api.services.seerr_client import SeerrClient, SeerrConfig, SeerrError, load_seerr_config, sanitize_movie
from api.services.seerr_discovery import DiscoveryScope, build_scopes, cache_action, collect_scope, sync_discovery

ROOT = Path(__file__).parents[1]
MIGRATION = ROOT / 'api/db/migrations/optional/seerr_discovery/001_initial.sql'
ROLLBACK = MIGRATION.with_name('rollback.sql')
UPGRADE = MIGRATION.with_name('002_unified_titles.sql')
NOW = datetime(2026, 10, 28, 14, tzinfo=timezone.utc)
CFG = SeerrConfig('https://fixture.invalid', 'fixture-key', enabled=True, source_id='fixture-instance', interval=0, failed_retry_hours=0)
SCOPE = DiscoveryScope('all', date(2026, 10, 26), date(2026, 11, 1))


def movie(ident=1, **changes):
    return dict(id=ident, title=f'Fixture {ident}', originalTitle=f'Original {ident}', mediaType='movie',
        overview='Descriptive synopsis', originalLanguage='en', runtime=90, releaseDate='2026-11-01',
        popularity=1.2, voteCount=0, voteAverage=0, genres=[{'id': 18, 'name': 'Drama'}],
        productionCountries=[{'iso_3166_1': 'US', 'name': 'United States'}],
        productionCompanies=[{'id': 1, 'name': 'Fixture Studio', 'originCountry': 'US'}],
        credits={'cast': [{'id': 1, 'name': 'Fixture Actor', 'order': 0}],
                 'crew': [{'id': 2, 'name': 'Fixture Director', 'job': 'Director'}]},
        releases={'results': [{'iso_3166_1': 'US', 'release_dates': [{'type': 4, 'release_date': '2026-12-01T00:00:00Z'}]}]}) | changes


class FixtureClient:
    def __init__(self, rows=None, details=None, pages=None):
        self.rows = [movie()] if rows is None else rows
        self.details = details or {}
        self.pages = pages
        self.requests = self.retry_count = self.detail_calls = 0

    def discover(self, params):
        self.requests += 1
        if self.pages:
            value = self.pages[params['page']]
            if isinstance(value, Exception):
                raise value
            return value
        return dict(page=1, totalPages=1 if self.rows else 0, totalResults=len(self.rows), results=self.rows)

    def movie(self, ident):
        self.requests += 1
        self.detail_calls += 1
        value = self.details.get(ident, next((r for r in self.rows if r['id'] == ident), movie(ident)))
        if isinstance(value, Exception):
            raise value
        return sanitize_movie(value)


@pytest.fixture
def database_v1():
    dsn = os.getenv('SEERR_DISCOVERY_TEST_DSN')
    if not dsn:
        pytest.skip('SEERR_DISCOVERY_TEST_DSN required for disposable-cluster integration tests')
    parsed = parse_dsn(dsn)
    root = Path(parsed.get('host', ''))
    if parsed.get('dbname') != 'plexintel_seerr_fixture' or not str(root).startswith('/tmp/plexintel-seerr-fixture.'):
        pytest.fail('Refusing a database outside the dedicated disposable Unix-socket fixture')
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_setting('data_directory'),current_setting('listen_addresses')")
                directory, listen = cur.fetchone()
                assert Path(directory) == root / 'data' and listen == '', 'Fixture must be TCP-disabled and isolated'
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovery_observations')
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovered_titles')
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovered_movies')
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovery_runs')
                cur.execute(MIGRATION.read_text())
                # Applying the opt-in migration twice must preserve schema/data compatibility.
                cur.execute(MIGRATION.read_text())
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def database(database_v1):
    with database_v1:
        with database_v1.cursor() as cur:
            cur.execute(UPGRADE.read_text())
    yield database_v1


def sync(database, client=None, *, scopes=None, config=CFG, when=NOW, **kwargs):
    return sync_discovery(client or FixtureClient(), config, scopes or [SCOPE],
        repository=DiscoveryRepository(database), dry_run=False, clock=lambda: when, **kwargs)


def scalar(conn, query, params=()):
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()[0]


def test_default_disabled_and_scopes_are_instance_configurable():
    cfg = replace(CFG, enabled=False, languages=('configured', 'all'), lookback_days=3, lookahead_days=4, window_days=3)
    scopes = build_scopes(cfg, anchor=date(2026, 10, 28))
    assert scopes[0].start == date(2026, 10, 25) and scopes[-1].end == date(2026, 11, 1)
    assert 'language' not in scopes[0].parameters and scopes[1].parameters['language'] == 'all'
    assert len({s.key for s in scopes}) == len(scopes) == 6
    repo = Mock()
    with pytest.raises(SeerrError, match='discovery_disabled'):
        sync_discovery(FixtureClient(), cfg, scopes, repository=repo, dry_run=False)
    repo.acquire.assert_not_called()


def test_private_configuration_and_secret_file_are_owner_only(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(('SEERR_', 'SEER_')):
            monkeypatch.delenv(key)
    key = tmp_path / 'key'
    key.write_text('secret-fixture-token')
    key.chmod(0o600)
    config = tmp_path / 'config.env'
    config.write_text(f'SEERR_URL=https://fixture.invalid\nSEERR_API_KEY_FILE={key}\nSEERR_DISCOVERY_LANGUAGES=en,all\nSEERR_DISCOVERY_SOURCE_ID=private-fixture\n')
    config.chmod(0o600)
    cfg = load_seerr_config(config)
    assert cfg.enabled is False and cfg.languages == ('en', 'all') and cfg.source_id == 'private-fixture'
    assert 'secret-fixture-token' not in repr(cfg) and 'https://' not in repr(cfg)
    config.chmod(0o644)
    from api.services.private_config import PrivateConfigError
    with pytest.raises(PrivateConfigError):
        load_seerr_config(config)


@pytest.mark.parametrize('changes', [dict(url='https://user:secret@host'), dict(retries=9), dict(interval=float('nan')),
    dict(languages=('server|en',)), dict(timeout=0), dict(max_pages=0)])
def test_configuration_rejects_invalid_values(changes):
    with pytest.raises(SeerrError):
        replace(CFG, **changes)


def test_dry_run_does_not_use_repository_even_when_passed():
    repo = Mock()
    result = sync_discovery(FixtureClient(), replace(CFG, enabled=False), [SCOPE],
                           repository=repo, dry_run=True, clock=lambda: NOW)
    assert result['status'] == 'success' and result['counts']['new_movies'] is None
    assert repo.mock_calls == []


def test_transport_get_only_percent_encoding_bounded_timeout_retries():
    session = Mock()
    session.headers = {}
    r = Mock(status_code=200)
    r.json.return_value = movie()
    session.get.side_effect = [requests.Timeout('private-url-secret'), r]
    sleeps = []
    client = SeerrClient(CFG, session=session, sleep=sleeps.append)
    assert client.movie(1)['id'] == 1 and client.retry_count == 1
    assert session.get.call_args.kwargs['timeout'] == CFG.timeout
    assert session.get.call_args.kwargs['allow_redirects'] is False
    assert session.post.call_count == session.put.call_count == session.delete.call_count == 0
    with pytest.raises(SeerrError, match='endpoint_not_allowlisted'):
        client._get('/request', {})


def test_auth_redirect_rate_limit_and_identity_failures_are_safe():
    for status, header in [(302, {}), (401, {}), (429, {'Retry-After': '600'})]:
        session = Mock(headers={})
        session.get.return_value = Mock(status_code=status, headers=header)
        client = SeerrClient(CFG, session=session, sleep=lambda _: None)
        with pytest.raises(SeerrError) as err:
            client.movie(1)
        assert err.value.stop and session.get.call_count == 1
    session = Mock(headers={})
    session.get.return_value = Mock(status_code=200)
    session.get.return_value.json.return_value = movie(2)
    with pytest.raises(SeerrError, match='detail_identity_mismatch'):
        SeerrClient(CFG, session=session).movie(1)


def test_status_presence_and_private_source_data():
    reference = sanitize_movie(movie(1300968, mediaInfo={'status': 3, 'status4k': 1, 'externalServiceId': 999,
        'serviceUrl': 'private-secret', 'requests': [{'id': 42, 'status': 2, 'is4k': False, 'requestedBy': {'email': 'private-secret'}}]}))
    values = metadata_values(reference)
    assert values['media_status'] == 3 and values['media_state']['request_states'] == [{'status': 2, 'is4k': False}]
    assert values['media_state']['externalServiceLinked'] is True
    assert 'private-secret' not in json.dumps(reference) and 'externalServiceId' not in json.dumps(reference)
    missing = metadata_values(sanitize_movie(movie()))
    null = metadata_values(sanitize_movie(movie(mediaInfo=None)))
    unknown_record = metadata_values(sanitize_movie(movie(mediaInfo={'status': 1, 'requests': []})))
    assert missing['media_state']['media_info'] == 'omitted' and null['media_state']['media_info'] == 'null'
    assert unknown_record['media_status'] == 1 and unknown_record['media_state']['request_count'] == 0


def test_pagination_deduplication_and_invalid_records_cannot_claim_complete():
    client = FixtureClient(pages={1: dict(page=1, totalPages=2, totalResults=3, results=[movie(1), movie(2)]),
        2: dict(page=2, totalPages=2, totalResults=3, results=[movie(2), {'id': True}])})
    accepted = []
    metrics, _ = collect_scope(client, SCOPE, 500, accepted.extend)
    assert [r['id'] for r in accepted] == [1, 2]
    assert metrics['duplicate_rows'] == metrics['invalid_rows'] == 1 and not metrics['complete']


def test_startup_migration_glob_cannot_activate_discovery():
    root = ROOT / 'api/db/migrations'
    assert MIGRATION not in list(root.glob('*.sql')) and ROLLBACK not in list(root.glob('*.sql'))
    assert 'seerr_discovery' not in (ROOT / 'run_daily_pipeline.sh').read_text()


def cli_module():
    spec = importlib.util.spec_from_file_location('seerr_sync_cli', ROOT / 'scripts/sync_seerr_discovery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_dry_run_and_disabled_execute_never_connect(monkeypatch, capsys):
    module = cli_module()
    monkeypatch.setattr(module, 'load_dotenv', lambda *a, **k: None)
    monkeypatch.setattr(module, 'load_seerr_config', lambda *a, **k: replace(CFG, enabled=False))
    monkeypatch.setattr(module, 'SeerrClient', lambda _: FixtureClient())
    connect = Mock(side_effect=AssertionError('Database access forbidden for preview/disabled execution'))
    monkeypatch.setattr(module, 'connect_db', connect)
    assert module.main(['--dry-run', '--start', '2026-10-26', '--end', '2026-11-01', '--json']) == 0
    assert module.main(['--execute']) == 1
    connect.assert_not_called()
    assert CFG.api_key not in capsys.readouterr().out


def test_cli_summary_uses_readonly_connection_and_no_seerr_client(database, monkeypatch, capsys):
    sync(database)
    module = cli_module()
    monkeypatch.setattr(module, 'load_dotenv', lambda *a, **k: None)
    monkeypatch.setattr(module, 'load_seerr_config', lambda *a, **k: replace(CFG, enabled=False))
    connection = psycopg2.connect(os.environ['SEERR_DISCOVERY_TEST_DSN'])
    wrapped = Mock(wraps=connection)
    monkeypatch.setattr(module, 'connect_db', lambda: wrapped)
    monkeypatch.setattr(module, 'SeerrClient', Mock(side_effect=AssertionError('Summary cannot call Seerr')))
    assert module.main(['--summary', '--json']) == 0
    assert wrapped.set_session.call_args.kwargs['readonly'] is True
    assert wrapped.rollback.call_count == wrapped.close.call_count == 1
    assert json.loads(capsys.readouterr().out)['total_movies'] == 1


def test_budget_exhaustion_is_deferred_without_marking_a_get_attempt(database):
    result = sync(database, FixtureClient(details={1: SeerrError('request_budget_exhausted', stop=True)}))
    row = DiscoveryRepository(database).get(1)
    assert result['status'] == 'partial' and result['counts']['enrichment_deferred'] == 1
    assert row['last_enrichment_attempt_at'] is None and row['enrichment_status'] == 'pending'


def test_fatal_discovery_authentication_does_not_attempt_enrichment(database):
    client = FixtureClient(pages={1: dict(page=1, totalPages=2, totalResults=2, results=[movie()]),
                                  2: SeerrError('http_403', stop=True)})
    result = sync(database, client)
    assert result['status'] == 'partial' and client.detail_calls == 0
    assert result['counts']['enrichment_deferred'] == 1


def test_expired_cache_is_refreshed_and_missing_title_remains_discovered(database):
    first = movie()
    del first['title']
    initial = sync(database, FixtureClient(rows=[first]))
    assert initial['status'] == 'success' and DiscoveryRepository(database).get(1)['title'] is None
    result = sync(database, FixtureClient(details={1: movie(popularity=2.1)}), when=NOW+timedelta(hours=25))
    assert result['counts']['enrichment_success'] == 1 and result['counts']['updated_movies'] == 1


def test_exclusive_session_lock_refuses_a_second_connection(database):
    repo = DiscoveryRepository(database)
    assert repo.acquire()
    other = psycopg2.connect(os.environ['SEERR_DISCOVERY_TEST_DSN'])
    try:
        with pytest.raises(SeerrError, match='discovery_already_running'):
            sync(other)
    finally:
        other.close()
        repo.release()


def test_initial_ingestion_and_structured_metadata(database):
    result = sync(database)
    assert result['status'] == 'success' and result['counts']['new_movies'] == 1
    row = DiscoveryRepository(database).get(1)
    assert row['runtime'] == 90 and row['directors'] == ['Fixture Director']
    assert row['production_companies'][0]['name'] == 'Fixture Studio'
    assert row['release_events'][0]['type'] == 4 and row['premiere_date'] == date(2026, 11, 1)
    assert row['first_discovered_at'] == row['last_enriched_at'] == NOW
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovery_observations') == 1


def test_discovery_does_not_apply_content_or_release_readiness_filters(database):
    result = sync(database, FixtureClient(rows=[movie(1, runtime=3, adult=True, genres=[], popularity=0,
        voteCount=0, originalLanguage='ja', releaseDate='2031-01-01'), movie(2, overview=None, runtime=None)]))
    assert result['status'] == 'success' and result['counts']['new_movies'] == 2
    assert DiscoveryRepository(database).get(1)['premiere_date'] == date(2031, 1, 1)
    assert DiscoveryRepository(database).get(2)['synopsis'] is None


def test_repeated_ingestion_uses_cache_preserves_first_seen_and_counts_existing(database):
    first = sync(database)
    client = FixtureClient()
    result = sync(database, client, when=NOW + timedelta(hours=1))
    assert result['counts']['existing_movies'] == 1 and result['counts']['new_movies'] == result['counts']['updated_movies'] == 0
    assert result['counts']['enrichment_cached'] == 1 and client.detail_calls == 0
    row = DiscoveryRepository(database).get(1)
    assert row['first_discovered_at'] == NOW and row['last_observed_at'] == NOW + timedelta(hours=1)
    assert row['last_enriched_at'] == NOW
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovery_observations') == 2
    assert first['run_id'] != result['run_id']


def test_new_title_change_detection_explicit_refresh_and_no_change_refresh(database):
    sync(database)
    result = sync(database, FixtureClient(rows=[movie(), movie(2)], details={1: movie(1, overview='Changed synopsis')}), refresh=True, when=NOW+timedelta(days=1))
    assert result['counts']['new_movies'] == 1 and result['counts']['updated_movies'] == 1
    assert DiscoveryRepository(database).get(1)['synopsis'] == 'Changed synopsis'
    same = sync(database, FixtureClient(details={1: movie(1, overview='Changed synopsis')}), refresh=True, when=NOW+timedelta(days=2))
    assert same['counts']['updated_movies'] == 0


def test_source_only_metadata_change_is_counted(database):
    sync(database)
    result = sync(database, FixtureClient(details={1: movie(posterPath='/changed-public-art')}), refresh=True)
    assert result['counts']['updated_movies'] == 1
    assert 'source_metadata' in scalar(database, 'SELECT changed_fields FROM public.seerr_discovery_observations WHERE run_id=%s', (result['run_id'],))


def test_missing_metadata_is_persisted_and_explicit_null_vs_omission(database):
    sync(database)
    detail = movie(runtime=0, overview=None, mediaInfo=None)
    del detail['title']
    result = sync(database, FixtureClient(details={1: detail}), refresh=True)
    row = DiscoveryRepository(database).get(1)
    assert row['title'] == 'Fixture 1' and row['synopsis'] is None and row['runtime'] is None
    assert row['field_states']['title'] == 'omitted' and row['field_states']['synopsis'] == 'null'
    assert row['field_states']['runtime'] == 'zero_unknown' and row['media_state']['media_info'] == 'null'
    assert result['status'] == 'success'  # Metadata sparsity is not collection failure or a filter.


def test_enrichment_failure_does_not_lose_membership_or_last_good_data(database):
    first = sync(database, FixtureClient(rows=[movie(), movie(2)], details={2: SeerrError('network_retries_exhausted')}))
    assert first['status'] == 'partial' and first['counts']['new_movies'] == 2 and first['counts']['enrichment_failed'] == 1
    old = DiscoveryRepository(database).get(1)
    second = sync(database, FixtureClient(details={1: SeerrError('server_retries_exhausted')}), refresh=True, when=NOW+timedelta(days=1))
    row = DiscoveryRepository(database).get(1)
    assert row['synopsis'] == old['synopsis'] and row['last_enriched_at'] == old['last_enriched_at']
    assert row['enrichment_status'] == 'failed' and second['status'] == 'partial'
    third = sync(database, FixtureClient(), when=NOW+timedelta(days=2))
    assert third['status'] == 'success'


def test_discovery_only_genre_ids_remain_queryable_when_details_fail(database):
    summary = movie(genreIds=[18, 27])
    del summary['genres']
    result = sync(database, FixtureClient(rows=[summary], details={1: SeerrError('http_404')}))
    row = DiscoveryRepository(database).get(1)
    assert result['status'] == 'partial' and row['genres'] == [{'id': 18}, {'id': 27}]
    assert row['field_states']['genres'] == 'ids_only'


def test_overlapping_windows_multiple_scopes_one_canonical_and_scope_memberships(database):
    scopes = [SCOPE, DiscoveryScope('configured', SCOPE.start, SCOPE.end, 'configured'),
              DiscoveryScope('overlap', date(2026, 10, 28), date(2026, 11, 3))]
    client = FixtureClient()
    result = sync(database, client, scopes=scopes)
    assert result['counts']['movies'] == result['counts']['new_movies'] == 1 and client.detail_calls == 1
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovered_titles') == 1
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovery_observations') == 3
    repo = DiscoveryRepository(database)
    repo.discover_page(result['run_id'], SCOPE.key, SCOPE.name, SCOPE.parameters, [sanitize_movie(movie())], NOW)
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovery_observations') == 3


def test_inconsistent_or_failed_pages_are_partial_and_never_delete_old_movies(database):
    sync(database, FixtureClient(rows=[movie(99)]))
    client = FixtureClient(pages={1: dict(page=1, totalPages=3, totalResults=3, results=[movie(1)]),
        2: SeerrError('server_retries_exhausted'), 3: dict(page=3, totalPages=3, totalResults=4, results=[movie(3)])})
    result = sync(database, client)
    assert result['status'] == 'partial' and not result['discovery_complete']
    assert DiscoveryRepository(database).get(99) is not None
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovered_titles') == 3
    assert scalar(database, 'SELECT status FROM public.seerr_discovery_runs WHERE run_id=%s', (result['run_id'],)) == 'partial'


def test_empty_discovery_is_successful_without_removing_previous_inventory(database):
    sync(database)
    result = sync(database, FixtureClient(rows=[]))
    assert result['status'] == 'success' and result['counts']['movies'] == 0
    assert DiscoveryRepository(database).get(1)


def test_page_transaction_failure_rolls_back_and_recovers(database, monkeypatch):
    repo = DiscoveryRepository(database)
    original = repo._save
    def fail(cur, record):
        if record['tmdb_id'] == 2:
            raise psycopg2.IntegrityError('fixture failure; must not be emitted')
        original(cur, record)
    monkeypatch.setattr(repo, '_save', fail)
    result = sync_discovery(FixtureClient(rows=[movie(), movie(2)]), CFG, [SCOPE], repository=repo, dry_run=False, clock=lambda: NOW)
    assert result['status'] == 'failed' and scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovered_titles') == 0
    assert result['errors'] == [{'code': 'database_or_internal_failure'}]
    assert sync(database)['status'] == 'success'


def test_interrupted_run_is_recovered_without_erasing_observations(database):
    from uuid import uuid4
    repo = DiscoveryRepository(database)
    ident = str(uuid4())
    assert repo.acquire()
    repo.start(ident, NOW, 'discover', CFG.source_key, {'source_id': CFG.source_id})
    repo.discover_page(ident, SCOPE.key, SCOPE.name, SCOPE.parameters, [sanitize_movie(movie())], NOW)
    repo.release()
    result = sync(database, when=NOW+timedelta(hours=1))
    assert result['status'] == 'success'
    assert scalar(database, 'SELECT status FROM public.seerr_discovery_runs WHERE run_id=%s', (ident,)) == 'partial'
    assert scalar(database, "SELECT (counts->>'movies')::int FROM public.seerr_discovery_runs WHERE run_id=%s", (ident,)) == 1
    assert scalar(database, "SELECT (counts->>'enrichment_pending')::int FROM public.seerr_discovery_runs WHERE run_id=%s", (ident,)) == 1
    assert scalar(database, 'SELECT COUNT(*) FROM public.seerr_discovery_observations WHERE run_id=%s', (ident,)) == 1


def test_inventory_refresh_works_outside_discovery_window_without_touching_last_seen(database):
    sync(database)
    result = sync(database, FixtureClient(details={1: movie(overview='Months later metadata')}), enrich_due=True,
                  when=NOW+timedelta(days=100))
    row = DiscoveryRepository(database).get(1)
    assert result['status'] == 'success' and row['synopsis'] == 'Months later metadata'
    assert row['last_observed_at'] == NOW and row['first_discovered_at'] == NOW
    assert scalar(database, 'SELECT observation_kind FROM public.seerr_discovery_observations WHERE run_id=%s', (result['run_id'],)) == 'refresh'


def test_refresh_cooldown_and_readonly_summary(database):
    config = replace(CFG, failed_retry_hours=2)
    sync(database, FixtureClient(details={1: SeerrError('http_404')}), config=config)
    result = sync(database, when=NOW+timedelta(hours=1), config=config)
    assert result['counts']['enrichment_deferred'] == 1 and result['status'] == 'partial'
    assert DiscoveryRepository(database).due(config, NOW+timedelta(hours=1)) == []
    database.set_session(readonly=True)
    summary = inventory_summary(database, config, NOW+timedelta(hours=1))
    assert summary['total_movies'] == 1 and summary['refresh_due'] == 0
    database.rollback()


def test_migration_rollback_removes_only_discovery_tables(database_v1):
    database = database_v1
    with database:
        with database.cursor() as cur:
            cur.execute('CREATE TABLE fixture_existing_inventory(id integer PRIMARY KEY)')
            cur.execute('INSERT INTO fixture_existing_inventory VALUES (42)')
    with database:
        with database.cursor() as cur:
            cur.execute(ROLLBACK.read_text())
    assert scalar(database, 'SELECT COUNT(*) FROM fixture_existing_inventory') == 1
    with database:
        with database.cursor() as cur:
            cur.execute('DROP TABLE fixture_existing_inventory')


def inventory_snapshot(conn):
    return {table: scalar(conn, f'SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM public.{table} t')
            for table in ('seerr_discovery_runs', 'seerr_discovered_titles', 'seerr_discovery_observations')}


def test_missing_source_identity_rejected_before_database_or_network(monkeypatch):
    config = replace(CFG, source_id=None)
    client, repo = FixtureClient(), Mock()
    with pytest.raises(SeerrError, match='discovery_source_id_required'):
        sync_discovery(client, config, [SCOPE], repository=repo, dry_run=False)
    assert repo.mock_calls == [] and client.requests == 0
    module = cli_module()
    monkeypatch.setattr(module, 'load_dotenv', lambda *a, **k: None)
    monkeypatch.setattr(module, 'load_seerr_config', lambda *a, **k: config)
    connect = Mock(side_effect=AssertionError('Missing identity cannot connect'))
    monkeypatch.setattr(module, 'connect_db', connect)
    assert module.main(['--execute']) == 1
    connect.assert_not_called()


@pytest.mark.parametrize('source_id', ['', ' spaced ', '../instance', 42])
def test_invalid_source_identity(source_id):
    with pytest.raises(SeerrError, match='invalid_discovery_source_id'):
        replace(CFG, source_id=source_id)


def test_same_instance_refresh_preserves_source_binding(database):
    first = sync(database)
    config = replace(CFG, url=CFG.url + '/api/v1/', api_key='rotated-fixture-token')
    assert config.source_key == CFG.source_key
    client = FixtureClient()
    second = sync(database, client, config=config, refresh=True, when=NOW+timedelta(days=1))
    assert second['status'] == 'success' and second['counts']['updated_movies'] == 0 and client.detail_calls == 1
    row = DiscoveryRepository(database).get(1)
    assert str(row['first_discovery_run_id']) == first['run_id'] and row['metadata_source_key'] == CFG.source_key
    assert scalar(database, 'SELECT count(DISTINCT source_key) FROM public.seerr_discovery_runs') == 1
    assert scalar(database, "SELECT count(DISTINCT parameters->>'source_id') FROM public.seerr_discovery_runs") == 1


@pytest.mark.parametrize('changes', [dict(url='https://other-fixture.invalid'), dict(source_id='other-instance'),
    dict(url='https://other-fixture.invalid', source_id='other-instance')])
@pytest.mark.parametrize('enrich_due', [False, True])
@pytest.mark.parametrize('seed_failure', [False, True])
def test_changed_instance_cannot_mutate_or_mix_inventory(database, changes, enrich_due, seed_failure):
    sync(database, FixtureClient(details={1: SeerrError('http_404')}) if seed_failure else None)
    before = inventory_snapshot(database)
    client = FixtureClient(rows=[movie(1, overview='Different source'), movie(2)])
    result = sync(database, client, config=replace(CFG, **changes), refresh=True, enrich_due=enrich_due)
    assert result['status'] == 'failed' and result['errors'] == [{'code': 'discovery_source_identity_mismatch'}]
    assert client.requests == 0 and inventory_snapshot(database) == before
    assert DiscoveryRepository(database).get(2) is None


@pytest.mark.parametrize('corruption,code', [
    ("UPDATE public.seerr_discovery_runs SET parameters=parameters-'source_id'", 'discovery_source_identity_ambiguous'),
    ("UPDATE public.seerr_discovery_runs SET parameters=jsonb_set(parameters,'{source_id}','null')", 'discovery_source_identity_ambiguous'),
    ("UPDATE public.seerr_discovered_titles SET metadata_source_key=NULL", 'discovery_source_identity_ambiguous'),
    ("UPDATE public.seerr_discovered_titles SET metadata_source_key='other-origin'", 'discovery_source_identity_mismatch'),
    ("UPDATE public.seerr_discovery_runs SET source_key='other-origin'", 'discovery_source_identity_mismatch')])
def test_legacy_or_contaminated_inventory_fails_closed(database, corruption, code):
    sync(database)
    with database:
        with database.cursor() as cur:
            cur.execute(corruption)
    before, client = inventory_snapshot(database), FixtureClient()
    result = sync(database, client)
    assert result['errors'] == [{'code': code}] and client.requests == 0
    assert inventory_snapshot(database) == before


def test_source_guard_precedes_interrupted_run_recovery(database):
    from uuid import uuid4
    repo = DiscoveryRepository(database)
    assert repo.acquire()
    repo.start(str(uuid4()), NOW, 'discover', CFG.source_key, {'source_id': CFG.source_id})
    repo.release()
    before = inventory_snapshot(database)
    result = sync(database, config=replace(CFG, source_id='other-instance'))
    assert result['status'] == 'failed' and inventory_snapshot(database) == before
    assert sync(database)['status'] == 'success'


def test_mixed_run_sources_are_rejected_even_when_latest_matches(database):
    first = sync(database)
    sync(database)
    with database:
        with database.cursor() as cur:
            cur.execute('UPDATE public.seerr_discovery_runs SET source_key=%s WHERE run_id=%s', ('other-origin', first['run_id']))
    before, client = inventory_snapshot(database), FixtureClient()
    result = sync(database, client)
    assert result['errors'] == [{'code': 'discovery_source_identity_mismatch'}]
    assert client.requests == 0 and inventory_snapshot(database) == before


RELEASE_CASES = [
    ({}, 'omitted', False),
    ({'releases': None}, 'null', False),
    ({'releases': {}}, 'results_omitted', False),
    ({'releases': {'results': None}}, 'results_null', False),
    ({'releases': {'results': 'invalid'}}, 'results_invalid', False),
    ({'releases': {'results': [{'iso_3166_1': 'US'}]}}, 'release_dates_omitted', False),
    ({'releases': {'results': [{'iso_3166_1': 'US', 'release_dates': None}]}}, 'release_dates_null', False),
    ({'releases': {'results': [{'release_dates': 'invalid'}]}}, 'release_dates_invalid', False),
    ({'releases': {'results': [None]}}, 'release_dates_invalid', False),
    ({'releases': {'results': [{'release_dates': [None]}]}}, 'release_dates_invalid', False),
    ({'releases': {'results': [{'release_dates': []}, {'release_dates': None}]}}, 'release_dates_null', False),
    ({'releases': {'results': [{'release_dates': [{'type': 4, 'release_date': '2027-01-01'}]},
                               {'release_dates': None}]}}, 'release_dates_null', False),
    ({'releases': {'results': []}}, 'empty', True),
    ({'releases': {'results': [{'iso_3166_1': 'US', 'release_dates': []}]}}, 'empty', True),
]


@pytest.mark.parametrize('incoming,state,authoritative_empty', RELEASE_CASES)
def test_nested_release_semantics_and_repeated_persistence(database, incoming, state, authoritative_empty):
    sync(database)
    repo = DiscoveryRepository(database)
    known = repo.get(1)['release_events']
    detail = movie()
    del detail['releases']
    detail.update(incoming)
    sanitized = sanitize_movie(detail)
    assert metadata_values(sanitized)['release_events'] == ([] if authoritative_empty else None)
    assert metadata_values(sanitized)['field_states']['release_events'] == state
    result = sync(database, FixtureClient(details={1: detail}), refresh=True, when=NOW+timedelta(days=1))
    assert result['status'] == 'success'
    row = repo.get(1)
    assert row['release_events'] == ([] if authoritative_empty else known)
    assert row['field_states']['release_events'] == state
    repeat = sync(database, FixtureClient(details={1: detail}), refresh=True, when=NOW+timedelta(days=2))
    again = repo.get(1)
    assert repeat['counts']['updated_movies'] == 0
    for key in ('release_events', 'field_states', 'metadata_fingerprint', 'metadata_updated_at'):
        assert again[key] == row[key]


def test_unknown_and_known_empty_release_inventory_are_distinct(database):
    unknown = movie(1)
    del unknown['releases']
    sync(database, FixtureClient(rows=[unknown, movie(2, releases={'results': []})]))
    repo = DiscoveryRepository(database)
    assert repo.get(1)['release_events'] is None and repo.get(2)['release_events'] == []
    # A subsequent unknown collection must also preserve a known-empty result.
    sync(database, FixtureClient(details={2: movie(2, releases=None)}, rows=[movie(2)]), refresh=True)
    assert repo.get(2)['release_events'] == [] and repo.get(2)['field_states']['release_events'] == 'null'


def test_populated_release_updates_replace_without_duplicates(database):
    sync(database)
    detail = movie(releases={'results': [
        {'iso_3166_1': 'GB', 'release_dates': [{'type': 3, 'release_date': '2027-02-01'}]},
        {'iso_3166_1': 'US', 'release_dates': [{'type': 4, 'release_date': '2027-03-01'}]}]})
    first = sync(database, FixtureClient(details={1: detail}), refresh=True, when=NOW+timedelta(days=1))
    row = DiscoveryRepository(database).get(1)
    assert first['counts']['updated_movies'] == 1
    assert row['release_events'] == [dict(country='GB', type=3, release_date='2027-02-01'),
                                    dict(country='US', type=4, release_date='2027-03-01')]
    second = sync(database, FixtureClient(details={1: detail}), refresh=True, when=NOW+timedelta(days=2))
    assert second['counts']['updated_movies'] == 0 and DiscoveryRepository(database).get(1)['release_events'] == row['release_events']


def test_refresh_batch_rotates_permanently_failing_titles(database):
    failures = {ident: SeerrError('http_404') for ident in (1, 2, 3)}
    sync(database, FixtureClient(rows=[movie(i) for i in failures], details=failures))
    config = replace(CFG, refresh_batch_size=2, failed_retry_hours=1)
    repo = DiscoveryRepository(database)
    assert [r['tmdb_id'] for r in repo.due(config, NOW+timedelta(days=1))] == [1, 2]
    sync(database, FixtureClient(details=failures), config=config, enrich_due=True, when=NOW+timedelta(days=1))
    assert [r['tmdb_id'] for r in repo.due(config, NOW+timedelta(days=2))] == [3, 1]
    result = sync(database, FixtureClient(details=failures), config=config, enrich_due=True, when=NOW+timedelta(days=2))
    assert result['counts']['movies'] == 2 and repo.get(3)['last_enrichment_attempt_at'] == NOW+timedelta(days=2)


def test_unattempted_titles_precede_retry_backlog(database):
    sync(database, FixtureClient(rows=[movie(1), movie(2), movie(3)], details={1: SeerrError('http_401', stop=True)}))
    config = replace(CFG, refresh_batch_size=2)
    assert [r['tmdb_id'] for r in DiscoveryRepository(database).due(config, NOW+timedelta(days=1))] == [2, 3]
