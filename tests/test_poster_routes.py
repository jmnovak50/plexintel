from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from api.routes import poster_routes


def _response(status_code: int, content_type: str):
    return SimpleNamespace(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=b"",
    )


class PosterRouteTests(unittest.TestCase):
    def test_is_image_response_requires_image_content_type(self):
        self.assertTrue(poster_routes._is_image_response(_response(200, "image/png")))
        self.assertFalse(poster_routes._is_image_response(_response(200, "text/html;charset=utf-8")))
        self.assertFalse(poster_routes._is_image_response(_response(303, "image/png")))

    def test_fetch_tautulli_image_falls_back_to_api_proxy_when_direct_proxy_returns_html(self):
        direct_response = _response(200, "text/html;charset=utf-8")
        api_response = _response(200, "image/png")

        def fake_get_setting_value(key: str):
            values = {
                "tautulli.base_url": "https://tautulli.example.com",
                "tautulli.api_url": "https://tautulli.example.com/api/v2",
                "tautulli.api_key": "secret-key",
            }
            return values.get(key)

        with patch.object(poster_routes, "get_setting_value", side_effect=fake_get_setting_value):
            with patch.object(
                poster_routes.requests,
                "get",
                side_effect=[direct_response, api_response],
            ) as mock_get:
                response = poster_routes._fetch_tautulli_image("/library/metadata/123/thumb/456")

        self.assertIs(response, api_response)
        self.assertEqual(mock_get.call_count, 2)
        direct_call = mock_get.call_args_list[0]
        self.assertEqual(direct_call.kwargs["allow_redirects"], False)
        self.assertEqual(
            direct_call.kwargs["params"],
            {"img": "/library/metadata/123/thumb/456", "apikey": "secret-key"},
        )

    def test_fetch_tautulli_image_raises_when_no_proxy_returns_image(self):
        direct_response = _response(200, "text/html;charset=utf-8")
        api_response = _response(200, "application/json")

        def fake_get_setting_value(key: str):
            values = {
                "tautulli.base_url": "https://tautulli.example.com",
                "tautulli.api_url": "https://tautulli.example.com/api/v2",
                "tautulli.api_key": "secret-key",
            }
            return values.get(key)

        with patch.object(poster_routes, "get_setting_value", side_effect=fake_get_setting_value):
            with patch.object(
                poster_routes.requests,
                "get",
                side_effect=[direct_response, api_response],
            ):
                with self.assertRaises(HTTPException) as raised:
                    poster_routes._fetch_tautulli_image("/library/metadata/123/thumb/456")

        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
