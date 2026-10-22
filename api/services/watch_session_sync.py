"""Raw observations only. This module never INSERTs or UPDATEs watch_history."""
from datetime import datetime, timedelta, timezone
import json
import os
from collections import Counter
import time

from api.services.watch_history_sync import (
    PLAYBACK_FIELDS, HistoryPaginationError, group_members, integer, iter_history_pages, map_history, text, utc,
)

SESSION_COLUMNS = (
    "source_event_id", "source_reference_id", "source_user_id", "username",
    "friendly_name", "rating_key", "media_type", "title", "watched_at",
    "started_at", "stopped_at", "played_duration", "percent_complete",
) + PLAYBACK_FIELDS + ("ip_suppressed_at",)
IDENTITY = {"source_event_id", "username", "rating_key"}


def timestamp(value):
    value = integer(value)
    try:
        return datetime.fromtimestamp(value, timezone.utc) if value and value > 0 else None
    except (OverflowError, OSError, ValueError):
        return None


def map_session(row):
    mapped = map_history(row)
    if mapped is None:
        return None
    values, supplied = mapped
    # Reject grouped payloads even if they arrive through a misconfigured caller.
    if group_members(row) != [values["watch_id"]]:
        raise ValueError("Raw-session persistence requires a single ungrouped source event")
    result = {c: values.get(c) for c in SESSION_COLUMNS}
    result.update(
        source_event_id=values["watch_id"],
        source_reference_id=integer(row.get("reference_id")),
        source_user_id=integer(row.get("user_id")),
        title=text(row.get("title")),
        watched_at=values["watched_at"].replace(tzinfo=timezone.utc) if values["watched_at"] else None,
        started_at=timestamp(row.get("started")), stopped_at=timestamp(row.get("stopped")),
    )
    return result, supplied


class SessionWriterPermissionError(RuntimeError):
    pass


class SessionPolicyError(RuntimeError):
    pass


def require_session_writer(cursor):
    cursor.execute("""
        SELECT r.rolsuper OR r.rolcreaterole OR r.rolbypassrls
          OR has_table_privilege(current_user, 'public.watch_history', 'INSERT,UPDATE,DELETE,TRUNCATE')
          OR has_any_column_privilege(current_user, 'public.watch_history', 'INSERT,UPDATE')
          OR pg_has_role(current_user, c.relowner, 'MEMBER')
        FROM pg_roles r CROSS JOIN pg_class c
        WHERE r.rolname = current_user AND c.oid = 'public.watch_history'::regclass
    """)
    if cursor.fetchone()[0]:
        raise SessionWriterPermissionError("Session ingestion requires a non-privileged role without model-history write access")


def purge_expired_ips(cursor):
    cursor.execute("""
        UPDATE public.watch_sessions s
        SET ip_address = NULL, ip_suppressed_at = COALESCE(s.ip_suppressed_at, statement_timestamp())
        FROM public.watch_session_policy p
        WHERE p.singleton AND s.ip_address IS NOT NULL AND (
            p.ip_retention_days = 0 OR s.started_at IS NULL
            OR s.started_at > statement_timestamp()
            OR s.started_at < statement_timestamp() - make_interval(days => p.ip_retention_days))
    """)
    return cursor.rowcount


