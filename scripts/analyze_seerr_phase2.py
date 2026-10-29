#!/usr/bin/env python3
"""Phase 2 offline curation analysis; optional narrowly scoped GET validation.

Never executes production embedding/scoring modules. Phase 1 artifacts are inputs only.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time

from dotenv import dotenv_values
import requests

import explore_seerr_candidates as ex

ROOT = ex.ROOT
BASE = ROOT / 'artifacts/seerr-exploration'
SOURCE_FILES = ['score_model.py', 'train_model.py', 'fetch_tautulli_data.py', 'build_training_data.py',
                'build_user_embeddings.py', 'ollama_embeddings.py', 'user_profile_embeddings.py',
                'xgb_model.pkl', 'run_daily_pipeline.sh']
SEED = 'plexintel-seerr-phase2-20261028'


def read_json(path):
    return json.loads(path.read_text())


def input_fingerprints():
    files = [ROOT / name for name in SOURCE_FILES]
    for dirname in ('2026-10-28-week', '2026-10-28-all-languages', '2026-10-28-week-mixed-pages', 'cache'):
        files.extend(p for p in (BASE / dirname).rglob('*') if p.is_file())
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def source_inspection():
    wanted = {
        'fetch_tautulli_data.py': ['_media_text_for_embedding', 'generate_media_embeddings', '_watch_text_for_embedding'],
        'ollama_embeddings.py': ['_post_embed', 'embed_texts'],
        'user_profile_embeddings.py': ['build_user_profiles', 'leave_one_title_out', 'fuse_media_and_user_embedding'],
        'build_training_data.py': ['build_user_watch_vectors', 'process_row', 'build_training_data'],
        'train_model.py': ['preprocess', 'train_and_evaluate'],
        'score_model.py': ['get_user_watch_vector', 'get_unwatched_media', 'preprocess_for_scoring', 'score_and_store'],
    }
    result = []
    for filename, functions in wanted.items():
        raw = (ROOT / filename).read_bytes()
        tree = ast.parse(raw)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions:
                result.append(dict(file=filename, function=node.name, start_line=node.lineno,
                                   end_line=node.end_lineno, file_sha256=hashlib.sha256(raw).hexdigest()))
    return result


def rank(row, tag):
    return hashlib.sha256(f"{SEED}:{tag}:{row['tmdb_id']}".encode()).hexdigest()


def has_synopsis(row):
    return bool((row.get('title') or '').strip() and (row.get('overview') or '').strip())


def diagnostics(row, cfg):
    """Overlapping observations, not quality labels or a list of independent AND gates."""
    runtime, popularity, votes = row.get('runtime'), row.get('popularity'), row.get('vote_count')
    components = row['completeness_components']
    return dict(
        popularity_below_min=popularity is not None and popularity < cfg['popularity_min'],
        popularity_unknown=popularity is None,
        votes_below_min=votes is not None and votes < cfg['votes_min'],
        votes_unknown=votes is None, zero_votes=votes == 0,
        rating_unsupported=(votes or 0) < cfg['votes_min'] or row.get('vote_average') is None,
        supported_rating_below_min=(votes or 0) >= cfg['votes_min'] and row.get('vote_average') is not None
                                   and row['vote_average'] < cfg['rating_min'],
        runtime_missing=runtime is None, runtime_below_min=runtime is not None and runtime < cfg['runtime_min'],
        synopsis_missing=not bool((row.get('overview') or '').strip()),
        genre_names_missing=not bool(row.get('genres')), genre_ids_and_names_missing=not components['genres'],
        cast_missing=not bool(row.get('cast')), crew_missing=not bool(row.get('crew')),
        director_missing=not components['director'], poster_missing=not components['poster'],
        primary_date_missing=not row.get('primary_release_date'),
        detail_primary_date_missing=not row.get('detail_primary_release_date'),
        release_events_missing=not bool(row.get('release_events')),
        completeness_below_min=row['completeness'] < cfg['completeness_min'],
        no_niche_genre=not bool(set(row.get('genres', [])) & set(cfg['niche_genres'])),
        no_admin_exception=row['tmdb_id'] not in cfg['niche_tmdb_ids'] and not bool(set(row.get('person_ids', [])) & set(cfg['person_ids'])),
        descriptive_embedding_possible=has_synopsis(row),
        metadata_path_pass=row['completeness'] >= cfg['completeness_min'] and runtime is not None and runtime >= cfg['runtime_min'])


def exclusive_class(row, cfg):
    if not has_synopsis(row):
        return 'missing_descriptive_synopsis'
    if row['runtime'] is None:
        return 'synopsis_present_runtime_unknown'
    if row['runtime'] < cfg['runtime_min']:
        return 'synopsis_present_short_form'
    if row['completeness'] < cfg['completeness_min']:
        return 'feature_like_synopsis_present_missing_other_metadata'
    return 'metadata_ready_feature_like'


def proposed_tier(row):
    """Descriptive simulation only: no scoring call, requests, or durable eligibility state."""
    if row.get('adult') is True or row.get('media_status') == 'blocklisted':
        return 'exclude_policy'
    if row.get('media_status') in ('available', 'partially_available', 'processing', 'pending'):
        return 'hold_existing_workflow'
    if any(s in ('pending', 'approved', 'completed') for s in row.get('standard_request_statuses') or []):
        return 'hold_existing_workflow'
    return 'evaluate_now' if row.get('detail_ok') and has_synopsis(row) else 'revisit'


def analyze(rows, decisions, cfg):
    by_id = {d['tmdb_id']: d for d in decisions if d['approach'] == 'multi_path'}
    records = []
    for row in rows:
        d = by_id[row['tmdb_id']]
        if d['included']:
            continue
        flags = diagnostics(row, cfg)
        records.append(dict(tmdb_id=row['tmdb_id'], title=row['title'],
            year=(row.get('primary_release_date') or '')[:4] or None,
            tmdb_url=f"https://www.themoviedb.org/movie/{row['tmdb_id']}",
            runtime=row['runtime'], popularity=row['popularity'], vote_count=row['vote_count'],
            vote_average=row['vote_average'], completeness=row['completeness'],
            genres=row['genres'], exclusive_class=exclusive_class(row, cfg),
            phase1_hard_exclusions=d['hard_exclusions'], phase1_soft_exclusion=d['soft_exclusion'],
            failed_paths=[p for p in ('popular', 'metadata', 'rated', 'niche_metadata', 'curated_title_or_person', 'defer_sparse_or_failed_detail')
                          if p not in d['qualifying_paths']],
            applicable_observations=[k for k, v in flags.items() if v and k not in ('descriptive_embedding_possible', 'metadata_path_pass')],
            proposed_tier=proposed_tier(row), **flags))
    stats = dict(total=len(rows), excluded=len(records), retained=sum(d['included'] for d in by_id.values()),
        overlapping_reasons=dict(Counter(k for r in records for k in r['applicable_observations'])),
        exclusive_classes=dict(Counter(r['exclusive_class'] for r in records)),
        evaluable_excluded=sum(r['descriptive_embedding_possible'] for r in records),
        metadata_ready_feature_excluded=sum(r['metadata_path_pass'] for r in records),
        rich_short_excluded=sum(r['completeness'] >= cfg['completeness_min'] and r['runtime'] is not None and r['runtime'] < cfg['runtime_min'] for r in records),
        tier_counts=dict(Counter(proposed_tier(r) for r in rows)),
        excluded_tier_counts=dict(Counter(r['proposed_tier'] for r in records)))
    return records, stats


def review_sample(rows, decisions, cfg):
    """Fixed disjoint primary strata, hash sampling within strata, no popularity cherry-picking."""
    by_id = {d['tmdb_id']: d for d in decisions if d['approach'] == 'multi_path'}
    def included(r):
        return by_id[r['tmdb_id']]['included']
    strata = [
        ('retained_high_priority', 5, lambda r: included(r) and (r['popularity'] or 0) >= cfg['popularity_min']),
        ('retained_niche_short_or_unknown_runtime', 5, lambda r: included(r) and 'niche_metadata' in by_id[r['tmdb_id']]['qualifying_paths'] and (r['runtime'] is None or r['runtime'] < cfg['runtime_min'])),
        ('retained_near_boundary', 5, lambda r: included(r) and ((r['runtime'] is not None and 40 <= r['runtime'] <= 50) or r['completeness'] == 5)),
        ('retained_sparse_or_deferred', 5, lambda r: included(r) and (r['completeness'] < 5 or by_id[r['tmdb_id']]['disposition'] == 'defer')),
        ('retained_strong_metadata', 5, lambda r: included(r) and r['completeness'] >= 6),
        ('excluded_feature_like', 4, lambda r: not included(r) and r['runtime'] is not None and r['runtime'] >= cfg['runtime_min']),
        ('excluded_just_below_runtime', 4, lambda r: not included(r) and r['runtime'] is not None and 25 <= r['runtime'] < cfg['runtime_min']),
        ('excluded_rich_low_popularity_short', 6, lambda r: not included(r) and r['completeness'] >= 5 and r['runtime'] is not None and r['runtime'] < 25),
        ('excluded_missing_runtime_rich_metadata', 6, lambda r: not included(r) and r['runtime'] is None and r['completeness'] >= 5),
        ('excluded_sparse_metadata', 5, lambda r: not included(r) and r['completeness'] < 5),
    ]
    chosen, seen, audit = [], set(), []
    for tag, quota, predicate in strata:
        pool = sorted((r for r in rows if r['tmdb_id'] not in seen and predicate(r)), key=lambda r: rank(r, tag))
        selected = pool[:quota]
        for r in selected:
            chosen.append(dict(tmdb_id=r['tmdb_id'], stratum=tag))
            seen.add(r['tmdb_id'])
        audit.append(dict(stratum=tag, eligible_remaining=len(pool), requested=quota, selected=len(selected)))
    # Insufficient strata are filled with a deterministic, equal-status alternating sample.
    target = min(50, len(rows))
    for state in (False, True):
        pool = sorted((r for r in rows if r['tmdb_id'] not in seen and included(r) == state), key=lambda r: rank(r, 'fill'))
        for r in pool[:max(0, target - len(chosen))]:
            chosen.append(dict(tmdb_id=r['tmdb_id'], stratum='excluded_fill' if not state else 'retained_fill'))
            seen.add(r['tmdb_id'])
    return chosen, audit


def old_cache_details(cache):
    result = {}
    for p in sorted(cache.glob('*.json')):
        data = read_json(p)
        row = data.get('data') or {}
        if 'credits' in row and ex.valid_id(row.get('id')):
            previous = result.get(row['id'])
            if previous is None or data['epoch'] > previous['epoch']:
                result[row['id']] = data
    return result


def response_projection(path, raw):
    """Only persist these projections, never raw account/settings responses."""
    if path == '/status':
        return {k: raw.get(k) for k in ('version', 'commitTag')}
    if path == '/settings/main':
        return {k: raw.get(k) for k in ('originalLanguage', 'discoverRegion', 'streamingRegion', 'locale', 'hideAvailable', 'hideRequested')}
    if path == '/auth/me':
        return {k: (raw.get('settings') or {}).get(k) for k in ('originalLanguage', 'streamingRegion', 'locale')}
    raise ValueError('Control endpoint not allowlisted')


def controls(client):
    results = {}
    for path in ('/status', '/settings/main', '/auth/me'):
        for attempt in range(client.retries + 1):
            time.sleep(client.interval)
            start = time.perf_counter()
            try:
                r = client.session.get(client.base + '/api/v1' + path, timeout=client.timeout, allow_redirects=False)
                status = r.status_code
                client.audit.append(dict(path=path, http_status=status, elapsed_seconds=time.perf_counter() - start,
                                         fetched_at=ex.utcnow(), attempt=attempt, source='network'))
                if status == 429 or 500 <= status < 600:
                    if attempt == client.retries:
                        results[path] = dict(error='rate_limit_or_server_error')
                        return results
                    retry = r.headers.get('Retry-After', '2')
                    try:
                        wait = float(retry)
                    except ValueError:
                        results[path] = dict(error='unhandled_retry_after')
                        return results
                    if not math.isfinite(wait) or wait > client.max_wait:
                        results[path] = dict(error='retry_after_exceeds_budget')
                        return results
                    time.sleep(max(0, wait))
                    continue
                if status != 200:
                    results[path] = dict(error=f'http_{status}')
                    if status in (401, 403) or 300 <= status < 400:
                        return results
                    break
                results[path] = response_projection(path, r.json())
                break
            except (requests.RequestException, ValueError):
                if attempt == client.retries:
                    results[path] = dict(error='network_or_json_failure')
                else:
                    time.sleep(2 ** attempt)
    return results


def collect_live(output, credential_file, rows, decisions, history):
    values = dotenv_values(credential_file, interpolate=False)
    base = os.getenv('SEERR_URL') or values.get('SEERR_URL') or values.get('SEER_URL')
    key = os.getenv('SEERR_API_KEY') or values.get('SEERR_API_KEY') or values.get('SEER_API_KEY')
    if not base or not key:
        raise ValueError('Configure Seerr credentials')
    live_dir = output / 'live-validation'
    if live_dir.exists():
        raise ValueError('Live validation already exists; use a new Phase 2 output directory')
    ex.private_dir(live_dir)
    client = ex.Client(base, key, live_dir / 'cache', ttl=0)
    result = dict(started_at=ex.utcnow(), controls=controls(client), movies=[])
    original_get = client.get
    def measured_get(path, params=None):
        start = time.perf_counter()
        try:
            return original_get(path, params)
        finally:
            client.audit.append(dict(path=path, source='measured_operation', elapsed_seconds=time.perf_counter() - start))
    client.get = measured_get
    sample, _ = review_sample(rows, decisions, ex.DEFAULT_RULES)
    ids = [1300968] + [r['tmdb_id'] for r in history[:3]] + [r['tmdb_id'] for r in sample[::5]][:10]
    ids += [1803126, 1810515]  # The two mismatched English-scope IDs in Phase 1.
    for tmdb_id in dict.fromkeys(ids):
        try:
            detail = client.get(f'/movie/{tmdb_id}')
            ex.write_json(live_dir / f'movie-{tmdb_id}.json', detail)
            row = ex.normalize({'id': tmdb_id}, detail)
            result['movies'].append(row)
        except ex.ApiError as err:
            result['movies'].append(dict(tmdb_id=tmdb_id, error=str(err)))
            if err.stop:
                break
    result['discovery'] = {}
    for scope, language in [('configured', None), ('all', 'all')]:
        print(f'Validating {scope} discovery with a shared primary-date sort', flush=True)
        summaries, coverage = ex.discover(client, '2026-10-26', '2026-11-01', language, 'primary_release_date.asc')
        result['discovery'][scope] = dict(coverage=coverage, rows=summaries)
        # Recheck boundary pages to detect observable drift within this operation.
        rechecks = []
        for page in sorted({1, coverage['expected_pages']}):
            params = dict(page=page, primaryReleaseDateGte='2026-10-26', primaryReleaseDateLte='2026-11-01', sortBy='primary_release_date.asc')
            if language is not None:
                params['language'] = language
            try:
                response = client.get('/discover/movies', params)
                rechecks.append(dict(page=page, total=response.get('totalResults'), ids=[r.get('id') for r in response['results']]))
            except ex.ApiError as err:
                rechecks.append(dict(page=page, error=str(err)))
        result['discovery'][scope]['boundary_rechecks'] = rechecks
    result['requests'] = client.audit
    result['finished_at'] = ex.utcnow()
    ex.write_json(live_dir / 'observations.json', result)
    return result


def language_comparison(rows, all_rows, live):
    ids, all_ids = {r['tmdb_id'] for r in rows}, {r['tmdb_id'] for r in all_rows}
    out = dict(snapshot_configured_only=sorted(ids - all_ids),
               snapshot_all_english_only=sorted(r['tmdb_id'] for r in all_rows if r['original_language'] == 'en' and r['tmdb_id'] not in ids),
               snapshot_all_language_count=len({r['original_language'] for r in all_rows}))
    if live and len(live.get('discovery', {})) == 2:
        scopes = live['discovery']
        a = {r['id'] for r in scopes['configured']['rows']}
        b = {r['id'] for r in scopes['all']['rows']}
        out.update(live_configured_count=len(a), live_all_count=len(b), live_superset=a <= b,
                   live_configured_only=sorted(a - b),
                   live_configured_complete=scopes['configured']['coverage']['complete'],
                   live_all_complete=scopes['all']['coverage']['complete'])
        for name, scope in scopes.items():
            checks = scope.get('boundary_rechecks', [])
            out[f'live_{name}_boundary_rechecks_stable'] = bool(checks) and all(
                check.get('total') == scope['coverage']['reported_total'] and check.get('ids') ==
                [r['id'] for r in scope['rows'][(check['page'] - 1) * 20:check['page'] * 20]] for check in checks)
        out['live_union_count'] = len(a | b)
    return out


def review_markdown(rows, decisions, sample, strata):
    by_id = {r['tmdb_id']: r for r in rows}
    ds = {r['tmdb_id']: r for r in decisions if r['approach'] == 'multi_path'}
    lines = ['# Candidate review: retained and rejected titles', '',
        f"{len(sample)} distinct titles from the immutable 333-title Phase 1 English-scope snapshot. "
        'Sampling uses predefined strata and SHA-256 order with a fixed seed, including all four rejected feature-like films. '
        'It is a coverage-oriented review sample, not a population estimate or a quality judgment. '
        'Synopses are Seerr metadata, not LLM assessments. No title is classified as good or bad.', '',
        'Selection provenance and all overlapping strata eligibility can be reconstructed from `review-sample.json`, '
        '`review-strata.json`, source snapshots and the script. Primary strata are assigned without replacement.', '']
    for included, section in [(True, 'Retained by Phase 1 multi-path'), (False, 'Excluded by Phase 1 multi-path — inspect these carefully')]:
        lines += [f'## {section}', '']
        for item in sample:
            r, d = by_id[item['tmdb_id']], ds[item['tmdb_id']]
            if bool(d['included']) != included:
                continue
            def clean(v):
                return str(v).replace('\n', ' ').replace('|', '\\|')
            year = (r.get('primary_release_date') or '')[:4] or 'year unknown'
            rating = r['vote_average'] if (r['vote_count'] or 0) > 0 else 'unrated (zero/unknown votes)'
            reasons = d['qualifying_paths'] if included else d['hard_exclusions'] + d['soft_exclusion'] + [
                k for k, value in diagnostics(r, ex.DEFAULT_RULES).items() if value and k in (
                    'runtime_missing', 'runtime_below_min', 'synopsis_missing', 'genre_names_missing', 'cast_missing',
                    'crew_missing', 'director_missing', 'completeness_below_min', 'popularity_below_min', 'rating_unsupported')]
            cast = ', '.join(p.get('name', '?') for p in (r['cast'] or [])[:5]) or 'unknown/empty'
            directors = ', '.join(r['directors']) or 'unknown/empty'
            synopsis = clean(r['overview'] or 'Synopsis unavailable.')
            if len(synopsis) > 450:
                synopsis = synopsis[:447].rsplit(' ', 1)[0] + '…'
            lines += [f"### {clean(r['title'])} ({year}) — [TMDB {r['tmdb_id']}](https://www.themoviedb.org/movie/{r['tmdb_id']})", '',
                f"Stratum: `{item['stratum']}`. Discovered in Phase 1 configured scope; multi-path **{d['disposition']}**; proposed tier **{proposed_tier(r)}**.", '',
                f"Language: {r['original_language'] or 'unknown'} · Genres: {', '.join(r['genres']) or 'unknown/empty'} · "
                f"Runtime: {r['runtime'] if r['runtime'] is not None else 'unknown'} min · Popularity: {r['popularity']} · "
                f"Votes: {r['vote_count']} · Rating: {rating} · Completeness: {r['completeness']}/7.", '',
                f"Reasons/observations: {', '.join(reasons) or 'broad eligible'}.", '',
                f"Director(s): {clean(directors)}. Cast (up to five in returned credit order): {clean(cast)}.", '',
                synopsis, '']
    return '\n'.join(lines)


def config():
    return dict(schema_version=1, experimental_only=True, enabled=False,
        hard_exclusions=dict(explicit_adult_policy=True, seerr_blocklist=True,
            verified_duplicate='deduplicate_identity', confirmed_standard_available='hold_existing_workflow',
            confirmed_standard_pending_or_processing='hold_existing_workflow',
            pending_or_approved_standard_request='hold_existing_workflow', unknown_status='retain_for_analysis_verify_before_any_future_request',
            invalid_identity='quarantine_for_repair', released_required=False),
        soft_prioritization=dict(phase1_reference_thresholds=ex.DEFAULT_RULES,
            popularity='continuous_log1p_only_no_gate', ratings='use_only_with_supported_vote_count',
            runtime='descriptive_preference_no_gate', genre='no_global_exclusion', metadata='readiness_and_uncertainty_not_quality'),
        evaluate_now=dict(title_required=True, nonempty_synopsis_required=True, detail_fetch_succeeded=True,
            compatible_vector_and_feature_contract_required_before_actual_scoring=True),
        revisit=dict(missing_metadata_days=7, failed_fetch_retry_hours=24, low_priority_days=14,
            maximum_interval_days=30, on_metadata_change=True, on_admin_override=True,
            maximum_attempts=None, permanent_drop_for_missing_metadata=False, release_date_required=False),
        overrides=dict(tmdb_ids=[], person_ids=[], genres=[], languages=[], action='raise_priority_or_request_human_review',
            bypass_confirmed_duplicates=False, bypass_explicit_blocklist=False),
        audit=dict(preserve_first_seen=True, append_observations=True, retain_all_rule_paths=True,
                   no_target_candidate_count=True, identity_namespace='tmdb:movie:<id>'))


def render_reports(output, rows, all_rows, stats, all_stats, language, live, cache_states, costs, records, cfg):
    table = ex.md_table
    lines = ['# Excluded candidate analysis', '',
        f"All {stats['excluded']} Phase 1 multi-path exclusions among {stats['total']} English-scope titles are in `excluded-candidate-analysis.csv` and `.json`.", '',
        'Counts overlap. These are observations/failures of alternative paths, not independent mandatory gates. '
        'Missing votes, low popularity, short runtime and sparse metadata are not quality judgments.', '']
    lines += table(['Observation', 'Excluded titles'], sorted(stats['overlapping_reasons'].items())) + ['']
    lines += ['## Mutually exclusive classes', ''] + table(['Class', 'Titles'], stats['exclusive_classes'].items()) + ['']
    lines += ['Classification checks for a missing synopsis first, then unknown runtime, then short runtime, then other metadata gaps. '
        'Consequently two of the four runtime>=40 exclusions appear in missing_descriptive_synopsis and two in the feature-like class. '
        'The overlapping runtime totals (135 short, 43 unknown, four >=40) are a different partition from these synopsis-first classes.', '']
    lines += [f"{stats['evaluable_excluded']}/{stats['excluded']} excluded titles have title plus synopsis, the current media embedding input. "
        f"{stats['rich_short_excluded']} rejected titles are metadata-rich but shorter than the Phase 1 runtime threshold. "
        f"Exactly {stats['metadata_ready_feature_excluded']} meet both the metadata and runtime paths yet fail multi-path; "
        'the rule uses OR, so low popularity alone cannot exclude such a title. Four excluded feature-like titles have completeness 4/7, '
        'one below the illustrative cutoff; inspect them individually in the review.', '',
        'The appropriate interpretation is mostly short-form or missing-runtime prioritization plus a smaller metadata-readiness effect. '
        'It is not evidence that these titles lack community demand. A title-only vector is technically constructible, but a missing synopsis '
        'is deferred under the proposed descriptive-evidence guardrail rather than declared unscorable forever.', '']
    excluded_ids = {item['tmdb_id'] for item in records}
    lines += table(['Rejected runtime>=40 title', 'Runtime', 'Completeness', 'Synopsis present', 'Missing components'], [
        [r['title'], r['runtime'], r['completeness'], has_synopsis(r),
         ', '.join(k for k, v in r['completeness_components'].items() if not v)]
        for r in rows if r['tmdb_id'] in excluded_ids and r['runtime'] is not None and r['runtime'] >= cfg['runtime_min']]) + ['']
    ex.write_text(output / 'excluded-candidate-analysis.md', '\n'.join(lines))

    controls_ = (live or {}).get('controls', {})
    references = [r for r in (live or {}).get('movies', []) if r.get('tmdb_id') == 1300968]
    lines = ['# Seerr data validation', '', '## Media and requests', '',
        f"Phase 1 cached field-presence observations: `{json.dumps(cache_states, sort_keys=True)}`. "
        'The original sanitizer retained mediaInfo/status/requests when returned; there is no evidence of a universal status-code extraction failure. '
        'However, the normalized unknown label did not distinguish absent fields, explicit nulls, an existing UNKNOWN-status record, or failed enrichment. '
        'The additive experimental correction now records those distinctions and sanitized service-link/library-identifier presence.', '']
    for r in references:
        lines += [f"Live reference TMDB 1300968: media status **{r.get('media_status_raw')} / {r.get('media_status')}**, "
            f"request statuses **{r.get('request_statuses')}**, external service linked **{r.get('external_service_link_present')}**, "
            f"Seerr library availability **{r.get('standard_library_availability')}**, actual Radarr monitored flag **{r.get('radarr_monitored')}**.", '']
    lines += ['Processing plus approved request establishes a workflow, not library availability. An external Radarr movie association '
        'does not establish monitored=true. No Radarr endpoint was called. A Seerr AVAILABLE code is a report by Seerr, '
        'not an independent fresh Plex inventory check. Null/missing mediaInfo never proves no past request; request deletion, visibility, '
        'permissions or absent data can prevent that conclusion. Existing historical library titles were also used as live controls.', '',
        'Only a stratified subset of weekly titles was refreshed. The cached 333-title field-presence result is a Phase 1 observation, '
        'not a statement about every current Seerr record. New observations and raw sanitized payloads are under `live-validation/`.', '',
        '## Language scope and drift', '', f"Sanitized live settings: `{json.dumps(controls_, sort_keys=True)}`.", '',
        f"Population comparison: `{json.dumps(language, sort_keys=True)}`.", '',
        'In Seerr 3.5.1, API-account originalLanguage overrides main.originalLanguage; streamingRegion can override discoverRegion. '
        'The discovery language query is passed to TMDB with_original_language, so it changes eligibility; all removes that filter. '
        'Metadata localization uses the request locale and server locale fallback and is a separate concern. The raw account value server|en '
        'is forwarded by the inspected route; it is not safe to treat a UI sentinel as an independent valid language. Observed default results are English. '
        'No configuration was changed. [Tagged discovery route](https://github.com/seerr-team/seerr/blob/v3.5.1/server/routes/discover.ts), '
        '[tagged TMDB mapping](https://github.com/seerr-team/seerr/blob/v3.5.1/server/api/themoviedb/index.ts).', '',
        'With identical remaining parameters against an immutable upstream population, removing an original-language constraint should yield a superset. '
        'Live pagination and per-query caches do not provide that immutable population. Phase 2 compares both scopes using primary_release_date.asc '
        'and rechecks boundary pages; matching counts alone cannot prove completeness.', '',
        'The Phase 1 mismatches were TMDB 1803126 (What Remains of Werner Auerbach) and 1810515 (TANDA AIR). '
        'The former was discovered in-range while its detail date was November 30; the latter had an English original-language code but absent detail release date. '
        'Those source-date changes/missingness, different sorts and collection times are evidence for catalog/cache/pagination drift, not evidence that '
        'the all-language parameter intentionally excludes one English title. The precise past upstream mutation cannot be reconstructed. '
        'Fresh detail observations and controlled membership are retained; a passing live superset check is only a check at that observation. '
        'The Phase 2 all-language result actually omits another configured-scope title (Moving Forwards, 1781997), despite using the same sort and '
        'stable boundary rechecks. Prefer an audited union of overlapping observations with discrepancy flags, rather than assuming any single '
        'paged response is a strict superset.', '',
        'The tagged upstream HTTP cache keys include endpoint and query, with a 300-second default TTL. Different language/sort/page queries '
        'can therefore hold observations from different moments; that is a source-supported mechanism, not proof of the exact historical mutation. '
        '[Upstream cache implementation](https://github.com/seerr-team/seerr/blob/v3.5.1/server/api/externalapi.ts). '
        'Movie details attach a permission-filtered media association, so absent associations should be described as not returned, not never requested. '
        '[Movie details route](https://github.com/seerr-team/seerr/blob/v3.5.1/server/routes/movie.ts).', '']
    ex.write_text(output / 'seerr-data-validation.md', '\n'.join(lines))

    lines = ['# Curation strategy comparison', '',
        'All counts below come from the immutable Phase 1 snapshots. Nothing is activated. Existing workflow/policy exclusions produced zero observed '
        'exclusions in those snapshots; unknown workflow states still require future verification.', '']
    lines += table(['Strategy', 'Configured 333', 'All-language 777', 'Recall risk / work'], [
        ['A: aggressive popularity >=5', 10, 16, 'Drops most discovery before personalization; cheapest embedding workload'],
        ['A: metadata + runtime', 90, 237, 'Discards shorts and metadata gaps, including plausible feature-like titles'],
        ['A: Phase 1 multi-path', stats['retained'], all_stats['retained'], 'Alternative paths rescue niche/unfinished titles, but still drops titles with usable embedding text'],
        ['B: broad', stats['total'], all_stats['total'], 'Retains uncertainty; title-only metadata and unvalidated prospective adapter remain problems'],
        ['C: tiered evaluate now', stats['tier_counts'].get('evaluate_now', 0), all_stats['tier_counts'].get('evaluate_now', 0), 'Nonempty title/synopsis and successful detail; no popularity/runtime gate'],
        ['C: tiered revisit', stats['tier_counts'].get('revisit', 0), all_stats['tier_counts'].get('revisit', 0), 'Retained candidates awaiting better descriptive metadata; no permanent discard'],
    ]) + ['']
    lines += ['A offers fewer embeddings but irreversibly removes opportunities before community prediction. Its small retrospective sample '
        'missed seven engaged viewers for BRATS under popularity filtering; it cannot quantify acquisition recall. B makes candidate retention simple '
        'and auditable but invites weak title-only inputs unless readiness is explicit. C keeps the broad pool while making uncertainty and retry work visible. '
        'It adds observation versioning, next-review timestamps and admin-review state; these are design requirements, not implemented records or timers.', '',
        'All three require an isolated prospective adapter: compatible metadata text, cached media embeddings, frozen model vocabulary/order, '
        'existing user/watch profiles, and TMDB identity outside library recommendation tables. Aggressive filtering does not solve feature compatibility. '
        'For 31 current profile rows, broad scoring is only 10,323 or 24,087 title-user pairs. Embedding and retrieval usually dominate the planning budget; '
        'that conclusion remains conditional until isolated target-hardware measurements exist. See the feasibility report for explicit measured/assumed costs.', '',
        '**Recommend C**, initially treating priority as ordering rather than an admission cutoff. Evaluate synopsis-bearing titles, revisit the rest, '
        'and reserve exclusions for explicit policy/blocklist/identity cases; existing workflows are holds, not judgments about interest. '
        'Do not use a target survivor count, votes requirement, hard language preference, or released-yet condition.', '']
    ex.write_text(output / 'curation-strategy-comparison.md', '\n'.join(lines))
    render_feasibility(output, costs)

    lines = ['# Phase 2 findings', '',
        '**Recommend tiered retention, not aggressive popularity/runtime pruning.** Keep all objectively eligible candidates; '
        'evaluate titles with descriptive metadata and revisit incomplete ones. This is an experimental policy only.', '',
        f"The {stats['excluded']} English-scope multi-path exclusions include {stats['evaluable_excluded']} titles with usable title-plus-synopsis text. "
        f"The mutually exclusive breakdown is `{json.dumps(stats['exclusive_classes'], sort_keys=True)}`. "
        f"{stats['metadata_ready_feature_excluded']} metadata-ready feature-like titles were excluded solely for low popularity: "
        'the metadata path would already retain them. Four feature-like exclusions instead have completeness 4/7; '
        'most rejections are short films or missing-runtime titles. These are priority/readiness distinctions, not evidence of poor quality.', '',
        'The live Hunger Games reference validates Processing (3) and Approved (2), while service linkage does not establish actual Radarr monitoring '
        'or library availability. Phase 1 preserved returned codes, but its generic unknown label obscured missing-vs-null-vs-existing-record differences. '
        'The experimental extractor now exposes those distinctions and regression tests cover them. No Phase 1 artifact was rewritten.', '',
        f"Same-sort live validation returned {language.get('live_configured_count', 'unobserved')} configured-scope and "
        f"{language.get('live_all_count', 'unobserved')} all-language titles; strict superset: **{language.get('live_superset', 'unobserved')}**. "
        'The all-language result omitted Moving Forwards (1781997), despite stable boundary rechecks. The account original-language override '
        '(server|en) explains the observed English eligibility scope; metadata localization is separate. Phase 1 also showed a changed detail date '
        'and used different sorts. Per-query caching is a supported mechanism for divergence, but the exact past upstream mutation remains unverified.', '',
        'The inspected local model has 1,605 inputs: 1,536 media/user embedding coordinates, 38 genre flags, 20 director flags, 10 decade flags and watch_sim. '
        'Direct actors, candidate watch counts, runtime, popularity and vote ratings are not features in this artifact. User profiles and watch similarity '
        'are behavioral inputs that can predate acquisition; the prospective title does not need its own watch history. The model is not a calibrated '
        'community-acquisition predictor, and current library selection and mixed movie/episode training limit transfer. '
        '**Important leakage channel:** training watch_sim uses an all-watch profile that can include the target film’s own qualifying watch event. '
        'The local model uses watch_sim in 14 splits. This channel is separate from the title-profile leave-one-out guard and must be assessed '
        'in a leakage-safe offline study; its effect on predictions was not measured.', '',
        '31 current profile rows imply 10,323/24,087 pairs for 333/777 titles. Retrieval is measured on bounded validation calls; '
        'embedding and XGBoost runtime are explicitly unmeasured assumptions, with ranges and memory/operation counts in the feasibility report. '
        'The current library-only scoring loader, missingness semantics, frozen vocabulary and embedding-version contract must be addressed in an isolated '
        'prospective experiment before any automation. No production embedding/scoring job or model inference was executed.', '',
        f"Proposed tiers: configured **{stats['tier_counts'].get('evaluate_now', 0)} evaluate / {stats['tier_counts'].get('revisit', 0)} revisit**; "
        f"all languages **{all_stats['tier_counts'].get('evaluate_now', 0)} evaluate / {all_stats['tier_counts'].get('revisit', 0)} revisit**. "
        'The standalone configuration sets enabled=false. Revisit missing metadata in 7 days, transient failures after 24 hours, '
        'and low-priority candidates within 14 days (30-day maximum interval); these are initial configurable operational assumptions, '
        'not learned thresholds or enabled schedules. No release date automatically disqualifies a title.', '',
        'Next step: inspect the 50-title retained/excluded review, then design a separate offline prospective feature-parity and calibration experiment. '
        'Measure embeddings on target hardware before deciding whether fewer candidates are necessary. Keep future-request status verification separate '
        'from engagement curation and do not treat unwatched/unacquired titles as negative examples.', '',
        '## Deliverables and evidence', '',
        '- `seerr-data-validation.md` and `live-validation/`: fresh GET-only reference/settings/same-sort discovery checks.',
        '- `excluded-candidate-analysis.csv/.json/.md`: all 182 snapshot exclusions with overlapping observations, failed paths and exclusive classes.',
        '- `candidate-review.md`, `review-sample.json`, `review-strata.json`: 50 deterministic representative titles with TMDB links, synopses and credits.',
        '- `curation-strategy-comparison.md`: candidate retention, overhead, bias, architecture and audit tradeoffs.',
        '- `prospective-scoring-feasibility.md`, `cost-estimates.json`: source/model inspection, measured local microbenchmarks and explicit planning assumptions.',
        '- `experimental-curation.json`: inactive hard/soft/revisit/override proposal.',
        '- `input-integrity.json`, `manifest.json`: immutable inputs/protected files and output hashes.', '',
        'Snapshot-only sections reuse Phase 1 inputs without refreshing membership. Live claims are limited to timestamped validation observations. '
        'Source citations are in the data-validation and feasibility reports. Current profile counts are aggregate-only; no user identity is exported.', '']
    ex.write_text(output / 'phase2-findings.md', '\n'.join(lines))


def render_feasibility(output, costs):
    lines = ['# Prospective scoring feasibility', '',
        'This is source and model-metadata inspection, aggregate database reads, and synthetic feature/matrix microbenchmarks. '
        'No production scoring module was imported, no model predict method was called, no embedding request was issued, and no training ran.', '',
        '## Actual representation and feature contract', '',
        '`fetch_tautulli_data.py:_media_text_for_embedding` formats **title — summary**. `generate_media_embeddings` sends those texts through '
        '`ollama_embeddings.embed_texts` to Ollama embeddinggemma in configured batches of 128, keep-alive 15 minutes, 16 configured threads, '
        'and 300-second timeout. It stores 768-dimensional vectors keyed by Plex rating_key. Those production functions write records and were not run. '
        'Seerr title/overview can construct the same string; adding cast, genres or release dates to that text would change the representation. '
        'Matching dimensions is necessary but does not verify matching model revision, tokenizer, truncation, normalization or metadata semantics. '
        'Existing vectors do not themselves establish which exact embedding model revision produced them.', '',
        'User profiles average eligible title vectors (maximum engagement > configured threshold OR at least five watches), deduplicated by title. '
        'Training uses leave-one-title-out profiles. The separate watch profile averages enriched watch-event embeddings, whose text includes metadata '
        'and playback/engagement context. A prospective film needs no synthetic watch event: compare its media vector to existing pre-cutoff user/watch profiles. '
        'If those profiles are absent or incompatible, defer or explicitly evaluate a cold-start policy; do not fabricate user evidence.', '',
        'The local xgb_model.pkl was loaded only for metadata inspection. It contains **1,605 named inputs and 100 trees (depth at most 6)**: '
        '768 media coordinates then 768 user coordinates; 38 genre indicators; 20 director indicators; 10 decade indicators; one watch_sim. '
        'There are no direct actor inputs in this artifact. Behavioral columns in training_data such as engagement ratio, watch count, '
        'played duration, labels and sample weights are not all fed to XGBoost. Seerr runtime/popularity/votes/cast can inform curation '
        'but must not be invented as features. Full feature names, artifact hash and topology are in `model-inspection.json`.', '',
        'Snapshot vocabulary coverage: all 272/333 and 657/777 titles with genre names match at least one trained genre flag. '
        'Despite 299/333 and 707/777 titles having director credits, **zero candidate directors match any of the 20 trained director flags**. '
        'Those flags would all be zero; with no actor features and title/synopsis-only media text, rich cast/crew data is not automatically used by this model. '
        'This is a concrete limit of the current representation, not a reason to reject those films. See cost-estimates.json vocabulary_coverage.', '',
        '| Input | Prospective source | Safe handling / gap |',
        '| --- | --- | --- |',
        '| Media emb_0..767 | Seerr title/overview → same frozen embedding model/text | Vector must be finite, nonzero, correct dimension and compatible revision; missing synopsis revisits |',
        '| User emb_768..1535 | Existing pre-acquisition user profile | Not provided by Seerr; requires eligible profile and common embedding contract |',
        '| 38 genre flags | Seerr genres mapped to frozen trained vocabulary | TMDB/Plex names can differ; missing fields must not silently assert absent genres |',
        '| 20 director flags | Seerr credits job=Director, exact trained names | Missing credits and unknown names are distinct; new directors fall outside vocabulary |',
        '| 10 decade flags | Reliable release year from separate observations | Missing/conflicting year is uncertainty; never a release-readiness gate |',
        '| watch_sim | Candidate media vector vs existing watch profile | Available without candidate plays; trained fallback is zero, which conflates no profile with zero similarity |', '',
        '## Serving and leakage concerns', '',
        '`score_model.py:get_unwatched_media` only joins library/media_embeddings/user_embeddings using rating_key and consults feedback/watch history. '
        'It cannot load a TMDB-only title. Its CLI calls ensure_app_schema and its orchestration writes recommendations/SHAP state. '
        'Importing the module resolves multiple app settings through database reads; it is not a pure feature utility. '
        'A future adapter must use a separate TMDB namespace and isolated outputs, preserve model feature names/order, and require parity checks '
        'instead of relying on positional padding/trimming. Missing categorical metadata currently becomes all-zero flags; the model has no '
        'dedicated unknown indicators. Numerical zero-fill cannot repair a missing media/user vector. None of these concerns is changed here.', '',
        'The model learns individual engagement within a selected library, using movies and episodes and weighted/class-balanced labels. '
        'Summing per-user probabilities is an unvalidated expected-count proxy, not a calibrated community demand forecast. '
        'Profiles, watch embeddings, feedback and candidate metadata must be frozen before each evaluated discovery time. '
        'Leave-one-title-out avoids one self-inclusion channel, but it does not protect watch_sim: '
        '`build_training_data.py:build_user_watch_vectors` averages all qualifying watch events once, then process_row uses that profile for every target. '
        'Thus a watched training title can contribute its own post-engagement event to its watch_sim feature. There is no target-title removal or time cutoff '
        'in that path. The inspected model uses watch_sim in 14 splits (gain about 42.47); prediction impact was not measured. '
        'A future prospective title has no such self-event, creating a training/serving difference. '
        'No training rows were replayed, so the magnitude and exact artifact training history remain unverified. '
        'A random row split and present-day metadata/profiles also do not establish a temporal holdout. '
        'Unacquired and unwatched titles are unobserved, not automatic negatives. Comparable availability/exposure windows, cold-start handling '
        'and movie-specific prospective calibration remain necessary.', '',
        '## Cost evidence and planning estimates', '',
        f"Evidence/assumptions: `{json.dumps(costs.get('assumptions', {}), sort_keys=True)}`.", '',
        'The live HTTP timing sample includes Seerr/server-cache behavior; it does not benchmark a cold TMDB crawl. '
        'Local benchmarks construct synthetic float32 arrays and cosine matrices only. They exclude database IO, pandas preprocessing, '
        'Ollama tokenization/inference, XGBoost inference, SHAP and persistence. No current candidates were scored.', '']
    lines += ex.md_table(['Stage / scope', '333 titles', '777 titles', 'Evidence'], costs.get('table', [])) + ['']
    lines += ['Embedding throughput assumptions of 1–20 short texts/second span planning scenarios, not measured target-hardware performance. '
        'No monetary price is asserted for local compute; hardware, token length, model cold start, contention and retries determine real cost. '
        'No additional external enrichment is required to produce the current media text, but repairing names/genres/overview gaps would add calls '
        'and an audit trail. Reuse one title embedding across all users; do not generate 31 embeddings per title. '
        'Batch profiles/watch vectors once, cache candidate text hashes plus model version, and chunk title-user features rather than materialize '
        'the entire community matrix. These are design recommendations, not implemented production logic.', '',
        'Worst-case routing work is 100×6 comparisons per pair (approximately 6.2M/14.5M for 31 profiles). '
        'Conditional inference estimates use a deliberately broad 1,000–100,000 pairs/second assumption. '
        'Inference is computationally plausible at these sizes; semantic compatibility and calibration are the larger blockers. '
        'If production explanation generation were copied, SHAP, metadata/context queries and writes could dominate; '
        'they are unnecessary for an initial offline acquisition feasibility measurement and were not benchmarked.', '',
        'Local source references: `fetch_tautulli_data.py` (_media_text_for_embedding, generate_media_embeddings, _watch_text_for_embedding), '
        '`ollama_embeddings.py` (_post_embed, embed_texts), `user_profile_embeddings.py` (build_user_profiles, leave_one_title_out), '
        '`build_training_data.py` (build_training_row), `train_model.py` (preprocess, train_and_evaluate), '
        '`score_model.py` (get_unwatched_media, preprocess_for_scoring, score_and_store). '
        'File hashes are recorded so this assessment can be tied to the inspected source revision.', '']
    ex.write_text(output / 'prospective-scoring-feasibility.md', '\n'.join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--credentials-file', type=Path, default=ROOT / '.seer_creds')
    parser.add_argument('--live', action='store_true', help='Collect only allowlisted GET validation into a new subdirectory')
    args = parser.parse_args(argv)
    output_path = args.output.resolve()
    protected = [(BASE / p).resolve() for p in ('cache', '2026-10-28-week', '2026-10-28-all-languages', '2026-10-28-week-mixed-pages')]
    if BASE.resolve() not in output_path.parents or any(p == output_path or p in output_path.parents for p in protected):
        parser.error('Phase 1 paths are immutable inputs')
    ex.private_dir(args.output)
    integrity = args.output / 'input-integrity.json'
    current = input_fingerprints()
    checks = read_json(integrity) if integrity.exists() else current
    if checks != current:
        raise ValueError('Protected source or Phase 1 inputs changed before analysis')
    if not integrity.exists():
        ex.write_json(integrity, checks)
    source = BASE / '2026-10-28-week'
    rows, decisions = read_json(source / 'candidates.json'), read_json(source / 'decisions.json')
    cfg = read_json(source / 'manifest.json')['rules']
    all_source = BASE / '2026-10-28-all-languages'
    all_rows, all_decisions = read_json(all_source / 'candidates.json'), read_json(all_source / 'decisions.json')
    records, stats = analyze(rows, decisions, cfg)
    _, all_stats = analyze(all_rows, all_decisions, cfg)
    sample, strata = review_sample(rows, decisions, cfg)
    live_file = args.output / 'live-validation/observations.json'
    live = collect_live(args.output, args.credentials_file, rows, decisions, read_json(source / 'history_candidates.json')) if args.live else read_json(live_file) if live_file.exists() else None
    if live:
        status_rows = []
        for observed in live.get('movies', []):
            detail_file = args.output / f"live-validation/movie-{observed['tmdb_id']}.json"
            if detail_file.exists():
                status_rows.append(ex.normalize({'id': observed['tmdb_id']}, read_json(detail_file)))
        ex.write_json(args.output / 'status-validation.json', dict(source='captured_live_sanitized_details',
            observation_started_at=live['started_at'], rows=status_rows))
    cached = old_cache_details(BASE / 'cache')
    states = Counter(ex.media_observation(cached[r['tmdb_id']]['data'])['media_info_field_state']
                     if r['tmdb_id'] in cached else 'cache_missing' for r in rows)
    language = language_comparison(rows, all_rows, live)
    costs_file = args.output / 'cost-estimates.json'
    costs = read_json(costs_file) if costs_file.exists() else dict(assumptions={'status': 'benchmarks_not_collected'}, table=[])
    ex.write_csv(args.output / 'excluded-candidate-analysis.csv', records)
    ex.write_json(args.output / 'excluded-candidate-analysis.json', records)
    ex.write_json(args.output / 'exclusion-distributions.json', dict(configured=stats, all_languages=all_stats))
    ex.write_json(args.output / 'review-sample.json', sample)
    ex.write_json(args.output / 'review-strata.json', dict(seed=SEED, strata=strata))
    ex.write_json(args.output / 'language-comparison.json', language)
    ex.write_json(args.output / 'experimental-curation.json', config())
    ex.write_json(args.output / 'source-inspection.json', source_inspection())
    ex.write_text(args.output / 'candidate-review.md', review_markdown(rows, decisions, sample, strata))
    render_reports(args.output, rows, all_rows, stats, all_stats, language, live, dict(states), costs, records, cfg)
    if checks != input_fingerprints():
        raise ValueError('A protected source or Phase 1 input changed; inspect integrity evidence')
    manifest = dict(finished_at=ex.utcnow(), live_validation_available=live is not None,
        input_integrity_verified=bool(checks), snapshot_english_titles=len(rows), snapshot_all_titles=len(all_rows),
        exclusions=len(records), review_sample=len(sample), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        extractor_sha256=hashlib.sha256(Path(ex.__file__).read_bytes()).hexdigest(),
        outputs_sha256={str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(args.output.rglob('*')) if p.is_file() and p.name != 'manifest.json'})
    ex.write_json(args.output / 'manifest.json', manifest)
    print(json.dumps(dict(output=str(args.output), excluded=len(records), review_sample=len(sample),
                          tier_counts=stats['tier_counts'], immutable_inputs_verified=bool(checks))))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError):
        print('Phase 2 analysis failed: inspect input formats, immutable paths and sanitized evidence.', file=ex.sys.stderr)
        raise SystemExit(1)
