"""Readiness defects: real catalog validation and synthetic TV metadata only."""
from dataclasses import replace
from datetime import date, timedelta
import json
from uuid import uuid4

import pytest
import requests

from api.db.seerr_discovery import DiscoveryRepository, require_unified_schema, inventory_summary
from api.services.seerr_client import SeerrError, sanitize_tv, tv_eligibility
from api.services.seerr_discovery import DiscoveryScope, collect_scope
from tests.test_seerr_discovery import database, database_v1, CFG, NOW, SCOPE, UPGRADE, scalar, sync, inventory_snapshot
from tests.test_seerr_unified_discovery import TV, DUAL, tv, summary, UnifiedClient, both

TV_CONFIG = replace(CFG, media_types=('tv',))


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('Live HTTP forbidden in remediation tests')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)


@pytest.mark.parametrize('drift', [
    'ALTER TABLE public.seerr_discovery_observations DROP CONSTRAINT seerr_observations_title_fkey',
    'ALTER TABLE public.seerr_discovery_observations DROP CONSTRAINT seerr_observations_run_title_scope_key',
    'ALTER TABLE public.seerr_discovered_titles DROP CONSTRAINT seerr_discovered_titles_pkey CASCADE; ALTER TABLE public.seerr_discovered_titles ADD PRIMARY KEY(tmdb_id)',
    'ALTER TABLE public.seerr_discovered_titles ALTER COLUMN premiere_date TYPE text USING premiere_date::text',
    'ALTER TABLE public.seerr_discovery_observations DROP COLUMN eligibility',
    'ALTER TABLE public.seerr_discovery_runs ALTER COLUMN parameters TYPE json USING parameters::json',
    'ALTER TABLE public.seerr_discovery_runs ALTER COLUMN counts DROP DEFAULT',
    'ALTER TABLE public.seerr_discovered_titles DROP CONSTRAINT seerr_titles_media_type_check',
    "ALTER TABLE public.seerr_discovered_titles DROP CONSTRAINT seerr_titles_media_type_check; ALTER TABLE public.seerr_discovered_titles ADD CHECK(media_type IN ('movie','tv','season'))",
    'ALTER TABLE public.seerr_discovered_titles DROP CONSTRAINT seerr_titles_tv_release_events_check; ALTER TABLE public.seerr_discovered_titles ADD CHECK(media_type=\'movie\' OR release_events IS NULL) NOT VALID',
    'ALTER TABLE public.seerr_discovery_observations ALTER COLUMN observation_id DROP IDENTITY',
    'ALTER SEQUENCE public.seerr_discovery_observations_observation_id_seq INCREMENT BY 2',
    'ALTER TABLE public.seerr_discovered_titles ENABLE ROW LEVEL SECURITY',
    'CREATE UNIQUE INDEX fixture_wrong_identity ON public.seerr_discovered_titles(tmdb_id)',
    'ALTER TABLE public.seerr_discovery_observations DISABLE TRIGGER ALL',
])
def test_incompatible_integrity_rejects_before_http_run_insertion_or_recovery(database, drift):
    # A running record would be modified by recovery if validation happened too late.
    run = str(uuid4()); repo = DiscoveryRepository(database)
    repo.start(run, NOW, 'discover', CFG.source_key, {'source_id': CFG.source_id})
    with database:
        with database.cursor() as cur:
            cur.execute(drift)
    before = inventory_snapshot(database); client = UnifiedClient()
    result = both(database, client)
    assert result['errors'] == [{'code': 'seerr_unified_schema_incompatible'}]
    assert client.requests == 0 and inventory_snapshot(database) == before
    assert scalar(database, 'SELECT status FROM public.seerr_discovery_runs WHERE run_id=%s', (run,)) == 'running'
    with pytest.raises(SeerrError, match='seerr_unified_schema_incompatible'):
        inventory_summary(database, DUAL, NOW)
    database.rollback()


