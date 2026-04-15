from typing import Mapping, Optional, Any

import requests
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value


def _normalize_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip()
    return normalized or None


def resolve_poster_path(
    media_type: Optional[str],
    thumb_path: Optional[str],
    parent_thumb_path: Optional[str],
    grandparent_thumb_path: Optional[str],
) -> Optional[str]:
    media_type_key = (media_type or "").strip().lower()

    thumb = _normalize_path(thumb_path)
    parent_thumb = _normalize_path(parent_thumb_path)
    grandparent_thumb = _normalize_path(grandparent_thumb_path)

    if media_type_key in {"movie", "show", "series"}:
        return thumb

    if media_type_key == "season":
        return thumb or parent_thumb

    if media_type_key == "episode":
        return parent_thumb or grandparent_thumb or thumb

    return thumb or parent_thumb or grandparent_thumb


def resolve_poster_path_from_row(row: Mapping[str, Any]) -> Optional[str]:
    return resolve_poster_path(
        media_type=row.get("media_type"),
        thumb_path=row.get("thumb_path"),
        parent_thumb_path=row.get("parent_thumb_path"),
        grandparent_thumb_path=row.get("grandparent_thumb_path"),
    )


def build_poster_url(rating_key: Any) -> Optional[str]:
    if rating_key is None:
        return None
    return f"/api/posters/{rating_key}"


def _is_image_response(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    return response.status_code == 200 and content_type.startswith("image/")


def fetch_tautulli_image(poster_path: str) -> requests.Response:
    last_error = None
    tautulli_url = get_setting_value("tautulli.base_url")
    tautulli_api_url = get_setting_value("tautulli.api_url")
    tautulli_api_key = get_setting_value("tautulli.api_key")

    if tautulli_url:
        proxy_url = f"{tautulli_url.rstrip('/')}/pms_image_proxy"
        try:
            direct_response = requests.get(
                proxy_url,
                params={"img": poster_path, "apikey": tautulli_api_key},
                allow_redirects=False,
                timeout=20,
            )
            if _is_image_response(direct_response):
                return direct_response
        except requests.RequestException as exc:
            last_error = exc

    if tautulli_api_url:
        try:
            api_response = requests.get(
                tautulli_api_url,
                params={
                    "cmd": "pms_image_proxy",
                    "apikey": tautulli_api_key,
                    "img": poster_path,
                },
                timeout=20,
            )
            if _is_image_response(api_response):
                return api_response
        except requests.RequestException as exc:
            last_error = exc

    if last_error:
        raise RuntimeError(f"Unable to fetch poster from Tautulli: {last_error}") from last_error

    raise RuntimeError("Unable to fetch poster from Tautulli.")


def fetch_poster_image_for_rating_key(
    rating_key: Any,
    *,
    allow_unconfigured: bool = False,
) -> Optional[dict[str, Any]]:
    tautulli_url = get_setting_value("tautulli.base_url")
    tautulli_api_url = get_setting_value("tautulli.api_url")
    tautulli_api_key = get_setting_value("tautulli.api_key")

    if not tautulli_api_key or (not tautulli_url and not tautulli_api_url):
        if allow_unconfigured:
            return None
        raise RuntimeError("Poster proxy is not configured.")

    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT media_type, thumb_path, parent_thumb_path, grandparent_thumb_path
                FROM library
                WHERE rating_key = %s
                """,
                (rating_key,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    poster_path = resolve_poster_path_from_row(row)
    if not poster_path:
        return None

    response = fetch_tautulli_image(poster_path)
    return {
        "content": response.content,
        "content_type": response.headers.get("Content-Type", "image/jpeg"),
    }
