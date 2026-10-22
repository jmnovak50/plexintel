from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

import build_user_embeddings
import fetch_tautulli_data as tautulli_sync


def compact_sql(sql):
    return " ".join(str(sql).split())


class FakeWatchCursor:
    def __init__(self, *, local_count=0, rowcounts=None):
        self.local_count = None
        self.rowcounts = rowcounts or {}
        self.executed = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        normalized = compact_sql(sql)
        self.executed.append((normalized, params))
        self.rowcount = 0
        for prefix, rowcount in self.rowcounts.items():
            if normalized.startswith(prefix):
                self.rowcount = rowcount
                break

    def fetchone(self):
        return (self.local_count,)


class FakeWatchConnection:
    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


class FakeIncrementalCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((compact_sql(sql), params))

    def fetchall(self):
        return []


class FakeIncrementalConnection:
    def __init__(self):
        self.cursor_obj = FakeIncrementalCursor()
        self.commit_count = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


class TautulliWatchReconciliationTests(unittest.TestCase):
    def test_incremental_load_clears_cache_before_listing_libraries(self):
        conn = FakeIncrementalConnection()
        events = []

        def fake_clear_cache():
            events.append("clear_cache")

        def fake_get_library_media_info(section_id, limit=None):
            events.append(f"library_{section_id}")
            return []

        with patch.object(tautulli_sync, "connect_to_db", return_value=(conn, conn.cursor_obj)):
            with patch.object(tautulli_sync, "clear_tautulli_cache", side_effect=fake_clear_cache):
                with patch.object(tautulli_sync, "sync_users_from_tautulli"):
                    with patch.object(
                        tautulli_sync,
                        "get_library_media_info",
                        side_effect=fake_get_library_media_info,
                    ):
                        with patch.object(tautulli_sync, "backfill_missing_header_records"):
                            with patch.object(tautulli_sync, "backfill_missing_plex_guids"):
                                with patch.object(tautulli_sync, "sync_new_watch_history"):
                                    with patch.object(tautulli_sync, "get_setting_value", return_value=False):
                                        tautulli_sync.run_incremental_load()

        self.assertIn("clear_cache", events)
        self.assertIn("library_1", events)
        self.assertLess(events.index("clear_cache"), events.index("library_1"))
        self.assertTrue(conn.closed)

    def test_fetch_pages_detects_malformed_payload(self):
        with patch.object(tautulli_sync, "fetch_tautulli_data", return_value={}):
            result = tautulli_sync.fetch_watch_history_pages(page_size=2)

        self.assertFalse(result["ok"])
        self.assertIn("history pagination", result["error"])

    def test_fetch_pages_detects_incomplete_pagination(self):
        pages = [
            {"recordsFiltered": 3, "data": [{"id": 1}, {"id": 2}]},
            {"recordsFiltered": 3, "data": []},
        ]

        with patch.object(tautulli_sync, "fetch_tautulli_data", side_effect=pages):
            result = tautulli_sync.fetch_watch_history_pages(page_size=2)

        self.assertFalse(result["ok"])
        self.assertIn("history pagination", result["error"])

    def test_sync_preserves_history_and_embeddings_and_uses_date_window(self):
        from datetime import datetime
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor()
        cursor.local_count = datetime(2026, 10, 20)
        with patch.object(tautulli_sync, "fetch_watch_history_pages", return_value={
            "ok": True, "rows": [{"id": "100", "rating_key": "500"}],
        }) as fetch, patch.object(tautulli_sync, "store_watch_history", return_value={}) as store:
            self.assertTrue(tautulli_sync.sync_new_watch_history(conn, cursor))
        fetch.assert_called_once_with(after_ts="2026-09-19")
        store.assert_called_once()
        self.assertEqual(conn.commit_count, 1)
        self.assertFalse(any(sql.startswith("DELETE") for sql, _ in cursor.executed))

    def test_sync_aborts_without_deleting_on_fetch_failure(self):
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor(local_count=2)

        with patch.object(
            tautulli_sync,
            "fetch_watch_history_pages",
            return_value={"ok": False, "rows": [], "error": "network failure"},
        ):
            result = tautulli_sync.sync_new_watch_history(conn, cursor)

        self.assertFalse(result)
        self.assertEqual(conn.commit_count, 0)
        self.assertFalse(any(sql.startswith("DELETE FROM") for sql, _params in cursor.executed))

    def test_sync_skips_malformed_rows_without_deleting(self):
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor(local_count=2)

        with patch.object(
            tautulli_sync,
            "fetch_watch_history_pages",
            return_value={"ok": True, "rows": [{"id": "100"}], "error": None},
        ):
            result = tautulli_sync.sync_new_watch_history(conn, cursor)

        self.assertTrue(result)
        self.assertEqual(conn.commit_count, 1)
        self.assertFalse(any(sql.startswith("DELETE FROM") for sql, _params in cursor.executed))

    def test_sync_preserves_rows_on_empty_upstream(self):
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor(local_count=2)

        with patch.object(
            tautulli_sync,
            "fetch_watch_history_pages",
            return_value={"ok": True, "rows": [], "error": None},
        ):
            result = tautulli_sync.sync_new_watch_history(conn, cursor)

        self.assertTrue(result)
        self.assertEqual(conn.commit_count, 1)
        self.assertFalse(any(sql.startswith("DELETE FROM") for sql, _params in cursor.executed))


