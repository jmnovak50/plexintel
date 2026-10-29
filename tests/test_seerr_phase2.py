"""Phase 2 curation coverage, determinism, privacy and read-only boundaries."""
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import analyze_seerr_phase2 as p2
import explore_seerr_candidates as ex


def row(ident=1, **kwargs):
    detail = dict(id=ident, title=f'Film {ident}', originalLanguage='en', releaseDate='2026-10-28',
        popularity=.2, voteCount=0, voteAverage=0, runtime=20, overview='An available descriptive synopsis.',
        posterPath='/poster', genres=[{'id': 27, 'name': 'Horror'}],
        credits={'cast': [{'id': 1, 'name': 'Actor'}], 'crew': [{'id': 2, 'name': 'Director', 'job': 'Director'}]})
    detail.update(kwargs)
    return ex.normalize({'id': ident}, detail)


def decisions(rows):
    return [d for r in rows for d in ex.simulate(r, ex.DEFAULT_RULES)]


def test_exclusion_observations_overlap_but_classes_reconcile():
    rows = [row(1), row(2, runtime=None), row(3, overview=None, credits={'cast': [], 'crew': []})]
    records, stats = p2.analyze(rows, decisions(rows), ex.DEFAULT_RULES)
    assert len(records) == 3 and sum(stats['exclusive_classes'].values()) == 3
    assert stats['overlapping_reasons']['popularity_below_min'] == 3
    assert stats['overlapping_reasons']['runtime_missing'] == 1
    assert stats['overlapping_reasons']['runtime_below_min'] == 2
    assert stats['evaluable_excluded'] == 2
    assert all(r['rating_unsupported'] and not r['supported_rating_below_min'] for r in records)


def test_rich_feature_with_low_popularity_cannot_fail_or_rule():
    r = row(runtime=95, popularity=0, voteCount=0)
    records, stats = p2.analyze([r], decisions([r]), ex.DEFAULT_RULES)
    assert not records and stats['metadata_ready_feature_excluded'] == 0
    assert p2.proposed_tier(r) == 'evaluate_now'


def test_readiness_does_not_require_runtime_votes_release_or_future_release_to_pass():
    r = row(runtime=None, voteCount=0, releaseDate='2030-01-01', popularity=0)
    assert p2.proposed_tier(r) == 'evaluate_now'
    r['primary_release_date'] = None
    assert p2.proposed_tier(r) == 'evaluate_now'
    r['overview'] = None
    assert p2.proposed_tier(r) == 'revisit'
    assert p2.config()['revisit']['permanent_drop_for_missing_metadata'] is False
    assert p2.config()['enabled'] is False


def test_tier_standard_and_4k_workflows_do_not_conflate():
    standard = row(mediaInfo={'status': 3, 'requests': [{'status': 2, 'is4k': False}]})
    four_k = row(mediaInfo={'status': 1, 'status4k': 3, 'requests': [{'status': 2, 'is4k': True}]})
    assert p2.proposed_tier(standard) == 'hold_existing_workflow'
    assert p2.proposed_tier(four_k) == 'evaluate_now'
    assert four_k['standard_request_statuses'] == [] and four_k['request_statuses_4k'] == ['approved']


def test_sampling_is_unique_repeatable_and_independent_of_input_order():
    rows = [row(i, popularity=8 if i % 5 == 0 else .2, runtime=None if i % 7 == 0 else 90 if i % 3 == 0 else 20,
                genres=[{'id': 99, 'name': 'Documentary'}] if i % 4 == 0 else [{'id': 27, 'name': 'Horror'}]) for i in range(1, 121)]
    sample, strata = p2.review_sample(rows, decisions(rows), ex.DEFAULT_RULES)
    backwards, _ = p2.review_sample(list(reversed(rows)), decisions(rows), ex.DEFAULT_RULES)
    assert sample == backwards and len(sample) == len({r['tmdb_id'] for r in sample}) == 50
    assert sum(s['selected'] for s in strata) <= 50


