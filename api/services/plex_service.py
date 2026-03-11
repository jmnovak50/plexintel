import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx

from api.services.app_settings import get_setting_value

_DEFAULT_PLEX_CLIENT_ID = str(uuid.uuid4())
PLEX_API = "https://plex.tv/api/v2"
PLEX_DISCOVER_API = "https://discover.provider.plex.tv"
PLEX_WATCHLIST_SUPPORTED_MEDIA_TYPES = {"movie", "show", "series", "tv_show"}


def _build_plex_headers(token: Optional[str] = None, accept: str = "application/xml") -> dict:
    client_id = get_setting_value("plex.client_id", default=_DEFAULT_PLEX_CLIENT_ID)
    product = get_setting_value("plex.product", default="PlexIntel")
    version = get_setting_value("plex.version", default="1.0")
    headers = {
        "X-Plex-Client-Identifier": client_id,
        "X-Plex-Product": product,
        "X-Plex-Version": version,
        "Accept": accept,
    }
    if token:
        headers["X-Plex-Token"] = token
    return headers

def create_plex_pin():
    headers = _build_plex_headers(accept="application/xml")
    headers["X-Plex-Device"] = "Web"
    headers["X-Plex-Platform"] = "Browser"

    resp = httpx.post("https://plex.tv/api/v2/pins", headers=headers)
    resp.raise_for_status()

    # ✅ Parse XML safely
    root = ET.fromstring(resp.text)

    return {
        "id": int(root.attrib["id"]),
        "code": root.attrib["code"],
        "clientIdentifier": root.attrib["clientIdentifier"],
        "qr": root.attrib.get("qr"),
        "authToken": root.attrib.get("authToken"),
        "expiresAt": root.attrib.get("expiresAt"),
    }
def poll_plex_pin(pin_id: int) -> Optional[str]:
    url = f"{PLEX_API}/pins/{pin_id}"
    headers = _build_plex_headers(accept="application/xml")

    response = httpx.get(url, headers=headers)

    if response.status_code == 404:
        print(f"❌ PIN {pin_id} not found or expired (404)")
        return None

    response.raise_for_status()

    root = ET.fromstring(response.text)
    auth_token = root.attrib.get("authToken", "")
    return auth_token if auth_token else None
def get_plex_user_info(token: str) -> dict:
    headers = _build_plex_headers(token=token, accept="application/xml")
    response = httpx.get("https://plex.tv/users/account", headers=headers)

    print(f"📡 get_plex_user_info status={response.status_code}")
    print(f"📭 Content-Type: {response.headers.get('Content-Type')}")
    print(f"📬 Raw response: {response.text}")

    if response.status_code != 200:
        return None

    if "application/xml" in response.headers.get("Content-Type", ""):
        root = ET.fromstring(response.text)
        return {
            "username": root.attrib.get("username"),
            "email": root.attrib.get("email"),
        }

    # fallback if it's unexpectedly JSON
    try:
        data = response.json()
        return {
            "username": data["user"]["username"],
            "email": data["user"].get("email"),
        }
    except Exception as e:
        print(f"❌ Unexpected response format: {e}")
        return None


def get_existing_pin(pin_id):
    # re-fetch the pin by ID
    headers = _build_plex_headers(accept="application/json")
    resp = httpx.get(f"https://plex.tv/api/v2/pins/{pin_id}", headers=headers)
    if resp.status_code != 200:
        raise Exception("Could not fetch PIN")
    return resp.json()


def supports_plex_watchlist(media_type: Optional[str]) -> bool:
    normalized_media_type = (media_type or "").strip().lower()
    return normalized_media_type in PLEX_WATCHLIST_SUPPORTED_MEDIA_TYPES


def plex_guid_to_rating_key(plex_guid: Optional[str]) -> Optional[str]:
    if not plex_guid or "/" not in plex_guid:
        return None
    return plex_guid.rsplit("/", 1)[-1].strip() or None


def get_plex_watchlist_state(token: str, plex_guid: Optional[str]) -> dict:
    rating_key = plex_guid_to_rating_key(plex_guid)
    if not rating_key:
        return {"watchlisted": False, "watchlisted_at": None}

    headers = _build_plex_headers(token=token, accept="application/json")
    response = httpx.get(
        f"{PLEX_DISCOVER_API}/library/metadata/{rating_key}/userState",
        headers=headers,
        timeout=30,
    )

    if response.status_code == 401:
        return {"watchlisted": False, "watchlisted_at": None, "status": "auth_required"}
    response.raise_for_status()

    payload = response.json().get("MediaContainer", {})
    user_state = payload.get("UserState")
    if isinstance(user_state, list):
        user_state = user_state[0] if user_state else {}
    elif user_state is None:
        user_state = {}

    watchlisted_at = user_state.get("watchlistedAt")
    return {
        "watchlisted": bool(watchlisted_at),
        "watchlisted_at": watchlisted_at,
        "status": "synced" if watchlisted_at else "not_watchlisted",
    }


def add_to_plex_watchlist(token: Optional[str], plex_guid: Optional[str], media_type: Optional[str]) -> dict:
    if not supports_plex_watchlist(media_type):
        return {"status": "not_supported", "synced_at": None}
    if not token:
        return {"status": "auth_required", "synced_at": None}

    rating_key = plex_guid_to_rating_key(plex_guid)
    if not rating_key:
        return {"status": "unresolved", "synced_at": None}

    headers = _build_plex_headers(token=token, accept="application/json")
    response = httpx.put(
        f"{PLEX_DISCOVER_API}/actions/addToWatchlist",
        params={"ratingKey": rating_key},
        headers=headers,
        timeout=30,
    )

    if response.status_code == 401:
        return {"status": "auth_required", "synced_at": None}
    if response.status_code >= 400:
        return {"status": "failed", "synced_at": None}

    user_state = get_plex_watchlist_state(token, plex_guid)
    if user_state.get("watchlisted"):
        return {"status": "synced", "synced_at": datetime.utcnow()}
    return {"status": "failed", "synced_at": None}


def remove_from_plex_watchlist(token: Optional[str], plex_guid: Optional[str], media_type: Optional[str]) -> dict:
    if not supports_plex_watchlist(media_type):
        return {"status": "not_supported", "synced_at": None}
    if not token:
        return {"status": "auth_required", "synced_at": None}

    rating_key = plex_guid_to_rating_key(plex_guid)
    if not rating_key:
        return {"status": "unresolved", "synced_at": None}

    headers = _build_plex_headers(token=token, accept="application/json")
    response = httpx.put(
        f"{PLEX_DISCOVER_API}/actions/removeFromWatchlist",
        params={"ratingKey": rating_key},
        headers=headers,
        timeout=30,
    )

    if response.status_code == 401:
        return {"status": "auth_required", "synced_at": None}
    if response.status_code >= 400:
        return {"status": "failed", "synced_at": None}

    user_state = get_plex_watchlist_state(token, plex_guid)
    if user_state.get("watchlisted"):
        return {"status": "failed", "synced_at": None}
    return {"status": "synced", "synced_at": datetime.utcnow()}
