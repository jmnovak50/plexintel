"""Optional captured-data integration smoke test, STRICTLY confined to a disposable cluster.

SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.XXX port=... dbname=plexintel_seerr_fixture'
python -m tests.replay_seerr_discovery
No HTTP calls. Reads Phase 1 cache and writes only the dedicated fixture database.
"""
from datetime import date
import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extensions import parse_dsn

from api.db.seerr_discovery import DiscoveryRepository
from api.services.seerr_client import SeerrConfig, sanitize_movie
from api.services.seerr_discovery import DiscoveryScope, sync_discovery


def fresh_fixture_connection():
    """Reset discovery tables only after verifying the dedicated disposable target."""
    dsn = os.environ['SEERR_DISCOVERY_TEST_DSN']
    parsed = parse_dsn(dsn)
    root = Path(parsed.get('host', ''))
    if parsed.get('dbname') != 'plexintel_seerr_fixture' or not str(root).startswith('/tmp/plexintel-seerr-fixture.'):
        raise RuntimeError('Dedicated TCP-disabled disposable cluster required')
    connection = psycopg2.connect(dsn)
    try:
        with connection:
            with connection.cursor() as cur:
                cur.execute("SELECT current_setting('data_directory'),current_setting('listen_addresses')")
                directory, listen = cur.fetchone()
                if Path(directory) != root / 'data' or listen:
                    raise RuntimeError('Unsafe fixture target')
                migration = Path(__file__).resolve().parents[1] / 'api/db/migrations/optional/seerr_discovery'
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovery_observations')
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovered_titles')
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovered_movies')
                cur.execute('DROP TABLE IF EXISTS public.seerr_discovery_runs')
                cur.execute((migration / '001_initial.sql').read_text())
                cur.execute((migration / '002_unified_titles.sql').read_text())
        return connection
    except BaseException:
        connection.close()
        raise


def main():
    artifacts = Path(__file__).resolve().parents[1] / 'artifacts/seerr-exploration'
    datasets = {name: json.loads((artifacts / directory / 'candidates.json').read_text())
                for name, directory in [('configured', '2026-10-28-week'), ('all', '2026-10-28-all-languages')]}
    details = {}
    for path in sorted((artifacts / 'cache').glob('*.json')):
        raw = json.loads(path.read_text())['data']
        if isinstance(raw, dict) and 'credits' in raw:
            details[raw['id']] = sanitize_movie(raw)
    class CapturedClient:
        requests = retry_count = 0  # No HTTP operations are performed by this adapter.
        def discover(self, params):
            rows = datasets['all' if params.get('language') == 'all' else 'configured']
            page = params['page']
            selected = rows[(page-1)*20:page*20]
            return dict(page=page, totalPages=(len(rows)+19)//20, totalResults=len(rows), results=[dict(
                id=r['tmdb_id'], title=r['title'], originalTitle=r['original_title'],
                releaseDate=r['discovery_primary_release_date'], originalLanguage=r['original_language'],
                overview=r['overview'], popularity=r['popularity'], voteCount=r['vote_count'],
                voteAverage=r['vote_average'], genreIds=r['genre_ids']) for r in selected])
        def movie(self, ident):
            return details[ident]
    connection = fresh_fixture_connection()
    try:
        cfg = SeerrConfig('https://captured-fixture.invalid', 'fixture-only', enabled=True, source_id='captured-fixture')
        scopes = [DiscoveryScope('configured', date(2026,10,26), date(2026,11,1), 'configured'),
                  DiscoveryScope('all', date(2026,10,26), date(2026,11,1), 'all', 'popularity.desc')]
        runs = [sync_discovery(CapturedClient(), cfg, scopes, repository=DiscoveryRepository(connection), dry_run=False) for _ in range(2)]
        assert all(r['status'] == 'success' for r in runs)
        expected = len({r['tmdb_id'] for rows in datasets.values() for r in rows})
        assert runs[0]['counts']['new_movies'] == expected and runs[1]['counts']['new_movies'] == 0
        assert runs[1]['counts']['existing_movies'] == runs[1]['counts']['enrichment_cached'] == expected
        result = dict(source='isolated fixture replay of captured Phase 1 data', actual_http_requests=0,
                      expected_union=expected, runs=runs)
        print(json.dumps(result, indent=2))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