def test_rejected_feature_like_movies_are_all_selected_for_review():
    features = [row(i, runtime=90, genres=[], credits={'cast': [], 'crew': []}) for i in range(1, 5)]
    assert all(r['completeness'] == 4 for r in features)
    rows = features + [row(i) for i in range(5, 80)]
    sample, _ = p2.review_sample(rows, decisions(rows), ex.DEFAULT_RULES)
    assert {r['tmdb_id'] for r in sample if r['stratum'] == 'excluded_feature_like'} == {1, 2, 3, 4}


def test_control_projection_drops_credentials_and_personal_data():
    raw = {'apiKey': 'secret', 'email': 'private', 'settings': {'originalLanguage': 'en', 'email': 'private'}}
    assert p2.response_projection('/auth/me', raw) == {'originalLanguage': 'en', 'streamingRegion': None, 'locale': None}
    assert 'secret' not in json.dumps(p2.response_projection('/settings/main', raw))
    with pytest.raises(ValueError):
        p2.response_projection('/settings/radarr', raw)


def test_control_redirect_does_not_follow_or_try_other_endpoints(monkeypatch):
    monkeypatch.setattr(p2.time, 'sleep', lambda _: None)
    client = Mock(retries=3, interval=0, timeout=25, base='https://example.invalid', audit=[])
    client.session.get.return_value.status_code = 302
    result = p2.controls(client)
    assert result == {'/status': {'error': 'http_302'}}
    assert client.session.get.call_count == 1
    assert client.session.get.call_args.kwargs['allow_redirects'] is False
    assert client.session.post.call_count == 0


def test_live_superset_check_catches_equal_count_but_different_ids():
    r1, r2 = row(1), row(2)
    live = {'discovery': {'configured': {'rows': [{'id': 1}], 'coverage': {'complete': True}},
                          'all': {'rows': [{'id': 2}], 'coverage': {'complete': True}}}}
    result = p2.language_comparison([r1], [r2], live)
    assert not result['live_superset'] and result['live_configured_only'] == [1]


def test_phase1_paths_and_descendants_are_rejected_before_writing():
    for name in ('2026-10-28-week', '2026-10-28-week/nested-phase2', 'cache/new-output'):
        with pytest.raises(SystemExit) as err:
            p2.main(['--output', str(p2.BASE / name)])
        assert err.value.code == 2


def test_human_review_includes_tmdb_synopsis_and_rejection_observations():
    rows = [row(1), row(2, runtime=90)]
    ds = decisions(rows)
    sample, strata = p2.review_sample(rows, ds, ex.DEFAULT_RULES)
    markdown = p2.review_markdown(rows, ds, sample, strata)
    assert 'https://www.themoviedb.org/movie/1' in markdown
    assert 'An available descriptive synopsis.' in markdown
    assert 'runtime_below_min' in markdown and 'Excluded by Phase 1' in markdown
    assert 'Retained by Phase 1' in markdown


def test_available_and_partial_records_are_not_unknown():
    full = row(mediaInfo={'status': 5, 'requests': [], 'libraryIdentifierPresent': True})
    partial = row(mediaInfo={'status': 4})
    assert full['standard_library_availability'] == 'seerr_reported_available'
    assert partial['standard_library_availability'] == 'seerr_reported_partially_available'
    assert p2.proposed_tier(full) == p2.proposed_tier(partial) == 'hold_existing_workflow'


def test_analysis_modules_do_not_import_production_job_modules():
    import ast
    forbidden = {'score_model', 'train_model', 'fetch_tautulli_data', 'ollama_embeddings', 'build_training_data', 'build_user_embeddings'}
    for name in ('analyze_seerr_phase2.py', 'benchmark_seerr_phase2.py'):
        tree = ast.parse((SCRIPTS / name).read_text())
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported.update(a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names)
        assert not imported & forbidden


