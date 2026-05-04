from __future__ import annotations

import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from api.routes import poster_routes
from api.services import poster_service


def _response(status_code: int, content_type: str):
    return SimpleNamespace(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=b"",
    )


class PosterRouteTests(unittest.TestCase):
    def setUp(self):
        poster_service.fetch_tautulli_server_identifier.cache_clear()

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

    def test_resize_poster_image_to_width_preserves_aspect_ratio(self):
        source = BytesIO()
        Image.new("RGB", (600, 900), color=(32, 64, 128)).save(source, format="PNG")

        payload = poster_service.resize_poster_image_to_width(source.getvalue(), "image/png", width=180)

        self.assertEqual(payload["content_type"], "image/jpeg")
        with Image.open(BytesIO(payload["content"])) as resized:
            self.assertEqual(resized.width, 180)
            self.assertEqual(resized.height, 270)

    def test_resize_poster_image_to_width_never_upscales(self):
        source = BytesIO()
        Image.new("RGB", (120, 180), color=(32, 64, 128)).save(source, format="PNG")
        source_bytes = source.getvalue()

        payload = poster_service.resize_poster_image_to_width(source_bytes, "image/png", width=240)

        self.assertEqual(payload["content"], source_bytes)
        self.assertEqual(payload["content_type"], "image/png")

    def test_build_public_poster_url_can_include_width(self):
        with patch.object(
            poster_service,
            "get_setting_value",
            return_value="https://plexintel.example.com/",
        ):
            self.assertEqual(
                poster_service.build_public_poster_url(42, width=240),
                "https://plexintel.example.com/api/posters/42?w=240",
            )

    def test_build_plex_item_url_uses_server_identifier_when_configured(self):
        def fake_get_setting_value(key: str, default=None):
            values = {
                "plex.web_base_url": "https://app.plex.tv/desktop/",
                "plex.server_identifier": "server id",
            }
            return values.get(key, default)

        with patch.object(poster_service, "get_setting_value", side_effect=fake_get_setting_value):
            self.assertEqual(
                poster_service.build_plex_item_url(42),
                "https://app.plex.tv/desktop/#!/server/server%20id/details?key=%2Flibrary%2Fmetadata%2F42",
            )

    def test_build_plex_item_url_fetches_server_identifier_from_tautulli(self):
        def fake_get_setting_value(key: str, default=None):
            values = {
                "plex.web_base_url": "https://app.plex.tv/desktop",
                "plex.server_identifier": None,
                "tautulli.api_url": "https://tautulli.example.com/api/v2",
                "tautulli.api_key": "secret-key",
            }
            return values.get(key, default)

        with patch.object(poster_service, "get_setting_value", side_effect=fake_get_setting_value):
            with patch.object(
                poster_service.requests,
                "get",
                return_value=SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {
                        "response": {
                            "data": {
                                "pms_identifier": "server id",
                            },
                        },
                    },
                ),
            ) as mock_get:
                self.assertEqual(
                    poster_service.build_plex_item_url(42),
                    "https://app.plex.tv/desktop/#!/server/server%20id/details?key=%2Flibrary%2Fmetadata%2F42",
                )
                self.assertEqual(mock_get.call_count, 1)

    def test_build_plex_item_url_returns_none_without_server_identifier(self):
        def fake_get_setting_value(key: str, default=None):
            values = {
                "plex.web_base_url": "https://app.plex.tv/desktop",
                "plex.server_identifier": None,
                "tautulli.api_url": None,
                "tautulli.api_key": None,
            }
            return values.get(key, default)

        with patch.object(poster_service, "get_setting_value", side_effect=fake_get_setting_value):
            self.assertIsNone(poster_service.build_plex_item_url(42))

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

    def test_public_poster_route_returns_image_without_session(self):
        image = BytesIO()
        Image.new("RGB", (12, 18), color=(32, 64, 128)).save(image, format="PNG")

        with patch.object(
            poster_routes,
                "fetch_poster_image_for_rating_key",
                return_value={"content": image.getvalue(), "content_type": "image/png"},
        ):
            response = poster_routes.get_poster(42)

        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=3600")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertTrue(response.body)

    def test_public_poster_route_resizes_when_width_is_requested(self):
        image = BytesIO()
        Image.new("RGB", (600, 900), color=(32, 64, 128)).save(image, format="PNG")

        with patch.object(
            poster_routes,
            "fetch_poster_image_for_rating_key",
            return_value={"content": image.getvalue(), "content_type": "image/png"},
        ):
            response = poster_routes.get_poster(42, w=180)

        self.assertEqual(response.media_type, "image/jpeg")
        with Image.open(BytesIO(response.body)) as resized:
            self.assertEqual(resized.width, 180)
            self.assertEqual(resized.height, 270)

    def test_public_poster_route_thumb_uses_thumbnail_width(self):
        image = BytesIO()
        Image.new("RGB", (600, 900), color=(32, 64, 128)).save(image, format="PNG")

        with patch.object(
            poster_routes,
            "fetch_poster_image_for_rating_key",
            return_value={"content": image.getvalue(), "content_type": "image/png"},
        ):
            response = poster_routes.get_poster(42, thumb=True)

        self.assertEqual(response.media_type, "image/jpeg")
        with Image.open(BytesIO(response.body)) as resized:
            self.assertEqual(resized.width, 180)
            self.assertEqual(resized.height, 270)


if __name__ == "__main__":
    unittest.main()
