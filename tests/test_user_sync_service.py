from __future__ import annotations

import unittest
from unittest.mock import patch

from api.services import user_sync_service


class FakeCursor:
    def __init__(self, fetchone_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.executed.append((normalized, params))

    def fetchone(self):
        if self.fetchone_values:
            return self.fetchone_values.pop(0)
        return None


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.commit_count = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


class UserSyncServiceTests(unittest.TestCase):
    def test_sync_users_from_tautulli_updates_existing_contact_fields(self):
        cursor = FakeCursor(fetchone_values=[(1, None, None)])
        conn = FakeConnection(cursor)

        with patch.object(
            user_sync_service,
            "fetch_tautulli_users",
            return_value=[
                {
                    "username": "jon",
                    "friendly_name": "Jon Snow",
                    "email": "jon@example.com",
                }
            ],
        ):
            result = user_sync_service.sync_users_from_tautulli(conn=conn, cursor=cursor)

        update_calls = [entry for entry in cursor.executed if "UPDATE public.users" in entry[0]]
        self.assertEqual(result, {"inserted": 0, "updated": 1})
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][1], ("jon@example.com", "Jon Snow", "jon"))

    def test_sync_users_from_tautulli_inserts_missing_users(self):
        cursor = FakeCursor(fetchone_values=[None])
        conn = FakeConnection(cursor)

        with patch.object(
            user_sync_service,
            "fetch_tautulli_users",
            return_value=[
                {
                    "username": "arya",
                    "friendly_name": "Arya Stark",
                    "email": "arya@example.com",
                }
            ],
        ):
            result = user_sync_service.sync_users_from_tautulli(conn=conn, cursor=cursor)

        insert_calls = [entry for entry in cursor.executed if "INSERT INTO public.users" in entry[0]]
        self.assertEqual(result, {"inserted": 1, "updated": 0})
        self.assertEqual(len(insert_calls), 1)
        self.assertEqual(insert_calls[0][1], ("arya", "arya@example.com", "Arya Stark"))


if __name__ == "__main__":
    unittest.main()
