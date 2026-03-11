from typing import Optional

import requests

from api.services.app_settings import get_setting_value


def fetch_tautulli_metadata(rating_key: int) -> Optional[dict]:
    api_url = get_setting_value("tautulli.api_url")
    api_key = get_setting_value("tautulli.api_key")
    if not api_url or not api_key:
        return None

    response = requests.get(
        api_url,
        params={
            "apikey": api_key,
            "cmd": "get_metadata",
            "rating_key": rating_key,
        },
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    return payload.get("response", {}).get("data")


def load_library_item(cur, rating_key: int) -> Optional[dict]:
    cur.execute(
        """
        SELECT
            rating_key,
            title,
            media_type,
            show_title,
            parent_rating_key,
            show_rating_key,
            plex_guid
        FROM public.library
        WHERE rating_key = %s
        """,
        (rating_key,),
    )
    return cur.fetchone()


def ensure_library_guid(cur, rating_key: int) -> Optional[dict]:
    item = load_library_item(cur, rating_key)
    if not item:
        return None

    if item.get("plex_guid"):
        return item

    try:
        metadata = fetch_tautulli_metadata(rating_key)
    except Exception:
        return item
    if not metadata:
        return item

    plex_guid = metadata.get("guid")
    if not plex_guid:
        return item

    cur.execute(
        """
        UPDATE public.library
        SET plex_guid = %s
        WHERE rating_key = %s
        """,
        (plex_guid, rating_key),
    )
    item["plex_guid"] = plex_guid
    return item
