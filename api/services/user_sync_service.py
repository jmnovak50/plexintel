from __future__ import annotations

from typing import Any

import requests

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value


def fetch_tautulli_users() -> list[dict[str, Any]]:
    api_url = get_setting_value("tautulli.api_url")
    api_key = get_setting_value("tautulli.api_key")
    if not api_url or not api_key:
        return []

    response = requests.get(
        api_url,
        params={"apikey": api_key, "cmd": "get_users"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("response", {}).get("data", {})

    if isinstance(data, list):
        users = data
    elif isinstance(data, dict):
        users = data.get("users")
        if users is None and isinstance(data.get("data"), list):
            users = data["data"]
    else:
        users = []

    return users if isinstance(users, list) else []


def sync_users_from_tautulli(conn=None, cursor=None) -> dict[str, int]:
    owns_connection = conn is None or cursor is None
    if owns_connection:
        conn = connect_db()
        cursor = conn.cursor()

    users = fetch_tautulli_users()
    inserted = 0
    updated = 0

    try:
        for raw_user in users:
            if not isinstance(raw_user, dict):
                continue

            username = (raw_user.get("username") or raw_user.get("friendly_name") or "").strip()
            if not username:
                continue

            friendly_name = (raw_user.get("friendly_name") or "").strip() or None
            email = (raw_user.get("email") or "").strip() or None

            cursor.execute(
                """
                SELECT user_id, plex_email, friendly_name
                FROM public.users
                WHERE username = %s
                """,
                (username,),
            )
            existing = cursor.fetchone()

            if existing:
                if isinstance(existing, dict):
                    existing_email = existing.get("plex_email")
                    existing_friendly_name = existing.get("friendly_name")
                else:
                    existing_email = existing[1] if len(existing) > 1 else None
                    existing_friendly_name = existing[2] if len(existing) > 2 else None
                if existing_email != email or existing_friendly_name != friendly_name:
                    cursor.execute(
                        """
                        UPDATE public.users
                        SET
                            plex_email = %s,
                            friendly_name = %s,
                            modified_at = now()
                        WHERE username = %s
                        """,
                        (email, friendly_name, username),
                    )
                    updated += 1
                continue

            cursor.execute(
                """
                INSERT INTO public.users (username, plex_email, friendly_name, created_at, modified_at)
                VALUES (%s, %s, %s, now(), now())
                """,
                (username, email, friendly_name),
            )
            inserted += 1

        if owns_connection:
            conn.commit()
    finally:
        if owns_connection:
            conn.close()

    return {"inserted": inserted, "updated": updated}