def benchmark_module():
    pytest.importorskip('numpy')
    import benchmark_seerr_phase2
    return benchmark_seerr_phase2


def test_model_metadata_inspection_does_not_call_fit_or_predict(tmp_path, monkeypatch):
    module = benchmark_module()
    joblib = pytest.importorskip('joblib')
    booster = Mock(feature_names=['emb_0', 'watch_sim'])
    booster.get_dump.return_value = [json.dumps({'split': 'watch_sim', 'children': [{'leaf': .1}, {'leaf': -.1}]})]
    booster.get_score.return_value = {'watch_sim': 1.0}
    model = Mock()
    model.get_booster.return_value = booster
    monkeypatch.setattr(joblib, 'load', lambda _: model)
    path = tmp_path / 'artifact.pkl'
    path.write_bytes(b'fixture')
    result = module.inspect_model(path)
    assert result['feature_count'] == 2 and result['max_depth'] == 1
    assert result['watch_sim_split_count'] == 1 and result['inference_executed'] is False
    assert model.predict.call_count == model.predict_proba.call_count == model.fit.call_count == 0
    assert path.read_bytes() == b'fixture'


def test_capacity_arithmetic_and_unmeasured_assumptions_are_explicit(tmp_path, monkeypatch):
    module = benchmark_module()
    output = tmp_path / 'phase2'
    output.mkdir()
    for name, count in [('2026-10-28-week', 333), ('2026-10-28-all-languages', 777)]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / 'candidates.json').write_text(json.dumps([
            dict(title='Movie', overview='Synopsis', genres=['Drama'], directors=['Unseen Director']) for _ in range(count)]))
    monkeypatch.setattr(module, 'benchmark', lambda fn: {'median_seconds': .5})
    model = dict(feature_count=1605, feature_groups={'emb': 1536}, feature_names=['genre_Drama', 'director_Known'], tree_count=100, max_depth=6)
    result = module.estimates(output, model, {'user_profile_rows': 3})
    assert result['calculated']['333']['pair_count'] == 999
    assert result['calculated']['777']['pair_count'] == 2331
    assert result['assumptions']['embedding_and_xgboost_throughput_measured'] is False
    assert result['calculated']['333']['metadata_seconds_warm_extrapolation'] is None
    assert result['vocabulary_coverage']['333']['directors']['titles_with_any_trained_flag'] == 0


def test_capacity_database_read_is_aggregate_only_and_read_only(monkeypatch):
    module = benchmark_module()
    import api.db.connection
    conn, cur = Mock(), Mock()
    conn.cursor.return_value.__enter__ = Mock(return_value=cur)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    cur.fetchone.side_effect = [(31, 768, 768), (31,)]
    cur.fetchall.return_value = []
    monkeypatch.setattr(api.db.connection, 'connect_db', lambda: conn)
    result = module.read_aggregates()
    assert result['user_profile_rows'] == 31
    assert conn.set_session.call_args.kwargs['readonly'] is True
    assert conn.rollback.call_count == conn.close.call_count == 1 and conn.commit.call_count == 0
    assert all(c.args[0].strip().upper().startswith(('SELECT ', 'SET LOCAL ')) for c in cur.execute.call_args_list)


def test_report_rendering_receives_rule_configuration_and_exclusion_records(tmp_path):
    rows = [row(1), row(2, runtime=90)]
    records, stats = p2.analyze(rows, decisions(rows), ex.DEFAULT_RULES)
    p2.render_reports(tmp_path, rows, rows, stats, stats, {}, None, {},
                      {'assumptions': {}, 'table': []}, records, ex.DEFAULT_RULES)
    assert '1 Phase 1 multi-path exclusions' in (tmp_path / 'excluded-candidate-analysis.md').read_text()
    assert (tmp_path / 'phase2-findings.md').exists()
    assert (tmp_path / 'prospective-scoring-feasibility.md').exists()