@pytest.mark.parametrize('missing', ['seerr_discovery_runs', 'seerr_discovery_observations', 'seerr_discovered_titles'])
def test_missing_required_table_is_safe(database, missing):
    with database:
        with database.cursor() as cur:
            cur.execute('DROP TABLE public.' + missing + ' CASCADE')
    client = UnifiedClient(); result = both(database, client)
    assert result['errors'][0]['code'] in ('seerr_unified_schema_required', 'seerr_unified_schema_incompatible')
    assert client.requests == 0


def test_view_cannot_impersonate_canonical_table(database):
    with database:
        with database.cursor() as cur:
            cur.execute('ALTER TABLE public.seerr_discovered_titles RENAME TO fixture_real_titles')
            cur.execute('CREATE VIEW public.seerr_discovered_titles AS SELECT * FROM public.fixture_real_titles')
    try:
        client = UnifiedClient(); result = both(database, client)
        assert result['errors'] == [{'code': 'seerr_unified_schema_incompatible'}] and client.requests == 0
    finally:
        with database:
            with database.cursor() as cur:
                cur.execute('DROP VIEW public.seerr_discovered_titles')
                cur.execute('ALTER TABLE public.fixture_real_titles RENAME TO seerr_discovered_titles')


def test_external_fk_does_not_disguise_an_untyped_unique_index(database):
    with database:
        with database.cursor() as cur:
            cur.execute('CREATE UNIQUE INDEX fixture_wrong_identity ON public.seerr_discovered_titles(tmdb_id)')
            cur.execute('CREATE TABLE public.fixture_external_ref(id bigint REFERENCES public.seerr_discovered_titles(tmdb_id))')
    try:
        client = UnifiedClient(); result = both(database, client)
        assert result['errors'] == [{'code': 'seerr_unified_schema_incompatible'}] and client.requests == 0
    finally:
        with database:
            with database.cursor() as cur:
                cur.execute('DROP TABLE public.fixture_external_ref')


def test_partial_manual_v1_upgrade_with_six_columns_is_rejected(database_v1):
    with database_v1:
        with database_v1.cursor() as cur:
            cur.execute('ALTER TABLE public.seerr_discovered_movies RENAME TO seerr_discovered_titles')
            cur.execute("ALTER TABLE public.seerr_discovered_titles ADD COLUMN media_type text DEFAULT 'movie', ADD COLUMN premiere_date date, ADD COLUMN discovery_premiere_date date, ADD COLUMN tv_metadata jsonb")
            cur.execute("ALTER TABLE public.seerr_discovery_observations ADD COLUMN media_type text DEFAULT 'movie', ADD COLUMN eligibility jsonb")
    client = UnifiedClient(); result = both(database_v1, client)
    assert result['errors'] == [{'code': 'seerr_unified_schema_incompatible'}] and client.requests == 0
    assert scalar(database_v1, 'SELECT count(*) FROM public.seerr_discovery_runs') == 0


def test_v2_guard_is_readonly_preserves_search_path_and_accepts_real_migration(database):
    before = inventory_snapshot(database)
    database.set_session(readonly=True)
    try:
        with database:
            with database.cursor() as cur:
                cur.execute("SET LOCAL search_path=pg_catalog")
            require_unified_schema(database)
            with database.cursor() as cur:
                cur.execute("SELECT current_setting('search_path'),current_setting('transaction_read_only')")
                assert cur.fetchone() == ('pg_catalog', 'on')
    finally:
        database.set_session(readonly=False)
    assert inventory_snapshot(database) == before
    assert both(database)['status'] == 'success'


def test_replica_mode_cannot_bypass_fk_integrity(database):
    with database:
        with database.cursor() as cur:
            cur.execute("SET session_replication_role=replica")
    try:
        client = UnifiedClient(); result = both(database, client)
        assert result['errors'] == [{'code': 'seerr_unified_schema_incompatible'}] and client.requests == 0
        assert scalar(database, 'SELECT count(*) FROM public.seerr_discovery_runs') == 0
    finally:
        with database:
            with database.cursor() as cur:
                cur.execute("SET session_replication_role=origin")


