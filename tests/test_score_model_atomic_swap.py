from __future__ import annotations

import unittest

import score_model


class FakeSqlAlchemyConnection:
    def __init__(self):
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.statements.append(str(statement))


class FakeSqlAlchemyEngine:
    def __init__(self):
        self.conn = FakeSqlAlchemyConnection()

    def begin(self):
        return self.conn


class RecommendationAtomicSwapTests(unittest.TestCase):
    def test_prepare_staging_table_uses_recommendations_like_schema(self):
        engine = FakeSqlAlchemyEngine()

        score_model.prepare_recommendations_staging_table(engine)

        sql = "\n".join(engine.conn.statements)
        self.assertIn("DROP TABLE IF EXISTS public.recommendations_new", sql)
        self.assertIn("CREATE TABLE public.recommendations_new", sql)
        self.assertIn("LIKE public.recommendations", sql)

    def test_swap_recommendations_from_staging_does_not_truncate_live_table(self):
        engine = FakeSqlAlchemyEngine()

        score_model.swap_recommendations_from_staging(engine)

        sql = "\n".join(engine.conn.statements)
        self.assertIn("LOCK TABLE public.recommendations IN EXCLUSIVE MODE", sql)
        self.assertIn("DELETE FROM public.recommendations", sql)
        self.assertIn("INSERT INTO public.recommendations", sql)
        self.assertIn("FROM public.recommendations_new", sql)
        self.assertNotIn("TRUNCATE", sql.upper())


if __name__ == "__main__":
    unittest.main()
