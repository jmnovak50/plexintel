"""Isolated safety/coverage contracts; no live Seerr or database calls."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location('seerr_exploration', Path(__file__).parents[1] / 'scripts/explore_seerr_candidates.py')
ex = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ex)


def movie(**overrides):
    base = dict(id=1, title='Small Film', mediaType='movie', popularity=0.2,
                voteCount=0, voteAverage=0, releaseDate='2026-11-01', originalLanguage='fr')
    return {**base, **overrides}


def test_pagination_deduplicates_and_flags_count_loss():
    client = Mock()
    client.get.side_effect = [dict(page=1, totalPages=2, totalResults=3, results=[movie(), movie(id=2)]),
                              dict(page=2, totalPages=2, totalResults=3, results=[movie(id=2)])]
    rows, audit = ex.discover(client, '2026-10-26', '2026-11-01', 'all')
    assert len(rows) == 2 and audit['duplicate_rows'] == 1 and not audit['complete']
    assert client.get.call_args_list[1].args[1]['page'] == 2
    assert client.get.call_args_list[0].args[1]['primaryReleaseDateGte'] == '2026-10-26'


def test_failed_page_does_not_become_empty_history():
    client = Mock()
    client.get.side_effect = [dict(page=1, totalPages=3, totalResults=3, results=[movie()]),
        ex.ApiError('server_error'), dict(page=3, totalPages=3, totalResults=3, results=[movie(id=3)])]
    rows, audit = ex.discover(client, '2026-10-26', '2026-11-01', 'all')
    assert len(rows) == 2 and audit['retrieved_pages'] == [1, 3]
    assert audit['failures'] == [{'page': 2, 'error': 'server_error'}]
    assert not audit['complete']


def test_pagination_drift_and_invalid_ids_are_incomplete():
    client = Mock()
    client.get.side_effect = [dict(page=1, totalPages=2, totalResults=2, results=[movie()]),
        dict(page=2, totalPages=2, totalResults=4, results=[movie(id=True)])]
    _, audit = ex.discover(client, '', '', 'all')
    assert audit['invalid_ids'] == 1 and not audit['complete']


def test_zero_result_set_is_complete():
    client = Mock()
    client.get.return_value = dict(page=1, totalPages=0, totalResults=0, results=[])
    rows, audit = ex.discover(client, '', '', 'all')
    assert rows == [] and audit['complete']


def test_unknown_status_unrated_and_release_events_are_explicit():
    row = ex.normalize(movie(), {**movie(), 'runtime': 0,
        'releases': {'results': [{'iso_3166_1': 'US', 'release_dates': [
            {'type': 3, 'release_date': '2026-11-01T00:00:00Z'}]}]}})
    assert row['media_status'] == 'unknown' and row['request_statuses'] is None
    assert row['runtime'] is None and row['rated_vote_average'] is None
    assert row['digital_event_count'] == 0 and row['release_events'][0]['country'] == 'US'
    assert not next(d for d in ex.simulate(row, ex.DEFAULT_RULES) if d['approach'] == 'broad')['hard_exclusions']


def test_primary_date_observations_are_auditable_when_details_drift():
    row = ex.normalize(movie(), {**movie(), 'releaseDate': None})
    assert row['primary_release_date'] == '2026-11-01' and row['detail_primary_release_date'] is None
    row = ex.normalize(movie(), {**movie(), 'releaseDate': '2026-11-30'})
    assert row['release_date_disagrees'] and row['discovery_primary_release_date'] == '2026-11-01'
    assert row['primary_release_date'] == '2026-11-30'


def test_niche_and_unreleased_paths_retain_without_votes_or_popularity():
    detail = {**movie(), 'genres': [{'id': 99, 'name': 'Documentary'}], 'runtime': 15,
              'overview': 'A film', 'posterPath': '/poster', 'credits': {'cast': [{'id': 5, 'name': 'A'}], 'crew': []}}
    row = ex.normalize(movie(), detail)
    decisions = {d['approach']: d for d in ex.simulate(row, ex.DEFAULT_RULES)}
    assert decisions['multi_path']['included'] and 'niche_metadata' in decisions['multi_path']['qualifying_paths']
    assert not decisions['popularity']['included'] and not decisions['metadata']['included']
    row = ex.normalize(movie(), {**movie(), 'status': 'Post Production'})
    assert next(d for d in ex.simulate(row, ex.DEFAULT_RULES) if d['approach'] == 'multi_path')['disposition'] == 'defer'


def test_enrichment_failure_is_deferred_and_status_hard_exclusions_apply_to_all():
    client = Mock()
    client.get.side_effect = ex.ApiError('http_403', stop=True)
    rows = ex.enrich(client, [movie(), movie(id=2)])
    assert client.get.call_count == 1 and not rows[0]['detail_ok']
    assert next(d for d in ex.simulate(rows[0], ex.DEFAULT_RULES) if d['approach'] == 'multi_path')['disposition'] == 'defer'
    row = ex.normalize(movie(), {**movie(), 'mediaInfo': {'status': 5}})
    assert all(not d['included'] and d['hard_exclusions'] for d in ex.simulate(row, ex.DEFAULT_RULES))


def test_request_absent_empty_and_unknown_codes_differ():
    a = ex.normalize(movie(), {**movie(), 'mediaInfo': {'status': 999, 'requests': []}})
    b = ex.normalize(movie(), {**movie(), 'mediaInfo': {'status': 1}})
    assert a['request_count'] == 0 and b['request_count'] is None
    assert a['media_status'] == 'unrecognized:999' and b['media_status'] == 'unknown'


def test_sanitization_removes_requester_credentials_and_internal_paths():
    data = ex.sanitize_movie({**movie(), 'apiKey': 'secret', 'mediaInfo': {'status': 2,
        'serviceUrl': 'private', 'requests': [{'id': 123, 'status': 1, 'requestedBy': {'email': 'private'}}]}})
    assert data['mediaInfo'] == {'status': 2, 'requestsFieldState': 'list', 'requests': [{'status': 1}]}
    assert 'secret' not in json.dumps(data) and 'private' not in json.dumps(data)


def test_processing_approved_reference_preserves_status_without_claiming_available():
    payload = {**movie(id=1300968), 'mediaInfo': {'id': 77, 'status': 3, 'status4k': 1,
        'externalServiceId': 123, 'ratingKey': None, 'serviceUrl': 'private',
        'downloadStatus': [], 'requests': [{'id': 88, 'status': 2, 'is4k': False, 'requestedBy': {'email': 'private'}}]}}
    clean = ex.sanitize_movie(payload)
    row = ex.normalize(movie(id=1300968), clean)
    assert row['media_status'] == 'processing' and row['request_statuses'] == ['approved']
    assert row['media_record_state'] == 'record_returned' and row['external_service_link_present'] is True
    assert row['standard_library_availability'] == 'not_reported_available'
    assert row['radarr_monitored'] is None and row['library_identifier_present'] is False
    assert 'externalServiceId' not in json.dumps(clean) and 'private' not in json.dumps(clean)
    assert ex.sanitize_movie(clean) == clean


@pytest.mark.parametrize('payload,state,record', [
    ({}, 'missing', 'unavailable'), ({'mediaInfo': None}, 'null', 'no_associated_record_returned'),
    ({'mediaInfo': {}}, 'object', 'record_returned'), ({'mediaInfo': 'bad'}, 'invalid', 'unavailable')])
def test_media_record_absence_null_and_unknown_record_are_distinct(payload, state, record):
    observed = ex.media_observation(ex.sanitize_movie(payload))
    assert observed['media_info_field_state'] == state and observed['media_record_state'] == record
    assert observed['standard_library_availability'] == 'unknown'


def test_null_request_list_and_failed_enrichment_are_not_empty_requests():
    payload = ex.sanitize_movie({'mediaInfo': {'status': 1, 'requests': None}})
    assert ex.media_observation(payload)['request_list_state'] == 'null'
    assert ex.media_observation(payload, 'network_failure')['media_record_state'] == 'extraction_failed'
    assert ex.media_observation(ex.sanitize_movie({'mediaInfo': {'requests': []}}))['request_list_state'] == 'empty_list'


def make_client(tmp_path, **kwargs):
    client = ex.Client('https://example.invalid', 'private-key', tmp_path / 'cache', interval=0, **kwargs)
    client.session = Mock()
    return client


def response(status=200, data=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = movie() if data is None else data
    return result


def test_client_only_gets_allowlisted_endpoints_and_never_redirects(tmp_path):
    client = make_client(tmp_path)
    client.session.get.return_value = response()
    assert client.get('/movie/1')['id'] == 1
    assert client.session.get.call_args.kwargs['allow_redirects'] is False
    for path in ('/request', '/settings/radarr', '/movie/1/../request', '/movie/0'):
        with pytest.raises(ValueError):
            client.get(path)
    assert client.session.post.call_count == 0
    client.session.get.return_value = response(302)
    with pytest.raises(ex.ApiError, match='http_302'):
        client.get('/movie/2')


def test_search_spaces_are_percent_encoded_for_seerr_validator(tmp_path):
    client = make_client(tmp_path)
    client.session.get.return_value = response(data=dict(results=[]))
    client.get('/search', {'query': 'A Movie: Part 2', 'page': 1})
    params = client.session.get.call_args.kwargs['params']
    assert 'A%20Movie%3A%20Part%202' in params and '+' not in params


def test_cache_scope_ttl_corruption_and_offline_stale(tmp_path, monkeypatch):
    client = make_client(tmp_path, ttl=10)
    client.session.get.return_value = response()
    client.get('/movie/1')
    file = next((tmp_path / 'cache').glob('*.json'))
    assert file.stat().st_mode & 0o777 == 0o600
    assert 'private-key' not in file.read_text()
    client.get('/movie/1')
    assert client.session.get.call_count == 1
    entry = json.loads(file.read_text())
    entry['epoch'] -= 20
    file.write_text(json.dumps(entry))
    client.offline = True
    client.get('/movie/1')
    assert client.audit[-1]['stale']
    client.key = 'another-key'
    other = ex.Client('https://example.invalid', 'another-key', tmp_path / 'cache', offline=True)
    with pytest.raises(ex.ApiError, match='offline_cache_miss'):
        other.get('/movie/1')
    file.write_text('broken')
    with pytest.raises(ex.ApiError, match='offline_cache_miss'):
        client.get('/movie/1')


def test_retry_after_respected_and_overbudget_stops(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(ex.time, 'sleep', sleeps.append)
    client = make_client(tmp_path)
    client.session.get.side_effect = [response(429, headers={'Retry-After': '3'}), response()]
    client.get('/movie/1')
    assert 3 in sleeps and client.session.get.call_count == 2
    client.session.get.side_effect = None
    client.session.get.return_value = response(429, headers={'Retry-After': '600'})
    with pytest.raises(ex.ApiError) as err:
        client.get('/movie/2')
    assert err.value.stop


def test_bad_detail_id_and_auth_failures_are_not_cached(tmp_path):
    client = make_client(tmp_path)
    client.session.get.return_value = response(data=movie(id=999))
    with pytest.raises(ex.ApiError, match='invalid_json_or_schema'):
        client.get('/movie/1')
    client.session.get.return_value = response(401)
    with pytest.raises(ex.ApiError) as err:
        client.get('/movie/1')
    assert err.value.stop and not list((tmp_path / 'cache').glob('*.json'))


def test_historical_match_ambiguity_and_current_status_neutralization():
    history = [dict(rating_key=1, title='Small Film', year=2026, viewers=2, engaged_viewers=2)]
    client = Mock()
    client.get.side_effect = [dict(results=[movie(), movie(id=2)]), dict(results=[movie()]),
                             {**movie(), 'mediaInfo': {'status': 5}}]
    rows, mapping = ex.match_history(client, history, 1)
    assert rows == [] and mapping[0]['result'] == 'ambiguous_match'
    rows, mapping = ex.match_history(client, history, 1)
    assert rows[0]['media_status'] == 'unknown'
    assert ex.compare_history(rows, ex.DEFAULT_RULES)[0]['engagement_retention'] == 1


def test_csv_formula_safety_and_json_losslessness(tmp_path):
    rows = [{'title': '=HYPERLINK("bad")', 'cast': ['A']}]
    ex.write_csv(tmp_path / 'data.csv', rows)
    ex.write_json(tmp_path / 'data.json', rows)
    assert "'=HYPERLINK" in (tmp_path / 'data.csv').read_text()
    assert json.loads((tmp_path / 'data.json').read_text()) == rows


def test_default_discovery_preserves_configured_language_scope():
    client = Mock()
    client.get.return_value = dict(page=1, totalPages=1, totalResults=1, results=[movie()])
    ex.discover(client, '2026-10-26', '2026-11-01', None)
    assert 'language' not in client.get.call_args.args[1]


def test_database_transaction_is_read_only_and_rolls_back(monkeypatch):
    import api.db.connection
    connection = Mock()
    cursor = Mock()
    cursor.fetchall.return_value = []
    connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
    connection.cursor.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(api.db.connection, 'connect_db', lambda: connection)
    rows, metadata = ex.read_history()
    assert rows == [] and metadata['available']
    assert connection.set_session.call_args.kwargs['readonly'] is True
    assert connection.set_session.call_args.kwargs['isolation_level'] == 'REPEATABLE READ'
    statements = [call.args[0].strip().upper() for call in cursor.execute.call_args_list]
    assert all(s.startswith(('SET LOCAL ', 'WITH ')) for s in statements)
    assert connection.rollback.call_count == 1 and connection.close.call_count == 1
    assert connection.commit.call_count == 0


def test_duplicate_historical_library_editions_are_not_double_counted():
    sources = [dict(rating_key=i, title='Small Film', year=2026, viewers=2, engaged_viewers=2) for i in (1, 2)]
    client = Mock()
    client.get.side_effect = [dict(results=[movie()]), movie(), dict(results=[movie()]), movie()]
    rows, mapping = ex.match_history(client, sources, 2)
    assert not rows and all(m['result'] == 'duplicate_library_editions_excluded' for m in mapping)


def test_partial_cli_persists_decisions_report_and_failure_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, 'load_dotenv', lambda *a, **k: None)
    monkeypatch.setenv('SEERR_URL', 'https://example.invalid')
    monkeypatch.setenv('SEERR_API_KEY', 'test-secret')
    client = Mock(audit=[])
    client.get.side_effect = [dict(page=1, totalPages=1, totalResults=1, results=[movie()]),
                              ex.ApiError('offline_cache_miss')]
    monkeypatch.setattr(ex, 'Client', lambda *a, **k: client)
    output = tmp_path / 'snapshot'
    result = ex.main(['--start', '2026-10-26', '--end', '2026-11-01', '--output', str(output), '--offline'])
    assert result == 2
    decisions = json.loads((output / 'decisions.json').read_text())
    assert len(decisions) == len(ex.APPROACHES)
    assert next(d for d in decisions if d['approach'] == 'multi_path')['disposition'] == 'defer'
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['discovery']['complete'] and not manifest['enrichment_complete']
    assert 'analysis.md' in manifest['outputs_sha256']
    assert 'test-secret' not in (output / 'manifest.json').read_text()
