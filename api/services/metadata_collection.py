"""Existing importer orchestration with explicit coverage and transaction outcomes."""
import json
from uuid import uuid4
from . import metadata_ingestion as metadata


class DiscoveryError(metadata.MetadataError):
    pass


def pages(fetch, endpoint, params, collection, page_size):
    result, seen, total = [], set(), None
    for _ in range(10000):
        payload = fetch(endpoint, {**params, 'start':len(result), 'length':page_size})
        if not isinstance(payload, dict) or not isinstance(payload.get(collection), list):
            raise DiscoveryError('discovery_page_failed')
        rows = payload[collection]
        count = payload.get('recordsFiltered', payload.get('recordsTotal', payload.get('total_count', payload.get('total_size'))))
        if count is not None:
            count = metadata.integer(count, required=True)
            if count < 0 or (total is not None and total != count): raise DiscoveryError('discovery_total_changed')
            total = count
        if len(rows) > page_size: raise DiscoveryError('oversized_discovery_page')
        for row in rows:
            if not isinstance(row, dict): raise DiscoveryError('invalid_discovery_row')
            key = metadata.integer(row.get('rating_key'), required=True)
            if key <= 0 or key in seen: raise DiscoveryError('duplicate_discovery_key')
            seen.add(key)
        result.extend(rows)
        if total is not None:
            if len(result) > total or (len(rows) < page_size and len(result) < total):
                raise DiscoveryError('truncated_discovery')
            if len(result) == total: return result
        elif len(rows) < page_size: return result
    raise DiscoveryError('discovery_page_limit')


def discover(adapter):
    """The existing two sections, with all hierarchy keys collected before writes."""
    inventory = {}
    def add(row, kind):
        key = metadata.integer(row.get('rating_key'), required=True)
        actual = row.get('media_type')
        if actual is not None and actual != kind: raise DiscoveryError('discovery_kind_mismatch')
        if key in inventory and inventory[key] != kind: raise DiscoveryError('discovery_identity_conflict')
        inventory[key] = kind
    for row in adapter.get_library_media_info(section_id=1): add(row, 'movie')
    for show in adapter.get_library_media_info(section_id=2):
        add(show, 'show')
        for season in adapter.get_children_metadata(show['rating_key']):
            add(season, 'season')
            for episode in adapter.get_children_metadata(season['rating_key']): add(episode, 'episode')
    return list(inventory.items())


def missing_headers(cur):
    cur.execute('''SELECT DISTINCT l.parent_rating_key AS rating_key,
            CASE WHEN l.media_type='episode' THEN 'season' ELSE 'show' END AS kind
        FROM public.library l LEFT JOIN public.library p ON p.rating_key=l.parent_rating_key
        WHERE l.media_type IN('episode','season') AND l.parent_rating_key IS NOT NULL AND p.rating_key IS NULL
        UNION SELECT DISTINCT l.show_rating_key,'show' FROM public.library l
        LEFT JOIN public.library p ON p.rating_key=l.show_rating_key
        WHERE l.media_type IN('episode','season') AND l.show_rating_key IS NOT NULL AND p.rating_key IS NULL''')
    return [(x['rating_key'], x['kind']) for x in (metadata.row_dict(cur, row) for row in cur.fetchall())]


def _stats():
    return dict(accepted=0, skipped_existing=0, previewed=0, failed=0, receipt_failed=0)


def _failure(conn, key, operation, exc, stats):
    conn.rollback(); stats['failed'] += 1
    try:
        with conn.cursor() as cur: metadata.record_failure(cur, key, operation, exc)
        conn.commit()
    except Exception:
        conn.rollback(); stats['receipt_failed'] += 1
    code = metadata.error_code(exc)
    print(json.dumps(dict(event='metadata_acceptance', rating_key=key, operation_id=str(operation),
                         status='failed', reason=code, receipt_failed=bool(stats['receipt_failed']))), flush=True)


def store_candidates(conn, items, *, dry_run=False, operation_id=None):
    stats = _stats(); operation = operation_id or uuid4()
    if dry_run:
        for item in items: metadata.validate_candidate(item); stats['previewed'] += 1
        return stats
    for item in items:
        key = metadata.integer(item.get('rating_key'), required=True)
        try:
            with conn.cursor() as cur: outcome = metadata.accept(cur, item, operation_id=operation)
            metadata.commit_metadata(conn,key,operation); stats[outcome] += 1
            print(json.dumps(dict(event='metadata_acceptance',rating_key=key,operation_id=str(operation),status=outcome)), flush=True)
        except metadata.CommitUncertain: raise
        except Exception as exc: _failure(conn, key, operation, exc, stats)
    return stats


