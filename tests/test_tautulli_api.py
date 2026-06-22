from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from api.services import tautulli_api


class FakeResponse:
    def __init__(self, *, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class TautulliApiTests(unittest.TestCase):
    def setUp(self):
        self.config = tautulli_api.TautulliConfig(
            api_url="https://tautulli.example.com/api/v2",
            api_key="secret-key",
            base_url="https://tautulli.example.com",
        )

    def test_normalizes_base_url_into_api_url(self):
        config = tautulli_api.resolve_tautulli_config(
            base_url="https://tautulli.example.com/",
            api_key="secret-key",
        )

        self.assertEqual(config.api_url, "https://tautulli.example.com/api/v2")
        self.assertEqual(config.base_url, "https://tautulli.example.com")

    def test_successful_api_envelope_returns_data(self):
        response = FakeResponse(
            payload={"response": {"result": "success", "data": {"users": []}}}
        )

        with patch.object(tautulli_api.requests, "get", return_value=response):
            data = tautulli_api.tautulli_request("get_users", config=self.config)

        self.assertEqual(data, {"users": []})

    def test_auth_failure_has_safe_error_message(self):
        response = FakeResponse(status_code=401, payload={})

        with patch.object(tautulli_api.requests, "get", return_value=response):
            with self.assertRaises(tautulli_api.TautulliApiError) as raised:
                tautulli_api.tautulli_request("get_users", config=self.config)

        self.assertIn("API key", str(raised.exception))
        self.assertNotIn("secret-key", str(raised.exception))

    def test_non_json_response_is_rejected(self):
        response = FakeResponse(json_error=ValueError("not json"))

        with patch.object(tautulli_api.requests, "get", return_value=response):
            with self.assertRaises(tautulli_api.TautulliApiError) as raised:
                tautulli_api.tautulli_request("get_users", config=self.config)

        self.assertIn("non-JSON", str(raised.exception))

    def test_tautulli_error_result_is_rejected(self):
        response = FakeResponse(
            payload={"response": {"result": "error", "message": "bad command"}}
        )

        with patch.object(tautulli_api.requests, "get", return_value=response):
            with self.assertRaises(tautulli_api.TautulliApiError) as raised:
                tautulli_api.tautulli_request("bad_cmd", config=self.config)

        self.assertIn("bad command", str(raised.exception))

    def test_timeout_is_rejected(self):
        with patch.object(
            tautulli_api.requests,
            "get",
            side_effect=requests.Timeout("slow"),
        ):
            with self.assertRaises(tautulli_api.TautulliApiError) as raised:
                tautulli_api.tautulli_request("get_users", config=self.config)

        self.assertIn("timed out", str(raised.exception))

    def test_network_error_does_not_echo_full_url_or_api_key(self):
        with patch.object(
            tautulli_api.requests,
            "get",
            side_effect=requests.ConnectionError(
                "failed for https://tautulli.example.com/api/v2?apikey=secret-key"
            ),
        ):
            with self.assertRaises(tautulli_api.TautulliApiError) as raised:
                tautulli_api.tautulli_request("get_users", config=self.config)

        message = str(raised.exception)
        self.assertIn("failed before a response", message)
        self.assertNotIn("secret-key", message)
        self.assertNotIn("apikey=", message)

    def test_missing_data_is_rejected_when_required(self):
        response = FakeResponse(payload={"response": {"result": "success"}})

        with patch.object(tautulli_api.requests, "get", return_value=response):
            with self.assertRaises(tautulli_api.TautulliApiError) as raised:
                tautulli_api.tautulli_request("get_users", config=self.config)

        self.assertIn("no response data", str(raised.exception))

    def test_delete_cache_sends_exact_command_without_requiring_data(self):
        response = FakeResponse(payload={"response": {"result": "success"}})

        with patch.object(tautulli_api.requests, "get", return_value=response) as mock_get:
            data = tautulli_api.delete_tautulli_cache(config=self.config)

        self.assertIsNone(data)
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["cmd"], "delete_cache")
        self.assertEqual(params["apikey"], "secret-key")
        self.assertEqual(mock_get.call_args.args[0], "https://tautulli.example.com/api/v2")


if __name__ == "__main__":
    unittest.main()
