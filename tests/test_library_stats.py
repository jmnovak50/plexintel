"""Stats contract tests; optional SQL tests require a disposable local /tmp cluster."""
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import MagicMock, patch

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from mcp.server.fastmcp.exceptions import ToolError
import psycopg2
from psycopg2.extensions import parse_dsn

from api.routes import agent_tools
from api.services.agent_auth import AgentPrincipal, require_agent_principal
from api.services import library_stats_service as stats, mcp_server
from api.services.mcp_auth import MCPAuthContext


SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)
UNTIL = datetime(2027, 1, 1, tzinfo=timezone.utc)
COUNTS = dict(movies=125, shows=20, seasons=35, episodes=300)


def response():
    return stats.LibraryStatsResponse(
        period=stats.LibraryStatsPeriod(since=SINCE, until=UNTIL),
        media_type=None, counts=COUNTS, total=480, unsupported_categories=[], added_at_timezone="UTC",
    )


class LibraryStatsTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(agent_tools.router, prefix='/api/agent')
        self.app.dependency_overrides[require_agent_principal] = lambda: AgentPrincipal('jwt', 'viewer')
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_authenticated_route_and_normalized_response(self):
        with patch.object(agent_tools, 'get_library_stats', return_value=response()) as service:
            result = self.client.get('/api/agent/library/stats', params={
                'since': '2026-01-01T00:00:00Z', 'until': '2027-01-01T00:00:00Z',
            })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), response().model_dump(mode='json'))
        service.assert_called_once_with(since=SINCE, until=UNTIL, media_type=None)

    def test_missing_authentication_is_rejected_before_query(self):
        self.app.dependency_overrides.clear()
        with patch.object(stats, 'connect_db') as connect:
            result = self.client.get('/api/agent/library/stats')
        self.assertEqual(result.status_code, 401)
        connect.assert_not_called()

    def test_invalid_inputs_are_rejected(self):
        for params, code in [
            ({'since': 'nonsense'}, 422), ({'until': 'nope'}, 422),
            ({'media_type': 'series'}, 422), ({'media_type': 'music'}, 422),
            ({'since': UNTIL.isoformat(), 'until': SINCE.isoformat()}, 400),
            ({'since': SINCE.isoformat(), 'until': SINCE.isoformat()}, 400),
            ({'since': '9999-01-01T00:00:00Z'}, 400),
        ]:
            with self.subTest(params=params), patch.object(stats, 'connect_db') as connect:
                self.assertEqual(self.client.get('/api/agent/library/stats', params=params).status_code, code)
                connect.assert_not_called()

    def test_sql_aggregation_is_readonly_parameterized_and_connection_closed(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {**COUNTS, "added_at_timezone": "UTC"}
        with patch.object(stats, 'connect_db', return_value=conn):
            result = stats.get_library_stats(
                since=datetime.fromisoformat('2026-01-01T00:00:00-06:00'),
                until=UNTIL, media_type='movie',
            )
        sql, params = cursor.execute.call_args.args
        self.assertIn('COUNT(DISTINCT rating_key)', sql)
        self.assertIn("added_at >= (%s::timestamptz AT TIME ZONE current_setting('TimeZone'))", sql)
        self.assertIn("added_at < (%s::timestamptz AT TIME ZONE current_setting('TimeZone'))", sql)
        self.assertNotIn('LIMIT', sql)
        self.assertNotIn('JOIN', sql)
        self.assertEqual(params, [datetime(2026, 1, 1, 6, tzinfo=timezone.utc), UNTIL, 'movie'])
        self.assertEqual(result.counts, {'movies': 125})
        self.assertEqual(result.total, 125)
        self.assertEqual(result.period.since, datetime(2026, 1, 1, 6, tzinfo=timezone.utc))
        conn.set_session.assert_called_once_with(readonly=True)
        conn.close.assert_called_once()

    def test_naive_utc_default_until_and_all_time_null_dates(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {**dict.fromkeys(COUNTS, 0), "added_at_timezone": "UTC"}
        before = datetime.now(timezone.utc)
        with patch.object(stats, 'connect_db', return_value=conn):
            result = stats.get_library_stats()
        self.assertLessEqual(before, result.period.until)
        self.assertLessEqual(result.period.until, datetime.now(timezone.utc))
        self.assertIsNone(result.period.since)
        self.assertEqual(result.total, 0)
        self.assertEqual(result.unsupported_categories, [])
        self.assertIn('added_at IS NULL', cursor.execute.call_args.args[0])
        with patch.object(stats, 'connect_db', return_value=conn):
            result = stats.get_library_stats(since=datetime(2026, 1, 1), until=UNTIL)
        self.assertEqual(result.period.since, SINCE)

    def test_db_failure_is_sanitized_and_connection_closed(self):
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError('private-database-details')
        with patch.object(stats, 'connect_db', return_value=conn):
            result = self.client.get('/api/agent/library/stats')
        self.assertEqual(result.status_code, 500)
        self.assertIn('incident', result.json()['detail'])
        self.assertNotIn('private-database-details', result.text)
        conn.close.assert_called_once()


class LibraryStatsMCPTests(unittest.TestCase):
    def build(self):
        with patch.object(mcp_server, 'get_setting_value', return_value=None):
            return mcp_server._build_mcp_server()

    def call(self, server, arguments, context=MCPAuthContext('static')):
        async def run():
            token = mcp_server.mcp_auth_context.set(context)
            try:
                return await server.call_tool('get_library_stats', arguments)
            finally:
                mcp_server.mcp_auth_context.reset(token)
        return anyio.run(run)

    def test_discovery_schema(self):
        server = self.build()
        tools = anyio.run(server.list_tools)
        tool = next(t for t in tools if t.name == 'get_library_stats')
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertEqual(set(tool.inputSchema['properties']), {'since', 'until', 'media_type'})
        enum = tool.inputSchema['properties']['media_type']['anyOf'][0]['enum']
        self.assertEqual(enum, ['movie', 'show', 'season', 'episode'])
        self.assertIn('counts', tool.outputSchema['properties'])

    def test_calls_rest_route_with_verified_identity_and_maps_response(self):
        server = self.build()
        real_get = mcp_server.httpx.AsyncClient.get
        calls = []

        async def capture(client, path, **kwargs):
            calls.append((path, kwargs))
            return await real_get(client, path, **kwargs)

        context = MCPAuthContext('jwt', plex_username='viewer')
        with patch.object(agent_tools, 'get_library_stats', return_value=response()) as service, \
             patch.object(mcp_server.httpx.AsyncClient, 'get', capture), \
             patch.object(mcp_server, 'search_agent_library') as search:
            result = self.call(server, {'since': SINCE.isoformat(), 'until': UNTIL.isoformat()}, context)
        self.assertEqual(calls, [('/api/agent/library/stats', {'params': {
            'since': SINCE.isoformat(), 'until': UNTIL.isoformat(),
        }})])
        self.assertEqual(result[1], response().model_dump(mode='json'))
        service.assert_called_once_with(since=SINCE, until=UNTIL, media_type=None)
        search.assert_not_called()
        token = mcp_server.mcp_auth_context.set(context)
        try:
            principal = mcp_server._library_stats_mcp_principal()
            self.assertEqual(principal.username, 'viewer')
            self.assertFalse(principal.can_read_all)
        finally:
            mcp_server.mcp_auth_context.reset(token)

    def test_validation_auth_and_rest_errors_propagate(self):
        server = self.build()
        with patch.object(agent_tools, 'get_library_stats') as service:
            for args in ({'media_type': 'music'}, {'since': 'garbage'}):
                with self.assertRaises(ToolError):
                    self.call(server, args)
            service.assert_not_called()
            result = self.call(server, {}, context=None)
            self.assertTrue(result.isError)
            service.assert_not_called()
        with patch.object(agent_tools, 'get_library_stats', side_effect=HTTPException(400, 'since must be earlier than until')):
            with self.assertRaisesRegex(ToolError, 'HTTP 400.*since must be earlier than until'):
                self.call(server, {})
        with patch.object(agent_tools, 'get_library_stats', side_effect=RuntimeError('sensitive')):
            with self.assertRaises(ToolError) as raised:
                self.call(server, {})
        self.assertIn('HTTP 500', str(raised.exception))
        self.assertIn('incident', str(raised.exception))
        self.assertNotIn('sensitive', str(raised.exception))


@unittest.skipUnless(os.getenv('PLEXINTEL_STATS_TEST_DSN'), 'Set PLEXINTEL_STATS_TEST_DSN to an isolated local /tmp PostgreSQL cluster')
class LibraryStatsPostgresTests(unittest.TestCase):
    """Actual PostgreSQL semantics, without accessing application configuration."""
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PLEXINTEL_STATS_TEST_DSN']
        config = parse_dsn(cls.dsn)
        if not config.get('host', '').startswith('/tmp/plexintel-stats-pg'):
            raise ValueError('SQL fixtures require an isolated /tmp/plexintel-stats-pg cluster')
        cls.conn = psycopg2.connect(cls.dsn)
        cls.conn.autocommit = True
        with cls.conn.cursor() as cur:
            cur.execute('CREATE TABLE public.library (rating_key integer, media_type text, added_at timestamp, show_rating_key integer, parent_rating_key integer)')
            data = []
            key = 0
            for media_type, count in zip(('movie', 'show', 'season', 'episode'), (125, 20, 35, 300)):
                for _ in range(count):
                    key += 1
                    data.append((key, media_type, datetime(2026, 1, 1), 10000, 10001))
            # Older parent; first season/episode belong to this show independently.
            data.extend([
                (10000, 'show', datetime(2022, 1, 1), None, None),
                (10001, 'season', datetime(2022, 1, 1), 10000, 10000),
                (20000, 'movie', datetime(2027, 1, 1), None, None),
                (20001, 'movie', datetime(2025, 12, 31, 23, 59, 59), None, None),
                (20002, 'movie', None, None, None),
                (20003, 'series', datetime(2022, 1, 1), None, None),
                (20004, 'movie', datetime(2028, 7, 1), None, None),
                data[0],  # Repeated ingestion identity is counted once.
            ])
            cur.executemany('INSERT INTO public.library VALUES (%s,%s,%s,%s,%s)', data)

    @classmethod
    def tearDownClass(cls):
        with cls.conn.cursor() as cur:
            cur.execute('DROP TABLE public.library')
        cls.conn.close()

    def query(self, **kwargs):
        def connect(**options):
            return psycopg2.connect(self.dsn, options="-c timezone=UTC", **options)
        with patch.object(stats, 'connect_db', side_effect=connect):
            return stats.get_library_stats(**kwargs)

    def test_more_than_fifty_exact_independent_entities_and_duplicate_identity(self):
        result = self.query(since=SINCE, until=UNTIL)
        self.assertEqual(result.counts, COUNTS)
        self.assertEqual(result.total, 480)
        self.assertEqual(result.unsupported_categories, [])

    def test_all_time_counts_include_unknown_dates_and_show_alias(self):
        result = self.query(until=UNTIL)
        self.assertEqual(result.counts, dict(movies=127, shows=22, seasons=36, episodes=300))
        self.assertEqual(result.total, 485)

    def test_filter_each_category_independently(self):
        for media_type, category in zip(('movie', 'show', 'season', 'episode'), COUNTS):
            with self.subTest(media_type=media_type):
                result = self.query(since=SINCE, until=UNTIL, media_type=media_type)
                self.assertEqual(result.counts, {category: COUNTS[category]})

    def test_non_utc_storage_and_dst_use_ingestion_session_timezone(self):
        # A locally stored 00:00 Chicago item is 06:00Z in January.
        def connect(**options):
            return psycopg2.connect(self.dsn, options="-c timezone=America/Chicago", **options)
        with patch.object(stats, 'connect_db', side_effect=connect):
            result = stats.get_library_stats(
                since=datetime(2026, 1, 1, 6, tzinfo=timezone.utc),
                until=datetime(2026, 1, 1, 6, 0, 1, tzinfo=timezone.utc),
            )
            self.assertEqual(result.counts, COUNTS)
            self.assertEqual(result.added_at_timezone, 'America/Chicago')
            excluded = stats.get_library_stats(
                since=SINCE, until=datetime(2026, 1, 1, 6, tzinfo=timezone.utc),
            )
            self.assertEqual(excluded.counts['episodes'], 0)
            # Summer midnight uses a different offset from winter midnight.
            summer = stats.get_library_stats(
                since=datetime(2028, 7, 1, 5, tzinfo=timezone.utc),
                until=datetime(2028, 7, 1, 5, 0, 1, tzinfo=timezone.utc),
            )
            self.assertEqual(summer.counts["movies"], 1)

    def test_ambiguous_fall_back_boundaries_fail_closed(self):
        def connect(**options):
            return psycopg2.connect(self.dsn, options="-c timezone=America/Chicago", **options)
        with patch.object(stats, 'connect_db', side_effect=connect):
            for hour in (6, 7):
                with self.assertRaisesRegex(HTTPException, 'repeated daylight-saving hour'):
                    stats.get_library_stats(
                        since=datetime(2026, 11, 1, hour, 30, tzinfo=timezone.utc),
                        until=datetime(2026, 11, 2, tzinfo=timezone.utc),
                    )

    def test_boundaries_empty_ranges_offsets_and_default_ytd(self):
        self.assertEqual(self.query(since=SINCE, until=datetime(2026, 1, 1, 0, 0, 1)).counts, COUNTS)
        self.assertEqual(self.query(since=datetime(2026, 1, 1, 0, 0, 1), until=UNTIL).total, 0)
        self.assertEqual(self.query(since=datetime(2027, 1, 1), until=datetime(2027, 1, 2)).counts['movies'], 1)
        result = self.query(since=datetime.fromisoformat('2025-12-31T18:00:00-06:00'), until=UNTIL)
        self.assertEqual(result.counts, COUNTS)
        # Default now covers the same fixture year-to-date when now is in 2026.
        with patch.object(stats, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 10, 25, tzinfo=timezone.utc)
            self.assertEqual(self.query(since=SINCE).counts, COUNTS)
