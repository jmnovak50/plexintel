from __future__ import annotations

import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from api.services import poster_service


def _response(status_code: int, content_type: str):
    return SimpleNamespace(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=b"",
    )


class PosterRouteTests(unittest.TestCase):
    def test_is_image_response_requires_image_content_type(self):
        self.assertTrue(poster_service._is_image_response(_response(200, "image/png")))
        self.assertFalse(poster_service._is_image_response(_response(200, "text/html;charset=utf-8")))
        self.assertFalse(poster_service._is_image_response(_response(303, "image/png")))

    def test_optimize_poster_image_resizes_and_converts_to_jpeg(self):
        source = BytesIO()
        Image.new("RGBA", (440, 660), color=(32, 64, 128, 255)).save(source, format="PNG")

        payload = poster_service.optimize_poster_image(source.getvalue(), "image/png")

        self.assertEqual(payload["content_type"], "image/jpeg")
        with Image.open(BytesIO(payload["content"])) as optimized:
            self.assertEqual(optimized.format, "JPEG")
            self.assertLessEqual(optimized.width, 220)
            self.assertLessEqual(optimized.height, 330)

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

        with patch.object(poster_service, "get_setting_value", side_effect=fake_get_setting_value):
            with patch.object(
                poster_service.requests,
                "get",
                side_effect=[direct_response, api_response],
            ) as mock_get:
                response = poster_service.fetch_tautulli_image("/library/metadata/123/thumb/456")

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

        with patch.object(poster_service, "get_setting_value", side_effect=fake_get_setting_value):
            with patch.object(
                poster_service.requests,
                "get",
                side_effect=[direct_response, api_response],
            ):
                with self.assertRaises(RuntimeError) as raised:
                    poster_service.fetch_tautulli_image("/library/metadata/123/thumb/456")

        self.assertEqual(str(raised.exception), "Unable to fetch poster from Tautulli.")


if __name__ == "__main__":
    unittest.main()
