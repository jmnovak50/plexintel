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
        self.local_count = local_count
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
        self.assertIn("missing a list 'data'", result["error"])

    def test_fetch_pages_detects_incomplete_pagination(self):
        pages = [
            {"recordsFiltered": 3, "data": [{"id": 1}, {"id": 2}]},
            {"recordsFiltered": 3, "data": []},
        ]

        with patch.object(tautulli_sync, "fetch_tautulli_data", side_effect=pages):
            result = tautulli_sync.fetch_watch_history_pages(page_size=2)

        self.assertFalse(result["ok"])
        self.assertIn("got 2 of 3", result["error"])

    def test_sync_reconciles_deleted_watch_rows_and_embeddings(self):
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor(
            local_count=2,
            rowcounts={
                "DELETE FROM watch_embeddings we USING watch_history wh": 1,
                "DELETE FROM watch_history": 1,
                "DELETE FROM watch_embeddings we WHERE NOT EXISTS": 0,
            },
        )
        fetch_result = {
            "ok": True,
            "rows": [
                {
                    "id": "100",
                    "rating_key": "500",
                    "date": "1760000000",
                    "play_duration": 1200,
                    "percent_complete": 95,
                    "media_type": "movie",
                    "user": "jason",
                    "title": "Arrival",
                    "friendly_name": "Jason",
                }
            ],
            "error": None,
        }

        with patch.object(tautulli_sync, "fetch_watch_history_pages", return_value=fetch_result):
            result = tautulli_sync.sync_new_watch_history(conn, cursor)

        self.assertTrue(result)
        self.assertEqual(conn.commit_count, 1)
        self.assertEqual(conn.rollback_count, 0)

        statements = [sql for sql, _params in cursor.executed]
        insert_index = next(i for i, sql in enumerate(statements) if sql.startswith("INSERT INTO watch_history"))
        stale_embedding_index = next(
            i for i, sql in enumerate(statements)
            if sql.startswith("DELETE FROM watch_embeddings we USING watch_history wh")
        )
        stale_watch_index = next(i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM watch_history"))
        orphan_embedding_index = next(
            i for i, sql in enumerate(statements)
            if sql.startswith("DELETE FROM watch_embeddings we WHERE NOT EXISTS")
        )

        self.assertLess(insert_index, stale_embedding_index)
        self.assertLess(stale_embedding_index, stale_watch_index)
        self.assertLess(stale_watch_index, orphan_embedding_index)

        insert_params = cursor.executed[insert_index][1]
        self.assertEqual(insert_params[0], 500)
        self.assertEqual(insert_params[4], 100)
        self.assertIn("we.watch_id::text = wh.watch_id::text", statements[stale_embedding_index])
        self.assertIn("wh.watch_id::text = ANY(%s)", statements[stale_embedding_index])
        self.assertIn("watch_id::text = ANY(%s)", statements[stale_watch_index])
        self.assertIn("wh.watch_id::text = we.watch_id::text", statements[orphan_embedding_index])
        self.assertEqual(cursor.executed[stale_watch_index][1], (["100"],))

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

    def test_sync_aborts_without_deleting_on_malformed_rows(self):
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor(local_count=2)

        with patch.object(
            tautulli_sync,
            "fetch_watch_history_pages",
            return_value={"ok": True, "rows": [{"id": "100"}], "error": None},
        ):
            result = tautulli_sync.sync_new_watch_history(conn, cursor)

        self.assertFalse(result)
        self.assertEqual(conn.commit_count, 0)
        self.assertFalse(any(sql.startswith("DELETE FROM") for sql, _params in cursor.executed))

    def test_sync_aborts_without_deleting_on_suspicious_empty_upstream(self):
        conn = FakeWatchConnection()
        cursor = FakeWatchCursor(local_count=2)

        with patch.object(
            tautulli_sync,
            "fetch_watch_history_pages",
            return_value={"ok": True, "rows": [], "error": None},
        ):
            result = tautulli_sync.sync_new_watch_history(conn, cursor)

        self.assertFalse(result)
        self.assertEqual(conn.commit_count, 0)
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
            {"username": "active", "rating_key": 101},
            {"username": "active", "rating_key": 102},
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


if __name__ == "__main__":
    unittest.main()
