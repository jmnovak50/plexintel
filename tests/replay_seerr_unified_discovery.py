"""Deterministic movie/TV replay. Dedicated disposable PostgreSQL, zero HTTP.

Run with the guarded SEERR_DISCOVERY_TEST_DSN described in the persistence guide.
This deliberately resets discovery tables in that fixture, never an application DB.
"""
from dataclasses import replace
import json
from unittest.mock import patch

from api.db.seerr_discovery import DiscoveryRepository
from api.services.seerr_discovery import sync_discovery
from tests.replay_seerr_discovery import fresh_fixture_connection
from tests.test_seerr_unified_discovery import DUAL, NOW, SCOPE, TV, UnifiedClient, movie, summary, tv


def main():
    # A hard failure if a future adapter accidentally attempts network IO.
    with patch('requests.sessions.Session.request', side_effect=AssertionError('Replay HTTP forbidden')):
        connection = fresh_fixture_connection()
        try:
            details = {('tv', 2): tv(2, type='Special'),
                       ('tv', 3): tv(3, type=None, seasons=None),
                       ('tv', 4): tv(4, firstAirDate='2018-01-01')}
            television = [summary(tv(i)) for i in range(1, 5)] + [summary(tv(5, firstAirDate=None))]
            clients = [UnifiedClient(movies=[movie(1)], television=television, details=details) for _ in range(2)]
            runs = [sync_discovery(client, replace(DUAL, enabled=True), [SCOPE, TV],
                repository=DiscoveryRepository(connection), dry_run=False, clock=lambda: NOW) for client in clients]
            assert all(run['status'] == 'success' for run in runs)
            assert runs[0]['counts']['titles'] == runs[0]['counts']['new_titles'] == 6
            assert runs[0]['counts']['by_media_type']['tv']['eligible'] == 2
            assert runs[0]['counts']['by_media_type']['tv']['provisional'] == 2
            assert runs[0]['counts']['by_media_type']['tv']['excluded'] == 1
            assert runs[1]['counts']['new_titles'] == runs[1]['counts']['updated_titles'] == 0
            assert runs[1]['counts']['enrichment_cached'] == 6
            assert not any(call[0] == 'detail' for call in clients[1].calls)
            with connection.cursor() as cur:
                cur.execute('SELECT media_type,tmdb_id,eligibility FROM public.seerr_discovery_observations WHERE run_id=%s ORDER BY media_type,tmdb_id', (runs[1]['run_id'],))
                audit = [dict(media_type=row[0], tmdb_id=row[1], eligibility=row[2]) for row in cur.fetchall()]
            print(json.dumps(dict(source='synthetic movie/TV responses, isolated fixture', actual_http_requests=0,
                synthetic_adapter_calls=[client.calls for client in clients], latest_eligibility_audit=audit, runs=runs), indent=2))
        finally:
            connection.close()


if __name__ == '__main__':
    main()
