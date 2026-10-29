#!/usr/bin/env python3
"""Explicit Seerr discovery preview, discovery-only persistence, or read-only inventory summary."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from api.db.connection import connect_db
from api.db.seerr_discovery import DiscoveryRepository, database_error_code, inventory_summary
from api.services.private_config import PrivateConfigError
from api.services.seerr_client import SeerrClient, SeerrError, load_seerr_config
from api.services.seerr_discovery import build_scopes, sync_discovery


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=lambda v: v.isoformat() if isinstance(v, (date, datetime)) else str(v))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--dry-run', action='store_true', help='GET preview only; never connects to PostgreSQL')
    action.add_argument('--execute', action='store_true', help='Write only the three opt-in discovery tables; also requires enabled=true')
    action.add_argument('--summary', action='store_true', help='Read-only inventory/run/refresh summary; no Seerr calls')
    parser.add_argument('--credentials-file', type=Path, help='Owner-only dotenv configuration file')
    parser.add_argument('--start', type=date.fromisoformat)
    parser.add_argument('--end', type=date.fromisoformat)
    parser.add_argument('--as-of', type=date.fromisoformat, help='UTC calendar anchor for configured lookback/lookahead')
    parser.add_argument('--language', action='append', help='Repeat for multiple scopes: all, configured, en, etc.')
    parser.add_argument('--media-type', action='append', choices=['movie', 'tv'], help='Repeat for a combined operation; defaults to movie')
    parser.add_argument('--sort-by', choices=['primary_release_date.asc', 'primary_release_date.desc', 'first_air_date.asc', 'first_air_date.desc', 'popularity.desc', 'vote_count.desc'])
    parser.add_argument('--max-pages', type=int)
    parser.add_argument('--refresh', action='store_true', help='Ignore metadata cache age and failed-attempt cooldown')
    parser.add_argument('--enrich-due', action='store_true', help='Refresh inventory outside current discovery windows; execute only')
    parser.add_argument('--json', action='store_true', help='Emit the full sanitized result as JSON on stdout')
    args = parser.parse_args(argv)
    if args.enrich_due and not args.execute:
        parser.error('--enrich-due requires --execute; use --summary to inspect due counts without writes')
    if args.enrich_due and any((args.start, args.end, args.as_of, args.language, args.sort_by)):
        parser.error('--enrich-due refreshes the stored inventory; discovery date/language/sort overrides do not apply')
    if (args.start is None) != (args.end is None):
        parser.error('--start and --end must be supplied together')
    load_dotenv(ROOT / '.env', override=False)
    connection = None
    try:
        config = load_seerr_config(args.credentials_file, languages=tuple(args.language) if args.language else None,
                                  media_types=tuple(args.media_type) if args.media_type else None,
                                  sort_by=args.sort_by, max_pages=args.max_pages)
        if args.execute and not config.enabled:
            raise SeerrError('discovery_disabled')
        if args.execute:
            config.require_source_identity()
        if args.summary:
            connection = connect_db()
            connection.set_session(readonly=True, autocommit=False)
            with connection.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='15s'")
            result = inventory_summary(connection, config, datetime.now(timezone.utc))
            connection.rollback()
        else:
            if args.execute:
                connection = connect_db()
            client = SeerrClient(config)
            scopes = [] if args.enrich_due else build_scopes(config, start=args.start, end=args.end, anchor=args.as_of)
            def log(event):
                print(_json({'timestamp': datetime.now(timezone.utc), **event}), file=sys.stderr)
            result = sync_discovery(client, config, scopes, dry_run=args.dry_run,
                repository=DiscoveryRepository(connection) if connection else None,
                refresh=args.refresh, enrich_due=args.enrich_due, log=log)
        if args.json:
            print(_json(result))
        elif args.summary:
            latest = result['latest_run']
            print(f"Discovered titles: {result['total_titles']} (movies {result['total_movies']}, TV {result['total_tv']}); refresh due: {result['refresh_due']}; "
                  f"latest status: {latest['status'] if latest else 'no runs'}")
            if latest:
                print(_json({'run_id': latest['run_id'], 'parameters': latest['parameters'], 'counts': latest['counts']}))
        else:
            print(f"Seerr discovery {'preview' if args.dry_run else 'execution'}: {result['status']} ({result['run_id']})")
            print(_json(result.get('counts', {})))
            if result.get('errors'):
                print(_json({'errors': result['errors'][:10], 'total_errors': len(result['errors'])}))
            if args.dry_run:
                print('Database not accessed; new/existing/updated counts are unknown in this preview.')
        return 0 if args.summary or result['status'] == 'success' else 2
    except (SeerrError, PrivateConfigError) as err:
        code = err.code if isinstance(err, SeerrError) else 'private_configuration_invalid'
        print(_json({'status': 'failed', 'code': code}), file=sys.stderr)
        return 75 if code == 'discovery_already_running' else 1
    except Exception as err:
        print(_json({'status': 'failed', 'code': database_error_code(err)}), file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