def test_ordinary_nonunique_index_does_not_break_compatibility(database):
    with database:
        with database.cursor() as cur:
            cur.execute('CREATE INDEX fixture_extra_reporting ON public.seerr_discovered_titles(title)')
        require_unified_schema(database)
    assert both(database)['status'] == 'success'


@pytest.mark.parametrize('seasons', ['omitted', None, [], 'malformed', [{'seasonNumber': 2, 'airDate': '2026-10-28'}]])
@pytest.mark.parametrize('kind', ['Scripted', None])
def test_incomplete_seasons_remain_provisional_even_with_type(seasons, kind):
    raw = tv(type=kind, seasons=seasons)
    if seasons == 'omitted': raw.pop('seasons')
    clean = sanitize_tv(raw)
    assessment = tv_eligibility(clean, TV.parameters, detail=True)
    assert assessment['state'] == 'provisional'
    assert assessment['reason'] in ('season_metadata_incomplete', 'season_metadata_invalid', 'season_one_missing')


@pytest.mark.parametrize('first_date', ['omitted', None, '', 'bad', 20261028])
def test_season_one_date_unknown_or_malformed_never_eligible(first_date):
    season = {'seasonNumber': 1, 'airDate': first_date}
    if first_date == 'omitted': season.pop('airDate')
    clean = sanitize_tv(tv(seasons=[season]))
    assessment = tv_eligibility(clean, TV.parameters, detail=True)
    assert assessment['state'] == 'provisional'
    assert clean['seasons'][0]['_fields']['airDate'] in ('omitted', 'null', 'invalid')


@pytest.mark.parametrize('seasons', [
    [{'seasonNumber': 1, 'airDate': '2019-01-01'}, {'seasonNumber': 2, 'airDate': '2026-10-28'}],
    [{'seasonNumber': 1, 'airDate': '2026-10-28'}, {'seasonNumber': 2, 'airDate': '2019-01-01'}],
    [{'seasonNumber': 1, 'airDate': '2026-10-28'}, {'seasonNumber': 2, 'airDate': '2026-10-30'}, {'seasonNumber': 3, 'airDate': '2026-10-29'}],
    [{'seasonNumber': 1, 'airDate': '2026-10-28'}, {'seasonNumber': 1, 'airDate': '2026-10-28'}],
])
def test_contradictory_season_dates_are_preserved_provisional_and_idempotent(database, seasons):
    raw = tv(seasons=seasons); client = UnifiedClient(movies=[], details={('tv', 1): raw})
    result = sync(database, client, scopes=[TV], config=TV_CONFIG)
    repo = DiscoveryRepository(database); row = repo.get(1, 'tv')
    assert result['counts']['provisional'] == 1 and result['counts']['eligible'] == 0
    assert row['tv_metadata']['season_premieres'] == sanitize_tv(raw)['seasons']
    assert row['source_metadata']['detail']['seasons'][0]['airDate'] == seasons[0]['airDate']
    observation = scalar(database, 'SELECT to_jsonb(o) FROM public.seerr_discovery_observations o')
    assert observation['eligibility']['reason'] in ('season_premiere_conflict', 'season_metadata_conflict')
    assert observation['detail_observed_at'] and observation['detail_metadata']['seasons']
    again = sync(database, client, scopes=[TV], config=TV_CONFIG, refresh=True, when=NOW+timedelta(days=1))
    assert again['counts']['updated_titles'] == 0
    assert repo.get(1, 'tv')['metadata_updated_at'] == row['metadata_updated_at']


def test_announced_future_series_requires_season_one_evidence():
    scope = DiscoveryScope('future', date(2027, 1, 1), date(2027, 1, 10), media_type='tv')
    missing = sanitize_tv(tv(firstAirDate='2027-01-05', seasons=None))
    reliable = sanitize_tv(tv(firstAirDate='2027-01-05'))
    assert tv_eligibility(missing, scope.parameters, detail=True)['state'] == 'provisional'
    assert tv_eligibility(reliable, scope.parameters, detail=True)['state'] == 'eligible'


