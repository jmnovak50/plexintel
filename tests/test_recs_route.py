from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from api import main


class RecsRouteSqlTests(unittest.TestCase):
    def _call_recs(self) -> str:
        class FakeCursor:
            description: list = []

            def __init__(self):
                self.calls = []

            def execute(self, sql, params):
                self.calls.append((sql, params))

            def fetchall(self):
                return []

            def close(self):
                pass

        class FakeConn:
            def __init__(self):
                self.cursor_obj = FakeCursor()

            def cursor(self, *_, **__):
                return self.cursor_obj

            def close(self):
                pass

        conn = FakeConn()

        with patch.object(main, "connect_db", return_value=conn):
            with patch.object(main, "get_setting_value", return_value=0.70):
                asyncio.run(main.get_recommendations(username="member", min_probability=0.70))

        return conn.cursor_obj.calls[0][0]

    def test_recs_route_selects_split_theme_arrays(self):
        sql = self._call_recs()

        self.assertIn("AS title_traits", sql)
        self.assertIn("AS taste_match", sql)
        self.assertIn("recs.semantic_themes", sql)
        self.assertIn("si.dimension >= 0 AND si.dimension < 768", sql)
        self.assertIn("si.dimension >= 768 AND si.dimension < 1536", sql)


if __name__ == "__main__":
    unittest.main()
