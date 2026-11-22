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

    payload = response.json().get("response", {})
    if payload.get("result") != "success":
        return None
    return payload.get("data")


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
    from api.services.metadata_ingestion import row_dict
    return row_dict(cur, cur.fetchone())


def ensure_library_guid(cur, rating_key: int) -> Optional[dict]:
    item = load_library_item(cur, rating_key)
    if not item:
        return None

    if item.get("plex_guid"):
        return item

    from api.services.metadata_ingestion import guid_plan, apply_plan
    # Fetch before acquiring metadata write locks. The caller owns commit.
    try:
        raw = fetch_tautulli_metadata(rating_key)
    except Exception:
        return item
    cur.execute('SAVEPOINT metadata_guid_completion')
    try:
        plan = guid_plan(cur, rating_key, raw, operator='feedback')
        if plan:
            apply_plan(cur, plan)
        item = load_library_item(cur, rating_key)
        cur.execute('RELEASE SAVEPOINT metadata_guid_completion')
    except Exception:
        cur.execute('ROLLBACK TO SAVEPOINT metadata_guid_completion')
        cur.execute('RELEASE SAVEPOINT metadata_guid_completion')
        print('Metadata GUID completion deferred; feedback remains available')
    return item