class FakeUserEmbeddingCursor:
    def __init__(self, conn):
        self.conn = conn
        self.fetchone_result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized = compact_sql(sql)
        self.conn.operations.append((normalized, params))

        if normalized.startswith("SELECT embedding FROM media_embeddings"):
            rating_key = params[0]
            embedding = self.conn.media_embeddings.get(rating_key)
            self.fetchone_result = (embedding,) if embedding is not None else None
        elif normalized.startswith("DELETE FROM user_embeddings"):
            self.conn.deleted_user_embeddings = True
        elif normalized.startswith("INSERT INTO user_embeddings"):
            self.conn.inserted_user_embeddings.append(params)

    def fetchone(self):
        return self.fetchone_result


class FakeUserEmbeddingConnection:
    def __init__(self, media_embeddings):
        self.media_embeddings = media_embeddings
        self.operations = []
        self.inserted_user_embeddings = []
        self.deleted_user_embeddings = False
        self.commit_count = 0

    def cursor(self):
        return FakeUserEmbeddingCursor(self)

    def commit(self):
        self.commit_count += 1


class UserEmbeddingRebuildTests(unittest.TestCase):
    def test_rebuild_clears_stale_user_embeddings_before_insert(self):
        conn = FakeUserEmbeddingConnection(
            media_embeddings={
                101: np.array([1.0, 0.0], dtype=np.float32),
                102: np.array([0.0, 1.0], dtype=np.float32),
            }
        )
        watch_history = [
            {"username": "active", "rating_key": 101, "watch_count": 1,
             "max_engagement_ratio": 0.75, "media_embedding": np.array([1.0, 0.0])},
            {"username": "active", "rating_key": 102, "watch_count": 1,
             "max_engagement_ratio": 0.75, "media_embedding": np.array([0.0, 1.0])},
        ]

        build_user_embeddings.build_user_embeddings(watch_history, conn)

        self.assertTrue(conn.deleted_user_embeddings)
        self.assertEqual(conn.commit_count, 1)
        self.assertEqual(len(conn.inserted_user_embeddings), 1)
        self.assertEqual(conn.inserted_user_embeddings[0][0], "active")

        delete_index = next(
            i for i, (sql, _params) in enumerate(conn.operations)
            if sql.startswith("DELETE FROM user_embeddings")
        )
        insert_index = next(
            i for i, (sql, _params) in enumerate(conn.operations)
            if sql.startswith("INSERT INTO user_embeddings")
        )
        self.assertLess(delete_index, insert_index)

    def test_rebuild_averages_pgvector_values_as_numeric_arrays(self):
        conn = FakeUserEmbeddingConnection(
            media_embeddings={
                101: build_user_embeddings.Vector([1.0, 0.0]),
                102: build_user_embeddings.Vector([0.0, 1.0]),
            }
        )
        watch_history = [
            {"username": "active", "rating_key": 101, "watch_count": 1,
             "max_engagement_ratio": 0.75,
             "media_embedding": build_user_embeddings.Vector([1.0, 0.0])},
            {"username": "active", "rating_key": 102, "watch_count": 1,
             "max_engagement_ratio": 0.75,
             "media_embedding": build_user_embeddings.Vector([0.0, 1.0])},
        ]

        build_user_embeddings.build_user_embeddings(watch_history, conn)

        stored_embedding = conn.inserted_user_embeddings[0][1]
        np.testing.assert_allclose(
            stored_embedding.to_numpy(),
            np.array([0.5, 0.5], dtype=np.float32),
        )




