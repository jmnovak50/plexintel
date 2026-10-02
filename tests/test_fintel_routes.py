from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import fintel_routes
from api.services import fintel_service


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed: list[tuple[str, tuple]] = []
        self.closed = False

    def execute(self, sql, params=None):
        self.executed.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return (1,)

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_obj = FakeCursor(rows)
        self.closed = False

    def cursor(self, *_, **__):
        return self.cursor_obj

    def close(self):
        self.closed = True


class FIntelServiceTests(unittest.TestCase):
    def tearDown(self):
        fintel_service.clear_external_id_cache()

    def test_parses_modern_and_legacy_external_ids(self):
        modern = fintel_service.parse_external_ids(
            {"guids": ["tmdb://398978", "imdb://tt1302006", "tvdb://1234"]}
        )
        self.assertEqual(modern.tmdb_id, "398978")
        self.assertEqual(modern.imdb_id, "tt1302006")
        self.assertEqual(modern.tvdb_id, "1234")

        legacy = fintel_service.parse_external_ids(
            {"guid": "com.plexapp.agents.themoviedb://398978?lang=en"}
        )
        self.assertEqual(legacy.tmdb_id, "398978")

    def test_tautulli_failure_returns_empty_ids_and_is_not_cached(self):
        with patch.object(
            fintel_service,
            "fetch_tautulli_metadata",
            side_effect=RuntimeError("offline"),
        ) as fetch:
            self.assertEqual(fintel_service.resolve_external_ids(1), fintel_service.ExternalIds())
            self.assertEqual(fintel_service.resolve_external_ids(1), fintel_service.ExternalIds())
        self.assertEqual(fetch.call_count, 2)

    def test_external_ids_are_cached(self):
        with patch.object(
            fintel_service,
            "fetch_tautulli_metadata",
            return_value={"guids": ["tmdb://10"]},
        ) as fetch:
            first = fintel_service.resolve_external_ids(1)
            second = fintel_service.resolve_external_ids(1)
        self.assertEqual(first, second)
        self.assertEqual(fetch.call_count, 1)

    def test_recommendations_keep_query_order_and_shape(self):
        conn = FakeConnection(
            [
                {
                    "rating_key": 10,
                    "title": "First",
                    "year": 2020,
                    "predicted_probability": Decimal("0.99"),
                },
                {
                    "rating_key": 11,
                    "title": "Second",
                    "year": 2019,
                    "predicted_probability": Decimal("0.80"),
                },
            ]
        )
        with (
            patch.object(fintel_service, "connect_db", return_value=conn),
            patch.object(fintel_service, "get_setting_value", return_value=0.7),
            patch.object(
                fintel_service,
                "resolve_external_ids",
                side_effect=[fintel_service.ExternalIds(tmdb_id="1"), fintel_service.ExternalIds(imdb_id="tt2")],
            ),
        ):
            result = fintel_service.fetch_fintel_recommendations(
                username="member",
                media_type="movie",
                limit=2,
            )

        self.assertEqual([item["rating_key"] for item in result], [10, 11])
        self.assertEqual(result[0]["tmdb_id"], "1")
        self.assertEqual(result[1]["imdb_id"], "tt2")
        sql, params = conn.cursor_obj.executed[0]
        self.assertIn("ORDER BY predicted_probability DESC NULLS LAST, rating_key ASC", sql)
        self.assertTrue(sql.endswith("LIMIT %s"))
        self.assertEqual(params[-1], 2)


class FIntelRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(fintel_routes.router)
        self.client = TestClient(app)

    def test_rejects_missing_or_invalid_api_key(self):
        with patch.object(fintel_routes, "get_setting_value", return_value="secret"):
            self.assertEqual(self.client.get("/api/fintel/v1/health").status_code, 401)
            self.assertEqual(
                self.client.get("/api/fintel/v1/health", headers={"X-API-Key": "wrong"}).status_code,
                401,
            )

    def test_health_checks_database(self):
        with (
            patch.object(fintel_routes, "get_setting_value", return_value="secret"),
            patch.object(fintel_routes, "check_fintel_health") as health,
        ):
            response = self.client.get("/api/fintel/v1/health", headers={"X-API-Key": "secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok", "schema_version": 1})
        health.assert_called_once_with()

    def test_recommendations_validate_limit_and_return_contract(self):
        recommendations = [
            {
                "rating_key": 123,
                "title": "The Irishman",
                "year": 2019,
                "media_type": "movie",
                "probability": 0.993,
                "tmdb_id": "398978",
                "imdb_id": "tt1302006",
                "tvdb_id": None,
            }
        ]
        with (
            patch.object(fintel_routes, "get_setting_value", return_value="secret"),
            patch.object(fintel_routes, "fetch_fintel_recommendations", return_value=recommendations) as fetch,
        ):
            response = self.client.get(
                "/api/fintel/v1/recommendations?username=jmnovak&limit=1",
                headers={"X-API-Key": "secret"},
            )
            invalid = self.client.get(
                "/api/fintel/v1/recommendations?username=jmnovak&limit=101",
                headers={"X-API-Key": "secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendations"], recommendations)
        self.assertEqual(invalid.status_code, 422)
        fetch.assert_called_once_with(username="jmnovak", media_type="movie", limit=1)


if __name__ == "__main__":
    unittest.main()
