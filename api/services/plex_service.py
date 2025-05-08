# plex_service.py
import httpx
import os
import uuid
from typing import Optional

PLEX_CLIENT_ID = os.getenv("PLEX_CLIENT_ID") or str(uuid.uuid4())
PLEX_PRODUCT = os.getenv("PLEX_PRODUCT", "PlexIntel")
PLEX_VERSION = os.getenv("PLEX_VERSION", "1.0")
PLEX_API = "https://plex.tv/api/v2"

import xml.etree.ElementTree as ET

def create_plex_pin():
    headers = {
        "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
        "X-Plex-Product": PLEX_PRODUCT,
        "X-Plex-Version": "1.0",
        "X-Plex-Device": "Web",
        "X-Plex-Platform": "Browser",
        "Accept": "application/xml",  # 💡 ensure we ask for XML
    }

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

import xml.etree.ElementTree as ET
import httpx
from typing import Optional

def poll_plex_pin(pin_id: int) -> Optional[str]:
    url = f"{PLEX_API}/pins/{pin_id}"
    headers = {
        "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
        "Accept": "application/xml",
    }

    response = httpx.get(url, headers=headers)

    if response.status_code == 404:
        print(f"❌ PIN {pin_id} not found or expired (404)")
        return None

    response.raise_for_status()

    root = ET.fromstring(response.text)
    auth_token = root.attrib.get("authToken", "")
    return auth_token if auth_token else None

import xml.etree.ElementTree as ET

def get_plex_user_info(token: str) -> dict:
    headers = {"X-Plex-Token": token}
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
    headers = {
        "Accept": "application/json",
        "X-Plex-Product": PLEX_PRODUCT,
        "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
    }
    resp = httpx.get(f"https://plex.tv/api/v2/pins/{pin_id}", headers=headers)
    if resp.status_code != 200:
        raise Exception("Could not fetch PIN")
    return resp.json()