def ingest_keys(adapter, conn, inventory, *, dry_run=False):
    stats = _stats(); preview = {}; operation = uuid4()
    with conn.cursor() as cur:
        if not dry_run: metadata.require_schema(cur)
        cur.execute('SELECT rating_key FROM public.library')
        existing = {metadata.row_dict(cur, x)['rating_key'] for x in cur.fetchall()}
    conn.rollback()
    def lookup(key):
        if key in preview: return preview[key]
        with conn.cursor() as cur: item = metadata.parent_metadata(cur, key)
        conn.rollback()
        return item
    unique = {}
    for key, kind in inventory:
        if key in unique and unique[key] != kind: raise DiscoveryError('discovery_identity_conflict')
        unique[key] = kind
    inventory = unique
    for key, kind in sorted(inventory.items(), key=lambda kv: ({'show':0,'season':1,'movie':2,'episode':3}[kv[1]],kv[0])):
        if key in existing: stats['skipped_existing'] += 1; continue
        try:
            item = adapter.get_metadata(key, parent_lookup=lookup, expected_type=kind)
            metadata.validate_candidate(item)
            if item['media_type'] != kind: raise metadata.MetadataError('discovered_kind_mismatch')
            if dry_run:
                if kind in ('episode','season'):
                    parent, show = lookup(item['parent_rating_key']), lookup(item['show_rating_key'])
                    if not parent or not show or show['media_type'] != 'show' or parent['media_type'] != ('season' if kind=='episode' else 'show'):
                        raise metadata.MetadataError('unaccepted_parent')
                    if kind=='episode' and parent['show_rating_key'] != item['show_rating_key']:
                        raise metadata.MetadataError('wrong_series_parent')
                if kind in ('show','season'): preview[key]=item
                stats['previewed'] += 1
                print(json.dumps(dict(event='metadata_preview',rating_key=key,status='would_accept')))
            else:
                result = store_candidates(conn, [item], operation_id=operation)
                for name in stats: stats[name] += result[name]
        except metadata.CommitUncertain: raise
        except Exception as exc:
            if dry_run:
                stats['failed'] += 1
                print(json.dumps(dict(event='metadata_preview',rating_key=key,status='failed',reason=type(exc).__name__)))
            else: _failure(conn, key, operation, exc, stats)
    return stats


def repair_guids(adapter, conn, *, dry_run=False):
    result = dict(applied=0, unchanged=0, previewed=0, failed=0)
    with conn.cursor() as cur:
        cur.execute("SELECT rating_key FROM public.library WHERE plex_guid IS NULL OR btrim(plex_guid)='' ORDER BY rating_key")
        keys = [metadata.row_dict(cur,x)['rating_key'] for x in cur.fetchall()]
    conn.rollback()
    for key in keys:
        try:
            raw = adapter.fetch_tautulli_data('get_metadata', {'rating_key':key})
            with conn.cursor() as cur: plan = metadata.guid_plan(cur, key, raw)
            conn.rollback()
            if plan is None: result['unchanged'] += 1; continue
            if dry_run: result['previewed'] += 1; continue
            with conn.cursor() as cur: outcome = metadata.apply_plan(cur, plan)
            metadata.commit_metadata(conn,key,plan['operation_id']); result['applied' if outcome in ('applied','replayed') else 'unchanged'] += 1
        except metadata.CommitUncertain: raise
        except Exception as exc:
            conn.rollback(); result['failed'] += 1
            print(json.dumps(dict(event='metadata_guid_completion',rating_key=key,status='deferred',reason=type(exc).__name__)))
    return result


def run(adapter, *, mode, dry_run=False):
    """No schema/bootstrap/model calls. Existing history keeps its own outcome."""
    adapter._METADATA_CACHE.clear(); adapter._METADATA_DRY_RUN = dry_run
    conn=None
    result = dict(mode=mode,dry_run=dry_run,coverage='incomplete',metadata=_stats(),users='not_run',history='not_run')
    try:
        if hasattr(adapter, 'connect_to_db'):
            conn, initial_cursor = adapter.connect_to_db()
            if initial_cursor is not None: initial_cursor.close()
            if conn is None: raise RuntimeError('Source database connection unavailable')
        else:
            conn = adapter.connect_db()
        # Legacy vector registration performs read queries on this fresh
        # connection. Finish that transaction before selecting preview mode.
        conn.rollback()
        conn.set_session(readonly=dry_run)
        with conn.cursor() as cur:
            if not dry_run: metadata.require_schema(cur)
        conn.rollback()
        if not dry_run and mode == 'incremental': adapter.clear_tautulli_cache()
        try:
            inventory = discover(adapter)
            with conn.cursor() as cur: inventory += missing_headers(cur)
            conn.rollback(); result['coverage']='complete'
            result['metadata'] = ingest_keys(adapter, conn, inventory, dry_run=dry_run)
            if mode=='incremental': result['guid_completion']=repair_guids(adapter,conn,dry_run=dry_run)
        except metadata.CommitUncertain as exc:
            try: conn.rollback()
            except Exception: pass
            result['metadata']['failed'] += 1
            result['commit_resolution']=dict(rating_key=exc.rating_key,operation_id=exc.operation_id,status=exc.resolved)
            conn.close(); conn=adapter.connect_db()
        except Exception as exc:
            conn.rollback(); result['metadata']['failed'] += 1
            result['error']=metadata.error_code(exc)
        if not dry_run and mode != 'recover':
            try:
                with conn.cursor() as cur: adapter.sync_users_from_tautulli(conn,cur)
                conn.commit(); result['users']='committed'
            except Exception:
                conn.rollback(); result['users']='failed'
            try:
                if mode=='full':
                    rows=adapter.get_watch_history()
                    with conn.cursor() as cur: adapter.store_watch_history(conn,cur,rows,source_grouping=1)
                    conn.commit();ok=True
                else:
                    with conn.cursor() as cur: ok=adapter.sync_new_watch_history(conn,cur)
                result['history']='committed' if ok else 'failed'
            except Exception:
                conn.rollback(); result['history']='failed'
        result['ok'] = result['coverage']=='complete' and result['metadata']['failed']==0 and result.get('guid_completion',{}).get('failed',0)==0 and result['users']!='failed' and result['history']!='failed'
        print('Metadata ingestion metrics: ' + json.dumps(result,sort_keys=True),flush=True)
        if not result['ok']: raise metadata.MetadataError('metadata_collection_incomplete')
        return result
    finally:
        if conn:
            try: conn.rollback()
            except Exception: pass
            conn.close()
        adapter._METADATA_DRY_RUN=False