class WatchHistoryMetricsTests(unittest.TestCase):
    def test_fetch_metrics_cover_every_page_without_logging_source_payloads(self):
        from contextlib import redirect_stdout
        from io import StringIO
        output = StringIO()
        pages = [
            {'recordsFiltered': 2, 'data': [{'id': 1, 'rating_key': 5, 'ip_address': '192.0.2.99'}]},
            {'recordsFiltered': 2, 'data': [{'id': 2, 'rating_key': 5}]},
        ]
        with patch.object(tautulli_sync, 'fetch_tautulli_data', side_effect=pages), redirect_stdout(output):
            result = tautulli_sync.fetch_watch_history_pages(page_size=1)
        self.assertTrue(result['ok'])
        self.assertEqual(result['metrics']['pages'], 2)
        self.assertEqual(result['metrics']['rows'], 2)
        self.assertGreaterEqual(result['metrics']['fetch_seconds'], 0)
        self.assertNotIn('192.0.2.99', output.getvalue())

    def test_sync_metrics_report_committed_counts_and_duration(self):
        import json
        from contextlib import redirect_stdout
        from io import StringIO
        conn, cursor, output = FakeWatchConnection(), FakeWatchCursor(), StringIO()
        with patch.object(tautulli_sync, 'fetch_watch_history_pages', return_value={
            'ok': True, 'rows': [{'id': i + 1, 'rating_key': 5} for i in range(12)],
            'metrics': {'pages': 1, 'fetch_seconds': 0.1},
        }), patch.object(tautulli_sync, 'store_watch_history', return_value={
            'inserted': 0, 'updated': 0, 'unchanged': 12, 'skipped': 0, 'failed': 0,
        }), redirect_stdout(output):
            self.assertTrue(tautulli_sync.sync_new_watch_history(conn, cursor))
        metrics = json.loads(output.getvalue().split('Watch history sync metrics: ')[1])
        self.assertEqual(metrics['status'], 'committed')
        self.assertEqual(metrics['unchanged'], 12)
        self.assertEqual(metrics['rows'], 12)
        self.assertEqual(metrics['pages'], 1)
        for key in ('watermark_seconds', 'fetch_seconds', 'persistence_seconds', 'total_seconds'):
            self.assertGreaterEqual(metrics[key], 0)

    def test_empty_history_still_records_the_api_page_request(self):
        with patch.object(tautulli_sync, 'fetch_tautulli_data', return_value={
            'recordsFiltered': 0, 'data': [],
        }):
            result = tautulli_sync.fetch_watch_history_pages()
        self.assertTrue(result['ok'])
        self.assertEqual(result['metrics']['pages'], 1)
        self.assertEqual(result['metrics']['rows'], 0)


if __name__ == "__main__":
    unittest.main()
