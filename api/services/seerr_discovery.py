"""Discovery membership and enrichment orchestration; no curation or acquisition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from api.db.seerr_discovery import database_error_code, digest, combine_counts, COUNT_FIELDS
from api.services.seerr_client import SeerrError, sanitize_movie, sanitize_tv, valid_tmdb_id, validate_media_type, parse_iso_date, tv_eligibility


@dataclass(frozen=True)
class DiscoveryScope:
    name: str
    start: date
    end: date
    language: str = 'all'
    sort_by: str = 'primary_release_date.asc'
    media_type: str = 'movie'

    def __post_init__(self):
        validate_media_type(self.media_type)
        if self.media_type == 'tv':
            object.__setattr__(self, 'sort_by', self.sort_by.replace('primary_release_date.', 'first_air_date.'))
        else:
            object.__setattr__(self, 'sort_by', self.sort_by.replace('first_air_date.', 'primary_release_date.'))
        import re
        if (type(self.start) is not date or type(self.end) is not date or self.start > self.end
                or not re.fullmatch(r'[A-Za-z0-9_.|-]{1,100}', self.name)
                or not re.fullmatch(r'(all|configured|[a-z]{2,3}(?:\|[a-z]{2,3})*)', self.language)
                or self.sort_by not in ('primary_release_date.asc', 'primary_release_date.desc', 'first_air_date.asc', 'first_air_date.desc', 'popularity.desc', 'vote_count.desc')):
            raise SeerrError('invalid_discovery_scope')

    @property
    def parameters(self):
        prefix = 'primaryReleaseDate' if self.media_type == 'movie' else 'firstAirDate'
        result = {prefix+'Gte': self.start.isoformat(), prefix+'Lte': self.end.isoformat(), 'sortBy': self.sort_by}
        if self.language != 'configured':
            result['language'] = self.language
        return result

    @property
    def key(self):
        return digest(dict(name=self.name, media_type=self.media_type, parameters=self.parameters))


def build_scopes(config, *, start=None, end=None, anchor=None):
    anchor = anchor or datetime.now(timezone.utc).date()
    start = start or anchor - timedelta(days=config.lookback_days)
    end = end or anchor + timedelta(days=config.lookahead_days)
    if start > end:
        raise SeerrError('invalid_date_window')
    result = []
    current = start
    while current <= end:
        last = min(end, current + timedelta(days=config.window_days - 1))
        for media_type in config.media_types:
            for language in config.languages:
                result.append(DiscoveryScope(language, current, last, language, config.sort_by, media_type))
                if len(result) > config.max_requests:
                    raise SeerrError('scope_count_exceeds_request_budget')
        current = last + timedelta(days=1)
    return result


def collect_scope(client, scope, max_pages, observe):
    """Stream durable page membership via observe; diagnostics never imply deletion."""
    metrics = dict(scope_key=scope.key, scope_name=scope.name, media_type=scope.media_type, parameters=scope.parameters,
        expected_pages=None, reported_total=None, pages=[], duplicate_rows=0, invalid_rows=0,
        raw_rows=0, unique_results=0, unique_titles=0, unique_movies=0, excluded=[], unresolved=[], eligibility_complete=True, errors=[], complete=False)
    seen = set()
    page, expected = 1, 1
    stop = False
    while page <= min(expected, max_pages):
        try:
            raw = (client.discover if scope.media_type == 'movie' else client.discover_tv)({**scope.parameters, 'page': page})
            pages, total = raw.get('totalPages'), raw.get('totalResults')
            if (type(raw.get('page')) is not int or raw['page'] != page or type(pages) is not int
                    or pages < 0 or type(total) is not int or total < 0 or not isinstance(raw.get('results'), list)
                    or pages == 0 and total != 0):
                raise SeerrError('invalid_pagination')
            if page == 1:
                metrics['expected_pages'], metrics['reported_total'] = pages, total
                expected = max(1, pages)
            elif pages != metrics['expected_pages'] or total != metrics['reported_total']:
                metrics['errors'].append(dict(page=page, code='pagination_totals_changed'))
                expected = max(expected, pages)
            rows = []
            metrics['raw_rows'] += len(raw['results'])
            for payload in raw['results']:
                if (not isinstance(payload, dict) or not valid_tmdb_id(payload.get('id'))
                        or payload.get('mediaType', scope.media_type) != scope.media_type):
                    metrics['invalid_rows'] += 1
                    continue
                if payload['id'] in seen:
                    metrics['duplicate_rows'] += 1
                    continue
                seen.add(payload['id'])
                clean = (sanitize_movie if scope.media_type == 'movie' else sanitize_tv)(payload)
                clean['_page'] = page
                if scope.media_type == 'tv':
                    assessment = tv_eligibility(clean, scope.parameters)
                    if assessment['state'] == 'excluded':
                        metrics['excluded'].append(dict(media_type='tv',tmdb_id=clean['id'],**assessment))
                        continue
                    if assessment['reason'] == 'original_premiere_unknown':
                        metrics['unresolved'].append(dict(media_type='tv',tmdb_id=clean['id'],**assessment))
                        metrics['eligibility_complete'] = False
                rows.append(clean)
                metrics['unique_titles'] += 1
            observe(rows)
            metrics['pages'].append(dict(page=page, reported_pages=pages, reported_total=total,
                                         raw_rows=len(raw['results']), accepted_rows=len(rows)))
        except SeerrError as err:
            metrics['errors'].append(dict(page=page, code=err.code))
            if page == 1 or err.stop:
                stop = err.stop
                break
        page += 1
    metrics['unique_results'] = len(seen)
    metrics['unique_movies'] = metrics['unique_titles'] if scope.media_type == 'movie' else 0
    if expected > max_pages:
        metrics['errors'].append(dict(code='page_limit_exceeded'))
    metrics['complete'] = (not metrics['errors'] and metrics['invalid_rows'] == 0 and metrics['duplicate_rows'] == 0
        and len(metrics['pages']) == max(1, metrics['expected_pages'] or 0)
        and metrics['unique_results'] == metrics['reported_total'])
    return metrics, stop


def cache_action(movie, config, now, force):
    if not movie or force or not config.cache_enabled:
        return 'fetch'
    if movie['enrichment_status'] == 'failed':
        attempt = movie.get('last_enrichment_attempt_at')
        return 'defer' if attempt and now - attempt < timedelta(hours=config.failed_retry_hours) else 'fetch'
    enriched = movie.get('last_enriched_at')
    if (movie.get('metadata_source_key') == config.source_key and enriched and
            timedelta(0) <= now - enriched < timedelta(hours=config.metadata_ttl_hours)):
        return 'cached'
    return 'fetch'


def sync_discovery(client, config, scopes, *, repository=None, dry_run=True, refresh=False,
                   enrich_due=False, clock=None, log=None):
    """An explicit caller owns/creates the connection; dry-run never accesses it."""
    source_clock = clock or (lambda: datetime.now(timezone.utc))
    def now():
        value = source_clock()
        if value.tzinfo is None:
            raise SeerrError('aware_utc_clock_required')
        return value.astimezone(timezone.utc)
    emit = log or (lambda event: None)
    if not dry_run and not config.enabled:
        raise SeerrError('discovery_disabled')
    if not dry_run:
        config.require_source_identity()
    if not dry_run and repository is None:
        raise SeerrError('persistence_connection_required')
    if dry_run and enrich_due:
        raise SeerrError('dry_run_inventory_refresh_requires_readonly_summary')
    if not scopes and not enrich_due:
        raise SeerrError('at_least_one_scope_required')
    repo = None if dry_run else repository
    run_id = str(uuid4())
    operation = 'enrich' if enrich_due else 'discover'
    parameters = dict(operation=operation, source_key=config.source_key, source_id=config.source_id,
        media_types=list(config.media_types) if enrich_due else sorted({s.media_type for s in scopes}),
        scopes=[dict(name=s.name, scope_key=s.key, media_type=s.media_type, language=s.language, query=s.parameters) for s in scopes],
        metadata_ttl_hours=config.metadata_ttl_hours, failed_retry_hours=config.failed_retry_hours,
        cache_enabled=config.cache_enabled, force_refresh=refresh, max_pages=config.max_pages,
        retries=config.retries, max_requests=config.max_requests, timeout=config.timeout,
        interval=config.interval, refresh_batch_size=config.refresh_batch_size)
    metrics, errors, warnings = [], [], ['live_pagination_is_not_an_atomic_snapshot',
        'upstream_region_and_account_settings_can_change_scope']
    seen = {}
    outcomes = dict(success=0, cached=0, failed=0, deferred=0, pending=0)
    typed_outcomes = {t: dict(outcomes) for t in ('movie', 'tv')}
    assessments = {}
    summary_evidence = {}
    def outcome(media_type, state):
        outcomes[state] += 1
        typed_outcomes[media_type][state] += 1
    def assess(media_type, tmdb_id, payload, detail=False):
        if media_type == 'tv':
            for scope in scopes:
                if scope.media_type == 'tv' and (media_type, tmdb_id, scope.key) in assessments:
                    key = (media_type, tmdb_id, scope.key)
                    assessments[key] = tv_eligibility(payload, scope.parameters, detail=detail, discovery=summary_evidence.get(key))
    result = dict(run_id=run_id, dry_run=dry_run, operation=operation, status='failed')
    started = False
    collection_stop = None
    requests_before = getattr(client, 'requests', 0)
    retries_before = getattr(client, 'retry_count', 0)
    if repo and not repo.acquire():
        raise SeerrError('discovery_already_running', stop=True)
    try:
        if repo:
            repo.start(run_id, now(), operation, config.source_key, parameters)
            started = True
        emit(dict(event='seerr_discovery_started', run_id=run_id, dry_run=dry_run, operation=operation, scope_count=len(scopes)))
        if enrich_due:
            for movie in repo.due(config, now(), force=refresh):
                payload = movie['source_metadata'].get('discovery') or {'id': movie['tmdb_id']}
                media_type = movie['media_type']
                seen[(media_type, movie['tmdb_id'])] = payload
                repo.discover_page(run_id, 'inventory_refresh', 'inventory_refresh', {'operation': 'enrich'}, [payload], now(), kind='refresh', media_type=media_type)
        else:
            for scope in scopes:
                def observe(rows):
                    if repo:
                        repo.discover_page(run_id, scope.key, scope.name, scope.parameters, rows, now(), media_type=scope.media_type)
                    for row in rows:
                        seen.setdefault((scope.media_type, row['id']), row)
                        if scope.media_type == 'tv':
                            key = ('tv', row['id'], scope.key)
                            summary_evidence[key] = row
                            assessments[key] = tv_eligibility(row, scope.parameters)
                coverage, stop = collect_scope(client, scope, config.max_pages, observe)
                metrics.append(coverage)
                emit(dict(event='seerr_scope_collected', run_id=run_id, scope_key=scope.key,
                          media_type=scope.media_type, titles=coverage['unique_titles'], complete=coverage['complete']))
                if stop:
                    collection_stop = coverage['errors'][-1]['code']
                    break
        stopped = collection_stop
        for index, (media_type, tmdb_id) in enumerate(seen, 1):
            if index % 50 == 0:
                emit(dict(event='seerr_enrichment_progress', run_id=run_id, processed=index-1, total=len(seen), outcomes=dict(outcomes)))
            if stopped:
                outcome(media_type, 'deferred')
                if repo:
                    repo.defer(run_id, tmdb_id, stopped, media_type)
                continue
            movie = repo.get(tmdb_id, media_type) if repo else None
            action = cache_action(movie, config, now(), refresh)
            if action in ('cached', 'defer'):
                outcome(media_type, 'cached' if action == 'cached' else 'deferred')
                if repo:
                    repo.reuse(run_id, movie, deferred=action == 'defer')
                    prior = movie['source_metadata'].get('detail')
                    if prior is not None:
                        assess(media_type, tmdb_id, prior, detail=True)
                continue
            try:
                detail = (client.movie if media_type == 'movie' else client.tv)(tmdb_id)
                assess(media_type, tmdb_id, detail, detail=True)
                if repo:
                    repo.enriched(run_id, tmdb_id, detail, now(), config.source_key, media_type)
                outcome(media_type, 'success')
            except SeerrError as err:
                budget_stop = err.code == 'request_budget_exhausted'
                outcome(media_type, 'deferred' if budget_stop else 'failed')
                errors.append(dict(media_type=media_type, tmdb_id=tmdb_id, stage='enrichment', code=err.code))
                if repo:
                    if budget_stop:
                        repo.defer(run_id, tmdb_id, err.code, media_type)
                    else:
                        repo.enrichment_failed(run_id, tmdb_id, now(), err.code, media_type)
                if err.stop:
                    stopped = err.code
        for metric in metrics:
            if metric['media_type'] == 'tv':
                metric['eligibility_complete'] = all(v['state'] != 'provisional'
                    for (kind, _, key), v in assessments.items() if kind == 'tv' and key == metric['scope_key'])
        discovery_complete = enrich_due or len(metrics) == len(scopes) and all(m['complete'] for m in metrics)
        enrichment_complete = outcomes['failed'] == 0 and outcomes['deferred'] == 0
        if repo:
            counts = repo.counts(run_id)
        else:
            rows = []
            for media_type in ('movie', 'tv'):
                row = dict.fromkeys(COUNT_FIELDS, 0)
                row.update(media_type=media_type, titles=sum(t == media_type for t, _ in seen))
                row.update({'enrichment_' + k: v for k, v in typed_outcomes[media_type].items()})
                for t, ident in seen:
                    if t != media_type:
                        continue
                    states = {v['state'] for (kind,i,_),v in assessments.items() if kind == t and i == ident}
                    if states:
                        state = 'eligible' if 'eligible' in states else 'provisional' if 'provisional' in states else 'excluded'
                        row[state] += 1
                rows.append(row)
            counts = combine_counts(rows)
            for k in ('new_titles','existing_titles','updated_titles','new_movies','existing_movies','updated_movies'):
                counts[k] = None
        counts.update(http_requests=getattr(client, 'requests', 0) - requests_before,
                      http_retries=getattr(client, 'retry_count', 0) - retries_before)
        status = 'success' if discovery_complete and enrichment_complete else 'partial' if counts['titles'] else 'failed'
        if repo:
            repo.finish(run_id, now(), status, metrics, counts, discovery_complete, enrichment_complete, errors, warnings)
        result.update(status=status, counts=counts, discovery_complete=discovery_complete,
                      enrichment_complete=enrichment_complete, pagination=metrics, errors=errors, warnings=warnings,
                      tv_assessments=[dict(media_type=t,tmdb_id=i,scope_key=k,**v) for (t,i,k),v in assessments.items()])
        emit(dict(event='seerr_discovery_finished', run_id=run_id, status=status, counts=counts))
        return result
    except Exception as err:
        # No SQL diagnostics, response text, URL or secret values leave the service.
        code = err.code if isinstance(err, SeerrError) else database_error_code(err)
        if repo and started:
            try:
                repo.conn.rollback()
                counts = repo.counts(run_id)
                status = 'partial' if counts['titles'] else 'failed'
                repo.finish(run_id, now(), status, metrics, counts, False, False, [{'code': code}], warnings)
                result.update(status=status, counts=counts)
            except Exception:
                result['warnings'] = ['run_remains_running_until_recovery_if_database_unavailable']
        result.update(errors=[{'code': code}], discovery_complete=False, enrichment_complete=False)
        emit(dict(event='seerr_discovery_failed', run_id=run_id, status=result['status'], code=code))
        return result
    finally:
        if repo:
            try:
                repo.release()
            except Exception:
                # Closing the caller-owned connection also releases a session advisory lock.
                repo.conn.close()