def persist_sessions(cursor, rows, *, dry_run=False, reasons=None):
    reasons = reasons if reasons is not None else Counter()
    stats = dict(inserted=0, updated=0, unchanged=0, skipped=0, failed=0)
    for row in rows:
        mapped = map_session(row)
        if mapped is None:
            stats["skipped"] += 1
            reasons["missing_source_or_media_identity"] += 1
            continue
        values, supplied = mapped
        cursor.execute("SAVEPOINT raw_session")
        try:
            if dry_run:
                cursor.execute("SELECT " + ", ".join(SESSION_COLUMNS) + " FROM public.watch_sessions WHERE source_event_id=%s", (values["source_event_id"],))
                old_row = cursor.fetchone()
                old = dict(zip(SESSION_COLUMNS, old_row)) if old_row else None
                cursor.execute("SELECT ip_retention_days, statement_timestamp() FROM public.watch_session_policy WHERE singleton")
                days, now = cursor.fetchone()
                candidate = dict(values)
                if old:
                    for c in SESSION_COLUMNS:
                        if c not in supplied and candidate[c] is None:
                            candidate[c] = old[c]
                    dates = [d for d in (old['started_at'], values['started_at']) if d is not None]
                    candidate['started_at'] = min(dates) if dates else None
                    candidate['ip_suppressed_at'] = old['ip_suppressed_at']
                start = candidate['started_at']
                if (not days or start is None or start > now or start < now - timedelta(days=days)
                        or candidate['ip_suppressed_at'] is not None
                        or (old and old['ip_address'] is not None and 'ip_address' in supplied and values['ip_address'] is None)):
                    candidate['ip_address'] = None
                    candidate['ip_suppressed_at'] = candidate['ip_suppressed_at'] or now
                if old is None:
                    outcome = 'inserted'
                elif any(old[c] != values[c] for c in IDENTITY):
                    outcome = 'skipped'
                else:
                    outcome = 'updated' if any(old[c] != candidate[c] for c in SESSION_COLUMNS) else 'unchanged'
            else:
                expressions = {
                    c: f"EXCLUDED.{c}" if c in supplied else f"COALESCE(EXCLUDED.{c}, watch_sessions.{c})"
                    for c in SESSION_COLUMNS if c not in IDENTITY
                }
                expressions['started_at'] = 'LEAST(watch_sessions.started_at, EXCLUDED.started_at)'
                expressions['ip_suppressed_at'] = 'COALESCE(watch_sessions.ip_suppressed_at, EXCLUDED.ip_suppressed_at)'
                expressions['ip_address'] = (
                    'CASE WHEN COALESCE(watch_sessions.ip_suppressed_at, EXCLUDED.ip_suppressed_at) IS NOT NULL '
                    'THEN NULL ELSE ' + expressions['ip_address'] + ' END'
                )
                assignments = ', '.join(f'{c}={expr}' for c, expr in expressions.items())
                changes = ' OR '.join(f'watch_sessions.{c} IS DISTINCT FROM {expr}' for c, expr in expressions.items())
                cursor.execute(
                    'INSERT INTO public.watch_sessions (' + ', '.join(SESSION_COLUMNS) + ') VALUES (' +
                    ', '.join(['%s'] * len(SESSION_COLUMNS)) + ') ON CONFLICT (source_event_id) DO UPDATE SET ' +
                    assignments + ' WHERE watch_sessions.rating_key=EXCLUDED.rating_key AND '
                    'watch_sessions.username IS NOT DISTINCT FROM EXCLUDED.username AND (' + changes + ') RETURNING (xmax=0)',
                    tuple(values[c] for c in SESSION_COLUMNS),
                )
                result = cursor.fetchone()
                if result:
                    outcome = 'inserted' if result[0] else 'updated'
                else:
                    cursor.execute('SELECT rating_key, username FROM public.watch_sessions WHERE source_event_id=%s', (values['source_event_id'],))
                    outcome = 'unchanged' if cursor.fetchone() == (values['rating_key'], values['username']) else 'skipped'
            cursor.execute('RELEASE SAVEPOINT raw_session')
            stats[outcome] += 1
            if outcome == 'skipped':
                reasons['source_identity_conflict'] += 1
        except Exception as exc:
            reasons["database_write_" + str(getattr(exc,"pgcode",None) or "unknown")] += 1
            cursor.execute('ROLLBACK TO SAVEPOINT raw_session')
            cursor.execute('RELEASE SAVEPOINT raw_session')
            stats['failed'] += 1
    return stats


