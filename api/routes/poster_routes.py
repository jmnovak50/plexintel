import os

import psycopg2
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, Response
from psycopg2.extras import RealDictCursor

from api.services.poster_service import resolve_poster_path_from_row

load_dotenv()

router = APIRouter()

DB_URL = os.getenv("DATABASE_URL")
TAUTULLI_URL = os.getenv("TAUTULLI_URL")
TAUTULLI_API_URL = os.getenv("TAUTULLI_API_URL")
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")


def _fetch_tautulli_image(poster_path: str) -> requests.Response:
    last_error = None

    if TAUTULLI_URL:
        proxy_url = f"{TAUTULLI_URL.rstrip('/')}/pms_image_proxy"
        try:
            direct_response = requests.get(
                proxy_url,
                params={"img": poster_path, "apikey": TAUTULLI_API_KEY},
                timeout=20,
            )
            if direct_response.status_code == 200:
                return direct_response
        except requests.RequestException as exc:
            last_error = exc

    if TAUTULLI_API_URL:
        try:
            api_response = requests.get(
                TAUTULLI_API_URL,
                params={
                    "cmd": "pms_image_proxy",
                    "apikey": TAUTULLI_API_KEY,
                    "img": poster_path,
                },
                timeout=20,
            )
            if api_response.status_code == 200:
                return api_response
        except requests.RequestException as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise HTTPException(status_code=502, detail="Unable to fetch poster from Tautulli.")


@router.get("/posters/{rating_key}")
def get_poster(rating_key: int, request: Request):
    token = request.session.get("plex_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not DB_URL or not TAUTULLI_API_KEY or (not TAUTULLI_URL and not TAUTULLI_API_URL):
        raise HTTPException(status_code=500, detail="Poster proxy is not configured.")

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT media_type, thumb_path, parent_thumb_path, grandparent_thumb_path
            FROM library
            WHERE rating_key = %s
            """,
            (rating_key,),
        )
        row = cur.fetchone()
    except Exception as exc:
        print("💥 Poster lookup DB error:", repr(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch poster metadata.")
    finally:
        if cur is not None and not cur.closed:
            cur.close()
        if conn is not None and not conn.closed:
            conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Poster not found.")

    poster_path = resolve_poster_path_from_row(row)
    if not poster_path:
        raise HTTPException(status_code=404, detail="Poster not found.")

    try:
        image_response = _fetch_tautulli_image(poster_path)
    except HTTPException:
        raise
    except requests.RequestException as exc:
        print("💥 Poster proxy upstream error:", repr(exc))
        raise HTTPException(status_code=502, detail="Unable to fetch poster from Tautulli.")

    content_type = image_response.headers.get("Content-Type", "image/jpeg")
    return Response(
        content=image_response.content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