def test_old_original_premiere_and_new_season_is_excluded_without_inventing_conflict():
    raw = tv(firstAirDate='2019-01-01', seasons=[{'seasonNumber': 1, 'airDate': '2019-01-01'}, {'seasonNumber': 2, 'airDate': '2026-10-28'}])
    assert tv_eligibility(sanitize_tv(raw), TV.parameters, detail=True) == {'state': 'excluded', 'reason': 'original_premiere_outside_window'}


@pytest.mark.parametrize('detail_date', ['2026-10-29', '2019-01-01'])
def test_summary_detail_conflict_is_provisional_on_fetch_and_cache(database, detail_date):
    raw = tv(firstAirDate=detail_date); client = UnifiedClient(movies=[], details={('tv', 1): raw})
    first = sync(database, client, scopes=[TV], config=TV_CONFIG)
    second = sync(database, client, scopes=[TV], config=TV_CONFIG)
    for result in (first, second):
        assert result['counts']['provisional'] == 1 and result['counts']['eligible'] == 0
        assert result['tv_assessments'][0]['reason'] == 'summary_detail_premiere_conflict'
        assert scalar(database, 'SELECT eligibility FROM public.seerr_discovery_observations WHERE run_id=%s', (result['run_id'],))['reason'] == 'summary_detail_premiere_conflict'
    assert second['counts']['enrichment_cached'] == 1


@pytest.mark.parametrize('resolution', ['valid', 'unknown', 'failure'])
@pytest.mark.parametrize('summary_state', ['omitted', None, 'invalid'])
def test_missing_summary_premiere_is_durably_retained_and_enriched(database, resolution, summary_state):
    raw = summary(tv(firstAirDate=summary_state))
    if summary_state == 'omitted': raw.pop('firstAirDate')
    detail = tv() if resolution == 'valid' else tv(firstAirDate=None) if resolution == 'unknown' else SeerrError('http_404')
    client = UnifiedClient(movies=[], television=[raw], details={('tv', 1): detail})
    result = sync(database, client, scopes=[TV], config=TV_CONFIG)
    row = DiscoveryRepository(database).get(1, 'tv')
    assert row and result['counts']['titles'] == 1 and ('detail', 'tv', 1) in client.calls
    assert not result['pagination'][0]['excluded'] and result['discovery_complete']
    assert result['pagination'][0]['unresolved'][0]['reason'] == 'original_premiere_unknown'
    assert result['counts']['eligible' if resolution == 'valid' else 'provisional'] == 1
    assert row['discovery_premiere_date'] is None
    if resolution == 'valid':
        assert row['premiere_date'] == date(2026, 10, 28) and result['status'] == 'success'
    if resolution == 'failure':
        assert result['status'] == 'partial' and row['enrichment_status'] == 'failed'


def test_summary_missing_date_confirmed_old_by_detail_is_audited_excluded(database):
    raw = summary(tv(firstAirDate=None))
    result = sync(database, UnifiedClient(movies=[], television=[raw], details={('tv', 1): tv(firstAirDate='2019-01-01')}), scopes=[TV], config=TV_CONFIG)
    assert result['counts']['excluded'] == 1 and DiscoveryRepository(database).get(1, 'tv')


def test_season_date_changes_only_update_tv_and_unknown_collection_retains_dates(database):
    both(database); repo = DiscoveryRepository(database); movie_before = repo.get(1)
    changed = tv(seasons=[{'seasonNumber': 1, 'airDate': '2019-01-01'}])
    both(database, UnifiedClient(details={('tv', 1): changed}), refresh=True)
    before = repo.get(1, 'tv')
    assert before['tv_metadata']['season_premieres'][0]['airDate'] == '2019-01-01'
    both(database, UnifiedClient(details={('tv', 1): tv(seasons=None)}), refresh=True)
    assert repo.get(1, 'tv')['tv_metadata']['season_premieres'] == before['tv_metadata']['season_premieres']
    assert repo.get(1)['metadata_fingerprint'] == movie_before['metadata_fingerprint']
    both(database, UnifiedClient(details={('tv', 1): tv(seasons=[])}), refresh=True)
    assert repo.get(1, 'tv')['tv_metadata']['season_premieres'] == []