def reconcile_memberships(cursor, groups, *, reasons=None):
    """Read model identities; write only verified links for already stored sessions."""
    reasons = reasons if reasons is not None else Counter()
    linked = 0
    for row in groups:
        mapped, members = map_history(row), group_members(row)
        if mapped is None or members is None:
            raise ValueError('Incomplete grouped source membership')
        values = mapped[0]
        cursor.execute('SELECT username, rating_key FROM public.watch_history WHERE watch_id=%s', (values['watch_id'],))
        identity = cursor.fetchone()
        if identity != (values['username'], values['rating_key']):
            reasons['missing_group_history' if identity is None else 'group_identity_mismatch'] += 1
            continue  # Missing legacy group or identity mismatch: never create/modify it.
        # Serialize link refreshes without explicitly locking or updating model rows.
        cursor.execute('SELECT pg_advisory_xact_lock(7401, %s)', (values['watch_id'],))
        cursor.execute('DELETE FROM public.watch_session_memberships WHERE watch_id=%s AND NOT (source_event_id=ANY(%s))', (values['watch_id'], members))
        cursor.execute('''
            INSERT INTO public.watch_session_memberships(watch_id, source_event_id)
            SELECT %s, s.source_event_id FROM public.watch_sessions s
            WHERE s.source_event_id=ANY(%s) AND s.rating_key=%s
              AND s.username IS NOT DISTINCT FROM %s
            ON CONFLICT (watch_id, source_event_id) DO NOTHING
        ''', (values['watch_id'], members, values['rating_key'], values['username']))
        linked += cursor.rowcount
    return linked


def ingest_sessions(conn, *, dry_run=False, since=None, until=None, page_size=1000,
                    incremental=False, fetch=None, reconciliation_days=None, retries=None):
    """Exclusive raw-session operation with fixed UTC bounds and bounded replay."""
    from api.services.tautulli_api import TautulliApiError, TautulliConfig, normalize_tautulli_api_url, tautulli_request
    totals = dict(inserted=0, updated=0, unchanged=0, skipped=0, failed=0,
                  errors=0, linked=0, ips_purged=0, pages=0, attempts=0, retries=0,
                  unlinked=0, busy=False)
    reasons, link_reasons = Counter(), Counter()
    started, locked = time.monotonic(), False
    if fetch is None:
        source_url, source_key = os.getenv('TAUTULLI_API_URL'), os.getenv('TAUTULLI_API_KEY')
        source_config = TautulliConfig(normalize_tautulli_api_url(api_url=source_url),source_key) if source_url and source_key else None
        def fetch(command, params):
            return tautulli_request(command, config=source_config, params=params, timeout=30, require_data=True)

    def emit(label):
        print(label + ': ' + json.dumps({**totals, 'skipped_reasons': dict(reasons),
              'membership_reasons': dict(link_reasons)}, sort_keys=True))

    conn.set_session(readonly=dry_run)
    try:
        days = int(reconciliation_days if reconciliation_days is not None else os.getenv('WATCH_SESSIONS_RECONCILIATION_DAYS','30'))
        retry_limit = int(retries if retries is not None else os.getenv('WATCH_SESSIONS_RETRIES','1'))
        if not 1 <= days <= 365 or not 0 <= retry_limit <= 2:
            raise ValueError('Invalid session reconciliation/retry configuration')
        since, until = utc(since), utc(until) or utc(datetime.now(timezone.utc))
        with conn.cursor() as cur:
            require_session_writer(cur)
            cur.execute('SELECT pg_try_advisory_lock(7402, 0)')
            locked = bool(cur.fetchone()[0])
            if not locked:
                totals['busy'] = True
                return totals
            # This integration deliberately keeps IP collection off.
            cur.execute('SELECT ip_retention_days FROM public.watch_session_policy WHERE singleton')
            policy = cur.fetchone()
            if policy is None or policy[0] != 0:
                raise SessionPolicyError('Session ingestion requires the approved zero-IP policy')
            if incremental and since is None:
                cur.execute('SELECT MAX(started_at) FROM public.watch_sessions')
                latest = cur.fetchone()[0]
                since = utc(latest) - timedelta(days=days) if latest else until - timedelta(days=days)
            if since is not None and since >= until:
                raise ValueError('since must be earlier than until')
            after = (since - timedelta(days=1)).strftime('%Y-%m-%d') if since else None
            before = (until + timedelta(days=1)).strftime('%Y-%m-%d')
            if not dry_run:
                totals['ips_purged'] = purge_expired_ips(cur)
                conn.commit()
            for attempt in range(retry_limit + 1):
                totals['attempts'] += 1
                try:
                    for rows in iter_history_pages(fetch, grouping=0, after=after, before=before, page_size=page_size):
                        selected = []
                        for row in rows:
                            mapped = map_session(row)
                            if mapped is None:
                                totals['skipped'] += 1
                                reasons['missing_source_or_media_identity'] += 1
                                continue
                            watched = utc(mapped[0]['watched_at'])
                            if watched is None or watched >= until or (since is not None and watched < since):
                                totals['skipped'] += 1
                                reasons['missing_watch_timestamp' if watched is None else 'outside_requested_window'] += 1
                                continue
                            selected.append(row)
                        page_reasons, page_links = Counter(), Counter()
                        stats = persist_sessions(cur, selected, dry_run=dry_run, reasons=page_reasons)
                        linked = 0
                        if not dry_run:
                            references = sorted({integer(r.get('reference_id')) for r in selected if integer(r.get('reference_id')) is not None})
                            for index in range(0, len(references), 50):
                                for groups in iter_history_pages(fetch, grouping=1, reference_id=','.join(map(str, references[index:index+50])), page_size=1000):
                                    linked += reconcile_memberships(cur, groups, reasons=page_links)
                            conn.commit()
                        for key, count in stats.items():
                            totals[key] += count
                        reasons.update(page_reasons)
                        link_reasons.update(page_links)
                        totals['linked'] += linked
                        totals['pages'] += 1
                        emit('Session ingestion metrics')
                    break
                except (HistoryPaginationError, TautulliApiError) as exc:
                    conn.rollback()
                    if attempt == retry_limit:
                        raise
                    totals['retries'] += 1
                    print('Session ingestion retry: reason=' + ('pagination_changed' if isinstance(exc,HistoryPaginationError) else 'source_unavailable'))
                    time.sleep(0.25)
                    # Retry the frozen date range from zero; committed rows are idempotent.
            if not dry_run:
                cur.execute("""SELECT CASE WHEN s.source_reference_id IS NULL THEN 'missing_source_reference'
                           ELSE 'no_verified_group_membership' END, count(*)
                    FROM public.watch_sessions s LEFT JOIN public.watch_session_memberships m USING(source_event_id)
                    WHERE m.source_event_id IS NULL GROUP BY 1""")
                unlinked = dict(cur.fetchall())
                totals['unlinked'] = sum(unlinked.values())
                totals['unlinked_reasons'] = unlinked
                conn.rollback()
    except (Exception, KeyboardInterrupt) as exc:
        conn.rollback()
        totals['errors'] += 1
        if isinstance(exc,KeyboardInterrupt):
            code='interrupted'
        elif isinstance(exc,HistoryPaginationError):
            code='pagination_incomplete'
        elif isinstance(exc,TautulliApiError):
            code='source_unavailable'
        elif isinstance(exc,SessionWriterPermissionError):
            code='restricted_writer_required'
        elif isinstance(exc,SessionPolicyError):
            code='zero_ip_policy_required'
        elif getattr(exc,'pgcode',None) == '42501':
            code='database_permission_denied'
        elif isinstance(exc,ValueError):
            code='invalid_input_or_configuration'
        else:
            code='database_or_policy_unavailable'
        totals['error_category'] = code
        print('Session ingestion failed: category=' + code + '; verify configuration/permissions or repeat the fixed date window')
    finally:
        if locked:
            try:
                with conn.cursor() as cleanup:
                    cleanup.execute('SELECT pg_advisory_unlock(7402, 0)')
                conn.rollback()
            except Exception:
                # Closing the caller-owned connection also releases the session lock.
                print('Session ingestion lock cleanup unavailable; close the connection')
        elif dry_run:
            conn.rollback()
        totals['total_seconds'] = round(time.monotonic() - started, 4)
        emit('Session ingestion totals')
    return totals
